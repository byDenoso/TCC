import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.build_plugin_marketplace import ROOT, SKILLS, VERSION, build


class PluginMarketplaceTests(unittest.TestCase):
    def test_committed_package_matches_sources(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_plugin_marketplace.py"), "--check"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_marketplace_resolves_portable_plugin_and_exact_three_skills(self):
        marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual([item["name"] for item in marketplace["plugins"]], ["nexo"])
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["source"]["source"], "local")
        plugin = ROOT / entry["source"]["path"]
        manifest = json.loads((plugin / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "nexo")
        self.assertEqual(manifest["version"], VERSION)
        self.assertEqual(manifest["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertEqual({path.name for path in (plugin / "skills").iterdir()}, set(SKILLS))
        for name in SKILLS:
            content = (plugin / "skills" / name / "SKILL.md").read_bytes()
            self.assertEqual(content, (ROOT / "gpt/skills" / f"{name}-{VERSION}.md").read_bytes())
            self.assertIn(f"\nname: {name}\n".encode(), content)

    def test_build_and_check_detect_source_or_package_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "gpt/skills"
            sources.mkdir(parents=True)
            for name in SKILLS:
                shutil.copyfile(ROOT / "gpt/skills" / f"{name}-{VERSION}.md",
                                sources / f"{name}-{VERSION}.md")
            build(root)
            self.assertEqual(build(root, check=True), [])
            source = sources / f"nexo-lite-{VERSION}.md"
            source.write_bytes(source.read_bytes() + b"\nTest source edit.\n")
            self.assertEqual(build(root, check=True), ["plugins/nexo/skills/nexo-lite/SKILL.md"])
            build(root)
            self.assertEqual(build(root, check=True), [])
            target = root / "plugins/nexo/skills/nexo-lite/SKILL.md"
            target.write_bytes(b"Out of sync.\n")
            self.assertEqual(build(root, check=True), ["plugins/nexo/skills/nexo-lite/SKILL.md"])

    def test_check_rejects_an_extra_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "gpt/skills"
            sources.mkdir(parents=True)
            for name in SKILLS:
                shutil.copyfile(ROOT / "gpt/skills" / f"{name}-{VERSION}.md",
                                sources / f"{name}-{VERSION}.md")
            build(root)
            extra = root / "plugins/nexo/skills/extra/SKILL.md"
            extra.parent.mkdir()
            extra.write_text("Unrequested skill.\n")
            self.assertEqual(build(root, check=True), ["plugins/nexo/skills/extra/SKILL.md"])


if __name__ == "__main__":
    unittest.main()
