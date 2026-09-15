import unittest

from nexo_control_plane.scientific_intake import (
    CapabilityRef,
    ExistingTestRef,
    IntakeDisposition,
    ScientificIntakePlan,
    ScientificTestSpec,
    scientific_fingerprint,
)
from nexo_control_plane.scientific_submit import ScientificSubmitService, build_dispatch_request


class FakeTower:
    def __init__(self, readback_override=None, persist_error=None):
        self.calls = []
        self.entities = {}
        self.readback_override = readback_override
        self.persist_error = persist_error

    def persist_test(self, entity):
        self.calls.append(("persist", entity["id"]))
        if self.persist_error:
            raise self.persist_error
        self.entities[entity["id"]] = dict(entity)
        return dict(entity)

    def readback_test(self, test_id):
        self.calls.append(("readback", test_id))
        if self.readback_override is not None:
            return dict(self.readback_override)
        return dict(self.entities[test_id])

    def mark_dispatched(self, test_id, dispatch_ref, correlation_id):
        self.calls.append(("mark_dispatched", test_id))
        entity = dict(self.entities[test_id])
        entity["status"] = "DISPATCHED"
        entity["dispatch_ref"] = dispatch_ref
        entity["correlation_id"] = correlation_id
        self.entities[test_id] = entity
        return dict(entity)


class FakeDispatch:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def submit(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return "github:commit:abc123"


def ready_plan():
    spec = ScientificTestSpec(
        question="PEER sem SH0ES",
        datasets=("DESI DR2", "Planck"),
        rival="LCDM",
        method="profile likelihood",
        decision_rule="p_global < 0.0027",
        execution_capability="peer_profile_v1",
    )
    cap = CapabilityRef(
        capability_id="peer_profile_v1",
        task_id="peer_profile",
        repository="byDenoso/TCC",
        source_revision="abc123",
        runtime_requirement="heavy",
        required_outputs=("result.json",),
    )
    fp = scientific_fingerprint(spec)
    return ScientificIntakePlan(
        spec=spec,
        fingerprint=fp,
        disposition=IntakeDisposition.READY,
        test_id="T-CHAT-ABC123",
        correlation_id="CORR-ABC123",
        capability=cap,
    )


class ScientificSubmitTests(unittest.TestCase):
    def test_tower_persist_and_readback_happen_before_dispatch(self):
        tower = FakeTower()
        dispatch = FakeDispatch()
        receipt = ScientificSubmitService(tower, dispatch).submit(ready_plan())
        self.assertEqual(tower.calls[0][0], "persist")
        self.assertEqual(tower.calls[1][0], "readback")
        self.assertEqual(len(dispatch.calls), 1)
        self.assertEqual(receipt.state, "DISPATCHED")
        self.assertTrue(receipt.canonical_readback)
        self.assertIn(("mark_dispatched", "T-CHAT-ABC123"), tower.calls)

    def test_failed_readback_prevents_dispatch(self):
        plan = ready_plan()
        bad = {"id": plan.test_id, "scientific_fingerprint": "sha256:wrong", "status": "READY"}
        tower = FakeTower(readback_override=bad)
        dispatch = FakeDispatch()
        with self.assertRaises(ValueError):
            ScientificSubmitService(tower, dispatch).submit(plan)
        self.assertEqual(dispatch.calls, [])

    def test_dispatch_failure_leaves_retryable_ready_receipt(self):
        tower = FakeTower()
        dispatch = FakeDispatch(error=RuntimeError("push failed"))
        receipt = ScientificSubmitService(tower, dispatch).submit(ready_plan())
        self.assertEqual(receipt.state, "READY")
        self.assertTrue(receipt.retryable)
        self.assertTrue(receipt.canonical_readback)
        self.assertEqual(tower.entities[receipt.test_id]["status"], "READY")

    def test_duplicates_do_not_persist_or_dispatch(self):
        spec = ScientificTestSpec(question="same test")
        existing = ExistingTestRef("T-OLD", scientific_fingerprint(spec), "VERIFIED", "RESULT::T-OLD")
        plan = ScientificIntakePlan(
            spec=spec,
            fingerprint=existing.fingerprint,
            disposition=IntakeDisposition.DUPLICATE_TERMINAL,
            test_id=existing.test_id,
            correlation_id="CORR-T-OLD",
            existing=existing,
        )
        tower = FakeTower()
        dispatch = FakeDispatch()
        receipt = ScientificSubmitService(tower, dispatch).submit(plan)
        self.assertEqual(receipt.state, "DUPLICATE_TERMINAL")
        self.assertEqual(tower.calls, [])
        self.assertEqual(dispatch.calls, [])

    def test_capability_gap_is_persisted_without_dispatch(self):
        spec = ScientificTestSpec(question="novel test")
        plan = ScientificIntakePlan(
            spec=spec,
            fingerprint=scientific_fingerprint(spec),
            disposition=IntakeDisposition.CAPABILITY_GAP,
            test_id="T-CHAT-GAP",
            correlation_id="CORR-GAP",
        )
        tower = FakeTower()
        dispatch = FakeDispatch()
        receipt = ScientificSubmitService(tower, dispatch).submit(plan)
        self.assertEqual(receipt.state, "CAPABILITY_GAP")
        self.assertEqual(dispatch.calls, [])
        self.assertEqual(tower.entities[plan.test_id]["execution_state"], "CAPABILITY_GAP")

    def test_dispatch_request_uses_existing_execution_adapter_contract(self):
        request = build_dispatch_request(ready_plan())
        self.assertEqual(request["domain"], "SCIENCE")
        self.assertEqual(request["adapter"], "execution")
        self.assertEqual(request["source_revision"], "abc123")
        self.assertTrue(request["args"]["execute"])
        self.assertEqual(request["args"]["test_id"], "T-CHAT-ABC123")
        self.assertEqual(request["args"]["task_id"], "peer_profile")
        self.assertEqual(request["args"]["required_outputs"], ["result.json"])


if __name__ == "__main__":
    unittest.main()
