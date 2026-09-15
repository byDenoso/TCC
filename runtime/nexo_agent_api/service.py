from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
                path = self.root / "entities" / "work" / f"{entity_name}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                hydrated = dict(item)
                hydrated.setdefault("entity_version", 1)
                path.write_text(json.dumps(hydrated, ensure_ascii=False, sort_keys=True), encoding="utf-8")
                return hydrated
        raise TowerAgentIssue("ENTITY_NOT_FOUND", "Canonical entity does not exist.", {"entity_kind": "work", "entity_name": entity_name})

    @staticmethod
    def _executor_eligible(item: dict[str, Any], capabilities: dict[str, Any]) -> bool:
        if item.get("owner_role") != "EXECUTOR" or item.get("status") not in {"READY", "RUNNING", "CHECKPOINTED"}:
            return False

        task_id = item.get("task_id")
        if task_id:
            capability = capabilities.get(str(task_id))
            capability_status = capability.get("status", "ACTIVE") if isinstance(capability, dict) else None
            capability_ready = isinstance(capability, dict) and capability_status in {"ACTIVE", "PROVEN"}
            required = (
                item.get("dependencies_resolved") is True,
                item.get("binding_verified") is True,
                capability_ready,
                bool(item.get("repository")),
                bool(item.get("source_revision")),
                bool(item.get("required_outputs")),
                bool(item.get("validation_ref")),
                item.get("runtime_available") is True,
                item.get("resource_lock_available") is True,
            )
            return all(required)

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
            "thread_id", "question", "next_action", "blocker", "migration_state", "interdomain_ref",
        )
        executor = (
            "task_id", "implementation_ref", "repository", "source_revision",
            "required_outputs", "validation_ref", "result_ref", "frozen_test",
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
        path = self.root / "entities" / entity_kind / f"{entity_name}.json"
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
        (event_dir / f"{event_id}.json").write_text(json.dumps(event, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return {"accepted": True, "entity_version": current_version + 1, "readback": "PASS", "event_id": event_id}
