from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GovernanceDecision:
    allowed: bool
    autonomy_level: str
    gate: str
    issue_code: str | None = None
    message: str | None = None


L4_POLICY_TARGET = ("governance", "NEXO_RSI_POLICY")
L4_ALLOWED_KEYS = {
    "retry_limit",
    "parallelism",
    "test_budget",
    "ranking_weights",
    "lane_priority",
    "promotion_threshold",
    "quarantine_threshold",
    "rollback_window",
    "shadow_evaluation_cycles",
}
L5_ENTITY_KINDS = {"constitution", "l5", "sovereign"}
L5_RESERVED_KEYS = {
    "human_override",
    "authority_root",
    "truth_owner",
    "truth_owners",
    "writer_authority",
    "writer_authorities",
    "permission_boundary",
    "permission_boundaries",
    "repository_permissions",
    "tool_permissions",
    "autonomy_ceiling",
    "l4_allowlist",
    "l5_rules",
    "constitution",
    "sovereign_layer",
}


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_promotion_evidence(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for key in ("baseline_ref", "hypothesis_ref", "metric", "rollback_ref"):
        if not _nonempty_string(value.get(key)):
            return False
    refs = value.get("evidence_refs")
    if not isinstance(refs, list) or not refs or not all(_nonempty_string(ref) for ref in refs):
        return False
    gain = value.get("observed_gain")
    if isinstance(gain, bool) or not isinstance(gain, (int, float)) or gain <= 0:
        return False
    return value.get("regression_passed") is True


def _declared_level(request: dict[str, Any]) -> str:
    raw = str(request.get("autonomy_level") or "L0").upper()
    return raw if raw in {"L0", "L1", "L2", "L3", "L4", "L5"} else "L0"


def evaluate_governance(request: dict[str, Any]) -> GovernanceDecision:
    entity_kind = str(request.get("entity_kind") or "").lower()
    entity_name = str(request.get("entity_name") or "")
    changes = request.get("changes")
    changed_keys = set(changes) if isinstance(changes, dict) else set()

    if entity_kind in L5_ENTITY_KINDS or changed_keys.intersection(L5_RESERVED_KEYS):
        return GovernanceDecision(
            allowed=False,
            autonomy_level="L5",
            gate="L5_HUMAN_ONLY",
            issue_code="L5_BOUNDARY_HUMAN_AUTHORITY_REQUIRED",
            message="L5 authority changes require human authority.",
        )

    declared = _declared_level(request)
    effective = "L4" if (entity_kind, entity_name) == L4_POLICY_TARGET else declared

    if effective == "L5":
        return GovernanceDecision(
            allowed=False,
            autonomy_level="L5",
            gate="L5_HUMAN_ONLY",
            issue_code="L5_BOUNDARY_HUMAN_AUTHORITY_REQUIRED",
            message="L5 authority changes require human authority.",
        )

    if effective != "L4":
        return GovernanceDecision(allowed=True, autonomy_level=effective, gate="PASS")

    if (entity_kind, entity_name) != L4_POLICY_TARGET:
        return GovernanceDecision(
            allowed=False,
            autonomy_level="L4",
            gate="L4_TARGET_NOT_ALLOWLISTED",
            issue_code="L4_POLICY_TARGET_NOT_ALLOWLISTED",
            message="L4 policy mutation target is not allowlisted.",
        )

    disallowed = sorted(changed_keys - L4_ALLOWED_KEYS)
    if disallowed:
        return GovernanceDecision(
            allowed=False,
            autonomy_level="L4",
            gate="L4_KEY_NOT_ALLOWLISTED",
            issue_code="L4_POLICY_KEY_NOT_ALLOWLISTED",
            message=f"L4 policy keys are not allowlisted: {', '.join(disallowed)}",
        )

    if not _valid_promotion_evidence(request.get("governance_evidence")):
        return GovernanceDecision(
            allowed=False,
            autonomy_level="L4",
            gate="L4_EVIDENCE_REQUIRED",
            issue_code="L4_PROMOTION_EVIDENCE_REQUIRED",
            message="L4 policy promotion requires positive evidence, regression pass, and rollback reference.",
        )

    return GovernanceDecision(allowed=True, autonomy_level="L4", gate="PASS")
