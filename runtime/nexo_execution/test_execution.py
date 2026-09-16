import tempfile
import unittest
from pathlib import Path

from benchmarks.idm_runtime_preflight import (
    prepare_runtime_dirs,
    prepare_ini_output_dirs,
    probe_distribution_version,
)
from runtime.nexo_execution.core import (
    ExecutionContract,
    ExecutionResult,
    GitHubActionsProvider,
    ResultVerifier,
)
from runtime.nexo_execution.router import (
    RoutingInput,
    choose_provider,
    choose_execution_path,
    should_run_preflight,
)


BASE = {
    "schema": "nexo.execution.v2",
    "execution_id": "EXEC-TEST-001",
    "work_id": "WORK::TEST::001",
    "test_id": "TEST::INFRA::001",
    "run_id": "RUN::TEST::INFRA::001::0001",
    "provider": "github_actions",
    "repository": "byDenoso/TCC",
    "commit_sha": "abc123",
    "task_id": "cosmology_benchmark",
    "parameters": {},
    "seed": 1,
    "timeout_minutes": 10,
    "required_outputs": ["result.json"],
}


class FakeActionsProvider(GitHubActionsProvider):
    def __init__(self):
        super().__init__(token="test-token")
        self.last_request = None

    def _request(self, url, method="GET", payload=None):
        self.last_request = (url, method, payload)
        return 204, b""


class ExecutionTests(unittest.TestCase):
    def test_contract_hash_is_stable(self):
        a = ExecutionContract.from_dict(dict(BASE))
        b = ExecutionContract.from_dict(dict(BASE))
        self.assertEqual(a.contract_hash, b.contract_hash)

    def test_v2_requires_canonical_test_and_run_identity(self):
        for field, value in (("test_id", "T-INFRA-001"), ("run_id", "RUN-001")):
            data = dict(BASE)
            data[field] = value
            with self.assertRaises(ValueError):
                ExecutionContract.from_dict(data)

    def test_contract_from_registration_binds_canonical_identity(self):
        registration = {
            "dispatch_ready": True,
            "readback": "PASS",
            "test_id": "TEST::SOFTWARE::BUTTONS-01",
            "run_id": "RUN::TEST::SOFTWARE::BUTTONS-01::0001",
        }
        execution = dict(BASE)
        execution.pop("schema")
        execution.pop("test_id")
        execution.pop("run_id")
        contract = ExecutionContract.from_registration(registration, **execution)
        self.assertEqual(contract.schema, "nexo.execution.v2")
        self.assertEqual(contract.test_id, registration["test_id"])
        self.assertEqual(contract.run_id, registration["run_id"])

    def test_contract_from_registration_rejects_failed_readback(self):
        registration = {
            "dispatch_ready": True,
            "readback": "FAIL",
            "test_id": "TEST::SOFTWARE::BUTTONS-01",
            "run_id": "RUN::TEST::SOFTWARE::BUTTONS-01::0001",
        }
        execution = dict(BASE)
        execution.pop("schema")
        execution.pop("test_id")
        execution.pop("run_id")
        with self.assertRaisesRegex(ValueError, "registration.*readback"):
            ExecutionContract.from_registration(registration, **execution)

    def test_v1_remains_readable_but_cannot_be_dispatched(self):
        legacy = dict(BASE)
        legacy["schema"] = "nexo.execution.v1"
        legacy.pop("run_id")
        contract = ExecutionContract.from_dict(legacy)
        provider = FakeActionsProvider()
        with self.assertRaisesRegex(ValueError, "legacy.*dispatch"):
            provider.submit(contract, contract_name="legacy.json")

    def test_unknown_task_is_rejected(self):
        data = dict(BASE)
        data["task_id"] = "not_allowed"
        with self.assertRaises(ValueError):
            ExecutionContract.from_dict(data)

    def test_idm_runtime_preflight_is_allowlisted(self):
        data = dict(BASE)
        data["task_id"] = "idm_runtime_preflight"
        contract = ExecutionContract.from_dict(data)
        self.assertEqual(contract.argv, ["python3", "benchmarks/idm_runtime_preflight.py"])

    def test_gz01_desi_edr_nz_pilot_is_allowlisted(self):
        data = dict(BASE)
        data["task_id"] = "gz01_desi_edr_nz_pilot"
        contract = ExecutionContract.from_dict(data)
        self.assertEqual(
            contract.argv,
            ["python3", "-m", "benchmarks.gz01_desi_edr_nz_pilot"],
        )

    def test_idm_preflight_prepares_class_output_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            prepare_runtime_dirs(repo)
            self.assertTrue((repo / "output").is_dir())

    def test_idm_preflight_prepares_nested_ini_root_parent(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            ini = repo / "ini" / "idm.ini"
            ini.parent.mkdir(parents=True)
            ini.write_text("root = output/ini/iDM\n", encoding="utf-8")
            prepare_ini_output_dirs(repo, ["ini/idm.ini"])
            self.assertTrue((repo / "output" / "ini").is_dir())

    def test_idm_preflight_prepares_class_default_root_parent(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            ini = repo / "ini" / "iDM.ini"
            ini.parent.mkdir(parents=True)
            ini.write_text("#root = output/test\noutput = tCl\n", encoding="utf-8")
            prepare_ini_output_dirs(repo, ["ini/iDM.ini"])
            self.assertTrue((repo / "output" / "ini").is_dir())

    def test_distribution_version_probe_uses_fresh_python_process(self):
        version = probe_distribution_version("pip")
        self.assertRegex(version, r"^\d+(?:\.\d+)+")

    def test_router_local_for_short_serial_work(self):
        self.assertEqual(choose_provider(RoutingInput(expected_runtime_minutes=2)), "local")

    def test_router_actions_for_heavy_work(self):
        self.assertEqual(choose_provider(RoutingInput(expected_runtime_minutes=20)), "github_actions")
        self.assertEqual(choose_provider(RoutingInput(parallelizable=True)), "github_actions")
        self.assertEqual(choose_provider(RoutingInput(requires_checkpoint=True)), "github_actions")

    def test_rollback_switch_forces_local(self):
        self.assertEqual(
            choose_provider(RoutingInput(expected_runtime_minutes=60, parallelizable=True, external_enabled=False)),
            "local",
        )

    def test_lean_fast_path_for_proven_reversible_known_work(self):
        inp = RoutingInput(
            expected_runtime_minutes=2,
            reversible=True,
            contract_known=True,
            capability_proven=True,
        )
        self.assertEqual(choose_execution_path(inp), "FAST_PATH")

    def test_lean_standard_path_for_material_but_reversible_work(self):
        inp = RoutingInput(
            reversible=True,
            contract_known=True,
            capability_proven=True,
            material_risk=True,
        )
        self.assertEqual(choose_execution_path(inp), "STANDARD_PATH")

    def test_lean_slow_path_protects_scientific_semantics_and_irreversibility(self):
        self.assertEqual(
            choose_execution_path(RoutingInput(capability_proven=True, scientific_semantic_change=True)),
            "SLOW_PATH",
        )
        self.assertEqual(
            choose_execution_path(RoutingInput(capability_proven=True, reversible=False)),
            "SLOW_PATH",
        )

    def test_proven_capability_skips_equivalent_preflight(self):
        inp = RoutingInput(capability_proven=True, contract_known=True)
        self.assertFalse(should_run_preflight(inp))

    def test_preflight_runs_when_relevant_proof_inputs_changed(self):
        inp = RoutingInput(capability_proven=True, contract_known=True)
        self.assertTrue(should_run_preflight(inp, version_changed=True))
        self.assertTrue(should_run_preflight(inp, contract_changed=True))
        self.assertTrue(should_run_preflight(inp, dependencies_changed=True))
        self.assertTrue(should_run_preflight(inp, health_changed=True))
        self.assertTrue(should_run_preflight(RoutingInput(capability_proven=False)))

    def test_verifier_passes_matching_result(self):
        contract = ExecutionContract.from_dict(dict(BASE))
        result = ExecutionResult(
            execution_id=contract.execution_id,
            work_id=contract.work_id,
            provider=contract.provider,
            run_id="1",
            commit_sha=contract.commit_sha,
            exit_code=0,
            started_at=1.0,
            finished_at=2.0,
            outputs=[{"path": "result.json", "sha256": "deadbeef", "bytes": 1}],
            contract_hash=contract.contract_hash,
        )
        self.assertEqual(ResultVerifier().verify(contract, result)["status"], "PASS")

    def test_actions_provider_sends_safe_contract_name_hash_and_canonical_ids(self):
        contract = ExecutionContract.from_dict(dict(BASE))
        provider = FakeActionsProvider()
        response = provider.submit(contract, contract_name="canary-cosmology.json")
        self.assertEqual(response["dispatch_http_status"], 204)
        self.assertEqual(response["test_id"], contract.test_id)
        self.assertEqual(response["run_id"], contract.run_id)
        _, method, payload = provider.last_request
        self.assertEqual(method, "POST")
        self.assertEqual(payload["inputs"]["contract_name"], "canary-cosmology.json")
        self.assertEqual(payload["inputs"]["expected_contract_hash"], contract.contract_hash)

    def test_actions_provider_rejects_path_traversal(self):
        contract = ExecutionContract.from_dict(dict(BASE))
        provider = FakeActionsProvider()
        with self.assertRaises(ValueError):
            provider.submit(contract, contract_name="../evil.json")


if __name__ == "__main__":
    unittest.main()
