"""Durable local boundary around the existing, unchanged execution runner.

This is not a scheduler, distributed lease, new scientific evaluator or approval
service. Call only for a reviewed, authorized contract in an isolated checkout.
The journal must survive the process and be shared by callers of this executor.
A process crash without complete outputs requires explicit method-specific
recovery; this module never restarts uncertain science from a timer alone.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Callable

from runtime.nexo_execution.campaign_store import CampaignError, atomic_json, digest, local_lock, require
from runtime.nexo_execution.core import ExecutionContract, _assert_dispatchable, sha256_file


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                       stderr=subprocess.DEVNULL, timeout=15).strip()
    except (subprocess.SubprocessError, OSError):
        raise CampaignError("EXECUTION_CHECKOUT_UNVERIFIED") from None


def _output(root: Path, name: str) -> Path:
    path = Path(name)
    require(isinstance(name, str) and path.parts and not path.is_absolute()
            and not any(part in {".", "..", ".git"} for part in path.parts)
            and not any(char in name for char in "\\\x00"), "OUTPUT_PATH_INVALID")
    target = root / path
    require(target.resolve().is_relative_to(root) and not any(p.is_symlink() for p in [target, *target.parents]),
            "OUTPUT_PATH_INVALID")
    return target


def _verified_result(root: Path, run: Path, contract: ExecutionContract) -> dict:
    try:
        result = json.loads((run / "result.json").read_text())
        verification = json.loads((run / "verification.json").read_text())
    except (ValueError, OSError):
        raise CampaignError("EXECUTION_EVIDENCE_INCOMPLETE") from None
    require(result.get("execution_id") == contract.execution_id and result.get("work_id") == contract.work_id
            and result.get("commit_sha") == contract.commit_sha and result.get("contract_hash") == contract.contract_hash
            and result.get("exit_code") == 0, "EXECUTION_RESULT_MISMATCH")
    require(verification.get("status") == "PASS" and verification.get("contract_hash") == contract.contract_hash
            and verification.get("execution_id") == contract.execution_id and verification.get("errors") == [],
            "EXECUTION_VERIFICATION_FAILED")
    rows = result.get("outputs")
    require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), "EXECUTION_OUTPUTS_INVALID")
    require(len({r.get("path") for r in rows}) == len(rows), "EXECUTION_OUTPUTS_INVALID")
    require(set(contract.required_outputs) == {r.get("path") for r in rows}, "EXECUTION_OUTPUTS_MISSING")
    for row in rows:
        path = _output(root, row["path"])
        require(path.is_file() and path.stat().st_size == row.get("bytes")
                and sha256_file(path) == row.get("sha256"), "EXECUTION_OUTPUT_INTEGRITY")
    return {"execution_id": contract.execution_id, "test_id": contract.test_id, "run_id": contract.run_id,
            "contract_hash": contract.contract_hash, "commit_sha": contract.commit_sha, "outputs": rows,
            "review_state": "NOT_REVIEWED", "publication_state": "INTERNAL",
            "result_file_sha256": sha256_file(run / "result.json"),
            "verification_file_sha256": sha256_file(run / "verification.json")}


def _stop_group(process: subprocess.Popen) -> None:
    # The runner and its solver share this process group. Kill any descendants,
    # even after the runner exits; no detached solver is intentionally supported.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def run_contract_once(contract_path: str | Path, *, repository_root: str | Path,
                      journal_directory: str | Path, expected_contract_hash: str,
                      authorized: bool = False, max_seconds: float | None = None,
                      publish: Callable[[dict], dict] | None = None) -> dict:
    """Execute the existing runner at most once per recoverable local intent.

    publish is a caller-owned, authorized persistence function. A publishing
    failure leaves verified local outputs intact and retries only persistence.
    It is not scientific review. Successful evidence remains NOT_REVIEWED.
    No credentials are forwarded to the solver's environment. This is not an
    OS filesystem/network sandbox; the checkout and evaluator must be trusted.
    """
    require(authorized is True, "EXECUTION_AUTHORIZATION_REQUIRED")
    require(os.name == "posix", "EXECUTION_PROCESS_GROUP_UNAVAILABLE")
    contract = ExecutionContract.load(contract_path)
    _assert_dispatchable(contract)  # Reuse the existing scientific runner gate.
    require(re.fullmatch(r"[a-f0-9]{64}", expected_contract_hash or "")
            and contract.contract_hash == expected_contract_hash, "EXECUTION_CONTRACT_MISMATCH")
    require(isinstance(contract.timeout_minutes, int) and not isinstance(contract.timeout_minutes, bool)
            and contract.timeout_minutes > 0, "EXECUTION_TIMEOUT_INVALID")
    seconds = contract.timeout_minutes * 60 if max_seconds is None else max_seconds
    require(isinstance(seconds, (int, float)) and not isinstance(seconds, bool)
            and 0 < seconds <= contract.timeout_minutes * 60, "EXECUTION_TIMEOUT_INVALID")
    root, journals = Path(repository_root).resolve(), Path(journal_directory).resolve()
    require(root.is_dir() and not Path(journal_directory).is_symlink(), "EXECUTION_DIRECTORY_INVALID")
    key = digest((contract.repository + "\n" + contract.test_id + "\n" + str(contract.run_id)).encode())
    run = journals / key
    binding = {"repository_root": str(root), "contract_hash": contract.contract_hash,
               "execution_id": contract.execution_id, "test_id": contract.test_id, "run_id": contract.run_id}
    with local_lock(journals / "executor.lock"):
        require(not run.is_symlink(), "EXECUTION_DIRECTORY_INVALID")
        run.mkdir(parents=True, exist_ok=True, mode=0o700)
        journal = run / "execution.json"
        require(not journal.is_symlink(), "EXECUTION_DIRECTORY_INVALID")
        require(_git(root, "rev-parse", "HEAD") == contract.commit_sha, "EXECUTION_COMMIT_MISMATCH")
        require(not _git(root, "diff", "HEAD", "--"), "EXECUTION_TRACKED_CHANGES")
        prior = json.loads(journal.read_text()) if journal.exists() else None
        if prior:
            require(prior.get("binding") == binding, "EXECUTION_INTENT_CONFLICT")
            # Independently check actual outputs on every retry, including a
            # crash after the runner completed but before the final journal.
            try:
                evidence = _verified_result(root, run, contract)
            except CampaignError:
                raise CampaignError("EXECUTION_REQUIRES_EXPLICIT_RECOVERY") from None
            replayed = True
        else:
            require(contract.required_outputs and len(set(contract.required_outputs)) == len(contract.required_outputs),
                    "EXECUTION_OUTPUTS_INVALID")
            for name in contract.required_outputs:
                path = _output(root, name)
                require(not path.exists(), "EXECUTION_OUTPUT_ALREADY_EXISTS")
                path.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(run / "contract.json", json.loads(contract.canonical_json()))
            atomic_json(journal, {"binding": binding, "state": "PREPARED"})
            home = run / "home"
            home.mkdir(mode=0o700, exist_ok=True)
            env = {"PATH": os.defpath, "HOME": str(home), "TMPDIR": str(home), "LANG": "C.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "OMP_NUM_THREADS": "1"}
            argv = [sys.executable, "-m", "runtime.nexo_execution.runner", str(run / "contract.json"),
                    "--result", str(run / "result.json"), "--verification", str(run / "verification.json"),
                    "--expected-contract-hash", contract.contract_hash]
            process = None
            old_handler = None
            def interrupted(_signum, _frame):
                raise InterruptedError("EXECUTION_INTERRUPTED")
            try:
                import threading
                if threading.current_thread() is threading.main_thread():
                    old_handler = signal.signal(signal.SIGTERM, interrupted)
                atomic_json(journal, {"binding": binding, "state": "RUNNING"})
                log_fd = os.open(run / "runner.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(log_fd, "wb") as log:
                    process = subprocess.Popen(argv, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                                               start_new_session=True)
                    process.wait(timeout=seconds)
                _stop_group(process)
                require(process.returncode == 0, "EXECUTION_RUNNER_FAILED")
                require(_git(root, "rev-parse", "HEAD") == contract.commit_sha
                        and not _git(root, "diff", "HEAD", "--"), "EXECUTION_SOURCE_CHANGED")
                evidence = _verified_result(root, run, contract)
            except BaseException as exc:
                # Interrupted/uncertain work must never silently start again.
                code = "EXECUTION_TIMEOUT" if isinstance(exc, subprocess.TimeoutExpired) else "EXECUTION_INTERRUPTED" if isinstance(exc, (InterruptedError, KeyboardInterrupt)) else "EXECUTION_FAILED"
                atomic_json(journal, {"binding": binding, "state": code})
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                if isinstance(exc, CampaignError):
                    raise
                raise CampaignError(code) from None
            finally:
                try:
                    if process is not None:
                        _stop_group(process)
                finally:
                    if old_handler is not None:
                        signal.signal(signal.SIGTERM, old_handler)
            replayed = False
        state = {"binding": binding, "state": "EXECUTED_LOCAL_VERIFIED", "evidence": evidence}
        atomic_json(journal, state)
        if publish is not None:
            try:
                receipt = publish({**evidence, "run_directory": str(run), "repository_root": str(root)})
                require(isinstance(receipt, dict) and receipt.get("state") == "PERSISTED_VERIFIED", "EXECUTION_PERSISTENCE_UNVERIFIED")
            except Exception:
                atomic_json(journal, {**state, "state": "PERSISTENCE_PENDING"})
                raise CampaignError("EXECUTION_PERSISTENCE_PENDING") from None
            state = {**state, "state": "EXECUTED_PERSISTED", "receipt": receipt}
            atomic_json(journal, state)
        return {**state, "replayed_without_compute": replayed, "run_directory": str(run)}


def publish_verified_run(evidence: dict, *, store, folder_id: str, campaign_id: str, actor_id: str,
                         journal_directory: str | Path, event_version: int = 1,
                         atlas_scope: str = "EXCLUDED") -> dict:
    """Persist verified execution files, then its RUN record, through the direct client.

    This does not create a scientific RESULT, interpret a statistic or approve a
    claim. All outputs are preflighted for the small-file client before upload.
    Larger outputs remain pending for an existing resumable-upload capability.
    The same publishing journal must be reused after a lost network response.
    """
    from datetime import datetime, timezone
    from runtime.nexo_execution.campaign_store import MAX_BYTES, make_event

    root = Path(evidence["repository_root"]).resolve()
    run = Path(evidence["run_directory"]).resolve()
    contract = ExecutionContract.load(run / "contract.json")
    actual = _verified_result(root, run, contract)
    require(actual == {k: evidence[k] for k in actual}, "EXECUTION_EVIDENCE_MISMATCH")
    journals = Path(journal_directory)
    key = digest((campaign_id + "\n" + str(contract.run_id) + "\n" + str(event_version)).encode())
    binding = {"campaign_id": campaign_id, "folder_id": folder_id, "actor_id": actor_id,
               "run_id": contract.run_id, "contract_hash": contract.contract_hash,
               "atlas_scope": atlas_scope, "event_version": event_version}
    with local_lock(journals / ("publish-" + key + ".lock")):
        state_file = journals / ("publish-" + key + ".json")
        if state_file.exists():
            publication = json.loads(state_file.read_text())
            require(publication.get("binding") == binding, "RUN_PUBLICATION_CONFLICT")
        else:
            publication = {"binding": binding, "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
            atomic_json(state_file, publication)
        paths = [(str(name), _output(root, name)) for name in contract.required_outputs]
        paths += [("execution/" + name, run / name) for name in ["contract.json", "result.json", "verification.json", "runner.log"]]
        for _, path in paths:
            require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_BYTES,
                    "RUN_ARTIFACT_REQUIRES_RESUMABLE_UPLOAD")
        stored = []
        for logical_name, path in paths:
            raw = path.read_bytes()
            # Fixed identity plus content-bound intent prevents changed bytes
            # from silently replacing an already published output.
            file_key = key + ":" + logical_name
            receipt = store.publish_bytes(raw=raw, folder_id=folder_id, campaign_id=campaign_id,
                                          name="RUN_ARTIFACT__" + digest(file_key.encode()) + path.suffix,
                                          mime_type="application/json" if path.suffix == ".json" else "application/octet-stream",
                                          intent_key=file_key, journal_directory=journals / "uploads")
            stored.append({"name": logical_name, "file_id": receipt["file_id"], "sha256": receipt["sha256"],
                           "size": receipt["size"], "version": receipt["version"], "mime_type": receipt["mime_type"]})
        event = make_event(campaign_id=campaign_id, entity_id=contract.run_id, kind="RUN", role="EXECUTOR",
                           actor_id=actor_id, version=event_version, atlas_scope=atlas_scope,
                           timestamp_utc=publication["timestamp_utc"], data={
                               "test_id": contract.test_id, "status": "SUCCEEDED", "runtime": "LOCAL",
                               "readback": {"status": "CONFIRMED"}, "contract_hash": contract.contract_hash,
                               "commit_sha": contract.commit_sha, "outputs": stored,
                               "review_state": "NOT_REVIEWED", "publication_state": "INTERNAL",
                               "limitations": ["Execution evidence only; not a scientific review or a new scientific claim."]})
        receipt = store.publish_event(event, folder_id, journals / "uploads")
        atomic_json(state_file, {**publication, "event_id": event["event_id"], "state": "PERSISTED_VERIFIED", "receipt": receipt})
        return {**receipt, "event_id": event["event_id"], "outputs": stored, "review_state": "NOT_REVIEWED"}
