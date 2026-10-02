"""The C01 producer uses canonical readiness; fixtures never authorize activation."""
import hashlib
from unittest.mock import patch

import pytest

from runtime.nexo_agent_api.readiness_comparison import compare_readiness
from tests.test_readiness_cache_invalidation import real_readiness
from runtime.nexo_agent_api.operational_canary import digest_json


def compare(fixture):
    return compare_readiness(
        fixture.root, fixture.test, access_scope="PUBLIC",
        authorization_revision="SYNTHETIC_SOFTWARE_CONTROL",
        manifest_revision="isolated-fixture",
        manifest_sha256=hashlib.sha256(b"synthetic-control").hexdigest())


def tree_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def test_replay_both_orders_is_read_only_and_never_admission_evidence(real_readiness):
    fixture = real_readiness
    before = tree_bytes(fixture.root)
    report = compare(fixture)
    assert tree_bytes(fixture.root) == before
    assert report["all_equal_and_stable"]
    assert report["activation_evidence"] is False
    assert report["selection"] == "BASELINE"
    assert {record["order"] for record in report["records"]} == {
        "BASELINE_THEN_CANDIDATE", "CANDIDATE_THEN_BASELINE"}
    for record in report["records"]:
        assert record["metrics"]["baseline"]["read_calls"] > 0
        assert record["metrics"]["candidate"]["read_calls"] == 0
        assert record["cold_fill_metrics"]["read_calls"] > 0
        assert record["context_before_metrics"]["read_calls"] > 0
        assert record["context_after_metrics"]["read_calls"] > 0
        assert record["result_sha256"]["baseline"] == record["result_sha256"]["candidate"]
    committed = dict(report)
    assert committed.pop("report_sha256") == digest_json(committed)
    assert fixture.test["id"] not in str(report)
    assert compare(fixture)["all_equal_and_stable"]  # replay adds no live unit/state


def test_unavailable_context_runs_baseline_without_candidate_proof(real_readiness):
    fixture = real_readiness
    (fixture.recipes / "smoke" / (fixture.test["recipe"] + ".json")).unlink()
    report = compare(fixture)
    assert not report["all_equal_and_stable"]
    assert all(r["status"] == "CONTEXT_UNAVAILABLE" for r in report["records"])


def test_corrupt_cached_result_is_reported_as_mismatch(real_readiness):
    wrong = {"policy": "CORRUPT", "eligible": False, "reasons": ["CONTROL"]}
    with patch("runtime.nexo_agent_api.readiness_comparison.ReadinessCache.get", return_value=wrong):
        report = compare(real_readiness)
    assert not report["all_equal_and_stable"]
    assert all(r["status"] == "MISMATCH" for r in report["records"])


def test_context_mutation_during_comparison_cannot_count_as_match(real_readiness):
    fixture = real_readiness
    from runtime.nexo_agent_api.readiness_cache import ReadinessCache
    original = ReadinessCache.get
    def changed(cache, context):
        path = fixture.recipes / "smoke" / (fixture.test["recipe"] + ".json")
        path.write_bytes(path.read_bytes() + b" ")
        return original(cache, context)
    with patch.object(ReadinessCache, "get", changed):
        report = compare(fixture)
    assert not report["all_equal_and_stable"]
    assert all(r["status"] == "CONTEXT_CHANGED" for r in report["records"])
