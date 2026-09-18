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


def _frozen_scientific_contract(test: dict[str, Any]) -> dict[str, Any] | None:
    """Return an already-frozen scientific contract without inventing fields."""
    nested = test.get("frozen_test")
    if isinstance(nested, dict):
        required = (
            nested.get("id"),
            nested.get("method"),
            nested.get("decision_rule"),
            nested.get("outputs"),
            nested.get("claim_boundary"),
        )
        return dict(nested) if all(bool(value) for value in required) else None

    required = (
        test.get("id") or test.get("test_id"),
        test.get("mechanism"),
        test.get("input_contract"),
        test.get("estimator_contract"),
        test.get("decision_contract"),
        test.get("claim_boundary"),
    )
    if not all(bool(value) for value in required):
        return None
    frozen: dict[str, Any] = {
        "id": test.get("id") or test.get("test_id"),
        "method": {
            "mechanism": test.get("mechanism"),
            "input_contract": test.get("input_contract"),
            "estimator_contract": test.get("estimator_contract"),
        },
        "decision_rule": test.get("decision_contract"),
        "outputs": ["scientific_result"],
        "claim_boundary": test.get("claim_boundary"),
    }
    if test.get("null_contract") is not None:
        frozen["method"]["null_contract"] = test.get("null_contract")
    return frozen


def _repair_required(
    test: dict[str, Any],
    *,
    reason: str,
    requested_capability_id: str | None = None,
    requested_task_id: str | None = None,
    missing_capabilities: list[str] | None = None,
) -> dict[str, Any] | None:
    frozen = _frozen_scientific_contract(test)
    if frozen is None:
        return None
    method = frozen.get("method")
    mechanism = ""
    if isinstance(method, dict):
        mechanism = str(method.get("mechanism") or "")
    mechanism = mechanism or str(test.get("mechanism") or "")
    repair_contract: dict[str, Any] = {
        "test_id": str(frozen.get("id") or test.get("id") or test.get("test_id") or ""),
        "mechanism": mechanism,
        "execution_class": str(test.get("execution_class") or ""),
        "target_repository": "byDenoso/TCC",
        "required_action": "IMPLEMENT_OR_BIND_MINIMAL_EVALUATOR_THEN_REDISCOVER",
        "same_pulse": True,
        "scientific_contract": frozen,
    }
    if requested_capability_id:
        repair_contract["requested_capability_id"] = requested_capability_id
    if requested_task_id:
        repair_contract["requested_task_id"] = requested_task_id
    if missing_capabilities:
        repair_contract["missing_capabilities"] = sorted(set(missing_capabilities))
    return {
        "status": "REPAIR_REQUIRED",
        "reason_code": "CAPABILITY_REPAIR_REQUIRED",
        "reason": reason,
        "repairable": True,
        "repair_contract": repair_contract,
    }


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
            repair = _repair_required(
                test,
                reason=f"capability not executable: {explicit_capability}",
                requested_capability_id=explicit_capability,
                requested_task_id=task_id or None,
            )
            return repair or {
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
            repair = _repair_required(
                test,
                reason=f"task_id not allowlisted: {task_id}",
                requested_task_id=task_id,
            )
            return repair or {"status": "NEEDS_ADAPTER", "reason": f"task_id not allowlisted: {task_id}"}

        required = {str(value) for value in test.get("required_capabilities", []) if str(value)}
        if not required:
            repair = _repair_required(
                test,
                reason="complete frozen scientific contract has no executable capability binding",
            )
            return repair or {"status": "NEEDS_ADAPTER", "reason": "no executable capability declared"}

        for capability_id, capability in self.capabilities.items():
            if not isinstance(capability, dict) or not _is_executable(capability):
                continue
            semantic = {str(value) for value in capability.get("semantic_capabilities", []) if str(value)}
            adapters = {str(value) for value in capability.get("adapter_for", []) if str(value)}
            if required.issubset(semantic | adapters):
                return self._resolved(str(capability_id), capability, "semantic capability match")

        missing = sorted(required)
        repair = _repair_required(
            test,
            reason=f"no executable capability covers: {', '.join(missing)}",
            missing_capabilities=missing,
        )
        return repair or {"status": "NEEDS_ADAPTER", "reason": f"no executable capability covers: {', '.join(missing)}"}
