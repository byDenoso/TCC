import json
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_core.guard import apply_transition, make_dedupe_key, verify_readback
from runtime.nexo_core.models import CanonicalEntity, CanonicalEvent
from runtime.nexo_core.projection import build_snapshot, validate_snapshot
from runtime.nexo_core.publisher import SnapshotValidationError, publish_snapshot


class NexoCoreV05Tests(unittest.TestCase):
    def test_dedupe_key_is_stable_for_equivalent_payloads(self):
        a = make_dedupe_key(
            role="Executor",
            run_id="RUN-1",
            entity_ref="WORK::W-1",
            event_type="STATE_TRANSITION",
            payload={"b": 2, "a": 1},
        )
        b = make_dedupe_key(
            role="Executor",
            run_id="RUN-1",
            entity_ref="WORK::W-1",
            event_type="STATE_TRANSITION",
            payload={"a": 1, "b": 2},
        )
        self.assertEqual(a, b)

    def test_transition_increments_version_and_binds_event(self):
        entity = CanonicalEntity(
            entity_ref="WORK::W-1",
            state="READY",
            entity_version=3,
            writer_role="Executor",
            data={"label": "Canary"},
        )
        event = CanonicalEvent(
            event_id="EVT-1",
            entity_ref=entity.entity_ref,
            event_type="STATE_TRANSITION",
            correlation_id="CORR-1",
            source_role="Executor",
            state_from="READY",
            state_to="RUNNING",
            resource_key="WORK::W-1",
            dedupe_key="D-1",
        )

        result = apply_transition(
            entity,
            event,
            expected_version=3,
            owner_role="Executor",
            seen_dedupe_keys=set(),
        )

        self.assertEqual(result.status, "APPLIED")
        self.assertEqual(result.entity.state, "RUNNING")
        self.assertEqual(result.entity.entity_version, 4)
        self.assertEqual(result.entity.last_event_id, "EVT-1")
        self.assertEqual(result.entity.last_correlation_id, "CORR-1")

    def test_stale_expected_version_is_rejected(self):
        entity = CanonicalEntity(
            entity_ref="WORK::W-1",
            state="READY",
            entity_version=4,
            writer_role="Executor",
        )
        event = CanonicalEvent(
            event_id="EVT-2",
            entity_ref=entity.entity_ref,
            event_type="STATE_TRANSITION",
            correlation_id="CORR-2",
            source_role="Executor",
            state_from="READY",
            state_to="RUNNING",
            resource_key="WORK::W-1",
            dedupe_key="D-2",
        )

        result = apply_transition(
            entity,
            event,
            expected_version=3,
            owner_role="Executor",
            seen_dedupe_keys=set(),
        )

        self.assertEqual(result.status, "WRITE_CONFLICT_RETRY_REQUIRED")
        self.assertEqual(result.entity, entity)

    def test_duplicate_event_is_noop(self):
        entity = CanonicalEntity(
            entity_ref="WORK::W-1",
            state="READY",
            entity_version=1,
            writer_role="Executor",
        )
        event = CanonicalEvent(
            event_id="EVT-3",
            entity_ref=entity.entity_ref,
            event_type="STATE_TRANSITION",
            correlation_id="CORR-3",
            source_role="Executor",
            state_from="READY",
            state_to="RUNNING",
            resource_key="WORK::W-1",
            dedupe_key="D-3",
        )

        result = apply_transition(
            entity,
            event,
            expected_version=1,
            owner_role="Executor",
            seen_dedupe_keys={"D-3"},
        )

        self.assertEqual(result.status, "NOOP")
        self.assertEqual(result.entity, entity)

    def test_wrong_writer_is_rejected(self):
        entity = CanonicalEntity(
            entity_ref="WORK::W-1",
            state="READY",
            entity_version=1,
            writer_role="Executor",
        )
        event = CanonicalEvent(
            event_id="EVT-4",
            entity_ref=entity.entity_ref,
            event_type="STATE_TRANSITION",
            correlation_id="CORR-4",
            source_role="Learner",
            state_from="READY",
            state_to="RUNNING",
            resource_key="WORK::W-1",
            dedupe_key="D-4",
        )

        result = apply_transition(
            entity,
            event,
            expected_version=1,
            owner_role="Executor",
            seen_dedupe_keys=set(),
        )

        self.assertEqual(result.status, "WRITE_AUTHORITY_CONFLICT")

    def test_readback_mismatch_is_unverified(self):
        expected = CanonicalEntity(
            entity_ref="WORK::W-1",
            state="RUNNING",
            entity_version=2,
            writer_role="Executor",
            last_event_id="EVT-5",
        )
        actual = CanonicalEntity(
            entity_ref="WORK::W-1",
            state="READY",
            entity_version=1,
            writer_role="Executor",
        )

        self.assertEqual(
            verify_readback(expected, actual),
            "CANONICAL_WRITE_UNVERIFIED",
        )

    def test_snapshot_builds_overview_and_graph_from_existing_fields(self):
        entities = [
            CanonicalEntity(
                entity_ref="WORK::W-1",
                state="BLOCKED",
                entity_version=2,
                writer_role="Executor",
                data={
                    "label": "DESI LyA",
                    "domain": "COSMOLOGY",
                    "dependency_ids": ["WORK::W-0"],
                    "evidence_refs": ["SOURCE::DESI-DR2"],
                    "result_ref": "ARTIFACT::RUN-1",
                },
            ),
            CanonicalEntity(
                entity_ref="WORK::W-0",
                state="PASS",
                entity_version=1,
                writer_role="Executor",
                data={"label": "Prior work", "domain": "COSMOLOGY"},
            ),
            CanonicalEntity(
                entity_ref="SOURCE::DESI-DR2",
                state="ACTIVE",
                entity_version=1,
                writer_role="Advisor",
                data={"label": "DESI DR2", "domain": "COSMOLOGY"},
            ),
            CanonicalEntity(
                entity_ref="ARTIFACT::RUN-1",
                state="VERIFIED",
                entity_version=1,
                writer_role="Executor",
                data={"label": "Run artifact", "domain": "COSMOLOGY"},
            ),
        ]

        snapshot = build_snapshot(
            entities,
            snapshot_id="SNAP-1",
            generated_at="2026-09-11T20:00:00-03:00",
            event_cursor="EVT-5",
        )

        self.assertEqual(snapshot["schema_version"], "0.5")
        self.assertEqual(snapshot["overview"]["blocked"], 1)
        self.assertEqual(snapshot["overview"]["pass"], 1)
        edge_types = {edge["type"] for edge in snapshot["edges"]}
        self.assertEqual(edge_types, {"DEPENDS_ON", "EVIDENCED_BY", "PRODUCED"})
        self.assertEqual(validate_snapshot(snapshot), [])

    def test_invalid_snapshot_does_not_replace_last_valid_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nexo-state.json"
            target.write_text(json.dumps({"schema_version": "0.5", "snapshot_id": "OLD"}), encoding="utf-8")
            invalid = {
                "schema_version": "0.5",
                "generated_at": "2026-09-11T20:00:00-03:00",
                "event_cursor": "EVT-1",
                "overview": {},
                "research": {},
                "olympus": {},
                "nexo": {},
                "system": {},
                "nodes": [],
                "edges": [],
            }

            with self.assertRaises(SnapshotValidationError):
                publish_snapshot(invalid, target)

            persisted = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(persisted["snapshot_id"], "OLD")


if __name__ == "__main__":
    unittest.main()
