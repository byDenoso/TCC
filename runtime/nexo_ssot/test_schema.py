from __future__ import annotations

import unittest

from .schema import normalize_record, validate_snapshot


class SnapshotSchemaTests(unittest.TestCase):
    def test_requires_revision_hash_and_sections(self) -> None:
        errors = validate_snapshot({"schema_version": "1.0"})
        joined = " ".join(errors)
        self.assertIn("ssot_revision", joined)
        self.assertIn("state_hash", joined)
        self.assertIn("projects", joined)

    def test_valid_minimal_snapshot(self) -> None:
        payload = {
            "schema_version": "1.0",
            "ssot_revision": 1,
            "state_hash": "sha256:test",
            "generated_at": "2026-09-14T00:00:00Z",
            "projects": [{"id": "PROJ::TEST"}],
            "work": [{"id": "WORK::TEST"}],
            "tests": [{"id": "TEST::TEST"}],
            "events": [{"id": "EVENT::TEST"}],
            "knowledge": [{"id": "KNOW::TEST"}],
            "relations": [{"id": "REL::TEST"}],
            "decisions": [{"id": "DEC::TEST"}],
            "olympus_summary": [{"id": "OLY::TEST"}],
            "system": {},
        }
        self.assertEqual(validate_snapshot(payload), [])

    def test_normalize_record_promotes_known_identifier(self) -> None:
        self.assertEqual(normalize_record({"work_id": "W1"})["id"], "W1")

    def test_normalize_record_promotes_real_drive_identifier_aliases(self) -> None:
        cases = {
            "meta_test_id": "MT-1",
            "knowledge_id": "KNOW-1",
            "cross_id": "CROSS-1",
            "learning_id": "LEARN-1",
            "integrity_id": "INT-1",
            "thread_id": "THR-1",
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(normalize_record({key: value})["id"], value)

    def test_duplicate_ids_are_rejected(self) -> None:
        payload = {
            "schema_version": "1.0",
            "ssot_revision": 1,
            "state_hash": "sha256:test",
            "generated_at": "2026-09-14T00:00:00Z",
            "projects": [{"id": "P1"}, {"id": "P1"}],
            "work": [{"id": "W1"}], "tests": [{"id": "T1"}], "events": [{"id": "E1"}],
            "knowledge": [{"id": "K1"}], "relations": [{"id": "R1"}], "decisions": [{"id": "D1"}],
            "olympus_summary": [{"id": "O1"}], "system": {},
        }
        self.assertIn("duplicate id in projects: P1", validate_snapshot(payload))


if __name__ == "__main__":
    unittest.main()
