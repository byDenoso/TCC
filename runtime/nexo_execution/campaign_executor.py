from __future__ import annotations

from dataclasses import dataclass

_TERMINAL = {"DONE", "PASS", "FAIL", "INCONCLUSIVE", "TERMINAL"}
_ACTIVE = {"RUNNING", "CHECKPOINTED", "QUEUED", "DISPATCHED"}

_SCIENTIFIC_CONTRACT = {
    "hubble_flow_selection", "h0_estimator", "local_group_like_observer_criteria",
    "external_priors", "ladder_likelihood", "frozen_holdout",
    "calibrator_hubble_flow_membership", "ladder_contract",
    "nuisance_foreground_priors", "frozen_likelihood_matrix",
}
_CAPABILITIES = {"mock_observer_backend"}


def classify_dependency(dependency_id: str) -> str:
    """Map legacy dependency names onto the lean execution model.

    Scientific choices belong to the frozen scientific contract, computational
    engines are capabilities, and only actual data/products remain artifacts.
    """
    key = str(dependency_id or "").strip()
    if key in _SCIENTIFIC_CONTRACT:
        return "SCIENTIFIC_CONTRACT"
    if key in _CAPABILITIES:
        return "CAPABILITY"
    return "INPUT_ARTIFACT"


@dataclass(frozen=True)
class CampaignGraph:
    tests: tuple[str, ...]
    predecessors: dict[str, tuple[str, ...]]
    max_parallel: int = 10

    @classmethod
    def h0_lcdm_origin(cls, max_parallel: int = 10) -> "CampaignGraph":
        tests = tuple(f"T-H0LCDM26-{i:03d}" for i in range(1, 16))
        first = tuple(f"T-H0LCDM26-{i:03d}" for i in range(1, 11))
        predecessors = {test_id: () for test_id in first}
        predecessors.update({
            "T-H0LCDM26-011": first,
            "T-H0LCDM26-012": ("T-H0LCDM26-011",),
            "T-H0LCDM26-013": ("T-H0LCDM26-012",),
            "T-H0LCDM26-014": ("T-H0LCDM26-013",),
            "T-H0LCDM26-015": ("T-H0LCDM26-014",),
        })
        return cls(tests=tests, predecessors=predecessors, max_parallel=max_parallel)

    def ready_tests(self, states: dict[str, str]) -> list[str]:
        normalized = {key: str(value or "").upper() for key, value in states.items()}
        active = sum(1 for value in normalized.values() if value in _ACTIVE)
        budget = max(0, self.max_parallel - active)
        ready: list[str] = []
        for test_id in self.tests:
            state = normalized.get(test_id, "")
            if state in _TERMINAL or state in _ACTIVE:
                continue
            if all(normalized.get(parent, "") in _TERMINAL for parent in self.predecessors.get(test_id, ())):
                ready.append(test_id)
                if len(ready) >= budget:
                    break
        return ready
