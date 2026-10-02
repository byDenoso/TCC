"""Shared, fail-closed receipt and delivery logic for NEXO inbox relays."""

import base64
import hashlib
import json
import os
import re
import subprocess
import time
from enum import Enum
from pathlib import Path


MAX_ATTEMPTS = 5
ACK_PATH = "nexo-one/tcc-public-inbox-ack.json"
REQUEST_PATH_RE = re.compile(r"(?:^|/)nexo_persist/requests/[^/]+\.json$")
SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
SHA256_RE = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")


class RelayError(RuntimeError):
    pass


class ContentConflict(RelayError):
    pass


class StableIdConflict(ContentConflict):
    pass


class StableIdValidationError(RelayError):
    pass


class TerminalTransportError(RelayError):
    pass


class TerminalReceiptError(TerminalTransportError):
    pass


class ReceiptLedgerUnavailable(RelayError):
    pass


class ReadFailure(RelayError):
    pass


class ReceiptDisposition(str, Enum):
    MATCH = "match"
    ABSENT = "absent"
    CONFLICT = "conflict"
    REJECTED_TERMINAL = "rejected_terminal"
    UNAVAILABLE = "unavailable"


class GitHubContents:
    def __init__(self, repo, branch="nexo-inbox", timeout=30):
        self.repo, self.branch, self.timeout = repo, branch, timeout

    def _run(self, args, data=None):
        try:
            result = subprocess.run(
                ["gh", "api", *args],
                input=data,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return 0, {"message": "timeout", "uncertain": True}
        if result.returncode == 0:
            try:
                return 200, json.loads(result.stdout or "{}")
            except (TypeError, ValueError):
                return 200, {}
        message = (result.stderr or "").strip()
        match = re.search(r"HTTP\s+(\d{3})", message)
        return (
            int(match.group(1)) if match else 0,
            {"message": message, "uncertain": not bool(match)},
        )

    def get(self, path):
        return self._run([f"repos/{self.repo}/contents/{path}?ref={self.branch}"])

    def repository(self, repo=None):
        return self._run([f"repos/{repo or self.repo}"])

    def put(self, path, body, sha=None):
        payload = {
            "message": "NEXO scheduled persistence relay",
            "branch": self.branch,
            "content": base64.b64encode(body.encode("utf-8")).decode("ascii"),
        }
        if sha:
            payload["sha"] = sha
        return self._run(
            ["--method", "PUT", f"repos/{self.repo}/contents/{path}", "--input", "-"],
            data=json.dumps(payload),
        )


def decoded(meta):
    try:
        content = meta["content"].encode("ascii")
        # GitHub's Contents API may wrap Base64 with standard line breaks.
        # Ignore ASCII whitespace while keeping strict alphabet validation.
        encoded = re.sub(rb"\s+", b"", content)
        return base64.b64decode(encoded, validate=True).decode("utf-8")
    except (KeyError, AttributeError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ReadFailure("GitHub contents response has invalid or missing UTF-8 content") from exc


def _normalise_fingerprint(value):
    if isinstance(value, str):
        raw = value
    elif isinstance(value, dict):
        raw = None
        for key in ("fingerprint", "sha256", "hash"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                raw = candidate
                break
    else:
        raw = None
    if raw is None:
        return None
    match = SHA256_RE.fullmatch(raw)
    return match.group(1).lower() if match else None


def _is_terminal_rejection(value):
    if isinstance(value, str):
        return value.strip().upper().replace("-", "_").startswith("REJECTED")
    if not isinstance(value, dict):
        return False
    for key in ("status", "outcome", "result", "disposition", "state"):
        value_at_key = value.get(key)
        if isinstance(value_at_key, str):
            normalized = value_at_key.strip().upper().replace("-", "_")
            if normalized.startswith("REJECTED") or normalized == "TERMINAL_REJECTION":
                return True
            if normalized in {"TERMINAL", "DENIED"} and value.get("terminal") is True:
                return True
    for key in ("items", "effects", "results", "outcomes", "rejections", "rejected"):
        nested = value.get(key)
        if isinstance(nested, (dict, list)):
            children = nested.values() if isinstance(nested, dict) else nested
            if any(_is_terminal_rejection(child) for child in children):
                return True
    return False


class WriterReceipts:
    """A snapshot of both transient ACKs and durable Writer receipts."""

    def __init__(self, acked=None, available=True, receipts=None, rejected=None, error=None):
        self.acked = acked if isinstance(acked, dict) else {}
        self.receipts = receipts if isinstance(receipts, dict) else {}
        self.rejected = rejected if isinstance(rejected, dict) else {}
        self.available = bool(available)
        self.error = error

    @classmethod
    def load(cls, repo="byDenoso/Pantheon", client=None):
        client = client or GitHubContents(repo, branch="main")
        try:
            status, meta = client.get(ACK_PATH)
        except Exception as exc:  # transport/read errors must never become absence
            return cls(available=False, error=f"receipt ledger read failed: {type(exc).__name__}")
        if status == 404:
            # GitHub may also mask an inaccessible private repository as 404.
            # Confirm repository access before treating a missing file as an
            # empty ledger.
            try:
                access_status, _ = client.repository()
            except Exception as exc:
                return cls(available=False, error=f"receipt repository access check failed: {type(exc).__name__}")
            if access_status == 200:
                return cls(available=True)
            return cls(available=False, error=f"receipt repository access check failed HTTP {access_status}")
        if status != 200:
            return cls(available=False, error=f"receipt ledger read failed HTTP {status}")
        try:
            document = json.loads(decoded(meta))
        except (ReadFailure, json.JSONDecodeError) as exc:
            return cls(available=False, error=f"receipt ledger could not be decoded: {type(exc).__name__}")
        if not isinstance(document, dict):
            return cls(available=False, error="receipt ledger root must be an object")
        acked = document.get("acked", {})
        receipts = document.get("receipts", {})
        rejected = document.get("rejected", {})
        if not isinstance(acked, dict) or not isinstance(receipts, dict):
            return cls(available=False, error="receipt ledger maps must be objects")
        if isinstance(rejected, list):
            rejected = {target: True for target in rejected if isinstance(target, str)}
        if not isinstance(rejected, dict):
            return cls(available=False, error="receipt rejection ledger must be an object or list")
        return cls(acked=acked, receipts=receipts, rejected=rejected)

    def disposition(self, target, body):
        if not self.available:
            return ReceiptDisposition.UNAVAILABLE
        if target in self.rejected:
            return ReceiptDisposition.REJECTED_TERMINAL
        expected = hashlib.sha256(body.encode("utf-8")).hexdigest()
        entries = []
        for table in (self.acked, self.receipts):
            if target in table:
                entries.append(table[target])
        if not entries:
            return ReceiptDisposition.ABSENT
        if any(_is_terminal_rejection(entry) for entry in entries):
            return ReceiptDisposition.REJECTED_TERMINAL
        fingerprints = [_normalise_fingerprint(entry) for entry in entries]
        if any(fingerprint is None or fingerprint != expected for fingerprint in fingerprints):
            return ReceiptDisposition.CONFLICT
        return ReceiptDisposition.MATCH

    def confirmed(self, target, body):
        disposition = self.disposition(target, body)
        if disposition == ReceiptDisposition.MATCH:
            return True
        if disposition == ReceiptDisposition.ABSENT:
            return False
        if disposition == ReceiptDisposition.UNAVAILABLE:
            detail = f": {self.error}" if self.error else ""
            raise ReceiptLedgerUnavailable(f"Writer receipt ledger unavailable{detail}")
        if disposition == ReceiptDisposition.REJECTED_TERMINAL:
            raise TerminalReceiptError(f"{target}: Writer recorded a terminal rejection; refusing redelivery")
        raise ContentConflict(f"{target}: Writer receipt fingerprint conflicts with canonical request bytes")


def classify(status):
    if status in (401, 403, 422):
        return "terminal"
    if status == 409:
        return "conflict"
    if status == 404:
        return "missing"
    if status == 0 or status == 429 or 500 <= status <= 599:
        return "uncertain"
    return "other"


def readback(client, target, expected):
    try:
        status, meta = client.get(target)
    except Exception as exc:
        raise ReadFailure(f"{target}: destination read failed: {type(exc).__name__}") from exc
    if status == 200:
        if decoded(meta) == expected:
            return "same", meta
        raise ContentConflict(f"{target}: same stable ID maps to different content")
    if status == 404:
        return "missing", meta
    if classify(status) == "terminal":
        raise TerminalTransportError(f"{target}: read denied/invalid HTTP {status}")
    raise ReadFailure(f"{target}: destination read failed HTTP {status}")


def relay_one(client, receipts, target, body, sleep=time.sleep, max_attempts=MAX_ATTEMPTS):
    # Resolve terminal and conflicting durable facts before any possible write.
    disposition = receipts.disposition(target, body)
    if disposition == ReceiptDisposition.MATCH:
        return "already_relayed_and_receipted"
    if disposition == ReceiptDisposition.UNAVAILABLE:
        receipts.confirmed(target, body)  # raises with the ledger read detail
    if disposition == ReceiptDisposition.REJECTED_TERMINAL:
        receipts.confirmed(target, body)  # raises a terminal receipt error
    if disposition == ReceiptDisposition.CONFLICT:
        receipts.confirmed(target, body)  # raises a content conflict

    state, meta = readback(client, target, body)
    if state == "same":
        # Recover a Writer ACK lost after the inbox commit. CAS the exact bytes
        # back to the branch so the Writer sees the item again and can receipt it.
        status, _ = client.put(target, body, sha=meta.get("sha"))
        if status in (200, 201):
            if readback(client, target, body)[0] == "same":
                return "redelivered_missing_writer_receipt"
        elif classify(status) in ("conflict", "uncertain"):
            if readback(client, target, body)[0] == "same":
                return "redelivered_missing_writer_receipt"
        elif classify(status) == "terminal":
            raise TerminalTransportError(f"{target}: redelivery denied/invalid HTTP {status}")
        else:
            raise RelayError(f"{target}: receipt recovery unresolved HTTP {status}")
        raise RelayError(f"{target}: receipt recovery unresolved HTTP {status}")

    for attempt in range(1, max_attempts + 1):
        try:
            status, _ = client.put(target, body)
        except Exception as exc:
            status = 0
            write_error = type(exc).__name__
        else:
            write_error = ""
        if status in (200, 201):
            if readback(client, target, body)[0] == "same":
                return "relayed"
        elif classify(status) == "terminal":
            raise TerminalTransportError(f"{target}: write denied/invalid HTTP {status}")
        elif classify(status) in ("conflict", "uncertain"):
            try:
                recovered, _ = readback(client, target, body)
            except ReadFailure:
                raise
            if recovered == "same":
                return "recovered_after_uncertain_write"
            # A successful 404 read proves absence; only then is retry safe.
        else:
            raise RelayError(f"{target}: unexpected HTTP {status}")
        if attempt < max_attempts:
            sleep(min(2 ** (attempt - 1), 8))
        elif write_error:
            raise RelayError(f"{target}: delivery unresolved after {max_attempts} attempts ({write_error})")
    raise RelayError(f"{target}: delivery unresolved after {max_attempts} attempts")


def _request_identity(data, path):
    raw_id = data.get("stable_id") or Path(path).stem
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise StableIdValidationError(f"{path}: stable_id must be a non-empty string")
    if len(raw_id) > 512 or any(ord(char) < 32 or ord(char) == 127 for char in raw_id):
        raise StableIdValidationError(f"{path}: stable_id exceeds limits or contains control characters")
    normalised = re.sub(r"[^a-z0-9-]+", "-", raw_id.lower()).strip("-")
    if not normalised:
        raise StableIdValidationError(f"{path}: stable_id has no usable legacy identity characters")
    # Keep the established target mapping for persisted IDs. Preflight below
    # detects any two source identities that the historical 60-char mapping
    # would otherwise silently collapse.
    return raw_id, normalised[:60]


def target_for_stable_id(raw_id, path="<request>"):
    _, stable = _request_identity({"stable_id": raw_id}, path)
    return f"inbox/scheduled-{stable}.json"


def load_request(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("request must be a JSON object")
    envelope = data["envelope"] if isinstance(data.get("envelope"), dict) else data
    if not isinstance(envelope.get("kind"), str) or "payload" not in envelope:
        raise ValueError("invalid envelope")
    raw_id, stable = _request_identity(data, path)
    del raw_id  # the validated source identity is used by the collision preflight
    body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    return f"inbox/scheduled-{stable}.json", body


def validate_stable_id_collisions(paths):
    identities_by_target = {}
    for path in paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            raw_id, stable = _request_identity(data, path)
        except (OSError, UnicodeError, json.JSONDecodeError, StableIdValidationError):
            # A malformed unrelated legacy file should not block another push;
            # load_request fails closed if that file itself is selected.
            continue
        target = f"inbox/scheduled-{stable}.json"
        previous = identities_by_target.get(target)
        if previous is not None and previous != raw_id:
            raise StableIdConflict(f"{target}: distinct stable_id values collapse to the same destination")
        identities_by_target[target] = raw_id


def all_request_paths():
    return [path.as_posix() for path in Path(".").glob("**/nexo_persist/requests/*.json")]


def collect_changed_paths(event=None, before=None, event_sha=None):
    event = event if event is not None else os.environ.get("EVENT", "")
    before = before if before is not None else (os.environ.get("BEFORE", "") or "0")
    event_sha = event_sha if event_sha is not None else os.environ.get("GITHUB_SHA", "")
    if event == "push" and not re.fullmatch(r"0+", before):
        if not event_sha:
            raise RelayError("GITHUB_SHA is required to read the push's pinned request candidates")
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=AM", before, event_sha],
            capture_output=True,
            text=True,
            check=True,
        )
        changed = result.stdout.split()
    else:
        changed = all_request_paths()
    if any(Path(path).name.startswith("replay-all") for path in changed):
        changed = all_request_paths()
    return [
        path
        for path in changed
        if REQUEST_PATH_RE.search(path) and not Path(path).name.startswith("replay-all")
    ]


def main():
    changed = collect_changed_paths()
    validate_stable_id_collisions(all_request_paths())
    client = GitHubContents(os.environ["GITHUB_REPOSITORY"])
    receipts = WriterReceipts.load(
        repo=os.environ.get("WRITER_RECEIPTS_REPO", "byDenoso/Pantheon")
    )
    verified = failures = 0
    for path in changed:
        try:
            target, body = load_request(path)
            result = relay_one(client, receipts, target, body)
            print(f"{target}: {result}")
            verified += 1
        except Exception as exc:
            print(f"::error::{path}: {type(exc).__name__}: {exc}")
            failures += 1
    print(f"verified={verified} failed={failures}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
