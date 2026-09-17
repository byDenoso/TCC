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
        for kind in ("campaign", "test_group", "test", "work", "run", "result"):
            (self.root / "entities" / kind).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, entity_kind: str, entity_id: str, **payload) -> None:
        data = {"id": entity_id, "entity_version": 1, **payload}
        (self.root / "entities" / entity_kind / f"{entity_id}.json").write_text(
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

    def test_checkpointed_run_is_recovery_frontier_not_active_compute(self) -> None:
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

        self.assertEqual(frontier["active"], [])
        self.assertEqual(frontier["recoverable"], ["TEST::A"])
        self.assertEqual(frontier["ready"], [])
        self.assertEqual(frontier["next_test_ids"], ["TEST::A"])

    def test_running_run_wins_over_creating_duplicate_work(self) -> None:
        self.write("campaign", "CAMP-RUN", status="ACTIVE", execution_order=["TEST::A"])
        self.write(
            "test",
            "TEST::A",
            campaign_id="CAMP-RUN",
            status="READY",
            current_run_id="RUN::TEST::A::0001",
        )
        self.write(
            "run",
            "RUN::TEST::A::0001",
            campaign_id="CAMP-RUN",
            test_id="TEST::A",
            status="RUNNING",
        )

        frontier = CampaignFrontierResolver(self.root).resolve("CAMP-RUN")

        self.assertEqual(frontier["active"], ["TEST::A"])
        self.assertEqual(frontier["recoverable"], [])
        self.assertEqual(frontier["ready"], [])

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

    def test_test_group_is_read_as_campaign_without_duplicate_campaign_entity(self) -> None:
        self.write(
            "test_group",
            "CAMP-H0",
            status="ACTIVE",
            execution_order=["T-H0-001"],
        )
        self.write("test", "T-H0-001", campaign_id="CAMP-H0", status="READY")

        frontier = CampaignFrontierResolver(self.root).resolve("CAMP-H0")

        self.assertEqual(frontier["ready"], ["T-H0-001"])
        self.assertEqual(frontier["campaign_source"], "test_group")
        self.assertFalse((self.root / "entities" / "campaign" / "CAMP-H0.json").exists())

    def test_legacy_scientific_state_remains_a_legitimate_blocker(self) -> None:
        self.write(
            "test_group",
            "CAMP-H0",
            status="BLOCKED_SCIENTIFIC_CONTRACT",
            execution_order=["T-H0-007"],
        )
        self.write(
            "test",
            "T-H0-007",
            campaign_id="CAMP-H0",
            state="BLOCKED_SCIENTIFIC_CONTRACT",
            blocker="FROZEN_SCIENTIFIC_BINDING_INCOMPLETE",
        )

        frontier = CampaignFrontierResolver(self.root).resolve("CAMP-H0")

        self.assertEqual(frontier["ready"], [])
        self.assertEqual(frontier["blocked"], ["T-H0-007"])
        self.assertEqual(frontier["blocker_classes"]["T-H0-007"], "SCIENTIFIC_DEFINITION_MISSING")

    def test_free_text_administrative_blocker_does_not_hide_ready_work(self) -> None:
        self.write(
            "campaign",
            "CAMP-ADMIN",
            status="ACTIVE",
            execution_order=["TEST::A"],
        )
        self.write(
            "test",
            "TEST::A",
            campaign_id="CAMP-ADMIN",
            status="READY",
            blocker="recipe_id missing",
        )

        frontier = CampaignFrontierResolver(self.root).resolve("CAMP-ADMIN")

        self.assertEqual(frontier["ready"], ["TEST::A"])
        self.assertEqual(frontier["blocked"], [])

    def test_legacy_work_with_campaign_id_is_visible_until_migrated_to_test(self) -> None:
        self.write(
            "campaign",
            "CAMP-LEGACY",
            status="ACTIVE",
            execution_order=["T-LEGACY-001"],
        )
        self.write(
            "work",
            "T-LEGACY-001",
            campaign_id="CAMP-LEGACY",
            kind="RESEARCH",
            owner_role="EXECUTOR",
            status="READY",
            required_capabilities=["science.mock_observer"],
        )

        frontier = CampaignFrontierResolver(self.root).resolve("CAMP-LEGACY")

        self.assertEqual(frontier["ready"], ["T-LEGACY-001"])
        self.assertEqual(frontier["sources"]["T-LEGACY-001"], "work")


if __name__ == "__main__":
    unittest.main()
