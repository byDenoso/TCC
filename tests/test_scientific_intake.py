import unittest

from nexo_control_plane.scientific_intake import (
    CapabilityRef,
    ExistingTestRef,
    IntakeDisposition,
    ScientificTestSpec,
    is_execution_utterance,
    parse_execution_clauses,
    plan_scientific_test,
    scientific_fingerprint,
)


class ScientificIntakeParsingTests(unittest.TestCase):
    def test_explicit_execution_commands_are_recognized(self):
        for text in (
            "Teste PEER sem SH0ES",
            "Rode o null global",
            "Execute D02",
            "Faça o teste de prior sensitivity",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_execution_utterance(text))

    def test_advisory_or_question_language_does_not_execute(self):
        for text in (
            "Vale a pena testar PEER sem SH0ES?",
            "O que acha do teste D02?",
            "Explique o teste de prior sensitivity",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_execution_utterance(text))

    def test_multiple_execution_clauses_are_split(self):
        clauses = parse_execution_clauses(
            "Teste PEER sem SH0ES; Teste PEER contra pNGB\nExecute o holdout DESI"
        )
        self.assertEqual(
            clauses,
            [
                "Teste PEER sem SH0ES",
                "Teste PEER contra pNGB",
                "Execute o holdout DESI",
            ],
        )

    def test_fingerprint_is_stable_under_formatting_and_case(self):
        a = ScientificTestSpec(
            question="PEER   sem SH0ES",
            datasets=("DESI DR2", "Planck"),
            rival="LCDM",
            decision_rule="p_global < 0.0027",
        )
        b = ScientificTestSpec(
            question="peer sem sh0es",
            datasets=("planck", "desi dr2"),
            rival="lcdm",
            decision_rule="P_GLOBAL < 0.0027",
        )
        self.assertEqual(scientific_fingerprint(a), scientific_fingerprint(b))

    def test_fingerprint_changes_for_material_scientific_change(self):
        base = ScientificTestSpec(
            question="PEER sem SH0ES",
            datasets=("DESI DR2", "Planck"),
            rival="LCDM",
        )
        changed = ScientificTestSpec(
            question="PEER com SH0ES",
            datasets=("DESI DR2", "Planck", "SH0ES"),
            rival="LCDM",
        )
        self.assertNotEqual(scientific_fingerprint(base), scientific_fingerprint(changed))


class ScientificIntakePlanningTests(unittest.TestCase):
    def setUp(self):
        self.spec = ScientificTestSpec(
            question="PEER sem SH0ES",
            datasets=("DESI DR2", "Planck"),
            rival="LCDM",
            method="profile likelihood",
            execution_capability="peer_profile_v1",
        )
        self.fp = scientific_fingerprint(self.spec)
        self.cap = CapabilityRef(
            capability_id="peer_profile_v1",
            task_id="peer_profile",
            repository="byDenoso/TCC",
            source_revision="abc123",
            runtime_requirement="heavy",
            required_outputs=("result.json",),
        )

    def test_terminal_duplicate_is_reused_without_new_identity(self):
        existing = ExistingTestRef(
            test_id="T-OLD-001",
            fingerprint=self.fp,
            status="VERIFIED",
            result_ref="RESULT::T-OLD-001",
        )
        plan = plan_scientific_test(self.spec, [existing], [self.cap])
        self.assertEqual(plan.disposition, IntakeDisposition.DUPLICATE_TERMINAL)
        self.assertEqual(plan.test_id, "T-OLD-001")
        self.assertIsNone(plan.capability)

    def test_active_duplicate_attaches_without_redispatch(self):
        existing = ExistingTestRef(
            test_id="T-ACTIVE-001",
            fingerprint=self.fp,
            status="RUNNING",
        )
        plan = plan_scientific_test(self.spec, [existing], [self.cap])
        self.assertEqual(plan.disposition, IntakeDisposition.ATTACH_EXISTING)
        self.assertEqual(plan.test_id, "T-ACTIVE-001")
        self.assertIsNone(plan.capability)

    def test_exact_declared_capability_makes_new_test_ready(self):
        plan = plan_scientific_test(self.spec, [], [self.cap])
        self.assertEqual(plan.disposition, IntakeDisposition.READY)
        self.assertEqual(plan.capability, self.cap)
        self.assertTrue(plan.test_id.startswith("T-CHAT-"))
        self.assertTrue(plan.correlation_id.startswith("CORR-"))

    def test_compatible_method_capability_is_resolved_when_not_explicit(self):
        spec = ScientificTestSpec(
            question="Profile PEER",
            method="profile likelihood",
        )
        cap = CapabilityRef(
            capability_id="generic_profile_v1",
            task_id="profile",
            repository="byDenoso/TCC",
            source_revision="def456",
            runtime_requirement="heavy",
            required_outputs=("result.json",),
            supported_methods=("profile likelihood",),
        )
        plan = plan_scientific_test(spec, [], [cap])
        self.assertEqual(plan.disposition, IntakeDisposition.READY)
        self.assertEqual(plan.capability, cap)

    def test_missing_capability_is_capability_gap_not_blocked(self):
        plan = plan_scientific_test(self.spec, [], [])
        self.assertEqual(plan.disposition, IntakeDisposition.CAPABILITY_GAP)
        self.assertIsNone(plan.capability)


if __name__ == "__main__":
    unittest.main()
