import unittest

from runtime.nexo_core.canary import run_v05_canary
from runtime.nexo_core.ssot import event_row_to_event, work_row_to_entity


class NexoCoreShadowTests(unittest.TestCase):
    def test_work_row_maps_existing_ssot_without_requiring_v05_columns(self):
        row = {
            "work_id": "W-SHADOW-1",
            "question": "Shadow migration canary",
            "status": "BLOCKED",
            "domain": "SCIENCE",
            "dependency_ids": "WORK::W-0;WORK::W-BASE",
            "resource_keys": "SOURCE::A;SOURCE::B",
            "result_ref": "ARTIFACT::R-1",
            "verification_status": "PENDING",
        }

        entity = work_row_to_entity(row, default_writer_role="Executor")

        self.assertEqual(entity.entity_ref, "WORK::W-SHADOW-1")
        self.assertEqual(entity.state, "BLOCKED")
        self.assertEqual(entity.entity_version, 1)
        self.assertEqual(entity.writer_role, "Executor")
        self.assertEqual(entity.data["dependency_ids"], ["WORK::W-0", "WORK::W-BASE"])
        self.assertEqual(entity.data["resource_keys"], ["SOURCE::A", "SOURCE::B"])
        self.assertEqual(entity.data["result_ref"], "ARTIFACT::R-1")

    def test_work_row_prefers_explicit_v05_write_metadata(self):
        row = {
            "work_id": "W-SHADOW-2",
            "status": "RUNNING",
            "entity_version": "7",
            "last_event_id": "EVT-7",
            "last_correlation_id": "CORR-7",
            "writer_role": "Advisor",
        }

        entity = work_row_to_entity(row, default_writer_role="Executor")

        self.assertEqual(entity.entity_version, 7)
        self.assertEqual(entity.writer_role, "Advisor")
        self.assertEqual(entity.last_event_id, "EVT-7")
        self.assertEqual(entity.last_correlation_id, "CORR-7")

    def test_event_row_derives_work_entity_ref_for_current_schema(self):
        row = {
            "event_id": "EVT-9",
            "work_id": "W-SHADOW-2",
            "event_type": "STATE_TRANSITION",
            "correlation_id": "CORR-9",
            "source_role": "Executor",
            "state_from": "READY",
            "state_to": "RUNNING",
            "resource_key": "WORK::W-SHADOW-2",
            "dedupe_key": "D-9",
            "run_id": "RUN-9",
        }

        event = event_row_to_event(row)

        self.assertEqual(event.entity_ref, "WORK::W-SHADOW-2")
        self.assertEqual(event.event_id, "EVT-9")
        self.assertEqual(event.dedupe_key, "D-9")

    def test_v05_canary_proves_transition_readback_and_snapshot(self):
        result = run_v05_canary(generated_at="2026-09-11T21:00:00-03:00")

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["readback"], "PASS")
        self.assertEqual(result["snapshot_errors"], [])
        self.assertEqual(result["snapshot"]["overview"]["pass"], 1)
        node = next(node for node in result["snapshot"]["nodes"] if node["id"] == "WORK::W-V05-CANARY")
        self.assertEqual(node["status"], "PASS")
        self.assertEqual(node["version"], 3)


if __name__ == "__main__":
    unittest.main()
