from __future__ import annotations

from typing import Any

from runtime.nexo_execution.core import TASK_REGISTRY


_EXECUTABLE_STATES = {"ACTIVE", "PROVEN", "VALIDATED_CURRENT"}
_LEGITIMATE_BLOCKERS = {
    "SCIENTIFIC_DEFINITION_MISSING",
    "AUTHORIZATION_MISSING",
    "IRREVERSIBLE_CONFLICT",
}


def _is_executable(capability: dict[str, Any]) -> bool:
    status = str(capability.get("status") or "ACTIVE").upper()
    if status not in _EXECUTABLE_STATES:
        return False
    if not capability.get("backend"):
        return False
    return bool(capability.get("task_id") or capability.get("executable"))


def _blocker_class(test: dict[str, Any]) -> str:
    return str(
        test.get("blocker_class")
        or test.get("blocker_type")
        or test.get("blocker_reason_code")
        or ""
    ).upper()


class CapabilityExecutionResolver:
    """Resolve a TEST to executable runtime without making manifests existence gates."""

    def __init__(self, capabilities: dict[str, Any]) -> None:
        self.capabilities = capabilities

    def _resolved(self, capability_id: str, capability: dict[str, Any], reason: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "RESOLVED",
            "capability_id": capability_id,
            "backend": capability.get("backend"),
            "reason": reason,
            "resolution_source": "capability_manifest",
        }
        if capability.get("task_id"):
            result["task_id"] = capability["task_id"]
        if capability.get("executable"):
            result["executable"] = capability["executable"]
        return result

    @staticmethod
    def _runtime_task(task_id: str) -> dict[str, Any]:
        return {
            "status": "RESOLVED",
            "capability_id": f"runtime::{task_id}",
            "task_id": task_id,
            "backend": "runtime_registry",
            "reason": "allowlisted runtime task reuse",
            "resolution_source": "runtime_registry",
        }

    def resolve(self, test: dict[str, Any]) -> dict[str, Any]:
        blocker = _blocker_class(test)
        if blocker in _LEGITIMATE_BLOCKERS:
            return {
                "status": "BLOCKED",
                "reason_code": blocker,
                "reason": str(test.get("blocker") or blocker),
            }

        explicit_capability = str(test.get("capability_id") or "")
        task_id = str(test.get("task_id") or "")

        if explicit_capability:
            capability = self.capabilities.get(explicit_capability)
            if isinstance(capability, dict) and _is_executable(capability):
                return self._resolved(explicit_capability, capability, "explicit capability reuse")
            if task_id in TASK_REGISTRY:
                return self._runtime_task(task_id)
            return {
                "status": "NEEDS_ADAPTER",
                "reason": f"capability not executable: {explicit_capability}",
            }

        if task_id:
            for capability_id, capability in self.capabilities.items():
                if not isinstance(capability, dict) or not _is_executable(capability):
                    continue
                if capability_id == task_id or str(capability.get("task_id") or "") == task_id:
                    return self._resolved(str(capability_id), capability, "existing task_id reuse")
            if task_id in TASK_REGISTRY:
                return self._runtime_task(task_id)
            return {"status": "NEEDS_ADAPTER", "reason": f"task_id not allowlisted: {task_id}"}

        required = {str(value) for value in test.get("required_capabilities", []) if str(value)}
        if not required:
            return {"status": "NEEDS_ADAPTER", "reason": "no executable capability declared"}

        for capability_id, capability in self.capabilities.items():
            if not isinstance(capability, dict) or not _is_executable(capability):
                continue
            semantic = {str(value) for value in capability.get("semantic_capabilities", []) if str(value)}
            adapters = {str(value) for value in capability.get("adapter_for", []) if str(value)}
            if required.issubset(semantic | adapters):
                return self._resolved(str(capability_id), capability, "semantic capability match")

        missing = ", ".join(sorted(required))
        return {"status": "NEEDS_ADAPTER", "reason": f"no executable capability covers: {missing}"}
