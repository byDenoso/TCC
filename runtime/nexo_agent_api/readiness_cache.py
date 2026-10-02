"""Fail-closed cache for canonical readiness results.

The cache is useful only when the caller supplies a complete immutable
context.  The default evaluator is still the canonical readiness function;
cache errors and incomplete context always run that function directly.
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .tower_paths import entity_path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ACCESS_SCOPES = {"PUBLIC", "PRIVATE"}
_CONTEXT_VERSION = "READINESS_CACHE_CONTEXT_V2"


class ReadinessContextUnavailable(ValueError):
    """Raised when a complete cache key cannot be proved from local state."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical(value))


def _read_digest(path: Path, metrics: dict[str, int] | None = None) -> str:
    try:
        raw = path.read_bytes()
        if metrics is not None:
            metrics["context_read_calls"] = metrics.get("context_read_calls", 0) + 1
            metrics["context_bytes_read"] = metrics.get("context_bytes_read", 0) + len(raw)
        return _sha256_bytes(raw)
    except OSError as exc:
        raise ReadinessContextUnavailable(f"CONTEXT_FILE_UNAVAILABLE:{path.name}") from exc


def _validator_bundle_hash(validator: Callable[..., Any], runtime_root: Path,
                           metrics: dict[str, int] | None = None) -> str:
    """Hash the readiness implementation and its local policy helpers."""
    try:
        source = inspect.getsourcefile(validator)
    except (TypeError, OSError):
        source = None
    if not source:
        raise ReadinessContextUnavailable("VALIDATOR_SOURCE_UNAVAILABLE")
    source_path = Path(source).resolve()
    files = {source_path}
    # readiness() delegates important eligibility decisions to these modules.
    # Hashing them makes a helper update invalidate entries automatically.
    api_dir = source_path.parent
    for name in ("parameter_admission.py", "evolution.py", "tower_paths.py"):
        candidate = api_dir / name
        if candidate.is_file():
            files.add(candidate.resolve())
        elif name != "tower_paths.py":
            raise ReadinessContextUnavailable(f"VALIDATOR_HELPER_UNAVAILABLE:{name}")
    records = []
    for path in sorted(files, key=lambda item: str(item).casefold()):
        records.append({"name": path.name, "sha256": _read_digest(path, metrics)})
    return _sha256_json({"bundle": records, "context_version": _CONTEXT_VERSION})


@dataclass(frozen=True)
class ReadinessCacheContext:
    """Content-derived key inputs for one readiness decision.

    `manifest_*`, access scope, and authorization revision are explicit
    because the readiness function's answer can be used in different data
    scopes even when its immediate test object is identical.
    """

    test_id: str
    test_contract_sha256: str
    dependency_revisions: tuple[tuple[str, str], ...]
    recipe_id: str
    recipe_sha256: str
    smoke_sha256: str
    manifest_revision: str
    manifest_sha256: str
    validator_version: str
    validator_sha256: str
    access_scope: str
    authorization_revision: str
    reservation_sha256: str
    parameter_contract_sha256: str = _sha256_bytes(b"NO_PARAMETER_CONTRACT")
    context_version: str = _CONTEXT_VERSION

    def __post_init__(self) -> None:
        if not self.test_id or not self.recipe_id or not self.manifest_revision:
            raise ReadinessContextUnavailable("CONTEXT_IDENTITY_INCOMPLETE")
        if self.access_scope not in _ACCESS_SCOPES:
            raise ReadinessContextUnavailable("ACCESS_SCOPE_UNVERIFIED")
        if not self.authorization_revision:
            raise ReadinessContextUnavailable("AUTHORIZATION_REVISION_UNVERIFIED")
        for name in ("test_contract_sha256", "recipe_sha256", "smoke_sha256",
                     "manifest_sha256", "validator_sha256", "reservation_sha256",
                     "parameter_contract_sha256"):
            if not _SHA256.fullmatch(getattr(self, name)):
                raise ReadinessContextUnavailable("CONTEXT_HASH_INVALID:" + name)
        if not self.validator_version:
            raise ReadinessContextUnavailable("VALIDATOR_VERSION_UNVERIFIED")
        if tuple(sorted(self.dependency_revisions)) != self.dependency_revisions:
            raise ReadinessContextUnavailable("DEPENDENCY_REVISIONS_NOT_CANONICAL")
        if any(not key or not _SHA256.fullmatch(value)
               for key, value in self.dependency_revisions):
            raise ReadinessContextUnavailable("DEPENDENCY_REVISION_INVALID")

    @property
    def key(self) -> str:
        return _sha256_json(asdict(self))

    @classmethod
    def from_runtime(
        cls,
        root: Path,
        test: Mapping[str, Any],
        *,
        access_scope: str,
        authorization_revision: str,
        manifest_revision: str,
        manifest_sha256: str,
        validator: Callable[..., Any],
        validator_version: str,
        recipe_root: Path | None = None,
        metrics_out: dict[str, Any] | None = None,
    ) -> "ReadinessCacheContext":
        """Capture every local readiness input that can affect the result.

        Callers should catch `ReadinessContextUnavailable` and run the baseline
        evaluator. Missing dependencies, recipes, or policy source never yield
        a cache key.
        """
        started = time.perf_counter()
        read_metrics: dict[str, int] = {"context_read_calls": 0, "context_bytes_read": 0}
        if not isinstance(test, Mapping):
            raise ReadinessContextUnavailable("TEST_SNAPSHOT_INVALID")
        test_id = str(test.get("id") or "")
        recipe_id = str(test.get("recipe") or "")
        if not test_id or not recipe_id:
            raise ReadinessContextUnavailable("TEST_OR_RECIPE_ID_MISSING")
        if not _SHA256.fullmatch(str(manifest_sha256 or "")):
            raise ReadinessContextUnavailable("MANIFEST_HASH_UNVERIFIED")

        dependency_ids = test.get("depends_on") or []
        if not isinstance(dependency_ids, list):
            raise ReadinessContextUnavailable("DEPENDENCIES_INVALID")
        dependencies: list[tuple[str, str]] = []
        for dependency_id in dependency_ids:
            dep_id = str(dependency_id)
            if not dep_id:
                raise ReadinessContextUnavailable("DEPENDENCY_ID_INVALID")
            dependency_path = entity_path(Path(root), "test", dep_id)
            if not dependency_path.is_file():
                raise ReadinessContextUnavailable("DEPENDENCY_REVISION_UNAVAILABLE")
            dependencies.append((dep_id, _read_digest(dependency_path, read_metrics)))
        dependencies.sort()

        if recipe_root is None:
            recipe_root = Path(os.environ.get(
                "NEXO_RECIPE_ROOT", "nexo-one/executor-runtime/recipes"))
        recipe_root = Path(recipe_root)
        if not recipe_root.is_absolute():
            # Match the runtime readiness implementation, which resolves its
            # default recipe root from the process working directory.
            recipe_root = Path.cwd() / recipe_root
        code = recipe_root / (recipe_id + ".py")
        smoke = recipe_root / "smoke" / (recipe_id + ".json")
        if not code.is_file() or not smoke.is_file():
            raise ReadinessContextUnavailable("RECIPE_OR_SMOKE_UNAVAILABLE")
        try:
            smoke_raw = smoke.read_bytes()
            read_metrics["context_read_calls"] += 1
            read_metrics["context_bytes_read"] += len(smoke_raw)
            json.loads(smoke_raw.decode("utf-8"))
        except (OSError, ValueError) as exc:
            raise ReadinessContextUnavailable("RECIPE_SMOKE_INVALID") from exc

        reservation_file = Path(root) / "evolution" / "batteries.json"
        if reservation_file.is_file():
            try:
                reservation_raw = reservation_file.read_bytes()
                read_metrics["context_read_calls"] += 1
                read_metrics["context_bytes_read"] += len(reservation_raw)
                reservation_sha256 = _sha256_bytes(reservation_raw)
                reservation_doc = json.loads(reservation_raw.decode("utf-8"))
                if not isinstance(reservation_doc, dict):
                    raise ValueError("not an object")
                if not isinstance(reservation_doc.get("batteries", []), list):
                    raise ValueError("batteries is not a list")
            except (OSError, ValueError) as exc:
                raise ReadinessContextUnavailable("RESERVATION_SNAPSHOT_INVALID") from exc
        else:
            # The canonical readiness reader treats a missing ledger as empty.
            reservation_sha256 = _sha256_bytes(b"MISSING:evolution/batteries.json")

        # Parameter admission reads these catalog files independently of the
        # recipe and smoke spec. Include absence as well as content: installing,
        # removing, or changing a preflight contract must invalidate cached READY.
        parameter_files = {}
        for relative in ("preflight/" + recipe_id + ".json", "recipe_param_preflight.py"):
            path = recipe_root / relative
            parameter_files[relative] = (
                _read_digest(path, read_metrics) if path.is_file()
                else _sha256_bytes(("MISSING:" + relative).encode("utf-8"))
            )

        context = cls(
            test_id=test_id,
            test_contract_sha256=_sha256_json(dict(test)),
            dependency_revisions=tuple(dependencies),
            recipe_id=recipe_id,
            recipe_sha256=_read_digest(code, read_metrics),
            smoke_sha256=_sha256_bytes(smoke_raw),
            manifest_revision=str(manifest_revision or ""),
            manifest_sha256=str(manifest_sha256),
            validator_version=str(validator_version or ""),
            validator_sha256=_validator_bundle_hash(validator, Path(root), read_metrics),
            access_scope=str(access_scope or "").upper(),
            authorization_revision=str(authorization_revision or ""),
            reservation_sha256=reservation_sha256,
            parameter_contract_sha256=_sha256_json(parameter_files),
        )
        if metrics_out is not None:
            metrics_out.update(read_metrics)
            metrics_out["context_elapsed_ms"] = (time.perf_counter() - started) * 1_000
            metrics_out["context_cache_hit"] = False
        return context


class ReadinessCache:
    """Thread-safe process cache. Persistent storage is deliberately opt-in."""

    def __init__(self) -> None:
        self._values: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _canonical_result(value: Any) -> bool:
        return (isinstance(value, dict)
                and type(value.get("eligible")) is bool
                and isinstance(value.get("reasons"), list)
                and all(isinstance(reason, str) for reason in value["reasons"])
                and isinstance(value.get("policy"), str))

    def get(self, context: ReadinessCacheContext) -> dict[str, Any] | None:
        with self._lock:
            value = self._values.get(context.key)
            return copy.deepcopy(value) if value is not None else None

    def put(self, context: ReadinessCacheContext, result: dict[str, Any]) -> None:
        if not self._canonical_result(result):
            raise ValueError("READINESS_RESULT_NOT_CANONICAL")
        with self._lock:
            self._values[context.key] = copy.deepcopy(result)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


class ReadinessContextEpoch:
    """Reuse captured contexts only while the caller's immutable Tower revision is fixed.

    The revision is supplied by the canonical materialization boundary. A new
    revision clears every cached context before any lookup can reuse it. This
    avoids hashing every dependency/recipe/validator file on each readiness
    call while retaining a strict invalidation boundary.
    """

    def __init__(self) -> None:
        self._revision: str | None = None
        self._contexts: dict[str, ReadinessCacheContext] = {}
        self._lock = threading.RLock()

    def capture(self, revision: str, identity: str,
                builder: Callable[[dict[str, Any]], ReadinessCacheContext]
                ) -> tuple[ReadinessCacheContext, dict[str, Any]]:
        if not revision or not identity:
            raise ReadinessContextUnavailable("IMMUTABLE_EPOCH_IDENTITY_MISSING")
        with self._lock:
            if revision != self._revision:
                self._revision = revision
                self._contexts.clear()
            cached = self._contexts.get(identity)
            if cached is not None:
                return cached, {
                    "context_read_calls": 0,
                    "context_bytes_read": 0,
                    "context_elapsed_ms": 0.0,
                    "context_cache_hit": True,
                }
            metrics: dict[str, Any] = {}
            started = time.perf_counter()
            context = builder(metrics)
            metrics.setdefault("context_elapsed_ms", (time.perf_counter() - started) * 1_000)
            metrics.setdefault("context_read_calls", 0)
            metrics.setdefault("context_bytes_read", 0)
            metrics["context_cache_hit"] = False
            self._contexts[identity] = context
            return context, metrics

    def invalidate(self) -> None:
        with self._lock:
            self._revision = None
            self._contexts.clear()


def evaluate_with_readiness_cache(
    baseline: Callable[[], dict[str, Any]],
    context: ReadinessCacheContext | None,
    cache: ReadinessCache | Any,
    *,
    enabled: bool = False,
) -> dict[str, Any]:
    """Run a cached candidate evaluation, falling back to baseline on doubt.

    The baseline callable remains the source of truth on a miss. Exceptions
    from the cache are ignored and trigger a baseline read. Exceptions from
    the baseline itself propagate; no stale cached READY can mask them.
    """
    if not enabled or context is None:
        return baseline()
    try:
        cached = cache.get(context)
        if cached is not None and ReadinessCache._canonical_result(cached):
            return copy.deepcopy(cached)
    except Exception:
        return baseline()

    result = baseline()
    if not ReadinessCache._canonical_result(result):
        return result
    try:
        cache.put(context, result)
    except Exception:
        # A storage problem affects only cache reuse, never readiness.
        pass
    return result
