import copy
import unittest

from runtime.nexo_core.frontend import (
    FrontendSnapshotError,
    build_frontend_envelope,
    validate_frontend_envelope,
)


class FrontendSnapshotContractTests(unittest.TestCase):
    def _snapshot(self):
        return {
            "schema_version": "0.5",
            "snapshot_id": "SNAP-V05-1",
            "generated_at": "2026-09-11T23:20:00-03:00",
            "event_cursor": "EVT-377",
            "overview": {"entities": 2, "active": 1, "blocked": 1},
            "research": {"entity_refs": ["WORK::SCI-1"]},
            "olympus": {"entity_refs": ["CLIENT::PRIVATE-1"]},
            "nexo": {"entity_refs": []},
            "system": {"entity_refs": []},
            "nodes": [
                {"id": "WORK::SCI-1", "type": "WORK", "status": "BLOCKED", "version": 2},
                {"id": "CLIENT::PRIVATE-1", "type": "CLIENT", "status": "ACTIVE", "version": 1},
            ],
            "edges": [],
        }

    def test_private_envelope_is_hashed_and_valid(self):
        envelope = build_frontend_envelope(self._snapshot(), visibility="private")
        self.assertEqual(envelope["contract_version"], "nexo-one/0.5")
        self.assertEqual(envelope["visibility"], "private")
        self.assertEqual(len(envelope["snapshot_sha256"]), 64)
        self.assertEqual(validate_frontend_envelope(envelope), [])

    def test_public_envelope_rejects_olympus_payload(self):
        with self.assertRaises(FrontendSnapshotError):
            build_frontend_envelope(self._snapshot(), visibility="public")

    def test_tampering_breaks_integrity_validation(self):
        envelope = build_frontend_envelope(self._snapshot(), visibility="private")
        tampered = copy.deepcopy(envelope)
        tampered["snapshot"]["overview"]["entities"] = 999
        self.assertIn("snapshot_sha256", validate_frontend_envelope(tampered))

    def test_public_envelope_without_private_scope_is_allowed(self):
        snapshot = self._snapshot()
        snapshot["olympus"]["entity_refs"] = []
        snapshot["nodes"] = [node for node in snapshot["nodes"] if not node["id"].startswith("CLIENT::")]
        snapshot["overview"]["entities"] = 1
        envelope = build_frontend_envelope(snapshot, visibility="public")
        self.assertEqual(validate_frontend_envelope(envelope), [])


if __name__ == "__main__":
    unittest.main()
