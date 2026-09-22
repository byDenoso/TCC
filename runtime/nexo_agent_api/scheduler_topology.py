from __future__ import annotations

from typing import Any

SCHEDULER_TOPOLOGY = "TWO_EXECUTORS_DOMAIN_SPLIT_V1"
EXECUTION_SCHEDULERS = {
    "GENERAL": "NEXO_GENERAL_EXECUTION_LOOP",
    "SCIENCE": "NEXO_CORE_LOOP_LEAN_MIN_V2",
}


def reconcile_scheduler_policy(control: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical policy shape matching the deployed recurring runtime."""
    current = dict(control.get("domain_workflow_policy") or {})
    desired = {
        **current,
        "one_scheduler_for_all_domains": False,
        "execution_scheduler_topology": SCHEDULER_TOPOLOGY,
        "execution_schedulers": dict(EXECUTION_SCHEDULERS),
        "scheduler_coordination": "CANONICAL_STATE_CURSOR_MATERIAL_DELTA",
        "learning_loops_are_execution_schedulers": False,
    }
    changed = desired != current
    return {
        "changed": changed,
        "previous": current,
        "domain_workflow_policy": desired,
    }
