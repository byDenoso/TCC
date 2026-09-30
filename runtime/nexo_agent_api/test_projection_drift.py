from runtime.nexo_agent_api.public_projection import _collapse_bulk_activity, _with_semantics
from tests.test_scientific_integrity import fixture, install_fixture_catalog, store_fixture_test, save, NOW, END


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


def test_recipe_bug_keeps_test_chances_opens_circuit_and_success_closes(tmp_path, monkeypatch):
    import json
    from runtime.nexo_agent_api.evolution import battery_status_requests, battery_requests, classify_failure
    from runtime.nexo_agent_api.tower_apply import apply_requests
    from runtime.nexo_agent_api.tower_paths import entity_path

    assert classify_failure("Traceback (most recent call last):\nKeyError: 'zHD'") == "RECIPE_BUG"
    assert classify_failure("urlopen error [Errno 110] Connection timed out") == "TRANSIENT"
    assert classify_failure("input obrigatório ausente") == "TEST"

    root = tmp_path
    install_fixture_catalog(tmp_path / 'recipes', monkeypatch, 'rcp')
    save(root, 'CONTROL.json', {'mode': 'ACTIVE'})
    for tid in ("T-1", "T-2"):
        store_fixture_test(root, tid, 'rcp')
    requests = battery_requests({'created_at': NOW}, {'battery_id': 'bat-fixture-one', 'tests': [
        {'test_id': tid, 'recipe': 'rcp', 'params': {'seed': 17}} for tid in ('T-1', 'T-2')]}, root)
    assert all(row['accepted'] for row in apply_requests(root, requests))

    bug = "Traceback (most recent call last):\nKeyError: 'zHD'"
    body = {"battery_id": "bat-fixture-one", "status": "DONE", 'run_ref': 'actions/runs/123', 'completed_at': END,
            "results": [{"test_id": t, "ok": False, "log_tail": bug} for t in ("T-1", "T-2")]}
    reqs = battery_status_requests({'_inbox_source': 'RUNNER_OBSERVATION', "created_at": END}, body, root, lambda *a, **k: [])
    fails = [r for r in reqs if r.get("event_type") == "TEST_RUNTIME_FAILURE"]
    assert all(r["changes"]["status"] == "READY" and r["changes"]["runtime_failure_count"] == 0 for r in fails)
    health = next(r for r in reqs if r.get("document") == "evolution/recipe_health.json")["merge"]["recipes"]["rcp"]
    assert health["state"] == "OPEN" and health["consecutive_bugs"] == 2
    assert all(row['accepted'] for row in apply_requests(root, reqs))
    retry = battery_requests({'created_at': END}, {'battery_id': 'bat-fixture-two', 'tests': [{'test_id': 'T-1', 'recipe': 'rcp', 'params': {'seed': 17}}]}, root)
    assert all(row['accepted'] for row in apply_requests(root, retry))
    spec = json.loads((root / 'evolution/batteries.json').read_text())['batteries'][-1]['tests'][0]
    body = {'battery_id': 'bat-fixture-two', 'status': 'DONE', 'run_ref': 'actions/runs/124', 'completed_at': END,
            'results': [{'test_id': 'T-1', 'ok': True, 'attempt_id': spec['attempt_id'], 'recipe_sha256': spec['recipe_sha256'],
                         'result': {'verdict': 'INCONCLUSIVE', 'summary': 'Isolated fixture'}}]}
    reqs = battery_status_requests({'_inbox_source': 'RUNNER_OBSERVATION', 'created_at': END}, body, root, lambda *a, **k: [])
    health = next(row for row in reqs if row.get('document') == 'evolution/recipe_health.json')['merge']['recipes']['rcp']
    assert health['state'] == 'CLOSED' and health['consecutive_bugs'] == 0


def _family_root(tmp_path):
    import json
    from runtime.nexo_agent_api.evolution import family_charter_requests
    from runtime.nexo_agent_api.tower_paths import entity_path

    root = tmp_path
    save(root, 'CONTROL.json', {'mode': 'ACTIVE'})
    (root / "roadmaps").mkdir()
    (root / "roadmaps" / "RM-X.json").write_text(json.dumps({"roadmap_id": "RM-X", "status": "ACTIVE"}))
    (root / "evolution").mkdir()
    tpl = {"display_name": "Robustez por faixa", "question": "q?", "null": "n", "rival": "r", "method": "m",
           "dataset_and_selection": "d", "success_criteria": "s", "kill_criteria": "k", "prediction": {"p_promoted": 0.5}}
    body = {"family_id": "de-bands", "roadmap_id": "RM-X", "recipe": "rcp_one", "domain": "science",
            "template": tpl, "instances": [{"label": f"b{i}", "params": {"band": [0, i]}} for i in range(3)]}
    [req] = family_charter_requests({"source": "TEST"}, body, root)
    (root / "evolution" / "families.json").write_text(json.dumps(req["merge"]))
    return root, entity_path


def test_family_expands_then_requires_bound_inputs_before_dispatch(tmp_path, monkeypatch):
    import json
    from runtime.nexo_agent_api.evolution import family_battery_items, family_instance_items, data_binding_requests
    from runtime.nexo_agent_api.tower_apply import apply_requests
    from runtime.nexo_agent_api.inbox_apply import proposal_to_requests

    root, entity_path = _family_root(tmp_path)
    install_fixture_catalog(tmp_path / 'recipes', monkeypatch, 'rcp_one')
    items = family_instance_items(root)
    assert len(items) == 3 and items[0]["payload"]["recipe_params"] == {"band": [0, 0]}
    for item in items:  # what the Writer does with each robot proposal
        reqs = proposal_to_requests(item, root)
        test = reqs[0]["changes"]
        assert test["status"] == "BLOCKED_INPUT" and test["family_id"] == "DE-BANDS" and test["recipe_params"]
        path = entity_path(root, "test", reqs[0]["entity_name"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": reqs[0]["entity_name"], "kind": "TEST", 'entity_version': 1, **test}))
        bindings = data_binding_requests({}, {'test_id': reqs[0]['entity_name'], **fixture()['data_binding']}, root)
        assert all(row['accepted'] for row in apply_requests(root, bindings))
    assert family_instance_items(root) == []  # every cell already has its test
    [battery] = family_battery_items(root)
    assert battery["kind"] == "TEST_BATTERY" and len(battery["payload"]["tests"]) == 3

    (root / "evolution" / "recipe_health.json").write_text(json.dumps({"recipes": {"rcp_one": {"state": "OPEN"}}}))
    [probe] = family_battery_items(root)
    assert len(probe["payload"]["tests"]) == 1  # half-open circuit: one probe only


def test_incomplete_contract_becomes_draft(tmp_path):
    from runtime.nexo_agent_api.inbox_apply import proposal_to_requests

    item = {"kind": "HYPOTHESIS_PROPOSAL", "payload": {"test_id": "T-DRAFT", "display_name": "Sem método", "domain": "science",
            "question": "q?", "success_criteria": "s", "kill_criteria": "k"}}
    [req, *_] = proposal_to_requests(item, tmp_path)
    assert req["changes"]["status"] == "DRAFT" and "método" in req["changes"]["draft_reason"]


def test_battery_takes_three_quarters_of_the_ready_queue(tmp_path, monkeypatch):
    import json
    from runtime.nexo_agent_api.evolution import family_battery_items
    from runtime.nexo_agent_api.tower_paths import entity_path
    install_fixture_catalog(tmp_path / 'recipes', monkeypatch, 'rcp_one')

    for n, expected in ((20, 15), (8, 6), (4, 4), (40, 20)):
        root = tmp_path / f"r{n}"
        (root / "evolution").mkdir(parents=True)
        for i in range(n):
            store_fixture_test(root, f'T-{i:02d}', 'rcp_one', family_id='F')
        [battery] = family_battery_items(root)
        assert len(battery["payload"]["tests"]) == expected, (n, len(battery["payload"]["tests"]))


def test_recipe_bind_makes_a_blocked_test_dispatchable_without_family(tmp_path, monkeypatch):
    import json
    from runtime.nexo_agent_api.evolution import family_battery_items, recipe_bind_requests
    from runtime.nexo_agent_api.tower_paths import entity_path
    from runtime.nexo_agent_api.tower_apply import apply_requests
    from runtime.nexo_agent_api.inbox_apply import ProposalError
    import pytest
    install_fixture_catalog(tmp_path / 'recipes', monkeypatch, 'rcp_one')
    save(tmp_path, 'CONTROL.json', {'mode': 'ACTIVE'})

    path = entity_path(tmp_path, "test", "T-BOUND")
    path.parent.mkdir(parents=True, exist_ok=True)
    test = store_fixture_test(tmp_path, 'T-BOUND', status='BLOCKED_INPUT', state='BLOCKED_INPUT', origin_kind='DENER_DIRECTED')
    test.pop('recipe'); test.pop('recipe_params'); path.write_text(json.dumps(test))
    with pytest.raises(ProposalError, match='RECIPE_BINDING_INVALID'):
        recipe_bind_requests({}, {"test_id": "T-BOUND", "recipe": "Bad Name", "params": {}}, tmp_path)
    [req] = recipe_bind_requests({"created_at": "2026-09-29T05:00:00Z"}, {"test_id": "T-BOUND", "recipe": "rcp_one", "params": {"a": 1}}, tmp_path)
    assert req["changes"]["status"] == "READY" and req["changes"]["recipe_params"] == {"a": 1}
    assert all(row['accepted'] for row in apply_requests(tmp_path, [req]))
    [battery] = family_battery_items(tmp_path)
    assert [t["test_id"] for t in battery["payload"]["tests"]] == ["T-BOUND"]


def test_robot_contests_positive_family_result_with_union3(tmp_path, monkeypatch):
    import json
    from runtime.nexo_agent_api.evolution import family_battery_items, family_contest_items, data_binding_requests
    from runtime.nexo_agent_api.tower_apply import apply_requests
    from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
    from runtime.nexo_agent_api.tower_paths import entity_path
    install_fixture_catalog(tmp_path / 'recipes', monkeypatch, 'w0wa_bao_sn_multi')
    save(tmp_path, 'CONTROL.json', {'mode': 'ACTIVE'})

    parent = {"id": "FAM-X-A", "kind": "TEST", "status": "DONE", "verdict": "PROMOTED", "review_state": "PENDING_REVIEW",
              "family_id": "X", "recipe": "w0wa_bao_sn_multi", "domain": "SCIENCE", "question": "q?", "null": "n", "rival": "r",
              "method": "m", "success_criteria": "s", "kill_criteria": "k",
              "recipe_params": {"mode": "redshift_jackknife", "compilations": ["pantheon_plus", "des_sn5yr"], "bands": [[0, 0.2]]}}
    path = entity_path(tmp_path, "test", "FAM-X-A")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(parent))
    [item] = family_contest_items(tmp_path)
    assert item["payload"]["contest_test"]["recipe_params"]["compilations"] == ["pantheon_plus", "union3"]
    reqs = proposal_to_requests(item, tmp_path)
    attack = next(r for r in reqs if r.get("entity_name", "").startswith("CONTEST-"))
    assert attack["changes"]["status"] == "BLOCKED_INPUT" and attack["changes"]["recipe"] == "w0wa_bao_sn_multi"
    assert any(r.get("entity_name") == "FAM-X-A" and r["changes"]["review_state"] == "CONTESTED" for r in reqs)
    apath = entity_path(tmp_path, "test", attack["entity_name"])
    apath.write_text(json.dumps({"id": attack["entity_name"], "kind": "TEST", 'entity_version': 1, **attack["changes"]}))
    bindings = data_binding_requests({}, {'test_id': attack['entity_name'], **fixture()['data_binding']}, tmp_path)
    assert all(row['accepted'] for row in apply_requests(tmp_path, bindings))
    path.write_text(json.dumps({**parent, "contests": [{"n": 1}]}))
    assert family_contest_items(tmp_path) == []  # attacked once already
    [battery] = family_battery_items(tmp_path)
    assert [t["test_id"] for t in battery["payload"]["tests"]] == [attack["entity_name"]]


def test_robot_spawns_replication_family_when_few_are_active(tmp_path):
    import json
    from runtime.nexo_agent_api.evolution import family_charter_requests, family_spawn_items

    (tmp_path / "evolution").mkdir()
    (tmp_path / "roadmaps").mkdir()
    (tmp_path / "roadmaps" / "RM-A.json").write_text(json.dumps({"status": "ACTIVE"}))
    tpl = {k: "x" for k in ("display_name", "question", "null", "rival", "method", "dataset_and_selection", "success_criteria", "kill_criteria")}
    fam = {"family_id": "F1", "roadmap_id": "RM-A", "recipe": "w0wa_bao_sn_multi", "domain": "SCIENCE", "template": tpl, "state": "CLOSED",
           "close_reason": "SUCCESS", "stop": {"kill_rejected": 2, "success_promoted": 2},
           "instances": [{"label": "A", "params": {"mode": "redshift_jackknife", "compilations": ["pantheon_plus", "des_sn5yr"]}}]}
    (tmp_path / "evolution" / "families.json").write_text(json.dumps({"families": {"F1": fam}}))
    [item] = family_spawn_items(tmp_path)
    assert item["payload"]["family_id"] == "F1-R" and len(item["payload"]["instances"]) == 3
    [req] = family_charter_requests(item, item["payload"], tmp_path)
    fams = req["merge"]["families"]
    assert fams["F1-R"]["state"] == "ACTIVE"
    (tmp_path / "evolution" / "families.json").write_text(json.dumps({"families": {**fams, "F1-R": {**fams["F1-R"], "state": "CLOSED", "close_reason": "SUCCESS"}}}))
    assert family_spawn_items(tmp_path) == []  # a successful replication is not replicated again


def test_learning_loop_promotes_a_rule_that_beats_the_baseline_on_the_holdout():
    from runtime.nexo_agent_api import discovery

    def t(i, units, verdict):
        return {"id": f"T{i}", "recipe": "r", "recipe_params": {"mode": "m", "compilations": ["a", "b"], "bands": [[0, 1]] * units},
                "verdict": verdict, "executed_at": f"2026-09-{10 + i // 3:02d}T0{i % 3}:00:00Z"}

    # 3 bands always decide; 5 bands always end inconclusive: a clean, learnable trait
    tests = [t(i, 3 if i % 2 else 5, "PROMOTED" if i % 2 else "INCONCLUSIVE") for i in range(40)]
    out = discovery.learning_loop(tests)
    rule = next(r for r in out["rules"] if r["feature"] == "units" and r["value"] == "5")
    assert rule["state"] == "ACTIVE" and rule["gain"] >= discovery.MIN_GAIN and rule["op"] == "CREATE"
    again = discovery.learning_loop(tests, out)
    assert [r["value"] for r in again["rules"] if r["feature"] == "units"] == ["5"]  # MERGE, no duplicate
    assert discovery.learning_loop(tests[:10])["evaluated"]["note"]
    fresh, stale = t(1, 3, None), t(0, 5, None)
    assert discovery.information_value(fresh, again["rules"]) > discovery.information_value(stale, again["rules"])


def test_search_space_and_autonomy_metrics():
    from runtime.nexo_agent_api import discovery

    tests = [{"id": f"F{i}", "family_id": "FAM", "verdict": "PROMOTED" if i < 2 else "INCONCLUSIVE", "executed_at": "2099-01-01T00:00:00Z"} for i in range(6)]
    space = discovery.search_space(tests)["FAM"]
    assert space["comparisons"] == 6 and space["positives"] == 2 and space["expected_by_chance"] == 0.3
    from datetime import datetime, timezone
    m = discovery.autonomy_metrics(tests, now=datetime(2099, 1, 1, 6, tzinfo=timezone.utc))
    assert m["results"] == 6 and m["robot_share"] == 1.0 and m["decisive_rate"] == round(2 / 6, 3)


def test_autonomy_metrics_reads_naive_timestamps_as_utc():
    from datetime import datetime, timezone
    from runtime.nexo_agent_api import discovery

    tests = [{"id": "N", "verdict": "PROMOTED", "executed_at": "2099-01-01T01:00:00", "created_at_effective": "2099-01-01 00:00:00"}]
    m = discovery.autonomy_metrics(tests, now=datetime(2099, 1, 1, 2, tzinfo=timezone.utc))
    assert m["results"] == 1 and m["median_hours_to_result"] == 1.0


def test_killed_family_spawns_prior_variant_and_generations_stop():
    import json, tempfile
    from pathlib import Path
    from runtime.nexo_agent_api.evolution import family_spawn_items

    root = Path(tempfile.mkdtemp())
    (root / "evolution").mkdir()
    (root / "roadmaps").mkdir()
    (root / "roadmaps" / "RM.json").write_text(json.dumps({"status": "ACTIVE"}))
    tpl = {"display_name": "x"}
    cell = {"label": "A", "params": {"mode": "bao_tracer_jackknife", "compilations": ["pantheon_plus", "union3"]}}
    base = {"roadmap_id": "RM", "recipe": "w0wa_bao_sn_multi", "domain": "SCIENCE", "template": tpl, "state": "CLOSED", "instances": [cell]}
    (root / "evolution" / "families.json").write_text(json.dumps({"families": {"K": {**base, "family_id": "K", "close_reason": "KILL"}}}))
    [item] = family_spawn_items(root)
    assert item["payload"]["family_id"] == "K-P" and len(item["payload"]["instances"]) == 3
    assert {c["params"]["priors"]["omega_m"][0] for c in item["payload"]["instances"]} == {0.30, 0.315, 0.33}
    (root / "evolution" / "families.json").write_text(json.dumps({"families": {"K-R-P": {**base, "family_id": "K-R-P", "close_reason": "KILL"}}}))
    assert family_spawn_items(root) == []  # two generations deep: stop
