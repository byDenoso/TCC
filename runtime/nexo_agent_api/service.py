from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.nexo_execution.core import TASK_REGISTRY
from .tower_paths import entity_path, json_file


class TowerAgentIssue(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class AgentService:
    """Small file-backed operational contract for NEXO agents."""

    ROLES = {"DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT"}
    LEGACY_ADVISOR_KINDS = {"ACTION", "RESEARCH", "REVIEW", "PROCEDURAL_HYPOTHESIS", "ENGINEERING_FIX"}
    LEGITIMATE_BLOCKERS = {
        "SCIENTIFIC_DEFINITION_MISSING",
        "AUTHORIZATION_MISSING",
        "IRREVERSIBLE_CONFLICT",
    }

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _read_json(self, relative: str) -> dict[str, Any]:
        path = self.root / relative
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise TowerAgentIssue("TOWER_FILE_NOT_FOUND", "Tower file not found.", {"path": relative}) from exc
        if not isinstance(payload, dict):
            raise TowerAgentIssue("TOWER_JSON_NOT_OBJECT", "Tower JSON root must be an object.", {"path": relative})
        return payload

    @staticmethod
    def _normalize_work(item: dict[str, Any]) -> dict[str, Any] | None:
        work_id = item.get("id") or item.get("work_id")
        if not work_id:
            return None
        normalized = dict(item)
        normalized.setdefault("id", str(work_id))
        return normalized

    def _work_items(self) -> list[dict[str, Any]]:
        index_path = self.root / "indexes" / "active-work.json"
        folder = self.root / "entities" / "work"
        items: dict[str, dict[str, Any]] = {}

        if index_path.exists():
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            for item in payload.get("work", []):
                if isinstance(item, dict):
                    normalized = self._normalize_work(item)
                    if normalized is not None:
                        items[str(normalized["id"])] = normalized

        if folder.exists():
            for path in sorted(folder.glob("*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    normalized = self._normalize_work(payload)
                    if normalized is not None:
                        items[str(normalized["id"])] = normalized

        return list(items.values())

    def _hydrate_work(self, entity_name: str) -> dict[str, Any]:
        for item in self._work_items():
            if str(item.get("id")) == entity_name:
                path = entity_path(self.root, "work", entity_name)
                path.parent.mkdir(parents=True, exist_ok=True)
                hydrated = dict(item)
                hydrated.setdefault("entity_version", 1)
                path.write_text(json.dumps(hydrated, ensure_ascii=False, sort_keys=True), encoding="utf-8")
                return hydrated
        raise TowerAgentIssue("ENTITY_NOT_FOUND", "Canonical entity does not exist.", {"entity_kind": "work", "entity_name": entity_name})

    @classmethod
    def _has_legitimate_blocker(cls, item: dict[str, Any]) -> bool:
        blocker_class = str(
            item.get("blocker_class")
            or item.get("blocker_type")
            or item.get("blocker_reason_code")
            or ""
        ).upper()
        return blocker_class in cls.LEGITIMATE_BLOCKERS

    @staticmethod
    def _manifest_has_task(task_id: str, capabilities: dict[str, Any]) -> bool:
        for capability_id, capability in capabilities.items():
            if not isinstance(capability, dict):
                continue
            status = str(capability.get("status") or "ACTIVE").upper()
            if status not in {"ACTIVE", "PROVEN", "VALIDATED_CURRENT"}:
                continue
            if str(capability_id) == task_id or str(capability.get("task_id") or "") == task_id:
                return bool(capability.get("backend") or capability.get("executable") or capability.get("task_id"))
        return False

    @classmethod
    def _executor_eligible(cls, item: dict[str, Any], capabilities: dict[str, Any]) -> bool:
        if item.get("owner_role") != "EXECUTOR" or item.get("status") not in {"READY", "RUNNING", "CHECKPOINTED"}:
            return False
        if cls._has_legitimate_blocker(item):
            return False
        if str(item.get("execution_policy") or "AUTO").upper() == "MANUAL":
            return False

        task_id = str(item.get("task_id") or "")
        if task_id:
            return task_id in TASK_REGISTRY or cls._manifest_has_task(task_id, capabilities)

        frozen_test = item.get("frozen_test")
        if not isinstance(frozen_test, dict):
            return False
        required_frozen = (
            bool(frozen_test.get("id")),
            bool(frozen_test.get("method")),
            bool(frozen_test.get("decision_rule")),
            bool(frozen_test.get("outputs")),
            bool(frozen_test.get("claim_boundary")),
        )
        return all(required_frozen)

    @classmethod
    def _advisor_routed(cls, item: dict[str, Any]) -> bool:
        terminal = {"DONE", "VERIFIED", "REJECTED", "FAILED"}
        if item.get("status") in terminal:
            return False
        if item.get("owner_role") == "ADVISOR":
            return True
        if item.get("status") in {"SOURCE_BINDING_PENDING", "BINDING_INCOMPLETE"}:
            return True
        if item.get("owner_role"):
            return False
        return item.get("kind") in cls.LEGACY_ADVISOR_KINDS

    @staticmethod
    def _queue_card(item: dict[str, Any], role: str) -> dict[str, Any]:
        common = (
            "id", "entity_version", "status", "kind", "owner_role", "priority",
            "thread_id", "question", "next_action", "blocker", "blocker_class",
            "migration_state", "interdomain_ref",
        )
        executor = (
            "task_id", "capability_id", "implementation_ref", "repository", "source_revision",
            "required_outputs", "validation_ref", "result_ref", "frozen_test",
            "execution_class", "dispatch_requested", "dispatch_state",
        )
        learner = ("result_ref", "learning_state")
        keys = common + (executor if role == "EXECUTOR" else ()) + (learner if role == "LEARNER" else ())
        return {key: item[key] for key in keys if key in item and item[key] is not None}

    def queue_for(self, role: str) -> list[dict[str, Any]]:
        role = role.upper()
        if role not in self.ROLES:
            raise TowerAgentIssue("ROLE_NOT_SUPPORTED", "Unknown NEXO role.", {"role": role})
        items = self._work_items()
        if role == "EXECUTOR":
            capabilities = self.capabilities_for("EXECUTOR")
            return [self._queue_card(item, role) for item in items if self._executor_eligible(item, capabilities)]
        if role == "ADVISOR":
            return [self._queue_card(item, role) for item in items if self._advisor_routed(item)]
        if role == "LEARNER":
            return [self._queue_card(item, role) for item in items if item.get("status") in {"VERIFIED", "DONE"} and item.get("learning_state") != "LEARNED"]
        if role == "EMERGENT":
            return [self._queue_card(item, role) for item in items if item.get("owner_role") == "EMERGENT" or item.get("kind") == "EMERGENT_TEST"]
        return [self._queue_card(item, role) for item in items if item.get("director_relevant") is True]

    def capabilities_for(self, role: str) -> dict[str, Any]:
        try:
            payload = self._read_json("manifests/capabilities.json")
        except TowerAgentIssue as exc:
            if exc.code == "TOWER_FILE_NOT_FOUND":
                return {}
            raise
        result: dict[str, Any] = {}
        for capability_id, capability in payload.get("capabilities", {}).items():
            roles = capability.get("roles", []) if isinstance(capability, dict) else []
            if not roles or role.upper() in roles:
                result[capability_id] = capability
        return result

    def campaign_frontier(self, campaign_id: str) -> dict[str, Any]:
        from .campaign_continuation import CampaignFrontierResolver

        return CampaignFrontierResolver(self.root).resolve(campaign_id)

    def resolve_test_execution(self, test: dict[str, Any]) -> dict[str, Any]:
        from .capability_resolution import CapabilityExecutionResolver

        return CapabilityExecutionResolver(self.capabilities_for("EXECUTOR")).resolve(test)

    def _campaign_item(self, campaign_id: str, test_id: str, source: str | None = None) -> dict[str, Any]:
        kinds = [source] if source in {"test", "work"} else ["test", "work"]
        for kind in kinds:
            path = entity_path(self.root, kind, test_id)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue
            if isinstance(payload, dict) and str(payload.get("campaign_id")) == campaign_id:
                return payload
        raise TowerAgentIssue(
            "CAMPAIGN_TEST_NOT_FOUND",
            "Campaign frontier referenced a test that cannot be read.",
            {"campaign_id": campaign_id, "test_id": test_id},
        )

    def continue_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Return one recovery-first continuation decision for a campaign.

        ACTIVE is the normal operational mode. SHADOW remains available only
        when explicitly requested for diagnostics or staged rollout.
        """
        requested_mode = str(os.getenv("NEXO_CAMPAIGN_CONTINUATION_MODE", "ACTIVE")).upper()
        mode = requested_mode if requested_mode in {"OFF", "SHADOW", "ACTIVE"} else "ACTIVE"
        frontier = self.campaign_frontier(campaign_id)

        if mode == "OFF":
            return {"campaign_id": campaign_id, "mode": mode, "action": "DISABLED", "frontier": frontier}
        if frontier.get("terminal"):
            return {"campaign_id": campaign_id, "mode": mode, "action": "TERMINAL", "frontier": frontier}

        recoverable = list(frontier.get("recoverable") or [])
        if recoverable:
            proposed = {
                "campaign_id": campaign_id,
                "mode": mode,
                "action": "RECOVER",
                "test_id": recoverable[0],
                "frontier": frontier,
            }
        else:
            active = list(frontier.get("active") or [])
            if active:
                proposed = {
                    "campaign_id": campaign_id,
                    "mode": mode,
                    "action": "RESUME",
                    "test_id": active[0],
                    "frontier": frontier,
                }
            else:
                ready = list(frontier.get("ready") or [])
                if not ready:
                    return {"campaign_id": campaign_id, "mode": mode, "action": "NO_OP", "frontier": frontier}

                test_id = ready[0]
                source = (frontier.get("sources") or {}).get(test_id)
                test = self._campaign_item(campaign_id, test_id, source)
                execution = self.resolve_test_execution(test)
                execution_status = str(execution.get("status") or "")
                if execution_status == "RESOLVED":
                    action = "DISPATCH"
                elif execution_status == "REPAIR_REQUIRED":
                    action = "REPAIR_CAPABILITY"
                elif execution_status == "BLOCKED":
                    action = "BLOCKED"
                else:
                    action = "RESOLVE_CAPABILITY"
                proposed = {
                    "campaign_id": campaign_id,
                    "mode": mode,
                    "action": action,
                    "test_id": test_id,
                    "execution": execution,
                    "frontier": frontier,
                }

        if mode == "SHADOW":
            shadow = dict(proposed)
            shadow["proposed_action"] = str(proposed["action"])
            shadow["action"] = "SHADOW"
            return shadow

        return proposed

    def bootstrap(self, role: str) -> dict[str, Any]:
        role = role.upper()
        control = self._read_json("CONTROL.json")
        snapshot = self._read_json("snapshot/latest.json")
        queue = self.queue_for(role)
        return {
            "role": role,
            "control": control,
            "event_cursor": snapshot.get("event_cursor"),
            "queue": queue,
            "queue_count": len(queue),
            "capabilities": self.capabilities_for(role),
        }

    def resolve_artifact(self, artifact_id: str) -> dict[str, Any]:
        payload = self._read_json("manifests/artifacts.json")
        artifact = payload.get("artifacts", {}).get(artifact_id)
        if not isinstance(artifact, dict):
            raise TowerAgentIssue("ARTIFACT_NOT_FOUND", "Artifact ref is not registered.", {"artifact_id": artifact_id})
        return artifact

    def resolve_capability(self, capability_id: str) -> dict[str, Any]:
        payload = self._read_json("manifests/capabilities.json")
        capability = payload.get("capabilities", {}).get(capability_id)
        if not isinstance(capability, dict):
            raise TowerAgentIssue("CAPABILITY_NOT_FOUND", "Capability is not registered.", {"capability_id": capability_id})
        return capability

    def mutate(
        self,
        entity_kind: str,
        entity_name: str,
        *,
        expected_version: int,
        changes: dict[str, Any],
        writer_role: str,
        event_type: str,
        material: bool = True,
    ) -> dict[str, Any]:
        path = entity_path(self.root, entity_kind, entity_name)
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            if entity_kind == "work":
                current = self._hydrate_work(entity_name)
            else:
                raise TowerAgentIssue("ENTITY_NOT_FOUND", "Canonical entity does not exist.", {"entity_kind": entity_kind, "entity_name": entity_name}) from exc
        current_version = int(current.get("entity_version", 0))
        if current_version != expected_version:
            raise TowerAgentIssue(
                "WRITE_CONFLICT_RETRY_REQUIRED",
                "Entity version changed before mutation.",
                {"expected_version": expected_version, "current_version": current_version},
            )
        protected = {"id", "entity_id", "entity_version"}
        if protected.intersection(changes):
            raise TowerAgentIssue("PROTECTED_FIELD_MUTATION", "Mutation cannot replace identity/version fields.")
        updated = dict(current)
        updated.update(changes)
        updated["entity_version"] = current_version + 1
        updated["writer_role"] = writer_role.upper()
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(updated, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
        readback = json.loads(path.read_text(encoding="utf-8"))
        if int(readback.get("entity_version", 0)) != current_version + 1:
            raise TowerAgentIssue("READBACK_FAILED", "Mutation readback did not match expected version.")
        event_dir = self.root / "events" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
        event_dir.mkdir(parents=True, exist_ok=True)
        event_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{hashlib.sha256(str(path).encode()).hexdigest()[:8]}"
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "entity_kind": entity_kind,
            "entity_name": entity_name,
            "entity_version": current_version + 1,
            "writer_role": writer_role.upper(),
            "material": material,
        }
        json_file(event_dir, event_id).write_text(json.dumps(event, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return {"accepted": True, "entity_version": current_version + 1, "readback": "PASS", "event_id": event_id}
