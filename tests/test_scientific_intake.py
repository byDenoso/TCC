import unittest

from nexo_control_plane.scientific_intake import (
    ScientificTestSpec,
    is_execution_utterance,
    parse_execution_clauses,
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
            question="peer sem shoes",
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


if __name__ == "__main__":
    unittest.main()
