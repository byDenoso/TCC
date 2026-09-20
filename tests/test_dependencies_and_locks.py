import unittest

from nexo_control_plane.dependencies import dependency_gate, dependencies_satisfied
from nexo_control_plane.locks import acquireable, conflicts
from nexo_control_plane.models import Backend, WorkDomain, WorkRecord, WorkStatus


def work(work_id, status=WorkStatus.READY, deps=(), resources=()):
    return WorkRecord(
        work_id=work_id,
        thread_id="THR::SCIENCE::ROOT",
        domain=WorkDomain.SCIENCE,
        status=status,
        execution_backend=Backend.GITHUB_SCIENCE,
        dependency_ids=tuple(deps),
        resource_keys=tuple(resources),
    )


class DependencyTests(unittest.TestCase):
    def test_done_and_verified_dependencies_satisfy(self):
        target = work("T3", deps=("T1", "T2"))
        by_id = {"T1": work("T1", WorkStatus.DONE), "T2": work("T2", WorkStatus.VERIFIED)}
        self.assertTrue(dependencies_satisfied(target, by_id))
        self.assertEqual(dependency_gate(target, by_id), WorkStatus.READY)

    def test_missing_dependency_waits(self):
        target = work("T3", deps=("T1",))
        self.assertFalse(dependencies_satisfied(target, {}))
        self.assertEqual(dependency_gate(target, {}), WorkStatus.WAIT_DEPENDENCY)

    def test_unfinished_dependency_waits(self):
        target = work("T3", deps=("T1",))
        by_id = {"T1": work("T1", WorkStatus.RUNNING)}
        self.assertEqual(dependency_gate(target, by_id), WorkStatus.WAIT_DEPENDENCY)

    def test_failed_dependency_blocks(self):
        target = work("T3", deps=("T1",))
        by_id = {"T1": work("T1", WorkStatus.FAILED)}
        self.assertEqual(dependency_gate(target, by_id), WorkStatus.BLOCKED)


class LockTests(unittest.TestCase):
    def test_disjoint_resources_do_not_conflict(self):
        a = work("A", resources=("science:T-DE042",))
        b = work("B", resources=("science:T-DM018",))
        self.assertFalse(conflicts(a, b))
        self.assertTrue(acquireable(a, [b]))

    def test_shared_resource_conflicts(self):
        a = work("A", resources=("repo:TCC:portable_camb",))
        b = work("B", status=WorkStatus.RUNNING, resources=("repo:TCC:portable_camb", "science:T-DM018"))
        self.assertTrue(conflicts(a, b))
        self.assertFalse(acquireable(a, [b]))

    def test_terminal_work_does_not_hold_lock(self):
        a = work("A", resources=("repo:TCC:portable_camb",))
        b = work("B", status=WorkStatus.DONE, resources=("repo:TCC:portable_camb",))
        self.assertTrue(acquireable(a, [b]))


if __name__ == "__main__":
    unittest.main()
