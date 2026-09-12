import unittest

from runtime.nexo_core.guard import apply_transition, make_payload_hash
from runtime.nexo_core.models import CanonicalEntity, CanonicalEvent
from runtime.nexo_core.ssot import event_row_to_event


class NexoEventContractTests(unittest.TestCase):
    def test_transition_binds_expected_and_result_versions(self):
        entity = CanonicalEntity(
            entity_ref="WORK::W-V05-CONTRACT",
            state="READY",
            entity_version=4,
            writer_role="Executor",
        )
        event = CanonicalEvent(
            event_id="EVT-V05-CONTRACT-1",
            entity_ref=entity.entity_ref,
            event_type="STATE_TRANSITION",
            correlation_id="CORR-V05-CONTRACT",
            source_role="Executor",
            state_from="READY",
            state_to="RUNNING",
            resource_key=entity.entity_ref,
            dedupe_key="D-V05-CONTRACT-1",
            payload_hash=make_payload_hash({"state_from": "READY", "state_to": "RUNNING"}),
        )

        result = apply_transition(
            entity,
            event,
            expected_version=4,
            owner_role="Executor",
            seen_dedupe_keys=set(),
        )

        self.assertEqual(result.status, "APPLIED")
        self.assertIsNotNone(result.event)
        self.assertEqual(result.event.expected_entity_version, 4)
        self.assertEqual(result.event.result_entity_version, 5)
        self.assertEqual(result.entity.entity_version, 5)

    def test_mismatched_explicit_event_version_is_rejected(self):
        entity = CanonicalEntity(
            entity_ref="WORK::W-V05-CONTRACT",
            state="READY",
            entity_version=4,
            writer_role="Executor",
        )
        event = CanonicalEvent(
            event_id="EVT-V05-CONTRACT-2",
            entity_ref=entity.entity_ref,
            event_type="STATE_TRANSITION",
            correlation_id="CORR-V05-CONTRACT",
            source_role="Executor",
            state_from="READY",
            state_to="RUNNING",
            resource_key=entity.entity_ref,
            dedupe_key="D-V05-CONTRACT-2",
            expected_entity_version=3,
            result_entity_version=4,
        )

        result = apply_transition(
            entity,
            event,
            expected_version=4,
            owner_role="Executor",
            seen_dedupe_keys=set(),
        )

        self.assertEqual(result.status, "EVENT_VERSION_CONTRACT_CONFLICT")
        self.assertEqual(result.entity, entity)

    def test_event_row_reads_v05_contract_columns(self):
        event = event_row_to_event(
            {
                "event_id": "EVT-V05-CONTRACT-3",
                "entity_ref": "WORK::W-V05-CONTRACT",
                "event_type": "STATE_TRANSITION",
                "correlation_id": "CORR-V05-CONTRACT",
                "source_role": "Executor",
                "state_from": "READY",
                "state_to": "RUNNING",
                "resource_key": "WORK::W-V05-CONTRACT",
                "dedupe_key": "D-V05-CONTRACT-3",
                "expected_entity_version": "4",
                "result_entity_version": "5",
                "payload_hash": "abc123",
                "event_schema_version": "0.5",
            }
        )

        self.assertEqual(event.expected_entity_version, 4)
        self.assertEqual(event.result_entity_version, 5)
        self.assertEqual(event.payload_hash, "abc123")
        self.assertEqual(event.event_schema_version, "0.5")


if __name__ == "__main__":
    unittest.main()
