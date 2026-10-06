from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.nexo_agent_api.live_tower import build_live_tower_payload
from runtime.nexo_agent_api.memory import Snapshot
from runtime.nexo_agent_api.retrieval import Retrieval, safe_clean


SECRET = "SYNTHETIC_REDACTION_SENTINEL_ONLY"


def _snapshot(tmp_path: Path) -> Snapshot:
    root = tmp_path / "source"
    root.mkdir()
    (root / "CONTROL.json").write_text(json.dumps({
        "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}), encoding="utf-8")
    files = {}
    for prefix, kind in (("runtime/runs", "RUN"), ("runtime/results", "RESULT"),
                         ("runtime/evidence", "EVIDENCE"), ("runtime/artifacts", "ARTIFACT"),
                         ("recipes", "RECIPE")):
        files[f"{prefix}/{kind}-REDACTION.json"] = {"encoding": "json", "value": {
            "id": f"{kind}-REDACTION", "status": "READY", "domain": "science",
            "title": "Public synthetic redaction fixture", "allowed_roles": ["ENGINEER"],
            "secret": SECRET, "nested": [{"Secret": SECRET, "se_cret": SECRET,
                                         "credentials": SECRET, "api_key": SECRET,
                                         "public": "visible evidence"}],
        }}
    payload = build_live_tower_payload(root, updated_at="2026-10-06T12:00:00Z", base={"files": files})
    tower = tmp_path / "TOWER.json"
    tower.write_text(json.dumps(payload), encoding="utf-8")
    return Snapshot.read(tower)


@pytest.mark.parametrize("operation", ["get", "search", "context"])
def test_expanded_surfaces_redact_secrets_at_output_boundary(tmp_path, operation):
    snapshot = _snapshot(tmp_path)
    engine = Retrieval(tmp_path / "retrieval.sqlite")
    engine.sync(snapshot)
    for kind in ("RUN", "RESULT", "EVIDENCE", "ARTIFACT", "RECIPE"):
        entity = f"{kind}-REDACTION"
        if operation == "get":
            result = engine.get(entity, "ENGINEER")
            assert result["data"]["nested"] == [{"public": "visible evidence"}]
        elif operation == "search":
            result = engine.search(entity, "ENGINEER")
            assert result["hits"], result
        else:
            result = engine.context(entity, "ENGINEER")
        encoded = json.dumps(result)
        assert "visible evidence" in encoded
        assert SECRET not in encoded
    # The input snapshot is evidence, never rewritten by cache sanitization.
    assert SECRET in json.dumps(snapshot.payload)


def test_secret_keys_keep_existing_redaction_and_public_fields():
    assert safe_clean({"SECRET": SECRET, "private_key": SECRET, "credentials": SECRET,
                       "api-key": SECRET, "public": [{"secret": SECRET, "ok": "visible"}]}) == {
        "public": [{"ok": "visible"}]}
