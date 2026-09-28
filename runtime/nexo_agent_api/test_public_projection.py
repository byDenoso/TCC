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
    _load_evolution,
    build_public_projection,
    projection_bytes,
    verify_projection,
)
from runtime.nexo_agent_api.tower_paths import entity_path

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
        (entity_path(root, "work", work_id)).write_text(
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
    defaults = {
        "tower_revision": "sha256:" + "b" * 64,
        "tower_file_id": "1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z",
        "generated_at": "2026-09-18T00:00:00Z",
    }
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
    payload = json.loads((entity_path(root, "work", "WORK-A")).read_text(encoding="utf-8"))
    payload["status"] = "RUNNING"
    (entity_path(root, "work", "WORK-A")).write_text(json.dumps(payload), encoding="utf-8")
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


def test_private_handoff_free_text_and_research_links_never_reach_public_projection(tmp_path):
    root = _tower(tmp_path)
    events = root / "events" / "2026-09-27"
    events.mkdir(parents=True)
    (events / "handoff.json").write_text(json.dumps({
        "event_id": "EV-HO-1",
        "handoff_id": "HO-PRIVATE-1",
        "request_id": "REQ-PRIVATE-1",
        "from_role": "ADVISOR",
        "to_role": "EXECUTOR",
        "state": "PENDING",
        "summary_plain": "SEGREDO_HANDOFF_RESUMO",
        "why_it_matters": "SEGREDO_HANDOFF_PORQUE",
        "next_action": "SEGREDO_HANDOFF_ACAO",
        "objective_ref": "OBJ::PRIVATE",
        "evidence_refs": [{"ref": "TEST::PRIVATE"}],
        "source_links": [{
            "label": "SEGREDO_FONTE",
            "url": "https://private.example/research",
            "access_date": "2026-09-27",
            "supports": "SEGREDO_SUPORTE",
        }],
    }), encoding="utf-8")

    raw = projection_bytes(_build(root))
    for secret in (
        b"SEGREDO_HANDOFF_RESUMO",
        b"SEGREDO_HANDOFF_PORQUE",
        b"SEGREDO_HANDOFF_ACAO",
        b"OBJ::PRIVATE",
        b"TEST::PRIVATE",
        b"SEGREDO_FONTE",
        b"private.example",
        b"SEGREDO_SUPORTE",
    ):
        assert secret not in raw


def test_new_guardian_status_maps_publish_safe_yellow_summaries(tmp_path):
    cases = (
        ("PASS_WITH_PENDING_WRITER", 0, []),
        ("YELLOW_WRITER_LAG", 1, ["writer"]),
        ("PASS_WITH_RECOVERY_GAP", 1, ["recovery"]),
        ("PERSISTED_INBOX_PENDING_WRITER", 1, ["inbox"]),
    )
    for index, (status, failing, areas) in enumerate(cases):
        root = _tower(tmp_path / str(index))
        artifact_dir = root / "entities" / "artifact"
        artifact_dir.mkdir()
        report = {
            "created_at": f"2026-09-26T14:{index:02d}:00Z",
            "payload": {
                "status": status,
                "checks": {
                    "tower_write_readback": "PENDING_NEXT_WRITER",
                    "durable_unapplied_count_min": 1,
                    "private_diagnostic": "must never be published",
                },
            },
        }
        (artifact_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")

        projection = _build(root)
        integrity = projection["integrity"]
        assert _core(integrity) == {
            "status": "YELLOW",
            "checked_at": report["created_at"],
            "checks_total": len(report["payload"]["checks"]),
            "checks_failing": failing,
            "failing_areas": areas,
        }
        raw = projection_bytes(projection)
        assert b"PENDING_NEXT_WRITER" not in raw
        assert b"must never be published" not in raw


def test_guardian_thematic_integrity_report_without_checks_still_advances_heartbeat(tmp_path):
    root = _tower(tmp_path)
    artifact_dir = root / "entities" / "artifact"
    artifact_dir.mkdir()
    (artifact_dir / "old.json").write_text(json.dumps({
        "kind": "INTEGRITY_REPORT",
        "source": "GUARDIAO",
        "created_at": "2026-09-26T14:47:20Z",
        "payload": {"status": "PERSISTED_INBOX_PENDING_WRITER", "checks": []},
    }), encoding="utf-8")
    (artifact_dir / "new.json").write_text(json.dumps({
        "kind": "INTEGRITY_REPORT",
        "source": "GUARDIAO",
        "created_at": "2026-09-27T22:08:21Z",
        "payload": {"status": "WARN", "title": "Thematic integrity report"},
    }), encoding="utf-8")

    integrity = _build(root)["integrity"]
    assert _core(integrity) == {
        "status": "YELLOW",
        "checked_at": "2026-09-27T22:08:21Z",
        "checks_total": 0,
        "checks_failing": 0,
        "failing_areas": [],
    }


def test_legacy_olympus_science_method_projects_to_olympus_lane(tmp_path):
    root = _tower(tmp_path)
    (entity_path(root, "test", "T-OLYCAUSE-DEMO")).write_text(
        json.dumps({
            "id": "T-OLYCAUSE-DEMO",
            "status": "RESULT",
            "domain": "SCIENCE",
        }),
        encoding="utf-8",
    )

    projected = next(item for item in _build(root)["tests"] if item["id"] == "T-OLYCAUSE-DEMO")
    assert projected["status_group"] == "DONE"
    assert projected["domain"] == "OLYMPUS"
    assert projected["target_domain"] == "OLYMPUS"
    assert projected["method_domain"] == "SCIENCE"
    assert projected["domain_projection"] == "SEMANTIC_TARGET_DOMAIN"
    assert projected["private"] is True


def test_raw_signal_clusters_are_not_published_without_materialized_incident(tmp_path):
    root = _tower(tmp_path)
    artifacts = root / "entities" / "artifact"
    artifacts.mkdir()
    for artifact_id, source in (("SIGNAL-A", "CHATGPT_TASK_EXECUTOR"), ("SIGNAL-B", "CHATGPT_TASK_EXECUTOR")):
        (artifacts / f"{artifact_id}.json").write_text(json.dumps({
            "id": artifact_id,
            "kind": "LEARNING_SIGNAL",
            "source": source,
            "created_at": "2026-09-26T10:00:00Z",
            "payload": {"signals": [{
                "code": "EMPTY_FRONTIER_ACTIVE_ROADMAP",
                "topic_id": "engineering.nexo.frontier",
                "symptom": "private detail",
            }]},
        }), encoding="utf-8")

    projection = _build(root)
    raw = projection_bytes(projection)
    assert b"EMPTY_FRONTIER_ACTIVE_ROADMAP" not in raw
    assert b"engineering.nexo.frontier" not in raw
    assert b"private detail" not in raw


def test_public_incident_summaries_use_reviewed_copy_or_neutral_fallback_without_raw_joins(tmp_path):
    root = _tower(tmp_path)
    evolution_dir = root / "evolution"
    evolution_dir.mkdir()
    (evolution_dir / "incidents.json").write_text(json.dumps({
        "incidents": [
            {
                "incident_id": "INC-KNOWN",
                "state": "OBSERVED",
                "evidence_count": 2,
                "signal_code": "WRITER_LAG_PATTERN",
                "topic_id": "engineering.nexo.writer.secret",
                "evidence_refs": ["SECRET-REF-A", "SECRET-REF-B"],
                "source_roles": ["GUARDIAO"],
                "private": False,
            },
            {
                "incident_id": "INC-UNKNOWN",
                "state": "OBSERVED",
                "evidence_count": 3,
                "signal_code": "UNREVIEWED_INTERNAL_PATTERN",
                "topic_id": "engineering.nexo.internal.secret",
                "evidence_refs": ["SECRET-REF-C", "SECRET-REF-D", "SECRET-REF-E"],
                "source_roles": ["EXECUTOR"],
                "private": False,
            },
        ]
    }), encoding="utf-8")

    projection = _build(root)
    incidents = {item["incident_id"]: item for item in projection["evolution"]["incidents"]}
    assert incidents["INC-KNOWN"]["summary_pt"].startswith(
        "O sistema detectou atrasos repetidos para registrar e confirmar mudanças."
    )
    assert incidents["INC-UNKNOWN"]["summary_pt"].startswith(
        "O sistema detectou o mesmo problema operacional mais de uma vez e abriu uma investigação para entender a causa."
    )
    for incident in incidents.values():
        assert set(incident) == {
            "incident_id", "state", "evidence_count", "summary_pt", "public_ids", "next_owner", "since", "missing"
        }

    raw = projection_bytes(projection)
    for secret in (
        b"WRITER_LAG_PATTERN",
        b"UNREVIEWED_INTERNAL_PATTERN",
        b"engineering.nexo.writer.secret",
        b"engineering.nexo.internal.secret",
        b"SECRET-REF-A",
        b"SECRET-REF-E",
    ):
        assert secret not in raw


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
    assert manifest["tower_revision"] == "sha256:" + "b" * 64
    assert manifest["tower_file_id"] == "1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z"
    assert manifest["tower_commit"] is None


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


def test_verification_requires_live_tower_provenance(tmp_path):
    root = _tower(tmp_path)
    without_file = _build(root, tower_file_id=None)
    ok, detail = verify_projection(without_file)
    assert not ok
    assert "tower_file_id" in detail

    without_revision = _build(root, tower_revision=None, tower_commit=None)
    ok, detail = verify_projection(without_revision)
    assert not ok
    assert "tower_revision/tower_commit" in detail


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
    (entity_path(root, "test", "T-OLY-DEMO")).write_text(
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
    payload = json.loads((entity_path(root, "work", "WORK-A")).read_text(encoding="utf-8"))
    payload["target_domain"] = "OLYMPUS"
    (entity_path(root, "work", "WORK-A")).write_text(json.dumps(payload), encoding="utf-8")

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
    (entity_path(root, "interdomain", relation_id)).write_text(
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

# --- NEXO ONE entity read model -----------------------------------------------


def test_public_test_projects_prereg_review_lineage_and_safe_execution(tmp_path):
    root = _tower(tmp_path)
    hypothesis_dir = root / "entities" / "hypothesis"
    hypothesis_dir.mkdir(parents=True, exist_ok=True)
    (entity_path(root, "hypothesis", "HYP-RICH")).write_text(json.dumps({
        "id": "HYP-RICH",
        "title": "A public hypothesis",
        "status": "OPEN",
        "domain": "SCIENCE",
        "created_at": "2026-09-27T11:00:00Z",
    }), encoding="utf-8")

    parent = {
        "id": "T-RICH-PARENT",
        "status": "RESULT",
        "domain": "SCIENCE",
        "roadmap_id": "RM-RICH",
        "hypothesis_id": "HYP-RICH",
        "question": "Does the signal survive the frozen null?",
        "prediction": {
            "expected_effect": "Positive residual after the frozen cut.",
            "p_promoted": 0.7,
            "private_note": "SECRET_PREDICTION",
        },
        "null": "No residual beyond the baseline.",
        "rival": "A stable residual remains.",
        "success_criteria": ["Residual exceeds the frozen threshold."],
        "kill_criteria": "Residual is consistent with zero.",
        "prereg_hash": "sha256:" + "a" * 64,
        "prereg_ref": "TOWER_V06/prereg/T-RICH-PARENT.json",
        "claim_boundary": "Applies only to the frozen observable and selection.",
        "limitations": ["One public catalog.", "No claim outside the frozen selection."],
        "created_at": "2026-09-27T12:01:00Z",
        "updated_at": "2026-09-27T14:01:00Z",
        "executed_at": "2026-09-27T12:30:00Z",
        "reproducibility": {
            "battery_id": "BAT-RICH",
            "run_ref": "run-42",
            "runner": "github-actions",
            "log_tail": "SECRET_LOG",
        },
        "contests": [{
            "at": "2026-09-27T13:00:00Z",
            "by": "REFEREE_1",
            "contest_test_id": "T-RICH-CONTEST",
            "reason": "Independent window replication.",
            "refs": ["SECRET_REF"],
        }],
        "reviews": [{
            "at": "2026-09-27T14:00:00Z",
            "referee": "REFEREE_1",
            "contest_test_id": "T-RICH-CONTEST",
            "outcome": "SURVIVED",
            "evidence": "SECRET_EVIDENCE",
        }],
    }
    child = {
        "id": "T-RICH-CHILD",
        "status": "READY",
        "domain": "SCIENCE",
        "roadmap_id": "RM-RICH",
        "hypothesis_id": "HYP-RICH",
        "parent_test_id": "T-RICH-PARENT",
    }
    for record in (parent, child):
        (entity_path(root, "test", record["id"])).write_text(json.dumps(record), encoding="utf-8")

    event_dir = root / "events" / "2026-09-27"
    event_dir.mkdir(parents=True)
    for event_id, entity_name in (
        ("20260927T120000000000Z-parent", "T-RICH-PARENT"),
        ("20260927T120200000000Z-child", "T-RICH-CHILD"),
    ):
        (event_dir / f"{event_id}.json").write_text(json.dumps({
            "event_id": event_id,
            "event_type": "ROADMAP_TEST_FROZEN",
            "entity_kind": "test",
            "entity_name": entity_name,
        }), encoding="utf-8")

    projection = _build(root)
    tests = {item["id"]: item for item in projection["tests"]}
    projected = tests["T-RICH-PARENT"]

    assert projected["entity_kind"] == "TEST"
    assert projected["question"] == parent["question"]
    assert projected["prereg"] == {
        "prediction": {
            "expected_effect": "Positive residual after the frozen cut.",
            "p_promoted": 0.7,
        },
        "null": parent["null"],
        "rival": parent["rival"],
        "criterion": {
            "success": ["Residual exceeds the frozen threshold."],
            "kill": ["Residual is consistent with zero."],
        },
        "hash": parent["prereg_hash"],
        "ref": parent["prereg_ref"],
        "at": parent["created_at"],
    }
    assert projected["review"] == [
        {
            "kind": "CONTEST",
            "by": "REFEREE_1",
            "axis": "Independent window replication.",
            "outcome": "PENDING",
            "at": "2026-09-27T13:00:00Z",
            "contest_test_id": "T-RICH-CONTEST",
        },
        {
            "kind": "VERDICT_REVIEW",
            "by": "REFEREE_1",
            "axis": "Independent window replication.",
            "outcome": "SURVIVED",
            "at": "2026-09-27T14:00:00Z",
            "contest_test_id": "T-RICH-CONTEST",
        },
    ]
    assert projected["limitations"] == parent["limitations"]
    assert projected["claim_boundary"] == parent["claim_boundary"]
    assert projected["execution"] == {
        "at": parent["executed_at"],
        "battery_id": "BAT-RICH",
        "run_ref": "run-42",
        "runner": "github-actions",
    }
    assert projected["parents"] == ["HYP-RICH"]
    assert projected["children"] == ["T-RICH-CHILD"]
    assert tests["T-RICH-CHILD"]["parents"] == ["HYP-RICH", "T-RICH-PARENT"]
    assert tests["T-RICH-CHILD"]["created_at_effective"] == "2026-09-27T12:02:00.000000Z"
    assert tests["T-RICH-CHILD"]["created_at_source"] == "EVENT_FIRST_OBSERVED"
    assert projected["created_at_effective"] == parent["created_at"]
    assert projected["created_at_source"] == "ENTITY"

    hypothesis = next(item for item in projection["hypotheses"] if item["id"] == "HYP-RICH")
    assert hypothesis["entity_kind"] == "HYPOTHESIS"
    assert hypothesis["children"] == ["T-RICH-CHILD", "T-RICH-PARENT"]
    assert hypothesis["parents"] == ["RM-RICH"]

    raw = projection_bytes(projection)
    for secret in (b"SECRET_PREDICTION", b"SECRET_LOG", b"SECRET_REF", b"SECRET_EVIDENCE"):
        assert secret not in raw


def test_private_test_never_gets_rich_scientific_read_model(tmp_path):
    root = _tower(tmp_path)
    record = {
        "id": "T-OLYCAUSE-PRIVATE",
        "status": "RESULT",
        "domain": "SCIENCE",
        "question": "SECRET_PRIVATE_QUESTION",
        "prediction": {"expected_effect": "SECRET_PRIVATE_PREDICTION", "p_promoted": 0.9},
        "null": "SECRET_PRIVATE_NULL",
        "rival": "SECRET_PRIVATE_RIVAL",
        "success_criteria": "SECRET_PRIVATE_SUCCESS",
        "kill_criteria": "SECRET_PRIVATE_KILL",
        "claim_boundary": "SECRET_PRIVATE_BOUNDARY",
        "limitations": ["SECRET_PRIVATE_LIMIT"],
        "contests": [{"reason": "SECRET_PRIVATE_CONTEST", "by": "REFEREE_1"}],
        "reviews": [{"evidence": "SECRET_PRIVATE_EVIDENCE", "referee": "REFEREE_1"}],
        "created_at": "2026-09-27T12:00:00Z",
    }
    (entity_path(root, "test", record["id"])).write_text(json.dumps(record), encoding="utf-8")

    projection = _build(root)
    projected = next(item for item in projection["tests"] if item["id"] == record["id"])
    for field in (
        "question",
        "prereg",
        "review",
        "limitations",
        "claim_boundary",
        "parents",
        "children",
        "execution",
        "created_at_effective",
        "first_observed_at",
    ):
        assert field not in projected
    raw = projection_bytes(projection)
    assert b"SECRET_PRIVATE_" not in raw


def test_roadmaps_are_first_class_with_progress_and_safe_charter(tmp_path):
    root = _tower(tmp_path)
    hypothesis_dir = root / "entities" / "hypothesis"
    hypothesis_dir.mkdir(parents=True, exist_ok=True)
    (entity_path(root, "hypothesis", "HYP-ROAD")).write_text(json.dumps({
        "id": "HYP-ROAD",
        "title": "Roadmap hypothesis",
        "status": "OPEN",
        "domain": "SCIENCE",
    }), encoding="utf-8")

    records = [
        {
            "id": "T-ROAD-1",
            "status": "RESULT",
            "domain": "SCIENCE",
            "roadmap_id": "RM-ROAD",
            "hypothesis_id": "HYP-ROAD",
            "review_state": "CONFIRMED",
        },
        {
            "id": "T-ROAD-2",
            "status": "BLOCKED_INPUT",
            "domain": "SCIENCE",
            "roadmap_id": "RM-ROAD",
            "hypothesis_id": "HYP-ROAD",
            "review_state": "PENDING_REVIEW",
        },
    ]
    for record in records:
        (entity_path(root, "test", record["id"])).write_text(json.dumps(record), encoding="utf-8")

    roadmap = {
        "roadmap_id": "RM-ROAD",
        "campaign_id": "CAMP-ROAD",
        "title": "Roadmap demo",
        "question": "Can the hypothesis survive two independent attacks?",
        "domain": "SCIENCE",
        "subdomain": "COSMOLOGY",
        "priority": "P0",
        "status": "ACTIVE",
        "state": "ACTIVE",
        "claim_boundary": "Only the frozen public tests count.",
        "created_at": "2026-09-27T10:00:00Z",
        "hypothesis_refs": ["HYP-ROAD"],
        "frontier_refs": ["T-ROAD-2"],
        "charter": {
            "status": "CHARTERED",
            "question": "Can the hypothesis survive two independent attacks?",
            "objectives": ["Resolve the frozen question."],
            "budget": {"max_tests": 12, "max_days": 14, "secret_budget": 999},
            "stop": {"success_confirmed": 2, "kill_consecutive_refuted": 3, "secret_stop": 999},
            "renewable": False,
            "review_every_days": 7,
            "chartered_at": "2026-09-27T10:05:00Z",
            "private_note": "SECRET_CHARTER",
        },
        "execution_policy": {"secret": "SECRET_EXECUTION_POLICY"},
    }
    (root / "roadmaps" / "RM-ROAD.json").write_text(json.dumps(roadmap), encoding="utf-8")

    projection = _build(root)
    projected = next(item for item in projection["roadmaps"] if item["id"] == "RM-ROAD")
    assert projected["entity_kind"] == "ROADMAP"
    assert projected["test_ids"] == ["T-ROAD-1", "T-ROAD-2"]
    assert projected["hypothesis_ids"] == ["HYP-ROAD"]
    assert projected["frontier_test_ids"] == ["T-ROAD-2"]
    assert projected["children"] == ["HYP-ROAD"]
    assert projected["progress"] == {
        "total": 2,
        "confirmed": 1,
        "refuted": 0,
        "in_review": 1,
        "blocked": 1,
        "ready": 0,
        "resumable": 0,
        "result": 1,
        "frontier": 1,
    }
    assert projected["charter"] == {
        "status": "CHARTERED",
        "question": roadmap["charter"]["question"],
        "objectives": ["Resolve the frozen question."],
        "budget": {"max_tests": 12, "max_days": 14},
        "stop": {"success_confirmed": 2, "kill_consecutive_refuted": 3},
        "renewable": False,
        "review_every_days": 7,
        "chartered_at": "2026-09-27T10:05:00Z",
    }
    assert projection["counts"]["roadmaps"] >= 1
    raw = projection_bytes(projection)
    assert b"SECRET_CHARTER" not in raw
    assert b"SECRET_EXECUTION_POLICY" not in raw
    assert b"secret_budget" not in raw
    assert b"secret_stop" not in raw


def test_public_activity_is_sanitized_and_role_oriented(tmp_path):
    root = _tower(tmp_path)
    (entity_path(root, "test", "T-ACT")).write_text(json.dumps({
        "id": "T-ACT",
        "status": "RESULT",
        "domain": "SCIENCE",
    }), encoding="utf-8")
    event_dir = root / "events" / "2026-09-27"
    event_dir.mkdir(parents=True)
    events = [
        ("20260927T120000000000Z-a", "ROADMAP_TEST_FROZEN", "test", "T-ACT"),
        ("20260927T121000000000Z-b", "RESULT_CONTESTED", "test", "T-ACT"),
        ("20260927T122000000000Z-c", "INTEGRITY_REPORT_RECORDED", "artifact", "INTEGRITY_REPORT::PRIVATE"),
    ]
    for event_id, event_type, kind, entity_name in events:
        (event_dir / f"{event_id}.json").write_text(json.dumps({
            "event_id": event_id,
            "event_type": event_type,
            "entity_kind": kind,
            "entity_name": entity_name,
            "private_note": "SECRET_EVENT",
        }), encoding="utf-8")

    projection = _build(root)
    assert projection["activity"] == [
        {
            "event_type": "ROADMAP_TEST_FROZEN",
            "role": "EXECUTOR",
            "at": "2026-09-27T12:00:00.000000Z",
            "entity_id": "T-ACT",
            "entity_kind": "TEST",
        },
        {
            "event_type": "RESULT_CONTESTED",
            "role": "REFUTADOR",
            "at": "2026-09-27T12:10:00.000000Z",
            "entity_id": "T-ACT",
            "entity_kind": "TEST",
        },
        {
            "event_type": "INTEGRITY_REPORT_RECORDED",
            "role": "GUARDIAO",
            "at": "2026-09-27T12:20:00.000000Z",
        },
    ]
    assert b"SECRET_EVENT" not in projection_bytes(projection)



def _core(integrity):
    """Guardião fields only; the live re-check keys are covered in test_projection_drift."""
    return {k: v for k, v in integrity.items() if k not in {"live_areas", "live_checked_at", "quiet_tasks", "report_age_h"}}
