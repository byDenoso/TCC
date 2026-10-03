"""Bounded operational work, executed ONLY inside the existing singleton Writer.

The hosted MCP submits immutable intents; it never patches Tower. The Writer
owns claims, frozen packages, dispatch outboxes and receipt admission. This
module deliberately does not import Antigravity or enable scientific dispatch.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Protocol

from .gpt_writer import apply_to_tower
from .inbox_apply import _operational_receipt_request
from .live_tower import read_live_tower_bytes, verify_live_tower

CONTRACT = "NEXO_OPERATIONAL_WORK_V1"
INTENT = "NEXO_OPERATIONAL_INTENT_V1"
PACKAGE = "NEXO_FROZEN_OPERATIONAL_PACKAGE_V1"
REPOSITORY = "byDenoso/Pantheon"
WORKFLOW = ".github/workflows/nexo-drive-operational.yml"
SCOPE = "ENGINEERING_OPERATIONAL_ONLY"
ACTIONS = frozenset({"claim_work", "prepare_package", "validate_package", "request_execution", "register_delivery"})
SHA = re.compile(r"^[0-9a-f]{64}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
TERMINAL = frozenset({"REGISTERED", "FAILED"})


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class OperationalError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False):
        self.code, self.retryable = code, retryable
        super().__init__(code)


def require(condition: Any, code: str) -> None:
    if not condition:
        raise OperationalError(code)


class Store(Protocol):
    def all(self) -> list[dict]: ...
    def get(self, work_id: str) -> dict: ...
    def save(self, work: dict, expected_version: int) -> dict: ...
    def receipt(self, body: dict) -> dict: ...


class TowerWriterStore:
    """Use the actual PR128 Writer and the existing DriveTower CAS/readback.

    No distributed-lock fiction: caller MUST be the singleton GitHub Writer job.
    The inherited Drive transport is head-check/PATCH/readback, not atomic CAS.
    GitHub concurrency `nexo-writer-robot` is the cross-process serialization.
    """
    def __init__(self, tower):
        self.tower = tower

    def _load(self):
        raw, head = self.tower.download(cache=False)
        data = read_live_tower_bytes(raw)
        fingerprint = verify_live_tower(data)
        require(data.get("revision") == data.get("state_fingerprint") == fingerprint, "OPERATIONAL_TOWER_HASH_MISMATCH")
        require(data.get("stable_file_id") == "1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z", "OPERATIONAL_TOWER_ID_MISMATCH")
        return raw, head, data

    @staticmethod
    def _entry(data, work_id):
        return data.get("files", {}).get(f"entities/artifact/{work_id}.json", {}).get("value")

    def all(self):
        _, _, data = self._load()
        result = []
        for key, entry in data.get("files", {}).items():
            value = entry.get("value", {})
            if key.startswith("entities/artifact/") and value.get("kind") == CONTRACT:
                state = copy.deepcopy(value["payload"])
                state["version"] = int(value.get("entity_version", 0))
                result.append(state)
        return sorted(result, key=lambda row: row["id"])

    def get(self, work_id):
        require(SAFE_ID.fullmatch(work_id), "WORK_ID_INVALID")
        _, _, data = self._load()
        value = self._entry(data, work_id)
        require(value and value.get("kind") == CONTRACT, "WORK_NOT_FOUND")
        state = copy.deepcopy(value["payload"])
        state["version"] = int(value.get("entity_version", 0))
        return state

    def save(self, work, expected_version):
        raw, head, data = self._load()
        prior = self._entry(data, work["id"])
        require(int((prior or {}).get("entity_version", 0)) == expected_version, "VERSION_CONFLICT")
        state = {k: v for k, v in work.items() if k != "version"}
        request = {
            "request_id": "REQ-OP-" + digest({"work": state, "base": expected_version})[:32],
            "entity_kind": "artifact", "entity_name": work["id"],
            "expected_version": expected_version, "writer_role": "LEARNER",
            "event_type": "OPERATIONAL_WORK_RECORDED", "material": True,
            "changes": {"kind": CONTRACT, "status": "RECORDED", "source": "WRITER_ROBOT", "payload": state},
        }
        packed, report = apply_to_tower(raw, [request], operational_work_authorized=True)
        require(not report.get("rejected") and not report.get("deferred"), "WRITER_STATE_REJECTED")
        require(packed is not None, "WRITER_STATE_NOT_APPLIED")
        receipt = self.tower.compare_and_swap(head, packed)
        require(receipt.get("readback") == "PASS", "TOWER_READBACK_FAILED")
        check = self.get(work["id"])
        require({k: v for k, v in check.items() if k != "version"} == state, "TOWER_BODY_READBACK_MISMATCH")
        return check

    def install_config(self, config):
        """Install the reviewed rollout once; Drive then owns this configuration."""
        raw, head, data = self._load()
        identity = "OPERATIONAL-CONTROL-RUNTIME-V1"
        prior = self._entry(data, identity)
        if prior:
            require(prior.get("kind") == "NEXO_OPERATIONAL_RUNTIME_V1", "CONFIG_IDENTITY_CONFLICT")
            return copy.deepcopy(prior["payload"])
        request = {"request_id": "REQ-OP-CONFIG-" + digest(config)[:32],
                   "entity_kind": "artifact", "entity_name": identity, "expected_version": 0,
                   "writer_role": "LEARNER", "event_type": "OPERATIONAL_RUNTIME_INSTALLED", "material": True,
                   "changes": {"kind": "NEXO_OPERATIONAL_RUNTIME_V1", "status": "RECORDED",
                               "source": "WRITER_ROBOT", "payload": config}}
        packed, report = apply_to_tower(raw, [request], operational_work_authorized=True)
        require(packed is not None and not report.get("rejected") and not report.get("deferred"), "CONFIG_INSTALL_REJECTED")
        require(self.tower.compare_and_swap(head, packed).get("readback") == "PASS", "CONFIG_READBACK_FAILED")
        _, _, data = self._load()
        require(self._entry(data, identity).get("payload") == config, "CONFIG_BODY_MISMATCH")
        return copy.deepcopy(config)

    def receipt(self, body):
        receipt_id = body["receipt_id"]
        envelope = {
            "kind": "OPERATIONAL_RECEIPT", "source": "WRITER_ROBOT",
            "created_at": body["executed_at"], "payload": body,
            "_inbox_source": "RUNNER_OBSERVATION",
            "_inbox_name": "operational-receipt-" + receipt_id,
            "_inbox_id": "runner:" + receipt_id,
        }
        [request] = _operational_receipt_request(envelope, body)
        raw, head, _ = self._load()
        packed, report = apply_to_tower(raw, [envelope])
        require(not report.get("rejected") and not report.get("deferred"), "WRITER_RECEIPT_REJECTED")
        if packed is not None:
            check = self.tower.compare_and_swap(head, packed)
            require(check.get("readback") == "PASS", "TOWER_RECEIPT_READBACK_FAILED")
        _, _, data = self._load()
        path = f"entities/artifact/{request['entity_name']}.json"
        recorded = data.get("files", {}).get(path, {}).get("value", {}).get("payload")
        require(recorded == body, "CANONICAL_RECEIPT_BODY_MISMATCH")
        return {"file_id": data["stable_file_id"], "revision": data["revision"],
                "path": path, "receipt_id": receipt_id, "body_sha256": digest(body), "readback": "PASS"}


def validate_definition(definition: dict) -> None:
    require(definition.get("scope") == SCOPE, "SCIENCE_NOT_ADMITTED_BY_OPERATIONAL_RUNTIME")
    require(definition.get("scientific_result_eligible") is False, "SCIENCE_ELIGIBILITY_FORBIDDEN")
    require(definition.get("recipe", {}).get("id") == "drive-sum-mean-v1", "RECIPE_NOT_ALLOWLISTED")
    require(SAFE_ID.fullmatch(str(definition.get("id", ""))) and definition["id"].startswith("OPERATIONAL-CONTROL-"), "WORK_ID_INVALID")
    require(definition.get("role") in {"EXECUTOR", "ENGENHEIRO"}, "ROLE_NOT_ALLOWED")
    code = definition.get("code", {})
    require(code.get("repository") == REPOSITORY and SHA1.fullmatch(str(code.get("sha", ""))), "CODE_NOT_PINNED")
    files = code.get("files", {})
    require(set(files) == {WORKFLOW, "scripts/nexo_operational_package.py"}
            and all(SHA.fullmatch(str(value)) for value in files.values()), "CODE_FILE_BINDINGS_REQUIRED")
    require(SHA.fullmatch(str(definition["recipe"].get("sha256", ""))), "RECIPE_HASH_MISSING")
    require(definition["recipe"]["sha256"] == "17f0855b95de6d77ad9bc26ff92a05a38692b14455a022dfc34a810ef6ad96be", "OPERATIONAL_RECIPE_HASH_NOT_ALLOWLISTED")
    recipe_ref = definition["recipe"].get("drive") or {}
    require(recipe_ref.get("file_id") and recipe_ref.get("version")
            and recipe_ref.get("sha256") == definition["recipe"]["sha256"], "RECIPE_REFERENCE_NOT_FROZEN")
    source = definition.get("input", {})
    require(source.get("file_id") == "1Cr7L6bbVlOqB0HUvYett0xkhRS-NWRWr", "INPUT_NOT_ALLOWLISTED")
    require(source.get("source_storage") == "GOOGLE_DRIVE_PRIVATE", "INPUT_STORAGE_INVALID")
    require(source.get("file_id") and source.get("version") and SHA.fullmatch(str(source.get("sha256", ""))), "INPUT_NOT_FROZEN")
    require(definition.get("known_result") == {"count": 3, "sum": 6, "mean": 2}, "KNOWN_RESULT_MUST_NOT_CHANGE")
    for destination in ("packages", "results"):
        folder = definition.get("destinations", {}).get(destination)
        require(isinstance(folder, str) and folder not in {"root", ""}, "EXISTING_DESTINATION_REQUIRED")
    # Only the allowlisted arithmetic control: no per-execution approval record.
    # Scientific code is outside this runtime and retains independent review.


def initialize_work(definition: dict, *, now: str | None = None) -> dict:
    require(SAFE_ID.fullmatch(str(definition.get("id", ""))) and definition["id"].startswith("OPERATIONAL-CONTROL-"), "WORK_ID_INVALID")
    state, error = "READY", None
    try:
        validate_definition(definition)
    except OperationalError as exc:
        state, error = "BLOCKED", {"code": exc.code, "retryable": False}
    return {"contract": CONTRACT, "id": definition["id"], "role": definition["role"],
            "scope": SCOPE, "state": state, "error": error, "definition": copy.deepcopy(definition),
            "definition_sha256": digest(definition), "version": 0, "owner": None,
            "outbox": None, "result": None, "receipt": None,
            "processed": {}, "updated_at": now or utcnow()}


def role_context(work: dict, prompt: str) -> dict:
    context = {"work_id": work["id"], "role": work["role"], "scope": work["scope"],
               "definition_sha256": work["definition_sha256"],
               "actions": sorted(ACTIONS), "writer_only": True, "antigravity_required": False}
    return {"contract": "NEXO_ROLE_SESSION_V1", "session_id": "drive-operational-control-v1",
            "role": work["role"], "work_id": work["id"],
            "mcp_endpoint": "https://nexo-one-two.vercel.app/api/mcp", "mcp_tool": "get_role_session",
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "context_sha256": digest(context)}


def freeze_package(work: dict, input_bytes: bytes, recipe_bytes: bytes) -> dict:
    definition = work["definition"]
    validate_definition(definition)
    require(digest(definition) == work["definition_sha256"], "DEFINITION_CHANGED")
    require(digest(input_bytes) == definition["input"]["sha256"], "INPUT_HASH_MISMATCH")
    require(digest(recipe_bytes) == definition["recipe"]["sha256"], "RECIPE_HASH_MISMATCH")
    require(work.get("role_session"), "ROLE_SESSION_REQUIRED")
    return {"contract": PACKAGE, "scope": SCOPE, "scientific_result_eligible": False,
            "work_id": work["id"], "definition_sha256": work["definition_sha256"],
            "input": copy.deepcopy(definition["input"]), "recipe": copy.deepcopy(definition["recipe"]),
            "code": copy.deepcopy(definition["code"]), "role_session": copy.deepcopy(work["role_session"]),
            "known_result": copy.deepcopy(definition["known_result"]),
            "review": copy.deepcopy(definition.get("review", {})),
            "input_bytes_b64": base64.b64encode(input_bytes).decode("ascii"),
            "recipe_bytes_b64": base64.b64encode(recipe_bytes).decode("ascii")}


def run_frozen(package: dict, expected_package_hash: str, input_bytes: bytes, recipe_bytes: bytes) -> dict:
    """Secret-free execution contract. The recipe is verified, not eval/exec'd."""
    require(digest(package) == expected_package_hash, "PACKAGE_HASH_MISMATCH")
    require(package.get("contract") == PACKAGE and package.get("scope") == SCOPE, "PACKAGE_CONTRACT_INVALID")
    require(package.get("scientific_result_eligible") is False, "SCIENCE_ELIGIBILITY_FORBIDDEN")
    require(package.get("recipe", {}).get("id") == "drive-sum-mean-v1", "RECIPE_NOT_ALLOWLISTED")
    require(digest(input_bytes) == package["input"]["sha256"], "INPUT_HASH_MISMATCH")
    require(digest(recipe_bytes) == package["recipe"]["sha256"], "RECIPE_HASH_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="nexo-isolated-") as temp:
        root = Path(temp)
        (root / "recipe.py").write_bytes(recipe_bytes)
        (root / "input.json").write_bytes(input_bytes)
        child = subprocess.run(
            [sys.executable, "-I", "-S", str(root / "recipe.py"), str(root / "input.json"), str(root / "output.json")],
            cwd=root, env={"LANG": "C.UTF-8"}, timeout=10, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        require(child.returncode == 0, "RECIPE_EXECUTION_FAILED")
        raw_result = (root / "output.json").read_bytes()
        require(len(raw_result) <= 65536, "RESULT_TOO_LARGE")
        result = json.loads(raw_result)
    require(set(result) == {"count", "sum", "mean"}, "RESULT_FIELDS_INVALID")
    require(type(result["count"]) is int and result["count"] > 0, "RESULT_COUNT_INVALID")
    require(all(type(result[k]) in (int, float) and math.isfinite(result[k]) for k in ("sum", "mean")), "RESULT_NONFINITE")
    result["known_result_matched"] = all(result[key] == expected for key, expected in package["known_result"].items())
    return {"contract": "NEXO_OPERATIONAL_RESULT_V1", "scope": SCOPE,
            "work_id": package["work_id"], "package_sha256": expected_package_hash,
            "definition_sha256": package["definition_sha256"],
            "input_sha256": package["input"]["sha256"], "recipe_sha256": package["recipe"]["sha256"],
            "result": result, "result_sha256": digest(result), "executed_at": utcnow()}


def verify_run(run: dict, work: dict) -> None:
    require(run.get("repository", {}).get("full_name") == REPOSITORY, "RUN_REPOSITORY_MISMATCH")
    require(run.get("head_repository", {}).get("full_name") == REPOSITORY, "RUN_HEAD_REPOSITORY_MISMATCH")
    require(run.get("head_branch") == "main", "RUN_NOT_MAIN")
    require(run.get("head_sha") == work["outbox"].get("execution_sha", work["definition"]["code"]["sha"]), "RUN_COMMIT_MISMATCH")
    require(run.get("path") == WORKFLOW, "RUN_WORKFLOW_MISMATCH")
    require(run.get("event") == "workflow_dispatch", "RUN_EVENT_MISMATCH")
    require(run.get("status") == "completed" and run.get("conclusion") == "success", "RUN_NOT_SUCCESSFUL")
    require(type(run.get("id")) is int and run["id"] > 0, "RUN_ID_INVALID")
    require(type(run.get("run_attempt")) is int and run["run_attempt"] > 0, "RUN_ATTEMPT_INVALID")
    require(run.get("display_title") == "nexo-op-" + work["outbox"]["key"], "RUN_CORRELATION_MISMATCH")


def collect_receipt(run: dict, output: dict, work: dict) -> dict:
    verify_run(run, work)
    require(output.get("contract") == "NEXO_OPERATIONAL_RESULT_V1", "RESULT_CONTRACT_INVALID")
    require(output.get("scope") == SCOPE and output.get("work_id") == work["id"], "RESULT_SCOPE_MISMATCH")
    require(output.get("package_sha256") == work["package"]["sha256"], "RESULT_PACKAGE_MISMATCH")
    require(output.get("definition_sha256") == work["definition_sha256"], "RESULT_DEFINITION_MISMATCH")
    require(output.get("input_sha256") == work["definition"]["input"]["sha256"], "RESULT_INPUT_MISMATCH")
    require(output.get("recipe_sha256") == work["definition"]["recipe"]["sha256"], "RESULT_RECIPE_MISMATCH")
    require(digest(output["result"]) == output.get("result_sha256"), "RESULT_HASH_MISMATCH")
    passed = output["result"].get("known_result_matched") is True
    return {"contract": "NEXO_OPERATIONAL_RECEIPT_V1", "receipt_id": f"drive-actions-{run['id']}-{run['run_attempt']}",
            "pipeline": "DRIVE_GITHUB_ACTIONS_WRITER_TOWER_V1", "status": "PASS" if passed else "DIVERGED",
            "scope": SCOPE, "scientific_result_eligible": False, "repository": REPOSITORY,
            "commit_sha": run["head_sha"], "run_ref": f"actions/runs/{run['id']}", "run_attempt": run["run_attempt"],
            "role_session": copy.deepcopy(work["role_session"]),
            "input": {**work["definition"]["input"], "scope": "DRIVE_BYTES_REVERIFIED_IN_SECRET_FREE_JOB"},
            "result": output["result"], "decision": "OPERATIONAL_CONTROL_PASS" if passed else "OPERATIONAL_CONTROL_DIVERGED",
            "result_sha256": output["result_sha256"], "executed_at": output["executed_at"]}


class OperationalWorker:
    """One short Writer tick. Every external side effect has a durable checkpoint."""
    def __init__(self, store: Store, drive, actions, *, recipe_loader, input_loader=None, now=utcnow):
        self.store, self.drive, self.actions = store, drive, actions
        self.recipe_loader, self.now = recipe_loader, now
        self.input_loader = input_loader or drive.read_frozen

    def _save(self, work):
        work["updated_at"] = self.now()
        return self.store.save(work, work["version"])

    def _prepare(self, work):
        definition = work["definition"]
        validate_definition(definition)
        raw = self.input_loader(definition["input"])
        package = freeze_package(work, raw, self.recipe_loader(definition["recipe"]))
        file = self.drive.put_immutable(definition["destinations"]["packages"], digest(package) + ".json", canonical(package))
        work.update(state="PREPARED", package={**file, "sha256": digest(package)}, error=None)

    def _validate(self, work):
        package = json.loads(self.drive.read_frozen(work["package"]))
        require(digest(package) == work["package"]["sha256"], "PACKAGE_HASH_MISMATCH")
        require(package == freeze_package(work, self.input_loader(work["definition"]["input"]), self.recipe_loader(work["definition"]["recipe"])), "PACKAGE_DEFINITION_MISMATCH")
        work.update(state="VALIDATED", error=None)

    def handle(self, intent: dict) -> dict:
        require(set(intent) == {"contract", "id", "action", "work_id", "principal", "role_session", "expected_version"}, "INTENT_FIELDS_INVALID")
        require(intent["contract"] == INTENT and intent["action"] in ACTIONS, "INTENT_ACTION_INVALID")
        require(SHA.fullmatch(str(intent["principal"])), "AUTHENTICATED_PRINCIPAL_REQUIRED")
        identity = {key: value for key, value in intent.items() if key != "id"}
        require(intent["id"] == "op-" + digest(identity)[:48], "INTENT_HASH_MISMATCH")
        work = self.store.get(intent["work_id"])
        prior = work["processed"].get(intent["id"])
        if prior:
            return {**prior, "idempotent": True}
        if work["version"] != intent["expected_version"]:
            return {"state": "VERSION_CONFLICT", "work_id": work["id"], "retryable": True}
        action = intent["action"]
        from .operational_prompts import PROMPTS
        require(intent["role_session"] == role_context(work, PROMPTS[work["role"]]), "ROLE_CONTEXT_OR_PROMPT_CHANGED")
        require(intent["role_session"]["work_id"] == work["id"] and intent["role_session"]["role"] == work["role"], "ROLE_SESSION_MISMATCH")
        if action == "request_execution":
            require(work.get("owner") in (None, intent["principal"]), "CLAIM_OWNERSHIP_REQUIRED")
        elif action != "claim_work":
            require(work.get("owner") == intent["principal"], "CLAIM_OWNERSHIP_REQUIRED")
            require(intent["role_session"] == work.get("role_session"), "SESSION_CHANGED")
        try:
            if action == "claim_work":
                require(work["state"] == "READY" or (work["state"] == "CLAIMED" and work["owner"] == intent["principal"]), "WORK_ALREADY_CLAIMED")
                work.update(state="CLAIMED", owner=intent["principal"], role_session=intent["role_session"])
            elif action == "prepare_package":
                require(work["state"] in {"CLAIMED", "BLOCKED"}, "WORK_NOT_PREPARABLE")
                self._prepare(work)
            elif action == "validate_package":
                require(work["state"] in {"PREPARED", "VALIDATED"}, "WORK_NOT_PREPARED")
                self._validate(work)
            elif action == "request_execution":
                require(work["state"] in {"READY", "CLAIMED", "PREPARED", "VALIDATED", "DISPATCH_PENDING", "DISPATCH_UNKNOWN", "RUNNING", "RESULT_AVAILABLE", "DELIVERY_PENDING", "REGISTERED"}, "WORK_NOT_EXECUTABLE")
                if work["state"] == "READY":
                    work.update(state="CLAIMED", owner=intent["principal"], role_session=intent["role_session"])
                if work["state"] == "CLAIMED":
                    self._prepare(work)
                if work["state"] == "PREPARED":
                    self._validate(work)
                work["auto_delivery"] = True
                if not work.get("outbox"):
                    execution_sha = self.actions.preflight(work)
                    key = digest({"id": work["id"], "package": work["package"]["sha256"]})[:40]
                    work.update(state="DISPATCH_PENDING", outbox={"key": key, "attempted": False, "run_id": None, "execution_sha": execution_sha})
            elif action == "register_delivery":
                require(work["state"] in {"RESULT_AVAILABLE", "DELIVERY_PENDING", "REGISTERED"}, "RESULT_NOT_AVAILABLE")
                if work["state"] != "REGISTERED":
                    work["state"] = "DELIVERY_PENDING"
            result = {"work_id": work["id"], "state": work["state"], "idempotent": False}
            work["processed"][intent["id"]] = result
            work = self._save(work)
            return result
        except OperationalError as exc:
            if action == "claim_work":
                return {"work_id": work["id"], "state": exc.code, "retryable": False}
            if exc.retryable:
                return {"work_id": work["id"], "state": work["state"],
                        "error": {"code": exc.code, "retryable": True}}
            work["error"] = {"code": exc.code, "retryable": exc.retryable}
            if not exc.retryable:
                work["resume_state"] = work["state"]
                work["state"] = "BLOCKED"
            self._save(work)
            return {"work_id": work["id"], "state": work["state"], "error": work["error"]}

    def progress(self, work_id: str) -> dict:
        work = self.store.get(work_id)
        if work["state"] in {"DISPATCH_PENDING", "DISPATCH_UNKNOWN", "RUNNING"}:
            matches = self.actions.find_runs(work)
            require(len(matches) <= 1, "DUPLICATE_RUN_REQUIRES_RECONCILIATION")
            if matches:
                run = matches[0]
                work["outbox"]["run_id"] = run["id"]
                if run["status"] != "completed":
                    work["state"] = "RUNNING"
                elif run.get("conclusion") != "success":
                    work.update(state="FAILED", error={"code": "ACTIONS_FAILED", "run_id": run["id"]})
                else:
                    output = self.actions.result(run, work)
                    receipt = collect_receipt(run, output, work)
                    location = self.drive.put_immutable(work["definition"]["destinations"]["results"], f"{receipt['receipt_id']}.json", canonical(output))
                    work.update(state="DELIVERY_PENDING" if work.get("auto_delivery") else "RESULT_AVAILABLE", result={"body": output, "receipt_body": receipt, "location": location})
                return self._save(work)
            if not work["outbox"]["attempted"]:
                # Durable at-most-one POST; an ambiguous response is reconciled.
                # Main metadata can move only when reviewed source hashes match.
                work["outbox"]["execution_sha"] = self.actions.preflight(work)
                work["outbox"]["attempted"] = True
                work["state"] = "DISPATCH_UNKNOWN"
                work = self._save(work)
                try:
                    self.actions.dispatch(work)
                    work["state"] = "DISPATCH_PENDING"
                    return self._save(work)
                except Exception as exc:
                    if getattr(exc, "dispatch_not_sent", False):
                        work["outbox"]["attempted"] = False
                        work["state"] = "DISPATCH_PENDING"
                        return self._save(work)
                    return work
        if work["state"] == "DELIVERY_PENDING":
            run = self.actions.get_run(work["outbox"]["run_id"])
            output = self.actions.result(run, work)
            receipt = collect_receipt(run, output, work)
            require(receipt == work["result"]["receipt_body"], "DELIVERY_RESULT_CHANGED")
            proof = self.store.receipt(receipt)
            work.update(state="REGISTERED", receipt=proof, error=None)
            return self._save(work)
        return work

    def tick(self, intents: list[dict]) -> dict:
        report = {"intents": [], "progress": [], "errors": []}
        for item in intents:
            try:
                report["intents"].append(self.handle(item))
            except Exception as exc:
                report["errors"].append({"work_id": item.get("work_id"), "code": getattr(exc, "code", type(exc).__name__)})
        for item in self.store.all():
            try:
                if item["state"] not in TERMINAL:
                    current = self.progress(item["id"])
                    if current["state"] == "DELIVERY_PENDING":
                        current = self.progress(item["id"])
                    report["progress"].append({"work_id": item["id"], "state": current["state"]})
            except Exception as exc:
                code = getattr(exc, "code", type(exc).__name__)
                report["errors"].append({"work_id": item["id"], "code": code})
                if isinstance(exc, OperationalError) and not exc.retryable:
                    current = self.store.get(item["id"])
                    current.update(resume_state=current["state"], state="BLOCKED",
                                   error={"code": code, "retryable": False})
                    self._save(current)
        return report
