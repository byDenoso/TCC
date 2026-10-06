from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


class WriterBundleDeterminismTest(unittest.TestCase):
    def test_committed_writer_matches_source_and_requires_extension(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        script = repo / "scripts" / "build_gpt_writer_bundle.py"
        spec = importlib.util.spec_from_file_location("build_gpt_writer_source_test", script)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as work:
            module.OUT = Path(work) / "nexo_gpt_writer.py"
            self.assertEqual(module.build().read_bytes(), (repo / "gpt/nexo_gpt_writer.py").read_bytes())
            module.REPO = Path(work) / "missing-sources"
            with self.assertRaisesRegex(RuntimeError, "Writer extension source missing"):
                module.build()

    def test_source_mtime_does_not_change_bundle_bytes(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        script = repo / "scripts" / "build_gpt_writer_bundle.py"
        spec = importlib.util.spec_from_file_location("build_gpt_writer_bundle_test", script)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        source = repo / "runtime" / "nexo_agent_api" / "gpt_writer.py"
        stat = source.stat()
        with tempfile.TemporaryDirectory() as work:
            module.OUT = Path(work) / "nexo_gpt_writer.py"
            first = module.build().read_bytes()
            try:
                os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
                second = module.build().read_bytes()
            finally:
                os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
