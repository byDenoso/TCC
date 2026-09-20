import unittest

from nexo_control_plane.models import Backend, WorkDomain, WorkRecord, WorkStatus
from nexo_control_plane.state_machine import InvalidTransition, can_transition, transition


class StateMachineTests(unittest.TestCase):
    def make_work(self, status=WorkStatus.READY, backend=Backend.GITHUB_SCIENCE):
        return WorkRecord(
            work_id="T-DE042",
            thread_id="THR::SCIENCE::ROOT",
            domain=WorkDomain.SCIENCE,
            status=status,
            execution_backend=backend,
            runtime_requirement="HEAVY",
        )

    def test_valid_async_transition_chain(self):
        chain = [
            WorkStatus.READY,
            WorkStatus.QUEUED,
            WorkStatus.DISPATCHED,
            WorkStatus.RUNNING,
            WorkStatus.RESULT_AVAILABLE,
            WorkStatus.VERIFYING,
            WorkStatus.VERIFIED,
            WorkStatus.DONE,
        ]
        for old, new in zip(chain, chain[1:]):
            self.assertTrue(can_transition(old, new, external_material=True), f"{old}->{new}")

    def test_external_result_cannot_jump_to_done(self):
        self.assertFalse(
            can_transition(WorkStatus.RESULT_AVAILABLE, WorkStatus.DONE, external_material=True)
        )

    def test_invalid_jump_fails_closed(self):
        work = self.make_work(status=WorkStatus.READY)
        with self.assertRaises(InvalidTransition):
            transition(work, WorkStatus.DONE)
        self.assertEqual(work.status, WorkStatus.READY)

    def test_legacy_done_remains_readable(self):
        work = self.make_work(status=WorkStatus.DONE)
        self.assertEqual(work.status, WorkStatus.DONE)


if __name__ == "__main__":
    unittest.main()
