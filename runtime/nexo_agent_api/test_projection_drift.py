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


def test_recipe_bug_keeps_test_chances_opens_circuit_and_success_closes(tmp_path):
    import json
    from runtime.nexo_agent_api.evolution import battery_status_requests, classify_failure
    from runtime.nexo_agent_api.tower_paths import entity_path

    assert classify_failure("Traceback (most recent call last):\nKeyError: 'zHD'") == "RECIPE_BUG"
    assert classify_failure("urlopen error [Errno 110] Connection timed out") == "TRANSIENT"
    assert classify_failure("input obrigatório ausente") == "TEST"

    root = tmp_path
    for tid in ("T-1", "T-2"):
        path = entity_path(root, "test", tid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": tid, "kind": "TEST", "status": "RUNNING", "execution_recipe": "rcp", "entity_version": 1}))
    (root / "evolution").mkdir()
    (root / "evolution" / "batteries.json").write_text(json.dumps({"batteries": [{"id": "b1", "status": "DISPATCHED"}]}))

    bug = "Traceback (most recent call last):\nKeyError: 'zHD'"
    body = {"battery_id": "b1", "status": "DONE", "results": [{"test_id": t, "ok": False, "log_tail": bug} for t in ("T-1", "T-2")]}
    reqs = battery_status_requests({"created_at": "2026-09-28T23:00:00Z"}, body, root, lambda *a, **k: [])
    fails = [r for r in reqs if r.get("event_type") == "TEST_RUNTIME_FAILURE"]
    assert all(r["changes"]["status"] == "READY" and r["changes"]["runtime_failure_count"] == 0 for r in fails)
    health = next(r for r in reqs if r.get("document") == "evolution/recipe_health.json")["merge"]["recipes"]["rcp"]
    assert health["state"] == "OPEN" and health["consecutive_bugs"] == 2
