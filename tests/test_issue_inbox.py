"""Issue inbox: which GitHub issues count as ChatGPT proposals, and how the envelope is read."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("nexo_tower", Path(__file__).resolve().parents[1] / "scripts" / "nexo_tower.py")
nexo_tower = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nexo_tower)
IssueInbox = nexo_tower.IssueInbox


def _issue(number, title, login="byDenoso", labels=(), body="{}", **extra):
    return {"number": number, "title": title, "user": {"login": login},
            "labels": [{"name": name} for name in labels], "body": body, **extra}


def test_selects_only_trusted_proposal_issues():
    items = IssueInbox.select([
        _issue(1, "[NEXO_INBOX] run T-1"),
        _issue(2, "anything", labels=["nexo-proposal"]),
        _issue(3, "[NEXO_INBOX] from a stranger", login="someone-else"),
        _issue(4, "[NEXO_INBOX] a pull request", pull_request={}),
        _issue(5, "ordinary bug report"),
    ])
    assert [item["id"] for item in items] == ["issue:1", "issue:2"]


def test_envelope_prefers_fenced_json_and_flags_garbage():
    assert IssueInbox.envelope('context\n```json\n{"kind": "X", "a": 1}\n```\n') == {"kind": "X", "a": 1}
    assert IssueInbox.envelope('{"kind": "Y"}') == {"kind": "Y"}
    assert "unparseable" in IssueInbox.envelope("not json")
