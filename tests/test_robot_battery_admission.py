"""The automatic proposal generator must satisfy the real admission contract."""
from datetime import datetime, timedelta, timezone
import copy
import re

from runtime.nexo_agent_api import evolution as e
from runtime.nexo_agent_api.tower_apply import apply_requests
from tests.test_scientific_integrity import install_fixture_catalog, save, store_fixture_test

NOW = datetime(2026, 9, 30, 20, 53, 10, tzinfo=timezone.utc)


def setup(root, recipes, monkeypatch, name="audit_recipe"):
    install_fixture_catalog(recipes, monkeypatch, name)
    save(root, "CONTROL.json", {"mode": "ACTIVE", "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"})
    return store_fixture_test(root, "TEST-ROBOT", name)


def test_generated_battery_passes_real_admission_and_reserves_once(tmp_path, monkeypatch):
    root = tmp_path / "tower"
    setup(root, tmp_path / "recipes", monkeypatch, "fixture_bao_sn_multi")
    item = e.family_battery_items(root, NOW)[0]
    assert re.fullmatch(r"[a-z0-9-]{3,48}", item["payload"]["battery_id"])
    requests = e.battery_requests(item, item["payload"], root)
    receipts = apply_requests(root, requests)
    assert all(r["accepted"] for r in receipts), receipts
    assert e.family_battery_items(root, NOW + timedelta(minutes=5)) == []
    assert e.battery_requests(item, item["payload"], root) == []


def test_same_proposal_is_stable_across_days_and_unrelated_versions(tmp_path, monkeypatch):
    root = tmp_path / "tower"
    test = setup(root, tmp_path / "recipes", monkeypatch)
    first = e.family_battery_items(root, NOW)[0]["payload"]
    test["entity_version"] += 1
    test["semantic"] = {"question_plain": "An unrelated display update"}
    save(root, "entities/test/TEST-ROBOT.json", test)
    later = e.family_battery_items(root, NOW + timedelta(days=1))[0]["payload"]
    assert first == later


def test_long_recipe_name_does_not_overflow_battery_id(tmp_path, monkeypatch):
    root = tmp_path / "tower"
    setup(root, tmp_path / "recipes", monkeypatch, "a_" * 20)
    item = e.family_battery_items(root, NOW)[0]
    assert len(item["payload"]["battery_id"]) == 40
    assert e.battery_requests(item, item["payload"], root)


def test_retry_gets_new_identity_only_after_previous_attempt_ends(tmp_path, monkeypatch):
    root = tmp_path / "tower"
    test = setup(root, tmp_path / "recipes", monkeypatch)
    first = e.family_battery_items(root, NOW)[0]
    receipts = apply_requests(root, e.battery_requests(first, first["payload"], root))
    assert all(r["accepted"] for r in receipts), receipts
    battery = e._read(root, e.BATTERIES_DOC)["batteries"][0]
    current = e._entity(root, "test", test["id"])
    # A failed runtime attempt returns this same frozen test to READY.
    battery["status"] = "DONE"
    save(root, e.BATTERIES_DOC, {"batteries": [battery]})
    current.update(status="READY", state="READY", execution_phase="READY")
    save(root, "entities/test/TEST-ROBOT.json", current)
    retry = e.family_battery_items(root, NOW + timedelta(minutes=2))[0]
    assert retry["payload"]["battery_id"] != first["payload"]["battery_id"]
    assert e.battery_requests(retry, retry["payload"], root)
    assert retry["payload"]["battery_id"] == e.family_battery_items(root, NOW + timedelta(days=1))[0]["payload"]["battery_id"]


def test_new_input_bytes_or_recipe_bytes_change_execution_identity(tmp_path, monkeypatch):
    root = tmp_path / "tower"; recipes = tmp_path / "recipes"
    test = setup(root, recipes, monkeypatch)
    original = e.family_battery_items(root, NOW)[0]["payload"]["battery_id"]
    changed = copy.deepcopy(test)
    changed["data_binding"]["inputs"][0]["sha256"] = "b" * 64
    save(root, "entities/test/TEST-ROBOT.json", changed)
    inputs = e.family_battery_items(root, NOW)[0]["payload"]["battery_id"]
    assert inputs != original
    (recipes / "audit_recipe.py").write_text("# corrected engineering implementation\nresult = 2\n")
    code = e.family_battery_items(root, NOW)[0]["payload"]["battery_id"]
    assert len({original, inputs, code}) == 3
