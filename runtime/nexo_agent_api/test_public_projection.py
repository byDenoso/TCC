"""The public projection must be derived, deterministic, and never inventive.

Two properties carry the whole design:

1. the same canonical state produces the same bytes and the same fingerprint, so
   an unchanged Tower cannot cause a churn-only republish;
2. a WORK id that exists only in an index never reaches the public surface,
   because indexes carry priority and entities carry existence.
"""
from __future__ import annotations

import json
from pathlib import Path

from .public_projection import (
    build_public_projection,
    projection_bytes,
    verify_projection,
)

CONTROL = {
    "truth_owner": "byDenoso/NEXO-Obsidian-Vault@main:TOWER_V06",
    "write_model": "GITHUB_CAS_ENTITY_EVENT",
    "write_guard": "READ_SHA_WRITE_READBACK",
    "derived_indexes_authority": "PROJECTION_ONLY_NEVER_EXISTENCE_GATE",
    "atlas_role": "READ_ONLY_PROJECTION",
    "drive_role": "LEGACY_PROJECTION_ONLY",
    "runtime_revision": "byDenoso/TCC@" + "0" * 40,
    "secret_operational_note": "must never reach the public surface",
}


def _tower(tmp_path: Path, *, index_only: bool = False) -> Path:
    root = tmp_path / "TOWER_V06"
    (root / "entities" / "work").mkdir(parents=True)
    (root / "entities" / "test").mkdir(parents=True)
    (root / "roadmaps").mkdir(parents=True)
    (root / "indexes").mkdir(parents=True)
    (root / "snapshot").mkdir(parents=True)
    (root / "manifests").mkdir(parents=True)

    (root / "CONTROL.json").write_text(json.dumps(CONTROL), encoding="utf-8")
    (root / "snapshot" / "latest.json").write_text(
        json.dumps({"counts": {"active_work": 2}, "event_cursor": "20260918T000000000000Z-abc"}),
        encoding="utf-8",
    )
    (root / "manifests" / "capabilities.json").write_text(
        json.dumps(
            {
                "capabilities": {
                    "science.demo_v1": {
                        "status": "ACTIVE",
                        "backend": "github_actions",
                        "private_runner_token_hint": "never publish this",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    for work_id in ("WORK-A", "WORK-B"):
        (root / "entities" / "work" / f"{work_id}.json").write_text(
            json.dumps(
                {
                    "id": work_id,
                    "kind": "WORK",
                    "status": "READY",
                    "priority": "P0",
                    "domain": "SCIENCE",
                    "owner_role": "EXECUTOR",
                    "title": f"title of {work_id}",
                    "human_action_required": work_id == "WORK-A",
                    "dependency_class": "HUMAN_DECISION_REQUIRED" if work_id == "WORK-A" else None,
                    "next_action": "WAIT_FOR_EXPLICIT_OPERATOR_DECISION" if work_id == "WORK-A" else None,
                    "question": "Choose whether to reopen the upstream gate." if work_id == "WORK-A" else None,
                    "updated_at": "2026-09-19",
                    "internal_notes": "canonical only",
                }
            ),
            encoding="utf-8",
        )

    index_work = [{"id": "WORK-B"}, {"id": "WORK-A"}]
    if index_only:
        index_work.append({"id": "WORK-GHOST"})
    (root / "indexes" / "active-work.json").write_text(
        json.dumps({"work": index_work, "count": len(index_work)}), encoding="utf-8"
    )
    return root


def _build(root: Path, **kwargs):
    defaults = {"tower_commit": "a" * 40, "generated_at": "2026-09-18T00:00:00Z"}
    defaults.update(kwargs)
    return build_public_projection(root, **defaults)


# --- determinism --------------------------------------------------------------


def test_same_canonical_state_yields_identical_bytes(tmp_path):
    root = _tower(tmp_path)
    first = projection_bytes(_build(root))
    second = projection_bytes(_build(root))
    assert first == second


def test_wall_clock_does_not_change_the_fingerprint(tmp_path):
    root = _tower(tmp_path)
    early = _build(root, generated_at="2026-09-18T00:00:00Z")
    later = _build(root, generated_at="2026-09-19T23:59:59Z")
    assert (
        early["manifest"]["projection_fingerprint"]
        == later["manifest"]["projection_fingerprint"]
    )
    assert early["manifest"]["generated_at"] != later["manifest"]["generated_at"]


def test_changed_canonical_state_changes_the_fingerprint(tmp_path):
    root = _tower(tmp_path)
    before = _build(root)["manifest"]["projection_fingerprint"]
    payload = json.loads((root / "entities" / "work" / "WORK-A.json").read_text(encoding="utf-8"))
    payload["status"] = "RUNNING"
    (root / "entities" / "work" / "WORK-A.json").write_text(json.dumps(payload), encoding="utf-8")
    after = _build(root)["manifest"]["projection_fingerprint"]
    assert before != after


def test_projection_ends_with_a_single_newline(tmp_path):
    raw = projection_bytes(_build(_tower(tmp_path)))
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    assert b"\r\n" not in raw


# --- existence authority ------------------------------------------------------


def test_index_only_work_never_reaches_the_public_surface(tmp_path):
    root = _tower(tmp_path, index_only=True)
    projection = _build(root)
    ids = [item["id"] for item in projection["work"]]
    assert "WORK-GHOST" not in ids
    assert ids == ["WORK-B", "WORK-A"], "a ordem do índice é a prioridade e deve ser preservada"
    assert projection["index_only_dropped"] == ["WORK-GHOST"]
    assert projection["counts"]["index_only_dropped"] == 1
    assert projection["counts"]["active_work"] == 2


def test_index_order_is_preserved_as_priority(tmp_path):
    root = _tower(tmp_path)
    assert [item["id"] for item in _build(root)["work"]] == ["WORK-B", "WORK-A"]


# --- allowlist ----------------------------------------------------------------


def test_only_allowlisted_fields_are_published(tmp_path):
    projection = _build(_tower(tmp_path))
    raw = projection_bytes(projection)
    assert b"internal_notes" not in raw
    assert b"canonical only" not in raw
    assert b"secret_operational_note" not in raw
    assert b"private_runner_token_hint" not in raw
    assert b"never publish this" not in raw

def test_campaigns_are_first_class_and_publish_source_links_without_leaking_roadmap(tmp_path):
    root = _tower(tmp_path)
    roadmap = {
        "schema_version": "1.0",
        "contract": "SCIENTIFIC_ROADMAP_V1",
        "roadmap_id": "RM-DEMO-V1",
        "campaign_id": "CAMP-DEMO",
        "title": "Demo campaign",
        "domain": "SCIENCE",
        "subdomain": "COSMOLOGY/DARK_ENERGY",
        "state": "ACTIVE",
        "semantic_description": "Campaign exists before any materialized test.",
        "semantic_state": "ACTIVE",
        "claim_boundary": "Demo boundary.",
        "atlas_projection": {
            "visible": True,
            "node_type": "CAMPAIGN",
            "parent_subdomain": "Energia escura",
            "label": "Demo · DDE",
            "show_tests": False,
            "private_layout_hint": "must never publish",
        },
        "source_links": [
            {"label": "Official release", "url": "https://example.org/release", "kind": "OFFICIAL"},
        ],
        "prior_art_snapshot": {
            "anchors": [
                "Primary paper, arXiv:2503.14743",
                "Independent paper, arXiv:2502.03515",
            ],
            "private_notes": "must never publish",
        },
        "execution_policy": {"secret_runtime_detail": "must never publish"},
    }
    (root / "roadmaps" / "RM-DEMO-V1.json").write_text(json.dumps(roadmap), encoding="utf-8")

    projection = _build(root)

    assert projection["counts"]["campaigns"] == 1
    assert len(projection["campaigns"]) == 1
    campaign = projection["campaigns"][0]
    assert campaign["campaign_id"] == "CAMP-DEMO"
    assert campaign["atlas_projection"] == {
        "visible": True,
        "node_type": "CAMPAIGN",
        "parent_subdomain": "Energia escura",
        "label": "Demo · DDE",
        "show_tests": False,
    }
    assert campaign["source_links"] == [
        {
            "label": "Official release",
            "url": "https://example.org/release",
            "kind": "OFFICIAL",
        },
        {
            "label": "Independent paper, arXiv:2502.03515",
            "url": "https://arxiv.org/abs/2502.03515",
            "kind": "ARXIV",
        },
        {
            "label": "Primary paper, arXiv:2503.14743",
            "url": "https://arxiv.org/abs/2503.14743",
            "kind": "ARXIV",
        },
    ]
    raw = projection_bytes(projection)
    assert b"private_layout_hint" not in raw
    assert b"private_notes" not in raw
    assert b"secret_runtime_detail" not in raw


def test_explicit_human_gate_index_survives_public_projection(tmp_path):
    projection = _build(_tower(tmp_path))
    assert projection["human_gates"] == {"work_ids": ["WORK-A"], "count": 1}
    assert projection["counts"]["needs_dener"] == 1
    work = {item["id"]: item for item in projection["work"]}
    assert "human_action_required" not in work["WORK-A"]
    assert "internal_notes" not in work["WORK-A"]



def test_authority_declaration_is_reproduced_from_control(tmp_path):
    projection = _build(_tower(tmp_path))
    declared = projection["authority_declaration"]
    assert declared["truth_owner"] == CONTROL["truth_owner"]
    assert declared["derived_indexes_authority"] == "PROJECTION_ONLY_NEVER_EXISTENCE_GATE"
    assert "secret_operational_note" not in declared


# --- manifest and verification ------------------------------------------------


def test_manifest_declares_itself_derived(tmp_path):
    manifest = _build(_tower(tmp_path))["manifest"]
    assert manifest["authority"] == "TOWER_V06"
    assert manifest["projection_only"] is True
    assert manifest["writeback"] == "FORBIDDEN"
    assert manifest["tower_repository"] == "byDenoso/NEXO-Obsidian-Vault"
    assert manifest["event_cursor"] == "20260918T000000000000Z-abc"
    assert manifest["tower_commit"] == "a" * 40


def test_verification_accepts_an_untouched_projection(tmp_path):
    ok, detail = verify_projection(_build(_tower(tmp_path)))
    assert ok, detail


def test_verification_rejects_tampering(tmp_path):
    projection = _build(_tower(tmp_path))
    projection["work"][0]["status"] = "VERIFIED"
    ok, detail = verify_projection(projection)
    assert not ok
    assert "declared=" in detail


def test_verification_rejects_a_projection_claiming_to_be_authoritative(tmp_path):
    projection = _build(_tower(tmp_path))
    projection["manifest"]["projection_only"] = False
    ok, detail = verify_projection(projection)
    assert not ok
    assert "projection_only" in detail


def test_verification_requires_provenance(tmp_path):
    root = _tower(tmp_path)
    without_commit = _build(root, tower_commit=None)
    ok, detail = verify_projection(without_commit)
    assert not ok
    assert "tower_commit" in detail


def test_missing_canonical_files_degrade_to_empty_not_to_invention(tmp_path):
    root = tmp_path / "TOWER_V06"
    root.mkdir()
    projection = _build(root)
    assert projection["work"] == []
    assert projection["counts"]["active_work"] == 0
    assert projection["authority_declaration"] == {}
    # sem event_cursor a verificação reprova, então nada incompleto é publicado
    ok, _ = verify_projection(projection)
    assert not ok


# --- domain ownership and Learning filaments ---------------------------------

def test_target_domain_owns_public_projection_without_erasing_method_provenance(tmp_path):
    root = _tower(tmp_path)
    (root / "entities" / "test" / "T-OLY-DEMO.json").write_text(
        json.dumps(
            {
                "id": "T-OLY-DEMO",
                "status": "RESULT",
                "domain": "SCIENCE",
                "target_domain": "OLYMPUS",
                "title": "Olympus target-domain method test",
            }
        ),
        encoding="utf-8",
    )
    payload = json.loads((root / "entities" / "work" / "WORK-A.json").read_text(encoding="utf-8"))
    payload["target_domain"] = "OLYMPUS"
    (root / "entities" / "work" / "WORK-A.json").write_text(json.dumps(payload), encoding="utf-8")

    projection = _build(root)
    test = next(item for item in projection["tests"] if item["id"] == "T-OLY-DEMO")
    work = next(item for item in projection["work"] if item["id"] == "WORK-A")

    for item in (test, work):
        assert item["domain"] == "OLYMPUS"
        assert item["target_domain"] == "OLYMPUS"
        assert item["method_domain"] == "SCIENCE"
        assert item["domain_projection"] == "TARGET_DOMAIN"


def test_interdomain_relations_are_projected_as_learning_filaments(tmp_path):
    root = _tower(tmp_path)
    (root / "entities" / "interdomain").mkdir(parents=True)
    relation_id = "META::INTERDOMAIN::SCIENCE-OLYMPUS-DEMO"
    relation = {
        "id": relation_id,
        "status": "SUPPORTED",
        "relation_type": "METHOD_TRANSFER",
        "source_domains": ["SCIENCE"],
        "target_domains": ["OLYMPUS"],
        "test_refs": ["T-OLY-DEMO"],
        "lesson_refs": ["ML-OLY-DEMO-001"],
    }
    (root / "entities" / "interdomain" / f"{relation_id}.json").write_text(
        json.dumps(relation), encoding="utf-8"
    )
    (root / "indexes" / "interdomain-active.json").write_text(
        json.dumps({"items": [{"id": relation_id}]}), encoding="utf-8"
    )

    projection = _build(root)
    assert projection["counts"]["cross_domain"] == 1
    assert projection["crossDomain"] == [
        {
            **relation,
            "projection_label": "DERIVED_NOT_EVIDENCE",
            "via": "LEARNING_INTERDOMAIN",
        }
    ]
