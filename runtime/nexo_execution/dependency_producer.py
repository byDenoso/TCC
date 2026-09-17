from __future__ import annotations

import copy
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

_VALID_EVIDENCE_STATES = {
    "VALIDATED", "VERIFIED", "READY", "SATISFIED", "COMPLETE", "COMPLETED",
    "VERIFIED_CURRENT_SESSION", "VERIFIED_PINNED_ARCHIVE_CURRENT_SESSION",
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


def register_producer(implementation_id: str, implementation: Callable[[dict[str, Any]], list[str]]) -> None:
    """Register an explicitly allowlisted dependency producer implementation."""
    key = str(implementation_id or "").strip()
    if not key:
        raise ValueError("implementation_id is required")
    if not callable(implementation):
        raise ValueError("producer implementation must be callable")
    PRODUCER_IMPLEMENTATIONS[key] = implementation


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


def _valid_canonical_evidence(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status") or "").upper()
    if status not in _VALID_EVIDENCE_STATES and not status.startswith("VERIFIED_"):
        return False
    return bool(payload.get("sha256") or payload.get("archive_sha256") or payload.get("fingerprint") or payload.get("source_ref"))


def _manifest(test: dict[str, Any]) -> list[dict[str, Any]]:
    raw = test.get("dependency_manifest") or []
    if not isinstance(raw, list):
        raise ValueError("dependency_manifest must be a list")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("dependency_manifest entries must be objects")
        dependency_id = str(item.get("id") or "").strip()
        if not dependency_id:
            raise ValueError("dependency id is required")
        if dependency_id in seen:
            raise ValueError(f"duplicate dependency id: {dependency_id}")
        seen.add(dependency_id)
        result.append(item)
    return result


def compile_hydration_plan(
    test: dict[str, Any],
    *,
    canonical_evidence: dict[str, Any] | None = None,
    recipes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile one TEST dependency manifest into deterministic hydration actions.

    The compiler never changes scientific fields. It only decides whether an
    already-declared dependency can be reused, produced, or must remain blocked.
    """
    canonical_evidence = canonical_evidence or {}
    recipes = recipes or {}
    items: list[dict[str, Any]] = []

    for dependency in _manifest(test):
        dependency_id = str(dependency["id"])
        required = bool(dependency.get("required", True))
        state = str(dependency.get("status") or "MISSING").upper()
        action = "NONE"
        reason = "already satisfied"

        if state != "SATISFIED":
            evidence_id = str(dependency.get("evidence_id") or "")
            recipe_id = str(dependency.get("recipe_id") or "")
            evidence = canonical_evidence.get(evidence_id) if evidence_id else None
            recipe = recipes.get(recipe_id) if recipe_id else None

            if evidence_id and _valid_canonical_evidence(evidence):
                action = "BIND_EXISTING"
                reason = "validated canonical evidence is reusable"
            elif recipe_id and isinstance(recipe, dict) and str(recipe.get("state") or "READY").upper() == "READY":
                action = "PRODUCE"
                reason = "validated producer recipe is ready"
            elif bool(dependency.get("external_required")):
                action = "BLOCKED_EXTERNAL"
                reason = str(dependency.get("blocker_reason") or "external input or authorization required")
            elif recipe_id:
                action = "WAIT_RECIPE"
                reason = "producer recipe exists but is not READY"
            else:
                action = "NEEDS_RECIPE"
                reason = "no reusable evidence or producer recipe declared"

        items.append({
            "dependency_id": dependency_id,
            "required": required,
            "current_status": state,
            "action": action,
            "reason": reason,
        })

    required_items = [item for item in items if item["required"]]
    evaluator_ready = all(item["current_status"] == "SATISFIED" for item in required_items)
    if evaluator_ready:
        status = "READY_FOR_EVALUATOR"
    elif any(item["action"] == "BLOCKED_EXTERNAL" for item in required_items):
        status = "BLOCKED_EXTERNAL"
    elif any(item["action"] in {"BIND_EXISTING", "PRODUCE"} for item in required_items):
        status = "HYDRATE"
    else:
        status = "WAITING_BINDING"

    return {
        "schema": "nexo.hydration-plan.v1",
        "test_id": str(test.get("id") or test.get("test_id") or ""),
        "status": status,
        "evaluator_ready": evaluator_ready,
        "items": items,
    }


def hydrate_test_dependencies(
    test: dict[str, Any],
    *,
    canonical_evidence: dict[str, Any] | None = None,
    recipes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hydrate reusable/producer-backed dependencies for one TEST.

    Optional blocked dependencies never stop the evaluator. Required blocked
    dependencies remain local to this TEST lane and do not affect other tests.
    """
    canonical_evidence = canonical_evidence or {}
    recipes = recipes or {}
    hydrated = copy.deepcopy(test)
    plan = compile_hydration_plan(hydrated, canonical_evidence=canonical_evidence, recipes=recipes)
    action_by_id = {item["dependency_id"]: item for item in plan["items"]}
    producer_results: list[dict[str, Any]] = []

    for dependency in _manifest(hydrated):
        dependency_id = str(dependency["id"])
        action = action_by_id[dependency_id]["action"]
        if action == "BIND_EXISTING":
            evidence_id = str(dependency.get("evidence_id") or "")
            evidence = canonical_evidence[evidence_id]
            dependency["status"] = "SATISFIED"
            dependency["binding"] = {
                "mode": "CANONICAL_EVIDENCE_REUSE",
                "evidence_id": evidence_id,
                "sha256": evidence.get("sha256") or evidence.get("archive_sha256"),
                "fingerprint": evidence.get("fingerprint"),
                "source_ref": evidence.get("source_ref"),
            }
        elif action == "PRODUCE":
            recipe_id = str(dependency.get("recipe_id") or "")
            recipe = recipes[recipe_id]
            try:
                result = run_recipe(recipe)
            except Exception as exc:
                result = {
                    "schema": "nexo.dependency-producer-result.v1",
                    "recipe_id": recipe_id,
                    "parent_test_id": str(hydrated.get("id") or hydrated.get("test_id") or ""),
                    "status": "FAILED_RECOVERABLE",
                    "reason": f"{type(exc).__name__}:{exc}",
                    "outputs": [],
                    "missing_required_outputs": [],
                }
            producer_results.append(result)
            if result.get("status") == "COMPLETE" and not result.get("missing_required_outputs"):
                dependency["status"] = "SATISFIED"
                dependency["binding"] = {
                    "mode": "PRODUCER_RESULT",
                    "recipe_id": recipe_id,
                    "producer_fingerprint": result.get("producer_fingerprint"),
                    "outputs": result.get("outputs", []),
                }
            else:
                dependency["status"] = "CHECKPOINTED" if result.get("status") == "FAILED_RECOVERABLE" else str(result.get("status") or "MISSING")
                dependency["last_producer_result"] = result
        elif action == "BLOCKED_EXTERNAL":
            dependency["status"] = "BLOCKED_EXTERNAL"
            dependency["blocker_reason"] = action_by_id[dependency_id]["reason"]

    required = [item for item in hydrated.get("dependency_manifest", []) if bool(item.get("required", True))]
    evaluator_ready = all(str(item.get("status") or "").upper() == "SATISFIED" for item in required)
    return {
        "schema": "nexo.hydration-result.v1",
        "test": hydrated,
        "evaluator_ready": evaluator_ready,
        "producer_results": producer_results,
        "plan": compile_hydration_plan(hydrated, canonical_evidence=canonical_evidence, recipes=recipes),
    }


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
