from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable

_REQUIRED_SCIENCE_FIELDS = {
    "dataset", "selection", "likelihood", "covariance", "model", "null_or_rival",
    "fixed_parameters", "free_parameters", "priors", "nuisance_policy", "cuts",
    "observable", "decision_rule", "claim_boundary",
}

# Domain producer implementations must be explicitly registered in code. A recipe
# may select an implementation id, but can never inject an arbitrary command.
PRODUCER_IMPLEMENTATIONS: dict[str, Callable[[dict[str, Any]], list[str]]] = {}


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


def load_recipe(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("dependency producer recipe root must be an object")
    return payload


def validate_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    if recipe.get("schema") != "nexo.dependency-producer.v1":
        raise ValueError("unsupported dependency producer schema")
    if str(recipe.get("state") or "READY").upper() != "READY":
        missing = [str(item) for item in recipe.get("missing_scientific_bindings") or [] if str(item)]
        raise ValueError("recipe is not READY; missing_scientific_bindings=" + ",".join(missing))
    for field in ("recipe_id", "parent_test_id", "capability_id", "repository", "requirements", "scientific_contract", "execution", "validation", "binding", "implementation_id"):
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
    if not str(recipe.get("implementation_id") or "").strip():
        raise ValueError("implementation_id is required")
    return {"status": "PASS", "recipe_id": recipe["recipe_id"], "producer_fingerprint": producer_fingerprint(recipe)}


def producer_fingerprint(recipe: dict[str, Any]) -> str:
    return _sha({
        "parent_test_id": recipe.get("parent_test_id"),
        "requirements": recipe.get("requirements"),
        "scientific_contract": recipe.get("scientific_contract"),
        "binding": recipe.get("binding"),
        "implementation_id": recipe.get("implementation_id"),
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


def run_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    validation = validate_recipe(recipe)
    implementation_id = str(recipe["implementation_id"])
    implementation = PRODUCER_IMPLEMENTATIONS.get(implementation_id)
    if implementation is None:
        raise ValueError(f"producer implementation is not allowlisted: {implementation_id}")
    output_paths = implementation(recipe)
    envelope = build_producer_envelope(recipe, output_paths, status="COMPLETE")
    if envelope["missing_required_outputs"]:
        envelope["status"] = "FAILED_RECOVERABLE"
    return {**envelope, "validation": validation}


def main() -> int:
    recipe_path = str(os.getenv("NEXO_PARAM_RECIPE_PATH") or "").strip()
    output_path = Path(str(os.getenv("NEXO_PARAM_RESULT_PATH") or "dependency_producer_result.json"))
    result: dict[str, Any]
    exit_code = 0
    try:
        if not recipe_path:
            raise ValueError("NEXO_PARAM_RECIPE_PATH is required")
        recipe = load_recipe(recipe_path)
        result = run_recipe(recipe)
        if result.get("status") != "COMPLETE":
            exit_code = 2
    except Exception as exc:
        result = {
            "schema": "nexo.dependency-producer-result.v1",
            "status": "NOT_EXECUTED",
            "reason": f"{type(exc).__name__}:{exc}",
            "recipe_path": recipe_path or None,
        }
        exit_code = 2
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
