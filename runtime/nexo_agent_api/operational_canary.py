"""Scoped, fail-closed runtime for the C01 readiness-cache canary.

This module only controls the reversible `readiness_cache` adapter. It does
not authorize other adapters, science settings, schedules, models, credentials,
or Tower authority. A trusted registry entry, frozen analysis plan, healthy
monitor, and readback-capable adapter are required before a candidate route.
"""
from __future__ import annotations

import copy
import contextvars
import datetime as dt
import hashlib
import inspect
import json
import marshal
import math
import os
import sys
import tempfile
import threading
import time
import types
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import NormalDist
from typing import Any, Callable, Mapping, Protocol

from .tower_paths import fs_path

_SHARED_READINESS_CACHE: Any = None
_SHARED_READINESS_CACHE_LOCK = threading.RLock()

CANARY_CONTRACT = "OPERATIONAL_CANARY_V1"
APPROVALS_CONTRACT = "EXECUTION_ASSESSMENT_APPROVALS_V1"
ADAPTER_ID = "readiness_cache"
REQUIRED_CORPUS_STRATA = frozenset({
    "missing_dependency", "hash_mismatch", "public", "private",
    "context_changed", "conflict", "timeout", "partial",
})
LIVE_PERFORMANCE_STRATA = frozenset({"public", "private"})
FORBIDDEN_SCOPES = frozenset({
    "models", "weights", "task_ids", "task_state", "cron", "triggers",
    "credentials", "acl", "tower_writer", "datasets", "priors", "nulls",
    "thresholds", "scientific_claims", "scientific_contracts", "camb_mcmc",
    "prompt_packs", "other_adapters",
})


class CanaryError(RuntimeError):
    pass


class AuthorizationError(CanaryError):
    pass


class AdapterConflict(CanaryError):
    pass


class ReadbackError(CanaryError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_json(value: Any) -> str:
    return sha256(canonical_json(value))


def parse_utc(value: str | dt.datetime) -> dt.datetime:
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    return parsed.astimezone(dt.timezone.utc)


def iso_utc(value: dt.datetime) -> str:
    return parse_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def deterministic_bucket(intent_id: str) -> int:
    """Stable 0..9999 bucket derived only from the canonical intent identity."""
    if not isinstance(intent_id, str) or not intent_id.strip():
        raise ValueError("INTENT_ID_REQUIRED")
    raw = hashlib.sha256(intent_id.encode("utf-8")).digest()
    return int.from_bytes(raw[:8], "big") % 10_000


def assigned_to_candidate(intent_id: str) -> bool:
    return deterministic_bucket(intent_id) < 1_000


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _normalised_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    # Readiness output is deterministic; compare every public decision field.
    return {key: result.get(key) for key in (
        "policy", "eligible", "reasons", "recipe_sha256", "input_scope",
        "recipe_scope", "param_preflight",
    ) if key in result}


def _readiness_results_equal(baseline: Any, candidate: Any) -> bool:
    try:
        return canonical_json(_normalised_result(baseline)) == canonical_json(_normalised_result(candidate))
    except (TypeError, ValueError):
        return False


def loaded_readiness_cache_sha256() -> str:
    """Fingerprint both readiness-cache source and code objects loaded in-process."""
    module = sys.modules.get("runtime.nexo_agent_api.readiness_cache")
    if module is None:
        from . import readiness_cache as module
    source_path = Path(module.__file__).resolve()
    source_hash = sha256(source_path.read_bytes())

    def stable_code(code: types.CodeType) -> types.CodeType:
        """Remove extraction-directory identity recursively from code objects.

        `marshal.dumps(code)` includes `co_filename`, including filenames in
        nested comprehensions and lambdas. Writer materializes each Tower under
        a fresh temporary root, so the exact same implementation otherwise
        receives a different candidate hash on every invocation.
        """
        filename = str(code.co_filename).replace("\\", "/")
        try:
            code_path = Path(code.co_filename)
            if code_path.is_absolute():
                try:
                    filename = code_path.resolve().relative_to(source_path.parent).as_posix()
                except ValueError:
                    # Every readiness-cache code object should be owned by this
                    # module. Preserve a stable basename for a generated or
                    # externally compiled function while still hashing its bytecode.
                    filename = "<external>/" + code_path.name
        except (OSError, ValueError, TypeError):
            pass
        constants = tuple(stable_code(value) if isinstance(value, types.CodeType) else value
                          for value in code.co_consts)
        return code.replace(co_filename=filename, co_consts=constants)

    loaded: list[dict[str, str]] = []
    for name, value in inspect.getmembers(module):
        if inspect.isfunction(value) and value.__module__ == module.__name__:
            loaded.append({"name": name, "code_sha256": sha256(marshal.dumps(stable_code(value.__code__)))})
        elif inspect.isclass(value) and value.__module__ == module.__name__:
            for member_name, member in inspect.getmembers(value):
                if inspect.isfunction(member) and member.__module__ == module.__name__:
                    loaded.append({"name": name + "." + member_name,
                                   "code_sha256": sha256(marshal.dumps(stable_code(member.__code__)))})
    loaded.sort(key=lambda item: item["name"])
    return digest_json({"source_sha256": source_hash, "loaded_code": loaded,
                        "python_cache_tag": sys.implementation.cache_tag})


def _binomial_cdf(k: int, n: int, p: float) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0 if k < n else 1.0
    log_p = math.log(p)
    log_q = math.log1p(-p)
    logs = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * log_p + (n - i) * log_q for i in range(k + 1)]
    peak = max(logs)
    return min(1.0, math.exp(peak) * sum(math.exp(item - peak) for item in logs))


def one_sided_binomial_upper(errors: int, independent_units: int, confidence: float = 0.95) -> float:
    """Exact Clopper-Pearson one-sided upper confidence bound."""
    if (type(errors) is not int or type(independent_units) is not int or errors < 0
            or independent_units <= 0 or errors > independent_units
            or not 0 < confidence < 1):
        raise ValueError("BINOMIAL_INPUT_INVALID")
    if errors == independent_units:
        return 1.0
    alpha = 1.0 - confidence
    if errors == 0:
        return 1.0 - alpha ** (1.0 / independent_units)
    low, high = 0.0, 1.0
    # Solve P(X <= errors | n, p) = alpha.
    for _ in range(72):
        middle = (low + high) / 2.0
        if _binomial_cdf(errors, independent_units, middle) > alpha:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


@dataclass(frozen=True)
class FrozenAnalysisPlan:
    """Pre-observation statistical choices tied to a corrected baseline replay."""

    baseline_replay_ref: str
    baseline_replay_sha256: str
    baseline_variance: float
    baseline_variance_n: int
    baseline_variance_ref: str
    expected_read_ratio: float
    strata_weights: tuple[tuple[str, float], ...]
    independence_basis: str
    cluster_key: str
    frozen_at: str
    corpus_strata: tuple[str, ...] = tuple(sorted(REQUIRED_CORPUS_STRATA))
    estimator: str = "stratified_paired_log_ratio_z95"
    confidence: float = 0.95
    power: float = 0.80
    max_candidate_units: int = 2_800
    minimum_candidate_units: int = 600
    maximum_days: int = 28
    minimum_days: int = 7
    max_candidate_units_per_day: int = 100
    target_read_ratio_upper: float = 0.85
    target_p95_latency_ratio: float = 1.10
    maximum_error_upper: float = 0.005

    def __post_init__(self) -> None:
        if not self.baseline_replay_ref or not self.baseline_variance_ref or not self.independence_basis:
            raise ValueError("FROZEN_PLAN_EVIDENCE_MISSING")
        if not _valid_hash(self.baseline_replay_sha256):
            raise ValueError("BASELINE_REPLAY_HASH_INVALID")
        if (isinstance(self.baseline_variance, bool) or not math.isfinite(self.baseline_variance)
                or self.baseline_variance < 0 or type(self.baseline_variance_n) is not int
                or self.baseline_variance_n < 2):
            raise ValueError("BASELINE_VARIANCE_INVALID")
        if not 0 < self.expected_read_ratio < self.target_read_ratio_upper < 1:
            raise ValueError("EXPECTED_EFFECT_INVALID")
        if self.estimator != "stratified_paired_log_ratio_z95":
            raise ValueError("ESTIMATOR_UNSUPPORTED")
        if self.confidence != 0.95:
            raise ValueError("C01_CONFIDENCE_MUST_MATCH_POLICY")
        if not (0 < self.power < 1):
            raise ValueError("CONFIDENCE_OR_POWER_INVALID")
        if self.cluster_key not in {"intent_id", "cluster_id"}:
            raise ValueError("CLUSTER_KEY_INVALID")
        if self.cluster_key == "cluster_id" and not self.independence_basis:
            raise ValueError("CLUSTER_INDEPENDENCE_NOT_JUSTIFIED")
        weights = dict(self.strata_weights)
        if set(weights) != LIVE_PERFORMANCE_STRATA:
            raise ValueError("LIVE_PERFORMANCE_STRATA_INVALID")
        if frozenset(self.corpus_strata) != REQUIRED_CORPUS_STRATA:
            raise ValueError("FROZEN_CORPUS_STRATA_INCOMPLETE")
        if any(not math.isfinite(weight) or weight <= 0 for weight in weights.values()):
            raise ValueError("STRATA_WEIGHT_INVALID")
        if not math.isclose(sum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-9):
            raise ValueError("STRATA_WEIGHTS_NOT_NORMALIZED")
        if (self.minimum_days != 7 or self.maximum_days != 28
                or self.max_candidate_units_per_day != 100
                or self.max_candidate_units != 2_800
                or self.minimum_candidate_units != 600):
            raise ValueError("C01_SAMPLE_LIMITS_MUST_MATCH_POLICY")
        if self.target_read_ratio_upper != 0.85 or self.target_p95_latency_ratio != 1.10:
            raise ValueError("C01_PERFORMANCE_LIMITS_MUST_MATCH_POLICY")
        if self.maximum_error_upper != 0.005:
            raise ValueError("C01_ERROR_BOUND_MUST_MATCH_POLICY")
        parse_utc(self.frozen_at)

    @property
    def required_candidate_units(self) -> int:
        # Normal approximation for the frozen paired log-ratio estimator.
        # Baseline replay variance, effect size, alpha and power are all frozen
        # before live observations; the observed sample cannot change this.
        delta = math.log(self.target_read_ratio_upper) - math.log(self.expected_read_ratio)
        if delta <= 0:
            return self.max_candidate_units + 1
        z_alpha = NormalDist().inv_cdf(self.confidence)
        z_power = NormalDist().inv_cdf(self.power)
        calculated = math.ceil(((z_alpha + z_power) ** 2 * self.baseline_variance) / (delta ** 2))
        return max(self.minimum_candidate_units, calculated)

    @property
    def can_start(self) -> bool:
        return self.required_candidate_units <= self.max_candidate_units

    @property
    def plan_sha256(self) -> str:
        return digest_json(asdict(self) | {"required_candidate_units": self.required_candidate_units})

    @classmethod
    def freeze_from_baseline_replay(
        cls,
        *,
        baseline_replay_ref: str,
        baseline_replay_sha256: str,
        baseline_variance: float,
        baseline_variance_n: int,
        baseline_variance_ref: str,
        expected_read_ratio: float,
        strata_weights: Mapping[str, float],
        independence_basis: str,
        cluster_key: str = "intent_id",
        frozen_at: str,
    ) -> "FrozenAnalysisPlan":
        """Create the immutable sample plan from a completed corrected-baseline replay."""
        return cls(
            baseline_replay_ref=baseline_replay_ref,
            baseline_replay_sha256=baseline_replay_sha256,
            baseline_variance=baseline_variance,
            baseline_variance_n=baseline_variance_n,
            baseline_variance_ref=baseline_variance_ref,
            expected_read_ratio=expected_read_ratio,
            strata_weights=tuple(sorted((str(key), float(value)) for key, value in strata_weights.items())),
            independence_basis=independence_basis,
            cluster_key=cluster_key,
            frozen_at=frozen_at,
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FrozenAnalysisPlan":
        fields = dict(value)
        fields["strata_weights"] = tuple(
            (str(item[0]), float(item[1])) for item in fields.get("strata_weights", [])
        )
        return cls(**fields)


@dataclass(frozen=True)
class CanaryConfig:
    canary_id: str
    baseline_version: str
    baseline_sha256: str
    candidate_version: str
    candidate_sha256: str
    proposal_ref: str
    analysis_plan: FrozenAnalysisPlan
    adapter_id: str = ADAPTER_ID
    assignment_numerator: int = 1
    assignment_denominator: int = 10

    def __post_init__(self) -> None:
        if not self.canary_id or not self.baseline_version or not self.candidate_version:
            raise ValueError("CANARY_IDENTITY_INCOMPLETE")
        if self.adapter_id != ADAPTER_ID:
            raise ValueError("ADAPTER_OUTSIDE_C01_SCOPE")
        if not _valid_hash(self.baseline_sha256) or not _valid_hash(self.candidate_sha256):
            raise ValueError("BASELINE_OR_CANDIDATE_HASH_INVALID")
        if self.baseline_sha256 == self.candidate_sha256:
            raise ValueError("BASELINE_CANDIDATE_HASH_COLLISION")
        if self.assignment_numerator != 1 or self.assignment_denominator != 10:
            raise ValueError("C01_ASSIGNMENT_MUST_BE_TEN_PERCENT")
        if not self.proposal_ref:
            raise ValueError("PROPOSAL_REFERENCE_MISSING")

    def proposal_payload(self) -> dict[str, Any]:
        return {
            "contract": CANARY_CONTRACT,
            "canary_id": self.canary_id,
            "adapter_id": self.adapter_id,
            "baseline": {"version": self.baseline_version, "sha256": self.baseline_sha256},
            "candidate": {"version": self.candidate_version, "sha256": self.candidate_sha256},
            "proposal_ref": self.proposal_ref,
            "analysis_plan": asdict(self.analysis_plan),
            "analysis_plan_sha256": self.analysis_plan.plan_sha256,
            "assignment": {"numerator": 1, "denominator": 10, "key": "sha256(intent_id)"},
            "limits": {
                "max_candidate_units_per_day": 100,
                "max_candidate_units_total": 2_800,
                "min_candidate_units": 600,
                "min_days": 7,
                "max_days": 28,
            },
            "allowed_scope": [ADAPTER_ID],
            "forbidden_scope": sorted(FORBIDDEN_SCOPES),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CanaryConfig":
        plan = value.get("analysis_plan")
        if not isinstance(plan, Mapping):
            raise ValueError("ANALYSIS_PLAN_INVALID")
        baseline = value.get("baseline")
        candidate = value.get("candidate")
        if not isinstance(baseline, Mapping) or not isinstance(candidate, Mapping):
            raise ValueError("BASELINE_OR_CANDIDATE_INVALID")
        assignment = value.get("assignment") or {}
        return cls(
            canary_id=str(value.get("canary_id") or ""),
            baseline_version=str(baseline.get("version") or ""),
            baseline_sha256=str(baseline.get("sha256") or ""),
            candidate_version=str(candidate.get("version") or ""),
            candidate_sha256=str(candidate.get("sha256") or ""),
            proposal_ref=str(value.get("proposal_ref") or ""),
            analysis_plan=FrozenAnalysisPlan.from_mapping(plan),
            adapter_id=str(value.get("adapter_id") or ADAPTER_ID),
            assignment_numerator=int(assignment.get("numerator", 1)),
            assignment_denominator=int(assignment.get("denominator", 10)),
        )

    @property
    def proposal_sha256(self) -> str:
        return digest_json(self.proposal_payload())


@dataclass(frozen=True)
class VerifiedMandate:
    canary_id: str
    approval_ref: str
    approved_at: str
    expires_at: str
    proposal_sha256: str
    registry_sha256: str
    adapter_id: str
    offline_corpus_sha256: str
    shadow_report_sha256: str


class MandateVerifier(Protocol):
    def verify(self, config: CanaryConfig, now: dt.datetime) -> VerifiedMandate | None: ...


class RegistryMandateVerifier:
    """Verify a scoped mandate in the trusted Writer approval registry.

    The expected registry hash, approval reference, and approval timestamp
    must arrive through trusted runtime configuration. Fields such as
    `source="DENER"` inside a proposal are never consulted.
    """

    def __init__(self, registry_path: Path, *, expected_registry_sha256: str,
                 expected_approval_ref: str, expected_approved_at: str) -> None:
        self.registry_path = Path(registry_path)
        self.expected_registry_sha256 = expected_registry_sha256
        self.expected_approval_ref = expected_approval_ref
        self.expected_approved_at = expected_approved_at

    def verify(self, config: CanaryConfig, now: dt.datetime) -> VerifiedMandate | None:
        try:
            if (not _valid_hash(self.expected_registry_sha256)
                    or not self.expected_approval_ref or not self.expected_approved_at
                    or not self.registry_path.is_file()):
                return None
            raw = self.registry_path.read_bytes()
            actual_registry_sha256 = sha256(raw)
            if actual_registry_sha256 != self.expected_registry_sha256:
                return None
            doc = json.loads(raw.decode("utf-8"))
            if not isinstance(doc, dict) or doc.get("contract") != APPROVALS_CONTRACT:
                return None
            records = doc.get("operational_canaries")
            if not isinstance(records, list):
                return None
            matches = [item for item in records if isinstance(item, dict)
                       and item.get("canary_id") == config.canary_id]
            if len(matches) != 1:
                return None
            item = matches[0]
            scopes = item.get("scope")
            if (item.get("enabled") is not True or item.get("adapter_id") != ADAPTER_ID
                    or scopes != [ADAPTER_ID]
                    or FORBIDDEN_SCOPES.intersection(set(item.get("forbidden_scope") or [])) != FORBIDDEN_SCOPES
                    or item.get("approval_ref") != self.expected_approval_ref
                    or item.get("approved_at") != self.expected_approved_at
                    or item.get("proposal_sha256") != config.proposal_sha256
                    or item.get("baseline_sha256") != config.baseline_sha256
                    or item.get("candidate_sha256") != config.candidate_sha256
                    or item.get("analysis_plan_sha256") != config.analysis_plan.plan_sha256
                    or not _valid_hash(item.get("offline_corpus_sha256"))
                    or not _valid_hash(item.get("shadow_report_sha256"))):
                return None
            starts = parse_utc(item["valid_from"])
            expires = parse_utc(item["expires_at"])
            current = parse_utc(now)
            if not starts <= current < expires:
                return None
            if parse_utc(self.expected_approved_at) > current:
                return None
            return VerifiedMandate(
                canary_id=config.canary_id,
                approval_ref=self.expected_approval_ref,
                approved_at=self.expected_approved_at,
                expires_at=iso_utc(expires),
                proposal_sha256=config.proposal_sha256,
                registry_sha256=actual_registry_sha256,
                adapter_id=ADAPTER_ID,
                offline_corpus_sha256=str(item["offline_corpus_sha256"]),
                shadow_report_sha256=str(item["shadow_report_sha256"]),
            )
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            return None


@dataclass(frozen=True)
class SelectionReceipt:
    adapter_id: str
    canary_id: str
    before_selection: dict[str, Any] | None
    after_selection: dict[str, Any]
    after_selection_sha256: str
    readback_sha256: str
    document_sha256: str
    selected_at: str


@dataclass(frozen=True)
class CandidateExecutionReceipt:
    canary_id: str
    intent_id: str
    reservation_token: str
    candidate_sha256: str
    readiness_context_sha256: str
    executed_at: str
    baseline_result_sha256: str
    result_sha256: str
    baseline_metrics_sha256: str
    candidate_metrics_sha256: str
    repeat: bool
    _runtime_nonce: object = field(repr=False, compare=False)


class TowerCanaryStore:
    """C01 state, evidence and pointer inside the canonical Tower snapshot.

    The Writer materializes the canonical Tower into `root`, this store
    mutates only `operational/operational_canary.json`, and the existing pack,
    CAS and readback path persists the resulting snapshot. No separate file,
    database, or `/tmp` ledger is an authority for live routing.
    """

    DOCUMENT = "operational/operational_canary.json"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.path = fs_path(self.root, self.DOCUMENT)

    def _empty(self) -> dict[str, Any]:
        return {"contract": CANARY_CONTRACT, "visibility": "PRIVATE",
                "canaries": {}, "adapters": {}}

    def _read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._empty()
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        if (not isinstance(doc, dict) or doc.get("contract") != CANARY_CONTRACT
                or doc.get("visibility") != "PRIVATE"):
            raise ValueError("TOWER_CANARY_DOCUMENT_INVALID")
        return doc

    def document_sha256(self) -> str:
        return digest_json(self._read())

    def _mutate(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        doc = self._read()
        result = callback(doc)
        encoded = canonical_json(doc) + b"\n"
        fd, name = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp",
                                    dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        readback = self._read()
        if canonical_json(readback) != canonical_json(doc):
            raise ReadbackError("TOWER_CANARY_DOCUMENT_READBACK_MISMATCH")
        return result

    def get(self, canary_id: str) -> dict[str, Any]:
        record = (self._read().get("canaries") or {}).get(canary_id, {})
        return copy.deepcopy(record) if isinstance(record, dict) else {}

    def config(self, canary_id: str) -> CanaryConfig | None:
        spec = self.get(canary_id).get("spec")
        if not isinstance(spec, dict):
            return None
        try:
            return CanaryConfig.from_mapping(spec)
        except (KeyError, TypeError, ValueError):
            return None

    def configured_canaries(self) -> list[CanaryConfig]:
        records = self._read().get("canaries") or {}
        if not isinstance(records, dict):
            return []
        result = []
        for canary_id in sorted(records):
            config = self.config(str(canary_id))
            if config is not None:
                result.append(config)
        return result

    def initialize(self, config: CanaryConfig) -> dict[str, Any]:
        def mutate(doc: dict[str, Any]):
            records = doc.setdefault("canaries", {})
            if not isinstance(records, dict):
                raise ValueError("CANARY_TOWER_STATE_INVALID")
            old = records.get(config.canary_id)
            if old is not None:
                if not isinstance(old, dict) or old.get("proposal_sha256") != config.proposal_sha256:
                    raise CanaryError("CANARY_ID_PROPOSAL_CONFLICT")
                return copy.deepcopy(old)
            record = {
                "canary_id": config.canary_id,
                "adapter_id": ADAPTER_ID,
                "spec": config.proposal_payload(),
                "proposal_sha256": config.proposal_sha256,
                "analysis_plan_sha256": config.analysis_plan.plan_sha256,
                "state": "PROPOSED",
                "created_at": None,
                "started_at": None,
                "observations": [],
                "reservations": {},
                "actuator_receipt": None,
                "last_gate": None,
            }
            records[config.canary_id] = record
            return copy.deepcopy(record)
        return self._mutate(mutate)

    def set_state(self, canary_id: str, state: str, *, at: dt.datetime,
                  details: Mapping[str, Any] | None = None) -> None:
        def mutate(doc: dict[str, Any]):
            record = (doc.get("canaries") or {}).get(canary_id)
            if not isinstance(record, dict):
                raise CanaryError("CANARY_TOWER_RECORD_MISSING")
            record["state"] = state
            record["state_at"] = iso_utc(at)
            if details:
                record.update(copy.deepcopy(dict(details)))
            if state == "CANARY" and not record.get("started_at"):
                record["started_at"] = iso_utc(at)
        self._mutate(mutate)

    def read_selection(self) -> dict[str, Any] | None:
        adapters = self._read().get("adapters")
        if not isinstance(adapters, dict):
            raise ValueError("ADAPTER_POINTERS_INVALID")
        selection = adapters.get(ADAPTER_ID)
        if selection is not None and not isinstance(selection, dict):
            raise ValueError("SELECTION_POINTER_INVALID")
        return copy.deepcopy(selection)

    def install_baseline_selection(self, config: CanaryConfig) -> dict[str, Any]:
        """Install/read back only the corrected baseline pointer, never candidate."""
        expected = {"variant": "baseline", "version": config.baseline_version,
                    "sha256": config.baseline_sha256}
        def mutate(doc: dict[str, Any]):
            adapters = doc.setdefault("adapters", {})
            if not isinstance(adapters, dict):
                raise AdapterConflict("ADAPTER_POINTERS_INVALID")
            current = adapters.get(ADAPTER_ID)
            if current is None:
                adapters[ADAPTER_ID] = copy.deepcopy(expected)
            elif any(current.get(key) != value for key, value in expected.items()):
                raise AdapterConflict("EXISTING_ADAPTER_SELECTION_CONFLICT")
        self._mutate(mutate)
        readback = self.read_selection()
        if readback is None or any(readback.get(key) != value for key, value in expected.items()):
            raise ReadbackError("BASELINE_SELECTION_READBACK_MISMATCH")
        receipt = {"adapter_id": ADAPTER_ID, "selection": readback,
                   "selection_sha256": digest_json(readback),
                   "document_sha256": self.document_sha256(), "readback": "PASS"}
        def save(doc: dict[str, Any]):
            record = (doc.get("canaries") or {}).get(config.canary_id)
            if not isinstance(record, dict):
                raise CanaryError("CANARY_TOWER_RECORD_MISSING")
            record["baseline_selection_receipt"] = copy.deepcopy(receipt)
        self._mutate(save)
        return receipt

    def existing_observation(self, canary_id: str, intent_id: str,
                             context_sha256: str) -> dict[str, Any] | None:
        record = self.get(canary_id)
        for observation in record.get("observations", []):
            if (isinstance(observation, dict)
                    and observation.get("intent_id") == intent_id
                    and observation.get("candidate_context_sha256") == context_sha256
                    and observation.get("candidate_evaluated") is True):
                return copy.deepcopy(observation)
        return None

    def reserve(self, config: CanaryConfig, intent_id: str, at: dt.datetime) -> tuple[str, bool] | None:
        at = parse_utc(at)
        token = uuid.uuid4().hex
        day = at.date().isoformat()
        answer: tuple[str, bool] | None = None
        def mutate(doc: dict[str, Any]):
            nonlocal answer
            record = (doc.get("canaries") or {}).get(config.canary_id)
            if not isinstance(record, dict) or record.get("state") != "CANARY":
                return
            observations = record.setdefault("observations", [])
            reservations = record.setdefault("reservations", {})
            observed = {str(item.get("intent_id")) for item in observations
                        if isinstance(item, dict) and item.get("candidate_evaluated") is True}
            active = {str(item.get("intent_id")) for item in reservations.values()
                      if isinstance(item, dict)}
            if intent_id in observed:
                # A repeated request reuses its recorded candidate assignment
                # and result. It must never invoke the candidate again.
                answer = ("repeat:" + intent_id, True)
                return
            if intent_id in active:
                # A parallel duplicate cannot run before the first result is
                # durably recorded in this canonical Writer transaction.
                return
            day_used = sum(1 for item in observations if isinstance(item, dict)
                           and item.get("candidate_evaluated") is True
                           and str(item.get("occurred_at", ""))[:10] == day)
            day_reserved = sum(1 for item in reservations.values() if isinstance(item, dict)
                               and str(item.get("reserved_at", ""))[:10] == day)
            total_used = sum(1 for item in observations if isinstance(item, dict)
                             and item.get("candidate_evaluated") is True)
            if (day_used + day_reserved >= config.analysis_plan.max_candidate_units_per_day
                    or total_used + len(reservations) >= config.analysis_plan.max_candidate_units):
                return
            reservations[token] = {"intent_id": intent_id, "reserved_at": iso_utc(at)}
            answer = (token, False)
        self._mutate(mutate)
        return answer

    def cancel_reservation(self, canary_id: str, token: str) -> None:
        def mutate(doc: dict[str, Any]):
            record = (doc.get("canaries") or {}).get(canary_id)
            if isinstance(record, dict):
                (record.get("reservations") or {}).pop(token, None)
        self._mutate(mutate)

    def reservation(self, canary_id: str, token: str) -> dict[str, Any] | None:
        record = self.get(canary_id)
        reservation = (record.get("reservations") or {}).get(token)
        return copy.deepcopy(reservation) if isinstance(reservation, dict) else None

    def record(self, config: CanaryConfig, receipt: CandidateExecutionReceipt, *, at: dt.datetime,
               stratum: str, cluster_id: str, baseline_result: Any,
               candidate_result: Any, baseline_metrics: Mapping[str, Any],
               candidate_metrics: Mapping[str, Any]) -> dict[str, Any]:
        if stratum not in LIVE_PERFORMANCE_STRATA or not cluster_id:
            raise ValueError("OBSERVATION_STRATUM_OR_CLUSTER_INVALID")
        at = parse_utc(at)
        pair: dict[str, Any] = {
            "intent_id": "",
            "cluster_id": cluster_id,
            "stratum": stratum,
            "occurred_at": iso_utc(at),
            "baseline_result": copy.deepcopy(baseline_result),
            "candidate_result": copy.deepcopy(candidate_result),
            "baseline_metrics": copy.deepcopy(dict(baseline_metrics)),
            "candidate_metrics": copy.deepcopy(dict(candidate_metrics)),
            "candidate_evaluated": True,
            "candidate_evaluation_count": 1,
            "metric_pairs": [],
            "candidate_sha256": receipt.candidate_sha256,
            "candidate_context_sha256": receipt.readiness_context_sha256,
            "candidate_receipt_sha256": digest_json({
                "intent_id": receipt.intent_id,
                "candidate_sha256": receipt.candidate_sha256,
                "context_sha256": receipt.readiness_context_sha256,
                "executed_at": receipt.executed_at,
                "baseline_result_sha256": receipt.baseline_result_sha256,
                "result_sha256": receipt.result_sha256,
                "baseline_metrics_sha256": receipt.baseline_metrics_sha256,
                "candidate_metrics_sha256": receipt.candidate_metrics_sha256,
            }),
            "decision_match": _readiness_results_equal(baseline_result, candidate_result),
        }
        answer: dict[str, Any] = {}
        def mutate(doc: dict[str, Any]):
            record = (doc.get("canaries") or {}).get(config.canary_id)
            if not isinstance(record, dict) or record.get("state") != "CANARY":
                raise CanaryError("CANARY_NOT_ACTIVE")
            if receipt.candidate_sha256 != config.candidate_sha256:
                raise CanaryError("CANDIDATE_EXECUTION_HASH_MISMATCH")
            reservations = record.setdefault("reservations", {})
            observations = record.setdefault("observations", [])
            if receipt.repeat:
                raise CanaryError("REPEAT_ROUTE_MUST_NOT_BE_EVALUATED")
            reservation = reservations.pop(receipt.reservation_token, None)
            if (not isinstance(reservation, dict)
                    or reservation.get("intent_id") != receipt.intent_id):
                raise CanaryError("CANDIDATE_RESERVATION_MISSING")
            if str(reservation.get("reserved_at", ""))[:10] != at.date().isoformat():
                raise CanaryError("CANDIDATE_RESERVATION_DAY_CROSSED")
            if receipt.executed_at != iso_utc(at):
                raise CanaryError("CANDIDATE_EXECUTION_TIMESTAMP_MISMATCH")
            if receipt.result_sha256 != digest_json(candidate_result):
                raise CanaryError("CANDIDATE_RESULT_RECEIPT_MISMATCH")
            pair["intent_id"] = receipt.intent_id
            if any(item.get("intent_id") == receipt.intent_id and item.get("candidate_evaluated") is True
                   for item in observations if isinstance(item, dict)):
                answer.update(recorded=False, reason="DUPLICATE_INTENT")
                return
            day = at.date().isoformat()
            day_count = sum(1 for item in observations if isinstance(item, dict)
                            and item.get("candidate_evaluated") is True
                            and str(item.get("occurred_at", ""))[:10] == day)
            if (day_count >= config.analysis_plan.max_candidate_units_per_day
                    or sum(1 for item in observations if isinstance(item, dict)
                           and item.get("candidate_evaluated") is True) >= config.analysis_plan.max_candidate_units):
                raise CanaryError("CANDIDATE_EVALUATION_CAP_REACHED")
            pair["metric_pairs"].append({
                "baseline_metrics": copy.deepcopy(dict(baseline_metrics)),
                "candidate_metrics": copy.deepcopy(dict(candidate_metrics)),
                "decision_match": pair["decision_match"],
                "candidate_receipt_sha256": pair["candidate_receipt_sha256"],
                "occurred_at": pair["occurred_at"],
                "stratum": stratum,
            })
            observations.append(copy.deepcopy(pair))
            answer.update(recorded=True, repeat=False, decision_match=pair["decision_match"])
        self._mutate(mutate)
        return answer

    def activate(self, config: CanaryConfig, *, expected_baseline_version: str,
                 expected_baseline_sha256: str, selected_at: dt.datetime) -> SelectionReceipt:
        before: dict[str, Any] | None = None
        after = {"variant": "candidate", "version": config.candidate_version,
                 "sha256": config.candidate_sha256, "canary_id": config.canary_id,
                 "selected_at": iso_utc(selected_at)}
        def mutate(doc: dict[str, Any]):
            nonlocal before
            adapters = doc.setdefault("adapters", {})
            if not isinstance(adapters, dict):
                raise AdapterConflict("ADAPTER_POINTERS_INVALID")
            current = adapters.get(ADAPTER_ID)
            if (not isinstance(current, dict) or current.get("variant") != "baseline"
                    or current.get("version") != expected_baseline_version
                    or current.get("sha256") != expected_baseline_sha256):
                raise AdapterConflict("BASELINE_SELECTION_CHANGED")
            before = copy.deepcopy(current)
            adapters[ADAPTER_ID] = copy.deepcopy(after)
        try:
            self._mutate(mutate)
            readback_doc = self._read()
            readback = (readback_doc.get("adapters") or {}).get(ADAPTER_ID)
            if readback != after:
                raise ReadbackError("CANDIDATE_SELECTION_READBACK_MISMATCH")
        except Exception:
            # An atomic replacement may have succeeded even if the subsequent
            # persistence/readback step failed. Compensate only if our exact
            # pointer is still selected, preserving every unrelated field.
            try:
                current = self.read_selection()
                if current == after and before is not None:
                    repair = SelectionReceipt(
                        adapter_id=ADAPTER_ID, canary_id=config.canary_id,
                        before_selection=before, after_selection=after,
                        after_selection_sha256=digest_json(after),
                        readback_sha256=config.candidate_sha256,
                        document_sha256=self.document_sha256(),
                        selected_at=iso_utc(selected_at),
                    )
                    self.rollback(repair, at=selected_at)
            except Exception:
                pass
            raise
        return SelectionReceipt(
            adapter_id=ADAPTER_ID,
            canary_id=config.canary_id,
            before_selection=before,
            after_selection=after,
            after_selection_sha256=digest_json(after),
            readback_sha256=str(readback.get("sha256") or ""),
            document_sha256=digest_json(readback_doc),
            selected_at=iso_utc(selected_at),
        )

    def rollback(self, receipt: SelectionReceipt, *, at: dt.datetime) -> dict[str, Any]:
        restored: dict[str, Any] | None = None
        def mutate(doc: dict[str, Any]):
            nonlocal restored
            adapters = doc.get("adapters")
            if not isinstance(adapters, dict):
                raise AdapterConflict("ADAPTER_POINTERS_INVALID")
            current = adapters.get(ADAPTER_ID)
            if (not isinstance(current, dict)
                    or digest_json(current) != receipt.after_selection_sha256
                    or current.get("canary_id") != receipt.canary_id):
                raise AdapterConflict("CANDIDATE_POINTER_CHANGED")
            if receipt.before_selection is None:
                adapters.pop(ADAPTER_ID, None)
            else:
                adapters[ADAPTER_ID] = copy.deepcopy(receipt.before_selection)
                restored = copy.deepcopy(receipt.before_selection)
        self._mutate(mutate)
        readback = self.read_selection()
        if readback != restored:
            raise ReadbackError("BASELINE_SELECTION_READBACK_MISMATCH")
        return {"adapter_id": ADAPTER_ID, "selection": readback,
                "document_sha256": self.document_sha256(), "readback": "PASS",
                "occurred_at": iso_utc(at)}

    def save_actuator_receipt(self, canary_id: str, receipt: SelectionReceipt) -> None:
        def mutate(doc: dict[str, Any]):
            record = (doc.get("canaries") or {}).get(canary_id)
            if not isinstance(record, dict):
                raise CanaryError("CANARY_TOWER_RECORD_MISSING")
            record["actuator_receipt"] = asdict(receipt)
            record["readback_status"] = "PASS"
            record["loaded_candidate_sha256"] = receipt.readback_sha256
        self._mutate(mutate)


@dataclass(frozen=True)
class CanaryRoute:
    canary_id: str
    intent_id: str
    variant: str
    token: str | None
    reason: str
    occurred_at: str
    repeat: bool = False


@dataclass(frozen=True)
class PromotionDecision:
    promotable: bool
    state: str
    candidate_units: int
    independent_units: int
    errors: int
    error_upper_95: float | None
    read_ratio_upper_95: float | None
    p95_latency_ratio: float | None
    blockers: tuple[str, ...]


def _metric_number(metrics: Mapping[str, Any], key: str) -> float:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError("METRIC_INVALID:" + key)
    return float(value)


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("METRIC_SAMPLE_EMPTY")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _paired_performance(observations: list[dict[str, Any]], plan: FrozenAnalysisPlan) -> tuple[float | None, float | None, list[str]]:
    blockers: list[str] = []
    if len(observations) < 2:
        return None, None, ["PAIRED_PERFORMANCE_SAMPLE_INSUFFICIENT"]
    weights = dict(plan.strata_weights)
    strata: dict[str, list[dict[str, Any]]] = {key: [] for key in weights}
    for observation in observations:
        if observation.get("decision_match") is not True:
            blockers.append("DECISION_DIVERGENCE")
        stratum = observation.get("stratum")
        if stratum not in strata:
            blockers.append("OBSERVATION_STRATUM_INVALID")
            continue
        strata[stratum].append(observation)
    weighted_mean = 0.0
    weighted_variance = 0.0
    latency_ratios = []
    z = NormalDist().inv_cdf(plan.confidence)
    for name, weight in weights.items():
        rows = strata[name]
        if len(rows) < 2:
            blockers.append("STRATUM_SAMPLE_INSUFFICIENT:" + name)
            continue
        logs: list[float] = []
        baseline_latencies: list[float] = []
        candidate_latencies: list[float] = []
        for row in rows:
            base = row["baseline_metrics"]
            cand = row["candidate_metrics"]
            base_reads = _metric_number(base, "read_calls")
            cand_reads = _metric_number(cand, "read_calls")
            if base_reads <= 0 or cand_reads <= 0:
                blockers.append("READ_CALL_METRIC_INVALID")
                continue
            logs.append(math.log(cand_reads / base_reads))
            baseline_latencies.append(_metric_number(base, "elapsed_ms"))
            candidate_latencies.append(_metric_number(cand, "elapsed_ms"))
            if cand.get("error") is True:
                blockers.append("CANDIDATE_EVALUATION_ERROR")
        if len(logs) < 2:
            blockers.append("STRATUM_METRICS_INCOMPLETE:" + name)
            continue
        mean = sum(logs) / len(logs)
        sample_var = sum((value - mean) ** 2 for value in logs) / (len(logs) - 1)
        weighted_mean += weight * mean
        weighted_variance += (weight ** 2) * sample_var / len(logs)
        base_p95 = _nearest_rank(baseline_latencies, 0.95)
        cand_p95 = _nearest_rank(candidate_latencies, 0.95)
        if base_p95 <= 0:
            blockers.append("BASELINE_LATENCY_INVALID:" + name)
        else:
            latency_ratios.append(cand_p95 / base_p95)
    if blockers and any(item.startswith("STRATUM") or item.endswith("INVALID") for item in blockers):
        return None, max(latency_ratios) if latency_ratios else None, blockers
    read_upper = math.exp(weighted_mean + z * math.sqrt(max(0.0, weighted_variance)))
    p95_ratio = max(latency_ratios) if len(latency_ratios) == len(weights) else None
    if p95_ratio is None:
        blockers.append("P95_STRATUM_COVERAGE_INCOMPLETE")
    return read_upper, p95_ratio, blockers


def validate_offline_corpus_report(report: Mapping[str, Any],
                                   config: CanaryConfig) -> str | None:
    """Validate a sanitized, pre-observation replay summary and its content hash."""
    if not isinstance(report, Mapping):
        return None
    payload = dict(report)
    claimed = payload.pop("report_sha256", None)
    if (payload.get("contract") != "C01_OFFLINE_CORPUS_REPLAY_V1"
            or payload.get("canary_id") != config.canary_id
            or payload.get("baseline_sha256") != config.baseline_sha256
            or payload.get("candidate_sha256") != config.candidate_sha256
            or payload.get("analysis_plan_sha256") != config.analysis_plan.plan_sha256
            or payload.get("candidate_adapter_sha256") != config.candidate_sha256
            or payload.get("decision_mismatches") != 0
            or payload.get("evaluation_errors") != 0
            or payload.get("critical_violations") != 0
            or set(payload.get("evaluation_orders") or []) != {"BASELINE_THEN_CANDIDATE", "CANDIDATE_THEN_BASELINE"}
            or not _valid_hash(claimed)
            or claimed != digest_json(payload)):
        return None
    counts = payload.get("strata_counts")
    order_counts = payload.get("evaluation_order_counts")
    if (not isinstance(counts, Mapping)
            or set(counts) != REQUIRED_CORPUS_STRATA
            or any(type(counts.get(name)) is not int or counts.get(name, 0) < 1
                   for name in REQUIRED_CORPUS_STRATA)
            or not isinstance(order_counts, Mapping)
            or set(order_counts) != {"BASELINE_THEN_CANDIDATE", "CANDIDATE_THEN_BASELINE"}
            or any(type(order_counts.get(name)) is not int or order_counts.get(name, 0) < 1
                   for name in ("BASELINE_THEN_CANDIDATE", "CANDIDATE_THEN_BASELINE"))):
        return None
    try:
        created_at = parse_utc(str(payload.get("created_at") or ""))
    except (TypeError, ValueError):
        return None
    if created_at <= parse_utc(config.analysis_plan.frozen_at):
        return None
    return str(claimed)


def validate_shadow_report(report: Mapping[str, Any], config: CanaryConfig) -> str | None:
    """Validate an independently monitored no-impact production shadow report."""
    if not isinstance(report, Mapping):
        return None
    payload = dict(report)
    claimed = payload.pop("report_sha256", None)
    if (payload.get("contract") != "C01_SHADOW_REPLAY_V1"
            or payload.get("canary_id") != config.canary_id
            or payload.get("baseline_sha256") != config.baseline_sha256
            or payload.get("candidate_sha256") != config.candidate_sha256
            or payload.get("analysis_plan_sha256") != config.analysis_plan.plan_sha256
            or type(payload.get("shadow_candidate_units")) is not int
            or payload.get("shadow_candidate_units", 0) < 1
            or payload.get("decision_mismatches") != 0
            or payload.get("evaluation_errors") != 0
            or payload.get("critical_violations") != 0
            or payload.get("selection_during_shadow") != "BASELINE"
            or not _valid_hash(claimed)
            or claimed != digest_json(payload)):
        return None
    try:
        observed = parse_utc(str(payload.get("observed_at") or ""))
    except (TypeError, ValueError):
        return None
    if observed <= parse_utc(config.analysis_plan.frozen_at):
        return None
    return str(claimed)


class OperationalCanary:
    """C01 state machine and active readiness-cache router."""

    def __init__(self, config: CanaryConfig, *, verifier: MandateVerifier | None,
                 ledger: TowerCanaryStore | None,
                 adapter: TowerCanaryStore | None,
                 monitor: Callable[[], bool] | None,
                 baseline_verifier: Callable[[CanaryConfig], bool] | None) -> None:
        self.config = config
        self.verifier = verifier
        self.ledger = ledger
        self.adapter = adapter
        self.monitor = monitor
        self.baseline_verifier = baseline_verifier
        self._lock = threading.RLock()
        self._verified_mandate: VerifiedMandate | None = None
        self._runtime_nonce = object()

    @property
    def state(self) -> str:
        if self.ledger is None:
            return "PROPOSED"
        return str(self.ledger.get(self.config.canary_id).get("state") or "PROPOSED")

    def _monitor_healthy(self) -> bool:
        if self.monitor is None:
            return False
        try:
            return self.monitor() is True
        except Exception:
            return False

    def _mandate(self, now: dt.datetime) -> VerifiedMandate | None:
        if self.verifier is None:
            return None
        try:
            mandate = self.verifier.verify(self.config, parse_utc(now))
        except Exception:
            return None
        if (mandate is None or mandate.canary_id != self.config.canary_id
                or mandate.adapter_id != ADAPTER_ID
                or mandate.proposal_sha256 != self.config.proposal_sha256
                or mandate.expires_at <= iso_utc(now)):
            return None
        return mandate

    def _mandate_reports_match(self, mandate: VerifiedMandate | None) -> bool:
        if mandate is None or self.ledger is None:
            return False
        record = self.ledger.get(self.config.canary_id)
        return (record.get("offline_corpus_sha256") == mandate.offline_corpus_sha256
                and record.get("shadow_report_sha256") == mandate.shadow_report_sha256)

    def start(self, *, now: dt.datetime,
              offline_corpus_report: Mapping[str, Any]) -> bool:
        """Start only after verified scope, replay evidence, and actuator readback."""
        at = parse_utc(now)
        plan = self.config.analysis_plan
        if (self.ledger is None or self.adapter is None or self.verifier is None
                or self.baseline_verifier is None or not plan.can_start
                or not self._monitor_healthy()):
            return False
        corpus_sha256 = validate_offline_corpus_report(offline_corpus_report, self.config)
        if corpus_sha256 is None:
            return False
        if parse_utc(plan.frozen_at) >= at:
            return False
        try:
            if self.baseline_verifier(self.config) is not True:
                return False
        except Exception:
            return False
        mandate = self._mandate(at)
        if mandate is None or mandate.offline_corpus_sha256 != corpus_sha256:
            return False
        if loaded_readiness_cache_sha256() != self.config.candidate_sha256:
            return False
        try:
            self.ledger.initialize(self.config)
            if self.state not in {"PROPOSED", "APPROVED_SCOPE", "SHADOW"}:
                return False
            selected = self.adapter.read_selection()
            if (not isinstance(selected, dict) or selected.get("variant") != "baseline"
                    or selected.get("version") != self.config.baseline_version
                    or selected.get("sha256") != self.config.baseline_sha256):
                return False
            self.ledger.set_state(self.config.canary_id, "APPROVED_SCOPE", at=at,
                                  details={"mandate": asdict(mandate),
                                           "offline_corpus_sha256": corpus_sha256,
                                           "frozen_plan_sha256": plan.plan_sha256})
            self.ledger.set_state(self.config.canary_id, "SHADOW", at=at)
        except Exception:
            return False
        self._verified_mandate = mandate
        return True

    def activate_canary(self, *, now: dt.datetime,
                        shadow_report: Mapping[str, Any]) -> bool:
        """Cross the separate SHADOW gate and read back the candidate selection."""
        at = parse_utc(now)
        if (self.state != "SHADOW" or self.ledger is None or self.adapter is None
                or self.baseline_verifier is None or not self._monitor_healthy()):
            return False
        shadow_sha256 = validate_shadow_report(shadow_report, self.config)
        mandate = self._mandate(at)
        if (shadow_sha256 is None or mandate is None
                or mandate.shadow_report_sha256 != shadow_sha256):
            return False
        try:
            if self.baseline_verifier(self.config) is not True:
                return False
        except Exception:
            return False
        current = self.adapter.read_selection()
        if (not isinstance(current, dict) or current.get("variant") != "baseline"
                or current.get("version") != self.config.baseline_version
                or current.get("sha256") != self.config.baseline_sha256):
            return False
        selection: SelectionReceipt | None = None
        try:
            selection = self.adapter.activate(
                self.config,
                expected_baseline_version=self.config.baseline_version,
                expected_baseline_sha256=self.config.baseline_sha256,
                selected_at=at,
            )
            if (selection.readback_sha256 != self.config.candidate_sha256
                    or loaded_readiness_cache_sha256() != self.config.candidate_sha256):
                raise ReadbackError("CANDIDATE_SELECTION_READBACK_MISMATCH")
            if self._mandate(at) is None:
                raise CanaryError("MANDATE_LOST_AFTER_SELECTION")
            self.ledger.save_actuator_receipt(self.config.canary_id, selection)
            self.ledger.set_state(self.config.canary_id, "CANARY", at=at,
                                  details={"shadow_report_sha256": shadow_sha256})
            self._verified_mandate = self._mandate(at)
            if (self._verified_mandate is None
                    or not self._mandate_reports_match(self._verified_mandate)):
                raise CanaryError("MANDATE_REPORTS_LOST_AFTER_SELECTION")
            return True
        except Exception:
            if selection is not None:
                try:
                    self.adapter.rollback(selection, at=at)
                    self.ledger.set_state(self.config.canary_id, "ROLLED_BACK", at=at,
                                          details={"activation_rollback": "PASS"})
                except Exception as exc:
                    self.ledger.set_state(self.config.canary_id, "INTERRUPTED", at=at,
                                          details={"activation_rollback": type(exc).__name__})
            return False

    def route(self, intent_id: str, *, now: dt.datetime) -> CanaryRoute:
        """Return CANDIDATE only for a verified, assigned, budgeted C01 intent."""
        at = parse_utc(now)
        baseline = CanaryRoute(self.config.canary_id, intent_id, "BASELINE", None,
                               "C01_NOT_ACTIVE", iso_utc(at))
        if (self.state not in {"CANARY", "PROMOTED"} or self.ledger is None or self.adapter is None
                or not self._monitor_healthy()):
            if self.state in {"CANARY", "PROMOTED"}:
                self.interrupt(now=at, reason="MONITOR_UNAVAILABLE")
            return baseline
        mandate = self._mandate(at)
        if mandate is None or not self._mandate_reports_match(mandate):
            self.interrupt(now=at, reason="MANDATE_UNAVAILABLE_OR_EXPIRED")
            return CanaryRoute(self.config.canary_id, intent_id, "BASELINE", None,
                               "MANDATE_UNAVAILABLE", iso_utc(at))
        self._verified_mandate = mandate
        selection = self.adapter.read_selection()
        if (not isinstance(selection, dict) or selection.get("variant") != "candidate"
                or selection.get("canary_id") != self.config.canary_id
                or selection.get("sha256") != self.config.candidate_sha256):
            self.interrupt(now=at, reason="CANDIDATE_SELECTION_READBACK_MISMATCH")
            return CanaryRoute(self.config.canary_id, intent_id, "BASELINE", None,
                               "SELECTION_READBACK_FAILED", iso_utc(at))
        record = self.ledger.get(self.config.canary_id)
        started = record.get("started_at")
        if (self.state == "CANARY" and started
                and (at - parse_utc(started)).total_seconds() >= self.config.analysis_plan.maximum_days * 86_400):
            self.ledger.set_state(self.config.canary_id, "INSUFFICIENT_EVIDENCE", at=at,
                                  details={"terminal_reason": "MAXIMUM_OBSERVATION_DAYS_REACHED"})
            self.rollback(now=at, reason="MAXIMUM_OBSERVATION_DAYS_REACHED",
                          final_state="INSUFFICIENT_EVIDENCE")
            return CanaryRoute(self.config.canary_id, intent_id, "BASELINE", None,
                               "MAXIMUM_OBSERVATION_DAYS_REACHED", iso_utc(at))
        if self.state == "PROMOTED":
            return CanaryRoute(self.config.canary_id, intent_id, "CANDIDATE",
                               "PROMOTED:" + intent_id, "PROMOTED_SELECTION", iso_utc(at))
        if not assigned_to_candidate(intent_id):
            return CanaryRoute(self.config.canary_id, intent_id, "BASELINE", None,
                               "DETERMINISTIC_CONTROL", iso_utc(at))
        reservation = self.ledger.reserve(self.config, intent_id, at)
        if reservation is None:
            return CanaryRoute(self.config.canary_id, intent_id, "BASELINE", None,
                               "CANDIDATE_BUDGET_EXHAUSTED", iso_utc(at))
        token, repeat = reservation
        return CanaryRoute(self.config.canary_id, intent_id, "CANDIDATE", token,
                           "REPEAT_ASSIGNMENT" if repeat else "DETERMINISTIC_CANDIDATE",
                           iso_utc(at), repeat=repeat)

    def evaluate_candidate(self, route: CanaryRoute, *, context: Any, cache: Any,
                           baseline_callable: Callable[[], dict[str, Any]],
                           context_metrics: Mapping[str, Any],
                           common_metrics: Mapping[str, Any],
                           measure: Callable[[str, Callable[[], Any]], tuple[Any, Mapping[str, Any]]],
                           now: dt.datetime
                           ) -> tuple[Any, Any, dict[str, Any], dict[str, Any], CandidateExecutionReceipt]:
        """Run both paired arms and mint proof bound to results and metrics."""
        if (route.canary_id != self.config.canary_id or route.variant != "CANDIDATE"
                or route.repeat or not route.token or self.ledger is None):
            raise CanaryError("FRESH_CANDIDATE_ROUTE_REQUIRED")
        at = parse_utc(now)
        if context is None or not self._monitor_healthy() or self._mandate(at) is None:
            raise CanaryError("CANDIDATE_PRECONDITION_MISSING")
        actual_hash = loaded_readiness_cache_sha256()
        if actual_hash != self.config.candidate_sha256:
            raise CanaryError("LOADED_CANDIDATE_HASH_MISMATCH")
        from .readiness_cache import evaluate_with_readiness_cache
        baseline_result, baseline_metrics = measure("baseline", baseline_callable)
        if not isinstance(baseline_metrics, Mapping):
            raise CanaryError("BASELINE_MEASUREMENT_MISSING")
        baseline_metrics = dict(baseline_metrics)
        # Timestamp the actual candidate invocation start. A reservation that
        # crossed midnight is rejected before candidate code runs.
        candidate_at = dt.datetime.now(dt.timezone.utc)
        reservation = self.ledger.reservation(self.config.canary_id, route.token)
        if (not isinstance(reservation, dict)
                or str(reservation.get("reserved_at", ""))[:10] != candidate_at.date().isoformat()):
            raise CanaryError("RESERVATION_DAY_CROSSED")
        candidate_error: str | None = None

        def invoke_candidate() -> Any:
            nonlocal candidate_error
            try:
                return evaluate_with_readiness_cache(
                    baseline_callable, context, cache, enabled=True)
            except Exception as exc:
                # An invoked candidate error is still an actual exposure. Mint
                # a receipt and record it before failing closed to baseline.
                candidate_error = type(exc).__name__
                return {"policy": "C01_CANDIDATE_ERROR", "eligible": False,
                        "reasons": ["CANDIDATE_EVALUATION_ERROR"]}

        result, candidate_metrics = measure("candidate", invoke_candidate)
        if not isinstance(candidate_metrics, Mapping):
            raise CanaryError("CANDIDATE_MEASUREMENT_MISSING")
        candidate_metrics = dict(candidate_metrics)
        if candidate_error is not None:
            candidate_metrics["error"] = True
            candidate_metrics["error_type"] = candidate_error
        for key in ("read_calls", "bytes_read", "elapsed_ms"):
            if _metric_number(baseline_metrics, key) < 0 or _metric_number(candidate_metrics, key) < 0:
                raise CanaryError("MEASUREMENT_METRIC_NEGATIVE:" + key)
        for target, source in (("read_calls", "read_calls"),
                               ("bytes_read", "bytes_read"),
                               ("elapsed_ms", "elapsed_ms")):
            common = _metric_number(common_metrics, source)
            baseline_metrics[target] += common
            candidate_metrics[target] += common
        candidate_metrics["read_calls"] += _metric_number(context_metrics, "context_read_calls")
        candidate_metrics["bytes_read"] += _metric_number(context_metrics, "context_bytes_read")
        candidate_metrics["elapsed_ms"] += _metric_number(context_metrics, "context_elapsed_ms")
        proof = CandidateExecutionReceipt(
            canary_id=self.config.canary_id,
            intent_id=route.intent_id,
            reservation_token=route.token,
            candidate_sha256=actual_hash,
            readiness_context_sha256=context.key,
            executed_at=iso_utc(candidate_at),
            baseline_result_sha256=digest_json(baseline_result),
            result_sha256=digest_json(result),
            baseline_metrics_sha256=digest_json(baseline_metrics),
            candidate_metrics_sha256=digest_json(candidate_metrics),
            repeat=False,
            _runtime_nonce=self._runtime_nonce,
        )
        return baseline_result, result, baseline_metrics, candidate_metrics, proof

    def record_pair(self, route: CanaryRoute, *, now: dt.datetime,
                    stratum: str, cluster_id: str,
                    baseline_result: Any, candidate_result: Any,
                    baseline_metrics: Mapping[str, Any], candidate_metrics: Mapping[str, Any],
                    candidate_receipt: CandidateExecutionReceipt) -> dict[str, Any]:
        """Record one completed paired candidate unit; divergences fail closed immediately."""
        at = parse_utc(now)
        if (route.canary_id != self.config.canary_id or route.variant != "CANDIDATE"
                or not route.token or self.ledger is None):
            raise CanaryError("CANDIDATE_ROUTE_REQUIRED")
        if (not isinstance(candidate_receipt, CandidateExecutionReceipt)
                or candidate_receipt._runtime_nonce is not self._runtime_nonce
                or candidate_receipt.canary_id != self.config.canary_id
                or candidate_receipt.intent_id != route.intent_id
                or candidate_receipt.reservation_token != route.token
                or candidate_receipt.executed_at != iso_utc(at)
                or candidate_receipt.candidate_sha256 != self.config.candidate_sha256
                or candidate_receipt.readiness_context_sha256 == ""
                or candidate_receipt.baseline_result_sha256 != digest_json(baseline_result)
                or candidate_receipt.result_sha256 != digest_json(candidate_result)
                or candidate_receipt.baseline_metrics_sha256 != digest_json(dict(baseline_metrics))
                or candidate_receipt.candidate_metrics_sha256 != digest_json(dict(candidate_metrics))):
            self.ledger.cancel_reservation(self.config.canary_id, route.token)
            self.interrupt(now=at, reason="CANDIDATE_EXECUTION_PROOF_INVALID")
            return {"recorded": False, "state": self.state,
                    "reason": "CANDIDATE_EXECUTION_PROOF_INVALID", "result": baseline_result}
        try:
            stored = self.ledger.record(
                self.config, candidate_receipt, at=at, stratum=stratum, cluster_id=cluster_id,
                baseline_result=baseline_result, candidate_result=candidate_result,
                baseline_metrics=baseline_metrics, candidate_metrics=candidate_metrics,
            )
        except Exception:
            self.ledger.cancel_reservation(self.config.canary_id, route.token)
            self.interrupt(now=at, reason="OBSERVATION_LEDGER_FAILURE")
            return {"recorded": False, "state": self.state, "result": baseline_result}
        # Persist a proven invocation before reacting to drift or monitor loss;
        # otherwise actual candidate executions would disappear from the caps
        # and experiment ledger.
        if not self._monitor_healthy() or self._mandate(at) is None:
            self.interrupt(now=at, reason="MONITOR_OR_MANDATE_LOST")
            return {"recorded": stored.get("recorded", False), "state": self.state,
                    "reason": "MONITOR_OR_MANDATE_LOST", "result": baseline_result}
        if not _readiness_results_equal(baseline_result, candidate_result):
            self.interrupt(now=at, reason="READINESS_DECISION_DIVERGENCE")
            return {"recorded": stored.get("recorded", False), "state": self.state,
                    "reason": "READINESS_DECISION_DIVERGENCE", "result": baseline_result}
        if candidate_metrics.get("error") is True or baseline_metrics.get("error") is True:
            self.interrupt(now=at, reason="CANDIDATE_EVALUATION_ERROR")
            return {"recorded": stored.get("recorded", False), "state": self.state,
                    "reason": "CANDIDATE_EVALUATION_ERROR", "result": baseline_result}
        if candidate_metrics.get("critical_violation") is True:
            self.interrupt(now=at, reason="CRITICAL_VIOLATION")
            return {"recorded": stored.get("recorded", False), "state": self.state,
                    "reason": "CRITICAL_VIOLATION", "result": baseline_result}
        return {**stored, "state": self.state, "result": candidate_result}

    def _promotion_decision(self, now: dt.datetime) -> PromotionDecision:
        at = parse_utc(now)
        if self.ledger is None:
            return PromotionDecision(False, "INSUFFICIENT_EVIDENCE", 0, 0, 0, None, None, None,
                                     ("LEDGER_UNAVAILABLE",))
        record = self.ledger.get(self.config.canary_id)
        observations = [item for item in record.get("observations", [])
                        if isinstance(item, dict) and item.get("candidate_evaluated") is True]
        units = len({str(item.get("intent_id")) for item in observations if item.get("intent_id")})
        clusters = ({str(item.get("intent_id")) for item in observations if item.get("intent_id")}
                    if self.config.analysis_plan.cluster_key == "intent_id" else
                    {str(item.get("cluster_id")) for item in observations if item.get("cluster_id")})
        errors = sum(1 for item in observations if item.get("candidate_metrics", {}).get("error") is True)
        blockers: list[str] = []
        if record.get("state") != "CANARY":
            blockers.append("CANARY_NOT_ACTIVE")
        started = record.get("started_at")
        if not started:
            blockers.append("OBSERVATION_START_MISSING")
            elapsed_days = 0
        else:
            elapsed_days = (at - parse_utc(started)).total_seconds() / 86_400
            if elapsed_days < self.config.analysis_plan.minimum_days:
                blockers.append("MINIMUM_OBSERVATION_DAYS_NOT_MET")
            if elapsed_days >= self.config.analysis_plan.maximum_days:
                blockers.append("MAXIMUM_OBSERVATION_DAYS_REACHED")
        required = self.config.analysis_plan.required_candidate_units
        if units < max(600, required):
            blockers.append("CANDIDATE_SAMPLE_INSUFFICIENT")
        if units > self.config.analysis_plan.max_candidate_units:
            blockers.append("CANDIDATE_SAMPLE_LIMIT_EXCEEDED")
        if len(clusters) < max(600, required):
            blockers.append("INDEPENDENT_CLUSTER_SAMPLE_INSUFFICIENT")
        if not self._monitor_healthy():
            blockers.append("MONITOR_UNAVAILABLE")
        if not self._mandate_reports_match(self._mandate(at)):
            blockers.append("MANDATE_UNAVAILABLE_OR_EXPIRED")
        error_upper = one_sided_binomial_upper(errors, len(clusters), 0.95) if clusters else None
        if errors or error_upper is None or error_upper > self.config.analysis_plan.maximum_error_upper:
            blockers.append("ERROR_BOUND_NOT_MET")
        read_upper, p95_ratio, performance_blockers = _paired_performance(observations, self.config.analysis_plan)
        blockers.extend(performance_blockers)
        if read_upper is None or read_upper > self.config.analysis_plan.target_read_ratio_upper:
            blockers.append("READ_CALL_RATIO_UPPER_BOUND_NOT_MET")
        if p95_ratio is None or p95_ratio > self.config.analysis_plan.target_p95_latency_ratio:
            blockers.append("P95_LATENCY_RATIO_NOT_MET")
        # Require every frozen stratum and count only observed candidate units.
        present = {item.get("stratum") for item in observations}
        if present != LIVE_PERFORMANCE_STRATA:
            blockers.append("FROZEN_STRATA_COVERAGE_INCOMPLETE")
        if units == 0:
            blockers.append("NO_CANDIDATE_UNITS_OBSERVED")
        collection_complete = (elapsed_days >= self.config.analysis_plan.minimum_days
                               and units >= max(600, required))
        observation_expired = (elapsed_days >= self.config.analysis_plan.maximum_days
                               or units >= self.config.analysis_plan.max_candidate_units)
        state = ("PROMOTION_READY" if not blockers else
                 "CANARY_COLLECTING" if not collection_complete and not observation_expired else
                 "INSUFFICIENT_EVIDENCE")
        return PromotionDecision(
            promotable=not blockers,
            state=state,
            candidate_units=units,
            independent_units=len(clusters),
            errors=errors,
            error_upper_95=error_upper,
            read_ratio_upper_95=read_upper,
            p95_latency_ratio=p95_ratio,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    def promotion_decision(self, *, now: dt.datetime) -> PromotionDecision:
        decision = self._promotion_decision(now)
        if self.ledger is not None and self.state == "CANARY":
            try:
                self.ledger.set_state(self.config.canary_id, self.state,
                                      at=parse_utc(now), details={"last_gate": asdict(decision)})
            except Exception:
                return PromotionDecision(False, "INSUFFICIENT_EVIDENCE", decision.candidate_units,
                                         decision.independent_units, decision.errors,
                                         decision.error_upper_95, decision.read_ratio_upper_95,
                                         decision.p95_latency_ratio,
                                         tuple(dict.fromkeys(decision.blockers + ("LEDGER_FAILURE",))))
        return decision

    def promote(self, *, now: dt.datetime) -> dict[str, Any]:
        at = parse_utc(now)
        decision = self.promotion_decision(now=at)
        if not decision.promotable or self.adapter is None or self.ledger is None:
            if self.ledger is not None and self.state == "CANARY":
                if decision.state == "INSUFFICIENT_EVIDENCE":
                    terminal_state = ("REJECTED" if decision.candidate_units >=
                                      max(600, self.config.analysis_plan.required_candidate_units)
                                      and decision.independent_units >=
                                      max(600, self.config.analysis_plan.required_candidate_units)
                                      and "MAXIMUM_OBSERVATION_DAYS_REACHED" not in decision.blockers
                                      else "INSUFFICIENT_EVIDENCE")
                    self.ledger.set_state(self.config.canary_id, terminal_state, at=at,
                                          details={"last_gate": asdict(decision)})
                    self.rollback(now=at, reason="C01_PROMOTION_GATE_FAILED",
                                  final_state=terminal_state)
                else:
                    self.ledger.set_state(self.config.canary_id, "CANARY", at=at,
                                          details={"last_gate": asdict(decision)})
            return {"promoted": False, "decision": asdict(decision), "state": self.state}
        if self._mandate(at) is None or not self._monitor_healthy():
            self.interrupt(now=at, reason="PROMOTION_PRECONDITION_FAILED")
            return {"promoted": False, "state": self.state, "reason": "PROMOTION_PRECONDITION_FAILED"}
        try:
            current = self.adapter.read_selection()
            if (not isinstance(current, dict) or current.get("variant") != "candidate"
                    or current.get("canary_id") != self.config.canary_id
                    or current.get("sha256") != self.config.candidate_sha256):
                raise ReadbackError("LOADED_CANDIDATE_HASH_MISMATCH")
            if self._mandate(at) is None or not self._monitor_healthy():
                raise CanaryError("PROMOTION_MONITOR_OR_MANDATE_LOST")
            receipt = self.ledger.get(self.config.canary_id).get("actuator_receipt")
            if not isinstance(receipt, dict) or receipt.get("readback_sha256") != self.config.candidate_sha256:
                raise ReadbackError("ACTUATOR_RECEIPT_UNAVAILABLE")
            self.ledger.set_state(self.config.canary_id, "PROMOTED", at=at,
                                  details={"promotion_gate": asdict(decision),
                                           "loaded_candidate_sha256": receipt["readback_sha256"]})
            return {"promoted": True, "state": self.state, "receipt": receipt,
                    "decision": asdict(decision)}
        except Exception as exc:
            self.interrupt(now=at, reason="PROMOTION_FAILED:" + type(exc).__name__)
            return {"promoted": False, "state": self.state,
                    "reason": type(exc).__name__}

    def rollback(self, *, now: dt.datetime, reason: str,
                 final_state: str = "ROLLED_BACK") -> dict[str, Any]:
        at = parse_utc(now)
        if self.ledger is None:
            return {"rolled_back": False, "state": "PROPOSED", "reason": "LEDGER_UNAVAILABLE"}
        record = self.ledger.get(self.config.canary_id)
        receipt_value = record.get("actuator_receipt")
        if self.adapter is None or not isinstance(receipt_value, dict):
            self.ledger.set_state(self.config.canary_id, final_state, at=at,
                                  details={"rollback_reason": reason, "actuator": "NOT_PROMOTED"})
            return {"rolled_back": True, "state": self.state, "reason": reason,
                    "actuator": "NOT_PROMOTED"}
        receipt = SelectionReceipt(**receipt_value)
        try:
            current = self.adapter.read_selection()
            if current == receipt.before_selection:
                # A prior fail-closed Writer invocation may already have
                # restored the exact baseline pointer. Make explicit rollback
                # requests idempotent without attempting to undo it twice.
                readback = {
                    "adapter_id": ADAPTER_ID,
                    "selection": current,
                    "document_sha256": self.adapter.document_sha256(),
                    "readback": "PASS",
                    "occurred_at": iso_utc(at),
                }
                self.ledger.set_state(self.config.canary_id, final_state, at=at,
                                      details={"rollback_reason": reason,
                                               "rollback_readback": readback})
                return {"rolled_back": True, "state": self.state,
                        "readback": readback}
            readback = self.adapter.rollback(receipt, at=at)
            self.ledger.set_state(self.config.canary_id, final_state, at=at,
                                  details={"rollback_reason": reason, "rollback_readback": readback})
            return {"rolled_back": True, "state": self.state, "readback": readback}
        except Exception as exc:
            self.ledger.set_state(self.config.canary_id, "INTERRUPTED", at=at,
                                  details={"rollback_reason": reason,
                                           "rollback_failure": type(exc).__name__})
            return {"rolled_back": False, "state": self.state,
                    "reason": "ROLLBACK_READBACK_FAILED"}

    def interrupt(self, *, now: dt.datetime, reason: str) -> dict[str, Any]:
        if self.ledger is None:
            return {"state": "INTERRUPTED", "reason": reason}
        current = self.state
        if current in {"CANARY", "PROMOTED"}:
            rollback = self.rollback(now=now, reason=reason)
            if not rollback.get("rolled_back"):
                self.ledger.set_state(self.config.canary_id, "INTERRUPTED", at=parse_utc(now),
                                      details={"interrupt_reason": reason})
            return {**rollback, "reason": reason}
        return {"state": current, "reason": reason}

    def public_status(self) -> dict[str, Any]:
        """Sanitized status: no intent, test, entity, or private scope identifiers."""
        record = self.ledger.get(self.config.canary_id) if self.ledger is not None else {}
        observations = [item for item in record.get("observations", [])
                        if isinstance(item, dict) and item.get("candidate_evaluated") is True]
        return {
            "contract": CANARY_CONTRACT,
            "canary_id": self.config.canary_id,
            "adapter_id": ADAPTER_ID,
            "state": self.state,
            "candidate_units": len({item.get("intent_id") for item in observations}),
            "candidate_units_today": sum(1 for item in observations
                                         if str(item.get("occurred_at", ""))[:10] ==
                                         dt.datetime.now(dt.timezone.utc).date().isoformat()),
            "max_candidate_units_per_day": 100,
            "max_candidate_units_total": 2_800,
            "minimum_candidate_units": 600,
            "minimum_days": 7,
            "maximum_days": 28,
            "mandate_verified": bool(self._verified_mandate),
            "monitor_healthy": self._monitor_healthy(),
            "promotion_gate": record.get("last_gate"),
        }


def default_off_status() -> dict[str, Any]:
    """Status used when no trusted mandate or runtime monitor is configured."""
    return {
        "contract": CANARY_CONTRACT,
        "canary_id": "C01-readiness-cache",
        "adapter_id": ADAPTER_ID,
        "state": "INSUFFICIENT_EVIDENCE",
        "enabled": False,
        "candidate_units": 0,
        "reason": "VERIFIED_MANDATE_MONITOR_AND_FROZEN_BASELINE_PLAN_REQUIRED",
        "max_candidate_units_per_day": 100,
        "max_candidate_units_total": 2_800,
        "minimum_candidate_units": 600,
        "minimum_days": 7,
        "maximum_days": 28,
    }


_WRITER_ACTION_FIELDS: dict[str, frozenset[str]] = {
    "INSTALL_CONFIG": frozenset({"config"}),
    "START_SHADOW": frozenset({"offline_corpus_report"}),
    "ACTIVATE_CANARY": frozenset({"shadow_report"}),
    "PROMOTE": frozenset(),
    "ROLLBACK": frozenset(),
    "INTERRUPT": frozenset(),
}
_CANARY_ID = "C01-readiness-cache"


def _request_result(action: str, state: str, *, accepted: bool,
                    issue: str | None = None, **safe_fields: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "accepted": accepted,
        "nexo_operation": "OPERATIONAL_CANARY",
        "action": action,
        "state": state,
    }
    if issue:
        result["issue"] = {"code": issue}
    result.update(safe_fields)
    return result


def _trusted_registry_verifier(environment: Mapping[str, str]) -> RegistryMandateVerifier | None:
    """Build a verifier only from trusted process configuration, never request data."""
    registry_path = environment.get("NEXO_C01_APPROVAL_REGISTRY_PATH")
    registry_hash = environment.get("NEXO_C01_APPROVAL_REGISTRY_SHA256")
    approval_ref = environment.get("NEXO_C01_APPROVAL_REF")
    approved_at = environment.get("NEXO_C01_APPROVED_AT")
    if not all((registry_path, registry_hash, approval_ref, approved_at)):
        return None
    try:
        return RegistryMandateVerifier(
            Path(str(registry_path)),
            expected_registry_sha256=str(registry_hash),
            expected_approval_ref=str(approval_ref),
            expected_approved_at=str(approved_at),
        )
    except (TypeError, ValueError, OSError):
        return None


def _baseline_matches(root: Path, config: CanaryConfig) -> bool:
    try:
        from .readiness_cache import _validator_bundle_hash
        from .scientific_integrity import readiness

        return _validator_bundle_hash(readiness, Path(root)) == config.baseline_sha256
    except Exception:
        return False


def apply_writer_canary_request(
    root: Path,
    request: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    action = str(request.get("action") or "") if isinstance(request, Mapping) else ""
    try:
        return _apply_writer_canary_request_impl(root, request, environment=environment)
    except Exception:
        # The Writer converts any rejected operation into a materialized-root
        # rollback. Do not leak paths, registry details, or private Tower data.
        state = "OFF"
        try:
            state = str(TowerCanaryStore(Path(root)).get(_CANARY_ID).get("state") or "OFF")
        except Exception:
            pass
        return _request_result(action, state, accepted=False, issue="C01_REQUEST_FAILED")


def _apply_writer_canary_request_impl(
    root: Path,
    request: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Apply one normalized C01 request to the Writer's materialized Tower.

    This function never publishes or writes a second state store. The normal
    Writer packs, CAS-writes, and reads back the private Tower document after
    this mutation. An INSTALL_CONFIG request only installs the frozen proposal
    and corrected-baseline pointer; live routing requires the separately pinned
    trusted registry, fresh Tower monitor, and evidence gates.
    """
    env = dict(os.environ if environment is None else environment)
    if not isinstance(request, Mapping):
        return _request_result("", "OFF", accepted=False, issue="C01_REQUEST_INVALID")
    action = request.get("action")
    if request.get("nexo_operation") != "OPERATIONAL_CANARY" or action not in _WRITER_ACTION_FIELDS:
        return _request_result(str(action or ""), "OFF", accepted=False, issue="C01_ACTION_INVALID")
    expected_keys = {"nexo_operation", "action"} | set(_WRITER_ACTION_FIELDS[str(action)])
    if set(request) != expected_keys:
        return _request_result(str(action), "OFF", accepted=False, issue="C01_REQUEST_FIELDS_INVALID")

    action = str(action)
    store = TowerCanaryStore(Path(root))
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)

    if action == "INSTALL_CONFIG":
        raw_config = request.get("config")
        if not isinstance(raw_config, Mapping):
            return _request_result(action, "OFF", accepted=False, issue="C01_CONFIG_INVALID")
        try:
            config = CanaryConfig.from_mapping(raw_config)
            if (raw_config.get("contract") != CANARY_CONTRACT
                    or config.canary_id != _CANARY_ID
                    or canonical_json(raw_config) != canonical_json(config.proposal_payload())):
                return _request_result(action, "OFF", accepted=False, issue="C01_CONFIG_SCOPE_INVALID")
            if not config.analysis_plan.can_start:
                return _request_result(action, "OFF", accepted=False, issue="C01_FROZEN_PLAN_EXCEEDS_BUDGET")
            if parse_utc(config.analysis_plan.frozen_at) >= now:
                return _request_result(action, "OFF", accepted=False, issue="C01_FROZEN_PLAN_NOT_PREOBSERVATION")
            if loaded_readiness_cache_sha256() != config.candidate_sha256:
                return _request_result(action, "OFF", accepted=False, issue="C01_CANDIDATE_CODE_HASH_MISMATCH")
            if not _baseline_matches(Path(root), config):
                return _request_result(action, "OFF", accepted=False, issue="C01_BASELINE_BUNDLE_HASH_MISMATCH")
            current = store.read_selection()
            record = store.get(config.canary_id)
            if record:
                if record.get("proposal_sha256") != config.proposal_sha256:
                    return _request_result(action, str(record.get("state") or "OFF"), accepted=False,
                                           issue="C01_CONFIG_CONFLICT")
                state = str(record.get("state") or "PROPOSED")
                if isinstance(current, dict) and current.get("variant") == "candidate":
                    pointer_ok = (state in {"CANARY", "PROMOTED"}
                                  and current.get("canary_id") == config.canary_id
                                  and current.get("sha256") == config.candidate_sha256)
                    if not pointer_ok:
                        return _request_result(action, state, accepted=False,
                                               issue="C01_SELECTION_STATE_CONFLICT")
                    return _request_result(action, state, accepted=True,
                                           installed=True, activated=True, enabled=False,
                                           selection_readback="PASS")
            baseline_pointer = {
                "variant": "baseline", "version": config.baseline_version,
                "sha256": config.baseline_sha256,
            }
            if current is not None and current != baseline_pointer:
                return _request_result(action, str(record.get("state") or "OFF"), accepted=False,
                                       issue="C01_BASELINE_SELECTION_CONFLICT")
            store.initialize(config)
            readback = store.install_baseline_selection(config)
            if readback.get("readback") != "PASS":
                raise ReadbackError("C01_BASELINE_SELECTION_READBACK_FAILED")
            return _request_result(action, store.get(config.canary_id).get("state", "PROPOSED"),
                                   accepted=True, installed=True, activated=False, enabled=False,
                                   selection_readback="PASS")
        except (CanaryError, TypeError, ValueError, OSError):
            return _request_result(action, "OFF", accepted=False, issue="C01_CONFIG_INSTALL_FAILED")

    config = store.config(_CANARY_ID)
    if config is None:
        return _request_result(action, "OFF", accepted=False, issue="C01_CONFIG_NOT_INSTALLED")
    state = str(store.get(config.canary_id).get("state") or "PROPOSED")
    verifier = _trusted_registry_verifier(env)
    monitor = lambda: _tower_monitor_healthy(Path(root), config)
    controller = OperationalCanary(
        config,
        verifier=verifier,
        ledger=store,
        adapter=store,
        monitor=monitor,
        baseline_verifier=lambda candidate_config: _baseline_matches(Path(root), candidate_config),
    )

    if action in {"START_SHADOW", "ACTIVATE_CANARY"}:
        if verifier is None or controller._mandate(now) is None:
            return _request_result(action, state, accepted=False, issue="C01_TRUSTED_MANDATE_UNAVAILABLE")
        monitor_status = refresh_tower_monitor(Path(root), env, now=now)
        if monitor_status.get("enabled") is not True:
            return _request_result(action, str(monitor_status.get("state") or state),
                                   accepted=False, issue="C01_MONITOR_UNAVAILABLE",
                                   selection_readback=monitor_status.get("selection_readback", "FAIL"))
        if not monitor():
            return _request_result(action, state, accepted=False, issue="C01_MONITOR_UNAVAILABLE")
        if not _baseline_matches(Path(root), config):
            return _request_result(action, state, accepted=False, issue="C01_BASELINE_BUNDLE_HASH_MISMATCH")
        if loaded_readiness_cache_sha256() != config.candidate_sha256:
            return _request_result(action, state, accepted=False, issue="C01_CANDIDATE_CODE_HASH_MISMATCH")
        mandate = controller._mandate(now)
        assert mandate is not None
        if action == "START_SHADOW":
            report = request.get("offline_corpus_report")
            corpus_hash = validate_offline_corpus_report(report, config) if isinstance(report, Mapping) else None
            if corpus_hash is None or corpus_hash != mandate.offline_corpus_sha256:
                return _request_result(action, state, accepted=False, issue="C01_OFFLINE_REPORT_NOT_AUTHORIZED")
            if controller.state == "SHADOW" and store.get(config.canary_id).get("offline_corpus_sha256") == corpus_hash:
                return _request_result(action, "SHADOW", accepted=True, shadow_ready=True)
            if not controller.start(now=now, offline_corpus_report=report):
                return _request_result(action, controller.state, accepted=False,
                                       issue="C01_SHADOW_GATE_FAILED")
            return _request_result(action, controller.state, accepted=True, shadow_ready=True)

        shadow_report = request.get("shadow_report")
        shadow_hash = validate_shadow_report(shadow_report, config) if isinstance(shadow_report, Mapping) else None
        if shadow_hash is None or shadow_hash != mandate.shadow_report_sha256:
            return _request_result(action, state, accepted=False, issue="C01_SHADOW_REPORT_NOT_AUTHORIZED")
        if controller.state == "CANARY":
            status = operational_status(Path(root), environment=env)
            if status.get("activated"):
                return _request_result(action, "CANARY", accepted=True, activated=True,
                                       selection_readback="PASS")
        if not controller.activate_canary(now=now, shadow_report=shadow_report):
            return _request_result(action, controller.state, accepted=False,
                                   issue="C01_ACTIVATION_READBACK_OR_GATE_FAILED")
        monitor_status = refresh_tower_monitor(Path(root), env)
        if monitor_status.get("enabled") is not True:
            return _request_result(action, str(monitor_status.get("state") or controller.state),
                                   accepted=False, issue="C01_ACTIVATION_MONITOR_READBACK_FAILED",
                                   selection_readback=monitor_status.get("selection_readback", "FAIL"))
        status = operational_status(Path(root), environment=env)
        if not status.get("activated"):
            return _request_result(action, controller.state, accepted=False,
                                   issue="C01_ACTIVATION_READBACK_FAILED")
        return _request_result(action, controller.state, accepted=True, activated=True,
                               enabled=bool(status.get("enabled")), selection_readback="PASS")

    if action == "PROMOTE":
        outcome = controller.promote(now=now)
        # The controller persists the fixed decision, including a nonterminal
        # collecting result. Treat a failed promotion gate as an accepted
        # evaluation so Writer retains that evidence in the canonical Tower.
        return _request_result(
            action, controller.state, accepted=True,
            promoted=bool(outcome.get("promoted")),
            reason_code=None if outcome.get("promoted") else "C01_PROMOTION_GATE_NOT_MET",
        )

    fixed_reason = "WRITER_ROLLBACK_REQUEST" if action == "ROLLBACK" else "WRITER_INTERRUPT_REQUEST"
    if action == "ROLLBACK":
        outcome = controller.rollback(now=now, reason=fixed_reason)
    elif controller.state in {"CANARY", "PROMOTED"}:
        # Keep the state explicitly fail-closed after compensating the adapter.
        outcome = controller.rollback(now=now, reason=fixed_reason, final_state="INTERRUPTED")
    else:
        store.set_state(config.canary_id, "INTERRUPTED", at=now,
                        details={"interrupt_reason": fixed_reason})
        outcome = {"rolled_back": True, "state": "INTERRUPTED", "actuator": "NOT_PROMOTED"}
    return _request_result(
        action, controller.state, accepted=True,
        rolled_back=bool(outcome.get("rolled_back")),
        selection_readback=("PASS" if outcome.get("rolled_back") else "FAIL"),
        reason_code=None if outcome.get("rolled_back") else "C01_ROLLBACK_READBACK_FAILED",
    )


def operational_status(
    root: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return a read-only, sanitized status for C01's actual Tower selection.

    Approval paths, registry hashes, proposal contents, intents, and private
    observations are intentionally omitted. `enabled` is true only while the
    configured candidate is actually selected and every runtime proof is fresh.
    """
    env = dict(os.environ if environment is None else environment)
    status: dict[str, Any] = {
        "contract": CANARY_CONTRACT,
        "canary_id": _CANARY_ID,
        "adapter_id": ADAPTER_ID,
        "code_support": True,
        "installed": False,
        "activated": False,
        "enabled": False,
        "effective_state": "OFF",
        "state": "OFF",
        "selection_variant": "missing",
        "selection_readback": "UNAVAILABLE",
        "authorization_verified": False,
        "monitor_healthy": False,
        "reason": "CONFIG_NOT_INSTALLED",
    }
    try:
        store = TowerCanaryStore(Path(root))
        config = store.config(_CANARY_ID)
        if config is None:
            return status
        record = store.get(config.canary_id)
        selection = store.read_selection()
        state = str(record.get("state") or "PROPOSED")
        status["state"] = state
        status["installed"] = True
        if isinstance(selection, dict):
            selection_variant = str(selection.get("variant") or "unknown").lower()
            status["selection_variant"] = selection_variant if selection_variant in {"baseline", "candidate"} else "unknown"
        elif selection is None:
            status["selection_variant"] = "missing"
        else:
            status["selection_variant"] = "unknown"

        baseline_selection = (isinstance(selection, dict)
                              and selection.get("variant") == "baseline"
                              and selection.get("version") == config.baseline_version
                              and selection.get("sha256") == config.baseline_sha256)
        candidate_selection = (isinstance(selection, dict)
                               and selection.get("variant") == "candidate"
                               and selection.get("version") == config.candidate_version
                               and selection.get("sha256") == config.candidate_sha256
                               and selection.get("canary_id") == config.canary_id)
        receipt_value = record.get("actuator_receipt")
        candidate_receipt = False
        if isinstance(receipt_value, dict):
            try:
                receipt = SelectionReceipt(**receipt_value)
                candidate_receipt = (
                    receipt.adapter_id == ADAPTER_ID
                    and receipt.canary_id == config.canary_id
                    and receipt.after_selection == selection
                    and receipt.after_selection_sha256 == digest_json(selection)
                    and receipt.readback_sha256 == config.candidate_sha256
                )
            except (TypeError, ValueError):
                candidate_receipt = False
        active_state = state in {"CANARY", "PROMOTED"}
        if baseline_selection and not active_state:
            status["selection_readback"] = "PASS"
        elif candidate_selection and candidate_receipt and active_state:
            status["selection_readback"] = "PASS"
            status["activated"] = True
        else:
            status["selection_readback"] = "FAIL"

        loaded_candidate_matches = loaded_readiness_cache_sha256() == config.candidate_sha256
        status["code_support"] = loaded_candidate_matches
        mandate = _trusted_registry_verifier(env)
        verified = mandate is not None and mandate.verify(config, dt.datetime.now(dt.timezone.utc)) is not None
        monitor_healthy = _tower_monitor_healthy(Path(root), config)
        baseline_matches = _baseline_matches(Path(root), config)
        status["authorization_verified"] = verified
        status["monitor_healthy"] = monitor_healthy
        enabled = bool(status["activated"] and active_state and verified and monitor_healthy
                       and baseline_matches and loaded_candidate_matches)
        status["enabled"] = enabled
        if enabled:
            status["effective_state"] = "ENABLED"
            status["reason"] = None
        elif status["selection_readback"] != "PASS":
            status["reason"] = "SELECTION_READBACK_FAILED"
        elif not verified:
            status["reason"] = "TRUSTED_MANDATE_UNAVAILABLE"
        elif not monitor_healthy:
            status["reason"] = "MONITOR_UNAVAILABLE"
        elif not baseline_matches:
            status["reason"] = "BASELINE_BUNDLE_HASH_MISMATCH"
        elif not loaded_candidate_matches:
            status["reason"] = "CANDIDATE_CODE_HASH_MISMATCH"
        elif state == "SHADOW":
            status["reason"] = "SHADOW_ONLY"
        elif not status["activated"]:
            status["reason"] = "C01_NOT_ACTIVE"
        else:
            status["reason"] = "C01_OFF"
        return status
    except Exception:
        # Keep diagnostics stable and never return private Tower content.
        status["reason"] = "TOWER_CANARY_STATE_UNREADABLE"
        status["selection_readback"] = "FAIL"
        return status


def make_readiness_evaluator(
    *,
    runtime_factory: Callable[[Path], OperationalCanary | None],
    metadata_provider: Callable[[Path, Mapping[str, Any]], Mapping[str, Any] | None],
    context_provider: Callable[[Path, Mapping[str, Any], Mapping[str, Any]], tuple[Any, Mapping[str, Any]]],
    measure: Callable[[str, Callable[[], Any]], tuple[Any, Mapping[str, Any]]],
    cache: Any = None,
) -> Callable[..., dict[str, Any]]:
    """Build the production readiness wrapper; all missing proof runs baseline.

    The returned callable accepts `(root, test, baseline_callable, *,
    ignore_reservation=False)`. Provider outputs are deliberately explicit so
    the Writer can supply the current materialized Tower revision, access
    policy revision, and measured I/O without trusting fields from an agent
    request. `measure` must report real `read_calls`, `bytes_read`, and
    `elapsed_ms` for both variants; incomplete metrics disable candidate use.
    """
    from .readiness_cache import ReadinessCache, ReadinessContextUnavailable

    global _SHARED_READINESS_CACHE
    if cache is None:
        with _SHARED_READINESS_CACHE_LOCK:
            if _SHARED_READINESS_CACHE is None:
                _SHARED_READINESS_CACHE = ReadinessCache()
            cache = _SHARED_READINESS_CACHE

    def baseline_only(baseline: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        return baseline()

    def measured(variant: str, function: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
        value, raw = measure(variant, function)
        if not isinstance(raw, Mapping):
            raise ValueError("MEASUREMENT_METRICS_MISSING")
        metrics = dict(raw)
        for key in ("read_calls", "bytes_read", "elapsed_ms"):
            number = _metric_number(metrics, key)
            if number < 0:
                raise ValueError("MEASUREMENT_METRIC_NEGATIVE:" + key)
        return value, metrics

    def evaluator(root: Path, test: Mapping[str, Any], baseline_callable: Callable[[], dict[str, Any]],
                  *, ignore_reservation: bool = False) -> dict[str, Any]:
        if not callable(baseline_callable):
            raise TypeError("BASELINE_CALLABLE_REQUIRED")
        if ignore_reservation:
            return baseline_only(baseline_callable)
        try:
            def control_path():
                runtime_value = runtime_factory(Path(root))
                if runtime_value is None or runtime_value.state not in {"CANARY", "PROMOTED"}:
                    return runtime_value, None, None
                metadata_value = metadata_provider(Path(root), test)
                if not isinstance(metadata_value, Mapping):
                    return runtime_value, metadata_value, None
                route_value = runtime_value.route(str(metadata_value.get("intent_id") or ""),
                                                  now=parse_utc(metadata_value.get("now")))
                return runtime_value, metadata_value, route_value

            (runtime, metadata, route), controller_metrics = measured("controller", control_path)
            if runtime is None or runtime.state not in {"CANARY", "PROMOTED"}:
                return baseline_only(baseline_callable)
            if not isinstance(metadata, Mapping):
                return baseline_only(baseline_callable)
            required = ("intent_id", "now", "stratum", "cluster_id", "access_scope",
                        "authorization_revision", "manifest_revision", "manifest_sha256",
                        "reservation_sha256")
            if any(not metadata.get(name) for name in required):
                return baseline_only(baseline_callable)
            if metadata.get("stratum") not in LIVE_PERFORMANCE_STRATA:
                return baseline_only(baseline_callable)
            now = parse_utc(metadata["now"])
            if route is None:
                return baseline_only(baseline_callable)
            if route.variant != "CANDIDATE":
                return baseline_only(baseline_callable)

            try:
                context, context_metrics = context_provider(Path(root), test, metadata)
            except Exception:
                if route.token and not route.token.startswith("PROMOTED:"):
                    runtime.ledger.cancel_reservation(runtime.config.canary_id, str(route.token))
                return baseline_only(baseline_callable)
            if context is None or not isinstance(context_metrics, Mapping):
                if route.token and not route.token.startswith("PROMOTED:"):
                    runtime.ledger.cancel_reservation(runtime.config.canary_id, str(route.token))
                return baseline_only(baseline_callable)
            context_metrics = dict(context_metrics)
            metadata_metrics = {
                "read_calls": _metric_number(controller_metrics, "read_calls"),
                "bytes_read": _metric_number(controller_metrics, "bytes_read"),
                "elapsed_ms": _metric_number(controller_metrics, "elapsed_ms"),
            }

            if runtime.state == "PROMOTED":
                # Promotion no longer uses experiment reservations/metrics.
                # The canonical pointer was verified by route(); apply the
                # selected cache directly and never call record_pair().
                from .readiness_cache import evaluate_with_readiness_cache
                try:
                    return evaluate_with_readiness_cache(
                        baseline_callable, context, cache, enabled=True)
                except Exception:
                    return baseline_only(baseline_callable)

            if route.repeat:
                # The same immutable intent/context returns its recorded result
                # without invoking the candidate a second time.
                existing = runtime.ledger.existing_observation(
                    runtime.config.canary_id, route.intent_id, context.key)
                if existing is None:
                    return baseline_only(baseline_callable)
                try:
                    baseline_result = baseline_callable()
                except Exception:
                    return baseline_only(baseline_callable)
                if not _readiness_results_equal(baseline_result, existing.get("candidate_result")):
                    return baseline_result
                return copy.deepcopy(existing["candidate_result"])

            try:
                baseline_result, candidate_result, baseline_metrics, candidate_metrics, candidate_receipt = \
                    runtime.evaluate_candidate(
                        route, context=context, cache=cache,
                        baseline_callable=baseline_callable,
                        context_metrics=context_metrics, common_metrics=metadata_metrics,
                        measure=measure, now=now)
            except Exception:
                runtime.ledger.cancel_reservation(runtime.config.canary_id, str(route.token))
                runtime.interrupt(now=now, reason="CANDIDATE_EVALUATION_OR_MEASUREMENT_FAILED")
                return baseline_only(baseline_callable)

            pair = runtime.record_pair(
                route, now=parse_utc(candidate_receipt.executed_at), stratum=str(metadata["stratum"]),
                cluster_id=str(metadata["cluster_id"]),
                baseline_result=baseline_result, candidate_result=candidate_result,
                baseline_metrics=baseline_metrics, candidate_metrics=candidate_metrics,
                candidate_receipt=candidate_receipt,
            )
            if pair.get("recorded") is not True or pair.get("state") != "CANARY":
                return baseline_result
            return candidate_result
        except Exception:
            # Runtime, provider, instrumentation, and persistence problems
            # never alter canonical readiness behavior.
            return baseline_only(baseline_callable)

    return evaluator


def make_tower_readiness_evaluator(
    *,
    metadata_provider: Callable[[Path, Mapping[str, Any]], Mapping[str, Any] | None] | None = None,
    context_provider: Callable[[Path, Mapping[str, Any], Mapping[str, Any]], tuple[Any, Mapping[str, Any]]] | None = None,
    measure: Callable[[str, Callable[[], Any]], tuple[Any, Mapping[str, Any]]] | None = None,
    monitor_provider: Callable[[Path, CanaryConfig], bool] | None = None,
    cache: Any = None,
    environment: Mapping[str, str] | None = None,
) -> Callable[..., dict[str, Any]]:
    """Production factory reading controller, selection and receipts from Tower.

    Registry pins are deployment/runtime inputs. No field in the Tower proposal
    such as `source="DENER"` can create or authenticate a mandate.
    """
    from .readiness_cache import ReadinessCacheContext, _validator_bundle_hash
    from .scientific_integrity import readiness as baseline_readiness
    from .live_tower import LIVE_TOWER_NAME, read_live_tower_bytes
    from .semantics import is_private, resolve as resolve_semantic

    env = dict(os.environ if environment is None else environment)
    if metadata_provider is None:
        metadata_provider = _tower_readiness_metadata
    if context_provider is None:
        def context_provider(root: Path, test: Mapping[str, Any],
                             metadata: Mapping[str, Any]) -> tuple[Any, Mapping[str, Any]]:
            metrics: dict[str, Any] = {}
            context = ReadinessCacheContext.from_runtime(
                root, test,
                access_scope=str(metadata["access_scope"]),
                authorization_revision=str(metadata["authorization_revision"]),
                manifest_revision=str(metadata["manifest_revision"]),
                manifest_sha256=str(metadata["manifest_sha256"]),
                validator=baseline_readiness,
                validator_version=str(getattr(baseline_readiness, "__name__", "readiness")),
                metrics_out=metrics,
            )
            return context, metrics
    if measure is None:
        measure = _measure_path_reads
    if monitor_provider is None:
        monitor_provider = _tower_monitor_healthy

    def runtime_factory(root: Path) -> OperationalCanary | None:
        store: TowerCanaryStore | None = None
        config: CanaryConfig | None = None
        controller: OperationalCanary | None = None
        now = dt.datetime.now(dt.timezone.utc)
        try:
            store = TowerCanaryStore(root)
            config = store.config("C01-readiness-cache")
            if config is None:
                return None
            record = store.get(config.canary_id)
            state = str(record.get("state") or "PROPOSED")
            if state not in {"CANARY", "PROMOTED"}:
                if (store.read_selection() or {}).get("variant") == "candidate":
                    _rollback_owned_candidate(
                        store, config, at=now, reason="C01_NOT_ACTIVE_SELECTION")
                return None
            if config.candidate_sha256 != loaded_readiness_cache_sha256():
                _rollback_owned_candidate(
                    store, config, at=now, reason="CANDIDATE_CODE_HASH_MISMATCH")
                return None
            registry_path = env.get("NEXO_C01_APPROVAL_REGISTRY_PATH")
            registry_hash = env.get("NEXO_C01_APPROVAL_REGISTRY_SHA256")
            approval_ref = env.get("NEXO_C01_APPROVAL_REF")
            approved_at = env.get("NEXO_C01_APPROVED_AT")
            verifier = None
            if registry_path and registry_hash and approval_ref and approved_at:
                verifier = RegistryMandateVerifier(
                    Path(registry_path), expected_registry_sha256=registry_hash,
                    expected_approval_ref=approval_ref, expected_approved_at=approved_at)

            def baseline_verifier(candidate_config: CanaryConfig) -> bool:
                try:
                    actual = _validator_bundle_hash(baseline_readiness, Path(root))
                    return actual == candidate_config.baseline_sha256
                except Exception:
                    return False

            monitor = None
            if monitor_provider is not None:
                monitor = lambda: monitor_provider(Path(root), config) is True
            controller = OperationalCanary(
                config, verifier=verifier, ledger=store, adapter=store,
                monitor=monitor, baseline_verifier=baseline_verifier)
            mandate = controller._mandate(now)
            if (controller.state not in {"CANARY", "PROMOTED"}
                    or not controller._monitor_healthy()
                    or mandate is None
                    or not controller._mandate_reports_match(mandate)
                    or baseline_verifier(config) is not True):
                controller.interrupt(
                    now=now, reason="RUNTIME_PROOF_UNAVAILABLE")
                return None
            return controller
        except Exception:
            if store is not None and config is not None:
                try:
                    state = str(store.get(config.canary_id).get("state") or "PROPOSED")
                    if state in {"CANARY", "PROMOTED"}:
                        _rollback_owned_candidate(
                            store, config, at=now, reason="RUNTIME_PROOF_ERROR")
                except Exception:
                    pass
            return None

    return make_readiness_evaluator(
        runtime_factory=runtime_factory,
        metadata_provider=metadata_provider,
        context_provider=context_provider,
        measure=measure,
        cache=cache,
    )


_READ_METRIC: contextvars.ContextVar[dict[str, int] | None] = contextvars.ContextVar(
    "nexo_c01_readiness_read_metric", default=None)
_READ_MEASURE_LOCK = threading.RLock()


def _measure_path_reads(variant: str, function: Callable[[], Any]
                        ) -> tuple[Any, dict[str, Any]]:
    """Count Python Path reads and bytes around one real readiness invocation."""
    metric = {"read_calls": 0, "bytes_read": 0}
    original_bytes = Path.read_bytes
    original_text = Path.read_text

    def read_bytes(path: Path) -> bytes:
        value = original_bytes(path)
        active = _READ_METRIC.get()
        if active is not None:
            active["read_calls"] += 1
            active["bytes_read"] += len(value)
        return value

    def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        value = original_text(path, *args, **kwargs)
        active = _READ_METRIC.get()
        if active is not None:
            encoding = kwargs.get("encoding") or (args[0] if args else None) or "utf-8"
            try:
                size = len(value.encode(str(encoding)))
            except (LookupError, UnicodeError):
                size = len(value.encode("utf-8", errors="replace"))
            active["read_calls"] += 1
            active["bytes_read"] += size
        return value

    started = time.perf_counter()
    token = None
    with _READ_MEASURE_LOCK:
        try:
            Path.read_bytes = read_bytes  # type: ignore[method-assign]
            Path.read_text = read_text  # type: ignore[method-assign]
            token = _READ_METRIC.set(metric)
            value = function()
            error = False
        except Exception:
            error = True
            raise
        finally:
            if token is not None:
                _READ_METRIC.reset(token)
            Path.read_bytes = original_bytes  # type: ignore[method-assign]
            Path.read_text = original_text  # type: ignore[method-assign]
    return value, {**metric, "elapsed_ms": (time.perf_counter() - started) * 1_000,
                   "error": error, "variant": variant}


def _tower_readiness_metadata(root: Path, test: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Derive assignment/scope from current canonical Tower content, not request claims."""
    from .live_tower import LIVE_TOWER_NAME, read_live_tower_bytes
    from .semantics import is_private, resolve as resolve_semantic

    started = time.perf_counter()
    reads = 0
    bytes_read = 0
    try:
        root = Path(root)
        manifest_raw = (root / LIVE_TOWER_NAME).read_bytes()
        reads += 1
        bytes_read += len(manifest_raw)
        manifest = read_live_tower_bytes(manifest_raw)
        raw_revision = str(manifest.get("state_fingerprint") or manifest.get("revision") or "")
        manifest_sha = raw_revision.removeprefix("sha256:")
        if not _valid_hash(manifest_sha):
            return None
        control_raw = (root / "CONTROL.json").read_bytes()
        reads += 1
        bytes_read += len(control_raw)
        authorization_revision = sha256(control_raw)
        reservation_path = root / "evolution" / "batteries.json"
        if reservation_path.is_file():
            reservation_raw = reservation_path.read_bytes()
            reads += 1
            bytes_read += len(reservation_raw)
            reservation_sha = sha256(reservation_raw)
        else:
            reservation_sha = sha256(b"MISSING:evolution/batteries.json")
        test_id = str(test.get("id") or "")
        if not test_id:
            return None
        if test.get("private") is True:
            scope = "PRIVATE"
        else:
            resolved = resolve_semantic(dict(test), entity_id=test_id)
            if resolved.get("basis") == "UNMAPPED":
                return None
            scope = "PRIVATE" if is_private(resolved) else "PUBLIC"
        # Stable exposure identity prevents context edits/retries from
        # manufacturing independent sample units. The cache key still hashes
        # the complete live context and invalidates on every change.
        intent_id = "C01:" + sha256(test_id.encode("utf-8"))
        config = TowerCanaryStore(root).config("C01-readiness-cache")
        if config is None:
            return None
        if config.analysis_plan.cluster_key == "cluster_id":
            cluster_id = str(test.get("canary_cluster_id") or "")
            if not cluster_id:
                return None
        else:
            cluster_id = intent_id
        return {
            "intent_id": intent_id,
            "now": dt.datetime.now(dt.timezone.utc),
            "stratum": scope.lower(),
            "cluster_id": cluster_id,
            "access_scope": scope,
            "authorization_revision": authorization_revision,
            "manifest_revision": raw_revision,
            "manifest_sha256": manifest_sha,
            "reservation_sha256": reservation_sha,
            "_metadata_read_calls": reads,
            "_metadata_bytes_read": bytes_read,
            "_metadata_elapsed_ms": (time.perf_counter() - started) * 1_000,
        }
    except Exception:
        return None


def _selection_readback_matches_record(
    store: TowerCanaryStore,
    config: CanaryConfig,
    record: Mapping[str, Any],
    selection: Mapping[str, Any] | None,
) -> bool:
    """Verify the selected pointer against its canonical activation receipt."""
    if not isinstance(selection, Mapping):
        return False
    state = str(record.get("state") or "")
    if state in {"CANARY", "PROMOTED"}:
        if (selection.get("variant") != "candidate"
                or selection.get("version") != config.candidate_version
                or selection.get("sha256") != config.candidate_sha256
                or selection.get("canary_id") != config.canary_id):
            return False
        receipt_value = record.get("actuator_receipt")
        try:
            receipt = SelectionReceipt(**receipt_value) if isinstance(receipt_value, dict) else None
        except (TypeError, ValueError):
            return False
        return bool(
            receipt is not None
            and receipt.adapter_id == ADAPTER_ID
            and receipt.canary_id == config.canary_id
            and receipt.after_selection == dict(selection)
            and receipt.after_selection_sha256 == digest_json(selection)
            and receipt.readback_sha256 == config.candidate_sha256
            and record.get("readback_status") == "PASS"
        )
    if state in {"PROPOSED", "SHADOW"}:
        expected = {"variant": "baseline", "version": config.baseline_version,
                    "sha256": config.baseline_sha256}
        receipt = record.get("baseline_selection_receipt")
        return bool(
            dict(selection) == expected
            and isinstance(receipt, dict)
            and receipt.get("adapter_id") == ADAPTER_ID
            and receipt.get("selection") == expected
            and receipt.get("selection_sha256") == digest_json(expected)
            and receipt.get("readback") == "PASS"
        )
    return False


def _rollback_owned_candidate(
    store: TowerCanaryStore,
    config: CanaryConfig,
    *,
    at: dt.datetime,
    reason: str,
) -> dict[str, Any]:
    """Restore only a still-current C01 pointer, using its scoped receipt."""
    controller = OperationalCanary(
        config, verifier=None, ledger=store, adapter=store, monitor=None,
        baseline_verifier=None,
    )
    record = store.get(config.canary_id)
    if controller.state in {"CANARY", "PROMOTED"}:
        outcome = controller.interrupt(now=at, reason=reason)
        selection_after = store.read_selection()
        if (outcome.get("rolled_back") is True
                and selection_after == (record.get("actuator_receipt") or {}).get("before_selection")):
            return outcome
        # If the active pointer is still the exact C01 candidate but its
        # activation receipt was lost/corrupted, use the separately verified
        # baseline-selection receipt to compensate the interrupted activation.
        selection_receipt_value = record.get("actuator_receipt")
        try:
            parsed_selection_receipt = (
                SelectionReceipt(**selection_receipt_value)
                if isinstance(selection_receipt_value, dict) else None
            )
        except (TypeError, ValueError):
            parsed_selection_receipt = None
        if (parsed_selection_receipt is not None
                and parsed_selection_receipt.after_selection_sha256 != digest_json(selection_after)):
            # A valid receipt that no longer hashes the live pointer signals
            # concurrent selection change. Never compensate over that pointer.
            return outcome

    # Compensate a process interruption between selection and state/readback
    # receipt persistence only when the exact C01 candidate pointer remains.
    try:
        record = store.get(config.canary_id)
        selection = store.read_selection()
        baseline_receipt = record.get("baseline_selection_receipt")
        if not (
            isinstance(selection, dict)
            and selection.get("variant") == "candidate"
            and selection.get("version") == config.candidate_version
            and selection.get("sha256") == config.candidate_sha256
            and selection.get("canary_id") == config.canary_id
            and set(selection) == {"variant", "version", "sha256", "canary_id", "selected_at"}
            and isinstance(baseline_receipt, dict)
            and baseline_receipt.get("readback") == "PASS"
            and baseline_receipt.get("selection") == {
                "variant": "baseline", "version": config.baseline_version,
                "sha256": config.baseline_sha256,
            }
            and baseline_receipt.get("selection_sha256") == digest_json(baseline_receipt["selection"])
        ):
            return {"rolled_back": False, "state": controller.state,
                    "reason": "NO_OWNED_CANDIDATE_POINTER"}
        receipt = SelectionReceipt(
            adapter_id=ADAPTER_ID, canary_id=config.canary_id,
            before_selection=copy.deepcopy(baseline_receipt["selection"]),
            after_selection=copy.deepcopy(selection),
            after_selection_sha256=digest_json(selection),
            readback_sha256=config.candidate_sha256,
            document_sha256=store.document_sha256(),
            selected_at=str(selection.get("selected_at") or iso_utc(at)),
        )
        readback = store.rollback(receipt, at=at)
        store.set_state(config.canary_id, "ROLLED_BACK", at=at,
                        details={"rollback_reason": reason,
                                 "rollback_readback": readback})
        return {"rolled_back": True, "state": "ROLLED_BACK", "readback": readback}
    except Exception as exc:
        try:
            if controller.state in {"CANARY", "PROMOTED", "SHADOW"}:
                store.set_state(config.canary_id, "INTERRUPTED", at=at,
                                details={"rollback_reason": reason,
                                         "rollback_failure": type(exc).__name__})
        except Exception:
            pass
        return {"rolled_back": False, "state": controller.state,
                "reason": "ROLLBACK_READBACK_FAILED"}


def refresh_tower_monitor(
    root: Path,
    environment: Mapping[str, str] | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Refresh the private C01 heartbeat only after live proof/readback checks.

    The normal Writer owns and packs this mutation with the canonical Tower.
    The heartbeat is never accepted from a proposal or public Tower field.
    """
    root = Path(root)
    env = dict(os.environ if environment is None else environment)
    at = parse_utc(now or dt.datetime.now(dt.timezone.utc))
    status: dict[str, Any] = {
        "enabled": False, "heartbeat_refreshed": False,
        "selection_readback": "FAIL", "reason": "CONFIG_NOT_INSTALLED",
        "state": "OFF",
    }
    store: TowerCanaryStore | None = None
    config: CanaryConfig | None = None
    try:
        store = TowerCanaryStore(root)
        config = store.config(_CANARY_ID)
        if config is None:
            return status
        record = store.get(config.canary_id)
        state = str(record.get("state") or "PROPOSED")
        status["state"] = state
        selection = store.read_selection()
        verifier = _trusted_registry_verifier(env)
        mandate = verifier.verify(config, at) if verifier is not None else None
        from .readiness_cache import _validator_bundle_hash
        from .scientific_integrity import readiness

        actual_baseline_sha = _validator_bundle_hash(readiness, root)
        actual_candidate_sha = loaded_readiness_cache_sha256()
        active = state in {"CANARY", "PROMOTED"}
        proof_ok = bool(
            mandate is not None
            and actual_baseline_sha == config.baseline_sha256
            and actual_candidate_sha == config.candidate_sha256
            and _selection_readback_matches_record(store, config, record, selection)
            and (not active or (
                record.get("offline_corpus_sha256") == mandate.offline_corpus_sha256
                and record.get("shadow_report_sha256") == mandate.shadow_report_sha256
            ))
        )
        if not proof_ok:
            status["reason"] = "TRUSTED_PROOF_OR_SELECTION_UNAVAILABLE"
            if active or (isinstance(selection, dict)
                          and selection.get("variant") == "candidate"
                          and selection.get("canary_id") == config.canary_id):
                rollback = _rollback_owned_candidate(
                    store, config, at=at, reason="MONITOR_PROOF_UNAVAILABLE")
                status["state"] = str(rollback.get("state") or state)
                status["rollback_readback"] = str(
                    (rollback.get("readback") or {}).get("readback")
                    if isinstance(rollback.get("readback"), Mapping)
                    else "FAIL"
                )
                if rollback.get("rolled_back") is not True:
                    status["reason"] = "TRUSTED_PROOF_UNAVAILABLE_ROLLBACK_UNVERIFIED"
            return status

        assert mandate is not None and isinstance(selection, dict)
        selection_sha256 = digest_json(selection)
        existing = record.get("monitor")
        if (isinstance(existing, dict)
                and existing.get("selection_sha256") == selection_sha256
                and _tower_monitor_healthy(root, config, now=at)):
            return {
                "enabled": True, "heartbeat_refreshed": False,
                "selection_readback": "PASS", "reason": None, "state": state,
            }
        payload = {
            "contract": "C01_MONITOR_V1", "state": "HEALTHY",
            "canary_id": config.canary_id,
            "baseline_sha256": config.baseline_sha256,
            "candidate_sha256": config.candidate_sha256,
            "analysis_plan_sha256": config.analysis_plan.plan_sha256,
            "selection_readback": "PASS",
            "selection_sha256": selection_sha256,
            "selection_variant": str(selection.get("variant") or ""),
            "loaded_candidate_sha256": actual_candidate_sha,
            "loaded_baseline_sha256": actual_baseline_sha,
            "registry_sha256": mandate.registry_sha256,
            "approval_ref": mandate.approval_ref,
            "approved_at": mandate.approved_at,
            "observed_at": iso_utc(at),
        }
        monitor = payload | {"proof_sha256": digest_json(payload)}

        def persist(doc: dict[str, Any]) -> None:
            record_now = (doc.get("canaries") or {}).get(config.canary_id)
            adapters = doc.get("adapters")
            if (not isinstance(record_now, dict)
                    or record_now.get("state") != state
                    or not isinstance(adapters, dict)
                    or adapters.get(ADAPTER_ID) != selection
                    or record_now.get("proposal_sha256") != config.proposal_sha256):
                raise AdapterConflict("C01_MONITOR_OBSERVATION_STALE")
            record_now["monitor"] = copy.deepcopy(monitor)

        store._mutate(persist)
        if not _tower_monitor_healthy(root, config, now=at):
            raise ReadbackError("C01_MONITOR_READBACK_FAILED")
        return {
            "enabled": True, "heartbeat_refreshed": True,
            "selection_readback": "PASS", "reason": None, "state": state,
        }
    except Exception as exc:
        status["reason"] = "MONITOR_REFRESH_FAILED"
        if store is not None and config is not None:
            try:
                state = str(store.get(config.canary_id).get("state") or "PROPOSED")
                if state in {"CANARY", "PROMOTED"}:
                    rollback = _rollback_owned_candidate(
                        store, config, at=at, reason="MONITOR_REFRESH_FAILED")
                    status["state"] = str(rollback.get("state") or state)
                    if rollback.get("rolled_back") is True:
                        status["rollback_readback"] = "PASS"
            except Exception:
                pass
        return status


def _tower_monitor_healthy(
    root: Path,
    config: CanaryConfig,
    *,
    now: dt.datetime | None = None,
) -> bool:
    """Verify a fresh private heartbeat and its current actuator readback."""
    try:
        store = TowerCanaryStore(root)
        record = store.get(config.canary_id)
        monitor = record.get("monitor")
        if not isinstance(monitor, dict):
            return False
        payload = dict(monitor)
        claimed = payload.pop("proof_sha256", None)
        if (payload.get("contract") != "C01_MONITOR_V1"
                or payload.get("state") != "HEALTHY"
                or payload.get("canary_id") != config.canary_id
                or payload.get("baseline_sha256") != config.baseline_sha256
                or payload.get("candidate_sha256") != config.candidate_sha256
                or payload.get("analysis_plan_sha256") != config.analysis_plan.plan_sha256
                or payload.get("selection_readback") != "PASS"
                or payload.get("loaded_candidate_sha256") != config.candidate_sha256
                or payload.get("loaded_baseline_sha256") != config.baseline_sha256
                or payload.get("selection_sha256") != digest_json(store.read_selection())
                or not _selection_readback_matches_record(
                    store, config, record, store.read_selection())
                or not _valid_hash(claimed)
                or claimed != digest_json(payload)):
            return False
        observed = parse_utc(str(payload.get("observed_at") or ""))
        age = (parse_utc(now or dt.datetime.now(dt.timezone.utc)) - observed).total_seconds()
        return -30 <= age <= 300
    except Exception:
        return False
