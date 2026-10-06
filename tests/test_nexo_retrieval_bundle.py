from __future__ import annotations

import ast
import base64
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


class NexoRetrievalBundleTest(unittest.TestCase):
    def test_bundled_search_preserves_tower_and_legacy_cache(self) -> None:
        from runtime.nexo_agent_api.live_tower import build_live_tower_payload
        from runtime.nexo_agent_api.memory import Memory, Snapshot

        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            source = root / "source"
            (source / "entities/tests").mkdir(parents=True)
            (source / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}), encoding="utf-8")
            (source / "entities/tests/T-CI-FIXTURE.json").write_text(json.dumps({
                "id": "T-CI-FIXTURE", "status": "READY", "domain": "science",
                "question": "Synthetic retrieval regression fixture"}), encoding="utf-8")
            tower = root / "TOWER.json"
            original = json.dumps(build_live_tower_payload(source)).encode("utf-8")
            tower.write_bytes(original)
            legacy = root / "legacy-cache"
            Memory(legacy).sync(Snapshot.read(tower))
            legacy_original = legacy.read_bytes()
            sidecar = Path(str(legacy) + ".retrieval-1.1")
            commands = (
                [str(self.loader()), "search", str(tower), str(legacy)],
                [str(repo / "gpt/nexo_gpt_writer.py"), "memory", "search", str(tower), str(legacy)],
                [str(repo / "gpt/nexo_gpt_writer.py"), "memory", "search", str(tower), str(sidecar)],
                [str(repo / "gpt/nexo_gpt_writer.py"), "retrieval", "search", str(tower), str(sidecar)],
            )
            for command in commands:
                proc = subprocess.run(
                    [sys.executable, *command, "--role", "ENGINEER", "--query", "T-CI-FIXTURE"],
                    text=True, capture_output=True, check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                result = json.loads(proc.stdout)
                self.assertEqual(result["method"], "nexo-retrieval-1.1.0")
                self.assertEqual([hit["id"] for hit in result["hits"]], ["TESTS::T-CI-FIXTURE"])
            self.assertTrue(sidecar.is_file())
            self.assertFalse(Path(str(sidecar) + ".retrieval-1.1").exists())
            self.assertEqual(tower.read_bytes(), original)
            self.assertEqual(legacy.read_bytes(), legacy_original)

    @staticmethod
    def loader() -> Path:
        return Path(__file__).resolve().parents[1] / "gpt" / "nexo_memory.py"

    def bundle(self) -> zipfile.ZipFile:
        tree = ast.parse(self.loader().read_text(encoding="utf-8"))
        payload = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_RETRIEVAL_BUNDLE":
                        payload = ast.literal_eval(node.value)
        self.assertIsInstance(payload, str)
        return zipfile.ZipFile(io.BytesIO(base64.b64decode(payload)))

    def test_loader_contains_reviewed_retrieval_runtime(self) -> None:
        with self.bundle() as archive:
            names = set(archive.namelist())
            for member in (
                "runtime/nexo_agent_api/retrieval.py",
                "runtime/nexo_agent_api/retrieval_cli.py",
                "runtime/nexo_agent_api/retrieval_mcp.py",
                "runtime/nexo_agent_api/retrieval_models.py",
            ):
                self.assertIn(member, names)
            source = archive.read("runtime/nexo_agent_api/retrieval_mcp.py").decode("utf-8")
            for tool in (
                "nexo_search", "nexo_get", "nexo_neighbors", "nexo_trace",
                "nexo_diff", "nexo_evidence", "nexo_groups",
            ):
                self.assertIn(tool, source)

    def test_memory_loader_routes_search_to_retrieval(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(self.loader()), "search", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("auto", proc.stdout)
        self.assertIn("graph", proc.stdout)
        version = subprocess.run(
            [sys.executable, str(self.loader()), "--version"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(version.returncode, 0, version.stderr)
        payload = json.loads(version.stdout)
        self.assertEqual(payload["retrieval_version"], "1.1.0")
        self.assertFalse(payload["tower_mutation"])

    def test_writer_bundle_exposes_retrieval_and_stable_memory_alias(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        script = repo / "scripts" / "build_gpt_writer_bundle.py"
        spec = importlib.util.spec_from_file_location("build_gpt_writer_bundle_retrieval_test", script)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        import tempfile

        with tempfile.TemporaryDirectory() as work:
            module.OUT = Path(work) / "nexo_gpt_writer.py"
            writer = module.build()
            retrieval = subprocess.run(
                [sys.executable, str(writer), "retrieval", "--help"],
                text=True,
                capture_output=True,
                check=False,
            )
            alias = subprocess.run(
                [sys.executable, str(writer), "memory", "search", "--help"],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(retrieval.returncode, 0, retrieval.stderr)
        self.assertIn("sync", retrieval.stdout)
        self.assertIn("serve", retrieval.stdout)
        self.assertEqual(alias.returncode, 0, alias.stderr)
        self.assertIn("auto", alias.stdout)
        self.assertIn("graph", alias.stdout)


if __name__ == "__main__":
    unittest.main()
