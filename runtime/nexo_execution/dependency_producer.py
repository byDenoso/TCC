from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

_REQUIRED_SCIENCE_FIELDS = {
    "dataset", "selection", "likelihood", "covariance", "model", "null_or_rival",
    "fixed_parameters", "free_parameters", "priors", "nuisance_policy", "cuts",
    "observable", "decision_rule", "claim_boundary",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    if recipe.get("schema") != "nexo.dependency-producer.v1":
        raise ValueError("unsupported dependency producer schema")
    for field in ("recipe_id", "parent_test_id", "capability_id", "repository", "requirements", "scientific_contract", "execution", "validation", "binding"):
        if field not in recipe:
            raise ValueError(f"missing recipe field: {field}")
    contract = recipe.get("scientific_contract")
    if not isinstance(contract, dict) or not contract:
        raise ValueError("scientific_contract must be a non-empty object")
    missing = sorted(_REQUIRED_SCIENCE_FIELDS - set(contract))
    if missing:
        raise ValueError("scientific_contract missing fields: " + ", ".join(missing))
    if not isinstance(recipe.get("requirements"), list) or not recipe["requirements"]:
        raise ValueError("requirements must be a non-empty list")
    execution = recipe.get("execution") or {}
    if int(execution.get("attempt_timeout_minutes") or 0) <= 0:
        raise ValueError("attempt_timeout_minutes must be positive")
    if execution.get("resume_policy") not in {"IDENTICAL_CONTRACT_ONLY", "DISABLED"}:
        raise ValueError("unsupported resume_policy")
    binding = recipe.get("binding") or {}
    if not binding.get("output_schema") or binding.get("target_test_id") != recipe.get("parent_test_id"):
        raise ValueError("binding must target parent_test_id with an output_schema")
    return {"status": "PASS", "recipe_id": recipe["recipe_id"], "producer_fingerprint": producer_fingerprint(recipe)}


def producer_fingerprint(recipe: dict[str, Any]) -> str:
    return _sha({
        "parent_test_id": recipe.get("parent_test_id"),
        "requirements": recipe.get("requirements"),
        "scientific_contract": recipe.get("scientific_contract"),
        "binding": recipe.get("binding"),
    })


def checkpoint_compatible(checkpoint: dict[str, Any], recipe: dict[str, Any]) -> bool:
    return (
        str(checkpoint.get("recipe_id") or "") == str(recipe.get("recipe_id") or "")
        and str(checkpoint.get("producer_fingerprint") or "") == producer_fingerprint(recipe)
        and str(checkpoint.get("status") or "").upper() in {"CHECKPOINTED", "RUNNING", "FAILED_RECOVERABLE"}
        and str((recipe.get("execution") or {}).get("resume_policy") or "") == "IDENTICAL_CONTRACT_ONLY"
    )


def build_producer_envelope(
    recipe: dict[str, Any],
    output_paths: Iterable[str],
    *,
    status: str,
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validate_recipe(recipe)
    outputs = []
    for raw in output_paths:
        path = Path(raw)
        if not path.is_file():
            continue
        outputs.append({"path": raw, "sha256": _sha_file(path), "bytes": path.stat().st_size})
    required = set((recipe.get("validation") or {}).get("required_outputs") or [])
    present = {Path(item["path"]).name for item in outputs} | {item["path"] for item in outputs}
    missing = sorted(item for item in required if item not in present)
    return {
        "schema": "nexo.dependency-producer-result.v1",
        "recipe_id": recipe["recipe_id"],
        "parent_test_id": recipe["parent_test_id"],
        "requirements": list(recipe["requirements"]),
        "producer_fingerprint": validation["producer_fingerprint"],
        "status": status,
        "outputs": outputs,
        "missing_required_outputs": missing,
        "checkpoint": checkpoint,
        "binding": recipe["binding"],
    }
