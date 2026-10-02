"""Exercise cached readiness with real canonical readers and changed files."""
import hashlib

import pytest

from runtime.nexo_agent_api import scientific_integrity as integrity
from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
from runtime.nexo_agent_api.readiness_cache import (
    ReadinessCache, ReadinessCacheContext, ReadinessContextUnavailable,
    evaluate_with_readiness_cache,
)
from runtime.nexo_agent_api.tower_apply import apply_requests
from runtime.nexo_agent_api.tower_paths import entity_path
from tests import test_execution_phase_reconciliation as phase_fixture

_save = phase_fixture._save


@pytest.fixture
def real_readiness():
    fixture = phase_fixture.ExecutionPhaseReconciliationTests()
    fixture.setUp()
    try:
        yield fixture
    finally:
        fixture.tearDown()


def context(fixture, *, scope="PUBLIC", authorization="frozen-auth-policy"):
    return ReadinessCacheContext.from_runtime(
        fixture.root, fixture.test, access_scope=scope,
        authorization_revision=authorization,
        manifest_revision="frozen-test-manifest",
        manifest_sha256=hashlib.sha256(b"synthetic-manifest").hexdigest(),
        validator=integrity.readiness, validator_version="corrected-runtime-fixture",
        recipe_root=fixture.recipes,
    )


def test_reservation_in_same_materialized_batch_cannot_reuse_cached_ready(real_readiness):
    fixture = real_readiness
    cache = ReadinessCache()
    baseline = lambda: integrity.readiness(fixture.root, fixture.test)
    old_context = context(fixture)
    assert evaluate_with_readiness_cache(baseline, old_context, cache, enabled=True)["eligible"]
    # Real reservation updates the canonical battery ledger before bundle publish.
    requests = proposal_to_requests(fixture._battery_items(), fixture.root)
    receipts = apply_requests(fixture.root, requests)
    assert all(receipt.get("accepted", True) for receipt in receipts)
    fresh_context = context(fixture)
    assert fresh_context.key != old_context.key
    fresh = evaluate_with_readiness_cache(baseline, fresh_context, cache, enabled=True)
    assert fresh == baseline()
    assert not fresh["eligible"]


def test_changed_and_missing_dependency_never_return_old_cached_ready(real_readiness):
    fixture = real_readiness
    fixture.test["depends_on"] = ["TEST-CACHE-DEPENDENCY"]
    _save(fixture.root, "entities/test/TEST-CACHE-DEPENDENCY.json", {
        "id": "TEST-CACHE-DEPENDENCY", "status": "DONE", "entity_version": 1,
        "executed_at": "2026-09-30T10:00:00Z", "verdict": "INCONCLUSIVE",
    })
    cache = ReadinessCache()
    baseline = lambda: integrity.readiness(fixture.root, fixture.test)
    original = context(fixture)
    initial = evaluate_with_readiness_cache(baseline, original, cache, enabled=True)
    assert initial["eligible"], initial
    _save(fixture.root, "entities/test/TEST-CACHE-DEPENDENCY.json", {
        "id": "TEST-CACHE-DEPENDENCY", "status": "READY", "entity_version": 2,
    })
    changed = context(fixture)
    assert changed.key != original.key
    assert not evaluate_with_readiness_cache(baseline, changed, cache, enabled=True)["eligible"]
    entity_path(fixture.root, "test", "TEST-CACHE-DEPENDENCY").unlink()
    with pytest.raises(ReadinessContextUnavailable):
        context(fixture)
    assert not evaluate_with_readiness_cache(baseline, None, cache, enabled=True)["eligible"]


def test_cache_hit_is_detached_and_scope_and_authorization_are_separate(real_readiness):
    fixture = real_readiness
    cache = ReadinessCache()
    baseline = lambda: integrity.readiness(fixture.root, fixture.test)
    public_context = context(fixture)
    first = evaluate_with_readiness_cache(baseline, public_context, cache, enabled=True)
    first["eligible"] = False
    assert cache.get(public_context)["eligible"]
    assert cache.get(context(fixture, scope="PRIVATE")) is None
    assert cache.get(context(fixture, authorization="changed-auth-policy")) is None
