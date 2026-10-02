from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from . import scientific_integrity
from .readiness_cache import (
    ReadinessCache,
    ReadinessCacheContext,
    ReadinessContextEpoch,
    ReadinessContextUnavailable,
    evaluate_with_readiness_cache,
)
from .tower_paths import entity_path


class ReadinessCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "tower"
        self.recipe_root = Path(self.tmp.name) / "recipes"
        (self.root / "evolution").mkdir(parents=True)
        (self.recipe_root / "smoke").mkdir(parents=True)
        self.test = {"id": "TEST::CACHE", "recipe": "R-CACHE",
                     "depends_on": ["TEST::DEP"], "design": "fixed-v1"}
        dependency = entity_path(self.root, "test", "TEST::DEP")
        dependency.parent.mkdir(parents=True)
        dependency.write_text(json.dumps({"id": "TEST::DEP", "entity_version": 1}), encoding="utf-8")
        (self.recipe_root / "R-CACHE.py").write_text("# frozen recipe\nVALUE = 1\n", encoding="utf-8")
        (self.recipe_root / "smoke" / "R-CACHE.json").write_text("{}", encoding="utf-8")
        (self.root / "evolution" / "batteries.json").write_text(
            json.dumps({"batteries": []}), encoding="utf-8")
        self.cache = ReadinessCache()

    def tearDown(self):
        self.tmp.cleanup()

    def context(self, *, scope="PUBLIC", authorization_revision="auth-v1"):
        return ReadinessCacheContext.from_runtime(
            self.root, self.test, access_scope=scope,
            authorization_revision=authorization_revision,
            manifest_revision="tower-r1", manifest_sha256="a" * 64,
            validator=scientific_integrity.readiness,
            validator_version="scientific_integrity.readiness@fixed",
            recipe_root=self.recipe_root,
        )

    @staticmethod
    def result(eligible=False):
        return {"policy": "TOWER_READINESS_V1", "eligible": eligible,
                "reasons": [] if eligible else ["NOT_READY"]}

    def test_cache_reuses_only_identical_full_context(self):
        first = self.context()
        calls = []
        baseline = lambda: calls.append("baseline") or self.result()
        self.assertEqual(evaluate_with_readiness_cache(baseline, first, self.cache, enabled=True), self.result())
        self.assertEqual(evaluate_with_readiness_cache(baseline, first, self.cache, enabled=True), self.result())
        self.assertEqual(calls, ["baseline"])

        dependency = entity_path(self.root, "test", "TEST::DEP")
        dependency.write_text(json.dumps({"id": "TEST::DEP", "entity_version": 2}), encoding="utf-8")
        changed_dependency = self.context()
        self.assertNotEqual(first.key, changed_dependency.key)
        self.assertEqual(evaluate_with_readiness_cache(
            baseline, changed_dependency, self.cache, enabled=True), self.result())
        self.assertEqual(calls, ["baseline", "baseline"])

        changed_scope = self.context(scope="PRIVATE")
        changed_auth = self.context(authorization_revision="auth-v2")
        self.assertNotEqual(changed_dependency.key, changed_scope.key)
        self.assertNotEqual(changed_dependency.key, changed_auth.key)

    def test_incomplete_context_and_cache_errors_fall_back_to_baseline(self):
        (entity_path(self.root, "test", "TEST::DEP")).unlink()
        with self.assertRaises(ReadinessContextUnavailable):
            self.context()
        calls = []
        baseline = lambda: calls.append(True) or self.result()
        self.assertEqual(evaluate_with_readiness_cache(baseline, None, self.cache, enabled=True), self.result())
        self.assertEqual(calls, [True])

        class BrokenCache:
            def get(self, _context):
                raise OSError("store unavailable")
            def put(self, *_args):
                raise AssertionError("must fail closed before write")

        (entity_path(self.root, "test", "TEST::DEP")).write_text("{}", encoding="utf-8")
        context = self.context()
        self.assertEqual(evaluate_with_readiness_cache(
            baseline, context, BrokenCache(), enabled=True), self.result())
        self.assertEqual(calls, [True, True])

    def test_context_epoch_invalidates_only_on_new_immutable_revision(self):
        epoch = ReadinessContextEpoch()
        builds = []

        def builder(_metrics):
            builds.append(True)
            return self.context()

        first, first_metrics = epoch.capture("tower-rev-1", "TEST::CACHE", builder)
        repeated, repeated_metrics = epoch.capture("tower-rev-1", "TEST::CACHE", builder)
        self.assertEqual(first.key, repeated.key)
        self.assertFalse(first_metrics["context_cache_hit"])
        self.assertTrue(repeated_metrics["context_cache_hit"])
        changed, changed_metrics = epoch.capture("tower-rev-2", "TEST::CACHE", builder)
        self.assertEqual(changed.key, first.key)
        self.assertFalse(changed_metrics["context_cache_hit"])
        self.assertEqual(len(builds), 2)


if __name__ == "__main__":
    unittest.main()
