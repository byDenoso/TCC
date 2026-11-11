#!/usr/bin/env python3
"""Derive the NEXO ChatGPT marketplace from the three pinned gpt/skills files."""
import argparse
import json
from pathlib import Path

SKILLS = ("nexo-master-router", "nexo-closed-loop", "nexo-lite")
SOURCE_VERSION = "0.4.0"


def render(source):
    text = source.read_text(encoding="utf-8").replace("\r\n", "\n")
    lines = []
    for line in text.splitlines(keepends=True):
        if "olympus" in line.casefold():
            if line.startswith("description:"):
                line = line.replace(", Olympus", "")
            else:
                continue
        lines.append(line)
    result = "".join(lines)
    if "olympus" in result.casefold():
        raise ValueError(f"Não foi possível retirar Olympus: {source}")
    return result


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def expected_files(root):
    marketplace = {
        "name": "nexo", "interface": {"displayName": "NEXO"},
        "plugins": [{"name": "nexo", "source": {"source": "local", "path": "./plugins/nexo"},
                     "category": "Productivity"}],
    }
    plugin = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "nexo", "version": SOURCE_VERSION,
        "description": "Skills do NEXO para pesquisa, operação e suporte técnico.",
        "extensions": {"com.openai": {"interface": {
            "displayName": "NEXO", "shortDescription": "Três skills do NEXO",
            "developerName": "NEXO", "category": "Productivity",
            "capabilities": ["Read"]}}},
    }
    paths = {
        root / ".agents/plugins/marketplace.json": json_text(marketplace),
        root / "plugins/nexo/plugin.json": json_text(plugin),
    }
    for name in SKILLS:
        source = root / "gpt/skills" / f"{name}-{SOURCE_VERSION}.md"
        paths[root / "plugins/nexo/skills" / name / "SKILL.md"] = render(source)
    return paths


def build(root, check):
    expected = expected_files(root)
    skills_root = root / "plugins/nexo/skills"
    actual = set(skills_root.rglob("SKILL.md")) if skills_root.exists() else set()
    wanted = {path for path in expected if path.name == "SKILL.md"}
    extra = actual - wanted
    if extra:
        raise ValueError(f"Skills não declaradas: {sorted(map(str, extra))}")
    if check:
        drift = [str(path.relative_to(root)) for path, content in expected.items()
                 if not path.is_file() or path.read_text(encoding="utf-8") != content]
        if drift:
            raise ValueError("Plugin diverge de gpt/skills: " + ", ".join(drift))
    else:
        for path, content in expected.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    return len(expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(f"NEXO marketplace: {build(args.root.resolve(), args.check)} arquivos verificados" if args.check
          else f"NEXO marketplace: {build(args.root.resolve(), False)} arquivos gerados")


if __name__ == "__main__":
    main()
