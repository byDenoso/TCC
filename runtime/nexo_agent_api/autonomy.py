"""Bounded autonomy over the existing Tower, dormant until authenticated approval.

The caller supplies verified human proposal hashes only after the gateway's
protected verifier has checked its signed attestation. Persisted metadata and
agent prose never authenticate a human. Tokens are process-local capabilities.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "NEXO_AUTONOMY_MANDATE_V1"
FRAGMENT_SCHEMA = "NEXO_OPERATIONAL_PROMPT_FRAGMENT_V1"
FRAGMENTS_DOC = "evolution/autonomy_prompt_fragments.json"
CAPACITY_DOC = "evolution/autonomy_capacity.json"
ACTIONS = {"APPROVE_AUTONOMY_MANDATE", "REVOKE_AUTONOMY_MANDATE"}
ROLES = {"LEARNER", "EXECUTOR", "ENGINEER", "REFEREE_1", "GUARDIAO"}
EVOLVABLE = {"priority", "public_sources", "attack_strategy", "operational_prompt_fragment"}
IMMUTABLE = ("authority", "frozen_science", "scheduler", "models", "access", "credentials", "cost")


class _Authority:
    def __deepcopy__(self, memo):
        return self


HUMAN_AUTHORITY = _Authority()
WRITER_AUTHORITY = _Authority()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def envelope_hash(item):
    return digest({key: item[key] for key in ("kind", "source", "created_at", "payload") if key in item})


def read(root, relative):
    try:
        value = json.loads((Path(root) / relative).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def attach_human_authority(item, verified_hashes):
    """Called only by trusted Writer context, never inferred from the envelope."""
    safe = {key: value for key, value in item.items() if key != "_autonomy_human_authority"}
    if (str(safe.get("source") or "").upper() == "DENER"
            and safe.get("kind") == "OPERATOR_INTENT"
            and (safe.get("payload") or {}).get("action") in ACTIONS
            and envelope_hash(safe) in (verified_hashes or ())):
        safe["_autonomy_human_authority"] = HUMAN_AUTHORITY
    return safe


def mandate(root):
    value = read(root, "CONTROL.json").get("autonomy_mandate")
    return value if isinstance(value, dict) else {}


def active(root, mandate_id=None):
    value = mandate(root)
    return (value.get("schema") == SCHEMA and value.get("status") == "ACTIVE"
            and value.get("domain") == "OBSERVATIONAL_COSMOLOGY"
            and value.get("public_data_only") is True and value.get("no_additional_cost") is True
            and value.get("runner") == "GITHUB_ACTIONS_STANDARD_PUBLIC"
            and (mandate_id is None or value.get("id") == mandate_id))


def status(root):
    value = mandate(root)
    capacity = read(root, CAPACITY_DOC)
    return {"schema": SCHEMA, "status": value.get("status") or "PREPARED_INACTIVE",
            "active": active(root), "mandate_id": value.get("id"), "revision": value.get("revision"),
            "parallelism": parallelism(root), "max_parallelism": 20,
            "capacity_next_stage": {1: 2, 2: 4}.get(parallelism(root)),
            "quota_status": (capacity.get("quota") or {}).get("status") or "UNVERIFIED",
            "activation_gate": "AUTHENTICATED_HUMAN_APPROVAL_REQUIRED",
            "immutable_constraints": list(IMMUTABLE), "evaluation_hours": 168}


def parallelism(root):
    capacity = read(root, CAPACITY_DOC)
    value = capacity.get("parallelism")
    return value if type(value) is int and value in {1, 2, 4} and capacity.get("mandate_id") == mandate(root).get("id") else 1


def operator_requests(item, body, root):
    from .inbox_apply import ProposalError
    action = body.get("action")
    if action not in ACTIONS:
        return None
    if item.get("_autonomy_human_authority") is not HUMAN_AUTHORITY:
        raise ProposalError("AUTHENTICATED_HUMAN_MANDATE_REQUIRED")
    mid = str(body.get("mandate_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", mid):
        raise ProposalError("MANDATE_ID_INVALID")
    current = mandate(root)
    proposal = envelope_hash(item)
    if current.get("last_proposal_sha256") == proposal:
        return []
    revision = body.get("expected_revision", 0)
    if type(revision) is not int or revision != int(current.get("revision") or 0):
        raise ProposalError("MANDATE_REVISION_CONFLICT")
    at = item.get("created_at")
    if timestamp(at) is None or not str(body.get("approval_ref") or "").strip():
        raise ProposalError("MANDATE_APPROVAL_REFERENCE_REQUIRED")
    if action == "REVOKE_AUTONOMY_MANDATE":
        if current.get("id") != mid:
            raise ProposalError("MANDATE_ID_CONFLICT")
        value = dict(current, status="REVOKED", revision=revision + 1, revoked_at=at)
    else:
        # Revocation is permanent for this mandate identity. A fresh human
        # approval must name a new ID; delayed approval can never resurrect it.
        retired = read(root, "CONTROL.json").get("revoked_autonomy_mandates") or []
        if mid in retired or (current.get("id") == mid and current.get("status") == "REVOKED"):
            raise ProposalError("REVOKED_MANDATE_CANNOT_REACTIVATE")
        if active(root):
            raise ProposalError("ACTIVE_MANDATE_REQUIRES_REVOCATION")
        receipt = body.get("activation_receipt")
        checks = receipt.get("checks") if isinstance(receipt, dict) else None
        required = {"transport", "writer", "public_projection", "prompts", "quota"}
        if (not isinstance(checks, dict) or any(checks.get(key) is not True for key in required)
                or not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("source_revision") or ""))
                or "tcc_revision" in receipt and not re.fullmatch(r"[0-9a-f]{40}", str(receipt["tcc_revision"]))
                or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", str(receipt.get("tower_fingerprint") or ""))
                or timestamp(receipt.get("checked_at")) is None):
            raise ProposalError("MANDATE_ACTIVATION_PROOF_INCOMPLETE")
        from .capacity_guard import POLICY as CAPACITY_POLICY
        value = {"schema": SCHEMA, "id": mid, "revision": revision + 1, "status": "ACTIVE",
                 "domain": "OBSERVATIONAL_COSMOLOGY", "public_data_only": True, "no_additional_cost": True,
                 "runner": "GITHUB_ACTIONS_STANDARD_PUBLIC", "initial_parallelism": 1, "max_parallelism": 20,
                 "activated_at": at, "activation_receipt": receipt, "immutable_constraints": list(IMMUTABLE),
                 "capacity_policy": dict(CAPACITY_POLICY)}
    value.update(approval_ref=body["approval_ref"], last_proposal_sha256=proposal)
    merge = {"autonomy_mandate": value}
    if action == "REVOKE_AUTONOMY_MANDATE":
        merge["revoked_autonomy_mandates"] = sorted(set((read(root, "CONTROL.json").get("revoked_autonomy_mandates") or []) + [mid]))
    requests = [{"request_id": "REQ-AUTONOMY-" + proposal[:32], "document": "CONTROL.json", "merge": merge,
                 "expected_mandate_revision": revision, "_autonomy_authority": HUMAN_AUTHORITY}]
    if action == "APPROVE_AUTONOMY_MANDATE":
        requests.append({"request_id": "REQ-AUTONOMY-CAPACITY-" + proposal[:32], "document": CAPACITY_DOC,
                         "merge": {"mandate_id": mid, "parallelism": 1, "stage_started_at": at,
                                   "quota": {"status": "AVAILABLE_FREE", "standard_public_runners": True,
                                             "additional_cost": 0, "checked_at": receipt["checked_at"],
                                             "approval_ref": body["approval_ref"]}},
                         "_autonomy_authority": WRITER_AUTHORITY})
    return requests


def guard_document(root, request):
    """Control and evaluated fragments cannot be changed by generic requests."""
    relative = request.get("document")
    protected = relative in {"CONTROL.json", FRAGMENTS_DOC, CAPACITY_DOC, "evolution/public_campaign_approvals.json",
                             "evolution/autonomy_capacity_reviews.json"}
    token = request.get("_autonomy_authority")
    allowed = token is HUMAN_AUTHORITY if relative == "CONTROL.json" else token is WRITER_AUTHORITY
    if protected and not allowed:
        return {"accepted": False, "request_id": request.get("request_id"),
                "issue": {"code": "AUTONOMY_PROTECTED_DOCUMENT"}}
    if relative == "evolution/genome.json":
        existing = {gene.get("id"): gene for gene in read(root, relative).get("genes") or []}
        if any(evolvable(gene) for gene in existing.values()) and token is not WRITER_AUTHORITY:
            return {"accepted": False, "issue": {"code": "AUTONOMY_GENE_REQUIRES_EVALUATED_CONVERTER"}}
        for gene in (request.get("merge") or {}).get("genes") or []:
            if (evolvable(gene) or evolvable(existing.get(gene.get("id"), {}))) and token is not WRITER_AUTHORITY:
                return {"accepted": False, "issue": {"code": "AUTONOMY_GENE_REQUIRES_EVALUATED_CONVERTER"}}
    if relative == "CONTROL.json":
        if (set(request.get("merge") or {}) - {"autonomy_mandate", "revoked_autonomy_mandates"}
                or request.get("expected_mandate_revision") != int(mandate(root).get("revision") or 0)):
            return {"accepted": False, "issue": {"code": "MANDATE_REVISION_OR_TARGET_CONFLICT"}}
    return None


def public_urls(value):
    urls = value if isinstance(value, list) else []
    return bool(urls) and all(isinstance(url, str) and urlsplit(url).scheme == "https"
                            and urlsplit(url).hostname and not urlsplit(url).username
                            and not urlsplit(url).password for url in urls)


def charter_allowed(root, body):
    """A standing mandate applies only to new explicitly scoped charters."""
    budget = body.get("budget") or {}
    return (active(root, body.get("mandate_id")) and body.get("domain") == "OBSERVATIONAL_COSMOLOGY"
            and body.get("public_data_only") is True and public_urls(body.get("public_data_refs"))
            and all(type(budget.get(key)) is int and budget[key] > 0 for key in ("max_tests", "max_days")))


def admission(root, tests, count, now=None):
    """Quota/capacity apply only to mandate-backed work; legacy runs keep their contract."""
    scoped = [test for test in tests if test.get("mandate_id")]
    if not scoped:
        return None
    if len(scoped) != len(tests) or any(not active(root, test.get("mandate_id")) for test in tests):
        return "AUTONOMY_MANDATE_INACTIVE_OR_MIXED"
    for test in scoped:
        if str(test.get("domain") or "").upper() not in {"SCIENCE", "COSMOLOGY", "COSMOLOGIA", "OBSERVATIONAL_COSMOLOGY"}:
            return "AUTONOMY_DOMAIN_OUT_OF_SCOPE"
        inputs = (test.get("data_binding") or test.get("input_binding") or {}).get("inputs") or []
        if (test.get("public_data_only") is not True or test.get("visibility") != "PUBLIC"
                or not inputs or any(not public_input(value) for value in inputs)):
            return "AUTONOMY_PUBLIC_PROVENANCE_REQUIRED"
    capacity = read(root, CAPACITY_DOC)
    quota = capacity.get("quota") or {}
    now = now or datetime.now(timezone.utc)
    checked = timestamp(quota.get("checked_at"))
    if (capacity.get("mandate_id") != mandate(root).get("id") or quota.get("status") != "AVAILABLE_FREE"
            or quota.get("standard_public_runners") is not True or quota.get("additional_cost") != 0
            or not checked or not 0 <= (now - checked).total_seconds() <= 3600):
        return "AUTONOMY_FREE_QUOTA_UNVERIFIED"
    from .scientific_integrity import batteries, ACTIVE
    reserved = sum(len(battery.get("tests") or []) for battery in batteries(root) if battery.get("status") in ACTIVE)
    if reserved + count > parallelism(root):
        return "AUTONOMY_GLOBAL_CAPACITY_FULL"
    return None


def valid_fragment(value):
    if not isinstance(value, dict) or value.get("role") not in ROLES:
        return False
    text = value.get("text")
    return (type(value.get("version")) is int and value["version"] > 0
            and isinstance(text, str) and 0 < len(text) <= 12000
            and value.get("sha256") == hashlib.sha256(text.encode("utf-8")).hexdigest())


def frozen_package(battery):
    return {"schema": "NEXO_SCIENTIFIC_PACKAGE_V1", "battery_id": battery["id"],
            **{key: battery[key] for key in ("mandate_id", "mandate_revision", "source_revision", "parallelism", "tests")}}


def package_json(battery):
    return json.dumps(frozen_package(battery), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def public_input(value):
    if not isinstance(value, dict) or value.get("public") is not True:
        return False
    if not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", str(value.get("sha256") or "")):
        return False
    if value.get("kind") == "generated":
        return bool(value.get("generator")) and type(value.get("seed")) is int
    url = value.get("url") or value.get("source_url")
    if not public_urls([url]):
        return False
    parsed = urlsplit(url)
    return not parsed.query and not parsed.fragment


def capacity_requests(root, verified_observation, now=None):
    """Trusted collector context only; no inbox payload can refresh quota or increase capacity."""
    if not isinstance(verified_observation, dict) or not active(root):
        return []
    now = now or datetime.now(timezone.utc)
    quota = verified_observation.get("quota") or {}
    if (quota.get("status") not in {"AVAILABLE_FREE", "UNAVAILABLE", "UNVERIFIED"}
            or timestamp(quota.get("checked_at")) is None
            or quota.get("standard_public_runners") is not True
            or quota.get("additional_cost") != 0):
        return []
    capacity = read(root, CAPACITY_DOC)
    stage = parallelism(root)
    requested = verified_observation.get("parallelism", stage)
    if requested != stage:
        if requested != {1: 2, 2: 4}.get(stage):
            return []
        from .capacity_guard import approved
        refs = verified_observation.get("battery_refs") or []
        review = approved(root, verified_observation.get("review_ref"), now)
        checked = timestamp(quota.get("checked_at"))
        if (not review or review["next_parallelism"] != requested or review["battery_refs"] != refs
                or quota["status"] != "AVAILABLE_FREE"
                or not 0 <= (now - checked).total_seconds() <= 3600):
            return []
        capacity["capacity_review_ref"] = verified_observation["review_ref"]
        capacity["stage_started_at"] = now.isoformat().replace("+00:00", "Z")
    capacity.update(mandate_id=mandate(root)["id"], parallelism=requested, quota=quota)
    return [{"request_id": "REQ-AUTONOMY-CAPACITY-" + digest(capacity)[:32], "document": CAPACITY_DOC,
             "merge": capacity, "_autonomy_authority": WRITER_AUTHORITY}]


def prompt_fragment(root, role):
    role = {"ADVISOR": "ENGINEER", "REFUTADOR": "REFEREE_1"}.get(role, role)
    document = read(root, FRAGMENTS_DOC)
    if document.get("schema") != FRAGMENT_SCHEMA or not active(root):
        return None
    rows = document.get("fragments") or []
    row = next((row for row in rows if row.get("role") == role), None)
    if not valid_fragment(row) or row.get("mandate_id") != mandate(root).get("id") or not row.get("independent_review_ref"):
        return None
    gene = next((gene for gene in read(root, "evolution/genome.json").get("genes") or [] if gene.get("id") == row.get("gene_id")), {})
    if (gene.get("status") != "CANONICAL" or gene.get("canonical") != {key: row[key] for key in ("role", "version", "text", "sha256")}
            or row.get("approval_ref") != mandate(root).get("approval_ref")):
        return None
    return dict(row)


def evolvable(gene):
    return gene.get("evolution_kind") in EVOLVABLE


def valid_gene_value(kind, value):
    if kind == "operational_prompt_fragment":
        return valid_fragment(value)
    if kind == "public_sources":
        return public_urls(value)
    if kind == "attack_strategy":
        return isinstance(value, str) and 0 < len(value) <= 12000
    if kind == "priority":
        return type(value) in {int, float, str} and bool(str(value).strip())
    return False


def gene_evaluation(root, gene):
    """Read actual independent evaluation records, not boolean claims in a proposal."""
    ref = str(gene.get("independent_evaluation_ref") or "")
    if not re.fullmatch(r"entities/evidence/[A-Za-z0-9_-]+\.json", ref):
        return None
    report = read(root, ref)
    plan = gene.get("evaluation_plan") or {}
    frozen_at = timestamp(gene.get("evaluation_frozen_at"))
    minimum_gain = plan.get("minimum_gain")
    units = plan.get("units")
    if (report.get("schema") != "NEXO_OPERATIONAL_GENE_EVALUATION_V1"
            or report.get("gene_id") != gene.get("id") or report.get("canary_sha256") != digest(gene.get("canary"))
            or report.get("plan_sha256") != digest(plan) or report.get("reviewer_role") not in {"REFEREE_1", "GUARDIAO"}
            or report.get("reviewer_role") == gene.get("proposed_by")
            or report.get("decision") != "PASS" or report.get("regression_passed") is not True
            or report.get("rollback_ref") != "sha256:" + digest(gene.get("canonical")) or not plan.get("metric")
            or type(plan.get("minimum_rounds_per_arm")) is not int or plan["minimum_rounds_per_arm"] < 10
            or not frozen_at or gene.get("evaluation_plan_sha256") != digest(plan)
            or type(minimum_gain) not in {int, float} or not math.isfinite(minimum_gain) or minimum_gain <= 0
            or type(plan.get("higher_is_better")) is not bool or not isinstance(units, list)):
        return None
    rows = report.get("observations") or []
    if not isinstance(rows, list):
        return None
    expected = {(unit.get("test_id"), unit.get("arm")) for unit in units if isinstance(unit, dict)}
    if len(expected) != len(units) or len({unit[0] for unit in expected}) != len(units):
        return None
    seen, counts = set(), {"canonical": 0, "canary": 0}
    values = {"canonical": [], "canary": []}
    from .scientific_integrity import batteries, RUN_REF, independence
    from .evolution import _attack_outcome
    attempts = {battery.get("id"): battery for battery in batteries(root)}
    for observation in rows:
        if not isinstance(observation, dict):
            return None
        tid, arm = observation.get("test_id"), observation.get("arm")
        if not isinstance(tid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", tid) or arm not in counts or tid in seen or (tid, arm) not in expected:
            return None
        test = read(root, "entities/test/" + tid + ".json")
        if (test.get("gene_id") != gene.get("id") or test.get("gene_arm") != arm
                or test.get("gene_plan_sha256") != gene["evaluation_plan_sha256"]
                or test.get("review_state") not in {"CONFIRMED", "REFUTED"}
                or not test.get("executed_at") or not test.get("verdict")):
            return None
        # A review label or claimed reviewer in an evaluation document is not
        # evidence. Recheck its independently frozen, executed contest and the
        # canonical review's author and polarity for every evaluated unit.
        verified_review = False
        for review in test.get("reviews") or []:
            if (not isinstance(review, dict) or review.get("referee") != report["reviewer_role"]
                    or not timestamp(review.get("at"))):
                continue
            attack_id = str(review.get("contest_test_id") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", attack_id):
                continue
            attack = read(root, "entities/test/" + attack_id + ".json")
            contest = next((entry for entry in test.get("contests") or []
                            if entry.get("contest_test_id") == attack_id), {})
            result = _attack_outcome(attack)
            declaration = attack.get("independence") or {}
            expected_review = declaration.get("on_pass" if result == "CONFIRMED" else "on_fail")
            if (contest.get("by") == report["reviewer_role"] and attack.get("contests_test_id") == tid
                    and timestamp(attack.get("executed_at"))
                    and result and expected_review == test["review_state"]
                    and independence(test, attack, Path(root))["eligible"]):
                verified_review = True
                break
        if not verified_review:
            return None
        executed_at, started_at = timestamp(test["executed_at"]), timestamp(test.get("started_at"))
        attempt = attempts.get(test.get("battery_id"), {})
        spec = next((spec for spec in attempt.get("tests") or [] if spec.get("test_id") == tid), {})
        if (not executed_at or not started_at or started_at < frozen_at or executed_at <= frozen_at
                or attempt.get("status") != "DONE" or attempt.get("conclusion") != "success"
                or attempt.get("run_ref") != test.get("run_ref")
                or not RUN_REF.fullmatch(str(test.get("run_ref") or ""))
                or not test.get("attempt_id") or spec.get("attempt_id") != test["attempt_id"]
                or spec.get("gene_plan_sha256") != gene["evaluation_plan_sha256"]
                or spec.get("gene_id") != gene["id"] or spec.get("gene_arm") != arm):
            return None
        value = (1 if test["review_state"] == "CONFIRMED" else 0) if plan["metric"] == "confirmed_per_test" else (test.get("statistics") or {}).get(plan["metric"])
        if type(value) not in {int, float} or not math.isfinite(value):
            return None
        values[arm].append(value)
        seen.add(tid)
        counts[arm] += 1
    if seen != {unit[0] for unit in expected} or any(count < plan["minimum_rounds_per_arm"] for count in counts.values()):
        return None
    gain = sum(values["canary"]) / counts["canary"] - sum(values["canonical"]) / counts["canonical"]
    if not plan["higher_is_better"]:
        gain = -gain
    if gain < minimum_gain:
        return None
    return report


def canonization_requests(root):
    """Writer promotes only evaluated operational genes under a live mandate."""
    if not active(root):
        return []
    genome = read(root, "evolution/genome.json")
    generation = int(genome.get("generation") or 0)
    lineage = list(genome.get("lineage") or [])
    fragments = read(root, FRAGMENTS_DOC).get("fragments") or []
    changes, fragment_changes = [], []
    for gene in genome.get("genes") or []:
        if (gene.get("status") != "CANARY" or not evolvable(gene)
                or not active(root, gene.get("mandate_id"))
                or not valid_gene_value(gene["evolution_kind"], gene.get("canary"))):
            continue
        report = gene_evaluation(root, gene)
        if not report:
            continue
        if gene["evolution_kind"] == "operational_prompt_fragment":
            fragment = dict(gene["canary"])
            previous = next((row for row in fragments if row.get("role") == fragment["role"]), {})
            if fragment["version"] != int(previous.get("version") or 0) + 1:
                continue
            fragment.update(mandate_id=gene["mandate_id"], gene_id=gene["id"],
                            approval_ref=mandate(root)["approval_ref"], independent_review_ref=gene["independent_evaluation_ref"])
            fragment_changes.append(fragment)
        generation += 1
        changes.append({"id": gene["id"], "status": "CANONICAL", "canonical": gene["canary"], "canary": None,
                        "last_decision": {"action": "CANONIZED", "authority": "STANDING_HUMAN_MANDATE",
                                          "mandate_id": gene["mandate_id"], "generation": generation,
                                          "evidence_ref": gene["independent_evaluation_ref"]}})
        lineage.append({"generation": generation, "gene": gene["id"], "from": gene.get("canonical"),
                        "to": gene["canary"], "evidence": gene["independent_evaluation_ref"],
                        "evidence_sha256": digest(report), "mandate_id": gene["mandate_id"]})
    if not changes:
        return []
    requests = [{"request_id": "REQ-AUTONOMY-GENES-" + digest(changes)[:32], "document": "evolution/genome.json",
                 "merge": {"generation": generation, "genes": changes, "lineage": lineage},
                 "list_merge": {"genes": "id"}, "_autonomy_authority": WRITER_AUTHORITY}]
    if fragment_changes:
        requests.append({"request_id": "REQ-AUTONOMY-FRAGMENTS-" + digest(fragment_changes)[:32],
                         "document": FRAGMENTS_DOC, "merge": {"schema": FRAGMENT_SCHEMA, "fragments": fragment_changes},
                         "list_merge": {"fragments": "role"}, "_autonomy_authority": WRITER_AUTHORITY})
    return requests
