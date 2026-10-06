from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path


class NexoMemoryBundleTest(unittest.TestCase):
    def test_generated_loader_matches_sources_and_declared_hashes(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "build_nexo_memory_source_test", repo / "scripts/build_nexo_memory_bundle.py")
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        self.assertEqual(self.loader().read_bytes(), module.render())
        constants = {
            target.id: ast.literal_eval(node.value)
            for node in ast.parse(self.loader().read_text(encoding="utf-8")).body
            if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)
        }
        for payload, digest in (("_BUNDLE", "_SHA256"), ("_RETRIEVAL_BUNDLE", "_RETRIEVAL_SHA256")):
            raw = base64.b64decode(constants[payload], validate=True)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), constants[digest])
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                self.assertIsNone(archive.testzip())
                for name in archive.namelist():
                    if name.endswith(".py") and not name.endswith("__init__.py"):
                        self.assertEqual(archive.read(name), (repo / name).read_bytes())

    @staticmethod
    def loader() -> Path:
        return Path(__file__).resolve().parents[1] / "gpt" / "nexo_memory.py"

    def bundle(self) -> zipfile.ZipFile:
        tree = ast.parse(self.loader().read_text(encoding="utf-8"))
        payload = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_BUNDLE":
                        payload = ast.literal_eval(node.value)
        self.assertIsInstance(payload, str)
        return zipfile.ZipFile(io.BytesIO(base64.b64decode(payload)))

    def test_bundle_contains_reviewable_memory_runtime(self) -> None:
        with self.bundle() as archive:
            names = set(archive.namelist())
            self.assertIn("runtime/nexo_agent_api/memory.py", names)
            self.assertIn("runtime/nexo_agent_api/memory_cli.py", names)
            self.assertIn("runtime/nexo_agent_api/live_tower.py", names)
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["version"], "1.0.1")
            memory = archive.read("runtime/nexo_agent_api/memory.py").decode("utf-8")
            self.assertIn("class Memory", memory)
            self.assertIn("def dreams(", memory)
            self.assertIn("def related_work(", memory)
            self.assertIn("def feedback_proposal(", memory)

    def test_writer_bundle_exposes_same_memory_cli(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        script = repo / "scripts" / "build_gpt_writer_bundle.py"
        spec = importlib.util.spec_from_file_location("build_gpt_writer_bundle_memory_test", script)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        import tempfile

        with tempfile.TemporaryDirectory() as work:
            module.OUT = Path(work) / "nexo_gpt_writer.py"
            writer = module.build()
            proc = subprocess.run(
                [sys.executable, str(writer), "memory", "--help"],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("context", proc.stdout)
        self.assertIn("feedback", proc.stdout)

    def test_cli_exposes_retrieval_without_write_commands(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(self.loader()), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for command in ("context", "search", "dream", "related", "feedback"):
            self.assertIn(command, proc.stdout)
        for command in ("apply", "robot", "scheduler", "delete"):
            blocked = subprocess.run(
                [sys.executable, str(self.loader()), command],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(blocked.returncode, 2)


if __name__ == "__main__":
    unittest.main()
