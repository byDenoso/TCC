from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from .evolution import (
    GENOME_DOC,
    evolution_status,
    incident_reconcile_requests,
    mutation_requests,
    operator_requests,
)
from .tower_apply import apply_document
from .tower_paths import entity_path, fs_path


class IncidentLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "entities" / "artifact").mkdir(parents=True)
        (self.root / "entities" / "test").mkdir(parents=True)
        (self.root / "entities" / "hypothesis").mkdir(parents=True)
        (self.root / "entities" / "lesson").mkdir(parents=True)
        (self.root / "evolution").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def signal(
        self,
        artifact_id: str,
        *,
        code: str = "WRITER_LAG_PATTERN",
        topic_id: str | None = "engineering.nexo.writer",
        source: str = "GUARDIAO",
        domain_id: str = "engineering",
        symptom: str = "detail",
    ) -> None:
        signal = {"code": code, "semantic": {"domain_id": domain_id}, "symptom": symptom}
        if topic_id is not None:
            signal["topic_id"] = topic_id
        payload = {
            "id": artifact_id,
            "kind": "LEARNING_SIGNAL",
            "source": source,
            "created_at": f"2026-09-26T10:{len(list((self.root / 'entities' / 'artifact').glob('*.json'))):02d}:00Z",
            "payload": {"signals": [signal]},
        }
        (self.root / "entities" / "artifact" / f"{artifact_id}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def apply_reconcile(self) -> dict:
        requests = incident_reconcile_requests(self.root)
        self.assertEqual(len(requests), 1)
        receipt = apply_document(self.root, requests[0])
        self.assertTrue(receipt["accepted"])
        return requests[0]["merge"]["incidents"][0]

    def current_incident(self, incident_id: str) -> dict:
        doc = json.loads(fs_path(self.root, "evolution/incidents.json").read_text(encoding="utf-8"))
        return next(item for item in doc["incidents"] if item["incident_id"] == incident_id)

    def test_semantic_dedupe_requires_same_code_and_same_stable_topic(self) -> None:
        self.signal("SIG-A", symptom="first shape")
        self.signal("SIG-B", source="EXECUTOR", symptom="different wording")
        self.signal("SIG-C", topic_id="engineering.nexo.other", symptom="same code, other topic")

        requests = incident_reconcile_requests(self.root)
        self.assertEqual(len(requests), 1)
        incidents = requests[0]["merge"]["incidents"]
        self.assertEqual(len(incidents), 1)
        incident = incidents[0]
        self.assertEqual(incident["evidence_count"], 2)
        self.assertEqual(incident["evidence_refs"], ["SIG-A", "SIG-B"])
        self.assertEqual(incident["state"], "OBSERVED")
        self.assertEqual(incident["next_owner"], "LEARNER")

    def test_replay_is_idempotent_after_private_registry_readback(self) -> None:
        self.signal("SIG-A")
        self.signal("SIG-B", source="EXECUTOR")
        incident = self.apply_reconcile()

        self.assertTrue(fs_path(self.root, "evolution/incidents.json").is_file())
        self.assertEqual(self.current_incident(incident["incident_id"])["evidence_count"], 2)
        self.assertEqual(incident_reconcile_requests(self.root), [])

    def test_missing_topic_id_never_opens_incident(self) -> None:
        self.signal("SIG-A", topic_id=None)
        self.signal("SIG-B", topic_id=None, source="EXECUTOR")
        self.assertEqual(incident_reconcile_requests(self.root), [])

    def test_stale_pressure_alone_never_opens_incident(self) -> None:
        status = evolution_status(self.root, now=datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc))
        self.assertTrue(status["emergence"]["stale"])
        self.assertEqual(status["incidents"], [])
        self.assertEqual(incident_reconcile_requests(self.root), [])

    def test_lifecycle_is_derived_from_test_review_canary_rollback_and_lesson(self) -> None:
        self.signal("SIG-A")
        self.signal("SIG-B", source="EXECUTOR")
        incident = self.apply_reconcile()
        incident_id = incident["incident_id"]

        test_path = entity_path(self.root, "test", "INC-T1")
        test_path.write_text(json.dumps({
            "id": "INC-T1",
            "entity_version": 1,
            "incident_id": incident_id,
            "hypothesis_id": "HYP-INC-1",
            "prereg_hash": "sha256:abc",
            "status": "READY",
            "state": "READY",
        }), encoding="utf-8")
        self.apply_reconcile()
        self.assertEqual(self.current_incident(incident_id)["state"], "PREREGISTERED")

        test = json.loads(test_path.read_text(encoding="utf-8"))
        test.update({"status": "DONE", "state": "DONE", "verdict": "SUPPORTED", "review_state": "PENDING_REVIEW"})
        test_path.write_text(json.dumps(test), encoding="utf-8")
        self.apply_reconcile()
        self.assertEqual(self.current_incident(incident_id)["state"], "REVIEWING")

        test["review_state"] = "CONFIRMED"
        test_path.write_text(json.dumps(test), encoding="utf-8")
        self.apply_reconcile()
        self.assertEqual(self.current_incident(incident_id)["state"], "CONFIRMED")

        fs_path(self.root, GENOME_DOC).write_text(json.dumps({
            "genes": [{
                "id": "executor.rank_weight",
                "status": "CANARY",
                "canonical": 1,
                "canary": 2,
                "incident_id": incident_id,
                "canary_id": "CANARY-INC-1",
                "rolled_back": [],
            }]
        }), encoding="utf-8")
        self.apply_reconcile()
        self.assertEqual(self.current_incident(incident_id)["state"], "CANARY")

        fs_path(self.root, GENOME_DOC).write_text(json.dumps({
            "genes": [{
                "id": "executor.rank_weight",
                "status": "CANONICAL",
                "canonical": 1,
                "canary": None,
                "incident_id": None,
                "canary_id": None,
                "rolled_back": [{
                    "incident_id": incident_id,
                    "canary_id": "CANARY-INC-1",
                    "at": "2026-09-26T13:00:00Z",
                }],
            }]
        }), encoding="utf-8")
        self.apply_reconcile()
        self.assertEqual(self.current_incident(incident_id)["state"], "ROLLED_BACK")

        lesson_path = entity_path(self.root, "lesson", "LESSON::engineering.nexo.writer")
        lesson_path.write_text(json.dumps({
            "id": "LESSON::engineering.nexo.writer",
            "entity_version": 1,
            "linked_incident_ids": [incident_id],
            "updated_at": "2026-09-26T14:00:00Z",
        }), encoding="utf-8")
        self.apply_reconcile()
        closed = self.current_incident(incident_id)
        self.assertEqual(closed["state"], "CLOSED")
        self.assertEqual(closed["next_owner"], "NONE")
        self.assertEqual(closed["lesson_ids"], ["LESSON::engineering.nexo.writer"])

    def test_public_status_is_minimal_and_private_incidents_do_not_leak(self) -> None:
        self.signal("PUB-A")
        self.signal("PUB-B", source="EXECUTOR")
        public_incident = self.apply_reconcile()
        public_status = evolution_status(self.root, public=True)
        [summary] = public_status["incidents"]
        self.assertEqual(set(summary), {"incident_id", "state", "evidence_count", "public_ids", "next_owner"})
        self.assertEqual(summary["incident_id"], public_incident["incident_id"])
        serialized = json.dumps(summary)
        self.assertNotIn("evidence_refs", serialized)
        self.assertNotIn("signal_code", serialized)
        self.assertNotIn("topic_id", serialized)

        # A private Olympus pattern is still tracked in the private Tower but is
        # absent from the public evolution payload.
        self.signal("PRIV-A", code="PRIVATE_PATTERN", topic_id="olympus.private.pattern", domain_id="olympus")
        self.signal("PRIV-B", code="PRIVATE_PATTERN", topic_id="olympus.private.pattern", domain_id="olympus", source="PITIA")
        self.apply_reconcile()
        private_registry = json.loads(fs_path(self.root, "evolution/incidents.json").read_text(encoding="utf-8"))
        private_items = [item for item in private_registry["incidents"] if item.get("private")]
        self.assertEqual(len(private_items), 1)
        self.assertEqual(private_items[0]["evidence_refs"], ["PRIV-A", "PRIV-B"])
        public_ids = {item["incident_id"] for item in evolution_status(self.root, public=True)["incidents"]}
        self.assertNotIn(private_items[0]["incident_id"], public_ids)

    def test_spine_mutation_and_spoofed_auto_canonization_are_blocked(self) -> None:
        self.signal("SIG-A")
        self.signal("SIG-B", source="EXECUTOR")
        incident = self.apply_reconcile()
        incident_id = incident["incident_id"]

        entity_path(self.root, "test", "INC-T1").write_text(json.dumps({
            "id": "INC-T1",
            "entity_version": 1,
            "incident_id": incident_id,
            "review_state": "CONFIRMED",
        }), encoding="utf-8")

        self.assertEqual(mutation_requests(
            {"source": "LEARNER", "created_at": "2026-09-26T12:00:00Z"},
            {"gene": "contract.writer_mode", "value": "unsafe", "incident_id": incident_id},
            self.root,
        ), [])

        fs_path(self.root, GENOME_DOC).write_text(json.dumps({
            "generation": 0,
            "genes": [{
                "id": "executor.rank_weight",
                "status": "CANARY",
                "canonical": 1,
                "canary": 2,
                "incident_id": incident_id,
                "canary_id": "CANARY-INC-1",
            }],
        }), encoding="utf-8")
        spoofed = operator_requests(
            {"source": "LEARNER", "created_at": "2026-09-26T12:00:00Z"},
            {"action": "CANONIZE", "gene": "executor.rank_weight", "approved_by": "DENER"},
            self.root,
        )
        self.assertIsNone(spoofed)


if __name__ == "__main__":
    unittest.main()
