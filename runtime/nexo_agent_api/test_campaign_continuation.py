from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .campaign_continuation import CampaignFrontierResolver


class CampaignFrontierResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for kind in ("campaign", "test", "run", "result"):
            (self.root / "entities" / kind).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, kind: str, entity_id: str, **payload) -> None:
        data = {"id": entity_id, "entity_version": 1, **payload}
        (self.root / "entities" / kind / f"{entity_id}.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def test_dependency_order_exposes_only_ready_frontier(self) -> None:
        self.write(
            "campaign",
            "CAMP-1",
            status="ACTIVE",
            execution_order=["TEST::A", "TEST::B", "TEST::C"],
        )
        self.write("test", "TEST::A", campaign_id="CAMP-1", status="VERIFIED")
        self.write(
            "test",
            "TEST::B",
            campaign_id="CAMP-1",
            status="READY",
            depends_on=["TEST::A"],
        )
        self.write(
            "test",
            "TEST::C",
            campaign_id="CAMP-1",
            status="READY",
            depends_on=["TEST::B"],
        )

        frontier = CampaignFrontierResolver(self.root).resolve("CAMP-1")

        self.assertEqual(frontier["completed"], ["TEST::A"])
        self.assertEqual(frontier["ready"], ["TEST::B"])
        self.assertEqual(frontier["blocked"], ["TEST::C"])
        self.assertEqual(frontier["next_test_ids"], ["TEST::B"])
        self.assertFalse(frontier["terminal"])

    def test_active_run_wins_over_creating_duplicate_work(self) -> None:
        self.write("campaign", "CAMP-2", status="ACTIVE", execution_order=["TEST::A"])
        self.write(
            "test",
            "TEST::A",
            campaign_id="CAMP-2",
            status="READY",
            current_run_id="RUN::TEST::A::0001",
        )
        self.write(
            "run",
            "RUN::TEST::A::0001",
            campaign_id="CAMP-2",
            test_id="TEST::A",
            status="CHECKPOINTED",
        )

        frontier = CampaignFrontierResolver(self.root).resolve("CAMP-2")

        self.assertEqual(frontier["active"], ["TEST::A"])
        self.assertEqual(frontier["ready"], [])
        self.assertEqual(frontier["next_test_ids"], ["TEST::A"])

    def test_failed_recoverable_run_is_recovery_frontier(self) -> None:
        self.write("campaign", "CAMP-3", status="ACTIVE", execution_order=["TEST::A"])
        self.write(
            "test",
            "TEST::A",
            campaign_id="CAMP-3",
            status="READY",
            current_run_id="RUN::TEST::A::0001",
        )
        self.write(
            "run",
            "RUN::TEST::A::0001",
            campaign_id="CAMP-3",
            test_id="TEST::A",
            status="FAILED",
            recoverable=True,
        )

        frontier = CampaignFrontierResolver(self.root).resolve("CAMP-3")

        self.assertEqual(frontier["recoverable"], ["TEST::A"])
        self.assertEqual(frontier["ready"], [])
        self.assertEqual(frontier["next_test_ids"], ["TEST::A"])

    def test_terminal_campaign_detected_from_terminal_test_ids(self) -> None:
        self.write(
            "campaign",
            "CAMP-4",
            status="ACTIVE",
            execution_order=["TEST::A", "TEST::B"],
            terminal_test_ids=["TEST::B"],
        )
        self.write("test", "TEST::A", campaign_id="CAMP-4", status="VERIFIED")
        self.write("test", "TEST::B", campaign_id="CAMP-4", status="DONE")

        frontier = CampaignFrontierResolver(self.root).resolve("CAMP-4")

        self.assertTrue(frontier["terminal"])
        self.assertEqual(frontier["status"], "TERMINAL")
        self.assertEqual(frontier["next_test_ids"], [])


if __name__ == "__main__":
    unittest.main()
