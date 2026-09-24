import json
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_agent_api.public_projection import build_public_projection, verify_projection


class PublicScienceTestProjectionTests(unittest.TestCase):
    def test_publishes_only_allowlisted_test_fields_and_nested_datasets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "entities" / "test").mkdir(parents=True)
            (root / "indexes").mkdir()
            (root / "snapshot").mkdir()
            (root / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
                "write_model": "IN_PLACE_FILE_REVISION_CAS_READBACK",
                "runtime_revision": "byDenoso/TCC@" + "a" * 40,
            }), encoding="utf-8")
            (root / "snapshot" / "latest.json").write_text(
                json.dumps({"event_cursor": "20260923T120000000000Z-science"}), encoding="utf-8"
            )
            (root / "indexes" / "active-work.json").write_text(
                json.dumps({"work": []}), encoding="utf-8"
            )
            record = {
                "id": "TEST-1",
                "status": "READY",
                "campaign_id": "CAMP-1",
                "hypothesis_ref": "HYP-1",
                "mechanism": "controlled comparison",
                "input_contract": {
                    "datasets": ["Pantheon+", "DES-SN5YR"],
                    "private_note": "must not enter public projection",
                },
                "scientific_result": {
                    "parameter": "H0",
                    "value": 70.5,
                    "err_lo": 1.2,
                    "err_hi": 1.3,
                    "unit": "km/s/Mpc",
                    "private_note": "must not enter public projection",
                    "statistics": {
                        "sigma_lee": 2.4,
                        "p_value": 0.02,
                        "private_metric": 999,
                    },
                },
            }
            (root / "entities" / "test" / "TEST-1.json").write_text(json.dumps(record), encoding="utf-8")

            projection = build_public_projection(
                root,
                tower_revision="sha256:" + "b" * 64,
                tower_file_id="stable-live-tower-file",
                generated_at="2026-09-23T12:00:00Z",
            )
            projected = projection["tests"][0]

            self.assertEqual(projected["hypothesis_ref"], "HYP-1")
            self.assertEqual(projected["mechanism"], "controlled comparison")
            self.assertEqual(projected["datasets"], ["Pantheon+", "DES-SN5YR"])
            self.assertEqual(projected["scientific_result"]["value"], 70.5)
            self.assertEqual(projected["statistics"]["sigma_lee"], 2.4)
            self.assertNotIn("input_contract", projected)
            self.assertNotIn("private_note", json.dumps(projected))
            self.assertNotIn("private_metric", json.dumps(projected))
            self.assertTrue(verify_projection(projection)[0])


if __name__ == "__main__":
    unittest.main()


def test_hypotheses_are_projected_with_fields_derived_from_their_tests(tmp_path):
    import json

    from runtime.nexo_agent_api.public_projection import build_public_projection
    from runtime.nexo_agent_api.tower_paths import entity_path

    (tmp_path / "CONTROL.json").write_text(json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}))
    for kind, eid, body in (
        ("hypothesis", "HYP-1", {"id": "HYP-1", "title": "Dark matter self-interacts", "status": "OPEN", "domain": "SCIENCE"}),
        ("hypothesis", "HYP-OLY", {"id": "HYP-OLY", "title": "private", "semantic": {"domain_id": "olympus"}}),
        ("test", "T-1", {"id": "T-1", "hypothesis_id": "HYP-1", "null": "CDM fits", "rival": "SIDM fits better",
                         "kill_criteria": "No velocity dependence works", "semantic": {"topic_id": "science.cosmology.dark_matter.nature"}}),
    ):
        path = entity_path(tmp_path, kind, eid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body))
    projection = build_public_projection(tmp_path, tower_revision="sha256:" + "b" * 64)
    [hyp] = projection["hypotheses"]
    assert hyp["id"] == "HYP-1"
    assert (hyp["statement"], hyp["model"], hyp["baseline"]) == ("Dark matter self-interacts", "SIDM fits better", "CDM fits")
    assert hyp["falsification_criterion"] == "No velocity dependence works"
    assert projection["manifest"]["source_snapshot_id"].startswith("LIVE_TOWER@sha256:")
