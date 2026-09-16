from __future__ import annotations

import unittest

from runtime.nexo_core.models import CanonicalEntity
from runtime.nexo_core.projection import build_snapshot, validate_snapshot


class CampaignProjectionTests(unittest.TestCase):
    def test_campaign_and_test_projection_is_generic_and_domain_driven(self) -> None:
        entities = [
            CanonicalEntity(
                entity_ref="CAMPAIGN::COSMOLOGY::PEER-2026",
                state="ACTIVE",
                entity_version=2,
                writer_role="ADVISOR",
                data={
                    "domain": "COSMOLOGY",
                    "label": "PEER 2026",
                    "project_id": "PROJECT::PEER",
                    "parent_id": "PROJECT::PEER",
                    "operational_status": "ACTIVE",
                    "analytical_status": "UNASSESSED",
                },
            ),
            CanonicalEntity(
                entity_ref="TEST::PEER::D04",
                state="COMPLETED",
                entity_version=3,
                writer_role="EXECUTOR",
                data={
                    "domain": "COSMOLOGY",
                    "label": "D04",
                    "project_id": "PROJECT::PEER",
                    "campaign_id": "CAMPAIGN::COSMOLOGY::PEER-2026",
                    "test_group_id": "TEST_GROUP::PEER_DETECTION_BATTERY",
                    "parent_id": "TEST_GROUP::PEER_DETECTION_BATTERY",
                    "operational_status": "COMPLETED",
                    "analytical_status": "INCONCLUSIVE",
                },
            ),
            CanonicalEntity(
                entity_ref="CAMPAIGN::OLYMPUS::RENILDE-RECOMP",
                state="ACTIVE",
                entity_version=1,
                writer_role="ADVISOR",
                data={
                    "domain": "OLYMPUS",
                    "label": "Renilde Recomp",
                    "project_id": "PROJECT::RENILDE",
                    "parent_id": "PROJECT::RENILDE",
                    "operational_status": "ACTIVE",
                    "analytical_status": "UNASSESSED",
                },
            ),
        ]
        snapshot = build_snapshot(entities, snapshot_id="S1", generated_at="2026-09-16T15:20:00Z", event_cursor="E1")
        self.assertEqual(validate_snapshot(snapshot), [])
        by_id = {node["id"]: node for node in snapshot["nodes"]}
        campaign = by_id["CAMPAIGN::COSMOLOGY::PEER-2026"]
        test = by_id["TEST::PEER::D04"]
        olympus = by_id["CAMPAIGN::OLYMPUS::RENILDE-RECOMP"]
        self.assertEqual(campaign["domain"], "COSMOLOGY")
        self.assertEqual(olympus["domain"], "OLYMPUS")
        self.assertEqual(campaign["route"], "/campaigns/CAMPAIGN%3A%3ACOSMOLOGY%3A%3APEER-2026")
        self.assertEqual(test["route"], "/tests/TEST%3A%3APEER%3A%3AD04")
        self.assertEqual(test["operational_status"], "COMPLETED")
        self.assertEqual(test["analytical_status"], "INCONCLUSIVE")
        self.assertEqual(test["campaign_id"], "CAMPAIGN::COSMOLOGY::PEER-2026")
        self.assertEqual(test["test_group_id"], "TEST_GROUP::PEER_DETECTION_BATTERY")
        self.assertEqual(test["project_id"], "PROJECT::PEER")
        belongs = {(edge["source"], edge["target"], edge["type"]) for edge in snapshot["edges"]}
        self.assertIn(("TEST::PEER::D04", "CAMPAIGN::COSMOLOGY::PEER-2026", "BELONGS_TO"), belongs)


if __name__ == "__main__":
    unittest.main()
