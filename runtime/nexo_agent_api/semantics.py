"""Semantic meaning of Tower entities (SEMANTIC_TAXONOMY_V1).

The taxonomy is a Git contract. Each TEST/CAMPAIGN either carries an explicit
``semantic`` block (canonical, written through the Tower) or gets one derived
from the contract's backfill rules. Nothing is guessed: no rule -> UNMAPPED.
The same resolved block organises the ATLAS graphs and the Learner.
"""

from __future__ import annotations

import fnmatch
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

TAXONOMY_PATH = Path(__file__).with_name("contracts") / "SEMANTIC_TAXONOMY_V1.json"
UNMAPPED = "UNMAPPED"

# Human-facing lifecycle (CONTROL.human_facing_status_model = READY_RUNNING_DONE_BLOCKED).
_DONE = {"RESULT", "VERIFIED", "DONE", "REJECTED", "COMPLETED", "CLOSED", "CLOSED_VERIFIED", "FALSIFIED", "SUPPORTED"}
_RUNNING = {"RUNNING", "IN_PROGRESS", "CLAIMED", "DISPATCHED", "EXECUTING", "VERIFY_PENDING"}


@lru_cache(maxsize=1)
def taxonomy() -> dict[str, Any]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _index() -> dict[str, dict[str, str]]:
    """id -> {domain_id, subdomain_id?, topic_id?, label} for every taxonomy node."""
    nodes: dict[str, dict[str, str]] = {}
    for domain in taxonomy()["domains"]:
        nodes[domain["id"]] = {"domain_id": domain["id"], "label": domain["label"]}
        for sub in domain.get("subdomains", []):
            nodes[sub["id"]] = {"domain_id": domain["id"], "subdomain_id": sub["id"], "label": sub["label"]}
            for topic in sub.get("topics", []):
                nodes[topic["id"]] = {
                    "domain_id": domain["id"],
                    "subdomain_id": sub["id"],
                    "topic_id": topic["id"],
                    "label": topic["label"],
                }
    return nodes


def status_group(status: Any) -> str:
    value = str(status or "").upper()
    if value in _DONE:
        return "DONE"
    if value.startswith("BLOCKED"):
        return "BLOCKED"
    if value in _RUNNING:
        return "RUNNING"
    if value.startswith("PAUSED"):
        return "PAUSED"
    return "READY"


def _from_node(node_id: str, basis: str) -> dict[str, Any]:
    node = _index().get(node_id)
    if not node:
        return {"domain_id": UNMAPPED, "subdomain_id": UNMAPPED, "topic_id": None, "basis": "UNMAPPED"}
    return {
        "domain_id": node["domain_id"],
        "subdomain_id": node.get("subdomain_id", UNMAPPED),
        "topic_id": node.get("topic_id"),
        "basis": basis,
    }


def _rule_for(test_id: str) -> str | None:
    rules = taxonomy()["backfill"]["standalone_test_rules"]
    if test_id in rules:
        return rules[test_id]
    for pattern, target in rules.items():
        if "*" in pattern and fnmatch.fnmatchcase(test_id, pattern):
            return target
    return None


def resolve(entity: dict[str, Any], *, entity_id: str | None = None) -> dict[str, Any]:
    """Resolve the semantic block for one TEST, WORK or CAMPAIGN record."""
    explicit = entity.get("semantic") if isinstance(entity.get("semantic"), dict) else {}
    backfill = taxonomy()["backfill"]
    resolved: dict[str, Any]
    node = explicit.get("topic_id") or explicit.get("subdomain_id")
    if node and node in _index():
        resolved = _from_node(node, "EXPLICIT")
    else:
        target = None
        basis = "UNMAPPED"
        campaign = str(entity.get("campaign_id") or "")
        roadmap = str(entity.get("roadmap_id") or "")
        if campaign in backfill["campaign_to_subdomain"]:
            target, basis = backfill["campaign_to_subdomain"][campaign], "CAMPAIGN"
        elif roadmap in backfill["roadmap_to_subdomain"]:
            target, basis = backfill["roadmap_to_subdomain"][roadmap], "ROADMAP"
        else:
            rule = _rule_for(str(entity_id or entity.get("id") or ""))
            if rule:
                target, basis = rule, "RULE"
        resolved = _from_node(target, basis) if target and target != UNMAPPED else _from_node("", "UNMAPPED")
    for key in ("question_plain", "why_it_matters", "result_meaning", "verdict_plain", "confidence_plain"):
        if explicit.get(key):
            resolved[key] = explicit[key]
    return resolved


def is_private(semantic: dict[str, Any]) -> bool:
    """Olympus is private by code, not by trusting the taxonomy's policy field."""
    return semantic.get("domain_id") == "olympus"


def public_tree() -> list[dict[str, Any]]:
    """Label tree for the ATLAS: ids and labels only, private domains included as labels."""
    return [
        {
            "id": domain["id"],
            "label": domain["label"],
            "private": domain.get("projection_policy") == "PRIVATE_ONLY",
            "subdomains": [
                {
                    "id": sub["id"],
                    "label": sub["label"],
                    "topics": [{"id": t["id"], "label": t["label"]} for t in sub.get("topics", [])],
                }
                for sub in domain.get("subdomains", [])
            ],
        }
        for domain in taxonomy()["domains"]
    ]
