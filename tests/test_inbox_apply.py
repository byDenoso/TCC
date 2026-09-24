

def test_integrity_report_and_signal_links(tmp_path):
    from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
    report = {"kind": "INTEGRITY_REPORT", "source": "CHATGPT", "created_at": "2026-09-25T09:00:00Z",
              "payload": {"date": "2026-09-25", "status": "YELLOW", "checks": [{"area": "inbox", "ok": False, "detail": "x"}]},
              "_inbox_name": "g1"}
    (req,) = proposal_to_requests(report, tmp_path)
    assert req["entity_name"].startswith("INTEGRITY_REPORT::")


def test_frontier_includes_entity_ready_tests_outside_active_roadmaps(tmp_path):
    import json
    from runtime.nexo_agent_api.frontier import roadmap_frontier
    (tmp_path / "indexes").mkdir()
    (tmp_path / "indexes" / "active-roadmaps.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    (tmp_path / "entities" / "test").mkdir(parents=True)
    (tmp_path / "entities" / "test" / "T-X.json").write_text(json.dumps({"id": "T-X", "status": "READY"}), encoding="utf-8")
    result = roadmap_frontier(tmp_path)
    assert [t["test_id"] for t in result["ready"]] == ["T-X"]
    assert result["batch"][0]["test_id"] == "T-X"
