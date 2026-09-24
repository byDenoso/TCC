#!/usr/bin/env python3
"""The one entry point that reads and writes the live NEXO Tower.

    nexo_tower.py status                 Drive head vs published ATLAS manifest
    nexo_tower.py pull   [--dest DIR]    download + verify + materialize (read-only use)
    nexo_tower.py download --out FILE    raw live Tower bytes (CI reader)
    nexo_tower.py apply  REQUEST.json... mutate -> CAS write same file id -> readback -> notify ATLAS
    nexo_tower.py project --out DIR      build the public projection straight from Drive
    nexo_tower.py frontier [--roadmap ID] next executable roadmap test (canonical frontier logic)
    nexo_tower.py inbox list|apply|done  ChatGPT proposals (GitHub issues, nexo-inbox branch, Drive NEXO_INBOX)

Every automation and every human-driven change goes through ``apply``; nothing
else writes operational truth.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.nexo_agent_api.drive_transport import (  # noqa: E402
    DriveInbox,
    DriveTower,
    TowerConflict,
    nexo_home,
    writer_lock,
)
from runtime.nexo_agent_api.live_tower import (  # noqa: E402
    LIVE_TOWER_NAME,
    materialize_live_tower,
    read_live_tower_bytes,
    verify_live_tower,
)

ATLAS_MANIFEST_URL = "https://bydenoso.github.io/Pantheon/tower-projection/manifest.json"
PAGES_REPOSITORY = "byDenoso/Pantheon"
PAGES_EVENT = "nexo-public-projection-updated"


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _published_manifest() -> dict | None:
    try:
        with urllib.request.urlopen(ATLAS_MANIFEST_URL + f"?t={int(time.time())}", timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def cmd_status(_: argparse.Namespace) -> int:
    tower, head = DriveTower().read()
    fingerprint = verify_live_tower(tower)
    published = _published_manifest() or {}
    atlas_revision = published.get("tower_revision") or published.get("source_state_fingerprint")
    _print({
        "tower_state_fingerprint": fingerprint,
        "tower_head_revision_id": head.head_revision_id,
        "tower_modified_time": head.modified_time,
        "tower_file_count": tower.get("file_count"),
        "atlas_tower_revision": atlas_revision,
        "atlas_generated_at": published.get("generated_at"),
        "atlas": "CURRENT" if atlas_revision == fingerprint else ("UNREACHABLE" if not published else "OUTDATED"),
    })
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    raw, head = DriveTower().download()
    fingerprint = verify_live_tower(read_live_tower_bytes(raw))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    _print({"path": str(out), "state_fingerprint": fingerprint, "head_revision_id": head.head_revision_id})
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    raw, head = DriveTower().download()
    fingerprint = verify_live_tower(read_live_tower_bytes(raw))
    dest = Path(args.dest) if args.dest else nexo_home() / "tower" / fingerprint.replace(":", "-")[:23] / "TOWER_V06"
    root, metadata = materialize_live_tower(raw, dest)
    _print({"root": str(root), "head_revision_id": head.head_revision_id, **metadata})
    return 0


def _push_signal(fingerprint: str) -> str:
    """Trigger the Pages deploy by pushing a tiny head marker to Pantheon.

    Push-triggered runs start immediately (GitHub throttles the cron to hours).
    Uses a dedicated clone under NEXO_HOME and the machine's normal git access;
    no token is read or handled here.
    """
    import subprocess

    repo = nexo_home() / "pantheon-signal"
    run = lambda *args: subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=120)
    try:
        if not (repo / ".git").is_dir():
            clone = subprocess.run(
                ["git", "clone", "-q", "--depth", "1", f"https://github.com/{PAGES_REPOSITORY}.git", str(repo)],
                capture_output=True, text=True, timeout=300,
            )
            if clone.returncode:
                return "SIGNAL_CLONE_FAILED"
        run("fetch", "-q", "--depth", "1", "origin", "main")
        run("reset", "-q", "--hard", "origin/main")
        marker = repo / "nexo-one" / "tower-head.json"
        marker.write_text(json.dumps({"tower_revision": fingerprint, "signalled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n", encoding="utf-8")
        run("add", str(marker))
        commit = run("-c", "user.name=NEXO Tower Writer", "-c", "user.email=denosooo2@gmail.com", "commit", "-q", "-m", f"tower: head {fingerprint[:19]} (Pages refresh signal)")
        if commit.returncode:
            return "SIGNAL_NOTHING_TO_COMMIT" if "nothing" in commit.stdout + commit.stderr else "SIGNAL_COMMIT_FAILED"
        push = run("push", "-q", "origin", "HEAD:main")
        return "PUSHED_SIGNAL" if push.returncode == 0 else "SIGNAL_PUSH_FAILED"
    except Exception as exc:  # the throttled cron still converges
        return f"SIGNAL_FAILED_{type(exc).__name__}"


def _notify_atlas(fingerprint: str = "") -> str:
    token = os.environ.get("NEXO_PAGES_DISPATCH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        if fingerprint and os.environ.get("NEXO_PAGES_SIGNAL", "1") != "0":
            return _push_signal(fingerprint)
        return "SKIPPED_NO_TOKEN_CRON_RECONCILES"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{PAGES_REPOSITORY}/dispatches",
        data=json.dumps({"event_type": PAGES_EVENT}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return f"DISPATCHED_{response.status}"
    except Exception as exc:  # the 15-min Pages reconciler still converges
        return f"DISPATCH_FAILED_{type(exc).__name__}"


from runtime.nexo_agent_api.tower_apply import apply_document as _apply_document  # noqa: E402


def cmd_apply(args: argparse.Namespace) -> int:
    from runtime.nexo_agent_api.mutations import apply_mutation_request

    requests = []
    for name in args.requests:
        payload = json.loads(Path(name).read_text(encoding="utf-8"))
        requests.extend(payload if isinstance(payload, list) else [payload])

    attempts = max(1, args.retries + 1)
    for attempt in range(1, attempts + 1):
        try:
            with writer_lock():
                drive = DriveTower(write=True)
                raw, base = drive.download()
                before = verify_live_tower(read_live_tower_bytes(raw))
                with tempfile.TemporaryDirectory(prefix="nexo-tower-write-") as work:
                    root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
                    receipts = [
                        _apply_document(root, request) if "document" in request else apply_mutation_request(root, request)
                        for request in requests
                    ]
                    if any("document" in request for request in requests):
                        from runtime.nexo_agent_api.live_tower import publish_live_tower

                        publish_live_tower(root)
                    rejected = [r for r in receipts if not r.get("accepted", True) or r.get("issue")]
                    if rejected:
                        _print({"status": "REJECTED", "tower_state_fingerprint": before, "receipts": receipts})
                        return 2
                    packed = (root / LIVE_TOWER_NAME).read_bytes()
                    after = verify_live_tower(read_live_tower_bytes(packed))
                    if after == before:
                        _print({"status": "NO_OP", "tower_state_fingerprint": before, "receipts": receipts})
                        return 0
                    if args.dry_run:
                        _print({"status": "DRY_RUN", "before": before, "after": after, "receipts": receipts})
                        return 0
                    write = drive.compare_and_swap(base, packed)
            _print({
                "status": "PASS",
                "before": before,
                "after": write["state_fingerprint"],
                "write": write,
                "atlas_notify": _notify_atlas(write["state_fingerprint"]),
                "receipts": receipts,
            })
            return 0
        except TowerConflict as exc:
            if attempt == attempts:
                _print({"status": "CONFLICT", "detail": str(exc), "attempts": attempt})
                return 3
            time.sleep(min(30, 2 ** attempt))
    return 3


def cmd_project(args: argparse.Namespace) -> int:
    from runtime.nexo_agent_api.public_projection import build_public_projection, verify_projection

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_public_projection import write_projection_if_changed  # noqa: E402

    raw, _ = DriveTower().download()
    with tempfile.TemporaryDirectory(prefix="nexo-tower-project-") as work:
        root, metadata = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        projection = build_public_projection(
            root,
            tower_revision=metadata["tower_revision"],
            tower_file_id=metadata["tower_file_id"],
            generated_at=None if args.no_timestamp else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        projection["manifest"].update(metadata)
        ok, detail = verify_projection(projection)
        if not ok:
            print(f"::error::projection failed verification: {detail}", file=sys.stderr)
            return 1
        changed = write_projection_if_changed(args.out, projection)
    _print({"out": args.out, "changed": changed, **projection["manifest"]})
    return 0


def cmd_frontier(args: argparse.Namespace) -> int:
    """Next executable roadmap work (V1 inline tests and V2 frontier_refs)."""
    from runtime.nexo_agent_api.frontier import roadmap_frontier

    raw, _ = DriveTower().download()
    with tempfile.TemporaryDirectory(prefix="nexo-tower-frontier-") as work:
        root, metadata = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        frontier = roadmap_frontier(root, args.roadmap)
    _print({"tower_state_fingerprint": metadata["tower_revision"], **frontier})
    return 0


class GitHubInbox:
    """ChatGPT proposals as files on the TCC ``nexo-inbox`` branch (``inbox/*.json``).

    ChatGPT's Drive connector cannot create raw JSON files, but its GitHub MCP can
    commit them. Applied files are moved to ``processed/``. Uses the machine's git
    access through a dedicated clone under NEXO_HOME.
    """

    BRANCH = "nexo-inbox"

    def __init__(self) -> None:
        import subprocess

        self.repo = nexo_home() / "tcc-inbox"
        self._sp = subprocess
        if not (self.repo / ".git").is_dir():
            self._sp.run(["git", "clone", "-q", "--depth", "1", "--branch", self.BRANCH,
                          "https://github.com/byDenoso/TCC.git", str(self.repo)], check=True, timeout=300)

    def _git(self, *args: str):
        return self._sp.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, timeout=120)

    def pending(self) -> list[dict]:
        self._git("fetch", "-q", "--depth", "1", "origin", self.BRANCH)
        self._git("reset", "-q", "--hard", f"origin/{self.BRANCH}")
        items = []
        for path in sorted((self.repo / "inbox").glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                payload = {"unparseable": path.read_text(encoding="utf-8", errors="replace")[:2000]}
            created = payload.get("created_at") if isinstance(payload, dict) else None
            items.append({"id": f"github:{path.name}", "name": path.name, "createdTime": created, "payload": payload})
        return items

    def mark_processed(self, item_id: str) -> None:
        name = item_id.split(":", 1)[1]
        self._git("mv", f"inbox/{name}", f"processed/{name}")
        self._git("-c", "user.name=NEXO Tower Writer", "-c", "user.email=denosooo2@gmail.com",
                  "commit", "-q", "-m", f"inbox: processed {name}")
        self._git("push", "-q", "origin", f"HEAD:{self.BRANCH}")


class IssueInbox:
    """ChatGPT proposals as GitHub issues on ``byDenoso/TCC`` (third create-only inbox).

    Opening an issue is the lightest write ChatGPT's GitHub connector allows, so it
    works when both the Drive file and the branch commit are refused. An issue is a
    proposal when its title starts with ``[NEXO_INBOX]`` or it carries the
    ``nexo-proposal`` label. The body is the proposal envelope: the first fenced
    ```json block, or the whole body. The repo is public, so only issues opened by
    ``TRUSTED_AUTHORS`` count. Applied issues get a comment and are closed.
    """

    REPO = "byDenoso/TCC"
    TITLE_PREFIX = "[NEXO_INBOX]"
    LABEL = "nexo-proposal"
    TRUSTED_AUTHORS = frozenset({"byDenoso"})

    def __init__(self) -> None:
        self.token = os.environ.get("NEXO_INBOX_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or self._gh_token()
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN (or gh auth) required to read the issue inbox")

    @staticmethod
    def _gh_token() -> str:
        import subprocess

        try:
            out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return ""
        return out.stdout.strip() if out.returncode == 0 else ""

    def _api(self, path: str, method: str = "GET", body: dict | None = None):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.REPO}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "nexo-tower-writer"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
        return json.loads(raw) if raw else None

    @staticmethod
    def envelope(body: str):
        import re

        match = re.search(r"```(?:json)?[ \t]*\n(.*?)```", body or "", re.S)
        text = match.group(1) if match else (body or "")
        try:
            return json.loads(text)
        except ValueError:
            return {"unparseable": text[:2000]}

    @classmethod
    def select(cls, issues: list[dict]) -> list[dict]:
        items = []
        for issue in issues:
            if "pull_request" in issue:
                continue
            labels = {label.get("name") for label in issue.get("labels", [])}
            if not (str(issue.get("title", "")).startswith(cls.TITLE_PREFIX) or cls.LABEL in labels):
                continue
            if (issue.get("user") or {}).get("login") not in cls.TRUSTED_AUTHORS:
                continue
            items.append({"id": f"issue:{issue['number']}", "name": f"issue-{issue['number']}",
                          "createdTime": issue.get("created_at"), "payload": cls.envelope(issue.get("body") or "")})
        return items

    def pending(self) -> list[dict]:
        return self.select(self._api("/issues?state=open&per_page=100&sort=created&direction=asc") or [])

    def mark_processed(self, item_id: str) -> None:
        number = item_id.split(":", 1)[1]
        self._api(f"/issues/{number}/comments", "POST", {"body": "Applied by the NEXO Tower writer (CAS + readback)."})
        self._api(f"/issues/{number}", "PATCH", {"state": "closed", "state_reason": "completed"})


def _collect_inbox(github: "GitHubInbox") -> list[dict]:
    """Every inbox, oldest first. A failing secondary inbox is logged, never fatal."""
    items = [dict(i, source="GITHUB") for i in github.pending()]
    for source, factory in (("ISSUE", IssueInbox), ("DRIVE", DriveInbox)):
        try:
            items += [dict(i, source=source) for i in factory().pending()]
        except Exception as exc:
            print(f"{source.lower()} inbox unavailable: {type(exc).__name__}: {exc}"[:300], file=sys.stderr)
    items.sort(key=lambda i: str(i.get("createdTime") or ""))
    return items


def _mark(github: "GitHubInbox", item_ids: list[str]) -> None:
    drive = issues = None
    for item_id in item_ids:
        if item_id.startswith("github:"):
            github.mark_processed(item_id)
        elif item_id.startswith("issue:"):
            issues = issues or IssueInbox()
            issues.mark_processed(item_id)
        else:
            drive = drive or DriveInbox(write=True)
            drive.mark_processed(item_id)


def _inbox_apply(github: "GitHubInbox", args: argparse.Namespace) -> int:
    """Apply every inbox proposal (generic converter) in ONE CAS write, then mark them processed."""
    from runtime.nexo_agent_api.inbox_apply import ProposalError, proposal_to_requests

    items = _collect_inbox(github)
    if not items:
        _print({"status": "EMPTY"})
        return 0
    raw, _ = DriveTower().download()
    requests, used, skipped = [], [], []
    with tempfile.TemporaryDirectory(prefix="nexo-inbox-") as work:
        root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        for item in items:
            envelope = item.get("payload")
            if not isinstance(envelope, dict):
                skipped.append({"id": item["id"], "reason": "UNPARSEABLE"})
                continue
            try:
                requests += proposal_to_requests({**envelope, "_inbox_id": item["id"], "_inbox_name": item["name"]}, root)
                used.append(item["id"])
            except ProposalError as exc:
                skipped.append({"id": item["id"], "reason": str(exc)})
    # Several proposals may target the same entity (a GPT pulse re-running a test):
    # the newest wins, so one write never conflicts with itself on entity_version.
    latest: dict[tuple, dict] = {}
    for request in requests:
        key = ("document", request["document"], request.get("request_id")) if "document" in request             else (request["entity_kind"], request["entity_name"])
        latest.pop(key, None)
        latest[key] = request
    requests = list(latest.values())
    if not requests:
        _print({"status": "NOTHING_APPLICABLE", "skipped": skipped})
        return 0
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(requests, handle, ensure_ascii=False)
    code = cmd_apply(argparse.Namespace(requests=[handle.name], dry_run=args.dry_run, retries=2))
    if code == 0 and not args.dry_run:
        _mark(github, used)
    print(json.dumps({"inbox_applied": used if code == 0 else [], "skipped": skipped}, ensure_ascii=False))
    return code


def cmd_inbox(args: argparse.Namespace) -> int:
    github = GitHubInbox()
    if args.action == "list":
        _print({"items": [{k: item.get(k) for k in ("id", "source", "name", "createdTime", "payload")}
                          for item in _collect_inbox(github)]})
    elif args.action == "apply":
        return _inbox_apply(github, args)
    else:
        _mark(github, args.ids)
        _print({"processed": args.ids})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    p = sub.add_parser("download"); p.add_argument("--out", required=True); p.set_defaults(func=cmd_download)
    p = sub.add_parser("pull"); p.add_argument("--dest"); p.set_defaults(func=cmd_pull)
    p = sub.add_parser("apply")
    p.add_argument("requests", nargs="+", help="mutation request JSON files (object or list)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--retries", type=int, default=2)
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser("project"); p.add_argument("--out", required=True); p.add_argument("--no-timestamp", action="store_true"); p.set_defaults(func=cmd_project)
    p = sub.add_parser("frontier", help="next executable roadmap test")
    p.add_argument("--roadmap")
    p.set_defaults(func=cmd_frontier)
    p = sub.add_parser("inbox", help="ChatGPT proposal inbox on Drive (create-only)")
    p.add_argument("action", choices=["list", "done", "apply"])
    p.add_argument("ids", nargs="*")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_inbox)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
