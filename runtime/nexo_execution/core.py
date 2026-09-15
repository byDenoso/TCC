from __future__ import annotations

import hashlib, json, os, subprocess, time, urllib.error, urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

VALID_PROVIDERS = {"local", "github_actions"}
TASK_REGISTRY: dict[str, list[str]] = {
    "cosmology_benchmark": ["python3", "benchmarks/cosmology_env_benchmark.py"],
    "idm_runtime_preflight": ["python3", "benchmarks/idm_runtime_preflight.py"],
    "gz01_desi_edr_nz_pilot": ["python3", "-m", "benchmarks.gz01_desi_edr_nz_pilot"],
    "gz01_multprobe_consistency": ["python3", "-m", "benchmarks.gz01_multprobe_consistency"],
    "gz01_covariance_redshift_envelope": ["python3", "-m", "benchmarks.gz01_covariance_redshift_envelope"],
    "gzsb05_s8_morphology": ["python3", "-m", "benchmarks.gzsb05_s8_morphology"],
    "gzsb06_s8_influence": ["python3", "-m", "benchmarks.gzsb06_s8_influence"],
}
for _gate_index in range(26):
    _gate_id = f"D{_gate_index:02d}"
    TASK_REGISTRY[f"peer_detection_d{_gate_index:02d}"] = [
        "python3", "-m", "benchmarks.peer_detection_gate", "--gate", _gate_id,
    ]
del _gate_index, _gate_id

@dataclass(frozen=True)
class ExecutionContract:
    schema: str; execution_id: str; work_id: str; test_id: str; provider: str
    repository: str; commit_sha: str; task_id: str; parameters: dict[str, Any]
    seed: int | None; timeout_minutes: int; required_outputs: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionContract":
        required = {"schema","execution_id","work_id","test_id","provider","repository","commit_sha","task_id","parameters","seed","timeout_minutes","required_outputs"}
        missing = sorted(required - set(data))
        if missing: raise ValueError("missing contract fields: " + ", ".join(missing))
        if data["schema"] != "nexo.execution.v1": raise ValueError(f"unsupported schema: {data['schema']}")
        if data["provider"] not in VALID_PROVIDERS: raise ValueError(f"unsupported provider: {data['provider']}")
        if data["task_id"] not in TASK_REGISTRY: raise ValueError(f"task is not allowlisted: {data['task_id']}")
        if int(data["timeout_minutes"]) <= 0: raise ValueError("timeout_minutes must be positive")
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
    execution_id: str; work_id: str; provider: str; run_id: str | None; commit_sha: str
    exit_code: int; started_at: float; finished_at: float; outputs: list[dict[str, Any]]
    contract_hash: str; error: str | None = None

    @property
    def execution_seconds(self) -> float:
        return self.finished_at - self.started_at

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self); data["execution_seconds"] = self.execution_seconds; return data

def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

def collect_outputs(paths: Iterable[str]) -> list[dict[str, Any]]:
    return [{"path": raw, "sha256": sha256_file(raw), "bytes": Path(raw).stat().st_size} for raw in paths if Path(raw).is_file()]

def current_git_sha() -> str:
    try: return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return "UNKNOWN"

class LocalProvider:
    name = "local"
    def submit(self, contract: ExecutionContract) -> ExecutionResult:
        env = os.environ.copy(); env.update({"NEXO_EXECUTION_ID":contract.execution_id,"NEXO_WORK_ID":contract.work_id,"NEXO_TEST_ID":contract.test_id,"NEXO_SEED":"" if contract.seed is None else str(contract.seed)})
        for key, value in contract.parameters.items(): env[f"NEXO_PARAM_{str(key).upper()}"] = str(value)
        started = time.time(); error = None
        try: exit_code = subprocess.run(contract.argv, env=env, timeout=contract.timeout_minutes*60, check=False).returncode
        except subprocess.TimeoutExpired: exit_code, error = 124, "timeout"
        except Exception as exc: exit_code, error = 125, f"provider_error:{type(exc).__name__}:{exc}"
        return ExecutionResult(contract.execution_id, contract.work_id, contract.provider, os.getenv("GITHUB_RUN_ID"), current_git_sha(), exit_code, started, time.time(), collect_outputs(contract.required_outputs), contract.contract_hash, error)

class GitHubActionsProvider:
    name = "github_actions"
    def __init__(self, token: str | None = None, workflow: str = "nexo-execution.yml"):
        self.token = token or os.getenv("GITHUB_TOKEN"); self.workflow = workflow
        if not self.token: raise ValueError("GITHUB_TOKEN is required")

    def _request(self, url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, bytes]:
        body = None if payload is None else json.dumps(payload).encode(); req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {self.token}"); req.add_header("Accept", "application/vnd.github+json"); req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if body is not None: req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as response: return response.status, response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GitHub API {exc.code}: {exc.read().decode(errors='replace')}") from exc

    def submit(self, contract: ExecutionContract, ref: str = "main", contract_name: str | None = None) -> dict[str, Any]:
        if contract.repository.count("/") != 1: raise ValueError("repository must be owner/name")
        if contract.provider != self.name: raise ValueError("contract provider must be github_actions")
        name = contract_name or f"{contract.execution_id}.json"
        if not name or "/" in name or ".." in name: raise ValueError("contract_name must be a safe filename")
        status, _ = self._request(f"https://api.github.com/repos/{contract.repository}/actions/workflows/{self.workflow}/dispatches", "POST", {"ref":ref,"inputs":{"contract_name":name,"expected_contract_hash":contract.contract_hash}})
        return {"execution_id":contract.execution_id,"dispatch_http_status":status,"contract_hash":contract.contract_hash,"contract_name":name}

class ResultVerifier:
    def verify(self, contract: ExecutionContract, result: ExecutionResult) -> dict[str, Any]:
        errors = []
        if result.execution_id != contract.execution_id: errors.append("execution_id_mismatch")
        if result.work_id != contract.work_id: errors.append("work_id_mismatch")
        if result.commit_sha != contract.commit_sha: errors.append("commit_sha_mismatch")
        if result.contract_hash != contract.contract_hash: errors.append("contract_hash_mismatch")
        if result.exit_code != 0: errors.append(f"nonzero_exit:{result.exit_code}")
        actual = {item["path"] for item in result.outputs}; missing = [p for p in contract.required_outputs if p not in actual]
        if missing: errors.append("missing_outputs:" + ",".join(missing))
        return {"status":"PASS" if not errors else "FAIL","execution_id":contract.execution_id,"contract_hash":contract.contract_hash,"errors":errors}
