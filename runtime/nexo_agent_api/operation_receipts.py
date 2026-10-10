"""Durable, private per-effect receipts for the canonical Tower Writer."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .tower_paths import entity_path


CONTRACT = "OPERATION_RECEIPT_V1"
RECEIPT_ROOT = Path("operations/receipts")
LEGACY_RECEIPT_ROOT = Path("mutations/receipts/operations")
STAGES = frozenset({"STAGED", "DELIVERED", "APPLIED", "RESERVED", "EXECUTED", "REVIEWED", "PROJECTED"})
OUTCOMES = frozenset({"APPLIED", "ALREADY_APPLIED", "REJECTED_TERMINAL", "DEFERRED_DEPENDENCY", "RETRYABLE_TRANSPORT"})
PUBLIC_OUTCOME_ALLOWLIST = OUTCOMES
PUBLIC_RETRY_CONDITIONS = frozenset({
    "SOURCE_REVISION_CHANGED",
    "AFTER_TRANSPORT_RECOVERY",
    "OPERATOR_REAUTHORIZATION",
    "RECONCILE_TOWER_BEFORE_REAPPLY",
})
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_GATEWAY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RECEIPT_ID_RE = re.compile(r"^OR-[0-9a-f]{32}$")
_RETRYABLE_DEPENDENCY_CODES = frozenset({
    "DEPENDENCY_UNRESOLVED",
    "DEPENDENCY_MISSING",
    "MISSING_DEPENDENCY",
    "DEPENDENCY_NOT_READY",
    "EQUIVALENT_EXECUTION_ALREADY_RESERVED",
    "TEST_TERMINAL_OR_RESERVED",
    "BATTERY_CAPACITY_FULL",
    "BATTERY_NOT_FOUND",
    "CONTEST_TEST_NOT_FOUND",
})


class OperationReceiptError(ValueError):
    """The private receipt ledger is unreadable or violates its contract."""


def is_safe_gateway_id(value: Any) -> bool:
    """Gateway IDs are public transport identities, limited to a bounded token alphabet."""
    return isinstance(value, str) and bool(_SAFE_GATEWAY_ID_RE.fullmatch(value))


def _trusted_child_intent(item: dict) -> str | None:
    parent = item.get("_inbox_id")
    child = item.get("_inbox_child_id")
    name = item.get("_inbox_name")
    if not all(isinstance(value, str) and value for value in (parent, child, name)):
        return None
    match = re.fullmatch(rf"{re.escape(parent)}\.batch-([0-9]+)", child)
    if not match or not name.endswith("-" + match.group(1)):
        return None
    return child


def private_operator_envelope(item: dict) -> bool:
    """Authority changes stay private even when submitted by a public gateway.

    A mixed batch must not export its parent identity or aggregate outcome.
    Public siblings still retain their own ordinary per-envelope receipts.
    """
    pending, seen = [item], set()
    while pending:
        current = pending.pop()
        if not isinstance(current, dict) or id(current) in seen:
            continue
        seen.add(id(current))
        kind = str(current.get("kind") or "").strip().upper()
        payload = current.get("payload")
        if not isinstance(payload, dict):
            continue
        if kind == "OPERATOR_INTENT" and str(payload.get("action") or "").strip().upper() in {
            "APPROVE_AUTONOMY_MANDATE", "REVOKE_AUTONOMY_MANDATE",
        }:
            return True
        if kind == "BATCH" and isinstance(payload.get("items"), list):
            pending.extend(payload["items"])
    return False


def public_gateway_envelope(item: dict, intent: str) -> bool:
    """Whether transport metadata identifies a canonical public gateway envelope."""
    if private_operator_envelope(item):
        return False
    if str(item.get("_inbox_source") or "").strip().upper() != "GATEWAY":
        return False
    if not isinstance(intent, str) or not intent.startswith("gateway:"):
        return False
    parent_intent = item.get("_inbox_id")
    if not isinstance(parent_intent, str) or not parent_intent.startswith("gateway:"):
        return False
    gateway_id = parent_intent[len("gateway:"):]
    if not is_safe_gateway_id(gateway_id):
        return False
    child_intent = _trusted_child_intent(item)
    expected_intent = child_intent or parent_intent
    if intent != expected_intent:
        return False
    name = item.get("_inbox_name")
    return isinstance(name, str) and bool(re.fullmatch(rf"gw-{re.escape(gateway_id)}(?:-[0-9]+)?", name))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def context_revision(root: str | Path) -> str:
    """Fallback context revision for a failed proposal with no resolved effect."""
    return dependency_context_revision(root, {})


_REFERENCE_KINDS = {
    "test_id": "test", "target_test_id": "test", "prerequisite_test_id": "test",
    "dependency_test_id": "test", "depends_on": "test", "work_id": "work", "source_work_id": "work",
    "parent_work_id": "work", "artifact_id": "artifact", "source_artifact_id": "artifact",
}


def dependency_context_revision(root: str | Path, request: dict, reason_code: Any = None) -> str:
    """Fingerprint only the entity/docs/files relevant to this effect's retry condition."""
    root = Path(root)
    paths: dict[str, Path] = {}
    if isinstance(request, dict):
        kind, name = request.get("entity_kind"), request.get("entity_name")
        if kind and name:
            try:
                path = entity_path(root, str(kind), str(name))
                paths[path.relative_to(root).as_posix()] = path
            except (ValueError, OSError):
                pass

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    entity_kind = _REFERENCE_KINDS.get(str(key).lower())
                    if entity_kind:
                        refs = child if isinstance(child, list) else [child]
                        for ref in refs:
                            if isinstance(ref, (str, int)) and str(ref).strip():
                                try:
                                    path = entity_path(root, entity_kind, str(ref))
                                    paths[path.relative_to(root).as_posix()] = path
                                except (ValueError, OSError):
                                    pass
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(request)

    codes = str(reason_code or "").upper()
    if any(token in codes for token in ("BATTERY", "RESERVATION", "CAPACITY")):
        path = root / "evolution" / "batteries.json"
        paths[path.relative_to(root).as_posix()] = path
    if isinstance(request, dict) and (request.get("battery_id") or request.get("kind") == "BATTERY_STATUS"):
        path = root / "evolution" / "batteries.json"
        paths[path.relative_to(root).as_posix()] = path
    if any(token in codes for token in ("ARTIFACT", "MANIFEST", "DATA_RELEASE", "CAPABILITY")):
        for relative in ("manifests/artifacts.json", "manifests/capabilities.json"):
            path = root / relative
            paths[relative] = path

    # Read the recipe/code smoke tests only for referenced tests. These files
    # are part of readiness and may appear/change outside the Tower snapshot.
    recipe_root = Path(__import__("os").environ.get("NEXO_RECIPE_ROOT", "nexo-one/executor-runtime/recipes"))
    if not recipe_root.is_absolute():
        recipe_root = Path.cwd() / recipe_root
    for relative, path in list(paths.items()):
        if "/test/" not in ("/" + relative.replace("\\", "/")) or not path.is_file():
            continue
        try:
            test = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        recipe = str(test.get("recipe") or "")
        if recipe:
            for recipe_path in (recipe_root / (recipe + ".py"), recipe_root / "smoke" / (recipe + ".json")):
                key = "external/" + recipe_path.name + ("/smoke" if recipe_path.parent.name == "smoke" else "")
                paths[key] = recipe_path
        if test.get("data_binding") or test.get("input_binding"):
            for rel in ("manifests/artifacts.json", "manifests/capabilities.json"):
                manifest = root / rel
                paths[rel] = manifest

    rows = []
    for key, path in sorted(paths.items()):
        try:
            content = path.read_bytes()
            rows.append({"path": key, "exists": True, "sha256": "sha256:" + hashlib.sha256(content).hexdigest()})
        except OSError:
            rows.append({"path": key, "exists": False})
    return sha256({"contract": CONTRACT, "context": rows})


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


_TRUSTED_INBOX_ANNOTATIONS = frozenset({"_inbox_source", "_inbox_name", "_inbox_id", "_inbox_child_id"})
_TRUSTED_CAPABILITY_FIELDS = frozenset({
    "_runner_battery_status_token",
    "_writer_dispatch_token",
    "_autonomy_human_authority",
    "_autonomy_authority",
    "_scientific_review_authority",
    "_runner_observation_authority",
})


def _is_runner_status_capability(value: Any) -> bool:
    # This singleton is created only by the in-process runner-result adapter.
    # A JSON producer can supply the same field name, but cannot recreate its
    # object identity, so its value remains part of the semantic fingerprint.
    from .scientific_integrity import RUNNER_BATTERY_STATUS_TOKEN

    return value is RUNNER_BATTERY_STATUS_TOKEN


def _is_writer_dispatch_capability(value: Any) -> bool:
    from .scientific_integrity import WRITER_DISPATCH_TOKEN

    return value is WRITER_DISPATCH_TOKEN


def _is_trusted_capability(field: str, value: Any) -> bool:
    if field == "_scientific_review_authority":
        from .autonomy import WRITER_AUTHORITY
        return value is WRITER_AUTHORITY
    if field in {"_autonomy_human_authority", "_autonomy_authority"}:
        from .autonomy import HUMAN_AUTHORITY, WRITER_AUTHORITY
        return value is HUMAN_AUTHORITY or (field == "_autonomy_authority" and value is WRITER_AUTHORITY)
    if field in {"_runner_battery_status_token", "_runner_observation_authority"}:
        return _is_runner_status_capability(value)
    if field == "_writer_dispatch_token":
        return _is_writer_dispatch_capability(value)
    return False


def payload_hash(payload: Any, *, trusted_transport: bool = False) -> str:
    """Hash canonical JSON, omitting only trusted transport and runtime capability metadata."""
    if trusted_transport and isinstance(payload, dict):
        payload = {
            key: value for key, value in payload.items()
            if key not in _TRUSTED_INBOX_ANNOTATIONS
            and not (key in _TRUSTED_CAPABILITY_FIELDS and _is_trusted_capability(key, value))
        }
    return sha256({"contract": CONTRACT, "payload": payload})


def intent_id(item: dict, label: str) -> str:
    identity = (item.get("intent_id") or _trusted_child_intent(item) or item.get("_inbox_id")
                or item.get("request_id") or label)
    identity = str(identity).strip()
    if not identity:
        raise OperationReceiptError("OPERATION_INTENT_ID_REQUIRED")
    return identity


def effect_id(request: dict, *, intent: str, index: int) -> str:
    value = request.get("request_id") or request.get("effect_id")
    if value:
        return str(value)
    # Position is the fallback effect identity; payload bytes are fingerprinted
    # separately so changing content cannot silently create a new effect.
    return "effect-" + sha256({"contract": CONTRACT, "intent_id": intent, "index": index})[7:39]


def envelope_effect_id(intent: str) -> str:
    """Stable receipt identity for the submitted semantic envelope itself."""
    return "envelope-" + sha256({"contract": CONTRACT, "intent_id": intent})[7:39]


def classify_reason(reason: Any) -> tuple[str, str | None]:
    """Only explicit dependency and reservation codes are deferred; all other validation is terminal."""
    if isinstance(reason, dict):
        code = reason.get("code") or reason.get("reason_code")
    else:
        code = reason
    code = str(code or "UNKNOWN_REJECTION").strip().upper()
    fragments = {part.strip() for part in re.split(r"[^A-Z0-9_]+", code) if part.strip()}
    dependency = code in _RETRYABLE_DEPENDENCY_CODES or bool(fragments.intersection(_RETRYABLE_DEPENDENCY_CODES))
    if code.startswith("TEST_NOT_EXECUTABLE:") and "DEPENDENCY_UNRESOLVED" in code:
        dependency = True
    return ("DEFERRED_DEPENDENCY" if dependency else "REJECTED_TERMINAL", code)


def _validate(receipt: dict) -> None:
    required = {
        "contract", "receipt_id", "intent_id", "payload_sha256", "effect_id", "stage", "outcome", "reason_code",
        "source_revision", "result_revision", "occurred_at", "observed_at", "visibility", "retry_condition", "supersedes",
    }
    if not isinstance(receipt, dict) or not required.issubset(receipt):
        raise OperationReceiptError("OPERATION_RECEIPT_FIELDS_MISSING")
    if receipt.get("contract") != CONTRACT:
        raise OperationReceiptError("OPERATION_RECEIPT_CONTRACT_INVALID")
    if not all(isinstance(receipt.get(key), str) and receipt[key].strip() for key in ("receipt_id", "intent_id", "effect_id")):
        raise OperationReceiptError("OPERATION_RECEIPT_ID_INVALID")
    if not isinstance(receipt.get("payload_sha256"), str) or not _HASH_RE.fullmatch(receipt["payload_sha256"]):
        raise OperationReceiptError("OPERATION_RECEIPT_PAYLOAD_HASH_INVALID")
    if receipt.get("stage") not in STAGES or receipt.get("outcome") not in OUTCOMES:
        raise OperationReceiptError("OPERATION_RECEIPT_STATE_INVALID")
    if receipt.get("visibility") not in {"PRIVATE", "PUBLIC"}:
        raise OperationReceiptError("OPERATION_RECEIPT_VISIBILITY_INVALID")
    for key in ("source_revision", "result_revision", "reason_code", "supersedes"):
        if receipt.get(key) is not None and not isinstance(receipt.get(key), str):
            raise OperationReceiptError(f"OPERATION_RECEIPT_{key.upper()}_INVALID")
    if receipt.get("retry_condition") is not None and not isinstance(receipt.get("retry_condition"), dict):
        raise OperationReceiptError("OPERATION_RECEIPT_RETRY_CONDITION_INVALID")
    if isinstance(receipt.get("retry_condition"), dict):
        condition = receipt["retry_condition"]
        if (condition.get("kind") not in PUBLIC_RETRY_CONDITIONS
                or set(condition) - {"kind", "source_revision", "detail"}
                or (condition.get("source_revision") is not None and not isinstance(condition.get("source_revision"), str))
                or (condition.get("detail") is not None and not isinstance(condition.get("detail"), str))):
            raise OperationReceiptError("OPERATION_RECEIPT_RETRY_CONDITION_INVALID")
    if receipt["outcome"] in {"DEFERRED_DEPENDENCY", "RETRYABLE_TRANSPORT"} and not receipt.get("retry_condition"):
        raise OperationReceiptError("OPERATION_RECEIPT_RETRY_CONDITION_REQUIRED")
    for key in ("occurred_at", "observed_at"):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            raise OperationReceiptError(f"OPERATION_RECEIPT_{key.upper()}_INVALID")


def build_receipt(
    *, intent: str, payload_sha256: str, effect: str, outcome: str,
    source_revision: str | None, result_revision: str | None,
    reason_code: str | None = None, retry_condition: dict | None = None,
    supersedes: str | None = None, visibility: str = "PRIVATE",
    occurred_at: str | None = None, observed_at: str | None = None,
) -> dict:
    outcome = str(outcome).upper()
    stage = "APPLIED" if outcome in {"APPLIED", "ALREADY_APPLIED"} else "DELIVERED"
    if outcome == "RETRYABLE_TRANSPORT":
        stage = "STAGED"
    occurred_at = occurred_at or now_utc()
    observed_at = observed_at or now_utc()
    identity = {
        "intent_id": str(intent), "payload_sha256": str(payload_sha256), "effect_id": str(effect),
        "stage": stage, "outcome": outcome, "occurred_at": occurred_at,
    }
    receipt = {
        "contract": CONTRACT,
        "receipt_id": "OR-" + hashlib.sha256(_canonical(identity)).hexdigest()[:32],
        "intent_id": identity["intent_id"], "payload_sha256": identity["payload_sha256"],
        "effect_id": identity["effect_id"], "stage": stage, "outcome": outcome,
        "reason_code": reason_code, "source_revision": source_revision, "result_revision": result_revision,
        "occurred_at": occurred_at, "observed_at": observed_at, "visibility": visibility,
        "retry_condition": retry_condition, "supersedes": supersedes,
    }
    _validate(receipt)
    return receipt


def _receipt_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for relative in (RECEIPT_ROOT, LEGACY_RECEIPT_ROOT):
        directory = root / relative
        if directory.exists():
            if not directory.is_dir():
                raise OperationReceiptError("OPERATION_RECEIPT_LEDGER_PATH_INVALID")
            paths.extend(directory.glob("*.json"))
    # The first implementation stored receipts directly in mutations/receipts.
    legacy = root / "mutations" / "receipts"
    if legacy.is_dir():
        paths.extend(path for path in legacy.glob("*.json") if path.is_file())
    return sorted(set(paths))


def load_receipts(root: str | Path) -> list[dict]:
    """Dual-read current and legacy receipt locations; unreadable ledgers are errors, never misses."""
    records: list[dict] = []
    for path in _receipt_paths(Path(root)):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise OperationReceiptError("OPERATION_RECEIPT_LEDGER_READ_FAILED") from exc
        if not isinstance(value, dict) or not {"receipt_id", "intent_id", "payload_sha256", "effect_id", "outcome"}.issubset(value):
            if path.parent == Path(root) / RECEIPT_ROOT:
                raise OperationReceiptError("OPERATION_RECEIPT_LEDGER_INVALID")
            continue
        # Older entries lacked the optional retry/supersession metadata.
        legacy = dict(value)
        legacy.setdefault("contract", CONTRACT)
        legacy.setdefault("reason_code", None)
        legacy.setdefault("source_revision", None)
        legacy.setdefault("result_revision", None)
        legacy.setdefault("occurred_at", legacy.get("observed_at") or "legacy")
        legacy.setdefault("observed_at", legacy.get("occurred_at") or "legacy")
        legacy.setdefault("visibility", "PRIVATE")
        legacy.setdefault("retry_condition", None)
        legacy.setdefault("supersedes", None)
        legacy.setdefault("stage", "APPLIED" if legacy.get("outcome") in {"APPLIED", "ALREADY_APPLIED"} else "DELIVERED")
        try:
            _validate(legacy)
        except OperationReceiptError as exc:
            raise OperationReceiptError("OPERATION_RECEIPT_LEDGER_INVALID") from exc
        records.append(legacy)
    return sorted(records, key=lambda row: (str(row.get("occurred_at") or ""), str(row.get("receipt_id") or "")))


def persist_receipt(root: str | Path, receipt: dict) -> Path:
    _validate(receipt)
    directory = Path(root) / RECEIPT_ROOT
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{receipt['receipt_id']}.json"
    body = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != body:
            raise OperationReceiptError("OPERATION_RECEIPT_ID_COLLISION")
        return path
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(path)
    return path


def latest_receipt(root: str | Path, *, intent: str, payload_sha256: str, effect: str) -> dict | None:
    matches = [row for row in load_receipts(root)
               if row["intent_id"] == intent and row["payload_sha256"] == payload_sha256 and row["effect_id"] == effect]
    return matches[-1] if matches else None


def envelope_receipts(root: str | Path, *, intent: str) -> list[dict]:
    effect = envelope_effect_id(intent)
    return [row for row in load_receipts(root)
            if row["intent_id"] == intent and row["effect_id"] == effect]


def latest_envelope_receipt(root: str | Path, *, intent: str, payload_sha256: str) -> dict | None:
    matches = [row for row in envelope_receipts(root, intent=intent)
               if row["payload_sha256"] == payload_sha256]
    return matches[-1] if matches else None


def terminal_payload_conflict(root: str | Path, *, intent: str, payload_sha256: str, effect: str, supersedes: str | None) -> dict | None:
    rows = load_receipts(root)
    terminal = [row for row in rows if row["outcome"] == "REJECTED_TERMINAL"]
    same_identity = [row for row in terminal if row["intent_id"] == intent
                     and row["payload_sha256"] != payload_sha256]
    if same_identity:
        # Changed bytes never reuse an intent, even when the submitter points
        # supersedes back at its own terminal record.
        return same_identity[-1]
    if supersedes:
        linked = next((row for row in terminal if row["receipt_id"] == supersedes), None)
        if linked and linked["intent_id"] != intent and linked["payload_sha256"] != payload_sha256:
            return None
        return linked or {"receipt_id": supersedes, "reason_code": "SUPERSEDES_RECEIPT_NOT_FOUND"}
    same_effect = [row for row in terminal if row["effect_id"] == effect
                   and row["payload_sha256"] != payload_sha256]
    return same_effect[-1] if same_effect else None


def retry_allowed(receipt: dict, source_revision: str | None) -> bool:
    if receipt.get("outcome") == "DEFERRED_DEPENDENCY":
        condition = receipt.get("retry_condition") or {}
        return condition.get("kind") == "SOURCE_REVISION_CHANGED" and source_revision != receipt.get("source_revision")
    if receipt.get("outcome") == "RETRYABLE_TRANSPORT":
        condition = receipt.get("retry_condition") or {}
        if condition.get("kind") == "AFTER_TRANSPORT_RECOVERY":
            return True
        if condition.get("kind") == "RECONCILE_TOWER_BEFORE_REAPPLY":
            return source_revision != receipt.get("source_revision")
        # Authentication and permission errors require explicit operator action.
        return False
    return False


def replay_receipt(receipt: dict, *, observed_at: str | None = None) -> dict:
    """Return a transient confirmation without writing a redundant Tower revision."""
    outcome = "ALREADY_APPLIED" if receipt.get("outcome") in {"APPLIED", "ALREADY_APPLIED"} else receipt.get("outcome")
    replay = dict(receipt)
    replay["outcome"] = outcome
    replay["stage"] = "APPLIED" if outcome == "ALREADY_APPLIED" else receipt.get("stage")
    replay["observed_at"] = observed_at or now_utc()
    _validate(replay)
    return replay


def public_receipt(receipt: dict) -> dict | None:
    """Export only explicitly-public, canonical gateway-envelope receipts."""
    if not isinstance(receipt, dict) or receipt.get("visibility") != "PUBLIC":
        return None
    if receipt.get("outcome") not in PUBLIC_OUTCOME_ALLOWLIST:
        return None
    try:
        _validate(receipt)
    except OperationReceiptError:
        return None
    intent = receipt.get("intent_id")
    if (not isinstance(intent, str) or not intent.startswith("gateway:")
            or not is_safe_gateway_id(intent[len("gateway:"):])
            or receipt.get("effect_id") != envelope_effect_id(intent)
            or not isinstance(receipt.get("receipt_id"), str)
            or not _RECEIPT_ID_RE.fullmatch(receipt["receipt_id"])):
        return None
    for revision in (receipt.get("source_revision"), receipt.get("result_revision")):
        if revision is not None and (not isinstance(revision, str) or not _HASH_RE.fullmatch(revision)):
            return None
    retry = receipt.get("retry_condition")
    safe_retry = None
    if isinstance(retry, dict) and retry.get("kind") in PUBLIC_RETRY_CONDITIONS:
        safe_retry = {"kind": retry["kind"]}
    allowed = (
        "contract", "receipt_id", "intent_id", "payload_sha256", "effect_id", "stage", "outcome",
        "reason_code", "source_revision", "result_revision", "occurred_at", "observed_at", "supersedes",
    )
    exported = {key: receipt.get(key) for key in allowed}
    # The public schema requires this field. Private validation details never
    # leave the boundary; the public representation is explicitly null.
    exported["reason_code"] = None
    supersedes = exported.get("supersedes")
    if supersedes is not None and (not isinstance(supersedes, str) or not _RECEIPT_ID_RE.fullmatch(supersedes)):
        exported["supersedes"] = None
    exported.update({"visibility": "PUBLIC", "retry_condition": safe_retry})
    return exported


def public_outcome(receipts: list[dict]) -> str | None:
    """Summarize only fully resolved envelope effects; partial effects remain unacknowledged."""
    if not receipts:
        return None
    outcomes = [str(row.get("outcome") or "") for row in receipts]
    if any(value not in OUTCOMES for value in outcomes):
        return None
    if "RETRYABLE_TRANSPORT" in outcomes:
        return "RETRYABLE_TRANSPORT"
    if "DEFERRED_DEPENDENCY" in outcomes:
        return "DEFERRED_DEPENDENCY"
    if "REJECTED_TERMINAL" in outcomes:
        return "REJECTED_TERMINAL"
    if set(outcomes) == {"APPLIED"}:
        return "APPLIED"
    return "ALREADY_APPLIED"


def legacy_ack_matches(acked: Any, receipts: Any, path: str, fingerprint: str) -> bool:
    """Dual-read legacy `acked` and string/dict `receipts` cursors by exact hash."""
    def value_hash(value: Any) -> Any:
        return value.get("fingerprint") if isinstance(value, dict) else value
    return value_hash((acked or {}).get(path)) == fingerprint or value_hash((receipts or {}).get(path)) == fingerprint
