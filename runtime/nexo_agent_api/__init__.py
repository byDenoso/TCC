"""Operational UX helpers for NEXO v0.7 agents."""

from .service import AgentService, TowerAgentIssue
from .handoff import install_handoff_protocol
from .ingress import install_request_ingress_protocol
from .scheduler_visibility import repair_orphan_runnable_tests
from .test_registry import register_test
from .views import materialize_role_views as _materialize_role_views

install_handoff_protocol(AgentService)
install_request_ingress_protocol(AgentService)


def materialize_role_views(root):
    """Materialize role views only after enforcing TEST -> WORK visibility."""
    visibility = repair_orphan_runnable_tests(root)
    result = _materialize_role_views(root)
    result["scheduler_visibility"] = visibility
    return result


__all__ = ["AgentService", "TowerAgentIssue", "materialize_role_views", "register_test"]
