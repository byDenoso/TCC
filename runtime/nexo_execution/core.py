from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable


VALID_PROVIDERS = {"local", "github_actions"}
TASK_REGISTRY: dict[str, list[str]] = {
    "cosmology_benchmark": ["python3", "benchmarks/cosmology_env_benchmark.py"],
}


@dataclass(frozen=True)
class ExecutionContract:
    schema: str
    execution_id: str
    work_id: str
    test_id: str
    provider: str
    repository: str
    commit_sha: str
    task_id: str
    parameters: dict[str, Any]
    seed: int | None
    timeout_minutes: int
    required_outputs: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionContract":
        required = {
            "schema", "execution_id", "work_id", "test_id", "provider",
            "repository", "commit_sha", "task_id", "parameters", "seed",
            "timeout_minutes", "required_outputs"
        }
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"missing contract fields: {', '.join(missing)}")
        if data["schema"] != "nexo.execution.v1":
            raise ValueError(f"unsupported schema: {data['schema']}")
        if data["provider"] not in VALID_PROVIDERS:
            raise ValueError(f"unsupported provider: {data['provider']}")
        if data["task_id"] not in TASK_REGISTRY:
            raise ValueError(f"task is not allowlisted: {data['task_id']}")
        if int(data["timeout_minutes"]) <= 0:
            raise ValueError("timeout_minutes must be positive")
        if not isinstance(data["required_outputs"], list) or not all(isinstance(x, str) and x for x in data["required_outputs"]):
            raise ValueError("required_outputs must be a string list")
        return cls(**data)

    @classmethod
    def load(cls, path: str | Path) -> "ExecutionContract":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @property
    def contract_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @property
    def argv(self) -> list[str]:
        return list(TASK_REGISTRY[self.task_id])


@dataclass
class ExecutionResult:
    execution_id: str
    work_id: str
    provider: str
    run_id: str | None
    commit_sha: str
    exit_code: int
    started_at: float
    finished_at: float
    outputs: list[dict[str, Any]]
    contract_hash: str
    error: str | None = None

    @property
    def execution_seconds(self) -> float:
        return self.finished_at - self.started_at

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["execution_seconds"] = self.execution_seconds
        return d


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_outputs(paths: Iterable[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in paths:
        p = Path(raw)
        if p.exists() and p.is_file():
            out.append({"path": raw, "sha256": sha256_file(p), "bytes": p.stat().st_size})
    return out


class LocalProvider:
    name = "local"

    def submit(self, contract: ExecutionContract) -> ExecutionResult:
        env = os.environ.copy()
        env["NEXO_EXECUTION_ID"] = contract.execution_id
        env["NEXO_WORK_ID"] = contract.work_id
        env["NEXO_TEST_ID"] = contract.test_id
        env["NEXO_SEED"] = "" if contract.seed is None else str(contract.seed)
        for key, value in contract.parameters.items():
            env[f"NEXO_PARAM_{str(key).upper()}"] = str(value)

        started = time.time()
        error = None
        try:
            cp = subprocess.run(
                contract.argv,
                env=env,
                timeout=contract.timeout_minutes * 60,
                check=False,
            )
            exit_code = cp.returncode
        except subprocess.TimeoutExpired:
            exit_code = 124
            error = "timeout"
        except Exception as exc:
            exit_code = 125
            error = f"provider_error:{type(exc).__name__}:{exc}"
        finished = time.time()

        return ExecutionResult(
            execution_id=contract.execution_id,
            work_id=contract.work_id,
            provider=contract.provider,
            run_id=os.getenv("GITHUB_RUN_ID"),
            commit_sha=contract.commit_sha,
            exit_code=exit_code,
            started_at=started,
            finished_at=finished,
            outputs=collect_outputs(contract.required_outputs),
            contract_hash=contract.contract_hash,
            error=error,
        )


class GitHubActionsProvider:
    name = "github_actions"

    def __init__(self, token: str | None = None, workflow: str = "nexo-execution.yml"):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.workflow = workflow
        if not self.token:
            raise ValueError("GITHUB_TOKEN is required")

    def _request(self, url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, bytes]:
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"GitHub API {exc.code}: {detail}") from exc

    def submit(self, contract: ExecutionContract, ref: str = "main", contract_path: str | None = None) -> dict[str, Any]:
        if contract.repository.count("/") != 1:
            raise ValueError("repository must be owner/name")
        if contract.provider != self.name:
            raise ValueError("contract provider must be github_actions")
        path = contract_path or f"runtime/nexo_execution/contracts/{contract.execution_id}.json"
        url = f"https://api.github.com/repos/{contract.repository}/actions/workflows/{self.workflow}/dispatches"
        status, _ = self._request(url, "POST", {
            "ref": ref,
            "inputs": {
                "contract_path": path,
                "expected_contract_hash": contract.contract_hash,
            },
        })
        return {"execution_id": contract.execution_id, "dispatch_http_status": status, "contract_hash": contract.contract_hash}


class ResultVerifier:
    def verify(self, contract: ExecutionContract, result: ExecutionResult) -> dict[str, Any]:
        errors: list[str] = []
        if result.execution_id != contract.execution_id:
            errors.append("execution_id_mismatch")
        if result.work_id != contract.work_id:
            errors.append("work_id_mismatch")
        if result.commit_sha != contract.commit_sha:
            errors.append("commit_sha_mismatch")
        if result.contract_hash != contract.contract_hash:
            errors.append("contract_hash_mismatch")
        if result.exit_code != 0:
            errors.append(f"nonzero_exit:{result.exit_code}")

        actual = {item["path"] for item in result.outputs}
        missing = [p for p in contract.required_outputs if p not in actual]
        if missing:
            errors.append("missing_outputs:" + ",".join(missing))

        return {
            "status": "PASS" if not errors else "FAIL",
            "execution_id": contract.execution_id,
            "contract_hash": contract.contract_hash,
            "errors": errors,
        }
