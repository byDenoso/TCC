"""Private, Writer-owned recovery of execution prerequisites.

One repair WORK per frozen TEST identity, not another scientific test or verdict.
Old intake artifacts are evidence to inspect, not permission to invent a binding.
Ownership is an assignment until the recipient explicitly accepts the handoff.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from . import scientific_integrity as integrity
from .semantics import is_private, resolve
from .tower_paths import entity_path

POLICY = "EXECUTION_RECOVERY_V1"
ROLES = {"DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT"}
TERMINAL_WORK = {"DONE", "VERIFIED", "REJECTED", "FAILED", "SUPERSEDED", "CANCELLED", "CANCELED",
                 "ARCHIVED", "COMPLETED", "CLOSED_VERIFIED", "DISCARDED", "WITHDRAWN"}


def _entity_version(value: Any) -> int | None:
    """Return a canonical CAS version without coercing malformed legacy data."""
    return value if type(value) is int and value > 0 else None


def _public(entity: dict) -> bool:
    entity_id = str(entity.get("id") or "")
    return bool(entity_id and not entity.get("private")
                and not is_private(resolve(entity, entity_id=entity_id)))


def _entities(root: Path, kind: str) -> list[dict]:
    return [integrity.read(root, p.relative_to(root).as_posix())
            for p in sorted((root / "entities" / kind).glob("*.json"))]


def fingerprint(test: dict) -> str:
    # Include the identity: scientifically different tests must never share a
    # repair merely because their current error strings happen to be equal.
    return integrity.digest({"test_id": test["id"], "frozen_design": test.get("prereg_hash") or
                             {key: test.get(key) for key in integrity.FROZEN}})


def evaluate_readiness(root: str | Path, test: dict, *, ignore_reservation: bool = False,
                       readiness_evaluator=None) -> dict:
    """Use the fail-closed Tower C01 wrapper, preserving canonical baseline behavior."""
    root = Path(root)
    baseline = lambda: integrity.readiness(root, test, ignore_reservation=ignore_reservation)
    evaluator = readiness_evaluator
    if evaluator is None:
        try:
            from .operational_canary import make_tower_readiness_evaluator

            evaluator = make_tower_readiness_evaluator()
        except (ImportError, AttributeError, TypeError, ValueError):
            evaluator = None
    if evaluator is None:
        return baseline()
    try:
        parameters = inspect.signature(evaluator).parameters
        if "ignore_reservation" in parameters:
            return evaluator(root, test, baseline, ignore_reservation=ignore_reservation)
        return evaluator(root, test, baseline)
    except Exception:
        return baseline()


def _binding_recovery(test: dict, artifacts: list[dict]) -> tuple[dict, list[str], list[str]]:
    candidates: dict[str, dict[str, tuple[Any, str]]] = {"data_binding": {}, "execution": {}}
    refs, conflicts = [], []
    for artifact in artifacts:
        body = artifact.get("payload") or {}
        if not isinstance(body, dict) or body.get("test_id") != test.get("id"):
            continue
        kind = artifact.get("kind")
        if kind not in {"DATA_BINDING", "RECIPE_BIND"}:
            continue
        ref = str(artifact.get("id") or "")
        if ref:
            refs.append(ref)
        # Exact target alone does not prove scientific compatibility. Require
        # the original frozen-design commitment, never today's inferred one.
        if not test.get("prereg_hash") or body.get("prereg_hash") != test["prereg_hash"]:
            continue
        if kind == "DATA_BINDING" and body.get("status") == "BOUND" and integrity.valid_inputs(body.get("inputs")):
            value = {k: body[k] for k in ("status", "inputs", "note") if k in body}
            candidates["data_binding"][integrity.digest(value["inputs"])] = (value, ref)
        elif kind == "RECIPE_BIND" and isinstance(body.get("params"), dict) and body.get("recipe"):
            value = {"recipe": body["recipe"], "recipe_params": body["params"]}
            candidates["execution"][integrity.digest(value)] = (value, ref)
    changes, restored = {}, []
    for key, values in candidates.items():
        if key == "data_binding" and (test.get("data_binding") or test.get("input_binding")):
            continue
        if key == "execution" and (test.get("recipe") or test.get("recipe_params") is not None):
            continue
        if len(values) > 1:
            conflicts.append("CONFLICTING_RECORDED_" + key.upper())
            continue
        if not values:
            continue
        value, ref = next(iter(values.values()))
        if key == "data_binding" and not (test.get("data_binding") or test.get("input_binding")):
            changes[key] = value
            restored.append(ref)
        elif key == "execution" and not test.get("recipe") and test.get("recipe_params") is None:
            changes.update(value)
            restored.append(ref)
    if restored:
        changes["binding_recovery_refs"] = sorted(set((test.get("binding_recovery_refs") or []) + restored))
    return changes, sorted(set(refs)), conflicts


def _owner(test: dict, work: list[dict]) -> tuple[str, str, list[str]]:
    explicit = str(test.get("owner_role") or "").upper()
    if explicit in ROLES:
        return explicit, "TEST_OWNER", []
    associated = []
    links = {str(test.get(key) or "") for key in ("work_id", "work_ref", "source_work_id", "parent_work_id")}
    for item in work:
        if item.get("kind") == "DEPENDENCY_RECOVERY" or item.get("status") in TERMINAL_WORK:
            continue
        if (str(item.get("id")) in links or item.get("test_id") == test["id"] or
                item.get("target_test_id") == test["id"] or (item.get("frozen_test") or {}).get("id") == test["id"]):
            associated.append(item)
    owners = {str(item.get("owner_role") or "").upper() for item in associated} & ROLES
    if len(owners) == 1:
        return next(iter(owners)), "EXISTING_WORK_OWNER", sorted(str(x["id"]) for x in associated)
    # The existing runtime routes incomplete/unowned preparation to ADVISOR.
    # This assigns operational triage, never a human or scientific conclusion.
    return "ADVISOR", "OWNER_CONFLICT_TRIAGE" if len(owners) > 1 else "UNASSIGNED_TRIAGE", sorted(str(x["id"]) for x in associated)


def _route(reasons: list[str], *, domain: str | None = None) -> tuple[str, str]:
    parameter_definition_errors = {
        "DATA_RELEASE_PARAM_MISMATCH", "UNSUPPORTED_COMPILATIONS", "UNSUPPORTED_DATA_RELEASE",
        "UNSUPPORTED_RECIPE_MODE", "UNSUPPORTED_RECIPE_PARAMS", "UNUSED_RECIPE_PARAMS",
        "RECIPE_PARAMS_INVALID", "RECIPE_PRIORS_INVALID", "RECIPE_HOLDOUTS_INVALID",
        "FROZEN_RECIPE_PARAMS_MISMATCH",
    }
    if parameter_definition_errors.intersection(reasons):
        return "LEARNER", "Preservar os parâmetros congelados e comparar a seleção ao contrato de dados; registrar a incompatibilidade e propor uma nova identidade científica se a seleção precisar mudar."
    if any(reason.startswith(("MISSING_", "FROZEN_", "CONFLICTING_")) for reason in reasons):
        return "LEARNER", "Recuperar a definição já congelada na linhagem e identificar a referência inequívoca; se houver conflito, registrar a decisão científica que falta."
    if any(reason.startswith(("RECIPE_", "PREFLIGHT_")) for reason in reasons):
        if str(domain or "SCIENCE").upper() == "SCIENCE":
            return "EXECUTOR", "Implementar e ligar a receita científica já contratada, validar os insumos e executar somente após os critérios canônicos de prontidão."
        return "ADVISOR", "Reparar a infraestrutura genérica da validação e encaminhar qualquer receita científica ao Operador."
    return "EXECUTOR", "Recuperar os insumos exatos e suas versões e assinaturas, registrar a ligação pelo escritor e revalidar a execução sem mudar o desenho científico."


def _request(kind: str, current: dict, changes: dict, event: str) -> dict | None:
    changes = {k: v for k, v in changes.items() if current.get(k) != v}
    if not changes:
        return None
    return {"request_id": "REQ-RECOVERY-" + integrity.digest({"id": current["id"], "version": current.get("entity_version", 0), "changes": changes})[:32],
            "entity_kind": kind, "entity_name": current["id"], "expected_version": int(current.get("entity_version") or 0),
            "writer_role": "ADVISOR", "event_type": event, "changes": changes}


def reconcile_requests(root: str | Path, *, readiness_evaluator=None) -> list[dict]:
    root = Path(root)
    artifacts, works = _entities(root, "artifact"), _entities(root, "work")
    work_by_id = {w.get("id"): w for w in works}
    requests = []
    active = integrity.active_tests(root)
    for test in _entities(root, "test"):
        tid = str(test.get("id") or "")
        if not tid or test.get("private") or is_private(resolve(test, entity_id=tid)):
            continue
        state = str(test.get("status") or test.get("state") or "").upper()
        # Never close execution work while an attempt/reservation is active,
        # even if a legacy TEST simultaneously carries a terminal-looking state.
        if tid in active:
            continue
        if integrity.terminal(test):
            # A legacy one-to-one execution WORK can outlive the TEST it was
            # created to execute. Close only that exact public EXECUTOR twin.
            # This reconciles lifecycle state; it does not dispatch or mutate
            # the TEST, result, verdict, review, binding, or scientific fields.
            current_work = work_by_id.get("WORK::" + tid)
            test_version = _entity_version(test.get("entity_version"))
            work_version = _entity_version((current_work or {}).get("entity_version"))
            if (current_work and test_version is not None and work_version is not None
                    and _public(current_work) and current_work.get("test_id") == tid
                    and str(current_work.get("owner_role") or "").upper() == "EXECUTOR"
                    and str(current_work.get("status") or "").upper() == "READY"):
                changes = {
                    "status": "DONE",
                    "operational_status": "DONE",
                    "closure_reason": "TEST_ENTITY_ALREADY_TERMINAL",
                    "completion_evidence": {
                        "kind": "TERMINAL_TEST_STATE_OBSERVED",
                        "test_id": tid,
                        "test_entity_version": test_version,
                        "test_status": state,
                        "test_verdict": test.get("verdict"),
                    },
                }
                requests.append({
                    "request_id": "REQ-WORK-CLOSE-" + integrity.digest({
                        "work_id": current_work["id"],
                        "work_version": work_version,
                        "test_id": tid,
                        "test_version": test_version,
                    })[:32],
                    "entity_kind": "work",
                    "entity_name": current_work["id"],
                    "expected_version": work_version,
                    "writer_role": "EXECUTOR",
                    "event_type": "WORK_RECONCILED_TERMINAL_TEST",
                    "changes": changes,
                })
            continue
        if state not in {"READY", "BLOCKED_INPUT"}:
            continue
        recovered, refs, conflicts = _binding_recovery(test, artifacts)
        provisional = {**test, **recovered}
        previous = test.get("readiness") or {}
        managed = bool(test.get("blocker") and previous.get("policy") == integrity.POLICY and
                       test["blocker"] == ",".join(previous.get("reasons") or []))
        if managed:
            provisional["blocker"] = None
        check = evaluate_readiness(root, provisional, readiness_evaluator=readiness_evaluator)
        check["reasons"] = sorted(set(check["reasons"] + conflicts))
        check["eligible"] = not check["reasons"]
        changes = {**recovered, "readiness": check}
        if check["eligible"]:
            changes.update(status="READY", state="READY", blocker=None)
        else:
            changes.update(status="BLOCKED_INPUT", state="BLOCKED_INPUT")
            if not test.get("blocker") or managed:
                changes["blocker"] = ",".join(check["reasons"])
        fp = fingerprint(test)
        wid = "WORK::RECOVERY-" + fp[:32]
        current_work = work_by_id.get(wid)
        if check["eligible"]:
            if current_work and current_work.get("status") not in TERMINAL_WORK:
                recovery = {**(current_work.get("recovery") or {}), "validation": check, "reasons": []}
                request = _request("work", current_work, {"status": "DONE", "recovery": recovery,
                                   "completion_evidence": {"kind": "READINESS_VALIDATED", "test_id": tid,
                                                           "prereg_hash": test.get("prereg_hash"), "recipe_sha256": check.get("recipe_sha256")}}, "DEPENDENCY_RECOVERY_VERIFIED")
                if request:
                    requests.append(request)
        else:
            changes["recovery_work_id"] = wid
            owner, owner_source, source_work = _owner(test, works)
            target, action = _route(check["reasons"], domain=test.get("domain"))
            current_work = current_work or {"id": wid, "entity_version": 0}
            recovery = {**(current_work.get("recovery") or {}), "policy": POLICY, "fingerprint": fp,
                        "reasons": check["reasons"], "target_role": target, "candidate_artifact_refs": refs,
                        "validation": check}
            old_recovery = current_work.get("recovery") or {}
            reopen = (current_work.get("status") == "DONE" and
                      (current_work.get("completion_evidence") or {}).get("kind") == "READINESS_VALIDATED")
            if reopen or (old_recovery.get("target_role") and old_recovery["target_role"] != target):
                # Moving from preparation to input recovery is a new offer,
                # not silent relief of the last accepted owner.
                recovery["ownership_state"] = "ASSIGNED_UNACCEPTED"
                recovery["route_generation"] = int(old_recovery.get("route_generation") or 1) + 1
                if recovery.get("acceptance_source"):
                    recovery["previous_acceptance"] = recovery.pop("acceptance_source")
            if "ownership_state" not in recovery:
                recovery.update(ownership_state="ASSIGNED_UNACCEPTED", owner_source=owner_source,
                                source_work_refs=source_work, route_generation=1)
            fields = {"kind": "DEPENDENCY_RECOVERY", "test_id": tid, "roadmap_id": test.get("roadmap_id"),
                      "domain": test.get("domain"), "priority": test.get("priority") or "P1",
                      "status": "WAIT_DEPENDENCY", "owner_role": current_work.get("owner_role") or owner,
                      "question": "Restaurar as condições de execução do teste congelado", "next_action": action,
                      "thread_id": current_work.get("thread_id") or "RECOVERY::" + fp[:32], "recovery": recovery}
            if reopen:
                fields["completion_evidence"] = None
            # Do not revive a manually retired repair under the same identity.
            if reopen or current_work.get("status") not in TERMINAL_WORK:
                request = _request("work", current_work, fields, "DEPENDENCY_RECOVERY_RECONCILED")
                if request:
                    requests.append(request)
        request = _request("test", test, changes, "TEST_READINESS_RECONCILED")
        if request:
            requests.append(request)
    return requests


def ensure_handoffs(root: str | Path) -> int:
    """Writer-internal private routing; never serialize a handoff to public inbox."""
    from . import AgentService
    from .handoff import _latest_by_handoff, _write_event
    root = Path(root)
    service, count = AgentService(root), 0
    previous = _latest_by_handoff(root)
    for work in _entities(root, "work"):
        recovery = work.get("recovery") or {}
        if recovery.get("policy") != POLICY:
            continue
        existing = [h for h in previous.values() if h.get("entity_ref") == work["id"] and h.get("handoff_type") == "BLOCKER_RECOVERY"]
        if work.get("status") in TERMINAL_WORK:
            if (work.get("completion_evidence") or {}).get("kind") == "READINESS_VALIDATED":
                for event in existing:
                    if event.get("state") in {"PENDING", "ACK"}:
                        _write_event(root, {**event, "state": "SUPERSEDED", "event_type": "HANDOFF_SUPERSEDED",
                                           "writer_role": "ADVISOR", "resolution": "PREREQUISITES_VALIDATED_BY_WRITER"})
                        count += 1
            continue
        # One open transfer per repair; diagnostics changing are not new owners.
        existing = [h for h in existing if h.get("to_role") == recovery.get("target_role")
                    and h.get("recovery_fingerprint") == recovery.get("fingerprint")
                    and ((h.get("work_envelope") or {}).get("recovery") or {}).get("route_generation") == recovery.get("route_generation")]
        if any(h.get("state") in {"PENDING", "ACK"} for h in existing):
            continue
        if recovery.get("ownership_state") == "ACCEPTED" or existing:
            continue  # failed/done transfer needs an explicit owner decision, not a retry loop
        owner, target = work.get("owner_role"), recovery.get("target_role")
        if owner not in ROLES or target not in ROLES:
            continue
        route = integrity.digest({"fingerprint": recovery["fingerprint"], "from": owner, "to": target,
                                  "generation": recovery.get("route_generation")})[:32]
        service.emit_handoff(request_id="REQ-RECOVERY-HO-" + route,
                             from_role=owner, to_role=target, handoff_type="BLOCKER_RECOVERY",
                             entity_ref=work["id"], thread_id=work["thread_id"], objective_ref=work.get("roadmap_id"),
                             summary_plain="O teste precisa recuperar condições verificáveis antes de executar.",
                             why_it_matters="A correção permite continuar o objetivo sem fabricar dados ou mudar os critérios científicos.",
                             next_action=work["next_action"], evidence_refs=[{"ref": work["test_id"], "kind": "TEST"}])
        count += 1
    return count


def status(root: str | Path) -> dict:
    items = [{key: work.get(key) for key in ("id", "test_id", "roadmap_id", "owner_role", "priority", "next_action", "recovery")}
             for work in _entities(Path(root), "work") if (work.get("recovery") or {}).get("policy") == POLICY
             and work.get("status") not in TERMINAL_WORK]
    return {"policy": POLICY, "open": len(items), "items": items,
            "ownership_scope": "ASSIGNMENT_IS_NOT_ACCEPTANCE", "scientific_effect": "NONE"}
