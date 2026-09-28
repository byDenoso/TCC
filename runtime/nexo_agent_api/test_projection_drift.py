from runtime.nexo_agent_api.public_projection import _collapse_bulk_activity, _with_semantics


def test_bulk_activity_collapses_with_count():
    rows = [{"event_type": "SEMANTIC_BACKFILLED", "role": "LEARNER", "at": f"2026-09-28T10:0{i}:00Z", "entity_id": f"T{i}"} for i in range(5)]
    rows.append({"event_type": "TEST_RESULT_RECORDED", "role": "EXECUTOR", "at": "2026-09-28T10:09:00Z"})
    out = _collapse_bulk_activity(rows)
    assert len(out) == 2 and out[0]["count"] == 5 and "entity_id" not in out[0]


def test_top_level_display_name_reaches_semantic():
    projected = _with_semantics({"id": "T-X", "entity_kind": "TEST", "status": "READY"}, {"id": "T-X", "display_name": "Nome curto"})
    assert projected["semantic"].get("display_name") == "Nome curto"


def test_invalid_topic_falls_back_to_valid_subdomain():
    from runtime.nexo_agent_api.semantics import resolve
    sem = resolve({"semantic": {"topic_id": "science.cosmology.dark_matter.nao_existe", "subdomain_id": "science.cosmology.dark_matter"}})
    assert sem["subdomain_id"] == "science.cosmology.dark_matter" and sem["basis"] == "EXPLICIT"


def test_archived_and_checkpointed_groups():
    from runtime.nexo_agent_api.semantics import status_group
    assert status_group("ARCHIVED") == "DONE" and status_group("CHECKPOINTED") == "RUNNING"
