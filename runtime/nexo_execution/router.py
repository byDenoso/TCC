from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingInput:
    expected_runtime_minutes: float | None = None
    requires_checkpoint: bool = False
    parallelizable: bool = False
    external_enabled: bool = True


def choose_provider(inp: RoutingInput) -> str:
    if not inp.external_enabled:
        return "local"
    if inp.requires_checkpoint or inp.parallelizable:
        return "github_actions"
    if inp.expected_runtime_minutes is not None and inp.expected_runtime_minutes >= 10:
        return "github_actions"
    return "local"
