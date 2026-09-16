from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingInput:
    expected_runtime_minutes: float | None = None
    requires_checkpoint: bool = False
    parallelizable: bool = False
    external_enabled: bool = True
    reversible: bool = True
    contract_known: bool = True
    capability_proven: bool = False
    material_risk: bool = False
    scientific_semantic_change: bool = False
    canonical_conflict: bool = False
    production_critical: bool = False
    new_capability: bool = False
    claim_change: bool = False
    conflicting_evidence: bool = False
    structural_migration: bool = False
    credential_boundary: bool = False


def choose_provider(inp: RoutingInput) -> str:
    if not inp.external_enabled:
        return "local"
    if inp.requires_checkpoint or inp.parallelizable:
        return "github_actions"
    if inp.expected_runtime_minutes is not None and inp.expected_runtime_minutes >= 10:
        return "github_actions"
    return "local"


def choose_execution_path(inp: RoutingInput) -> str:
    slow_path = (
        not inp.reversible
        or inp.scientific_semantic_change
        or inp.canonical_conflict
        or inp.production_critical
        or inp.new_capability
        or inp.claim_change
        or inp.conflicting_evidence
        or inp.structural_migration
        or inp.credential_boundary
    )
    if slow_path:
        return "SLOW_PATH"

    if inp.material_risk:
        return "STANDARD_PATH"

    if inp.contract_known and inp.capability_proven:
        return "FAST_PATH"

    return "STANDARD_PATH"


def should_run_preflight(
    inp: RoutingInput,
    *,
    version_changed: bool = False,
    contract_changed: bool = False,
    dependencies_changed: bool = False,
    health_changed: bool = False,
) -> bool:
    if not inp.capability_proven:
        return True
    return any(
        (
            version_changed,
            contract_changed,
            dependencies_changed,
            health_changed,
            inp.new_capability,
        )
    )
