"""Synthetic history fixtures: current permissions must also gate cached evidence."""
from __future__ import annotations

import json
import sys

import pytest

from runtime.nexo_agent_api.live_tower import build_live_tower_payload
from runtime.nexo_agent_api.memory import Conflict, Memory, Snapshot
from runtime.nexo_agent_api.retrieval import Retrieval


BEFORE = "2026-10-01T12:00:00Z"
AFTER = "2026-10-02T12:00:00Z"
ENTITY = "TEST-ACL-FIXTURE"
UID = "TEST::" + ENTITY
QUERY = "historicalevidencealpha"


def history(tmp_path, engine_cls, roles=None, conflicting=False):
    source = tmp_path / "source"
    entities = source / "entities" / "tests"
    entities.mkdir(parents=True)
    (source / "CONTROL.json").write_text(json.dumps({
        "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}), encoding="utf-8")
    (entities / "unrelated.json").write_text(json.dumps({
        "id": "TEST-PUBLIC-FIXTURE", "kind": "TEST", "status": "READY",
        "question": "Unrelated synthetic control evidence"}), encoding="utf-8")
    path = entities / "historical.json"
    document = {
        "id": ENTITY, "kind": "TEST", "status": "READY", "entity_version": 1,
        "allowed_roles": roles if roles is not None else ["ENGINEER", "EXECUTOR"],
        "question": QUERY + " Original synthetic historical evidence",
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    if conflicting:
        (entities / "conflicting.json").write_text(json.dumps({
            **document, "question": QUERY + " Conflicting synthetic evidence"}), encoding="utf-8")
    tower = tmp_path / "tower.json"
    engine = engine_cls(tmp_path / "cache.sqlite")

    def sync(at):
        raw = json.dumps(build_live_tower_payload(source, updated_at=at)).encode()
        tower.write_bytes(raw)
        engine.sync(Snapshot.read(tower))
        assert tower.read_bytes() == raw

    sync(BEFORE)
    return engine, path, document, sync


@pytest.mark.parametrize("engine_cls", [Memory, Retrieval])
@pytest.mark.parametrize("change", ["revoke", "delete", "remove"])
@pytest.mark.parametrize("include_inactive", [False, True])
def test_history_denies_current_revocation_or_deletion(
        tmp_path, engine_cls, change, include_inactive):
    engine, path, document, sync = history(tmp_path, engine_cls)
    initial = engine.search(QUERY, "ENGINEER", as_of=BEFORE, mode="lexical")
    assert [hit["id"] for hit in initial["hits"]] == [UID]

    if change == "remove":
        path.unlink()
    else:
        if change == "revoke":
            document["allowed_roles"] = ["EXECUTOR"]
        else:
            document["status"] = "DELETED"
        document["entity_version"] = 2
        path.write_text(json.dumps(document), encoding="utf-8")
    sync(AFTER)

    result = engine.search(QUERY, "ENGINEER", as_of=BEFORE, mode="lexical",
                           include_inactive=include_inactive)
    assert result["hits"] == []


@pytest.mark.parametrize("engine_cls", [Memory, Retrieval])
def test_history_remains_available_to_still_authorized_role(tmp_path, engine_cls):
    engine, path, document, sync = history(tmp_path, engine_cls)
    document.update(allowed_roles=["EXECUTOR"], entity_version=2,
                    question=QUERY + " Updated synthetic evidence")
    path.write_text(json.dumps(document), encoding="utf-8")
    sync(AFTER)

    result = engine.search(QUERY, "EXECUTOR", as_of=BEFORE, mode="lexical")
    assert [hit["id"] for hit in result["hits"]] == [UID]
    assert result["hits"][0]["citation"]["entity_version"] == "1"
    assert "Original synthetic historical evidence" in result["hits"][0]["excerpt"]


@pytest.mark.parametrize("engine_cls", [Memory, Retrieval])
def test_current_grant_does_not_expand_historical_permissions(tmp_path, engine_cls):
    engine, path, document, sync = history(tmp_path, engine_cls, roles=["EXECUTOR"])
    document.update(allowed_roles=["ENGINEER", "EXECUTOR"], entity_version=2)
    path.write_text(json.dumps(document), encoding="utf-8")
    sync(AFTER)

    historical = engine.search(QUERY, "ENGINEER", as_of=BEFORE, mode="lexical")
    current = engine.search(QUERY, "ENGINEER", mode="lexical")
    assert historical["hits"] == []
    assert [hit["id"] for hit in current["hits"]] == [UID]


@pytest.mark.parametrize("engine_cls", [Memory, Retrieval])
def test_archival_does_not_revoke_authorized_history(tmp_path, engine_cls):
    engine, path, document, sync = history(tmp_path, engine_cls)
    document.update(status="ARCHIVED", entity_version=2)
    path.write_text(json.dumps(document), encoding="utf-8")
    sync(AFTER)

    result = engine.search(QUERY, "ENGINEER", as_of=BEFORE, mode="lexical")
    assert [hit["id"] for hit in result["hits"]] == [UID]


@pytest.mark.parametrize("engine_cls", [Memory, Retrieval])
def test_current_deletion_cannot_be_bypassed_with_include_inactive(tmp_path, engine_cls):
    engine, path, document, sync = history(tmp_path, engine_cls)
    document.update(status="DELETED", entity_version=2)
    path.write_text(json.dumps(document), encoding="utf-8")
    sync(AFTER)

    result = engine.search(QUERY, "ENGINEER", mode="lexical", include_inactive=True)
    assert result["hits"] == []


@pytest.mark.parametrize("engine_cls", [Memory, Retrieval])
@pytest.mark.parametrize("as_of", [None, BEFORE])
def test_current_identity_conflict_stays_quarantined(tmp_path, engine_cls, as_of):
    engine, path, _, sync = history(tmp_path, engine_cls, conflicting=True)
    control = path.parents[2] / "CONTROL.json"
    control.write_text(json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
                                   "revision_marker": 2}), encoding="utf-8")
    sync(AFTER)

    result = engine.search(QUERY, "ENGINEER", as_of=as_of, mode="lexical", include_inactive=True)
    assert result["hits"] == []


@pytest.mark.parametrize("engine_cls", [Memory, Retrieval])
def test_permission_change_during_search_fails_closed(tmp_path, monkeypatch, engine_cls):
    engine, path, document, sync = history(tmp_path, engine_cls)
    module = sys.modules[engine_cls.__module__]
    query_vector = module.query_vector

    def revoke_during_scoring(text, model):
        document.update(allowed_roles=["EXECUTOR"], entity_version=2)
        path.write_text(json.dumps(document), encoding="utf-8")
        sync(AFTER)
        return query_vector(text, model)

    monkeypatch.setattr(module, "query_vector", revoke_during_scoring)
    with pytest.raises(Conflict, match="Authorization/source changed during retrieval"):
        engine.search(QUERY, "ENGINEER", as_of=BEFORE, mode="hybrid")


@pytest.mark.parametrize("engine_cls", [Memory, Retrieval])
def test_permission_change_during_empty_search_fails_closed(tmp_path, monkeypatch, engine_cls):
    engine, path, document, sync = history(tmp_path, engine_cls)
    eligible = engine.eligible
    changed = False

    def revoke_during_eligibility(doc, role, as_at, include_inactive=False):
        nonlocal changed
        if not changed:
            changed = True
            document.update(allowed_roles=["EXECUTOR"], entity_version=2)
            path.write_text(json.dumps(document), encoding="utf-8")
            sync(AFTER)
        return eligible(doc, role, as_at, include_inactive)

    monkeypatch.setattr(engine, "eligible", revoke_during_eligibility)
    with pytest.raises(Conflict, match="Authorization/source changed during retrieval"):
        engine.search("", "ENGINEER", as_of=BEFORE, mode="lexical")
