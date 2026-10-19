"""Generate the NEXO plugin from the pinned skills in gpt/skills/."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.4.0"
SKILLS = ("nexo-master-router", "nexo-closed-loop", "nexo-lite")


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def generated_files(root=ROOT):
    files = {
        Path(".agents/plugins/marketplace.json"): json_bytes({
            "name": "nexo-marketplace",
            "interface": {"displayName": "NEXO"},
            "plugins": [{
                "name": "nexo",
                "source": {"source": "local", "path": "./plugins/nexo"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Productivity",
            }],
        }),
        Path("plugins/nexo/plugin.json"): json_bytes({
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "name": "nexo",
            "version": VERSION,
            "description": "Router, ciclo de pesquisa e NEXO Lite.",
            "author": {"name": "Dener Pereira"},
            "repository": "https://github.com/byDenoso/TCC",
            "extensions": {"com.openai": {"interface": {
                "displayName": "NEXO",
                "shortDescription": "Router, ciclo de pesquisa e NEXO Lite.",
                "developerName": "Dener Pereira",
                "category": "Productivity",
            }}},
        }),
    }
    for name in SKILLS:
        source = root / "gpt/skills" / f"{name}-{VERSION}.md"
        files[Path("plugins/nexo/skills") / name / "SKILL.md"] = source.read_bytes()
    return files


def build(root=ROOT, check=False):
    files = generated_files(root)
    if check:
        divergent = [str(path) for path, content in files.items()
                     if not (root / path).is_file() or (root / path).read_bytes() != content]
        divergent += [str(path.relative_to(root))
                      for path in (root / "plugins/nexo").rglob("*")
                      if path.is_file() and path.relative_to(root) not in files]
        return divergent
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Falha se o pacote divergir da fonte.")
    args = parser.parse_args()
    divergent = build(check=args.check)
    if divergent:
        print("Pacote divergente: " + ", ".join(divergent))
        return 1
    print("NEXO: pacote conferido." if args.check else "NEXO: pacote gerado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
