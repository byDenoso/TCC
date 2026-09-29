"""Tower writer for a runtime without Drive credentials (ChatGPT's Python sandbox).

ChatGPT's Drive connector does the I/O (read the Tower, check the revision,
update_file on the same id, read back); this module does the rest offline with
the same rules as ``scripts/nexo_tower.py apply``:

    python nexo_gpt_writer.py apply  TOWER.json PROPOSALS.json OUT.json
    python nexo_gpt_writer.py verify TOWER.json [EXPECTED_FINGERPRINT]
    python nexo_gpt_writer.py frontier TOWER.json [ROADMAP_ID]   (what to execute next)
    python nexo_gpt_writer.py handoff TOWER.json list ROLE   (messages addressed to one role)

PROPOSALS.json is a list of inbox proposal envelopes ({kind, source, payload,
created_at}) and/or raw writer requests ({entity_kind, ...} or {document, ...}).
The result JSON lists before/after fingerprints, receipts and the proposals that
were rejected (those stay in the inbox).
"""

from __future__ import annotations

import json
import sys
import tempfile
from typing import Any
from pathlib import Path

from . import evolution
from .inbox_apply import ProposalError, proposal_to_requests
from .live_tower import LIVE_TOWER_NAME, materialize_live_tower, read_live_tower_bytes, verify_live_tower
from .tower_apply import apply_requests


def _is_request(item: dict) -> bool:
    return "document" in item or "entity_kind" in item or item.get("nexo_operation") in {
        "HANDOFF_CREATE", "HANDOFF_TRANSITION",
    }


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
                flat += [{**sub, "_inbox_source": item.get("_inbox_source"),
                          "_inbox_name": f"{base}-{i}", "_inbox_id": item.get("_inbox_id")}
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
            receipts = []
            for request in requests:
                operation = request.get("nexo_operation")
                if operation not in {"HANDOFF_CREATE", "HANDOFF_TRANSITION"}:
                    receipts.extend(apply_requests(root, [request]))
                    continue
                if str(request.get("_inbox_source") or "").upper() != "DRIVE":
                    receipts.append({
                        "accepted": False,
                        "issue": {"code": "PRIVATE_HANDOFF_REQUIRES_DRIVE_INBOX"},
                    })
                    continue
                from . import AgentService, TowerAgentIssue

                try:
                    service = AgentService(root)
                    if operation == "HANDOFF_CREATE":
                        envelope = request.get("handoff")
                        if not isinstance(envelope, dict):
                            raise TypeError("handoff must be a JSON object")
                        receipts.append(service.emit_handoff(**envelope))
                    else:
                        transition = request.get("transition")
                        if not isinstance(transition, dict):
                            raise TypeError("transition must be a JSON object")
                        receipts.append(service.transition_handoff(
                            transition.get("handoff_id", ""),
                            state=transition.get("state", ""),
                            writer_role=transition.get("writer_role", ""),
                        ))
                except TowerAgentIssue as exc:
                    receipts.append({
                        "accepted": False,
                        "issue": {"code": exc.code, "message": exc.message, "details": exc.details},
                    })
                    continue
                except (TypeError, AttributeError):
                    receipts.append({"accepted": False, "issue": {"code": "HANDOFF_ENVELOPE_INVALID"}})
                    continue
                else:
                    from .live_tower import publish_live_tower

                    publish_live_tower(root)
            failed = [r for r in receipts if not r.get("accepted", True) or r.get("issue")]
            report["receipts"].extend(receipts)
            if failed:
                report["rejected"].append({"item": label, "reason": failed[0].get("issue")})
            else:
                report["applied"].append(label)

        # Contest lifecycle is mechanical: attacks cannot be attacked, and a completed
        # depth-1 attack closes the original from its frozen criterion result.
        contest_requests = evolution.contest_chain_reconcile_requests(root)
        if contest_requests:
            contest_receipts = apply_requests(root, contest_requests)
            contest_failed = [r for r in contest_receipts if not r.get("accepted", True) or r.get("issue")]
            report["receipts"].extend(contest_receipts)
            if contest_failed:
                report["rejected"].append({"item": "contest-chain-reconcile", "reason": contest_failed[0].get("issue")})
            else:
                report["reconciled_contests"] = [r.get("document") or r.get("entity_name") for r in contest_receipts]

        # Maintenance is mechanical too: watchdog, repeated-failure stop, stale drafts,
        # pre-registration audit and roadmap FDR annotations.
        maintenance_requests = evolution.maintenance_reconcile_requests(root)
        if maintenance_requests:
            maintenance_receipts = apply_requests(root, maintenance_requests)
            maintenance_failed = [r for r in maintenance_receipts if not r.get("accepted", True) or r.get("issue")]
            report["receipts"].extend(maintenance_receipts)
            if maintenance_failed:
                report["rejected"].append({"item": "maintenance-reconcile", "reason": maintenance_failed[0].get("issue")})
            else:
                report["maintenance"] = len(maintenance_receipts)

        # Incident lifecycle is derived from canonical evidence already present in
        # the materialized Tower. Agents never declare incident state directly.
        incident_requests = evolution.incident_reconcile_requests(root)
        if incident_requests:
            incident_receipts = apply_requests(root, incident_requests)
            incident_failed = [r for r in incident_receipts if not r.get("accepted", True) or r.get("issue")]
            report["receipts"].extend(incident_receipts)
            if incident_failed:
                report["rejected"].append({"item": "incident-reconcile", "reason": incident_failed[0].get("issue")})
            else:
                report["reconciled"] = [r.get("document") or r.get("entity_name") for r in incident_receipts]
        packed = (root / LIVE_TOWER_NAME).read_bytes()
    after = verify_live_tower(read_live_tower_bytes(packed))
    report["after"] = after
    report["status"] = "NO_OP" if after == before else "READY_TO_UPLOAD"
    return (None if after == before else packed), report


def _queued_batteries(raw: bytes) -> list[dict]:
    from .evolution import pending_batteries

    with tempfile.TemporaryDirectory(prefix="nexo-robot-bat-") as work:
        root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        return pending_batteries(root)


def _family_items(raw: bytes, kind: str) -> list[dict]:
    """Robot-made proposals from pre-registered families: new grid cells as tests, READY instances as batteries."""
    from .evolution import family_battery_items, family_contest_items, family_instance_items, family_spawn_items

    build = {"spawn": family_spawn_items, "instances": family_instance_items, "contests": family_contest_items}.get(kind, family_battery_items)
    with tempfile.TemporaryDirectory(prefix="nexo-robot-family-") as work:
        root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        return build(root)


def _stop_closures(raw: bytes) -> list[dict]:
    from datetime import datetime, timezone

    from .evolution import evolution_status

    with tempfile.TemporaryDirectory(prefix="nexo-robot-status-") as work:
        root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        roadmaps = evolution_status(root).get("roadmaps", [])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [{"kind": "ROADMAP_CLOSE", "source": "WRITER_ROBOT", "created_at": now, "_inbox_name": f"robot-close-{r['roadmap_id']}",
             "payload": {"roadmap_id": r["roadmap_id"], "reason": r["stop_reached"],
                         "final_report": f"Fechado automaticamente pelo critério de parada ({r['stop_reached']}): "
                                         f"{r['confirmed']} confirmados, {r['tests_used']} testes usados."}}
            for r in roadmaps if r.get("stop_reached")]


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


PRODUCERS = ("GPT", "CLAUDE")


def producer_of(item: dict[str, Any]) -> str | None:
    """Declared producer of an automated proposal. Scheduled GPT files (scheduled-*) are GPT by convention."""
    value = str(item.get("producer") or "").strip().upper()
    if value in PRODUCERS:
        return value
    if str(item.get("_inbox_name") or "").startswith("scheduled-"):
        return "GPT"
    return None


def split_by_producer(items: list[dict[str, Any]], active: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(apply, shadow). Items without a producer (Dener, conversations, robot) always apply."""
    active = str(active or "GPT").strip().upper()
    if active not in PRODUCERS:
        active = "GPT"
    keep, shadow = [], []
    for item in items:
        producer = producer_of(item)
        (shadow if producer and producer != active else keep).append(item)
    return keep, shadow


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[0] == "handoff" and argv[2] == "list":
        from . import AgentService

        role = argv[3].upper()
        with tempfile.TemporaryDirectory(prefix="nexo-gpt-handoff-") as work:
            root, metadata = materialize_live_tower(Path(argv[1]).read_bytes(), Path(work) / "TOWER_V06")
            items = AgentService(root).inbox_for(role)
        print(json.dumps({
            "tower_state_fingerprint": metadata["tower_revision"],
            "role": role,
            "count": len(items),
            "items": items,
        }, ensure_ascii=False, indent=1))
        return 0
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
                items.append({**payload, "_inbox_source": "DRIVE",
                              "_inbox_name": entry.get("name"), "_inbox_id": entry.get("id")})
        github = _GitHubInbox(os.environ.get("NEXO_INBOX_GITHUB_TOKEN", "").strip())
        for entry in github.pending():
            items.append({**entry["payload"], "_inbox_source": "GITHUB",
                          "_inbox_name": entry["name"], "_inbox_id": "github:" + entry["path"]})
        gateway_file = os.environ.get("NEXO_GATEWAY_ITEMS", "")
        gateway_ids = []
        if gateway_file and Path(gateway_file).is_file():
            try:
                gateway = json.loads(Path(gateway_file).read_text(encoding="utf-8")).get("items") or []
            except ValueError:
                gateway = []
            for entry in gateway:
                if isinstance(entry.get("envelope"), dict) and entry.get("id"):
                    items.append({**entry["envelope"], "_inbox_source": "GATEWAY",
                                  "_inbox_name": f"gw-{entry['id']}", "_inbox_id": "gateway:" + entry["id"]})
                    gateway_ids.append(entry["id"])
        updates_file = os.environ.get("NEXO_BATTERY_UPDATES", "")
        if updates_file and Path(updates_file).is_file():
            try:
                updates = json.loads(Path(updates_file).read_text(encoding="utf-8"))
            except ValueError:
                updates = []
            for index, update in enumerate(updates if isinstance(updates, list) else []):
                if isinstance(update, dict):
                    items.append({**update, "_inbox_source": "WRITER_ROBOT",
                                  "_inbox_name": f"battery-update-{index}-{update.get('payload', {}).get('battery_id')}"})
        # Producer gate (fallback in shadow): only the active producer's automated proposals reach the Tower;
        # the other producer's are acknowledged and logged, never applied. Unlabelled items (Dener, conversations,
        # robot) always pass, so switching GPT <-> CLAUDE never creates a second writer or a second truth.
        gateway_shadow: list[str] = []
        items, shadowed = split_by_producer(items, os.environ.get("NEXO_ACTIVE_PRODUCER", "GPT"))
        if shadowed:
            print(json.dumps({"shadow": len(shadowed), "active_producer": os.environ.get("NEXO_ACTIVE_PRODUCER", "GPT"),
                              "names": [str(s.get("_inbox_name")) for s in shadowed][:50]}, ensure_ascii=False))
            shadow_ids = {str(s.get("_inbox_id")) for s in shadowed}
            for entry in list(github.seen):
                if "github:" + entry["path"] in shadow_ids:
                    github.mark_processed(entry)
            for entry in pending:
                if entry.get("id") in shadow_ids:
                    inbox.mark_processed(entry["id"])
            gateway_shadow = [g for g in gateway_ids if "gateway:" + g in shadow_ids]
        dispatch_dir = os.environ.get("NEXO_BATTERY_DIR", "")
        dispatched: list[str] = []
        for attempt in range(3):
            raw, base = tower.download(cache=False)
            packed, report = apply_to_tower(raw, items)
            # Mechanical duties the GPT should not spend a run on: close roadmaps whose stop criterion was met.
            closes = _stop_closures(packed or raw)
            if closes:
                packed, extra = apply_to_tower(packed or raw, closes)
                report["applied"] = report.get("applied", []) + extra.get("applied", [])
                report["after"] = extra.get("after", report.get("after"))
                report["status"] = "READY_TO_UPLOAD"
            # Families: the robot itself turns pre-registered grids into tests and READY instances into batteries.
            for family_kind in ("spawn", "instances", "contests", "batteries"):
                family_items = _family_items(packed or raw, family_kind)
                if family_items:
                    packed, extra = apply_to_tower(packed or raw, family_items)
                    report["applied"] = report.get("applied", []) + extra.get("applied", [])
                    report["rejected"] = report.get("rejected", []) + extra.get("rejected", [])
                    report["after"] = extra.get("after", report.get("after"))
                    report["status"] = "READY_TO_UPLOAD"
            # Batteries queued by the Executor: hand their specs to the dispatcher step and mark them DISPATCHED.
            queued = _queued_batteries(packed or raw)
            if queued and dispatch_dir:
                Path(dispatch_dir).mkdir(parents=True, exist_ok=True)
                marks = []
                for battery in queued:
                    Path(dispatch_dir, f"{battery['id']}.json").write_text(json.dumps(battery, ensure_ascii=False), encoding="utf-8")
                    marks.append({"kind": "BATTERY_STATUS", "source": "WRITER_ROBOT", "_inbox_name": f"robot-dispatch-{battery['id']}",
                                  "payload": {"battery_id": battery["id"], "status": "DISPATCHED", "run_ref": "github-actions"}})
                packed, extra = apply_to_tower(packed or raw, marks)
                report["applied"] = report.get("applied", []) + extra.get("applied", [])
                report["after"] = extra.get("after", report.get("after"))
                report["status"] = "READY_TO_UPLOAD"
                dispatched = [b["id"] for b in queued]
            if packed is None:
                if not items:
                    print(json.dumps({"status": "NO_OP", "pending": len(pending)}))
                    out = os.environ.get("GITHUB_OUTPUT")
                    if out and gateway_shadow:  # shadowed-only run still advances the gateway cursor
                        with open(out, "a", encoding="utf-8") as handle:
                            handle.write("gateway_applied=" + ",".join(gateway_shadow) + chr(10))
                    return 0
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
        applied = {str(n) for n in report.get("applied", [])}
        acked = [g for g in gateway_ids if f"gw-{g}" in applied or any(n.startswith(f"gw-{g}-") for n in applied)] + gateway_shadow
        out = os.environ.get("GITHUB_OUTPUT")
        if out and acked and report.get("write"):
            with open(out, "a", encoding="utf-8") as handle:
                handle.write("gateway_applied=" + ",".join(acked) + chr(10))
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
