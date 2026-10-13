"""Regression tests for safe legacy H0 scientific predecessor admission."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from . import scientific_integrity as integrity


class VerifiedLegacyDependencyTests(unittest.TestCase):
    DEPENDENCY = "T-H0HOM26-001"
    RUN = "RUN-607f3f5d2431abc503b6"
    RESULT = "RESULT-880e86a80b26ffff100b"
    EVIDENCE = "EVIDENCE-880e86a80b26ffff100b"
    ARTIFACT = "TOWER_V06/runtime/artifacts/T-H0HOM26-001-SCIENTIFIC-RESULT.json"
    DECISION = "NO_ANISOTROPY_EVIDENCE"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scientific = {
            "status": "VERIFIED", "decision": self.DECISION,
            "run_ref": self.RUN, "result_ref": self.RESULT,
            "evidence_ref": self.EVIDENCE, "artifact_ref": self.ARTIFACT,
        }
        self.dependency = {
            "id": self.DEPENDENCY, "status": "DONE",
            "scientific_result": self.scientific,
        }
        self._put("runtime/runs/" + self.RUN + ".json", {
            "run_id": self.RUN, "result_id": self.RESULT,
            "evidence_id": self.EVIDENCE, "work_id": "WORK::" + self.DEPENDENCY,
            "status": "VERIFIED", "readback_status": "PASS",
        })
        self._put("runtime/results/" + self.RESULT + ".json", {
            "id": self.RESULT, "run_id": self.RUN,
            "evidence_ref": self.EVIDENCE, "work_id": "WORK::" + self.DEPENDENCY,
            "status": "COMPLETE", "scientific_closure": {"complete": True},
            "scientific_decision": self.DECISION,
        })
        self._put("runtime/evidence/" + self.EVIDENCE + ".json", {
            "id": self.EVIDENCE, "run_id": self.RUN,
            "source_id": self.DEPENDENCY, "validation_status": "PASS",
            "verification_scope": "SCIENTIFIC",
        })
        self._put(self.ARTIFACT.removeprefix("TOWER_V06/"), {
            "test_id": self.DEPENDENCY, "status": "TERMINAL",
            "decision": self.DECISION,
        })

    def _put(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def _change(self, relative, key, value):
        path = self.root / relative
        current = json.loads(path.read_text(encoding="utf-8"))
        current[key] = value
        self._put(relative, current)

    def _valid(self, dependency=None):
        return integrity._verified_legacy_dependency(
            self.root, self.DEPENDENCY,
            self.dependency if dependency is None else dependency,
        )

    def test_genuine_run_result_evidence_and_artifact_accepts(self):
        self.assertTrue(self._valid())

    def test_done_label_alone_cannot_bypass_readback(self):
        dependency = copy.deepcopy(self.dependency)
        dependency["scientific_result"] = {"status": "VERIFIED"}
        self.assertFalse(self._valid(dependency))

    def test_unverified_test_not_accepted(self):
        dependency = copy.deepcopy(self.dependency)
        dependency["scientific_result"]["status"] = "DRAFT"
        self.assertFalse(self._valid(dependency))

    def test_missing_run_file_fails_closed(self):
        (self.root / "runtime/runs" / (self.RUN + ".json")).unlink()
        self.assertFalse(self._valid())

    def test_readback_failure_rejects(self):
        self._change("runtime/runs/" + self.RUN + ".json", "readback_status", "FAIL")
        self.assertFalse(self._valid())

    def test_wrong_source_id_rejects(self):
        self._change("runtime/evidence/" + self.EVIDENCE + ".json", "source_id", "OTHER")
        self.assertFalse(self._valid())

    def test_scientific_decision_mismatch_rejects(self):
        self._change(self.ARTIFACT.removeprefix("TOWER_V06/"), "decision", "DIFFERENT")
        self.assertFalse(self._valid())

    def test_out_of_scope_artifact_path_rejects(self):
        dependency = copy.deepcopy(self.dependency)
        dependency["scientific_result"]["artifact_ref"] = "../../tmp/forged.json"
        self.assertFalse(self._valid(dependency))


if __name__ == "__main__":
    unittest.main()
