from __future__ import annotations

import pytest

from nexo_control.github_runner import select_correlated_run, summarize_results


def test_exact_correlation_selects_one_run():
    runs = [
        {"id": 1, "display_title": "OTHER", "head_branch": "branch"},
        {"id": 2, "display_title": "CORR", "head_branch": "branch"},
    ]
    assert select_correlated_run(runs, "CORR", "branch")["id"] == 2


def test_missing_correlation_fails_closed():
    with pytest.raises(ValueError, match="zero matching runs"):
        select_correlated_run([], "CORR", "branch")


def test_duplicate_correlation_fails_closed():
    runs = [
        {"id": 1, "display_title": "CORR", "head_branch": "branch"},
        {"id": 2, "display_title": "CORR", "head_branch": "branch"},
    ]
    with pytest.raises(ValueError, match="multiple matching runs"):
        select_correlated_run(runs, "CORR", "branch")


def test_wrong_ref_is_not_a_match():
    runs = [{"id": 1, "display_title": "CORR", "head_branch": "other"}]
    with pytest.raises(ValueError, match="zero matching runs"):
        select_correlated_run(runs, "CORR", "branch")


def test_campaign_summary_requires_no_technical_failures_for_learning():
    summary = summarize_results(
        "C1",
        [
            {"test_id": "T1", "validation": {"status": "PASSED"}},
            {"test_id": "T2", "validation": {"status": "NOT_PROMOTED"}},
        ],
    )
    assert summary["ready_for_learning"] is True

    failed = summarize_results("C1", [{"test_id": "T1", "validation": {"status": "FAILED"}}])
    assert failed["ready_for_learning"] is False
