"""Read and write the stable live Tower object on Google Drive.

This is the only code path that writes operational truth. The loop is:

    lock -> download (base) -> mutate locally -> re-read Drive head
    -> refuse if head moved -> upload same file id -> download readback
    -> compare state_fingerprint

Drive v3 has no revision precondition on ``files.update``, so the compare-and-
swap is emulated: a process-wide lock serialises local writers and the head
re-read right before upload catches any foreign writer. With a single writer
role the remaining window is the upload itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .live_tower import LIVE_TOWER_FILE_ID, read_live_tower_bytes

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
_API = "https://www.googleapis.com/drive/v3/files"
_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_META_FIELDS = "id,name,headRevisionId,md5Checksum,modifiedTime,size,mimeType"


class TowerConflict(RuntimeError):
    """The Drive head moved between base read and write."""


class TowerReadbackMismatch(RuntimeError):
    """Drive returned different state than what was written."""


def _tower_cache_path(md5: str) -> Path:
    return nexo_home() / "cache" / f"tower-{md5}.json"


def nexo_home() -> Path:
    return Path(os.environ.get("NEXO_HOME") or Path.home() / ".nexo")


def load_credentials(*, write: bool) -> Any:
    """Credentials from env or ``$NEXO_HOME/google-credentials.json``.

    Accepted shapes: a service-account key (``type: service_account``) or an
    authorized-user token (``client_id``, ``client_secret``, ``refresh_token``).
    Env ``GOOGLE_SERVICE_ACCOUNT_JSON`` may hold the JSON itself or a path.
    """
    scopes = [DRIVE_SCOPE if write else READONLY_SCOPE]
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    info: dict[str, Any] | None = None
    if raw:
        info = json.loads(raw if raw.startswith("{") else Path(raw).read_text(encoding="utf-8"))
    elif os.environ.get("GOOGLE_REFRESH_TOKEN"):
        info = {
            "type": "authorized_user",
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
        }
    else:
        path = nexo_home() / "google-credentials.json"
        if path.is_file():
            info = json.loads(path.read_text(encoding="utf-8"))
    if info is None:
        raise RuntimeError(
            "NEXO_DRIVE_CREDENTIAL_MISSING: set GOOGLE_SERVICE_ACCOUNT_JSON, "
            "GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN, or create "
            f"{nexo_home() / 'google-credentials.json'}"
        )
    if info.get("type") == "service_account":
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_info(info, scopes=scopes)
    from google.oauth2.credentials import Credentials

    return Credentials(
        None,
        refresh_token=info["refresh_token"],
        token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=info["client_id"],
        client_secret=info["client_secret"],
        scopes=scopes,
    )


@dataclass(frozen=True)
class DriveHead:
    head_revision_id: str | None
    md5: str | None
    modified_time: str | None
    size: int | None

    @classmethod
    def from_meta(cls, meta: dict[str, Any]) -> "DriveHead":
        size = meta.get("size")
        return cls(meta.get("headRevisionId"), meta.get("md5Checksum"), meta.get("modifiedTime"), int(size) if size else None)

    def same_content(self, other: "DriveHead") -> bool:
        if self.md5 and other.md5:
            return self.md5 == other.md5
        return self.head_revision_id == other.head_revision_id


class DriveTower:
    """Thin client for the one live Tower file. ``session`` is injectable for tests."""

    def __init__(self, file_id: str = LIVE_TOWER_FILE_ID, *, session: Any = None, write: bool = False) -> None:
        self.file_id = file_id
        self.write = write
        if session is None:
            from google.auth.transport.requests import AuthorizedSession

            session = AuthorizedSession(load_credentials(write=write))
        self.session = session

    def _check(self, response: Any, action: str) -> Any:
        if response.status_code >= 400:
            raise RuntimeError(f"DRIVE_{action}_FAILED:{response.status_code}:{response.text[:300]}")
        return response

    def head(self) -> DriveHead:
        response = self._check(
            self.session.get(f"{_API}/{self.file_id}", params={"fields": _META_FIELDS, "supportsAllDrives": "true"}, timeout=60),
            "HEAD",
        )
        return DriveHead.from_meta(response.json())

    def download(self, *, cache: bool | None = None) -> tuple[bytes, DriveHead]:
        """Live Tower bytes. Readers reuse a local copy whose md5 matches the Drive head.

        The cache is content-addressed (Drive md5Checksum, re-verified on read), so a
        stale copy can never be returned; writers (write=True) always fetch fresh bytes.
        """
        head = self.head()
        use_cache = (not self.write) if cache is None else cache
        cached = _tower_cache_path(head.md5) if use_cache and head.md5 else None
        if cached and cached.is_file():
            raw = cached.read_bytes()
            if hashlib.md5(raw).hexdigest() == head.md5:
                return raw, head
        response = self._check(
            self.session.get(f"{_API}/{self.file_id}", params={"alt": "media", "supportsAllDrives": "true"}, timeout=300),
            "DOWNLOAD",
        )
        raw = response.content
        if cached and hashlib.md5(raw).hexdigest() == head.md5:
            try:
                cached.parent.mkdir(parents=True, exist_ok=True)
                for old in cached.parent.glob("tower-*.json"):
                    old.unlink(missing_ok=True)  # keep only the current revision
                cached.write_bytes(raw)
            except OSError:
                pass  # cache is an optimisation only
        return raw, head

    def read(self) -> tuple[dict[str, Any], DriveHead]:
        raw, head = self.download()
        return read_live_tower_bytes(raw), head

    def upload(self, raw: bytes) -> DriveHead:
        response = self._check(
            self.session.patch(
                f"{_UPLOAD}/{self.file_id}",
                params={"uploadType": "media", "fields": _META_FIELDS, "supportsAllDrives": "true"},
                data=raw,
                headers={"Content-Type": "application/json"},
                timeout=300,
            ),
            "UPLOAD",
        )
        return DriveHead.from_meta(response.json())

    def compare_and_swap(self, base: DriveHead, raw: bytes) -> dict[str, Any]:
        """Upload ``raw`` only if Drive still holds ``base``; then read back."""
        expected = json.loads(raw.decode("utf-8"))["state_fingerprint"]
        current = self.head()
        if not current.same_content(base):
            raise TowerConflict(
                f"TOWER_HEAD_MOVED base={base.head_revision_id} current={current.head_revision_id}"
            )
        written = self.upload(raw)
        readback, head = self.read()
        if readback.get("state_fingerprint") != expected:
            raise TowerReadbackMismatch(
                f"TOWER_READBACK_MISMATCH expected={expected} got={readback.get('state_fingerprint')}"
            )
        return {
            "status": "PASS",
            "file_id": self.file_id,
            "state_fingerprint": expected,
            "head_revision_id": head.head_revision_id or written.head_revision_id,
            "readback": "PASS",
        }


class DriveInbox:
    """Create-only proposal inbox (ChatGPT -> Tower writer), never the Tower itself.

    Writers outside the single Tower writer create one new file per message in
    ``NEXO_INBOX``; the writer applies it and moves it to ``NEXO_INBOX/processed``.
    """

    FOLDER = "application/vnd.google-apps.folder"

    def __init__(self, name: str = "NEXO_INBOX", *, session: Any = None, write: bool = False) -> None:
        if session is None:
            from google.auth.transport.requests import AuthorizedSession

            session = AuthorizedSession(load_credentials(write=write))
        self.session = session
        self.name = name

    def _query(self, q: str) -> list[dict[str, Any]]:
        response = self.session.get(
            _API,
            params={"q": q, "fields": "files(id,name,createdTime,parents)", "orderBy": "createdTime", "pageSize": 200,
                    "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"},
            timeout=60,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"DRIVE_LIST_FAILED:{response.status_code}:{response.text[:300]}")
        return response.json().get("files", [])

    def _folder(self, name: str, parent: str | None = None) -> str | None:
        q = f"name = '{name}' and mimeType = '{self.FOLDER}' and trashed = false"
        if parent:
            q += f" and '{parent}' in parents"
        found = self._query(q)
        return found[0]["id"] if found else None

    def pending(self) -> list[dict[str, Any]]:
        inbox = self._folder(self.name)
        if not inbox:
            return []
        items = self._query(f"'{inbox}' in parents and mimeType != '{self.FOLDER}' and trashed = false")
        for item in items:
            raw = self.session.get(f"{_API}/{item['id']}", params={"alt": "media"}, timeout=60)
            try:
                item["payload"] = json.loads(raw.content.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                item["payload"] = None
        return items

    def mark_processed(self, file_id: str) -> None:
        inbox = self._folder(self.name)
        processed = self._folder("processed", inbox)
        if not processed:
            created = self.session.post(
                _API, json={"name": "processed", "mimeType": self.FOLDER, "parents": [inbox]}, timeout=60
            )
            processed = created.json()["id"]
        self.session.patch(
            f"{_API}/{file_id}", params={"addParents": processed, "removeParents": inbox}, json={}, timeout=60
        )


@contextmanager
def writer_lock(name: str = "tower.lock", *, stale_after: float = 3 * 3600) -> Iterator[Path]:
    """Exclusive local lock so overlapping automations never write concurrently."""
    home = nexo_home()
    home.mkdir(parents=True, exist_ok=True)
    path = home / name
    if path.exists() and time.time() - path.stat().st_mtime > stale_after:
        path.unlink(missing_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise TowerConflict(f"NEXO_WRITER_BUSY:{path}") from exc
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "at": time.time()}).encode())
        os.close(fd)
        yield path
    finally:
        path.unlink(missing_ok=True)
