from __future__ import annotations

import unittest
from .reconcile import reconcile_exports

class ReconcileTests(unittest.TestCase):
    def item(self, result, section, rid):
        return next(x for x in result["items"] if x["section"] == section and x["record_id"] == rid)

    def test_git_wins_newer_work(self):
        r = reconcile_exports({"work":[{"id":"W1","status":"READY","entity_version":1}]},{"work":[{"id":"W1","status":"RUNNING","entity_version":2}]})
        self.assertEqual(self.item(r,"work","W1")["resolved"]["status"],"RUNNING")

    def test_drive_wins_olympus(self):
        r = reconcile_exports({"olympus_summary":[{"id":"O1","program":"V3"}]},{"olympus_summary":[{"id":"O1","program":"V2"}]})
        self.assertEqual(self.item(r,"olympus_summary","O1")["resolved"]["program"],"V3")

    def test_verified_result_wins(self):
        r = reconcile_exports({"tests":[{"id":"T1","status":"RUNNING"}]},{"tests":[{"id":"T1","status":"VERIFIED","verification":"PASS"}]})
        self.assertEqual(self.item(r,"tests","T1")["resolved"]["status"],"VERIFIED")

    def test_unknown_disagreement_conflicts(self):
        r = reconcile_exports({"decisions":[{"id":"D1","decision":"A"}]},{"decisions":[{"id":"D1","decision":"B"}]})
        self.assertEqual(r["material_conflict_count"],1)
        self.assertEqual(self.item(r,"decisions","D1")["status"],"CONFLICT")

if __name__ == "__main__":
    unittest.main()
