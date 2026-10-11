"""Fail-closed adapters for the existing NEXO ingress routes.

The adapters normalize route-specific deliveries into items for the existing
single Tower Writer. They do not apply Tower mutations, select a replacement
Writer, discover credentials, or resolve live CONTROL. A caller may construct
``RouteGrant`` only after resolving current policy and capabilities; tests use
synthetic grants and fixtures exclusively.
"""
from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import hmac
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import inbox_client, operation_receipts
from .drive_transport import TowerConflict, TowerTransportError


_ROUTES = frozenset({"drive", "gateway", "github", "sheet_spool"})
_ENVELOPE_FIELDS = frozenset({"kind", "source", "created_at", "intent_id", "payload", "supersedes"})
_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|\+00:00)")
# Writer owns this suffix namespace for generated children; reserve it only in
# the shared Gateway identity namespace so unrelated legacy route IDs survive.
_BATCH_CHILD_ID_SUFFIX = re.compile(r"\.batch-(?:0|[1-9][0-9]*)$")
# Sheet spool identities are gateway:sheet-<stable_id>; reserve that prefix on
# the general Gateway feed so only the dedicated Sheet adapter can emit it.
_GATEWAY_RESERVED_ROUTE_PREFIXES = ("sheet-",)
_FOREIGN_DRIVE_INTENT_PREFIXES = ("gateway:", "github:", "runner:")
_TERMINAL_WRITER_OUTCOMES = frozenset({"APPLIED", "ALREADY_APPLIED", "REJECTED_TERMINAL"})
_PRIVATE_STAGING_KINDS = frozenset({
    "BOARD_POST", "HANDOFF", "NEXO_HANDOFF", "AGENT_HANDOFF",
    "HANDOFF_TRANSITION", "HANDOFF_ACK", "HANDOFF_DONE", "HANDOFF_FAILED",
    "NEXO_THOUGHT",
})


@dataclass(frozen=True)
class RouteGrant:
    """Explicit caller-supplied policy decision; never loaded from this module.

    ``state`` and ``policy_revision`` must come from a trusted, current policy
    resolver. Supplying a grant in a test does not establish live authorization.
    """

    route: str
    principal: str
    runtime_role: str
    policy_revision: str
    allowed_kinds: frozenset[str] = field(default_factory=frozenset)
    enabled: bool = False
    state: str = "UNVERIFIED"
    public_sanitized: bool = False

    def require(self, route: str, *, kind: str | None = None) -> None:
        if (route not in _ROUTES or self.route != route or self.enabled is not True
                or self.state != "ACTIVE"
                or not isinstance(self.principal, str) or not self.principal.strip()
                or not isinstance(self.runtime_role, str) or not self.runtime_role.strip()
                or not isinstance(self.policy_revision, str) or not self.policy_revision.strip()
                or not isinstance(self.allowed_kinds, (set, frozenset, tuple, list))
                or not self.allowed_kinds
                or any(not isinstance(value, str) or not value.strip() for value in self.allowed_kinds)):
            raise PermissionError("INGRESS_ROUTE_NOT_AUTHORIZED")
        if kind is not None:
            allowed = {str(value).upper() for value in self.allowed_kinds}
            if str(kind).upper() not in allowed:
                raise PermissionError("EVENT_KIND_NOT_AUTHORIZED")


def _parse_object(value: Any, error: str) -> dict:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(error) from None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            raise ValueError(error) from None
    if not isinstance(value, dict):
        raise ValueError(error)
    return value


def _batch_time_is_valid(value: Any) -> bool:
    if not isinstance(value, str) or not _UTC_TIMESTAMP.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _canonical_event(envelope: dict, grant: RouteGrant, *, identity: str,
                     batch_child: bool = False) -> dict:
    """Validate one event through inbox_client's Writer envelope contract."""
    if (not isinstance(envelope, dict)
            or any(not isinstance(key, str) or key.startswith("_") for key in envelope)):
        raise ValueError("UNTRUSTED_TRANSPORT_METADATA")
    if set(envelope) - _ENVELOPE_FIELDS:
        raise ValueError("UNSUPPORTED_ENVELOPE_FIELDS")
    kind = envelope.get("kind")
    grant.require(grant.route, kind=kind if isinstance(kind, str) else "")
    if envelope.get("source") != grant.runtime_role:
        raise PermissionError("RUNTIME_ROLE_NOT_AUTHORIZED")
    if not isinstance(identity, str) or not identity or identity != identity.strip() or len(identity) > 200:
        raise ValueError("STABLE_INTENT_ID_REQUIRED")
    if (not batch_child and identity.startswith("gateway:")
            and _BATCH_CHILD_ID_SUFFIX.search(identity)):
        raise ValueError("AMBIGUOUS_BATCH_CHILD_ID")
    supplied = envelope.get("intent_id")
    if supplied is not None and supplied != identity:
        raise ValueError("STABLE_INTENT_ID_CONFLICT")
    event = {**envelope, "intent_id": identity}
    if str(kind).upper() != "BATCH":
        inbox_client.prepare(event, runtime_role=grant.runtime_role,
                             allowed_kinds={str(value) for value in grant.allowed_kinds})
        return event

    # Gateway/Git feed batches are split by the existing Writer. Validate the
    # parent shape here without sending BATCH through Drive's per-child client.
    if not _batch_time_is_valid(event.get("created_at")):
        raise ValueError("CREATED_AT_UTC_REQUIRED")
    payload = event.get("payload")
    children = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(children, list) or not children:
        raise ValueError("BATCH_ITEMS_REQUIRED")
    if event.get("supersedes") is not None and (
            not isinstance(event["supersedes"], str) or not event["supersedes"]
            or event["supersedes"] != event["supersedes"].strip()):
        raise ValueError("SUPERSEDES_ID_INVALID")
    normalized = []
    for index, child in enumerate(children):
        if not isinstance(child, dict):
            raise ValueError("BATCH_CHILD_INVALID")
        child_identity = f"{identity}.batch-{index}"
        normalized.append(_canonical_event(child, grant, identity=child_identity,
                                           batch_child=True))
    event["payload"] = {**payload, "items": normalized}
    return event


def _writer_item(envelope: dict, *, source: str, name: str, inbox_id: str) -> dict:
    return {
        **envelope,
        "_inbox_source": source,
        "_inbox_name": name,
        "_inbox_id": inbox_id,
    }


def _reject_foreign_drive_intent(envelope: dict) -> None:
    intent_id = envelope.get("intent_id")
    if (isinstance(intent_id, str)
            and intent_id.startswith(_FOREIGN_DRIVE_INTENT_PREFIXES)):
        raise ValueError("DRIVE_FOREIGN_ROUTE_INTENT_ID")


def _valid_github_path(path: Any) -> bool:
    return (isinstance(path, str) and path.startswith("inbox/") and path.endswith(".json")
            and "\\" not in path and "\x00" not in path
            and all(part not in {"", ".", ".."} for part in path.split("/")))


def _assert_public_staging_event(envelope: dict) -> None:
    kind = str(envelope.get("kind") or "").upper().replace("-", "_").replace(" ", "_")
    if kind in _PRIVATE_STAGING_KINDS:
        raise PermissionError("PRIVATE_EVENT_REQUIRES_DRIVE")
    if kind == "BATCH":
        children = (envelope.get("payload") or {}).get("items")
        if not isinstance(children, list):
            raise ValueError("BATCH_ITEMS_REQUIRED")
        for child in children:
            if not isinstance(child, dict):
                raise ValueError("BATCH_CHILD_INVALID")
            _assert_public_staging_event(child)


def _batch_child_events(envelope: dict) -> list[dict]:
    if str(envelope.get("kind") or "").upper() != "BATCH":
        return []
    payload = envelope.get("payload")
    children = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(children, list):
        return []
    events = []
    for child in children:
        if not isinstance(child, dict):
            continue
        events.append(child)
        events.extend(_batch_child_events(child))
    return events


class DriveInboxAdapter:
    """Adapter for the existing private Drive inbox and raw-upload client."""

    route = "drive"

    def __init__(self, *, grant: RouteGrant | None = None, inbox: Any = None):
        self.grant = grant
        self.inbox = inbox

    def _grant(self) -> RouteGrant:
        if self.grant is None:
            raise PermissionError("INGRESS_ROUTE_NOT_AUTHORIZED")
        self.grant.require(self.route)
        return self.grant

    def collect(self, entries: list[dict] | None = None) -> list[dict]:
        grant = self._grant()
        if entries is None:
            if self.inbox is None:
                raise RuntimeError("DRIVE_INBOX_CLIENT_REQUIRED")
            entries = self.inbox.pending()
        if not isinstance(entries, list):
            raise ValueError("DRIVE_INBOX_ENTRY_LIST_REQUIRED")
        result = []
        top_level_events = {}
        batch_child_events = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("DRIVE_INBOX_ENTRY_INVALID")
            file_id, name, envelope = entry.get("id"), entry.get("name"), entry.get("payload")
            if not isinstance(file_id, str) or not file_id.strip() or not isinstance(name, str) or not name:
                raise ValueError("DRIVE_INBOX_IDENTITY_REQUIRED")
            envelope = _parse_object(envelope, "DRIVE_INBOX_ENVELOPE_INVALID")
            _reject_foreign_drive_intent(envelope)
            identity = (envelope["intent_id"] if "intent_id" in envelope
                        else "drive:" + file_id)
            normalized = _canonical_event(envelope, grant, identity=identity)
            intent_id = normalized["intent_id"]
            if (intent_id in top_level_events
                    and top_level_events[intent_id] != normalized):
                raise ValueError("AMBIGUOUS_BATCH_CHILD_ID")
            top_level_events[intent_id] = normalized
            for child in _batch_child_events(normalized):
                child_id = child.get("intent_id")
                if (child_id in batch_child_events
                        and batch_child_events[child_id] != child):
                    raise ValueError("AMBIGUOUS_BATCH_CHILD_ID")
                batch_child_events[child_id] = child
            result.append(_writer_item(normalized, source="DRIVE", name=name, inbox_id=file_id))
        if any(top_level_events[child_id] != child
               for child_id, child in batch_child_events.items()
               if child_id in top_level_events):
            raise ValueError("AMBIGUOUS_BATCH_CHILD_ID")
        return result

    def prepare(self, envelope: dict) -> dict:
        grant = self._grant()
        kind = envelope.get("kind") if isinstance(envelope, dict) else None
        grant.require(self.route, kind=kind if isinstance(kind, str) else "")
        if isinstance(envelope, dict):
            _reject_foreign_drive_intent(envelope)
        return inbox_client.prepare(envelope, runtime_role=grant.runtime_role,
                                    allowed_kinds={str(value) for value in grant.allowed_kinds})

    def submit(self, envelope: dict, transport: Any, *, tower: dict,
               journal: dict | None) -> dict:
        prepared = self.prepare(envelope)
        # deliver() owns deterministic create/readback/journal handling. Its
        # DELIVERED result is intentionally distinct from a Writer receipt.
        return inbox_client.deliver(prepared, transport, tower=tower, journal=journal)

    @staticmethod
    def receipt_status(tower: dict, prepared: dict) -> dict:
        return inbox_client.receipt_status(tower, prepared)

    def acknowledge(self, item: dict, receipt: dict) -> None:
        grant = self._grant()
        if self.inbox is None:
            raise RuntimeError("DRIVE_INBOX_CLIENT_REQUIRED")
        _require_terminal_receipt(item, receipt)
        file_id = item.get("_inbox_id") if isinstance(item, dict) else None
        if not isinstance(file_id, str) or not file_id:
            raise ValueError("DRIVE_INBOX_IDENTITY_REQUIRED")
        # Authorization is checked before the route-specific acknowledgement.
        grant.require(self.route)
        self.inbox.mark_processed(file_id)


class GatewayVerifiedFeedAdapter:
    """Adapter for the existing post-verifier Gateway JSON feed, not a Sheet API."""

    route = "gateway"

    def __init__(self, *, grant: RouteGrant | None = None):
        self.grant = grant

    def collect(self, feed: bytes | str | dict, *, verified: bool = False) -> list[dict]:
        if self.grant is None:
            raise PermissionError("INGRESS_ROUTE_NOT_AUTHORIZED")
        grant = self.grant
        grant.require(self.route)
        if grant.public_sanitized is not True:
            raise PermissionError("SANITIZED_PUBLIC_PAYLOAD_REQUIRED")
        if verified is not True:
            raise PermissionError("VERIFIED_GATEWAY_FEED_REQUIRED")
        document = _parse_object(feed, "GATEWAY_FEED_INVALID")
        entries = document.get("items")
        if not isinstance(entries, list):
            raise ValueError("GATEWAY_FEED_ITEMS_REQUIRED")
        result = []
        for row in entries:
            if not isinstance(row, dict):
                raise ValueError("GATEWAY_FEED_ENTRY_INVALID")
            gateway_id, envelope = row.get("id"), row.get("envelope")
            if not operation_receipts.is_safe_gateway_id(gateway_id):
                raise ValueError("GATEWAY_ID_INVALID")
            if gateway_id.startswith(_GATEWAY_RESERVED_ROUTE_PREFIXES):
                raise ValueError("GATEWAY_ID_RESERVED_FOR_SHEET")
            if not isinstance(envelope, dict):
                raise ValueError("GATEWAY_ENVELOPE_INVALID")
            identity = "gateway:" + gateway_id
            normalized = _canonical_event(envelope, grant, identity=identity)
            _assert_public_staging_event(normalized)
            result.append(_writer_item(normalized, source="GATEWAY",
                                       name="gw-" + gateway_id, inbox_id=identity))
        return result


class GitHubStagingAdapter:
    """Compatibility adapter for Git staging; requires active policy and public data proof."""

    route = "github"

    def __init__(self, *, client: Any = None, grant: RouteGrant | None = None):
        self.client = client
        self.grant = grant

    def _grant(self) -> RouteGrant:
        if self.grant is None:
            raise PermissionError("INGRESS_ROUTE_NOT_AUTHORIZED")
        self.grant.require(self.route)
        if self.grant.public_sanitized is not True:
            raise PermissionError("SANITIZED_PUBLIC_PAYLOAD_REQUIRED")
        return self.grant

    def collect(self, entries: list[dict] | None = None) -> list[dict]:
        grant = self._grant()
        if entries is None:
            if self.client is None:
                raise RuntimeError("GITHUB_STAGING_CLIENT_REQUIRED")
            entries = self.client.pending()
        if not isinstance(entries, list):
            raise ValueError("GITHUB_STAGING_ENTRY_LIST_REQUIRED")
        result = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("GITHUB_STAGING_ENTRY_INVALID")
            path, envelope = entry.get("path"), entry.get("payload")
            if not _valid_github_path(path):
                raise ValueError("GITHUB_STAGING_PATH_INVALID")
            envelope = _parse_object(envelope, "GITHUB_STAGING_ENVELOPE_INVALID")
            identity = "github:" + path
            normalized = _canonical_event(envelope, grant, identity=identity)
            _assert_public_staging_event(normalized)
            result.append(_writer_item(normalized, source="GITHUB",
                                       name=entry.get("name") or path.rsplit("/", 1)[-1],
                                       inbox_id=identity))
        return result

    def acknowledge(self, entry: dict, receipt: dict) -> None:
        grant = self._grant()
        if not isinstance(entry, dict) or not _valid_github_path(entry.get("path")):
            raise ValueError("GITHUB_STAGING_ENTRY_INVALID")
        envelope = entry.get("payload", entry.get("envelope"))
        if not isinstance(envelope, dict):
            raise ValueError("GITHUB_STAGING_ENVELOPE_INVALID")
        normalized = _canonical_event(envelope, grant, identity="github:" + entry["path"])
        _assert_public_staging_event(normalized)
        _require_terminal_receipt(normalized, receipt)
        if self.client is None:
            raise RuntimeError("GITHUB_STAGING_CLIENT_REQUIRED")
        readback = getattr(self.client, "read_pending_fresh", None)
        if not callable(readback):
            raise RuntimeError("GITHUB_STAGING_READBACK_BINDING_REQUIRED")
        grant.require(self.route)
        self.client.mark_processed(entry)
        remaining = readback()
        if (not isinstance(remaining, list)
                or any(isinstance(row, dict) and row.get("path") == entry["path"]
                       for row in remaining)):
            raise RuntimeError("GITHUB_STAGING_ACK_READBACK_REQUIRED")


class SheetSpoolAdapter:
    """Adapter for the historical CSV-exported Sheet spool.

    The source workflow exports ``stable_id,envelope_b64url`` rows, converts
    each to a ``sheet-<stable_id>`` Gateway item, and later CAS-updates a
    separate acknowledgement ledger. This adapter only parses a supplied
    export; it does not fetch the Sheet, acquire credentials, or activate the
    retired workflow. A caller must provide an explicit route grant, verifier
    assertion, and SHA-256 readback for the exact export bytes. The hash is
    checked at ingress but is not added to Writer payloads, so an unrelated
    new row cannot change an existing row's idempotency identity.
    """

    route = "sheet_spool"
    _COLUMNS = frozenset({"stable_id", "envelope_b64url"})

    def __init__(self, *, grant: RouteGrant | None = None, ack_store: Any = None):
        self.grant = grant
        self.ack_store = ack_store

    def _grant(self) -> RouteGrant:
        if self.grant is None:
            raise PermissionError("INGRESS_ROUTE_NOT_AUTHORIZED")
        grant = self.grant
        grant.require(self.route)
        if grant.public_sanitized is not True:
            raise PermissionError("SANITIZED_PUBLIC_PAYLOAD_REQUIRED")
        return grant

    def collect(self, csv_export: bytes | str, *, verified: bool = False,
                expected_sha256: str | None = None,
                acknowledged: set[str] | frozenset[str] = frozenset()) -> list[dict]:
        grant = self._grant()
        if verified is not True:
            raise PermissionError("VERIFIED_SHEET_EXPORT_REQUIRED")
        if isinstance(csv_export, bytes):
            export_bytes = csv_export
            try:
                csv_export = csv_export.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise ValueError("SHEET_SPOOL_CSV_INVALID") from None
        elif isinstance(csv_export, str):
            export_bytes = csv_export.encode("utf-8")
        else:
            raise ValueError("SHEET_SPOOL_CSV_INVALID")
        if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
            raise ValueError("SHEET_EXPORT_REVISION_REQUIRED")
        if not hmac.compare_digest(hashlib.sha256(export_bytes).hexdigest(), expected_sha256.lower()):
            raise ValueError("SHEET_EXPORT_READBACK_MISMATCH")
        try:
            reader = csv.DictReader(io.StringIO(csv_export, newline=""))
            if (not reader.fieldnames
                    or any(not isinstance(column, str) or not column.strip() for column in reader.fieldnames)
                    or len(set(reader.fieldnames)) != len(reader.fieldnames)
                    or not self._COLUMNS.issubset(reader.fieldnames)):
                raise ValueError("SHEET_SPOOL_COLUMNS_REQUIRED")
            result = []
            observed = set()
            for row in reader:
                stable_id = str(row.get("stable_id") or "").strip().lower()
                raw = str(row.get("envelope_b64url") or "").strip()
                if not stable_id and not raw:
                    continue
                if not stable_id or not raw or None in row:
                    raise ValueError("SHEET_SPOOL_ROW_INVALID")
                gateway_id = "sheet-" + stable_id
                if not operation_receipts.is_safe_gateway_id(gateway_id):
                    raise ValueError("SHEET_SPOOL_STABLE_ID_INVALID")
                if stable_id in observed:
                    raise ValueError("SHEET_SPOOL_DUPLICATE_STABLE_ID")
                observed.add(stable_id)
                if stable_id in acknowledged:
                    continue
                if not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", raw):
                    raise ValueError("SHEET_SPOOL_ENVELOPE_INVALID")
                padded = raw + "=" * ((4 - len(raw) % 4) % 4)
                try:
                    decoded = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
                    envelope = _parse_object(decoded, "SHEET_SPOOL_ENVELOPE_INVALID")
                except (UnicodeEncodeError, binascii.Error):
                    raise ValueError("SHEET_SPOOL_ENVELOPE_INVALID") from None
                identity = "gateway:" + gateway_id
                normalized = _canonical_event(envelope, grant, identity=identity)
                _assert_public_staging_event(normalized)
                item = _writer_item(normalized, source="GATEWAY", name=gateway_id,
                                    inbox_id=identity)
                result.append(item)
            return result
        except csv.Error:
            raise ValueError("SHEET_SPOOL_CSV_INVALID") from None

    def acknowledge(self, item: dict, receipt: dict, *, expected_version: str) -> dict:
        grant = self._grant()
        if self.ack_store is None:
            raise RuntimeError("SHEET_ACK_CAS_BINDING_REQUIRED")
        _require_terminal_receipt(item, receipt)
        inbox_id = item.get("_inbox_id") if isinstance(item, dict) else None
        if item.get("_inbox_source") != "GATEWAY":
            raise ValueError("SHEET_ACK_SOURCE_MISMATCH")
        intent_id = item.get("intent_id")
        if not isinstance(inbox_id, str) or inbox_id != intent_id:
            raise ValueError("SHEET_ACK_IDENTITY_MISMATCH")
        prefix = "gateway:sheet-"
        if not intent_id.startswith(prefix):
            raise ValueError("SHEET_SPOOL_IDENTITY_REQUIRED")
        stable_id = intent_id[len(prefix):]
        if not operation_receipts.is_safe_gateway_id("sheet-" + stable_id):
            raise ValueError("SHEET_SPOOL_STABLE_ID_INVALID")
        if not isinstance(expected_version, str) or not expected_version.strip():
            raise ValueError("SHEET_ACK_EXPECTED_VERSION_REQUIRED")
        grant.require(self.route)
        write = self.ack_store.compare_and_swap(
            stable_id=stable_id, expected_version=expected_version,
            receipt_id=receipt["receipt_id"],
        )
        if not isinstance(write, dict) or write.get("accepted") is not True:
            if isinstance(write, dict) and write.get("conflict") is True:
                raise TowerConflict("SHEET_ACK_VERSION_CONFLICT")
            raise RuntimeError("SHEET_ACK_WRITE_UNCONFIRMED")
        readback = self.ack_store.read(stable_id)
        if (not isinstance(readback, dict)
                or readback.get("stable_id") != stable_id
                or readback.get("receipt_id") != receipt["receipt_id"]
                or not isinstance(readback.get("version"), str)
                or not readback["version"]
                or readback.get("version") != write.get("version")):
            raise RuntimeError("SHEET_ACK_READBACK_REQUIRED")
        return readback


def _require_terminal_receipt(item: dict, receipt: dict) -> None:
    if not isinstance(receipt, dict):
        raise ValueError("WRITER_TERMINAL_RECEIPT_REQUIRED")
    outcome = receipt.get("outcome")
    if not isinstance(outcome, str) or outcome not in _TERMINAL_WRITER_OUTCOMES:
        raise ValueError("WRITER_TERMINAL_RECEIPT_REQUIRED")
    if (not isinstance(item, dict)
            or not {"kind", "source", "created_at", "payload"}.issubset(item)):
        raise ValueError("WRITER_RECEIPT_EVENT_REQUIRED")
    expected = item.get("intent_id") if isinstance(item, dict) else None
    if not isinstance(expected, str) or receipt.get("intent_id") != expected:
        raise ValueError("WRITER_RECEIPT_IDENTITY_MISMATCH")
    try:
        operation_receipts._validate(receipt)
    except (operation_receipts.OperationReceiptError, TypeError):
        raise ValueError("WRITER_RECEIPT_INVALID") from None
    if (receipt.get("effect_id") != operation_receipts.envelope_effect_id(expected)
            or not re.fullmatch(r"OR-[a-f0-9]{32}", str(receipt.get("receipt_id") or ""))
            or not all(isinstance(receipt.get(key), str)
                       and re.fullmatch(r"sha256:[a-f0-9]{64}", receipt[key])
                       for key in ("source_revision", "result_revision"))):
        raise ValueError("WRITER_READBACK_RECEIPT_REQUIRED")
    expected_stage = "APPLIED" if receipt["outcome"] in {"APPLIED", "ALREADY_APPLIED"} else "DELIVERED"
    if receipt.get("stage") != expected_stage:
        raise ValueError("WRITER_RECEIPT_STATE_INVALID")
    expected_hash = operation_receipts.payload_hash(item, trusted_transport=True)
    if receipt.get("payload_sha256") != expected_hash:
        raise ValueError("WRITER_RECEIPT_PAYLOAD_MISMATCH")


def retry_disposition(error: BaseException) -> str:
    """Classify same-route recovery; this API never selects a different route."""
    retry = getattr(error, "retry_condition", None)
    status = getattr(error, "status_code", None)
    if (isinstance(error, PermissionError) or status in {401, 403}
            or retry == "OPERATOR_REAUTHORIZATION"):
        return "STOP_AUTHORIZATION"
    if (isinstance(error, (TimeoutError, ConnectionError, TowerConflict))
            or retry in {"AFTER_TRANSPORT_RECOVERY", "RECONCILE_TOWER_BEFORE_REAPPLY"}):
        return "RECONCILE_SAME_ROUTE"
    return "STOP"
