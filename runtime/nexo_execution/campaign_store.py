"""Direct campaign files, without a global state writer.

A durable upload intent pins a Drive-generated ID BEFORE sending bytes. Retrying
that intent is idempotent. The local journal lock is not a distributed lock:
independent hosts must share an approved execution serializer, not rely on Drive
names or list-before-create for exclusion. Reading preserves conflicting events
as errors instead of choosing whichever listing happened to return last.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA = "NEXO_CAMPAIGN_EVENT_V1"
API = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"
DOC = "application/vnd.google-apps.document"
MAX_BYTES = 5 * 1024 * 1024
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")
DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{1,200}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
ROLES = {
    "METHOD": {"CIENTISTA"}, "ASSIGNMENT": {"CIENTISTA", "MAESTRO"},
    "RUN": {"EXECUTOR"}, "RESULT": {"EXECUTOR"},
    "REVIEW": {"CRITICO"}, "MANUSCRIPT": {"EDITOR"},
    "SYNTHESIS": {"EDITOR", "SINTETIZADOR"},
    "PATCH": {"EXECUTOR", "ENGENHEIRO"},
    "CHECKPOINT": {"CIENTISTA", "EXECUTOR", "CRITICO", "EDITOR", "MAESTRO", "ENGENHEIRO", "SINTETIZADOR"},
    "LOG": {"CIENTISTA", "EXECUTOR", "CRITICO", "EDITOR", "MAESTRO", "ENGENHEIRO", "SINTETIZADOR"},
}
META = "id,name,mimeType,parents,trashed,version,md5Checksum,size,modifiedTime,appProperties"


class CampaignError(RuntimeError):
    """Bounded, credential-free error code."""


def require(value: Any, code: str) -> None:
    if not value:
        raise CampaignError(code)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_safe(value: Any, depth: int = 0) -> None:
    require(depth <= 40, "EVENT_TOO_DEEP")
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str) and key not in {"__proto__", "prototype", "constructor"}, "EVENT_KEY_INVALID")
            _json_safe(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _json_safe(item, depth + 1)
    elif isinstance(value, bool) or value is None or isinstance(value, str):
        return
    elif isinstance(value, int):
        require(abs(value) <= 9007199254740991, "UNSAFE_JSON_INTEGER")
    elif isinstance(value, float):
        require(math.isfinite(value), "NONFINITE_JSON_NUMBER")
        require(not value.is_integer() or abs(value) <= 9007199254740991, "UNSAFE_JSON_INTEGER")
    else:
        raise CampaignError("NON_JSON_VALUE")


def json_bytes(value: Any) -> bytes:
    _json_safe(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def event_identity(event: dict) -> str:
    fields = [event[k] for k in ("campaign_id", "role", "kind", "entity_id")]
    fields.append(str(event["version"]))
    return "EV-" + digest("\n".join(fields).encode("utf-8"))


def validate_event(event: Any, campaign_id: str | None = None) -> dict:
    require(isinstance(event, dict) and event.get("schema") == SCHEMA, "EVENT_SCHEMA_UNSUPPORTED")
    _json_safe(event)
    for key in ("campaign_id", "entity_id", "actor_id"):
        require(isinstance(event.get(key), str) and ID.fullmatch(event[key]), "EVENT_ID_INVALID")
    require(campaign_id is None or event["campaign_id"] == campaign_id, "CAMPAIGN_ID_MISMATCH")
    require(type(event.get("version")) is int and 1 <= event["version"] <= 9007199254740991, "EVENT_VERSION_INVALID")
    require(event.get("kind") in ROLES and event.get("role") in ROLES[event["kind"]], "EVENT_ROLE_KIND_MISMATCH")
    require(event.get("access") == "PRIVATE" and event.get("atlas_scope") in {"PRIVATE", "EXCLUDED"}, "EVENT_ACCESS_INVALID")
    require(isinstance(event.get("data"), dict), "EVENT_DATA_INVALID")
    try:
        date = event["timestamp_utc"]
        require(isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", date), "EVENT_TIMESTAMP_INVALID")
        datetime.fromisoformat(date.replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError):
        raise CampaignError("EVENT_TIMESTAMP_INVALID") from None
    require(event.get("event_id") == event_identity(event), "EVENT_IDENTITY_MISMATCH")
    return event


def make_event(*, campaign_id: str, entity_id: str, kind: str, role: str, actor_id: str,
               data: dict, version: int = 1, atlas_scope: str = "EXCLUDED", timestamp_utc: str | None = None) -> dict:
    event = dict(schema=SCHEMA, campaign_id=campaign_id, entity_id=entity_id, kind=kind,
                 role=role, actor_id=actor_id, version=version, access="PRIVATE", atlas_scope=atlas_scope,
                 timestamp_utc=timestamp_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), data=data)
    event["event_id"] = event_identity(event)
    return validate_event(event)


def parse_event(raw: bytes, campaign_id: str | None = None) -> dict:
    require(len(raw) <= MAX_BYTES, "EVENT_TOO_LARGE")
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError):
        raise CampaignError("EVENT_JSON_INVALID") from None
    return validate_event(value, campaign_id)


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def atomic_json(path: Path, value: dict) -> None:
    """Private local checkpoint. Never a source-side or distributed transaction."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not path.is_symlink(), "JOURNAL_SYMLINK_DENIED")
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".nexo-", delete=False) as stream:
            name = stream.name
            os.chmod(name, 0o600)
            stream.write(json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        name = None
        if os.name == "posix":
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


@contextmanager
def local_lock(path: Path) -> Iterator[None]:
    """OS-held lock, released on exit/crash; never delete its inode or steal by TTL."""
    require(os.name == "posix", "LOCAL_LOCK_PLATFORM_UNQUALIFIED")
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CampaignError("LOCAL_WORK_ALREADY_RUNNING") from None
        yield
    finally:
        os.close(fd)


class DriveCampaignStore:
    def __init__(self, root_id: str, *, session, write: bool = False, sleep=time.sleep):
        """Borrow the caller's existing authorized HTTP session.

        This client neither reads credentials nor imports the legacy Tower API.
        The caller owns session lifetime and must close it after use, including
        exceptions. Use an existing AuthorizedSession in its context manager.
        The write flag narrows this client's behavior; it does not grant OAuth
        scope or permissions that the supplied identity does not already hold.
        """
        require(isinstance(root_id, str) and DRIVE_ID.fullmatch(root_id), "ROOT_ID_INVALID")
        require(callable(getattr(session, "request", None)), "AUTHORIZED_SESSION_REQUIRED")
        self.root_id, self.write, self.sleep = root_id, write, sleep
        self.session = session

    def _call(self, method: str, url: str, *, accepted=(200,), **kwargs):
        for attempt in range(3):
            response = None
            try:
                response = self.session.request(method, url, timeout=30, allow_redirects=False, **kwargs)
            except Exception:
                if attempt == 2:
                    raise CampaignError("DRIVE_TRANSPORT_UNCERTAIN") from None
            else:
                code = response.status_code
                if code in accepted:
                    return response
                if code in {401, 403}:
                    response.close()
                    raise CampaignError(f"DRIVE_AUTH_{code}")
                retry = code in {408, 425, 429} or 500 <= code <= 599
                if not retry or attempt == 2:
                    response.close()
                    raise CampaignError(f"DRIVE_HTTP_{code}")
            delay = 2 ** attempt
            if response is not None:
                header = response.headers.get("Retry-After")
                response.close()
                if header:
                    try:
                        delay = max(delay, float(header))
                    except (TypeError, ValueError):
                        raise CampaignError("DRIVE_RETRY_DEFERRED") from None
                    if not math.isfinite(delay) or delay > 10:
                        raise CampaignError("DRIVE_RETRY_DEFERRED")
            self.sleep(delay)
        raise CampaignError("DRIVE_TRANSPORT_UNCERTAIN")

    @staticmethod
    def _json(response):
        try:
            return response.json()
        finally:
            response.close()

    def metadata(self, file_id: str, *, allow_missing=False):
        require(isinstance(file_id, str) and DRIVE_ID.fullmatch(file_id), "DRIVE_ID_INVALID")
        r = self._call("GET", f"{API}/{file_id}", accepted=(200, 404) if allow_missing else (200,),
                       params={"fields": META, "supportsAllDrives": "true"})
        if r.status_code == 404:
            r.close()
            return None
        meta = self._json(r)
        require(meta.get("id") == file_id and meta.get("trashed") is False, "FILE_IDENTITY_INVALID")
        return meta

    def campaign_folder(self, folder_id: str, campaign_id: str):
        require(isinstance(campaign_id, str) and ID.fullmatch(campaign_id), "CAMPAIGN_ID_INVALID")
        root = self.metadata(self.root_id)
        require(root.get("mimeType") == FOLDER, "ROOT_NOT_FOLDER")
        folder = self.metadata(folder_id)
        require(folder.get("mimeType") == FOLDER and folder.get("name") == campaign_id
                and folder.get("parents") == [self.root_id], "CAMPAIGN_FOLDER_MISMATCH")
        return folder

    def list_files(self, folder_id: str, campaign_id: str, *, max_files=500):
        require(type(max_files) is int and 1 <= max_files <= 500, "CAMPAIGN_LIST_LIMIT_INVALID")
        self.campaign_folder(folder_id, campaign_id)
        items, seen, token = [], set(), None
        for _ in range(20):
            params = {"q": f"'{folder_id}' in parents and trashed = false", "pageSize": min(max_files, 100),
                      "fields": f"nextPageToken,incompleteSearch,files({META})", "supportsAllDrives": "true",
                      "includeItemsFromAllDrives": "true", "orderBy": "name"}
            if token:
                params["pageToken"] = token
            page = self._json(self._call("GET", API, params=params))
            require(not page.get("incompleteSearch"), "CAMPAIGN_LIST_INCOMPLETE")
            require(isinstance(page.get("files"), list), "CAMPAIGN_LIST_INVALID")
            items.extend(page["files"])
            require(len(items) <= max_files, "CAMPAIGN_LIST_LIMIT")
            token = page.get("nextPageToken")
            if not token:
                ids = [item.get("id") for item in items]
                require(len(set(ids)) == len(ids), "CAMPAIGN_LIST_DUPLICATE")
                return items
            require(token not in seen, "CAMPAIGN_PAGE_LOOP")
            seen.add(token)
        raise CampaignError("CAMPAIGN_LIST_LIMIT")

    def read_bytes(self, file_id: str, *, max_bytes=MAX_BYTES):
        response = self._call("GET", f"{API}/{file_id}", params={"alt": "media", "supportsAllDrives": "true"}, stream=True)
        parts, size = [], 0
        try:
            for part in response.iter_content(65536):
                size += len(part)
                require(size <= max_bytes, "ARTIFACT_TOO_LARGE")
                parts.append(part)
            return b"".join(parts)
        finally:
            response.close()

    def read_event(self, file_id: str, folder_id: str, campaign_id: str):
        self.campaign_folder(folder_id, campaign_id)
        before = self.metadata(file_id)
        require(before.get("parents") == [folder_id], "EVENT_PARENT_MISMATCH")
        if before["mimeType"] == DOC:
            response = self._call("GET", f"{API}/{file_id}/export", params={"mimeType": "text/plain"}, stream=True)
            try:
                pieces, size = [], 0
                for piece in response.iter_content(65536):
                    size += len(piece)
                    require(size <= MAX_BYTES, "EVENT_TOO_LARGE")
                    pieces.append(piece)
                raw = b"".join(pieces)
            finally:
                response.close()
        else:
            require(before["mimeType"] == "application/json", "EVENT_MIME_UNSUPPORTED")
            raw = self.read_bytes(file_id)
            require(before.get("md5Checksum") == hashlib.md5(raw).hexdigest(), "EVENT_BYTES_MISMATCH")
        after = self.metadata(file_id)
        require(before == after, "EVENT_READ_RACE")
        return {"event": parse_event(raw, campaign_id), "file_id": file_id, "version": before["version"],
                "mime_type": before["mimeType"], "sha256": digest(raw)}

    def publish_event(self, event: dict, folder_id: str, journal_directory: Path):
        validate_event(event)
        return self.publish_bytes(raw=json_bytes(event), folder_id=folder_id, campaign_id=event["campaign_id"],
                                  name=f"NEXO_EVENT__{event['event_id']}.json", mime_type="application/json",
                                  intent_key=event["event_id"], journal_directory=journal_directory, event_id=event["event_id"])

    def publish_bytes(self, *, raw: bytes, folder_id: str, campaign_id: str, name: str,
                      mime_type: str, intent_key: str, journal_directory: Path, event_id: str | None = None):
        require(self.write, "WRITE_NOT_ENABLED")
        require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "USE_EXISTING_RESUMABLE_UPLOAD")
        require(isinstance(name, str) and 0 < len(name) <= 220 and not re.search(r"[\x00-\x1f/\\]", name), "ARTIFACT_NAME_INVALID")
        require(re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", mime_type) and not mime_type.startswith("application/vnd.google-apps"), "RAW_MIME_REQUIRED")
        require(isinstance(intent_key, str) and 0 < len(intent_key) <= 256, "INTENT_KEY_INVALID")
        require(not Path(journal_directory).is_symlink(), "JOURNAL_SYMLINK_DENIED")
        journal = Path(journal_directory) / (digest(intent_key.encode()) + ".json")
        binding = dict(root_id=self.root_id, folder_id=folder_id, campaign_id=campaign_id,
                       name=name, mime_type=mime_type, sha256=digest(raw), size=len(raw), intent_key=intent_key)
        with local_lock(journal.with_suffix(".lock")):
            self.campaign_folder(folder_id, campaign_id)
            require(not journal.is_symlink(), "JOURNAL_SYMLINK_DENIED")
            if journal.exists():
                try:
                    intent = json.loads(journal.read_bytes())
                except (ValueError, OSError):
                    raise CampaignError("UPLOAD_INTENT_CORRUPT") from None
                require(intent.get("binding") == binding, "UPLOAD_INTENT_CONFLICT")
            else:
                generated = self._json(self._call("GET", API + "/generateIds", params={"count": 1, "space": "drive", "type": "files"}))
                require(isinstance(generated.get("ids"), list) and len(generated["ids"]) == 1, "GENERATED_ID_INVALID")
                intent = {"binding": binding, "file_id": generated["ids"][0], "state": "PREPARED"}
                require(DRIVE_ID.fullmatch(intent["file_id"]), "GENERATED_ID_INVALID")
                atomic_json(journal, intent)
            file_id = intent["file_id"]
            meta = self.metadata(file_id, allow_missing=True)
            if meta is None:
                metadata = {"id": file_id, "name": name, "mimeType": mime_type, "parents": [folder_id]}
                if event_id:
                    metadata["appProperties"] = {"nexo_event_id": event_id, "nexo_campaign_id": campaign_id}
                boundary = "nexo_" + digest(raw)[:32]
                payload = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
                           + json_bytes(metadata) + f"\r\n--{boundary}\r\nContent-Type: {mime_type}\r\n\r\n".encode()
                           + raw + f"\r\n--{boundary}--\r\n".encode())
                # Every retry retains the pre-generated file ID, including after a lost response.
                response = self._call("POST", UPLOAD, accepted=(200, 201, 409),
                                      params={"uploadType": "multipart", "supportsAllDrives": "true"},
                                      headers={"Content-Type": f"multipart/related; boundary={boundary}"}, data=payload)
                response.close()
            before = self.metadata(file_id)
            require(before.get("name") == name and before.get("mimeType") == mime_type
                    and before.get("parents") == [folder_id], "UPLOAD_READBACK_IDENTITY_MISMATCH")
            actual = self.read_bytes(file_id)
            after = self.metadata(file_id)
            require(before == after and digest(actual) == binding["sha256"]
                    and before.get("md5Checksum") == hashlib.md5(actual).hexdigest(), "UPLOAD_READBACK_BYTES_MISMATCH")
            self.campaign_folder(folder_id, campaign_id)
            receipt = {"state": "PERSISTED_VERIFIED", "file_id": file_id, "folder_id": folder_id,
                       "mime_type": mime_type, "sha256": digest(actual), "size": len(actual),
                       "version": before.get("version"), "intent_key": intent_key}
            atomic_json(journal, {**intent, "state": "VERIFIED", "receipt": receipt})
            return receipt
