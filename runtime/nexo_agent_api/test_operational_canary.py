from __future__ import annotations

import datetime as dt
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from . import operational_canary as c01
from .readiness_cache import ReadinessCache


UTC = dt.timezone.utc


class FrozenAnalysisPlanPolicyTests(unittest.TestCase):
    def setUp(self):
        now = dt.datetime.now(UTC).replace(microsecond=0)
        self.plan = c01.FrozenAnalysisPlan.freeze_from_baseline_replay(
            baseline_replay_ref="fixture-baseline",
            baseline_replay_sha256="1" * 64,
            baseline_variance=0.02,
            baseline_variance_n=40,
            baseline_variance_ref="fixture-variance",
            expected_read_ratio=0.70,
            strata_weights={"public": 0.5, "private": 0.5},
            independence_basis="one stable test identity per intent",
            cluster_key="intent_id",
            frozen_at=c01.iso_utc(now),
        )

    def test_plan_rejects_weakened_confidence(self):
        with self.assertRaisesRegex(ValueError, "C01_CONFIDENCE_MUST_MATCH_POLICY"):
            dataclasses.replace(self.plan, confidence=0.90)

    def test_plan_rejects_weakened_error_ceiling(self):
        with self.assertRaisesRegex(ValueError, "C01_ERROR_BOUND_MUST_MATCH_POLICY"):
            dataclasses.replace(self.plan, maximum_error_upper=0.01)


def _report(config: c01.CanaryConfig, contract: str, observed_at: dt.datetime) -> dict:
    if contract == "C01_OFFLINE_CORPUS_REPLAY_V1":
        payload = {
            "contract": contract, "canary_id": config.canary_id,
            "baseline_sha256": config.baseline_sha256,
            "candidate_sha256": config.candidate_sha256,
            "candidate_adapter_sha256": config.candidate_sha256,
            "analysis_plan_sha256": config.analysis_plan.plan_sha256,
            "strata_counts": {name: 1 for name in c01.REQUIRED_CORPUS_STRATA},
            "evaluation_orders": ["BASELINE_THEN_CANDIDATE", "CANDIDATE_THEN_BASELINE"],
            "evaluation_order_counts": {"BASELINE_THEN_CANDIDATE": 1,
                                        "CANDIDATE_THEN_BASELINE": 1},
            "decision_mismatches": 0, "evaluation_errors": 0,
            "critical_violations": 0, "created_at": c01.iso_utc(observed_at),
        }
    else:
        payload = {
            "contract": contract, "canary_id": config.canary_id,
            "baseline_sha256": config.baseline_sha256,
            "candidate_sha256": config.candidate_sha256,
            "analysis_plan_sha256": config.analysis_plan.plan_sha256,
            "shadow_candidate_units": 1, "decision_mismatches": 0,
            "evaluation_errors": 0, "critical_violations": 0,
            "selection_during_shadow": "BASELINE",
            "observed_at": c01.iso_utc(observed_at),
        }
    return payload | {"report_sha256": c01.digest_json(payload)}


class _Verifier:
    def __init__(self, config, offline_hash, shadow_hash, expiry):
        self.config = config
        self.offline_hash = offline_hash
        self.shadow_hash = shadow_hash
        self.expiry = expiry

    def verify(self, config, now):
        if config.proposal_sha256 != self.config.proposal_sha256:
            return None
        return c01.VerifiedMandate(
            canary_id=config.canary_id, approval_ref="root-approved-ref",
            approved_at=c01.iso_utc(now - dt.timedelta(minutes=1)),
            expires_at=c01.iso_utc(self.expiry),
            proposal_sha256=config.proposal_sha256, registry_sha256="b" * 64,
            adapter_id=c01.ADAPTER_ID, offline_corpus_sha256=self.offline_hash,
            shadow_report_sha256=self.shadow_hash,
        )


class OperationalCanaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = dt.datetime.now(UTC).replace(microsecond=0)
        self.plan = c01.FrozenAnalysisPlan.freeze_from_baseline_replay(
            baseline_replay_ref="test-fixture-baseline",
            baseline_replay_sha256="1" * 64,
            baseline_variance=0.02, baseline_variance_n=40,
            baseline_variance_ref="test-fixture-variance",
            expected_read_ratio=0.70,
            strata_weights={"public": 0.5, "private": 0.5},
            independence_basis="one stable test identity per intent",
            cluster_key="intent_id",
            frozen_at=c01.iso_utc(self.now - dt.timedelta(days=2)),
        )
        self.config = c01.CanaryConfig(
            canary_id="C01-readiness-cache", baseline_version="fixed",
            baseline_sha256="1" * 64, candidate_version="cache-v1",
            candidate_sha256=c01.loaded_readiness_cache_sha256(),
            proposal_ref="evidence/c01-test", analysis_plan=self.plan,
        )
        self.store = c01.TowerCanaryStore(self.root)
        self.store.initialize(self.config)
        self.store.install_baseline_selection(self.config)
        self.offline = _report(self.config, "C01_OFFLINE_CORPUS_REPLAY_V1",
                               self.now - dt.timedelta(days=1))
        self.shadow = _report(self.config, "C01_SHADOW_REPLAY_V1",
                              self.now - dt.timedelta(minutes=2))
        self.verifier = _Verifier(
            self.config, self.offline["report_sha256"], self.shadow["report_sha256"],
            self.now + dt.timedelta(days=20))

    def tearDown(self):
        self.tmp.cleanup()

    def controller(self, *, store=None):
        return c01.OperationalCanary(
            self.config, verifier=self.verifier, ledger=store or self.store,
            adapter=store or self.store, monitor=lambda: True,
            baseline_verifier=lambda _: True,
        )

    def activate(self, controller=None):
        controller = controller or self.controller()
        self.assertTrue(controller.start(now=self.now, offline_corpus_report=self.offline))
        self.assertEqual(controller.state, "SHADOW")
        self.assertTrue(controller.activate_canary(now=self.now, shadow_report=self.shadow))
        self.assertEqual(controller.state, "CANARY")
        return controller

    def assigned_intent(self):
        for index in range(20_000):
            intent = f"intent-{index}"
            if c01.assigned_to_candidate(intent):
                return intent
        self.fail("could not find deterministic candidate intent")

    def writer_fixture(self, name: str):
        from .live_tower import build_live_tower_payload
        from .readiness_cache import _validator_bundle_hash
        from .scientific_integrity import readiness

        root = self.root / name
        root.mkdir(parents=True, exist_ok=True)
        (root / "CONTROL.json").write_text(json.dumps({
            "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
        }), encoding="utf-8")
        config = c01.CanaryConfig(
            canary_id="C01-readiness-cache", baseline_version="corrected-baseline",
            baseline_sha256=_validator_bundle_hash(readiness, root), candidate_version="cache-v1",
            candidate_sha256=c01.loaded_readiness_cache_sha256(),
            proposal_ref="PRIVATE_C01_PROPOSAL_SENTINEL", analysis_plan=self.plan,
        )
        raw = c01.canonical_json(build_live_tower_payload(root))
        return root, config, raw

    @staticmethod
    def writer_envelope(action: str, payload: dict, *, source: str = "DENER") -> dict:
        return {
            "kind": "C01_CANARY", "source": source,
            "created_at": "2099-01-01T00:00:00Z",
            "_inbox_name": f"c01-test-{action}-{uuid.uuid4().hex}",
            "payload": {"action": action, **payload},
        }

    @staticmethod
    def repack(root: Path, base_raw: bytes) -> bytes:
        from .live_tower import build_live_tower_payload, read_live_tower_bytes
        return c01.canonical_json(build_live_tower_payload(root, base=read_live_tower_bytes(base_raw)))

    def test_real_writer_envelope_installs_private_config_baseline_only_and_rejects_untrusted_start(self):
        from .gpt_writer import apply_to_tower
        from .live_tower import materialize_live_tower

        off = c01.operational_status(self.root / "empty-tower", environment={})
        self.assertFalse(off["installed"])
        self.assertFalse(off["activated"])
        self.assertFalse(off["enabled"])
        self.assertEqual(off["effective_state"], "OFF")
        self.assertEqual(off["state"], "OFF")
        self.assertEqual(off["reason"], "CONFIG_NOT_INSTALLED")

        _source, config, raw = self.writer_fixture("writer-install")
        envelope = self.writer_envelope("INSTALL_CONFIG", {"config": config.proposal_payload()})
        packed, report = apply_to_tower(raw, [envelope])
        self.assertIsNotNone(packed)
        self.assertEqual(report["rejected"], [])
        installed_root, _ = materialize_live_tower(packed, self.root / "writer-installed")
        store = c01.TowerCanaryStore(installed_root)
        self.assertEqual(store.config(config.canary_id).proposal_sha256, config.proposal_sha256)
        self.assertEqual(store.get(config.canary_id)["state"], "PROPOSED")
        self.assertEqual(store.read_selection()["variant"], "baseline")
        status = c01.operational_status(installed_root, environment={})
        self.assertTrue(status["installed"])
        self.assertFalse(status["activated"])
        self.assertFalse(status["enabled"])
        self.assertEqual(status["effective_state"], "OFF")

        bad_root, bad_config, bad_raw = self.writer_fixture("writer-bad-config")
        bad_payload = bad_config.proposal_payload()
        bad_payload["candidate"]["sha256"] = "f" * 64
        bad_envelope = self.writer_envelope("INSTALL_CONFIG", {"config": bad_payload})
        rejected_bytes, bad_report = apply_to_tower(bad_raw, [bad_envelope])
        self.assertIsNotNone(rejected_bytes)
        self.assertEqual(bad_report["rejected"][0]["reason"], "C01_CANDIDATE_CODE_HASH_MISMATCH")
        rejected_root, _ = materialize_live_tower(rejected_bytes, self.root / "writer-bad-config-rejected")
        self.assertIsNone(c01.TowerCanaryStore(rejected_root).config(bad_config.canary_id))
        self.assertEqual(status["selection_readback"], "PASS")
        store._mutate(lambda doc: doc["canaries"][config.canary_id].update(
            monitor={"operator_note": "PRIVATE_MONITOR_SENTINEL"},
            observations=[{"intent_id": "PRIVATE_INTENT_SENTINEL"}],
        ))
        untrusted_status = json.dumps(c01.operational_status(installed_root, environment={}))
        self.assertNotIn("PRIVATE_MONITOR_SENTINEL", untrusted_status)
        self.assertNotIn("PRIVATE_INTENT_SENTINEL", untrusted_status)
        self.assertNotIn("PRIVATE_C01_PROPOSAL_SENTINEL", json.dumps(report))

        offline = _report(config, "C01_OFFLINE_CORPUS_REPLAY_V1", self.now - dt.timedelta(minutes=1))
        untrusted_start = self.writer_envelope(
            "START_SHADOW", {"offline_corpus_report": offline})
        env = {
            "NEXO_C01_APPROVAL_REGISTRY_PATH": str(self.root / "missing-registry.json"),
            "NEXO_C01_APPROVAL_REGISTRY_SHA256": "0" * 64,
            "NEXO_C01_APPROVAL_REF": "source_thread01a0fabc",
            "NEXO_C01_APPROVED_AT": c01.iso_utc(self.now - dt.timedelta(minutes=2)),
        }
        with patch.dict(os.environ, env, clear=False):
            rejected, result = apply_to_tower(packed, [untrusted_start])
        self.assertEqual(result["rejected"][0]["reason"], "C01_TRUSTED_MANDATE_UNAVAILABLE")
        state_root, _ = materialize_live_tower(rejected or packed, self.root / "writer-after-refusal")
        self.assertEqual(c01.TowerCanaryStore(state_root).get(config.canary_id)["state"], "PROPOSED")
        status = c01.operational_status(state_root, environment=env)
        self.assertFalse(status["enabled"])

    def test_writer_envelopes_require_registry_and_monitor_then_activate_and_rollback_readback(self):
        from .gpt_writer import apply_to_tower
        from .live_tower import materialize_live_tower

        _source, config, raw = self.writer_fixture("writer-transitions")
        packed, install_report = apply_to_tower(
            raw, [self.writer_envelope("INSTALL_CONFIG", {"config": config.proposal_payload()})])
        self.assertIsNotNone(packed)
        self.assertEqual(install_report["rejected"], [])
        now = dt.datetime.now(UTC).replace(microsecond=0)
        offline = _report(config, "C01_OFFLINE_CORPUS_REPLAY_V1", now - dt.timedelta(minutes=2))
        shadow = _report(config, "C01_SHADOW_REPLAY_V1", now - dt.timedelta(minutes=1))
        approved_at = c01.iso_utc(now - dt.timedelta(minutes=3))
        approval_ref = "source_thread01a0fabc"
        registry = {
            "contract": c01.APPROVALS_CONTRACT,
            "operational_canaries": [{
                "canary_id": config.canary_id, "enabled": True,
                "adapter_id": c01.ADAPTER_ID, "scope": [c01.ADAPTER_ID],
                "forbidden_scope": sorted(c01.FORBIDDEN_SCOPES),
                "approval_ref": approval_ref, "approved_at": approved_at,
                "proposal_sha256": config.proposal_sha256,
                "baseline_sha256": config.baseline_sha256,
                "candidate_sha256": config.candidate_sha256,
                "analysis_plan_sha256": config.analysis_plan.plan_sha256,
                "offline_corpus_sha256": offline["report_sha256"],
                "shadow_report_sha256": shadow["report_sha256"],
                "valid_from": c01.iso_utc(now - dt.timedelta(days=1)),
                "expires_at": c01.iso_utc(now + dt.timedelta(days=1)),
            }],
        }
        registry_path = self.root / "trusted-c01-registry.json"
        registry_raw = c01.canonical_json(registry)
        registry_path.write_bytes(registry_raw)
        env = {
            "NEXO_C01_APPROVAL_REGISTRY_PATH": str(registry_path),
            "NEXO_C01_APPROVAL_REGISTRY_SHA256": c01.sha256(registry_raw),
            "NEXO_C01_APPROVAL_REF": approval_ref,
            "NEXO_C01_APPROVED_AT": approved_at,
        }

        state_root, _ = materialize_live_tower(packed, self.root / "writer-before-shadow")
        store = c01.TowerCanaryStore(state_root)
        monitor_status = c01.refresh_tower_monitor(state_root, env, now=now)
        self.assertTrue(monitor_status["enabled"])
        self.assertTrue(monitor_status["heartbeat_refreshed"])
        packed = self.repack(state_root, packed)

        # A correct registry file is still rejected when either trusted
        # provenance pin (reference or approval time) does not match it.
        for bad_pins in (
            dict(env, NEXO_C01_APPROVAL_REF="untrusted-thread-ref"),
            dict(env, NEXO_C01_APPROVED_AT=c01.iso_utc(now - dt.timedelta(minutes=4))),
        ):
            with patch.dict(os.environ, bad_pins, clear=False):
                refused, refusal_report = apply_to_tower(packed, [self.writer_envelope(
                    "START_SHADOW", {"offline_corpus_report": offline})])
            self.assertEqual(refusal_report["rejected"][0]["reason"],
                             "C01_TRUSTED_MANDATE_UNAVAILABLE")
            refused_root, _ = materialize_live_tower(refused, self.root / f"writer-pin-refused-{uuid.uuid4().hex}")
            self.assertEqual(c01.TowerCanaryStore(refused_root).get(config.canary_id)["state"], "PROPOSED")
            packed = refused

        with patch.dict(os.environ, env, clear=False):
            shadowed, shadow_report = apply_to_tower(packed, [self.writer_envelope(
                "START_SHADOW", {"offline_corpus_report": offline})])
        self.assertIsNotNone(shadowed)
        self.assertEqual(shadow_report["rejected"], [])
        shadow_root, _ = materialize_live_tower(shadowed, self.root / "writer-shadow-ready")
        self.assertEqual(c01.TowerCanaryStore(shadow_root).get(config.canary_id)["state"], "SHADOW")
        packed = self.repack(shadow_root, shadowed)

        with patch.dict(os.environ, env, clear=False):
            activated, activation_report = apply_to_tower(packed, [self.writer_envelope(
                "ACTIVATE_CANARY", {"shadow_report": shadow})])
        self.assertIsNotNone(activated)
        self.assertEqual(activation_report["rejected"], [])
        active_root, _ = materialize_live_tower(activated, self.root / "writer-active")
        active_store = c01.TowerCanaryStore(active_root)
        self.assertEqual(active_store.get(config.canary_id)["state"], "CANARY")
        self.assertEqual(active_store.read_selection()["variant"], "candidate")
        self.assertTrue(c01._tower_monitor_healthy(active_root, config))
        monitor_receipt = active_store.get(config.canary_id)["monitor"]
        self.assertEqual(monitor_receipt["selection_sha256"],
                         c01.digest_json(active_store.read_selection()))

        # A later ordinary Writer batch must refresh a missing monitor before
        # readiness/promotion work and persist that heartbeat in its packed Tower.
        active_store._mutate(lambda doc: doc["canaries"][config.canary_id].pop("monitor", None))
        self.assertFalse(c01._tower_monitor_healthy(active_root, config))
        activated = self.repack(active_root, activated)

        with patch.dict(os.environ, env, clear=False):
            gated, promotion_report = apply_to_tower(
                activated, [self.writer_envelope("PROMOTE", {})])
        self.assertIsNotNone(gated)
        self.assertEqual(promotion_report["rejected"], [])
        gated_root, _ = materialize_live_tower(gated, self.root / "writer-promotion-gate")
        gated_record = c01.TowerCanaryStore(gated_root).get(config.canary_id)
        self.assertEqual(gated_record["state"], "CANARY")
        self.assertEqual(gated_record["last_gate"]["state"], "CANARY_COLLECTING")
        self.assertTrue(c01._tower_monitor_healthy(
            gated_root, config))
        self.assertEqual(gated_record["monitor"]["selection_sha256"],
                         c01.digest_json(c01.TowerCanaryStore(gated_root).read_selection()))
        activated = gated
        active_root, _ = materialize_live_tower(activated, self.root / "writer-active-gated")
        active_store = c01.TowerCanaryStore(active_root)
        status = c01.operational_status(active_root, environment=env)
        self.assertTrue(status["activated"])
        self.assertTrue(status["enabled"])
        self.assertEqual(status["effective_state"], "ENABLED")
        self.assertEqual(status["selection_readback"], "PASS")
        self.assertNotIn(approval_ref, json.dumps(status))
        self.assertNotIn(str(registry_path), json.dumps(status))
        self.assertNotIn(config.proposal_sha256, json.dumps(status))
        from .gpt_writer import _operational_status
        with patch.dict(os.environ, env, clear=False):
            writer_status = _operational_status(active_root)
        self.assertTrue(writer_status["C01"]["activated"])
        self.assertTrue(writer_status["C01"]["enabled"])
        self.assertEqual(writer_status["C01"]["effective_state"], "ENABLED")
        self.assertEqual(writer_status["C01"]["selection_readback"], "PASS")

        # The public CLI status path is read-only even on a trusted active Tower.
        import contextlib
        import io
        from .gpt_writer import _main
        bundle_path = self.root / "trusted-active-tower.json"
        bundle_path.write_bytes(activated)
        before_bundle = bundle_path.read_bytes()
        before_tree = {
            path.relative_to(active_root): path.read_bytes()
            for path in active_root.rglob("*") if path.is_file()
        }
        output = io.StringIO()
        with patch.dict(os.environ, env, clear=False), contextlib.redirect_stdout(output):
            self.assertEqual(_main(["status", str(bundle_path)]), 0)
        after_tree = {
            path.relative_to(active_root): path.read_bytes()
            for path in active_root.rglob("*") if path.is_file()
        }
        self.assertEqual(bundle_path.read_bytes(), before_bundle)
        self.assertEqual(after_tree, before_tree)
        self.assertTrue(json.loads(output.getvalue())["C01"]["enabled"])

        # A concurrent unrelated pointer survives the adapter-specific rollback.
        active_store._mutate(lambda doc: doc["adapters"].update(
            unrelated_adapter={"version": "preserve-me"}))
        activated_with_unrelated = self.repack(active_root, activated)
        rolled_back, rollback_report = apply_to_tower(
            activated_with_unrelated, [self.writer_envelope("ROLLBACK", {})])
        self.assertIsNotNone(rolled_back)
        self.assertEqual(rollback_report["rejected"], [])
        final_root, _ = materialize_live_tower(rolled_back, self.root / "writer-rolled-back")
        final_store = c01.TowerCanaryStore(final_root)
        self.assertEqual(final_store.read_selection()["variant"], "baseline")
        self.assertEqual(final_store.get(config.canary_id)["state"], "ROLLED_BACK")
        self.assertEqual(final_store._read()["adapters"]["unrelated_adapter"], {"version": "preserve-me"})
        final_status = c01.operational_status(final_root, environment=env)
        self.assertFalse(final_status["enabled"])
        self.assertFalse(final_status["activated"])
        self.assertEqual(final_status["effective_state"], "OFF")

    def test_candidate_fingerprint_is_stable_across_fresh_bundle_extractions_and_detects_loaded_code_change(self):
        repo_root = Path(__file__).resolve().parents[2]
        runtime_src = repo_root / "runtime"
        hashes = []
        altered_hash = None
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            for label in ("extraction-one", "extraction-two"):
                extraction = temp_root / label
                shutil.copytree(runtime_src, extraction / "runtime",
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                script = (
                    "from runtime.nexo_agent_api.operational_canary "
                    "import loaded_readiness_cache_sha256; "
                    "print(loaded_readiness_cache_sha256())"
                )
                completed = subprocess.run(
                    [sys.executable, "-c", script], cwd=extraction,
                    check=True, capture_output=True, text=True,
                )
                hashes.append(completed.stdout.strip())
            extraction = temp_root / "extraction-one"
            script = (
                "import runtime.nexo_agent_api.readiness_cache as cache; "
                "from runtime.nexo_agent_api.operational_canary import loaded_readiness_cache_sha256; "
                "scope = {}; exec(compile('def changed(value): return value + 1', "
                "cache.__file__, 'exec'), scope); cache._canonical.__code__ = scope['changed'].__code__; "
                "print(loaded_readiness_cache_sha256())"
            )
            completed = subprocess.run(
                [sys.executable, "-c", script], cwd=extraction,
                check=True, capture_output=True, text=True,
            )
            altered_hash = completed.stdout.strip()
        self.assertEqual(len(set(hashes)), 1)
        self.assertNotEqual(hashes[0], altered_hash)

    @staticmethod
    def readiness():
        return {"policy": "TOWER_READINESS_V1", "eligible": False,
                "reasons": ["NOT_READY"], "recipe_sha256": "a" * 64}

    @staticmethod
    def measure(_variant, call):
        value = call()
        return value, {"read_calls": 10, "bytes_read": 200,
                       "elapsed_ms": 5.0, "error": False}

    def evaluate_one(self, controller, intent):
        route = controller.route(intent, now=self.now)
        self.assertEqual(route.variant, "CANDIDATE")
        context = SimpleNamespace(key="c" * 64)
        baseline, candidate, base_metrics, candidate_metrics, proof = controller.evaluate_candidate(
            route, context=context, cache=ReadinessCache(), baseline_callable=self.readiness,
            context_metrics={"context_read_calls": 1, "context_bytes_read": 20,
                             "context_elapsed_ms": 0.1},
            common_metrics={"read_calls": 1, "bytes_read": 10, "elapsed_ms": 0.1},
            measure=self.measure, now=self.now,
        )
        receipt_at = c01.parse_utc(proof.executed_at)
        outcome = controller.record_pair(
            route, now=receipt_at, stratum="public", cluster_id=intent,
            baseline_result=baseline, candidate_result=candidate,
            baseline_metrics=base_metrics, candidate_metrics=candidate_metrics,
            candidate_receipt=proof,
        )
        return route, proof, outcome

    def test_cache_adapter_is_off_when_proofs_missing(self):
        self.assertFalse(c01.default_off_status()["enabled"])
        self.assertEqual(c01.default_off_status()["candidate_units"], 0)
        self.assertEqual(c01.default_off_status()["state"], "INSUFFICIENT_EVIDENCE")

    def test_report_sha_must_be_bound_by_mandate_before_shadow(self):
        forged_verifier = _Verifier(self.config, "f" * 64, self.shadow["report_sha256"],
                                    self.now + dt.timedelta(days=20))
        controller = c01.OperationalCanary(
            self.config, verifier=forged_verifier, ledger=self.store, adapter=self.store,
            monitor=lambda: True, baseline_verifier=lambda _: True,
        )
        self.assertFalse(controller.start(now=self.now, offline_corpus_report=self.offline))
        self.assertEqual(controller.state, "PROPOSED")

        controller = self.controller()
        self.assertTrue(controller.start(now=self.now, offline_corpus_report=self.offline))
        wrong_shadow = _report(self.config, "C01_SHADOW_REPLAY_V1",
                               self.now - dt.timedelta(minutes=3))
        self.assertFalse(controller.activate_canary(now=self.now, shadow_report=wrong_shadow))
        self.assertEqual(controller.state, "SHADOW")

    def test_activation_actuator_receipt_failure_rolls_selection_back(self):
        controller = self.controller()
        self.assertTrue(controller.start(now=self.now, offline_corpus_report=self.offline))
        original = self.store.save_actuator_receipt
        self.store.save_actuator_receipt = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
        try:
            self.assertFalse(controller.activate_canary(now=self.now, shadow_report=self.shadow))
        finally:
            self.store.save_actuator_receipt = original
        self.assertEqual(self.store.read_selection()["variant"], "baseline")
        self.assertEqual(controller.state, "ROLLED_BACK")

    def test_rollback_preserves_unrelated_concurrent_adapter_data(self):
        controller = self.activate()
        record = self.store.get(self.config.canary_id)
        receipt = c01.SelectionReceipt(**record["actuator_receipt"])
        def concurrent(doc):
            doc["adapters"]["unrelated"] = {"revision": "kept"}
        self.store._mutate(concurrent)
        rolled = self.store.rollback(receipt, at=self.now)
        self.assertEqual(rolled["readback"], "PASS")
        doc = self.store._read()
        self.assertEqual(doc["adapters"]["unrelated"], {"revision": "kept"})
        self.assertEqual(doc["adapters"][c01.ADAPTER_ID]["variant"], "baseline")

    def test_candidate_metrics_cannot_be_forged_after_runtime_receipt(self):
        controller = self.activate()
        route = controller.route(self.assigned_intent(), now=self.now)
        context = SimpleNamespace(key="c" * 64)
        baseline, candidate, base_metrics, cand_metrics, proof = controller.evaluate_candidate(
            route, context=context, cache=ReadinessCache(), baseline_callable=self.readiness,
            context_metrics={"context_read_calls": 0, "context_bytes_read": 0,
                             "context_elapsed_ms": 0},
            common_metrics={"read_calls": 0, "bytes_read": 0, "elapsed_ms": 0},
            measure=self.measure, now=self.now,
        )
        cand_metrics["elapsed_ms"] += 100
        result = controller.record_pair(
            route, now=c01.parse_utc(proof.executed_at), stratum="public", cluster_id=route.intent_id,
            baseline_result=baseline, candidate_result=candidate,
            baseline_metrics=base_metrics, candidate_metrics=cand_metrics,
            candidate_receipt=proof,
        )
        self.assertFalse(result["recorded"])
        self.assertEqual(controller.state, "ROLLED_BACK")
        self.assertEqual(self.store.get(self.config.canary_id)["observations"], [])

    def test_repeat_intent_cannot_execute_candidate_twice(self):
        controller = self.activate()
        intent = self.assigned_intent()
        first, _, outcome = self.evaluate_one(controller, intent)
        self.assertTrue(outcome["recorded"])
        duplicate = controller.route(intent, now=self.now)
        self.assertTrue(duplicate.repeat)
        with self.assertRaises(c01.CanaryError):
            controller.evaluate_candidate(
                duplicate, context=SimpleNamespace(key="c" * 64), cache=ReadinessCache(),
                baseline_callable=self.readiness, context_metrics={}, common_metrics={},
                measure=self.measure, now=self.now,
            )
        obs = self.store.get(self.config.canary_id)["observations"]
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["candidate_evaluation_count"], 1)

    def test_promotion_check_before_minimum_does_not_stop_collection(self):
        controller = self.activate()
        decision = controller.promote(now=self.now + dt.timedelta(hours=1))
        self.assertFalse(decision["promoted"])
        self.assertEqual(controller.state, "CANARY")
        self.assertEqual(self.store.read_selection()["variant"], "candidate")
        self.assertIn("CANDIDATE_SAMPLE_INSUFFICIENT", decision["decision"]["blockers"])

    def test_promoted_hot_path_uses_cache_without_reservation_or_rollback(self):
        controller = self.activate()
        self.store.set_state(self.config.canary_id, "PROMOTED", at=self.now)
        intent = "post-promotion-intent"
        context = SimpleNamespace(key="d" * 64)
        cached = self.readiness() | {"eligible": True, "reasons": []}

        class Cache:
            def get(self, _context):
                return dict(cached)
            def put(self, *_args):
                raise AssertionError("promoted hit should not write")

        def metadata(_root, _test):
            return {"intent_id": intent, "now": self.now, "stratum": "public",
                    "cluster_id": intent, "access_scope": "PUBLIC",
                    "authorization_revision": "auth", "manifest_revision": "rev",
                    "manifest_sha256": "1" * 64, "reservation_sha256": "2" * 64}

        evaluator = c01.make_readiness_evaluator(
            runtime_factory=lambda _root: controller, metadata_provider=metadata,
            context_provider=lambda *_args: (context, {"context_read_calls": 0,
                "context_bytes_read": 0, "context_elapsed_ms": 0}),
            measure=lambda _variant, fn: (fn(), {"read_calls": 1, "bytes_read": 1,
                                                 "elapsed_ms": 1, "error": False}),
            cache=Cache(),
        )
        calls = []
        result = evaluator(self.root, {"id": "TEST::1"}, lambda: calls.append(True) or self.readiness())
        self.assertEqual(result, cached)
        self.assertEqual(calls, [])
        self.assertEqual(controller.state, "PROMOTED")

    def test_exposure_caps_reserve_no_more_than_100_per_day_or_2800_total(self):
        controller = self.activate()
        record = self.store.get(self.config.canary_id)
        first_token, _ = self.store.reserve(self.config, "budget-0", self.now)
        self.assertIsNotNone(first_token)
        self.store.cancel_reservation(self.config.canary_id, first_token)
        def preload(doc):
            target = doc["canaries"][self.config.canary_id]
            target["reservations"] = {}
            target["observations"] = [
                {"intent_id": f"used-{i}", "candidate_evaluated": True,
                 "occurred_at": c01.iso_utc(self.now), "cluster_id": f"used-{i}"}
                for i in range(100)
            ]
        self.store._mutate(preload)
        self.assertIsNone(self.store.reserve(self.config, "over-daily", self.now))
        next_day = self.now + dt.timedelta(days=1)
        def preload_total(doc):
            target = doc["canaries"][self.config.canary_id]
            target["observations"] = [
                {"intent_id": f"all-{i}", "candidate_evaluated": True,
                 "occurred_at": c01.iso_utc(next_day), "cluster_id": f"all-{i}"}
                for i in range(2_800)
            ]
        self.store._mutate(preload_total)
        self.assertIsNone(self.store.reserve(self.config, "over-total", next_day))

    def test_cross_midnight_reservation_is_rejected_before_candidate_invocation(self):
        controller = self.activate()
        intent = self.assigned_intent()
        route_at = self.now.replace(hour=23, minute=59, second=0)
        route = controller.route(intent, now=route_at)
        self.assertEqual(route.variant, "CANDIDATE")
        RealDateTime = dt.datetime

        class BoundaryDateTime(RealDateTime):
            @classmethod
            def now(cls, tz=None):
                value = (self.now.replace(hour=0, minute=1, second=0)
                         + dt.timedelta(days=1))
                return value if tz is None else value.astimezone(tz)

        variants = []
        def measure(variant, call):
            variants.append(variant)
            return call(), {"read_calls": 1, "bytes_read": 1,
                            "elapsed_ms": 1, "error": False}

        c01.dt.datetime = BoundaryDateTime
        try:
            with self.assertRaises(c01.CanaryError):
                controller.evaluate_candidate(
                    route, context=SimpleNamespace(key="e" * 64), cache=ReadinessCache(),
                    baseline_callable=self.readiness,
                    context_metrics={"context_read_calls": 0, "context_bytes_read": 0,
                                     "context_elapsed_ms": 0},
                    common_metrics={"read_calls": 0, "bytes_read": 0, "elapsed_ms": 0},
                    measure=measure, now=route_at,
                )
        finally:
            c01.dt.datetime = RealDateTime
        self.assertEqual(variants, ["baseline"])

    def test_noarg_production_factory_admits_promoted_state_only_with_current_registry_pin(self):
        from .scientific_integrity import readiness as baseline_readiness
        from .readiness_cache import _validator_bundle_hash

        root = self.root / "production"
        root.mkdir()
        now = dt.datetime.now(UTC).replace(microsecond=0)
        baseline_sha = _validator_bundle_hash(baseline_readiness, root)
        config = c01.CanaryConfig(
            canary_id="C01-readiness-cache", baseline_version="corrected-baseline",
            baseline_sha256=baseline_sha, candidate_version="cache-v1",
            candidate_sha256=c01.loaded_readiness_cache_sha256(),
            proposal_ref="evidence/production-fixture", analysis_plan=self.plan,
        )
        store = c01.TowerCanaryStore(root)
        store.initialize(config)
        store.install_baseline_selection(config)
        offline = _report(config, "C01_OFFLINE_CORPUS_REPLAY_V1", now - dt.timedelta(days=1))
        shadow = _report(config, "C01_SHADOW_REPLAY_V1", now - dt.timedelta(minutes=2))
        store.set_state(config.canary_id, "PROMOTED", at=now, details={
            "offline_corpus_sha256": offline["report_sha256"],
            "shadow_report_sha256": shadow["report_sha256"],
        })
        approval_ref = "source_thread01a0fabc"
        approved_at = c01.iso_utc(now - dt.timedelta(minutes=1))
        registry_doc = {
            "contract": c01.APPROVALS_CONTRACT,
            "operational_canaries": [{
                "canary_id": config.canary_id, "enabled": True,
                "adapter_id": c01.ADAPTER_ID, "scope": [c01.ADAPTER_ID],
                "forbidden_scope": sorted(c01.FORBIDDEN_SCOPES),
                "approval_ref": approval_ref, "approved_at": approved_at,
                "proposal_sha256": config.proposal_sha256,
                "baseline_sha256": config.baseline_sha256,
                "candidate_sha256": config.candidate_sha256,
                "analysis_plan_sha256": config.analysis_plan.plan_sha256,
                "offline_corpus_sha256": offline["report_sha256"],
                "shadow_report_sha256": shadow["report_sha256"],
                "valid_from": c01.iso_utc(now - dt.timedelta(days=1)),
                "expires_at": c01.iso_utc(now + dt.timedelta(days=1)),
            }],
        }
        registry_path = root / "approved-registry.json"
        registry_raw = c01.canonical_json(registry_doc)
        registry_path.write_bytes(registry_raw)
        env = {
            "NEXO_C01_APPROVAL_REGISTRY_PATH": str(registry_path),
            "NEXO_C01_APPROVAL_REGISTRY_SHA256": c01.sha256(registry_raw),
            "NEXO_C01_APPROVAL_REF": approval_ref,
            "NEXO_C01_APPROVED_AT": approved_at,
        }
        # Build the active state with the real adapter actuator receipt; the
        # monitor is then emitted by the production refresh function.
        store.set_state(config.canary_id, "CANARY", at=now)
        selection_receipt = store.activate(
            config, expected_baseline_version=config.baseline_version,
            expected_baseline_sha256=config.baseline_sha256, selected_at=now,
        )
        store.save_actuator_receipt(config.canary_id, selection_receipt)
        store.set_state(config.canary_id, "PROMOTED", at=now)
        monitor_status = c01.refresh_tower_monitor(root, env, now=now)
        self.assertTrue(monitor_status["enabled"])
        self.assertTrue(monitor_status["heartbeat_refreshed"])
        intent = "post-promotion"
        context = SimpleNamespace(key="f" * 64)
        cached = self.readiness()

        class Cache:
            def get(self, _context):
                return dict(cached)
            def put(self, *_args):
                raise AssertionError("cache should already contain the context")

        kwargs = {
            "environment": env,
            "metadata_provider": lambda *_args: {
                "intent_id": intent, "now": now, "stratum": "public",
                "cluster_id": intent, "access_scope": "PUBLIC",
                "authorization_revision": "auth", "manifest_revision": "rev",
                "manifest_sha256": "3" * 64, "reservation_sha256": "4" * 64,
            },
            "context_provider": lambda *_args: (context, {"context_read_calls": 0,
                "context_bytes_read": 0, "context_elapsed_ms": 0}),
            "measure": lambda _variant, call: (call(), {"read_calls": 1,
                "bytes_read": 1, "elapsed_ms": 1, "error": False}),
            "cache": Cache(),
        }
        evaluator = c01.make_tower_readiness_evaluator(**kwargs)
        calls = []
        result = evaluator(root, {"id": "TEST::PROMOTED"},
                           lambda: calls.append(True) or self.readiness())
        self.assertEqual(result, cached)
        self.assertEqual(calls, [])
        # A lost fresh monitor must not leave the selected candidate live when
        # the production no-arg factory fails closed to the baseline evaluator.
        store._mutate(lambda doc: doc["canaries"][config.canary_id].pop("monitor", None))
        fallback = c01.make_tower_readiness_evaluator(**kwargs)
        baseline_calls = []
        result = fallback(root, {"id": "TEST::PROMOTED"},
                          lambda: baseline_calls.append(True) or self.readiness())
        self.assertEqual(result, self.readiness())
        self.assertEqual(baseline_calls, [True])
        self.assertEqual(store.read_selection()["variant"], "baseline")
        self.assertEqual(store.get(config.canary_id)["state"], "ROLLED_BACK")

    def test_production_metadata_uses_lowercase_stratum_but_uppercase_scope(self):
        from .semantics import taxonomy
        from .live_tower import LIVE_TOWER_NAME, build_live_tower_payload
        (self.root / "CONTROL.json").write_text("{}", encoding="utf-8")
        self.store.initialize(self.config)
        manifest = build_live_tower_payload(self.root)
        (self.root / LIVE_TOWER_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        domains = taxonomy()["domains"]
        public_domain = next(item for item in domains if item.get("projection_policy") != "PRIVATE_ONLY")
        public_topic = public_domain["subdomains"][0]["topics"][0]["id"]
        private = c01._tower_readiness_metadata(self.root, {"id": "TEST::private", "private": True,
                                                              "recipe": "R"})
        public = c01._tower_readiness_metadata(self.root, {"id": "TEST::public", "recipe": "R",
                                                            "semantic": {"topic_id": public_topic}})
        self.assertEqual(private["stratum"], "private")
        self.assertEqual(private["access_scope"], "PRIVATE")
        self.assertEqual(public["stratum"], "public")
        self.assertEqual(public["access_scope"], "PUBLIC")

    def test_private_tower_document_pack_materialize_round_trip_is_not_projected(self):
        from .live_tower import build_live_tower_payload, materialize_live_tower, verify_live_tower
        from .public_projection import build_public_projection

        (self.root / "CONTROL.json").write_text(
            json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}), encoding="utf-8")
        private_intent = "PRIVATE_INTENT_SENTINEL"
        def add_private_row(doc):
            doc["canaries"][self.config.canary_id]["observations"].append({
                "intent_id": private_intent, "candidate_evaluated": True,
                "candidate_evaluation_count": 1, "occurred_at": c01.iso_utc(self.now),
                "stratum": "private",
            })
        self.store._mutate(add_private_row)
        packed = build_live_tower_payload(self.root)
        revision = verify_live_tower(packed)
        wire = c01.canonical_json(packed)
        materialized, metadata = materialize_live_tower(wire, self.root / "round-trip")
        self.assertEqual(metadata["tower_revision"], revision)
        round_store = c01.TowerCanaryStore(materialized)
        self.assertEqual(round_store.get(self.config.canary_id)["observations"][0]["intent_id"],
                         private_intent)
        repacked = build_live_tower_payload(materialized, base=packed)
        self.assertEqual(verify_live_tower(repacked), revision)
        projection = build_public_projection(materialized)
        projected_bytes = json.dumps(projection, ensure_ascii=False)
        self.assertNotIn(private_intent, projected_bytes)
        self.assertNotIn(c01.TowerCanaryStore.DOCUMENT, projected_bytes)

    def test_c01_proposal_envelope_is_narrow_and_discards_claimed_authority(self):
        from .inbox_apply import ProposalError, proposal_to_requests
        envelope = {
            "kind": "C01_CANARY", "source": "DENER", "created_at": "2099-01-01T00:00:00Z",
            "payload": {"action": "INSTALL_CONFIG", "config": self.config.proposal_payload()},
        }
        request, = proposal_to_requests(envelope, self.root)
        self.assertEqual(request["nexo_operation"], "OPERATIONAL_CANARY")
        self.assertEqual(request["action"], "INSTALL_CONFIG")
        self.assertEqual(request["config"], self.config.proposal_payload())
        self.assertNotIn("source", request)
        self.assertNotIn("created_at", request)

        forged = {**envelope, "payload": {**envelope["payload"], "source": "DENER"}}
        with self.assertRaises(ProposalError):
            proposal_to_requests(forged, self.root)


if __name__ == "__main__":
    unittest.main()
