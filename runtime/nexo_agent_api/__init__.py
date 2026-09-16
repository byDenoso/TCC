"""Operational UX helpers for NEXO v0.7 agents."""

from .service import AgentService, TowerAgentIssue
from .handoff import install_handoff_protocol
from .ingress import install_request_ingress_protocol
from .test_registry import register_test

install_handoff_protocol(AgentService)
install_request_ingress_protocol(AgentService)

from .views import materialize_role_views

__all__ = ["AgentService", "TowerAgentIssue", "materialize_role_views", "register_test"]
