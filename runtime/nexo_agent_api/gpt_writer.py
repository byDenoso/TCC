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


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "frontier":
        # Same frontier as the CLI writer: resume CHECKPOINTED/RUNNING first, then READY.
        from .frontier import roadmap_frontier

        with tempfile.TemporaryDirectory(prefix="nexo-gpt-frontier-") as work:
            root, _ = materialize_live_tower(Path(argv[1]).read_bytes(), Path(work) / "TOWER_V06")
            print(json.dumps(roadmap_frontier(root, argv[2] if len(argv) > 2 else None), ensure_ascii=False, indent=1))
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
