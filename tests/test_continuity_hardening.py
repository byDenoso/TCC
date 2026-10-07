"""Regression cases for existing NEXO contracts; synthetic, never science results."""
import copy
import json
from pathlib import Path

import pytest

from tests.test_continuity_enxame import Lab, SPEC, SCOPE
from runtime.nexo_agent_api import continuity_cli, enxame
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, materialize_live_tower
from runtime.nexo_agent_api.memory import digest


@pytest.fixture
def lab(tmp_path):
    return Lab(tmp_path / "tower")


def persist_snapshot(lab, tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_bytes(lab.raw)
    return path


def revise_source(lab, tmp_path):
    root, _ = materialize_live_tower(lab.raw, tmp_path / "source-revision")
    (root / "contracts/SYNTHETIC.json").write_text(json.dumps({"purpose": "A new synthetic source revision"}))
    lab.raw = json.dumps(build_live_tower_payload(root, base=lab.tower)).encode()


@pytest.mark.parametrize("defect", ["OBJECAO", "CONFLITO"])
def test_registration_confirmation_requires_current_quorum(lab, defect):
    lab.mature()
    assert not lab.freeze()["rejected"]
    assert not lab.register()["rejected"]
    test = next(v["value"] for p, v in lab.tower["files"].items() if p.startswith("entities/test/"))
    assert not lab.event("A3", defect, {"text": "New material defect after preparation"}, sv=1)["rejected"]
    assert not lab.view()["cards"]["card-1"]["quorum"]
    result = lab.event("A5", "REGISTRO", {
        "test_id": test["id"],
        "readback": {"source_revision": lab.tower["revision"],
                     "entity_version": test["entity_version"], "content_sha256": digest(test)},
    }, sv=1)
    assert result["rejected"], "A correct readback does not close an open scientific objection"
    assert lab.view()["cards"]["card-1"]["registration"] is None
    assert not lab.view()["execution_triggered"]


@pytest.mark.parametrize("blank", [" \n\t", [" "], {"description": "\t"}])
@pytest.mark.parametrize("location", ["essential", "requirement", "extra_required"])
def test_empty_content_remains_an_explicit_gap(lab, blank, location):
    spec = copy.deepcopy(SPEC)
    if location == "essential":
        name = "kill_criteria"
        spec[name] = blank
    elif location == "requirement":
        name = "threshold"
        spec["requirements"][name] = {"status": "DEFINED", "value": blank}
    else:
        name = "additional_control"
        spec["requirements"][name] = {"required": True, "status": "DEFINED", "value": blank}
    assert not lab.event("A1", "CLAIM", {"claim": "Synthetic claim"})["rejected"]
    assert not lab.event("A2", "SPEC", {"spec": spec}, sv=1)["rejected"]
    assert not lab.event("A3", "ENDOSSO", {"rationale": "Synthetic partial review"}, sv=1)["rejected"]
    assert not lab.event("A1", "ENDOSSO", {"rationale": "Synthetic partial review"}, sv=1)["rejected"]
    assert name in lab.view()["cards"]["card-1"]["gaps"]
    result = lab.event("A5", "FREEZE", {"spec_sha256": digest(spec)}, sv=1)
    assert result["rejected"]


@pytest.mark.parametrize("value", [0, 0.0, False, {"value": 0}])
def test_defined_zero_is_not_a_missing_value(value):
    spec = copy.deepcopy(SPEC)
    spec["requirements"]["cost"] = {"status": "DEFINED", "value": value}
    assert "cost" not in enxame.gap_names(spec)


def test_replay_of_historical_memory_does_not_revalidate_changed_source(lab, tmp_path):
    body = {"event_id": "historical", "scope": "WORK", "category": "OPERATIONAL_LESSON",
            "text": "A source-linked operational observation", "sources": [lab.source],
            "applicability": "Only the cited synthetic source revision"}
    assert not lab.apply("NEXO_MEMORY_ENTRY", "CHATGPT", body)["rejected"]
    revise_source(lab, tmp_path)
    result = lab.apply("NEXO_MEMORY_ENTRY", "CHATGPT", body)
    assert not result["rejected"], result
    entries = [v["value"] for v in lab.tower["files"].values() if v.get("value", {}).get("kind") == "NEXO_MEMORY_ENTRY"]
    assert len(entries) == 1 and entries[0]["payload"]["sources"] == [lab.source]
    assert lab.apply("NEXO_MEMORY_ENTRY", "CHATGPT", {**body, "event_id": "new-stale-source"})["rejected"]
    assert lab.apply("NEXO_MEMORY_ENTRY", "CHATGPT", {**body, "text": "Conflicting retry"})["rejected"]
    assert lab.apply("NEXO_MEMORY_ENTRY", "DENER", body)["rejected"]


def test_replay_of_project_progress_preserves_historical_source(lab, tmp_path):
    created = {"event_id": "created", "project_id": "general", "title": "Synthetic project",
               "scope": "WORK", "action": "CREATED", "text": "Start", "expected_previous": None}
    assert not lab.apply("NEXO_PROJECT_EVENT", "CHATGPT", created)["rejected"]
    previous = next(v["value"]["id"] for v in lab.tower["files"].values() if v.get("value", {}).get("kind") == "NEXO_PROJECT_EVENT")
    progress = {**created, "event_id": "progress", "action": "PROGRESS", "text": "Material work",
                "expected_previous": previous, "sources": [lab.source]}
    assert not lab.apply("NEXO_PROJECT_EVENT", "CHATGPT", progress)["rejected"]
    revise_source(lab, tmp_path)
    assert not lab.apply("NEXO_PROJECT_EVENT", "CHATGPT", progress)["rejected"]
    assert len([v for v in lab.tower["files"].values() if v.get("value", {}).get("kind") == "NEXO_PROJECT_EVENT"]) == 2


def test_reader_uses_one_validated_source_read(lab, tmp_path, monkeypatch):
    lab.mature()
    path = persist_snapshot(lab, tmp_path)
    original = Path.read_bytes
    reads = []
    def counted(p):
        if p == path:
            reads.append(p)
        return original(p)
    monkeypatch.setattr(Path, "read_bytes", counted)
    result = continuity_cli.inspect(path)
    assert len(reads) == 1, "Projection must derive from the same bytes that supplied source_revision"
    assert result["source_revision"] == lab.tower["revision"]
    assert result["total_events"] == 4


def test_positive_page_requires_pinned_revision(lab, tmp_path):
    lab.mature()
    path = persist_snapshot(lab, tmp_path)
    with pytest.raises(ValueError, match="CONTINUITY_REVISION_REQUIRED"):
        continuity_cli.inspect(path, after=1)


def test_page_rejects_source_change(lab, tmp_path):
    lab.mature()
    path = persist_snapshot(lab, tmp_path)
    first = continuity_cli.inspect(path, limit=2)
    assert not lab.event("A4", "SINAL", {"weight": 1})["rejected"]
    path.write_bytes(lab.raw)
    with pytest.raises(ValueError, match="CONTINUITY_REVISION_CHANGED"):
        continuity_cli.inspect(path, after=2, expected_revision=first["source_revision"])


def test_pinned_pages_cover_each_event_once(lab, tmp_path):
    lab.mature()
    path = persist_snapshot(lab, tmp_path)
    first = continuity_cli.inspect(path, limit=2)
    second = continuity_cli.inspect(path, after=first["next_offset"], limit=2,
                                    expected_revision=first["source_revision"])
    ids = [e["event_id"] for e in first["events"] + second["events"]]
    assert len(ids) == len(set(ids)) == 4 and second["next_offset"] is None
    assert first["next_cursor"]["expected_revision"] == first["source_revision"]


@pytest.mark.parametrize("kwargs", [{"after": -1}, {"after": True}, {"limit": 0}, {"limit": 1001}, {"limit": True}])
def test_reader_bounds_are_enforced_at_function_boundary(lab, tmp_path, kwargs):
    with pytest.raises(ValueError, match="CONTINUITY_PAGINATION_INVALID"):
        continuity_cli.inspect(persist_snapshot(lab, tmp_path), **kwargs)


def test_logical_agent_endorsements_do_not_claim_human_review(lab):
    lab.mature()
    assert lab.view()["independent_human_reviewers"] == 0
