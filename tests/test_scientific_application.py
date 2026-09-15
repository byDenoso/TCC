import unittest

from nexo_control_plane.scientific_intake import (
    CapabilityRef,
    ExistingTestRef,
    execution_subject,
    scientific_fingerprint,
)
from nexo_control_plane.scientific_application import ScientificIntakeApplication
from nexo_control_plane.scientific_submit import SubmitReceipt


class FakeCatalog:
    def __init__(self, existing=None, capabilities=None):
        self._existing = list(existing or [])
        self._capabilities = list(capabilities or [])

    def existing_tests(self):
        return list(self._existing)

    def capabilities(self):
        return list(self._capabilities)


class FakeSubmitter:
    def __init__(self):
        self.plans = []

    def submit(self, plan):
        self.plans.append(plan)
        return SubmitReceipt(
            test_id=plan.test_id,
            state=plan.disposition.value if plan.disposition.value != "READY" else "DISPATCHED",
            correlation_id=plan.correlation_id,
            canonical_readback=True,
            dispatch_ref="github:commit:123" if plan.disposition.value == "READY" else None,
        )


class ScientificApplicationTests(unittest.TestCase):
    def test_execution_subject_removes_command_verb(self):
        self.assertEqual(execution_subject("Teste PEER sem SH0ES"), "PEER sem SH0ES")
        self.assertEqual(execution_subject("Execute PEER sem SH0ES"), "PEER sem SH0ES")
        self.assertEqual(execution_subject("Faça o teste PEER sem SH0ES"), "PEER sem SH0ES")

    def test_two_commands_become_two_independent_submissions(self):
        capability = CapabilityRef(
            capability_id="generic_profile_v1",
            task_id="profile",
            repository="byDenoso/TCC",
            source_revision="abc123",
            runtime_requirement="heavy",
            required_outputs=("result.json",),
            supported_methods=("profile likelihood",),
        )
        catalog = FakeCatalog(capabilities=[capability])
        submitter = FakeSubmitter()
        app = ScientificIntakeApplication(catalog, submitter)
        receipts = app.submit_utterance(
            "Teste PEER sem SH0ES; Execute PEER contra pNGB",
            defaults={"method": "profile likelihood"},
        )
        self.assertEqual(len(receipts), 2)
        self.assertEqual(len(submitter.plans), 2)
        self.assertEqual(submitter.plans[0].spec.question, "PEER sem SH0ES")
        self.assertEqual(submitter.plans[1].spec.question, "PEER contra pNGB")
        self.assertNotEqual(receipts[0]["test_id"], receipts[1]["test_id"])

    def test_equivalent_command_verbs_share_fingerprint_and_attach(self):
        submitter = FakeSubmitter()
        probe_app = ScientificIntakeApplication(FakeCatalog(), submitter)
        first = probe_app.submit_utterance("Teste PEER sem SH0ES")[0]
        fingerprint = first["fingerprint"]

        existing = ExistingTestRef(
            test_id=first["test_id"],
            fingerprint=fingerprint,
            status="RUNNING",
        )
        submitter2 = FakeSubmitter()
        app = ScientificIntakeApplication(FakeCatalog(existing=[existing]), submitter2)
        second = app.submit_utterance("Execute peer sem sh0es")[0]
        self.assertEqual(second["fingerprint"], fingerprint)
        self.assertEqual(second["state"], "ATTACH_EXISTING")

    def test_defaults_are_bound_into_scientific_spec(self):
        submitter = FakeSubmitter()
        app = ScientificIntakeApplication(FakeCatalog(), submitter)
        app.submit_utterance(
            "Rode o teste decisivo",
            defaults={
                "datasets": ["DESI DR2", "Planck"],
                "rival": "LCDM",
                "decision_rule": "p < 0.01",
                "test_group_id": "TEST_GROUP::DETECTION",
            },
        )
        spec = submitter.plans[0].spec
        self.assertEqual(spec.datasets, ("DESI DR2", "Planck"))
        self.assertEqual(spec.rival, "LCDM")
        self.assertEqual(spec.decision_rule, "p < 0.01")
        self.assertEqual(spec.test_group_id, "TEST_GROUP::DETECTION")


if __name__ == "__main__":
    unittest.main()
