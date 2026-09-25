"""Referee 2 (Claude, external model) helper for the NEXO closed loop.

    python scripts/referee2.py queue  [--out DIR]   download the Tower, print what Referee 2 must judge
    python scripts/referee2.py submit FILE.json     push one inbox envelope to byDenoso/TCC@nexo-inbox

Referee 2 only reads the Tower and proposes VERDICT_REVIEW (referee 2) or LEARNING_SIGNAL notes;
the GPT Guardião applies them. Olympus personal data is never printed (private tests show ids only).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from runtime.nexo_agent_api.evolution import evolution_status  # noqa: E402
from runtime.nexo_agent_api.live_tower import materialize_live_tower  # noqa: E402
from runtime.nexo_agent_api.tower_paths import entity_path  # noqa: E402

REVIEW_FIELDS = ("id", "roadmap_id", "question", "null", "rival", "method", "dataset_and_selection", "success_criteria",
                 "kill_criteria", "claim_boundary", "verdict", "decision", "result_summary", "statistics", "limitations",
                 "reproducibility", "prediction", "prereg_hash", "review_state", "reviews", "contests", "executed_at")


def _download(out: Path) -> bytes:
    out.mkdir(parents=True, exist_ok=True)
    target = out / "tower.json"
    subprocess.run([sys.executable, str(REPO / "scripts" / "nexo_tower.py"), "download", "--out", str(target)],
                   check=True, capture_output=True)
    return target.read_bytes()


def queue(out: Path) -> dict:
    raw = _download(out)
    with tempfile.TemporaryDirectory(prefix="referee2-") as work:
        root, _ = materialize_live_tower(raw, Path(work) / "T")
        status = evolution_status(root)
        items = []
        for test_id in status["review_queue"]["referee_2"]:
            test = json.loads(entity_path(root, "test", test_id).read_text(encoding="utf-8"))
            if test.get("private") or str(test.get("domain") or "").upper() == "OLYMPUS":
                items.append({"id": test_id, "private": True, "verdict": test.get("verdict"),
                              "statistics": test.get("statistics"), "reviews": test.get("reviews")})
            else:
                items.append({k: test.get(k) for k in REVIEW_FIELDS if test.get(k) not in (None, "", [], {})})
        return {"referee_2_queue": items, "canaries_waiting": status["gate"]["canaries_waiting"],
                "roadmaps": status["roadmaps"], "genome": status["genome"]}


def submit(path: Path) -> str:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    kind = str(envelope.get("kind") or "BATCH")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"inbox/{stamp}-{kind}-referee2.json"
    env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="r2-", dir="C:/" if os.name == "nt" else None) as tmp:
        blob_src = Path(tmp) / "b.json"
        blob_src.write_text(json.dumps(envelope, ensure_ascii=False, indent=1), encoding="utf-8")
        env["GIT_INDEX_FILE"] = str(Path(tmp) / "idx")
        git = ["git", "-C", str(REPO), "-c", "core.protectNTFS=false"]
        run = lambda *a: subprocess.run([*git, *a], check=True, capture_output=True, text=True, env=env).stdout.strip()
        run("fetch", "-q", "origin", "nexo-inbox")
        run("read-tree", "origin/nexo-inbox")
        blob = run("hash-object", "-w", str(blob_src))
        run("update-index", "--add", "--cacheinfo", f"100644,{blob},{name}")
        tree = run("write-tree")
        message = f"inbox: Referee 2 {kind}\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
        commit = subprocess.run([*git, "commit-tree", tree, "-p", "origin/nexo-inbox"], input=message, check=True,
                                capture_output=True, text=True, env=env).stdout.strip()
        run("push", "-q", "origin", f"{commit}:refs/heads/nexo-inbox")
    return name


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "queue":
        out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path(tempfile.gettempdir()) / "referee2"
        print(json.dumps(queue(out), ensure_ascii=False, indent=1, default=str))
    elif len(sys.argv) == 3 and sys.argv[1] == "submit":
        print("pushed", submit(Path(sys.argv[2])))
    else:
        print(__doc__)
        raise SystemExit(2)
