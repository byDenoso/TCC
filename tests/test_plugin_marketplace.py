"""Verify the packaged skills remain exact derivatives of gpt/skills."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.build_plugin_marketplace import SKILLS, SOURCE_VERSION, build

ROOT = Path(__file__).resolve().parents[1]


class MarketplaceTests(unittest.TestCase):
    def test_repository_package_matches_sources(self):
        self.assertEqual(build(ROOT, check=True), 5)
        manifest = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual([p["name"] for p in manifest["plugins"]], ["nexo"])
        self.assertEqual(manifest["plugins"][0]["source"]["path"], "./plugins/nexo")
        for name in SKILLS:
            packaged = (ROOT / "plugins/nexo/skills" / name / "SKILL.md").read_text()
            self.assertIn("name: " + name, packaged)
            self.assertNotIn("olympus", packaged.casefold())

    def test_drift_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = root / "gpt/skills"
            sources.mkdir(parents=True)
            for name in SKILLS:
                shutil.copyfile(ROOT / "gpt/skills" / f"{name}-{SOURCE_VERSION}.md",
                                sources / f"{name}-{SOURCE_VERSION}.md")
            build(root, check=False)
            self.assertEqual(build(root, check=True), 5)
            target = root / "plugins/nexo/skills/nexo-lite/SKILL.md"
            target.write_text(target.read_text() + "\nDeriva alterada\n")
            with self.assertRaisesRegex(ValueError, "diverge"):
                build(root, check=True)


if __name__ == "__main__":
    unittest.main()
