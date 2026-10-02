from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .gpt_writer import _main
from .live_tower import build_live_tower_payload
from .operation_receipts import CONTRACT as OPERATION_RECEIPT_CONTRACT
from .operational_canary import CANARY_CONTRACT


class WriterStatusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "tower"
        self.root.mkdir()
        (self.root / "CONTROL.json").write_text(
            json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def run_status(self) -> dict:
        bundle = build_live_tower_payload(self.root)
        bundle_path = self.root.parent / "tower.json"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.dict(
            os.environ,
            {
                "NEXO_C01_APPROVAL_REGISTRY_PATH": "PRIVATE_REGISTRY_PATH_SENTINEL",
                "NEXO_C01_APPROVAL_REGISTRY_SHA256": "PRIVATE_REGISTRY_HASH_SENTINEL",
                "NEXO_C01_APPROVAL_REF": "PRIVATE_APPROVAL_REF_SENTINEL",
            },
            clear=False,
        ):
            self.assertEqual(_main(["status", str(bundle_path)]), 0)
        return json.loads(output.getvalue())

    def test_cli_status_reports_supported_contracts_and_default_c01_off(self):
        private_doc = {
            "contract": CANARY_CONTRACT,
            "visibility": "PRIVATE",
            "canaries": {},
            "adapters": {},
            "private_registry_record": "PRIVATE_TOWER_REGISTRY_SENTINEL",
            "observations": [{"intent_id": "PRIVATE_OBSERVATION_SENTINEL"}],
        }
        operational_dir = self.root / "operational"
        operational_dir.mkdir()
        (operational_dir / "operational_canary.json").write_text(
            json.dumps(private_doc), encoding="utf-8"
        )

        status = self.run_status()

        contracts = status["operational_contracts"]
        self.assertEqual(contracts[OPERATION_RECEIPT_CONTRACT]["implementation"], "TCC_RUNTIME")
        self.assertEqual(contracts[OPERATION_RECEIPT_CONTRACT]["schema"], "PRESENT")
        self.assertEqual(contracts[CANARY_CONTRACT]["implementation"], "TCC_RUNTIME")
        self.assertEqual(contracts[CANARY_CONTRACT]["schema"], "PRESENT")
        self.assertEqual(contracts["ATLAS_OBSERVATION_V1"]["schema"], "PRESENT")
        self.assertEqual(contracts["ATLAS_OBSERVATION_V1"]["deployment"], "UNVERIFIED")

        c01 = status["C01"]
        self.assertEqual(c01["state"], "OFF")
        self.assertEqual(c01["effective_state"], "OFF")
        self.assertEqual(c01["reason"], "CONFIG_NOT_INSTALLED")
        self.assertFalse(c01["installed"])
        self.assertFalse(c01["activated"])
        self.assertFalse(c01["enabled"])

        # The preexisting evolution status remains additive and compatible.
        self.assertIn("gate", status)
        rendered = json.dumps(status)
        for secret in (
            "PRIVATE_REGISTRY_PATH_SENTINEL",
            "PRIVATE_REGISTRY_HASH_SENTINEL",
            "PRIVATE_APPROVAL_REF_SENTINEL",
            "PRIVATE_TOWER_REGISTRY_SENTINEL",
            "PRIVATE_OBSERVATION_SENTINEL",
        ):
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
