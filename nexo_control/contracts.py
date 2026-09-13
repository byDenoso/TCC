from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_SCHEMA_PATH = ROOT / ".nexo" / "schemas" / "campaign.schema.json"

EXECUTOR_REGISTRY = {"github_workflow"}
VALIDATOR_REGISTRY = {"artifact_presence_only", "contract_test_pass"}
FORBIDDEN_KEYS = {"run", "command", "shell", "script"}


def load_campaign(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("campaign must be a mapping")
    return validate_campaign(data)


def _walk_forbidden(value: Any, path: str = "campaign") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"forbidden key: {path}.{key}")
            _walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden(child, f"{path}[{index}]")


def _check_dependencies(tests: list[dict[str, Any]]) -> None:
    ids = [test["test_id"] for test in tests]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate test_id")

    known = set(ids)
    graph: dict[str, list[str]] = {}
    for test in tests:
        test_id = test["test_id"]
        deps = list(test["depends_on"])
        for dep in deps:
            if dep not in known:
                raise ValueError(f"missing dependency: {dep}")
        graph[test_id] = deps

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("dependency cycle")
        if node in visited:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep)
        visiting.remove(node)
        visited.add(node)

    for node in ids:
        visit(node)


def validate_campaign(campaign: dict[str, Any]) -> dict[str, Any]:
    _walk_forbidden(campaign)

    schema = json.loads(CAMPAIGN_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(campaign), key=lambda err: list(err.path))
    if errors:
        err = errors[0]
        location = ".".join(str(item) for item in err.path) or "campaign"
        raise ValueError(f"schema validation failed at {location}: {err.message}")

    budget = campaign["budget"]
    tests = campaign["tests"]
    if len(tests) > budget["max_tests"]:
        raise ValueError("max_tests budget exceeded")
    if budget["max_parallel"] > budget["max_tests"]:
        raise ValueError("max_parallel cannot exceed max_tests")

    for test in tests:
        if test["executor"] not in EXECUTOR_REGISTRY:
            raise ValueError(f"unknown executor: {test['executor']}")
        validator = test["promotion"]["validator"]
        if validator not in VALIDATOR_REGISTRY:
            raise ValueError(f"unknown validator: {validator}")

    _check_dependencies(tests)
    return campaign
