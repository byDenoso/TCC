import unittest

from nexo_control_plane.events import make_transition_event
from nexo_control_plane.models import Backend, Role, WorkDomain, WorkRecord, WorkStatus


def work():
    return WorkRecord(
        work_id="T-DE042",
        thread_id="THR::SCIENCE::ROOT",
        domain=WorkDomain.SCIENCE,
        status=WorkStatus.RUNNING,
        execution_backend=Backend.GITHUB_SCIENCE,
        correlation_id="CORR-DE042",
        resource_keys=("science:T-DE042",),
    )


class EventTests(unittest.TestCase):
    def test_same_transition_has_stable_dedupe_key(self):
        a = make_transition_event(
            work(), Role.EXECUTOR, Role.LEARNER, WorkStatus.RUNNING, WorkStatus.RESULT_AVAILABLE, "artifact:1"
        )
        b = make_transition_event(
            work(), Role.EXECUTOR, Role.LEARNER, WorkStatus.RUNNING, WorkStatus.RESULT_AVAILABLE, "artifact:1"
        )
        self.assertEqual(a.dedupe_key, b.dedupe_key)
        self.assertEqual(a.event_id, b.event_id)

    def test_different_transition_changes_dedupe_key(self):
        a = make_transition_event(
            work(), Role.EXECUTOR, Role.LEARNER, WorkStatus.RUNNING, WorkStatus.RESULT_AVAILABLE, "artifact:1"
        )
        b = make_transition_event(
            work(), Role.EXECUTOR, Role.LEARNER, WorkStatus.RESULT_AVAILABLE, WorkStatus.VERIFYING, "artifact:1"
        )
        self.assertNotEqual(a.dedupe_key, b.dedupe_key)

    def test_event_keeps_role_and_correlation_boundaries(self):
        event = make_transition_event(
            work(), Role.CORE, Role.EXECUTOR, WorkStatus.WAIT_DEPENDENCY, WorkStatus.READY, "dependency:ENG-1"
        )
        self.assertEqual(event.source_role, "CORE")
        self.assertEqual(event.target_role, "EXECUTOR")
        self.assertEqual(event.correlation_id, "CORR-DE042")
        self.assertEqual(event.resource_key, "science:T-DE042")


if __name__ == "__main__":
    unittest.main()
