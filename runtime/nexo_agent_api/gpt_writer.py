"""Tower writer for a runtime without Drive credentials (ChatGPT's Python sandbox).

ChatGPT's Drive connector does the I/O (read the Tower, check the revision,
update_file on the same id, read back); this module does the rest offline with
the same rules as ``scripts/nexo_tower.py apply``:

    python nexo_gpt_writer.py apply  TOWER.json PROPOSALS.json OUT.json
    python nexo_gpt_writer.py verify TOWER.json [EXPECTED_FINGERPRINT]
    python nexo_gpt_writer.py frontier TOWER.json [ROADMAP_ID]   (what to execute next)

PROPOSALS.json is a list of inbox proposal envelopes ({kind, source, payload,
created_at}) and/or raw writer requests ({entity_kind, ...} or {document, ...}).
The result JSON lists before/after fingerprints, receipts and the proposals that
were rejected (those stay in the inbox).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from .inbox_apply import ProposalError, proposal_to_requests
from .live_tower import LIVE_TOWER_NAME, materialize_live_tower, read_live_tower_bytes, verify_live_tower
from .tower_apply import apply_requests


def _is_request(item: dict) -> bool:
    return "document" in item or "entity_kind" in item


def apply_to_tower(tower_raw: bytes, items: list[dict]) -> tuple[bytes | None, dict]:
    before = verify_live_tower(read_live_tower_bytes(tower_raw))
    report: dict = {"before": before, "applied": [], "rejected": [], "receipts": []}
    with tempfile.TemporaryDirectory(prefix="nexo-gpt-writer-") as work:
        root, _ = materialize_live_tower(tower_raw, Path(work) / "TOWER_V06")
        # A BATCH is applied item by item, so later envelopes see earlier ones (e.g. canary then canonize).
        flat: list[dict] = []
        for item in items:
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            if str(item.get("kind") or "").upper() == "BATCH" and isinstance(payload.get("items"), list):
                base = item.get("_inbox_name") or "batch"
                flat += [{**sub, "_inbox_name": f"{base}-{i}", "_inbox_id": item.get("_inbox_id")}
                         for i, sub in enumerate(payload["items"]) if isinstance(sub, dict)]
            else:
                flat.append(item)
        items = flat
        for index, item in enumerate(items):
            label = item.get("_inbox_name") or item.get("request_id") or f"item-{index}"
            try:
                requests = [item] if _is_request(item) else proposal_to_requests(item, root)
            except ProposalError as exc:
                report["rejected"].append({"item": label, "reason": str(exc)})
                continue
            receipts = apply_requests(root, requests)
            failed = [r for r in receipts if not r.get("accepted", True) or r.get("issue")]
            report["receipts"].extend(receipts)
            if failed:
                report["rejected"].append({"item": label, "reason": failed[0].get("issue")})
            else:
                report["applied"].append(label)
        packed = (root / LIVE_TOWER_NAME).read_bytes()
    after = verify_live_tower(read_live_tower_bytes(packed))
    report["after"] = after
    report["status"] = "NO_OP" if after == before else "READY_TO_UPLOAD"
    return (None if after == before else packed), report


class _GitHubInbox:
    """byDenoso/TCC@nexo-inbox inbox/*.json via the REST API (optional; needs a token with Contents read/write)."""

    API = "https://api.github.com/repos/byDenoso/TCC/contents"

    def __init__(self, token: str) -> None:
        self.token, self.seen = token, []

    def _req(self, method: str, path: str, body: dict | None = None):
        import urllib.request

        url = f"{self.API}/{path}" + ("?ref=nexo-inbox" if method == "GET" else "")
        data = json.dumps({"branch": "nexo-inbox", **body}).encode() if body else None
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "User-Agent": "nexo-writer-robot"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read() or b"null")

    def pending(self) -> list[dict]:
        if not self.token:
            return []
        import base64

        for item in sorted(self._req("GET", "inbox") or [], key=lambda i: i["name"]):
            if item["type"] != "file" or not item["name"].endswith(".json"):
                continue
            blob = self._req("GET", item["path"])
            try:
                payload = json.loads(base64.b64decode(blob["content"]).decode("utf-8-sig"))
            except ValueError:
                continue
            if isinstance(payload, dict):
                self.seen.append({"name": item["name"], "path": item["path"], "sha": blob["sha"], "content": blob["content"], "payload": payload})
        return self.seen

    def mark_processed(self, entry: dict) -> None:
        self._req("PUT", "processed/" + entry["name"], {"message": f"writer robot: processed {entry['name']}",
                                                         "content": "".join(entry["content"].split())})
        self._req("DELETE", entry["path"], {"message": f"writer robot: applied {entry['name']}", "sha": entry["sha"]})


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "frontier":
        # Same frontier as the CLI writer: resume CHECKPOINTED/RUNNING first, then READY.
        from .frontier import roadmap_frontier

        with tempfile.TemporaryDirectory(prefix="nexo-gpt-frontier-") as work:
            root, _ = materialize_live_tower(Path(argv[1]).read_bytes(), Path(work) / "TOWER_V06")
            print(json.dumps(roadmap_frontier(root, argv[2] if len(argv) > 2 else None), ensure_ascii=False, indent=1))
        return 0
    if len(argv) >= 1 and argv[0] == "robot":
        # Unattended writer (GitHub Actions): Drive NEXO_INBOX -> apply -> compare-and-swap the same Tower file id.
        # Needs env GOOGLE_SERVICE_ACCOUNT_JSON with write scope. Prints only ids and counts (never proposal content).
        import os
        from .drive_transport import DriveInbox, DriveTower, TowerConflict

        tower, inbox = DriveTower(write=True), DriveInbox(write=True)
        pending = [i for i in inbox.pending() if not str(i.get("name", "")).startswith("_")]
        items = []
        for entry in pending:
            payload = entry.get("payload")
            if isinstance(payload, dict):
                items.append({**payload, "_inbox_name": entry.get("name"), "_inbox_id": entry.get("id")})
        github = _GitHubInbox(os.environ.get("NEXO_INBOX_GITHUB_TOKEN", "").strip())
        for entry in github.pending():
            items.append({**entry["payload"], "_inbox_name": entry["name"], "_inbox_id": "github:" + entry["path"]})
        if not items:
            print(json.dumps({"status": "NO_OP", "pending": len(pending)}))
            return 0
        for attempt in range(3):
            raw, base = tower.download(cache=False)
            packed, report = apply_to_tower(raw, items)
            if packed is None:
                break
            if os.environ.get("NEXO_ROBOT_DRY"):
                print(json.dumps({"status": "DRY_RUN", "pending": len(pending), "items": len(items),
                                  "applied": len(report.get("applied", [])), "rejected": len(report.get("rejected", [])),
                                  "before": report.get("before"), "after": report.get("after")}))
                return 0
            try:
                write = tower.compare_and_swap(base, packed)
                report["write"] = {k: write.get(k) for k in ("state_fingerprint", "head_revision_id", "readback")}
                break
            except TowerConflict:
                if attempt == 2:
                    print(json.dumps({"status": "CONFLICT"}))
                    return 3
        by_name = {e.get("name"): e.get("id") for e in pending}
        applied_roots = {str(n) for n in report.get("applied", [])}
        for entry in github.seen:
            if entry["name"] in applied_roots or any(n.startswith(entry["name"] + "-") for n in applied_roots):
                github.mark_processed(entry)
        for name in report.get("applied", []):
            base_name = str(name).rsplit("-", 1)[0] if name not in by_name else name
            file_id = by_name.get(name) or by_name.get(base_name)
            if file_id:
                inbox.mark_processed(file_id)
        summary = {"status": report.get("status"), "before": report.get("before"), "after": report.get("after"),
                   "applied": len(report.get("applied", [])), "rejected": [r.get("item") for r in report.get("rejected", [])],
                   "write": report.get("write")}
        print(json.dumps(summary, ensure_ascii=False))
        out = os.environ.get("GITHUB_OUTPUT")
        if out and report.get("write"):
            with open(out, "a", encoding="utf-8") as handle:
                handle.write("tower_revision=" + str(report["write"]["state_fingerprint"]) + "\n")
        return 0
    if len(argv) >= 2 and argv[0] == "status":
        # Closed-loop view: Dener's gate, referee queues, roadmap stop criteria, genome, decoys, canary arm.
        from .evolution import evolution_status

        with tempfile.TemporaryDirectory(prefix="nexo-gpt-status-") as work:
            root, _ = materialize_live_tower(Path(argv[1]).read_bytes(), Path(work) / "TOWER_V06")
            print(json.dumps(evolution_status(root), ensure_ascii=False, indent=1, default=str))
        return 0
    if len(argv) >= 2 and argv[0] == "verify":
        fingerprint = verify_live_tower(read_live_tower_bytes(Path(argv[1]).read_bytes()))
        ok = len(argv) < 3 or fingerprint == argv[2]
        print(json.dumps({"fingerprint": fingerprint, "readback": "PASS" if ok else "MISMATCH"}))
        return 0 if ok else 1
    if len(argv) == 4 and argv[0] == "apply":
        items = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        packed, report = apply_to_tower(Path(argv[1]).read_bytes(), items if isinstance(items, list) else [items])
        if packed is not None:
            Path(argv[3]).write_bytes(packed)
            report["out"] = argv[3]
        print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
