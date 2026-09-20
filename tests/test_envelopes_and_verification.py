import unittest

from nexo_control_plane.envelopes import ExecutionEnvelope, ResultEnvelope, build_execution_envelope
from nexo_control_plane.models import Backend, WorkDomain, WorkRecord, WorkStatus
from nexo_control_plane.verification import can_close, can_learn, result_is_verifiable


def work(status=WorkStatus.READY, verification=""):
    return WorkRecord(
        work_id="T-DE042",
        thread_id="THR::SCIENCE::ROOT",
        domain=WorkDomain.SCIENCE,
        status=status,
        execution_backend=Backend.GITHUB_SCIENCE,
        runtime_requirement="NESTED",
        correlation_id="CORR-DE042",
        lane_id="DE",
        attempt=2,
        resource_keys=("science:T-DE042",),
        verification_status=verification,
        work_type="nested_sampling",
    )


class EnvelopeTests(unittest.TestCase):
    def test_execution_envelope_freezes_identity_and_hash(self):
        envelope = build_execution_envelope(
            work(), source_revision="abc123", input_hash="sha256:input", seed=42
        )
        self.assertIsInstance(envelope, ExecutionEnvelope)
        self.assertEqual(envelope.work_id, "T-DE042")
        self.assertEqual(envelope.correlation_id, "CORR-DE042")
        self.assertEqual(envelope.source_revision, "abc123")
        self.assertEqual(envelope.input_hash, "sha256:input")
        self.assertEqual(envelope.seed, 42)
        self.assertEqual(envelope.attempt, 2)

    def test_execution_envelope_rejects_missing_source_revision(self):
        with self.assertRaises(ValueError):
            build_execution_envelope(work(), source_revision="", input_hash="sha256:input")

    def test_result_envelope_rejects_missing_identity(self):
        with self.assertRaises(ValueError):
            ResultEnvelope(
                work_id="",
                correlation_id="CORR",
                backend_run_id="run-1",
                status="COMPLETED",
                exit_code=0,
                artifact_ref="artifact",
                checkpoint_ref="",
                runtime_seconds=10.0,
                result_hash="sha256:r",
                source_revision="abc123",
            )


class VerificationTests(unittest.TestCase):
    def test_complete_hashed_result_is_verifiable(self):
        result = ResultEnvelope(
            work_id="T-DE042",
            correlation_id="CORR-DE042",
            backend_run_id="run-1",
            status="COMPLETED",
            exit_code=0,
            artifact_ref="artifact:1",
            checkpoint_ref="",
            runtime_seconds=10.0,
            result_hash="sha256:r",
            source_revision="abc123",
        )
        self.assertTrue(result_is_verifiable(result))

    def test_raw_result_cannot_teach_or_close(self):
        raw = work(WorkStatus.RESULT_AVAILABLE, "")
        self.assertFalse(can_learn(raw))
        self.assertFalse(can_close(raw))

    def test_verified_external_result_can_teach_and_close(self):
        verified = work(WorkStatus.VERIFIED, "PASS")
        self.assertTrue(can_learn(verified))
        self.assertTrue(can_close(verified))

    def test_done_external_without_verification_fails_closed(self):
        legacy_like = work(WorkStatus.DONE, "")
        self.assertFalse(can_learn(legacy_like))
        self.assertFalse(can_close(legacy_like))


if __name__ == "__main__":
    unittest.main()
