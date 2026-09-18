from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingInput:
    expected_runtime_minutes: float | None = None
    requires_checkpoint: bool = False
    parallelizable: bool = False
    external_enabled: bool = True
    required_capabilities: tuple[str, ...] = ()


def choose_provider(inp: RoutingInput) -> str:
    # Portable scientific capabilities are local runtime resources. They must
    # not be routed through GitHub Actions merely because the surrounding job
    # is long-running or parallelizable. The capability adapter performs its
    # own hash/provenance checks and fails closed before task launch.
    if "peer.camb.exact_v2" in inp.required_capabilities:
        return "local"
    if not inp.external_enabled:
        return "local"
    if inp.requires_checkpoint or inp.parallelizable:
        return "github_actions"
    if inp.expected_runtime_minutes is not None and inp.expected_runtime_minutes >= 10:
        return "github_actions"
    return "local"
