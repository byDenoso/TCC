

def test_integrity_report_and_signal_links(tmp_path):
    from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
    report = {"kind": "INTEGRITY_REPORT", "source": "CHATGPT", "created_at": "2026-09-25T09:00:00Z",
              "payload": {"date": "2026-09-25", "status": "YELLOW", "checks": [{"area": "inbox", "ok": False, "detail": "x"}]},
              "_inbox_name": "g1"}
    (req,) = proposal_to_requests(report, tmp_path)
    assert req["entity_name"].startswith("INTEGRITY_REPORT::")
