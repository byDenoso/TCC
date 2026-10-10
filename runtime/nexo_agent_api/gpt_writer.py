"""Tower writer for a runtime without Drive credentials (ChatGPT's Python sandbox).

ChatGPT's Drive connector does the I/O (read the Tower, check the revision,
update_file on the same id, read back); this module does the rest offline with
the same rules as ``scripts/nexo_tower.py apply``:

    python nexo_gpt_writer.py apply  TOWER.json PROPOSALS.json OUT.json
    python nexo_gpt_writer.py verify TOWER.json [EXPECTED_FINGERPRINT]
    python nexo_gpt_writer.py frontier TOWER.json [ROADMAP_ID]   (what to execute next)
    python nexo_gpt_writer.py handoff TOWER.json list ROLE   (messages addressed to one role)

PROPOSALS.json is a list of inbox proposal envelopes ({kind, source, payload,
created_at}) and/or raw writer requests ({entity_kind, ...} or {document, ...}).
The result JSON lists before/after fingerprints, receipts and the proposals that
were rejected (those stay in the inbox).
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import shutil
from typing import Any
from pathlib import Path

from . import evolution
from . import operation_receipts as operation_receipts
from .inbox_apply import ProposalError, proposal_to_requests
from .live_tower import LIVE_TOWER_NAME, materialize_live_tower, read_live_tower_bytes, verify_live_tower
from .tower_apply import apply_requests


def _is_request(item: dict) -> bool:
    return "document" in item or "entity_kind" in item or item.get("nexo_operation") in {
        "HANDOFF_CREATE", "HANDOFF_TRANSITION", "EXECUTION_OBSERVATION_ASSESSMENT", "OPERATIONAL_CANARY",
    }


def _claims_operational_receipt(request: dict) -> bool:
    changes = request.get("changes") if isinstance(request.get("changes"), dict) else {}
    return (str(changes.get("kind") or "").upper() == "OPERATIONAL_RECEIPT"
            or str(request.get("entity_name") or "").upper().startswith("OPERATIONAL_RECEIPT::")
            or str(request.get("event_type") or "").upper() == "OPERATIONAL_RECEIPT_RECORDED")


def _root_revision(root: Path) -> str:
    return verify_live_tower(read_live_tower_bytes((root / LIVE_TOWER_NAME).read_bytes()))


def _operational_status(root: Path) -> dict[str, Any]:
    """Expose implemented contracts and verified C01 selection without private evidence."""
    from . import operational_canary

    contract_dir = Path(__file__).with_name("contracts")
    receipt_schema = contract_dir / "OPERATION_RECEIPT_V1.json"
    canary_schema = contract_dir / "OPERATIONAL_CANARY_V1.schema.json"
    atlas_schema = contract_dir / "ATLAS_OBSERVATION_V1.json"
    atlas_implementation = (
        Path(__file__).resolve().parents[2].parent
        / "Pantheon" / "nexo-one" / "src" / "data" / "atlasObservation.ts"
    )
    contracts = {
        operation_receipts.CONTRACT: {
            "schema": "PRESENT" if receipt_schema.is_file() else "MISSING",
            "implementation": "TCC_RUNTIME",
            "deployment": "UNVERIFIED",
        },
        operational_canary.CANARY_CONTRACT: {
            "schema": "PRESENT" if canary_schema.is_file() else "MISSING",
            "implementation": "TCC_RUNTIME",
            "deployment": "UNVERIFIED",
        },
        "ATLAS_OBSERVATION_V1": {
            "schema": "PRESENT" if atlas_schema.is_file() else "MISSING",
            "implementation": "PANTHEON_SOURCE" if atlas_implementation.is_file() else "UNVERIFIED",
            "deployment": "UNVERIFIED",
        },
    }
    return {
        "operational_contracts": contracts,
        "C01": operational_canary.operational_status(root),
    }


def _apply_one_request(root: Path, item: dict, request: dict, *,
                       operational_receipt_validated: bool = False,
                       operational_work_authorized: bool = False) -> dict:
    changes = request.get("changes") or {}
    reserved = (changes.get("kind") == "NEXO_OPERATIONAL_WORK_V1"
                or str(request.get("entity_name") or "").startswith("OPERATIONAL-CONTROL-"))
    if reserved and not operational_work_authorized:
        return {"accepted": False, "issue": {"code": "OPERATIONAL_WORK_REQUIRES_WRITER_SERVICE"}}
    if _claims_operational_receipt(request) and not operational_receipt_validated:
        return {"accepted": False,
                "issue": {"code": "OPERATIONAL_RECEIPT_REQUIRES_STRICT_CONVERTER"}}
    operation = request.get("nexo_operation")
    if operation in {"ENXAME_EVENT", "ENXAME_REGISTER_TEST", "NEXO_MEMORY_ENTRY", "NEXO_PROJECT_EVENT"}:
        # Only a private envelope conversion can enter the specialized protocol.
        if (str(item.get("_inbox_source") or "").upper() != "DRIVE"
                or item.get("kind") != operation or item.get("source") != request.get("role")
                or _is_request(item)):
            return {"accepted": False, "issue": {"code": "PRIVATE_PROTOCOL_ENVELOPE_REQUIRED"}}
        from . import enxame, continuity
        try:
            module = enxame if operation.startswith("ENXAME_") else continuity
            receipt = module.apply(root, request)
            if receipt.get("accepted", True) and not receipt.get("issue"):
                from .live_tower import publish_live_tower
                publish_live_tower(root)
            return receipt
        except (ValueError, TypeError, KeyError) as exc:
            code = str(exc)
            if not code or len(code) > 150 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:" for c in code):
                code = "PRIVATE_PROTOCOL_INVALID"
            return {"accepted": False, "issue": {"code": code}}
    if operation == "EXECUTION_OBSERVATION_ASSESSMENT":
        from .execution_assessment import AssessmentError, apply_assessment
        from .service import TowerAgentIssue

        if str(item.get("_inbox_source") or "").upper() != "RUNNER_OBSERVATION":
            return {"accepted": False, "issue": {"code": "VERIFIED_RUNNER_OBSERVATION_REQUIRED"}}
        try:
            receipt = apply_assessment(root, request.get("assessment"))
            if receipt.get("status") != "NO_OP":
                from .live_tower import publish_live_tower

                publish_live_tower(root)
            return receipt
        except AssessmentError as exc:
            return {"accepted": False, "issue": {"code": str(exc)}}
        except TowerAgentIssue as exc:
            return {"accepted": False, "issue": {"code": exc.code, "details": exc.details}}

    if operation == "OPERATIONAL_CANARY":
        from . import operational_canary

        try:
            receipt = dict(operational_canary.apply_writer_canary_request(root, request))
            if receipt.get("accepted", True) and not receipt.get("issue"):
                from .live_tower import publish_live_tower

                publish_live_tower(root)
            return receipt
        except (ValueError, TypeError, OSError):
            return {"accepted": False, "issue": {"code": "OPERATIONAL_CANARY_REJECTED"}}

    if operation not in {"HANDOFF_CREATE", "HANDOFF_TRANSITION"}:
        receipt = apply_requests(root, [request])[0]
        if receipt.get("accepted", True) and not receipt.get("issue"):
            from .live_tower import publish_live_tower

            publish_live_tower(root)
        return receipt
    if str(item.get("_inbox_source") or "").upper() != "DRIVE":
        return {"accepted": False, "issue": {"code": "PRIVATE_HANDOFF_REQUIRES_DRIVE_INBOX"}}

    from . import AgentService, TowerAgentIssue

    try:
        service = AgentService(root)
        if operation == "HANDOFF_CREATE":
            envelope = request.get("handoff")
            if not isinstance(envelope, dict):
                raise TypeError("handoff must be a JSON object")
            receipt = service.emit_handoff(**envelope)
        else:
            transition = request.get("transition")
            if not isinstance(transition, dict):
                raise TypeError("transition must be a JSON object")
            receipt = service.transition_handoff(
                transition.get("handoff_id", ""),
                state=transition.get("state", ""),
                writer_role=transition.get("writer_role", ""),
            )
            if (root / "bootstrap").is_dir():
                from .views import materialize_role_views

                materialize_role_views(root)
        from .live_tower import publish_live_tower

        publish_live_tower(root)
        return receipt
    except TowerAgentIssue as exc:
        return {"accepted": False, "issue": {"code": exc.code, "message": exc.message, "details": exc.details}}
    except (TypeError, AttributeError):
        return {"accepted": False, "issue": {"code": "HANDOFF_ENVELOPE_INVALID"}}


def _append_effect_receipt(report: dict, receipt: dict) -> None:
    report["operation_receipts"].append(receipt)
    public = operation_receipts.public_receipt(receipt)
    if public and not any(row.get("receipt_id") == public.get("receipt_id") for row in report["public_operation_receipts"]):
        report["public_operation_receipts"].append(public)


def _build_effect_receipt(
    *, root: Path, item: dict, label: str, request: dict, request_index: int,
    intent: str, source_revision: str, outcome: str, reason_code: str | None = None,
    retry_condition: dict | None = None, supersedes: str | None = None,
    result_revision: str | None = None, persist: bool = True,
) -> dict:
    payload = request if request else item
    effect = operation_receipts.effect_id(request, intent=intent, index=request_index)
    payload_digest = operation_receipts.payload_hash(payload, trusted_transport=True)
    receipt = operation_receipts.build_receipt(
        intent=intent, payload_sha256=payload_digest, effect=effect, outcome=outcome,
        source_revision=source_revision,
        result_revision=result_revision if result_revision is not None else _root_revision(root),
        reason_code=reason_code, retry_condition=retry_condition, supersedes=supersedes,
    )
    if persist:
        operation_receipts.persist_receipt(root, receipt)
    return receipt


def _build_envelope_receipt(
    *, root: Path, item: dict, intent: str, source_revision: str,
    outcome: str, reason_code: str | None = None, retry_condition: dict | None = None,
    supersedes: str | None = None, result_revision: str | None = None,
) -> dict:
    receipt = operation_receipts.build_receipt(
        intent=intent,
        payload_sha256=operation_receipts.payload_hash(item, trusted_transport=True),
        effect=operation_receipts.envelope_effect_id(intent),
        outcome=outcome,
        source_revision=source_revision,
        result_revision=result_revision if result_revision is not None else _root_revision(root),
        reason_code=reason_code,
        retry_condition=retry_condition,
        supersedes=supersedes,
        visibility=("PUBLIC" if operation_receipts.public_gateway_envelope(item, intent) else "PRIVATE"),
    )
    operation_receipts.persist_receipt(root, receipt)
    return receipt


def _existing_effect(root: Path, *, intent: str, request: dict, payload: dict,
                     request_index: int, source_revision: str, supersedes: str | None) -> dict | None:
    effect = operation_receipts.effect_id(request, intent=intent, index=request_index)
    payload_digest = operation_receipts.payload_hash(request if request else payload, trusted_transport=True)
    prior = operation_receipts.latest_receipt(root, intent=intent, payload_sha256=payload_digest, effect=effect)
    if prior:
        if prior["outcome"] in {"APPLIED", "ALREADY_APPLIED", "REJECTED_TERMINAL"}:
            return operation_receipts.replay_receipt(prior)
        if prior["outcome"] == "DEFERRED_DEPENDENCY" and not operation_receipts.retry_allowed(prior, source_revision):
            return operation_receipts.replay_receipt(prior)
        if prior["outcome"] == "RETRYABLE_TRANSPORT" and not operation_receipts.retry_allowed(prior, source_revision):
            return operation_receipts.replay_receipt(prior)
        return None
    conflict = operation_receipts.terminal_payload_conflict(
        root, intent=intent, payload_sha256=payload_digest, effect=effect, supersedes=supersedes,
    )
    if conflict:
        conflict_reason = conflict.get("reason_code") or "TERMINAL_PAYLOAD_CHANGED_WITHOUT_NEW_IDENTITY"
        return operation_receipts.build_receipt(
            intent=intent, payload_sha256=payload_digest, effect=effect, outcome="REJECTED_TERMINAL",
            source_revision=source_revision, result_revision=source_revision,
            reason_code=conflict_reason,
            supersedes=conflict["receipt_id"],
        )
    return None


def _runner_battery_identity(payload: dict) -> str:
    """Identify a source observation, never its position or mutable result content.

    Older collectors omit run_attempt/artifact_id, so source execution timestamps
    and per-test attempt IDs retain reruns without treating changed result bytes
    as a new observation. Missing source fields stay missing (fail conservatively).
    """
    fields = ("battery_id", "status", "run_ref", "run_id", "run_attempt", "attempt_id",
              "artifact_id", "artifact_sha256", "started_at", "completed_at")
    identity = {key: payload[key] for key in fields if key in payload}
    if "started_tests" in payload:
        identity["started_tests"] = payload["started_tests"]
    sources = []
    for result in (payload.get("results") if isinstance(payload.get("results"), list) else []):
        if isinstance(result, dict):
            sources.append({key: result[key] for key in (
                "test_id", "attempt_id", "run_attempt", "artifact_id", "artifact_sha256",
                "recipe_sha256", "started_at", "executed_at",
            ) if key in result})
    identity["result_sources"] = sorted(sources, key=lambda row: json.dumps(row, sort_keys=True))
    return "runner:battery:v2:" + operation_receipts.sha256(identity)[7:]


def _migrate_runner_battery_receipt(root: Path, item: dict, intent: str) -> dict | None:
    """Bind exact legacy observations to v2 without reopening their retry gates.

    Legacy receipts contain hashes, not source metadata. Only an exact envelope
    (or pre-conversion failure) hash can prove the match; battery ID alone cannot.
    Keep the old receipt immutable and persist a private, linked v2 envelope once.
    """
    payload = item.get("payload")
    if (item.get("kind") != "BATTERY_STATUS" or item.get("source") != "WRITER_ROBOT"
            or item.get("_inbox_source") != "RUNNER_OBSERVATION"
            or not isinstance(payload, dict) or intent != _runner_battery_identity(payload)):
        return None
    digest = operation_receipts.payload_hash(item, trusted_transport=True)
    pattern = re.compile(r"runner:battery:[0-9]+:" + re.escape(str(payload.get("battery_id") or "")))
    matches = []
    for row in operation_receipts.load_receipts(root):
        old_intent = row["intent_id"]
        if (not pattern.fullmatch(old_intent) or row["payload_sha256"] != digest
                or row["effect_id"] not in {
                    operation_receipts.envelope_effect_id(old_intent),
                    operation_receipts.effect_id({}, intent=old_intent, index=0),
                }):
            continue
        matches.append(row)
    if not matches:
        return None
    # Historical duplicates may span several positions. A durable terminal result
    # must not be hidden by a later deferred duplicate from another position.
    terminal = [row for row in matches if row["outcome"] == "REJECTED_TERMINAL"]
    applied = [row for row in matches if row["outcome"] in {"APPLIED", "ALREADY_APPLIED"}]
    prior = (terminal or applied or matches)[-1]
    migrated = operation_receipts.build_receipt(
        intent=intent, payload_sha256=digest, effect=operation_receipts.envelope_effect_id(intent),
        outcome=prior["outcome"], source_revision=prior["source_revision"],
        result_revision=prior["result_revision"], reason_code=prior["reason_code"],
        retry_condition=prior["retry_condition"], supersedes=prior["receipt_id"],
        occurred_at=prior["occurred_at"],
    )
    operation_receipts.persist_receipt(root, migrated)
    return migrated


def apply_to_tower(tower_raw: bytes, items: list[dict], *, readiness_evaluator=None, operational_work_authorized: bool = False,
                   verified_human_intents: frozenset[str] | None = None,
                   verified_capacity_observation: dict | None = None) -> tuple[bytes | None, dict]:
    before = verify_live_tower(read_live_tower_bytes(tower_raw))
    contract_versions = {"operation_receipts": operation_receipts.CONTRACT}
    try:
        from .operational_canary import CANARY_CONTRACT

        contract_versions["operational_canary"] = CANARY_CONTRACT
    except (ImportError, AttributeError):
        pass
    report: dict = {"before": before, "applied": [], "rejected": [], "receipts": [], "handled": [],
                    "operation_receipts": [], "public_operation_receipts": [],
                    "contracts": contract_versions}
    with tempfile.TemporaryDirectory(prefix="nexo-gpt-writer-") as work:
        root, _ = materialize_live_tower(tower_raw, Path(work) / "TOWER_V06")
        from . import autonomy
        if isinstance(verified_capacity_observation, dict):
            for request in autonomy.capacity_requests(root, {"quota": verified_capacity_observation.get("quota")}):
                apply_requests(root, [request])
        for request in autonomy.capacity_requests(root, verified_capacity_observation):
            apply_requests(root, [request])
        # Fixed policy may consume an existing authorized review before any new
        # reservation changes its prospective sample.
        from .capacity_guard import facts as capacity_facts, review_requests as capacity_review_requests, REGISTRY as CAPACITY_REVIEWS
        def refresh_capacity_policy():
            proof = capacity_facts(root)
            if not proof:
                return
            receipts = apply_requests(root, capacity_review_requests(root))
            if any(not row.get("accepted") for row in receipts):
                return
            quota = autonomy.read(root, autonomy.CAPACITY_DOC).get("quota") or {}
            growth = autonomy.capacity_requests(root, {"quota": quota, "parallelism": proof["next_parallelism"],
                                                      "battery_refs": proof["battery_refs"],
                                                      "review_ref": CAPACITY_REVIEWS + "#" + proof["id"]})
            receipts.extend(apply_requests(root, growth))
            report["receipts"].extend(receipts)
            report["autonomy_capacity"] = {"review_id": proof["id"], "parallelism": autonomy.parallelism(root)}
        refresh_capacity_policy()
        # Refresh/compensate the private canary monitor only at the mutating
        # Writer boundary. Read-only status and standalone readiness calls do
        # not write this file; the normal pack/CAS/readback persists this state.
        try:
            from .operational_canary import refresh_tower_monitor

            monitor_status = refresh_tower_monitor(root)
            if (monitor_status.get("heartbeat_refreshed")
                    or monitor_status.get("rollback_readback") == "PASS"):
                from .live_tower import publish_live_tower

                publish_live_tower(root)
        except Exception:
            # The production readiness wrapper independently fails closed if
            # the monitor cannot be verified. Do not abort unrelated proposals.
            pass
        # A BATCH is applied item by item, so later envelopes see earlier ones (e.g. canary then canonize).
        flat: list[dict] = []
        for item in items:
            item = autonomy.attach_human_authority(item, verified_human_intents)
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            if str(item.get("kind") or "").upper() == "BATCH" and isinstance(payload.get("items"), list):
                base = item.get("_inbox_name") or "batch"
                parent_id = str(item.get("_inbox_id") or "").strip()
                child_intents = []
                if (str(item.get("_inbox_source") or "").upper() == "GATEWAY"
                        and parent_id.startswith("gateway:")):
                    gateway_id = parent_id[len("gateway:"):]
                    child_intents = [f"{parent_id}.batch-{i}" for i, sub in enumerate(payload["items"])
                                     if isinstance(sub, dict)]
                    report.setdefault("gateway_batch_intents", {})[gateway_id] = child_intents
                child_position = 0
                children = []
                for i, sub in enumerate(payload["items"]):
                    if not isinstance(sub, dict):
                        continue
                    child_intent = (child_intents[child_position] if child_intents
                                    else (f"{parent_id}.batch-{i}" if parent_id else None))
                    child_position += 1
                    children.append({**sub, "_inbox_source": item.get("_inbox_source"),
                                     "_inbox_name": f"{base}-{i}", "_inbox_id": parent_id or None,
                                     "_inbox_child_id": child_intent})
                flat += children
            else:
                # Child receipt identity is Writer-owned transport metadata.
                # A top-level envelope cannot mint a new intent by supplying it.
                flat.append({key: value for key, value in item.items() if key != "_inbox_child_id"})
        items = flat
        changed_receipt_ledger = False
        for index, item in enumerate(items):
            label = item.get("_inbox_name") or item.get("request_id") or f"item-{index}"
            intent = operation_receipts.intent_id(item, str(label))
            supersedes = str(item.get("supersedes") or ((item.get("payload") or {}).get("supersedes") if isinstance(item.get("payload"), dict) else "") or "").strip() or None
            envelope_payload_hash = operation_receipts.payload_hash(item, trusted_transport=True)
            envelope_source = operation_receipts.dependency_context_revision(root, item)
            envelope_prior = operation_receipts.latest_envelope_receipt(
                root, intent=intent, payload_sha256=envelope_payload_hash,
            )
            if (envelope_prior is None and intent.startswith("runner:battery:v2:")
                    and not operation_receipts.envelope_receipts(root, intent=intent)):
                envelope_prior = _migrate_runner_battery_receipt(root, item, intent)
                if envelope_prior is not None:
                    changed_receipt_ledger = True
            if envelope_prior:
                if (envelope_prior["outcome"] in {"DEFERRED_DEPENDENCY", "RETRYABLE_TRANSPORT"}
                        and operation_receipts.retry_allowed(envelope_prior, envelope_source)):
                    pass  # Re-evaluate only after the recorded retry condition changed.
                else:
                    confirmation = operation_receipts.replay_receipt(envelope_prior)
                    _append_effect_receipt(report, confirmation)
                    if confirmation["outcome"] in {"APPLIED", "ALREADY_APPLIED"}:
                        report["applied"].append(label)
                        report["handled"].append(label)
                    elif confirmation["outcome"] == "REJECTED_TERMINAL":
                        report["rejected"].append({"item": label, "reason": confirmation.get("reason_code")})
                        report["handled"].append(label)
                    else:
                        report.setdefault("deferred", []).append({"item": label, "outcome": confirmation["outcome"]})
                    continue
            else:
                conflicting_envelopes = [row for row in operation_receipts.envelope_receipts(root, intent=intent)
                                         if row["payload_sha256"] != envelope_payload_hash]
                if conflicting_envelopes:
                    prior = conflicting_envelopes[-1]
                    row = _build_envelope_receipt(
                        root=root, item=item, intent=intent, source_revision=envelope_source,
                        outcome="REJECTED_TERMINAL", reason_code="TERMINAL_PAYLOAD_CHANGED_WITHOUT_NEW_IDENTITY",
                        supersedes=prior["receipt_id"], result_revision=envelope_source,
                    )
                    _append_effect_receipt(report, row)
                    changed_receipt_ledger = True
                    report["rejected"].append({"item": label, "reason": row["reason_code"]})
                    report["handled"].append(label)
                    continue
            try:
                raw_request = _is_request(item)
                requests = [item] if raw_request else proposal_to_requests(item, root)
                operational_receipt_validated = (
                    not raw_request and str(item.get("kind") or "").upper() == "OPERATIONAL_RECEIPT"
                )
            except ProposalError as exc:
                requests = []
                conversion_error = str(exc)
            else:
                conversion_error = None
            if not requests and conversion_error is None:
                conversion_error = "PROPOSAL_HAS_NO_EFFECTS"
            source_revision = operation_receipts.dependency_context_revision(root, item, conversion_error)
            savepoint = (root / LIVE_TOWER_NAME).read_bytes()
            if conversion_error is not None:
                prior = _existing_effect(root, intent=intent, request={}, payload=item, request_index=0,
                                         source_revision=source_revision, supersedes=supersedes)
                if prior:
                    _append_effect_receipt(report, prior)
                    if prior["outcome"] in {"APPLIED", "ALREADY_APPLIED"}:
                        report["applied"].append(label)
                        report["handled"].append(label)
                    elif prior["outcome"] == "REJECTED_TERMINAL":
                        report["rejected"].append({"item": label, "reason": prior.get("reason_code")})
                        report["handled"].append(label)
                    else:
                        report.setdefault("deferred", []).append({"item": label, "outcome": prior["outcome"]})
                    if prior.get("reason_code") in {"TERMINAL_PAYLOAD_CHANGED_WITHOUT_NEW_IDENTITY", "SUPERSEDES_RECEIPT_NOT_FOUND"}:
                        operation_receipts.persist_receipt(root, prior)
                        changed_receipt_ledger = True
                    continue
                if conversion_error == "PROPOSAL_HAS_NO_EFFECTS":
                    # Without a prior durable effect receipt, a no-op conversion
                    # cannot prove that an older Tower mutation completed.
                    outcome, reason_code = "DEFERRED_DEPENDENCY", "LEGACY_EFFECT_RESULT_UNVERIFIED"
                else:
                    outcome, reason_code = operation_receipts.classify_reason(conversion_error)
                row = _build_effect_receipt(
                    root=root, item=item, label=str(label), request={}, request_index=0, intent=intent,
                    source_revision=source_revision, outcome=outcome, reason_code=reason_code,
                    retry_condition={"kind": "SOURCE_REVISION_CHANGED", "source_revision": source_revision} if outcome == "DEFERRED_DEPENDENCY" else None,
                    supersedes=supersedes,
                )
                _append_effect_receipt(report, row)
                changed_receipt_ledger = True
                envelope_row = _build_envelope_receipt(
                    root=root, item=item, intent=intent, source_revision=source_revision,
                    outcome=outcome, reason_code=reason_code,
                    retry_condition={"kind": "SOURCE_REVISION_CHANGED", "source_revision": source_revision}
                    if outcome == "DEFERRED_DEPENDENCY" else None,
                    supersedes=envelope_prior["receipt_id"] if envelope_prior else None,
                )
                _append_effect_receipt(report, envelope_row)
                if outcome == "REJECTED_TERMINAL":
                    report["rejected"].append({"item": label, "reason": reason_code})
                    report["handled"].append(label)
                else:
                    report.setdefault("deferred", []).append({"item": label, "outcome": outcome})
                continue

            prior_rows: list[dict | None] = []
            retry_links: list[dict | None] = []
            effect_sources: list[str] = []
            for request_index, request in enumerate(requests):
                effect_source = operation_receipts.dependency_context_revision(root, request)
                effect_sources.append(effect_source)
                prior = _existing_effect(root, intent=intent, request=request, payload=item,
                                         request_index=request_index, source_revision=effect_source,
                                         supersedes=supersedes)
                if prior and prior.get("receipt_id", "").startswith("OR-") and prior.get("reason_code") in {
                    "TERMINAL_PAYLOAD_CHANGED_WITHOUT_NEW_IDENTITY", "SUPERSEDES_RECEIPT_NOT_FOUND"
                }:
                    operation_receipts.persist_receipt(root, prior)
                    changed_receipt_ledger = True
                prior_rows.append(prior)
                effect = operation_receipts.effect_id(request, intent=intent, index=request_index)
                payload_digest = operation_receipts.payload_hash(request, trusted_transport=True)
                retry_links.append(operation_receipts.latest_receipt(root, intent=intent,
                                                                     payload_sha256=payload_digest, effect=effect))
            terminal_prior = next((row for row in prior_rows if row and row["outcome"] == "REJECTED_TERMINAL"), None)
            runnable_requests = [request for request, row in zip(requests, prior_rows) if row is None]
            if terminal_prior and runnable_requests:
                # A previously rejected envelope stays closed as one unit. Do not apply
                # unrecorded siblings after a partial or damaged ledger read.
                for request_index, (request, prior) in enumerate(zip(requests, prior_rows)):
                    if prior is not None:
                        _append_effect_receipt(report, prior)
                        continue
                    row = _build_effect_receipt(
                        root=root, item=item, label=str(label), request=request, request_index=request_index,
                        intent=intent, source_revision=effect_sources[request_index], outcome="REJECTED_TERMINAL",
                        reason_code="ENVELOPE_ALREADY_TERMINAL", supersedes=terminal_prior["receipt_id"],
                    )
                    _append_effect_receipt(report, row)
                    operation_receipts.persist_receipt(root, row)
                    changed_receipt_ledger = True
                report["rejected"].append({"item": label, "reason": "ENVELOPE_ALREADY_TERMINAL"})
                report["handled"].append(label)
                envelope_row = _build_envelope_receipt(
                    root=root, item=item, intent=intent, source_revision=envelope_source,
                    outcome="REJECTED_TERMINAL", reason_code="ENVELOPE_ALREADY_TERMINAL",
                    supersedes=envelope_prior["receipt_id"] if envelope_prior else terminal_prior["receipt_id"],
                )
                _append_effect_receipt(report, envelope_row)
                changed_receipt_ledger = True
                continue

            if not runnable_requests:
                for prior in prior_rows:
                    if prior:
                        _append_effect_receipt(report, prior)
                envelope_outcome = operation_receipts.public_outcome([row for row in prior_rows if row])
                if envelope_outcome in {"APPLIED", "ALREADY_APPLIED"}:
                    report["applied"].append(label)
                    report["handled"].append(label)
                elif envelope_outcome == "REJECTED_TERMINAL":
                    report["rejected"].append({"item": label, "reason": terminal_prior.get("reason_code") if terminal_prior else "PRIOR_TERMINAL_RECEIPT"})
                    report["handled"].append(label)
                else:
                    report.setdefault("deferred", []).append({"item": label, "outcome": envelope_outcome or "UNRESOLVED"})
                continue

            receipts = []
            result_revisions: list[str] = []
            active_indices = [i for i, row in enumerate(prior_rows) if row is None]
            source_tower_revision = _root_revision(root)
            for request_index in active_indices:
                receipt = _apply_one_request(
                    root, item, requests[request_index],
                    operational_receipt_validated=operational_receipt_validated,
                    operational_work_authorized=operational_work_authorized,
                )
                receipts.append((request_index, receipt))
                result_revisions.append(_root_revision(root))
                if not receipt.get("accepted", True) or receipt.get("issue"):
                    break
            failed = [r for _, r in receipts if not r.get("accepted", True) or r.get("issue")]
            report["receipts"].extend(receipt for _, receipt in receipts)
            if failed:
                shutil.rmtree(root)
                root, _ = materialize_live_tower(savepoint, root)
                for _, receipt in receipts:
                    receipt["rolled_back"] = True
                issue = failed[0].get("issue")
                outcome, reason_code = operation_receipts.classify_reason(issue)
                failure_index = next((request_index for request_index, receipt in receipts
                                      if not receipt.get("accepted", True) or receipt.get("issue")), None)
                for request_index in active_indices:
                    request = requests[request_index]
                    prior = retry_links[request_index]
                    is_failure = request_index == failure_index
                    effect_outcome = outcome if is_failure or outcome == "REJECTED_TERMINAL" else "DEFERRED_DEPENDENCY"
                    effect_reason = reason_code if is_failure else (
                        "ENVELOPE_TERMINAL_ROLLBACK" if outcome == "REJECTED_TERMINAL" else "ENVELOPE_ROLLED_BACK"
                    )
                    row = _build_effect_receipt(
                        root=root, item=item, label=str(label), request=request, request_index=request_index,
                        intent=intent, source_revision=effect_sources[request_index], outcome=effect_outcome, reason_code=effect_reason,
                        retry_condition={"kind": "SOURCE_REVISION_CHANGED", "source_revision": effect_sources[request_index]} if effect_outcome == "DEFERRED_DEPENDENCY" else None,
                        supersedes=prior["receipt_id"] if prior else None,
                        result_revision=source_tower_revision,
                    )
                    _append_effect_receipt(report, row)
                    operation_receipts.persist_receipt(root, row)
                    changed_receipt_ledger = True
                for prior in prior_rows:
                    if prior:
                        _append_effect_receipt(report, prior)
                envelope_outcome = outcome
                envelope_retry = None
                if envelope_outcome == "DEFERRED_DEPENDENCY":
                    envelope_retry = {"kind": "SOURCE_REVISION_CHANGED", "source_revision": envelope_source}
                envelope_row = _build_envelope_receipt(
                    root=root, item=item, intent=intent, source_revision=envelope_source,
                    outcome=envelope_outcome, reason_code=reason_code, retry_condition=envelope_retry,
                    supersedes=envelope_prior["receipt_id"] if envelope_prior else None,
                    result_revision=source_tower_revision,
                )
                _append_effect_receipt(report, envelope_row)
                changed_receipt_ledger = True
                report["rejected"].append({"item": label, "reason": reason_code, "outcome": outcome})
                if outcome == "REJECTED_TERMINAL":
                    report["handled"].append(label)
                else:
                    report.setdefault("deferred", []).append({"item": label, "outcome": outcome})
            else:
                recorded_refusal = next((request.get("changes", {}).get("payload", {}).get("_not_applied_reason")
                                         for request in requests if str(request.get("changes", {}).get("kind", "")).startswith("UNAPPLIED_")), None)
                new_result_by_index = {idx: revision for (idx, _), revision in zip(receipts, result_revisions)}
                for request_index, prior in enumerate(prior_rows):
                    if prior:
                        _append_effect_receipt(report, prior)
                        continue
                    request = requests[request_index]
                    if recorded_refusal:
                        outcome, reason_code, retry_condition = "REJECTED_TERMINAL", str(recorded_refusal), None
                    else:
                        outcome = "ALREADY_APPLIED" if new_result_by_index.get(request_index) == source_tower_revision else "APPLIED"
                        reason_code, retry_condition = None, None
                    row = _build_effect_receipt(
                        root=root, item=item, label=str(label), request=request, request_index=request_index,
                        intent=intent, source_revision=effect_sources[request_index], outcome=outcome,
                        reason_code=reason_code, retry_condition=retry_condition,
                        supersedes=(retry_links[request_index]["receipt_id"] if retry_links[request_index] else supersedes),
                        result_revision=new_result_by_index.get(request_index, _root_revision(root)),
                    )
                    _append_effect_receipt(report, row)
                    operation_receipts.persist_receipt(root, row)
                    changed_receipt_ledger = True
                if recorded_refusal:
                    report["rejected"].append({"item":label, "reason":recorded_refusal, "recorded":True})
                    report["handled"].append(label)
                    envelope_row = _build_envelope_receipt(
                        root=root, item=item, intent=intent, source_revision=envelope_source,
                        outcome="REJECTED_TERMINAL", reason_code=str(recorded_refusal),
                        supersedes=envelope_prior["receipt_id"] if envelope_prior else None,
                    )
                    _append_effect_receipt(report, envelope_row)
                    changed_receipt_ledger = True
                else:
                    item_outcomes = []
                    for request_index, prior in enumerate(prior_rows):
                        if prior:
                            item_outcomes.append(prior["outcome"])
                        else:
                            item_outcomes.append("ALREADY_APPLIED" if new_result_by_index.get(request_index) == source_tower_revision else "APPLIED")
                    envelope_outcome = operation_receipts.public_outcome([{"outcome": value} for value in item_outcomes])
                    envelope_row = _build_envelope_receipt(
                        root=root, item=item, intent=intent, source_revision=envelope_source,
                        outcome=envelope_outcome or "DEFERRED_DEPENDENCY",
                        reason_code=None if envelope_outcome in {"APPLIED", "ALREADY_APPLIED"} else "ENVELOPE_EFFECTS_UNRESOLVED",
                        retry_condition={"kind": "SOURCE_REVISION_CHANGED", "source_revision": envelope_source}
                        if envelope_outcome in {"DEFERRED_DEPENDENCY", "RETRYABLE_TRANSPORT"} else None,
                        supersedes=envelope_prior["receipt_id"] if envelope_prior else None,
                    )
                    _append_effect_receipt(report, envelope_row)
                    changed_receipt_ledger = True
                    if envelope_outcome not in {"APPLIED", "ALREADY_APPLIED"}:
                        report.setdefault("deferred", []).append({"item": label, "outcome": envelope_outcome or "UNRESOLVED"})
                        continue
                    report["applied"].append(label)
                    report["handled"].append(label)

        if changed_receipt_ledger:
            from .live_tower import publish_live_tower

            publish_live_tower(root)

        # Contest lifecycle is mechanical: attacks cannot be attacked, and a completed
        # depth-1 attack closes the original from its frozen criterion result.
        contest_requests = evolution.contest_chain_reconcile_requests(root)
        if contest_requests:
            contest_receipts = apply_requests(root, contest_requests)
            contest_failed = [r for r in contest_receipts if not r.get("accepted", True) or r.get("issue")]
            report["receipts"].extend(contest_receipts)
            if contest_failed:
                report["rejected"].append({"item": "contest-chain-reconcile", "reason": contest_failed[0].get("issue")})
            else:
                report["reconciled_contests"] = [r.get("document") or r.get("entity_name") for r in contest_receipts]

        # A terminal result and a live execution phase describe incompatible
        # states. Repair only the cases for which the existing evidence planner
        # can bind the exact attempt, runner observation, result, and battery.
        # Ambiguous historical rows remain conflicts and are never guessed.
        from .execution_phase_reconciliation import build_reconciliation_plan

        phase_savepoint = (root / LIVE_TOWER_NAME).read_bytes()
        phase_error = None
        try:
            phase_plan = build_reconciliation_plan(root)
            phase_requests = phase_plan["requests"]
            phase_receipts = apply_requests(root, phase_requests) if phase_requests else []
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            phase_error = type(exc).__name__
            phase_plan = {"summary": {"terminal_running": None, "conflict_count": None}}
            phase_requests = []
            phase_receipts = [{"accepted": False, "issue": {
                "code": "EXECUTION_PHASE_RECONCILIATION_FAILED", "error_type": phase_error,
            }}]
        phase_failed = [r for r in phase_receipts if not r.get("accepted", True) or r.get("issue")]
        report["receipts"].extend(phase_receipts)
        report["execution_phase_reconciliation"] = {
            "terminal_running": phase_plan["summary"]["terminal_running"],
            "proposed": len(phase_requests),
            "applied": len(phase_receipts) - len(phase_failed),
            "conflicts": phase_plan["summary"]["conflict_count"],
        }
        if phase_error:
            report["execution_phase_reconciliation"]["error_type"] = phase_error
        if phase_failed:
            shutil.rmtree(root)
            root, _ = materialize_live_tower(phase_savepoint, root)
            for receipt in phase_receipts:
                receipt["rolled_back"] = True
            report["execution_phase_reconciliation"]["rolled_back"] = (
                len(phase_receipts) - len(phase_failed))
            report["execution_phase_reconciliation"]["applied"] = 0
            report["rejected"].append({
                "item": "execution-phase-reconcile",
                "reason": phase_failed[0].get("issue"),
            })

        # Maintenance is mechanical too: watchdog, repeated-failure stop, stale drafts,
        # pre-registration audit and roadmap FDR annotations.
        maintenance_requests = evolution.maintenance_reconcile_requests(root) + autonomy.canonization_requests(root)
        if maintenance_requests:
            maintenance_receipts = apply_requests(root, maintenance_requests)
            maintenance_failed = [r for r in maintenance_receipts if not r.get("accepted", True) or r.get("issue")]
            report["receipts"].extend(maintenance_receipts)
            if maintenance_failed:
                report["rejected"].append({"item": "maintenance-reconcile", "reason": maintenance_failed[0].get("issue")})
            else:
                report["maintenance"] = len(maintenance_receipts)

        # Incident lifecycle is derived from canonical evidence already present in
        # the materialized Tower. Agents never declare incident state directly.
        incident_requests = evolution.incident_reconcile_requests(root)
        if incident_requests:
            incident_receipts = apply_requests(root, incident_requests)
            incident_failed = [r for r in incident_receipts if not r.get("accepted", True) or r.get("issue")]
            report["receipts"].extend(incident_receipts)
            if incident_failed:
                report["rejected"].append({"item": "incident-reconcile", "reason": incident_failed[0].get("issue")})
            else:
                report["reconciled"] = [r.get("document") or r.get("entity_name") for r in incident_receipts]
        # Readiness is an ongoing invariant, including tests created before the
        # admission gate. Commit its repair WORK and private route together.
        from . import execution_recovery
        recovery_savepoint = (root / LIVE_TOWER_NAME).read_bytes()
        recovery_receipts = []
        routed = 0
        try:
            recovery_requests = execution_recovery.reconcile_requests(root, readiness_evaluator=readiness_evaluator)
            recovery_receipts = apply_requests(root, recovery_requests)
            if not any(not r.get("accepted", True) or r.get("issue") for r in recovery_receipts):
                routed = execution_recovery.ensure_handoffs(root)
        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            # One malformed legacy repair must not discard independently
            # accepted proposals or acknowledge an uncommitted repair.
            recovery_receipts.append({"accepted": False, "issue": {"code": "EXECUTION_RECOVERY_FAILED", "error_type": type(exc).__name__}})
        recovery_failed = [r for r in recovery_receipts if not r.get("accepted", True) or r.get("issue")]
        report["receipts"].extend(recovery_receipts)
        if recovery_failed:
            shutil.rmtree(root)
            root, _ = materialize_live_tower(recovery_savepoint, root)
            for receipt in recovery_receipts:
                receipt["rolled_back"] = True
            report["rejected"].append({"item": "execution-recovery", "reason": recovery_failed[0].get("issue")})
        else:
            if routed:
                from .live_tower import publish_live_tower
                publish_live_tower(root)
            report["execution_recovery"] = {"mutations": len(recovery_receipts), "handoffs_created": routed}
        from .public_campaigns import publication_requests
        refresh_capacity_policy()
        public_requests = publication_requests(root)
        if public_requests:
            public_receipts = apply_requests(root, public_requests)
            report["receipts"].extend(public_receipts)
            report["public_campaigns"] = {"approved_updates": sum(receipt.get("accepted") is True for receipt in public_receipts)}
        # Includes private canary controller/selection/metric mutations from the
        # same materialized Tower snapshot in the ordinary Writer pack path.
        from .telemetry import SEMANTIC_ENTITY_COUNT_KEYS, refresh_semantic_counts

        semantic_root = root / "entities"
        if ((root / "snapshot" / "latest.json").is_file()
                and any((semantic_root / kind).is_dir() for kind in SEMANTIC_ENTITY_COUNT_KEYS)):
            refresh_semantic_counts(root)
        from .live_tower import publish_live_tower

        publish_live_tower(root)
        packed = (root / LIVE_TOWER_NAME).read_bytes()
    after = verify_live_tower(read_live_tower_bytes(packed))
    report["after"] = after
    report["status"] = "NO_OP" if after == before else "READY_TO_UPLOAD"
    return (None if after == before else packed), report


def _queued_batteries(raw: bytes) -> list[dict]:
    from .evolution import pending_batteries

    with tempfile.TemporaryDirectory(prefix="nexo-robot-bat-") as work:
        root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        return pending_batteries(root)


def _clear_dispatch_specs(directory: str) -> None:
    """Remove only prior battery specs from the designated private staging directory."""
    if not directory:
        return
    root = Path(directory).resolve()
    if not root.is_dir():
        return
    for path in root.glob("*.json"):
        if path.resolve().parent != root or not re.fullmatch(r"[a-z0-9-]{3,48}", path.stem):
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict) and value.get("id") == path.stem and isinstance(value.get("tests"), list):
            path.unlink()


def _emit_committed_dispatch_specs(directory: str, raw: bytes, battery_ids: list[str]) -> None:
    """Export reservations only after successful CAS and verified Drive readback."""
    from .scientific_integrity import batteries
    with tempfile.TemporaryDirectory(prefix="nexo-dispatch-readback-") as work:
        root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        by_id = {battery.get("id"): battery for battery in batteries(root)}
        selected = [by_id[bid] for bid in battery_ids if bid in by_id and by_id[bid].get("status") == "DISPATCH_PENDING"]
    target = Path(directory).resolve()
    target.mkdir(parents=True, exist_ok=True)
    for battery in selected:
        if not re.fullmatch(r"[a-z0-9-]{3,48}", str(battery.get("id") or "")):
            continue
        path = target / (battery["id"] + ".json")
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(battery, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)


def _family_items(raw: bytes, kind: str) -> list[dict]:
    """Robot-made proposals from pre-registered families: new grid cells as tests, READY instances as batteries."""
    from .evolution import family_battery_items, family_contest_items, family_instance_items, family_spawn_items

    build = {"spawn": family_spawn_items, "instances": family_instance_items, "contests": family_contest_items}.get(kind, family_battery_items)
    with tempfile.TemporaryDirectory(prefix="nexo-robot-family-") as work:
        root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        return build(root)


def _stop_closures(raw: bytes) -> list[dict]:
    from datetime import datetime, timezone

    from .evolution import evolution_status

    def exhausted(used: Any, limit: Any) -> bool:
        # Charter limits are integers (legacy JSON can store integer strings).
        # Unknown/invalid limits never become invented authority to close.
        if type(used) not in (int, str) or type(limit) not in (int, str):
            return False
        try:
            count, maximum = int(used), int(limit)
        except ValueError:
            return False
        return maximum > 0 and count >= maximum

    with tempfile.TemporaryDirectory(prefix="nexo-robot-status-") as work:
        root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        roadmaps = evolution_status(root).get("roadmaps", [])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    closures = []
    for roadmap in roadmaps:
        if (roadmap.get("charter_status") != "CHARTERED"
                or roadmap.get("renewable")
                or str(roadmap.get("state") or "").upper() in {"CLOSED", "CANCELLED", "ARCHIVED"}):
            continue
        # SUCCESS/KILL counts are review signals, not proof that every frozen
        # comparison was executed and independently reviewed. Recompute budget
        # exhaustion because those signals can mask BUDGET in roadmap_progress.
        if not (exhausted(roadmap.get("tests_used"), roadmap.get("max_tests"))
                or exhausted(roadmap.get("days"), roadmap.get("max_days"))):
            continue
        rid = roadmap["roadmap_id"]
        closures.append({
            "kind": "ROADMAP_CLOSE", "source": "WRITER_ROBOT", "created_at": now,
            "_inbox_name": f"robot-close-{rid}",
            "payload": {
                "roadmap_id": rid, "reason": "BUDGET",
                "final_report": (
                    "Encerramento operacional por esgotamento do orcamento aprovado: "
                    f"{roadmap.get('tests_used')} / {roadmap.get('max_tests')} testes; "
                    f"{roadmap.get('days')} / {roadmap.get('max_days')} dias. "
                    "Nao constitui confirmacao ou refutacao cientifica. Comparacoes "
                    "nao concluidas e revisao pendente devem constar do relatorio final."
                ),
            },
        })
    return closures


class _GitHubInbox:
    """byDenoso/TCC@nexo-inbox inbox/*.json via the REST API (optional; needs a token with Contents read/write)."""

    API = "https://api.github.com/repos/byDenoso/TCC/contents"

    def __init__(self, token: str) -> None:
        self.token, self.seen = token, []

    def _req(self, method: str, path: str, body: dict | None = None):
        import urllib.request

        url = f"{self.API}/{path}" + ("?ref=nexo-inbox" if method == "GET" else "")
        data = json.dumps({"branch": "nexo-inbox", **body}).encode() if body else None
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "User-Agent": "nexo-writer-robot"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read() or b"null")

    def pending(self) -> list[dict]:
        if not self.token:
            return []
        import base64

        for item in sorted(self._req("GET", "inbox") or [], key=lambda i: i["name"]):
            if item["type"] != "file" or not item["name"].endswith(".json"):
                continue
            blob = self._req("GET", item["path"])
            try:
                payload = json.loads(base64.b64decode(blob["content"]).decode("utf-8-sig"))
            except ValueError:
                continue
            if isinstance(payload, dict):
                self.seen.append({"name": item["name"], "path": item["path"], "sha": blob["sha"], "content": blob["content"], "payload": payload})
        return self.seen

    def mark_processed(self, entry: dict) -> None:
        self._req("PUT", "processed/" + entry["name"], {"message": f"writer robot: processed {entry['name']}",
                                                         "content": "".join(entry["content"].split())})
        self._req("DELETE", entry["path"], {"message": f"writer robot: applied {entry['name']}", "sha": entry["sha"]})


PRODUCERS = ("GPT", "CLAUDE")


def producer_of(item: dict[str, Any]) -> str | None:
    """Declared producer of an automated proposal. Scheduled GPT files (scheduled-*) are GPT by convention."""
    value = str(item.get("producer") or "").strip().upper()
    if value in PRODUCERS:
        return value
    if str(item.get("_inbox_name") or "").startswith("scheduled-"):
        return "GPT"
    return None


def split_by_producer(items: list[dict[str, Any]], active: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(apply, shadow). Items without a producer (Dener, conversations, robot) always apply."""
    active = str(active or "GPT").strip().upper()
    if active not in PRODUCERS:
        active = "GPT"
    keep, shadow = [], []
    for item in items:
        producer = producer_of(item)
        (shadow if producer and producer != active else keep).append(item)
    return keep, shadow


def _gateway_results(report: dict, gateway_ids: list[str], shadow_ids: set[str] | None = None) -> tuple[dict, list[str], list[str]]:
    shadow_ids = shadow_ids or set()
    # Revalidate even pre-projected rows at the last export boundary. This
    # prevents callers that assemble reports from smuggling private effect IDs.
    receipts = [safe for row in (report.get("public_operation_receipts") or [])
                if isinstance(row, dict) and (safe := operation_receipts.public_receipt(row))]
    result_items, reported, resolved = [], [], []
    for gateway_id in gateway_ids:
        if not operation_receipts.is_safe_gateway_id(gateway_id):
            continue
        intent = "gateway:" + str(gateway_id)
        expected = (report.get("gateway_batch_intents") or {}).get(gateway_id)
        expected = [str(value) for value in expected] if isinstance(expected, list) else []
        intents = set(expected or [intent])
        matched = [row for row in receipts if row.get("intent_id") in intents]
        if expected and {row.get("intent_id") for row in matched} != intents:
            continue
        outcome = operation_receipts.public_outcome(matched)
        resolution = None
        if outcome is None and gateway_id in shadow_ids:
            outcome, resolution = "REJECTED_TERMINAL", "PRODUCER_SHADOW"
        if outcome is None:
            continue
        item = {"id": gateway_id, "intent_id": intent, "outcome": outcome}
        if resolution:
            item["resolution"] = resolution
        safe_rows = [operation_receipts.public_receipt(row) for row in matched]
        safe_rows = [row for row in safe_rows if row]
        if safe_rows:
            item["receipts"] = safe_rows
            item["receipt_ids"] = sorted({row["receipt_id"] for row in safe_rows})
        result_items.append(item)
        reported.append(gateway_id)
        if outcome in {"APPLIED", "ALREADY_APPLIED", "REJECTED_TERMINAL"}:
            resolved.append(gateway_id)
    return ({"contract": operation_receipts.CONTRACT, "items": result_items}, reported, resolved)


def _emit_gateway_results(report: dict, gateway_ids: list[str], shadow_ids: set[str] | None = None,
                          *, path: str | None = None, output: str | None = None) -> tuple[list[str], list[str]]:
    payload, reported, resolved = _gateway_results(report, gateway_ids, shadow_ids)
    if path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if output and (reported or resolved):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write("gateway_reported=" + ",".join(reported) + "\n")
            handle.write("gateway_resolved=" + ",".join(resolved) + "\n")
    return reported, resolved


def _transport_gateway_report(gateway_entries: list[dict], exc: Exception) -> dict:
    condition = getattr(exc, "retry_condition", None)
    if condition is None:
        condition = "RECONCILE_TOWER_BEFORE_REAPPLY" if type(exc).__name__ == "TowerConflict" else "AFTER_TRANSPORT_RECOVERY"
    report = {"operation_receipts": [], "public_operation_receipts": []}
    for entry in gateway_entries:
        gateway_id = str(entry.get("id") or "")
        envelope = entry.get("envelope")
        if not gateway_id or not isinstance(envelope, dict):
            continue
        receipt = operation_receipts.build_receipt(
            intent="gateway:" + gateway_id,
            payload_sha256=operation_receipts.payload_hash(envelope, trusted_transport=True),
            effect=operation_receipts.envelope_effect_id("gateway:" + gateway_id),
            outcome="RETRYABLE_TRANSPORT",
            source_revision=None,
            result_revision=None,
            reason_code="TOWER_TRANSPORT_UNAVAILABLE",
            retry_condition={"kind": condition},
            visibility="PUBLIC",
        )
        report["operation_receipts"].append(receipt)
        safe = operation_receipts.public_receipt(receipt)
        if safe:
            report["public_operation_receipts"].append(safe)
    return report


def _github_science_dispatch_enabled(raw_live_tower: bytes) -> bool:
    """Honor CONTROL: never enqueue GitHub science when that surface is disabled."""
    try:
        live = read_live_tower_bytes(raw_live_tower)
        entry = (live.get("files") or {}).get("CONTROL.json") or {}
        control = entry.get("value") if isinstance(entry, dict) else {}
        if not isinstance(control, dict):
            return True
        role = str(control.get("github_actions_science_role") or "").upper()
    except (OSError, ValueError, TypeError, KeyError):
        return True
    return role not in {
        "DISABLED", "DISABLED_BUDGET_EXHAUSTED", "RETIRED", "FROZEN",
        "RETIRED_AS_OPERATIONAL_STATE",
    }


def _runner_battery_updates(path: str) -> list[dict]:
    """Load only Writer-produced BATTERY_STATUS observations."""
    if not path or not Path(path).is_file():
        return []
    try:
        updates = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    result = []
    for update in updates if isinstance(updates, list) else []:
        payload = update.get("payload") if isinstance(update, dict) else None
        if (isinstance(payload, dict)
                and set(update) == {"kind", "source", "payload"}
                and update.get("kind") == "BATTERY_STATUS"
                and update.get("source") == "WRITER_ROBOT"
                and ("results" not in payload or isinstance(payload["results"], list))
                and str(payload.get("battery_id") or "")):
            try:
                identity = _runner_battery_identity(payload)
            except (TypeError, ValueError):
                continue  # Malformed/non-finite source metadata cannot stop other observations.
            result.append({**update, "_inbox_source": "RUNNER_OBSERVATION",
                           "_inbox_name": "battery-update-" + identity.rsplit(":", 1)[-1],
                           "_inbox_id": identity})
    return result


def _runner_execution_assessment_updates(path: str) -> list[dict]:
    """Load only the reviewed assessment shape appended by the collector."""
    if not path or not Path(path).is_file():
        return []
    try:
        updates = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    result = []
    for update in updates if isinstance(updates, list) else []:
        assessment = update.get("assessment") if isinstance(update, dict) else None
        approved = assessment.get("approved") if isinstance(assessment, dict) else None
        source = assessment.get("source") if isinstance(assessment, dict) else None
        test_id = str(approved.get("test_id") or "") if isinstance(approved, dict) else ""
        artifact_id = approved.get("artifact_id") if isinstance(approved, dict) else None
        if (isinstance(update, dict)
                and set(update) == {"nexo_operation", "assessment"}
                and update.get("nexo_operation") == "EXECUTION_OBSERVATION_ASSESSMENT"
                and isinstance(assessment, dict)
                and set(assessment) == {"approved", "source"}
                and isinstance(approved, dict) and isinstance(source, dict)
                and test_id and type(artifact_id) is int and artifact_id > 0):
            result.append({**update, "_inbox_source": "RUNNER_OBSERVATION",
                           "_inbox_name": f"execution-assessment-{test_id}-{artifact_id}",
                           "_inbox_id": f"runner:assessment:{test_id}:{artifact_id}"})
    return result


def _runner_operational_updates(path: str) -> list[dict]:
    """Load Writer-collected receipts and stamp their non-user-authenticable source."""
    if not path or not Path(path).is_file():
        return []
    try:
        updates = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    result = []
    for update in updates if isinstance(updates, list) else []:
        payload = update.get("payload") if isinstance(update, dict) else None
        receipt_id = str(payload.get("receipt_id") or "") if isinstance(payload, dict) else ""
        if (receipt_id and set(update) == {"kind", "source", "created_at", "payload"}
                and update.get("kind") == "OPERATIONAL_RECEIPT"
                and update.get("source") == "WRITER_ROBOT"
                and update.get("created_at") == payload.get("executed_at")):
            result.append({**update, "_inbox_source": "RUNNER_OBSERVATION",
                           "_inbox_name": "operational-receipt-" + receipt_id,
                           "_inbox_id": "runner:" + receipt_id})
    return result


def _main(argv: list[str]) -> int:
    if argv and argv[0] == "continuity":
        from .continuity_cli import main as continuity_main
        return continuity_main(argv[1:])
    if argv and argv[0] == "memory":
        # Existing automations keep the stable memory command. Evidence
        # retrieval uses the measured 1.1 engine; its cache is a sidecar so
        # memory 1.0.1 indexes remain readable and untouched.
        if len(argv) > 1 and argv[1] in {"context", "search"}:
            from .retrieval_cli import main as retrieval_main, memory_cache_path
            routed = list(argv[1:])
            if len(routed) >= 3:
                routed[2] = memory_cache_path(routed[2])
            return retrieval_main(routed)
        from .memory_cli import main as memory_main
        return memory_main(argv[1:])
    if argv and argv[0] == "retrieval":
        from .retrieval_cli import main as retrieval_main
        return retrieval_main(argv[1:])
    if len(argv) == 4 and argv[0] == "handoff" and argv[2] == "list":
        from . import AgentService

        role = argv[3].upper()
        with tempfile.TemporaryDirectory(prefix="nexo-gpt-handoff-") as work:
            root, metadata = materialize_live_tower(Path(argv[1]).read_bytes(), Path(work) / "TOWER_V06")
            items = AgentService(root).inbox_for(role)
        print(json.dumps({
            "tower_state_fingerprint": metadata["tower_revision"],
            "role": role,
            "count": len(items),
            "items": items,
        }, ensure_ascii=False, indent=1))
        return 0
    if len(argv) >= 2 and argv[0] == "frontier":
        # Same frontier as the CLI writer: resume CHECKPOINTED/RUNNING first, then READY.
        from .frontier import roadmap_frontier

        with tempfile.TemporaryDirectory(prefix="nexo-gpt-frontier-") as work:
            root, _ = materialize_live_tower(Path(argv[1]).read_bytes(), Path(work) / "TOWER_V06")
            print(json.dumps(roadmap_frontier(root, argv[2] if len(argv) > 2 else None), ensure_ascii=False, indent=1))
        return 0
    if len(argv) >= 1 and argv[0] == "robot":
        # Unattended writer (GitHub Actions): Drive NEXO_INBOX -> apply -> compare-and-swap the same Tower file id.
        # Needs env GOOGLE_SERVICE_ACCOUNT_JSON with write scope. Prints only ids and counts (never proposal content).
        import os
        from .drive_transport import DriveInbox, DriveTower, TowerConflict, TowerTransportError
        dispatch_dir = os.environ.get("NEXO_BATTERY_DIR", "")
        _clear_dispatch_specs(dispatch_dir)

        gateway_file = os.environ.get("NEXO_GATEWAY_ITEMS", "")
        gateway_entries = []
        if gateway_file and Path(gateway_file).is_file():
            try:
                gateway_entries = json.loads(Path(gateway_file).read_text(encoding="utf-8")).get("items") or []
            except (ValueError, OSError):
                gateway_entries = []
        gateway_entries = [entry for entry in gateway_entries
                           if isinstance(entry, dict) and isinstance(entry.get("envelope"), dict)
                           and operation_receipts.is_safe_gateway_id(entry.get("id"))]
        gateway_ids = [str(entry["id"]) for entry in gateway_entries]
        # This file is produced by the robot's protected HMAC/OIDC verifier,
        # never from client metadata or the raw Drive/GitHub inbox.
        verified_human_intents = frozenset()
        verified_capacity_observation = None
        context_file = os.environ.get("NEXO_VERIFIED_HUMAN_INTENTS", "")
        if context_file:
            try:
                context = json.loads(Path(context_file).read_text(encoding="utf-8"))
                verified_human_intents = frozenset(value for value in context.get("proposal_sha256") or []
                                                   if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value))
                verified_capacity_observation = context.get("capacity_observation")
            except (ValueError, OSError, TypeError):
                pass
        items = [{**entry["envelope"], "_inbox_source": "GATEWAY",
                  "_inbox_name": f"gw-{entry['id']}", "_inbox_id": "gateway:" + str(entry["id"])}
                 for entry in gateway_entries]
        try:
            tower, inbox = DriveTower(write=True), DriveInbox(write=True)
        except Exception as exc:
            print(json.dumps({"status": "TRANSPORT_UNAVAILABLE", "error_type": type(exc).__name__}))
            return 2
        try:
            pending = [i for i in inbox.pending() if not str(i.get("name", "")).startswith("_")]
        except TowerTransportError as exc:
            pending = []
            print(json.dumps({"status": "INBOX_TRANSPORT_UNAVAILABLE", "action": exc.action,
                              "status_code": exc.status_code, "retry_condition": exc.retry_condition}))
        for entry in pending:
            payload = entry.get("payload")
            if isinstance(payload, dict):
                items.append({**payload, "_inbox_source": "DRIVE",
                              "_inbox_name": entry.get("name"), "_inbox_id": entry.get("id")})
        github = _GitHubInbox(os.environ.get("NEXO_INBOX_GITHUB_TOKEN", "").strip())
        try:
            github_entries = github.pending()
        except Exception as exc:
            github_entries = []
            print(json.dumps({"status": "GITHUB_INBOX_UNAVAILABLE", "error_type": type(exc).__name__}))
        for entry in github_entries:
            items.append({**entry["payload"], "_inbox_source": "GITHUB",
                          "_inbox_name": entry["name"], "_inbox_id": "github:" + entry["path"]})
        updates_file = os.environ.get("NEXO_BATTERY_UPDATES", "")
        items.extend(_runner_battery_updates(updates_file))
        items.extend(_runner_execution_assessment_updates(updates_file))
        items.extend(_runner_operational_updates(os.environ.get("NEXO_OPERATIONAL_UPDATES", "")))
        # Producer gate (fallback in shadow): only the active producer's automated proposals reach the Tower;
        # the other producer's are acknowledged and logged, never applied. Unlabelled items (Dener, conversations,
        # robot) always pass, so switching GPT <-> CLAUDE never creates a second writer or a second truth.
        gateway_shadow: list[str] = []
        items, shadowed = split_by_producer(items, os.environ.get("NEXO_ACTIVE_PRODUCER", "GPT"))
        if shadowed:
            print(json.dumps({"shadow": len(shadowed), "active_producer": os.environ.get("NEXO_ACTIVE_PRODUCER", "GPT"),
                              "names": [str(s.get("_inbox_name")) for s in shadowed][:50]}, ensure_ascii=False))
            shadow_ids = {str(s.get("_inbox_id")) for s in shadowed}
            for entry in list(github.seen):
                if "github:" + entry["path"] in shadow_ids:
                    try:
                        github.mark_processed(entry)
                    except Exception as exc:
                        print(json.dumps({"status": "GITHUB_INBOX_MARK_FAILED", "error_type": type(exc).__name__}))
            for entry in pending:
                if entry.get("id") in shadow_ids:
                    try:
                        inbox.mark_processed(entry["id"])
                    except TowerTransportError as exc:
                        print(json.dumps({"status": "DRIVE_INBOX_MARK_FAILED", "action": exc.action,
                                          "status_code": exc.status_code, "retry_condition": exc.retry_condition}))
                    except Exception as exc:
                        print(json.dumps({"status": "DRIVE_INBOX_MARK_FAILED", "error_type": type(exc).__name__}))
            gateway_shadow = [g for g in gateway_ids if "gateway:" + g in shadow_ids]
        # Operational work shares the existing Writer, credential and concurrency.
        try:
            from .operational_tick import tick_existing_writer
            operational_report = tick_existing_writer(tower, os.environ)
            print(json.dumps({"operational_worker": operational_report}, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"operational_worker": "ITEMS_DEFERRED",
                              "error_type": type(exc).__name__,
                              "code": getattr(exc, "code", type(exc).__name__)}))
        items = [item for item in items if item.get("contract") != "NEXO_OPERATIONAL_INTENT_V1"]
        dispatch_dir = os.environ.get("NEXO_BATTERY_DIR", "")
        _clear_dispatch_specs(dispatch_dir)
        dispatched: list[str] = []
        for attempt in range(3):
            dispatched = []
            _clear_dispatch_specs(dispatch_dir)
            try:
                raw, base = tower.download(cache=False)
            except TowerTransportError as exc:
                transport_report = _transport_gateway_report(gateway_entries, exc)
                _emit_gateway_results(
                    transport_report, gateway_ids, set(gateway_shadow),
                    path=os.environ.get("NEXO_OPERATION_RECEIPTS_OUT"),
                    output=os.environ.get("GITHUB_OUTPUT"),
                )
                print(json.dumps({"status": "TOWER_TRANSPORT_UNAVAILABLE", "action": exc.action,
                                  "status_code": exc.status_code, "retry_condition": exc.retry_condition}))
                return 0
            trusted_context = {}
            if verified_human_intents:
                trusted_context["verified_human_intents"] = verified_human_intents
            if verified_capacity_observation is not None:
                trusted_context["verified_capacity_observation"] = verified_capacity_observation
            packed, report = apply_to_tower(raw, items, **trusted_context)
            # Mechanical duties the GPT should not spend a run on: close roadmaps whose stop criterion was met.
            closes = _stop_closures(packed or raw)
            if closes:
                changed, extra = apply_to_tower(packed or raw, closes)
                if changed is not None:
                    packed = changed
                report["applied"] = report.get("applied", []) + extra.get("applied", [])
                report["after"] = extra.get("after", report.get("after"))
                report["status"] = "READY_TO_UPLOAD"
            # Families: the robot itself turns pre-registered grids into tests and READY instances into batteries.
            for family_kind in ("spawn", "instances", "contests", "batteries"):
                family_items = _family_items(packed or raw, family_kind)
                if family_items:
                    changed, extra = apply_to_tower(packed or raw, family_items)
                    if changed is not None:
                        packed = changed
                    report["applied"] = report.get("applied", []) + extra.get("applied", [])
                    report["rejected"] = report.get("rejected", []) + extra.get("rejected", [])
                    report["after"] = extra.get("after", report.get("after"))
                    report["status"] = "READY_TO_UPLOAD"
            # Batteries queued by the Executor: hand their specs to the dispatcher step and mark them DISPATCHED.
            queued = _queued_batteries(packed or raw)
            github_science_enabled = _github_science_dispatch_enabled(packed or raw)
            if queued and dispatch_dir and github_science_enabled:
                from .scientific_integrity import WRITER_DISPATCH_TOKEN

                marks = []
                for battery in queued:
                    marks.append({"kind": "BATTERY_STATUS", "source": "WRITER_ROBOT", "_inbox_name": f"robot-dispatch-{battery['id']}",
                                  "_writer_dispatch_token": WRITER_DISPATCH_TOKEN,
                                  "payload": {"battery_id": battery["id"], "status": "DISPATCHED", "run_ref": "github-actions"}})
                changed, extra = apply_to_tower(packed or raw, marks)
                if changed is not None:
                    packed = changed
                report["applied"] = report.get("applied", []) + extra.get("applied", [])
                report["after"] = extra.get("after", report.get("after"))
                report["status"] = "READY_TO_UPLOAD"
                dispatched = [b["id"] for b in queued]
            elif queued and dispatch_dir and not github_science_enabled:
                print(json.dumps({
                    "status": "GITHUB_SCIENCE_DISPATCH_DISABLED_BY_CONTROL",
                    "queued": len(queued),
                    "execution_primary": "CHATGPT_RUNTIME",
                }))
            if packed is None:
                if not items:
                    print(json.dumps({"status": "NO_OP", "pending": len(pending)}))
                    _emit_gateway_results(
                        report, gateway_ids, set(gateway_shadow),
                        path=os.environ.get("NEXO_OPERATION_RECEIPTS_OUT"),
                        output=os.environ.get("GITHUB_OUTPUT"),
                    )
                    return 0
                break
            if os.environ.get("NEXO_ROBOT_DRY"):
                print(json.dumps({"status": "DRY_RUN", "pending": len(pending), "items": len(items),
                                  "applied": len(report.get("applied", [])), "rejected": len(report.get("rejected", [])),
                                  "before": report.get("before"), "after": report.get("after")}))
                return 0
            try:
                write = tower.compare_and_swap(base, packed)
                report["write"] = {k: write.get(k) for k in ("state_fingerprint", "head_revision_id", "readback")}
                if dispatch_dir and dispatched and write.get("readback") in {True, "PASS"}:
                    _emit_committed_dispatch_specs(dispatch_dir, packed, dispatched)
                break
            except TowerConflict:
                if attempt == 2:
                    transport_report = _transport_gateway_report(gateway_entries, TowerConflict("TOWER_HEAD_MOVED"))
                    _emit_gateway_results(
                        transport_report, gateway_ids, set(gateway_shadow),
                        path=os.environ.get("NEXO_OPERATION_RECEIPTS_OUT"),
                        output=os.environ.get("GITHUB_OUTPUT"),
                    )
                    print(json.dumps({"status": "CONFLICT"}))
                    return 3
            except TowerTransportError as exc:
                transport_report = _transport_gateway_report(gateway_entries, exc)
                _emit_gateway_results(
                    transport_report, gateway_ids, set(gateway_shadow),
                    path=os.environ.get("NEXO_OPERATION_RECEIPTS_OUT"),
                    output=os.environ.get("GITHUB_OUTPUT"),
                )
                print(json.dumps({"status": "TOWER_TRANSPORT_UNAVAILABLE", "action": exc.action,
                                  "status_code": exc.status_code, "retry_condition": exc.retry_condition}))
                return 0
        by_name = {e.get("name"): e.get("id") for e in pending}
        applied_roots = {str(n) for n in report.get("handled", []) + report.get("applied", [])}
        for entry in github.seen:
            if _fully_handled(entry["name"], items, applied_roots):
                try:
                    github.mark_processed(entry)
                except Exception as exc:
                    print(json.dumps({"status": "GITHUB_INBOX_MARK_FAILED", "error_type": type(exc).__name__}))
        for name, file_id in by_name.items():
            if file_id and _fully_handled(str(name), items, applied_roots):
                try:
                    inbox.mark_processed(file_id)
                except TowerTransportError as exc:
                    print(json.dumps({"status": "DRIVE_INBOX_MARK_FAILED", "action": exc.action,
                                      "status_code": exc.status_code, "retry_condition": exc.retry_condition}))
                except Exception as exc:
                    print(json.dumps({"status": "DRIVE_INBOX_MARK_FAILED", "error_type": type(exc).__name__}))
        summary = {"status": report.get("status"), "before": report.get("before"), "after": report.get("after"),
                   "applied": len(report.get("applied", [])), "rejected": [r.get("item") for r in report.get("rejected", [])],
                   "write": report.get("write")}
        print(json.dumps(summary, ensure_ascii=False))
        applied = applied_roots
        _emit_gateway_results(
            report, gateway_ids, set(gateway_shadow),
            path=os.environ.get("NEXO_OPERATION_RECEIPTS_OUT"),
            output=os.environ.get("GITHUB_OUTPUT"),
        )
        out = os.environ.get("GITHUB_OUTPUT")
        if out and report.get("write"):
            with open(out, "a", encoding="utf-8") as handle:
                handle.write("tower_revision=" + str(report["write"]["state_fingerprint"]) + "\n")
        return 0
    if len(argv) >= 2 and argv[0] == "status":
        # Closed-loop view: Dener's gate, referee queues, roadmap stop criteria, genome, decoys, canary arm.
        from .evolution import evolution_status

        with tempfile.TemporaryDirectory(prefix="nexo-gpt-status-") as work:
            root, _ = materialize_live_tower(Path(argv[1]).read_bytes(), Path(work) / "TOWER_V06")
            status = evolution_status(root)
            status.update(_operational_status(root))
            print(json.dumps(status, ensure_ascii=False, indent=1, default=str))
        return 0
    if len(argv) >= 2 and argv[0] == "verify":
        fingerprint = verify_live_tower(read_live_tower_bytes(Path(argv[1]).read_bytes()))
        ok = len(argv) < 3 or fingerprint == argv[2]
        print(json.dumps({"fingerprint": fingerprint, "readback": "PASS" if ok else "MISMATCH"}))
        return 0 if ok else 1
    if len(argv) == 4 and argv[0] == "apply":
        items = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        packed, report = apply_to_tower(Path(argv[1]).read_bytes(), items if isinstance(items, list) else [items])
        if packed is not None:
            Path(argv[3]).write_bytes(packed)
            report["out"] = argv[3]
        print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
        return 0
    print(__doc__)
    return 2



def _fully_handled(label: str, items: list[dict], handled: set[str]) -> bool:
    if label in handled:
        return True
    item = next((item for item in items if item.get("_inbox_name") == label), {})
    children = (item.get("payload") or {}).get("items") if item.get("kind") == "BATCH" else None
    return isinstance(children, list) and bool(children) and all(f"{label}-{index}" in handled for index in range(len(children)))


def main(argv: list[str]) -> int:
    if argv and argv[0] == "robot":
        from .drive_transport import writer_lock
        with writer_lock():
            return _main(argv)
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
