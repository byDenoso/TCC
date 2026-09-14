from __future__ import annotations

import unittest
from .public_projection import public_summary

class PublicProjectionTests(unittest.TestCase):
    def test_summary_emits_only_contract_fields(self):
        rows=[{"id":"O1","label":"Client","status":"ACTIVE","program":"V3","extra":"x"}]
        result=public_summary(rows)
        self.assertEqual(result,[{"id":"O1","label":"Client","status":"ACTIVE","program":"V3"}])

if __name__ == "__main__":
    unittest.main()
