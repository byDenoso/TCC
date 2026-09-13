from __future__ import annotations

CAMPAIGN_TRANSITIONS = {
    "PLANNED": {"READY", "BLOCKED"},
    "READY": {"RUNNING", "BLOCKED"},
    "RUNNING": {"VALIDATING", "FAILED", "BLOCKED"},
    "VALIDATING": {"LEARNING", "FAILED", "BLOCKED"},
    "LEARNING": {"CLOSED", "FAILED", "BLOCKED"},
    "BLOCKED": {"READY", "FAILED"},
    "FAILED": set(),
    "CLOSED": set(),
}

TEST_TRANSITIONS = {
    "PLANNED": {"READY", "BLOCKED"},
    "READY": {"DISPATCHED", "BLOCKED"},
    "DISPATCHED": {"RUNNING", "FAILED", "BLOCKED"},
    "RUNNING": {"VALIDATING", "FAILED"},
    "VALIDATING": {"PASSED", "NOT_PROMOTED", "FAILED", "BLOCKED"},
    "BLOCKED": {"READY", "FAILED"},
    "PASSED": set(),
    "NOT_PROMOTED": set(),
    "FAILED": set(),
}


def _transition(kind: str, transitions: dict[str, set[str]], current: str, target: str) -> str:
    if current not in transitions or target not in transitions[current]:
        raise ValueError(f"illegal {kind} transition: {current} -> {target}")
    return target


def transition_campaign_state(current: str, target: str) -> str:
    return _transition("campaign", CAMPAIGN_TRANSITIONS, current, target)


def transition_test_state(current: str, target: str) -> str:
    return _transition("test", TEST_TRANSITIONS, current, target)
