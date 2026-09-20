import unittest

from nexo_control_plane.models import Backend, WorkDomain, WorkRecord, WorkStatus
from nexo_control_plane.reconcile import ExternalRunState, reconcile


def work(status, run_id="run-1"):
    return WorkRecord(
        work_id="T-DE042",
        thread_id="THR::SCIENCE::ROOT",
        domain=WorkDomain.SCIENCE,
        status=status,
        execution_backend=Backend.GITHUB_SCIENCE,
        runtime_requirement="NESTED",
        correlation_id="CORR-DE042",
        external_run_id=run_id,
    )


class ReconcileTests(unittest.TestCase):
    def test_running_success_moves_to_result_available(self):
        ext = ExternalRunState("run-1", "CORR-DE042", "COMPLETED", 0, "artifact:1", "", "sha256:r")
        decision = reconcile(work(WorkStatus.RUNNING), ext)
        self.assertEqual(decision.next_status, WorkStatus.RESULT_AVAILABLE)
        self.assertEqual(decision.action, "INGEST_RESULT")

    def test_failed_with_checkpoint_moves_to_checkpointed(self):
        ext = ExternalRunState("run-1", "CORR-DE042", "FAILED", 124, "artifact:partial", "checkpoint:7", "")
        decision = reconcile(work(WorkStatus.RUNNING), ext)
        self.assertEqual(decision.next_status, WorkStatus.CHECKPOINTED)
        self.assertEqual(decision.action, "RESUME_ELIGIBLE")

    def test_dispatched_missing_external_run_fails_closed(self):
        decision = reconcile(work(WorkStatus.DISPATCHED), None)
        self.assertEqual(decision.next_status, WorkStatus.BLOCKED)
        self.assertEqual(decision.action, "DISPATCH_MISSING")

    def test_duplicate_run_ids_block(self):
        ext = ExternalRunState(
            "run-1",
            "CORR-DE042",
            "RUNNING",
            None,
            "",
            "",
            "",
            conflicting_run_ids=("run-1", "run-2"),
        )
        decision = reconcile(work(WorkStatus.RUNNING), ext)
        self.assertEqual(decision.next_status, WorkStatus.BLOCKED)
        self.assertEqual(decision.action, "DUPLICATE_RUN_CONFLICT")

    def test_already_aligned_is_noop(self):
        ext = ExternalRunState("run-1", "CORR-DE042", "COMPLETED", 0, "artifact:1", "", "sha256:r")
        decision = reconcile(work(WorkStatus.RESULT_AVAILABLE), ext)
        self.assertEqual(decision.next_status, WorkStatus.RESULT_AVAILABLE)
        self.assertEqual(decision.action, "NO_OP")

    def test_mismatched_correlation_blocks(self):
        ext = ExternalRunState("run-1", "WRONG", "RUNNING", None, "", "", "")
        decision = reconcile(work(WorkStatus.RUNNING), ext)
        self.assertEqual(decision.next_status, WorkStatus.BLOCKED)
        self.assertEqual(decision.action, "IDENTITY_MISMATCH")


if __name__ == "__main__":
    unittest.main()
