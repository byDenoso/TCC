from __future__ import annotations

import unittest
from .public_projection import public_summary


class PublicProjectionTests(unittest.TestCase):
    def test_summary_emits_only_pseudonymous_contract_fields(self):
        rows=[{
            "id":"O1",
            "label":"Client Name",
            "title":"Client Name",
            "name":"Client Name",
            "status":"ACTIVE",
            "program":"V3",
            "phase":"RECOMPOSITION",
            "checkin_status":"STALE",
            "freshness":"2026-09-14",
            "next_action":"CHECKIN",
            "labs":"private",
            "measurements":"private",
        }]
        result=public_summary(rows)
        self.assertEqual(result,[{
            "id":"O1",
            "status":"ACTIVE",
            "program":"V3",
            "phase":"RECOMPOSITION",
            "checkin_status":"STALE",
            "freshness":"2026-09-14",
            "next_action":"CHECKIN",
        }])
        serialized=str(result)
        self.assertNotIn("Client Name", serialized)
        self.assertNotIn("private", serialized)


if __name__ == "__main__":
    unittest.main()
