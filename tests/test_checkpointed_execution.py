"""Synthetic integration of the real upstream runner and local recovery boundary.
No cosmological result or hosted Actions capacity is tested by this suite.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from runtime.nexo_execution.campaign_store import CampaignError, atomic_json, local_lock
from runtime.nexo_execution.core import ExecutionContract
from runtime.nexo_execution.checkpointed import run_contract_once, publish_verified_run
from runtime.nexo_execution.campaign_store import DriveCampaignStore
try:
    from .test_campaign_store import FakeDrive
except ImportError:
    from test_campaign_store import FakeDrive

HERE = Path(__file__).resolve().parents[1]


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        for name in ["__init__.py", "core.py", "runner.py"]:
            target = self.repo / "runtime/nexo_execution" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE / "runtime/nexo_execution" / name, target)
        (self.repo / "benchmarks").mkdir()
        self.script = self.repo / "benchmarks/cosmology_env_benchmark.py"
        # Deliberately uses the allowlisted path in a disposable SYNTHETIC repo.
        self.script.write_text("import json,os\nfrom pathlib import Path\n"
                               "p=Path('count.txt');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')\n"
                               "Path('out.json').write_text(json.dumps({'answer':2+2,'credentials_inherited': 'GITHUB_TOKEN' in os.environ}))\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "synthetic runner fixture")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.data = {"schema": "nexo.execution.v2", "execution_id": "synthetic", "work_id": "WORK::SYNTHETIC",
                     "test_id": "TEST::SYNTHETIC", "run_id": "RUN::SYNTHETIC", "provider": "local",
                     "repository": "synthetic/fixture", "commit_sha": self.sha, "task_id": "cosmology_benchmark",
                     "parameters": {}, "seed": 1, "timeout_minutes": 1, "required_outputs": ["out.json"]}
        self.contract = self.base / "contract.json"
        self.journals = self.base / "journals"
        self.save()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True, stderr=subprocess.DEVNULL)

    def save(self):
        self.contract.write_text(json.dumps(self.data))
        self.hash = ExecutionContract.from_dict(self.data).contract_hash

    def run_it(self, **kwargs):
        return run_contract_once(self.contract, repository_root=self.repo, journal_directory=self.journals,
                                 expected_contract_hash=self.hash, authorized=kwargs.pop("authorized", True), **kwargs)

    def test_executes_real_runner_and_reuses_verified_result(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-secret-not-for-solver"}):
            first = self.run_it()
        self.assertEqual(first["state"], "EXECUTED_LOCAL_VERIFIED")
        self.assertFalse(first["replayed_without_compute"])
        self.assertEqual(json.loads((self.repo / "out.json").read_text()), {"answer": 4, "credentials_inherited": False})
        second = self.run_it()
        self.assertTrue(second["replayed_without_compute"])
        self.assertEqual((self.repo / "count.txt").read_text(), "1")
        self.assertEqual(second["evidence"]["review_state"], "NOT_REVIEWED")
        self.assertEqual(second["evidence"]["run_id"], "RUN::SYNTHETIC")

    def test_persistence_failure_retries_only_persistence(self):
        def failed(_):
            raise OSError("injected network failure")
        with self.assertRaisesRegex(CampaignError, "PERSISTENCE_PENDING"):
            self.run_it(publish=failed)
        result = self.run_it(publish=lambda _: {"state": "PERSISTED_VERIFIED", "file_id": "synthetic"})
        self.assertTrue(result["replayed_without_compute"])
        self.assertEqual(result["state"], "EXECUTED_PERSISTED")
        self.assertEqual((self.repo / "count.txt").read_text(), "1")

    def test_incomplete_receipt_cannot_mark_persisted(self):
        with self.assertRaisesRegex(CampaignError, "PERSISTENCE_PENDING"):
            self.run_it(publish=lambda _: {"state": "SENT"})

    def test_tampered_output_does_not_recompute(self):
        self.run_it()
        (self.repo / "out.json").write_text("tampered")
        with self.assertRaisesRegex(CampaignError, "EXPLICIT_RECOVERY"):
            self.run_it()
        self.assertEqual((self.repo / "count.txt").read_text(), "1")

    def test_post_run_crash_is_recoverable_from_evidence(self):
        first = self.run_it()
        journal = Path(first["run_directory"]) / "execution.json"
        value = json.loads(journal.read_text())
        atomic_json(journal, {"binding": value["binding"], "state": "RUNNING"})
        self.assertTrue(self.run_it()["replayed_without_compute"])
        self.assertEqual((self.repo / "count.txt").read_text(), "1")

    def test_uncertain_running_is_not_restarted(self):
        first = self.run_it()
        (Path(first["run_directory"]) / "verification.json").unlink()
        with self.assertRaisesRegex(CampaignError, "EXPLICIT_RECOVERY"):
            self.run_it()
        self.assertEqual((self.repo / "count.txt").read_text(), "1")

    def test_contract_change_same_run_conflicts(self):
        self.run_it()
        self.data["seed"] = 9
        self.save()
        with self.assertRaisesRegex(CampaignError, "INTENT_CONFLICT"):
            self.run_it()

    def test_authorization_is_required(self):
        with self.assertRaisesRegex(CampaignError, "AUTHORIZATION_REQUIRED"):
            self.run_it(authorized=False)
        self.assertFalse((self.repo / "count.txt").exists())

    def test_wrong_commit_is_rejected_before_compute(self):
        self.data["commit_sha"] = "a" * 40
        self.save()
        with self.assertRaisesRegex(CampaignError, "COMMIT_MISMATCH"):
            self.run_it()

    def test_tracked_modification_is_rejected(self):
        self.script.write_text("raise Exception('changed')")
        with self.assertRaisesRegex(CampaignError, "TRACKED_CHANGES"):
            self.run_it()

    def test_existing_output_is_never_adopted_on_first_run(self):
        (self.repo / "out.json").write_text("stale")
        with self.assertRaisesRegex(CampaignError, "OUTPUT_ALREADY_EXISTS"):
            self.run_it()

    def test_path_escape_is_rejected(self):
        for name in ["../escape", "/tmp/escape", ".git/config", "bad\\path"]:
            with self.subTest(name=name):
                self.data["required_outputs"] = [name]
                self.save()
                with self.assertRaisesRegex(CampaignError, "OUTPUT_PATH_INVALID"):
                    self.run_it()

    def test_concurrent_invocation_is_rejected_by_shared_os_lock(self):
        with local_lock(self.journals / "executor.lock"):
            with self.assertRaises(CampaignError):
                self.run_it()
        self.assertEqual(self.run_it()["state"], "EXECUTED_LOCAL_VERIFIED")

    def test_failed_runner_is_not_retried_automatically(self):
        self.script.write_text("raise SystemExit(3)\n")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "failing synthetic fixture")
        self.data["commit_sha"] = self.git("rev-parse", "HEAD").strip()
        self.save()
        with self.assertRaisesRegex(CampaignError, "RUNNER_FAILED"):
            self.run_it()
        with self.assertRaisesRegex(CampaignError, "EXPLICIT_RECOVERY"):
            self.run_it()

    def test_timeout_terminates_process_group_and_releases_lock(self):
        self.script.write_text("import os,time\nfrom pathlib import Path\nPath('pid.txt').write_text(str(os.getpid()))\ntime.sleep(60)\n")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "timeout synthetic fixture")
        self.data["commit_sha"] = self.git("rev-parse", "HEAD").strip()
        self.save()
        with self.assertRaisesRegex(CampaignError, "TIMEOUT"):
            self.run_it(max_seconds=3)
        pid = int((self.repo / "pid.txt").read_text())
        proc = Path(f"/proc/{pid}/stat")
        # A terminated but not-yet-reaped orphan can be a zombie, never running.
        self.assertTrue(not proc.exists() or proc.read_text().split()[2] == "Z")
        with local_lock(self.journals / "executor.lock"):
            pass

    def test_real_runner_persists_through_direct_client_without_recomputation(self):
        drive = FakeDrive()
        store = DriveCampaignStore("root", session=drive, write=True, sleep=lambda _: None)
        callback = lambda e: publish_verified_run(e, store=store, folder_id="folder", campaign_id="CAMP-SYNTHETIC",
                                                  actor_id="executor-fixture", journal_directory=self.base / "publish")
        result = self.run_it(publish=callback)
        self.assertEqual(result["state"], "EXECUTED_PERSISTED")
        self.assertEqual(len(result["receipt"]["outputs"]), 5)
        self.assertEqual(drive.created, 6)
        event_id = result["receipt"]["file_id"]
        event = store.read_event(event_id, "folder", "CAMP-SYNTHETIC")["event"]
        self.assertEqual(event["kind"], "RUN")
        self.assertEqual(event["atlas_scope"], "EXCLUDED")
        self.assertEqual(event["data"]["review_state"], "NOT_REVIEWED")
        self.assertTrue(self.run_it(publish=callback)["replayed_without_compute"])
        self.assertEqual(drive.created, 6)
        self.assertEqual((self.repo / "count.txt").read_text(), "1")

    def test_lost_upload_response_reuses_runner_output_and_remote_id(self):
        drive = FakeDrive(); drive.lost = True
        store = DriveCampaignStore("root", session=drive, write=True, sleep=lambda _: None)
        callback = lambda e: publish_verified_run(e, store=store, folder_id="folder", campaign_id="CAMP-SYNTHETIC",
                                                  actor_id="executor-fixture", journal_directory=self.base / "publish")
        self.run_it(publish=callback)
        self.assertEqual(drive.created, 6)
        self.assertEqual((self.repo / "count.txt").read_text(), "1")

    def test_actions_provider_remains_disabled(self):
        self.data["provider"] = "github_actions"
        self.save()
        with self.assertRaisesRegex(ValueError, "disabled"):
            self.run_it()


if __name__ == "__main__":
    unittest.main()
