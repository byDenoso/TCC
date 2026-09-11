import unittest

from nexo_control_plane.models import Backend, Role, WorkDomain, WorkRecord, WorkStatus
from nexo_control_plane.policy import (
    InvalidEngineeringSignal,
    engineering_from_signal,
    knowledge_namespace,
    may_create_work,
    science_review_required,
)
from nexo_control_plane.router import route


def work(domain, runtime="LIGHT", status=WorkStatus.READY):
    return WorkRecord(
        work_id="W1",
        thread_id=f"THR::{domain.value}::ROOT",
        domain=domain,
        status=status,
        runtime_requirement=runtime,
    )


class PolicyTests(unittest.TestCase):
    def test_advisor_is_science_only(self):
        self.assertTrue(may_create_work(Role.ADVISOR, WorkDomain.SCIENCE))
        self.assertFalse(may_create_work(Role.ADVISOR, WorkDomain.ENGINEERING))
        self.assertFalse(may_create_work(Role.ADVISOR, WorkDomain.SYSTEM))

    def test_core_may_create_engineering_but_not_science_hypotheses(self):
        self.assertTrue(may_create_work(Role.CORE, WorkDomain.ENGINEERING))
        self.assertTrue(may_create_work(Role.CORE, WorkDomain.SYSTEM))
        self.assertFalse(may_create_work(Role.CORE, WorkDomain.SCIENCE))

    def test_knowledge_namespace_is_domain_separated(self):
        self.assertEqual(knowledge_namespace(work(WorkDomain.SCIENCE)), "OBJECT")
        self.assertEqual(knowledge_namespace(work(WorkDomain.ENGINEERING)), "PROCEDURAL")

    def test_scientific_numerics_change_requires_science_review(self):
        eng = work(WorkDomain.ENGINEERING, "CODE")
        eng.affects_scientific_numerics = True
        self.assertTrue(science_review_required(eng))
        eng.affects_scientific_numerics = False
        self.assertFalse(science_review_required(eng))

    def test_engineering_work_only_from_typed_signal(self):
        parent = work(WorkDomain.SCIENCE, "HEAVY")
        eng = engineering_from_signal("CAPABILITY_GAP", parent)
        self.assertEqual(eng.domain, WorkDomain.ENGINEERING)
        self.assertEqual(eng.parent_id, parent.work_id)
        self.assertEqual(eng.execution_backend, Backend.GITHUB_ENGINEERING)
        procedural = engineering_from_signal("PROCEDURAL_HYPOTHESIS", parent)
        self.assertEqual(procedural.domain, WorkDomain.ENGINEERING)
        self.assertEqual(procedural.priority, "MEDIUM")
        self.assertEqual(procedural.work_type, "ENGINEERING_IMPROVEMENT")
        with self.assertRaises(InvalidEngineeringSignal):
            engineering_from_signal("ADVISOR_FEELS_LIKE_REFACTORING", parent)


class RouterTests(unittest.TestCase):
    def test_heavy_science_routes_to_github_science(self):
        self.assertEqual(route(work(WorkDomain.SCIENCE, "HEAVY")), Backend.GITHUB_SCIENCE)

    def test_light_science_stays_local(self):
        self.assertEqual(route(work(WorkDomain.SCIENCE, "LIGHT")), Backend.LOCAL)

    def test_engineering_code_routes_to_github_engineering(self):
        self.assertEqual(route(work(WorkDomain.ENGINEERING, "CODE")), Backend.GITHUB_ENGINEERING)

    def test_olympus_defaults_local(self):
        self.assertEqual(route(work(WorkDomain.OLYMPUS, "HEAVY")), Backend.LOCAL)

    def test_waiting_dependency_does_not_dispatch(self):
        self.assertEqual(route(work(WorkDomain.SCIENCE, "HEAVY", WorkStatus.WAIT_DEPENDENCY)), Backend.WAIT_DEPENDENCY)


if __name__ == "__main__":
    unittest.main()
