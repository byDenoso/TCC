"""Portable, bounded evidence packages and publish-after-readback native Docs.

No credential discovery, Tower write, sharing change, or scheduler operation.
The producer supplies its authorized transport and durable checkpoint callback.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

CONTRACT = "NEXO_ARTIFACT_PACKAGE_V1"
DOC_MIME = "application/vnd.google-apps.document"
MAX_BYTES = 128 * 1024
MAX_DOCUMENT_BYTES = 256 * 1024
CAMPAIGNS_ID = "1Rxu3GJ1hHlvVBbAkBRp4e_5F7fTIOsNE"
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\Z")
_DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{1,256}\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
PRODUCERS = frozenset({"MAESTRO", "CIENTISTA", "ENGENHEIRO", "EXECUTOR",
                       "CRITICO", "SINTETIZADOR", "EDITOR"})


class PackageError(ValueError):
    """A safe contract code, never private content."""


class PackageUnavailable(RuntimeError):
    """Retry the same delivery when its authorized evidence source recovers."""


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical(value: dict) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError):
        raise PackageError("PACKAGE_JSON_INVALID") from None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackageError("PACKAGE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def document_bytes(raw: bytes) -> bytes:
    """Only native Docs' UTF-8 BOM and terminal paragraph are transport framing."""
    if not isinstance(raw, bytes) or len(raw) > MAX_DOCUMENT_BYTES + 5:
        raise PackageError("DOCUMENT_TOO_LARGE")
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    if raw.endswith(b"\r\n"):
        raw = raw[:-2]
    elif raw.endswith(b"\n"):
        raw = raw[:-1]
    return raw


def parse_package(raw: bytes) -> dict:
    raw = document_bytes(raw)
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise PackageError("DOCUMENT_TOO_LARGE")
    try:
        package = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(PackageError("PACKAGE_NONFINITE_JSON")))
    except (UnicodeError, ValueError):
        raise PackageError("PACKAGE_JSON_INVALID") from None
    validate_package(package)
    return package


def validate_package(package: dict) -> dict:
    fields = {"contract", "artifact_id", "campaign_id", "created_at", "producer_role", "provenance", "files"}
    if type(package) is not dict or set(package) != fields or package.get("contract") != CONTRACT:
        raise PackageError("PACKAGE_FIELDS_INVALID")
    if any(not isinstance(package[k], str) or not _TOKEN.fullmatch(package[k])
           for k in ("artifact_id", "campaign_id")):
        raise PackageError("PACKAGE_ID_INVALID")
    if not isinstance(package["producer_role"], str) or package["producer_role"] not in PRODUCERS:
        raise PackageError("PACKAGE_PRODUCER_INVALID")
    try:
        when = datetime.fromisoformat(package["created_at"].replace("Z", "+00:00"))
        if not package["created_at"].endswith(("Z", "+00:00")) or when.utcoffset().total_seconds() != 0:
            raise ValueError()
    except (AttributeError, TypeError, ValueError):
        raise PackageError("PACKAGE_UTC_REQUIRED") from None
    if not isinstance(package["provenance"], dict) or not package["provenance"]:
        raise PackageError("PACKAGE_PROVENANCE_REQUIRED")
    if not isinstance(package["files"], list) or not package["files"]:
        raise PackageError("PACKAGE_FILES_REQUIRED")
    total, names = 0, set()
    for entry in package["files"]:
        if type(entry) is not dict or set(entry) != {"name", "mime_type", "size_bytes", "sha256", "content_b64"}:
            raise PackageError("PACKAGE_FILE_FIELDS_INVALID")
        name = entry["name"]
        # Flat portable filenames only. Also reject Windows aliases and devices.
        if (not isinstance(name, str) or not _TOKEN.fullmatch(name) or name.endswith(".")
                or name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *("COM"+str(i) for i in range(1, 10)), *("LPT"+str(i) for i in range(1, 10))}
                or name.casefold() in names):
            raise PackageError("PACKAGE_FILENAME_INVALID")
        names.add(name.casefold())
        if (not isinstance(entry["mime_type"], str)
                or not re.fullmatch(r"[a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+", entry["mime_type"])
                or type(entry["size_bytes"]) is not int or not 0 < entry["size_bytes"] <= MAX_BYTES
                or not isinstance(entry["sha256"], str) or not _HASH.fullmatch(entry["sha256"])
                or not isinstance(entry["content_b64"], str)
                or len(entry["content_b64"]) > 4 * ((MAX_BYTES + 2) // 3)):
            raise PackageError("PACKAGE_FILE_INVALID")
        try:
            content = base64.b64decode(entry["content_b64"], validate=True)
        except ValueError:
            raise PackageError("PACKAGE_ENCODING_INVALID") from None
        if (base64.b64encode(content).decode("ascii") != entry["content_b64"]
                or len(content) != entry["size_bytes"] or digest(content) != entry["sha256"]):
            raise PackageError("PACKAGE_FILE_HASH_MISMATCH")
        total += len(content)
    if total > MAX_BYTES or len(canonical(package)) > MAX_DOCUMENT_BYTES:
        raise PackageError("PACKAGE_TOO_LARGE")
    return package


def pack(*, artifact_id: str, campaign_id: str, created_at: str, producer_role: str,
         provenance: dict, files: list[dict]) -> dict:
    package = dict(contract=CONTRACT, artifact_id=artifact_id, campaign_id=campaign_id,
                   created_at=created_at, producer_role=producer_role, provenance=provenance,
                   files=[dict(name=f["name"], mime_type=f["mime_type"], size_bytes=len(f["content"]),
                               sha256=digest(f["content"]), content_b64=base64.b64encode(f["content"]).decode("ascii"))
                          for f in files])
    return validate_package(package)


def prepare_document(raw: bytes, *, stable_id: str, folder_id: str) -> dict:
    if not isinstance(stable_id, str) or not _TOKEN.fullmatch(stable_id):
        raise PackageError("DOCUMENT_STABLE_ID_INVALID")
    if not isinstance(folder_id, str) or not _DRIVE_ID.fullmatch(folder_id):
        raise PackageError("DOCUMENT_FOLDER_INVALID")
    if not raw or len(raw) > MAX_DOCUMENT_BYTES:
        raise PackageError("DOCUMENT_TOO_LARGE")
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise PackageError("DOCUMENT_UTF8_REQUIRED") from None
    return {"title": "nexo-doc-v1-" + stable_id, "text": text, "sha256": digest(raw), "folder_id": folder_id}


def publish_document(prepared: dict, transport, *, journal: dict) -> dict:
    """Port: lookup(title), create(title), read(id), fill(id,text,revision), move(id,folder), checkpoint(journal).

    lookup must be exhaustive across private staging, destination and processed.
    read returns text bytes, revision, mime_type, parent_ids, private_verified.
    Never repeat an ambiguous create/fill/move without first reconciling readback.
    """
    if type(journal) is not dict:
        raise PackageError("DURABLE_DELIVERY_JOURNAL_REQUIRED")
    identity = {key: prepared[key] for key in ("title", "sha256", "folder_id")}
    if journal and any(journal.get(key) != value for key, value in identity.items()):
        raise PackageError("DOCUMENT_IDENTITY_CONFLICT")
    if journal.get("stage") == "PERMISSION_DENIED":
        raise PermissionError("OPERATOR_REAUTHORIZATION_REQUIRED")
    def checkpoint(**values):
        journal.update({**identity, **values})
        transport.checkpoint(dict(journal))
    try:
        if transport.verify_destination(prepared["folder_id"]) is not True:
            raise PackageError("DOCUMENT_DESTINATION_UNVERIFIED")
        file_id = journal.get("file_id")
        if not file_id:
            found = transport.lookup(prepared["title"])
            if len(found) > 1:
                raise PackageError("DOCUMENT_DUPLICATES_REQUIRE_RECONCILIATION")
            if found:
                file_id = found[0]
            elif journal.get("stage") in {"CREATING", "OUTCOME_UNKNOWN"}:
                return {**journal, "stage": "OUTCOME_UNKNOWN"}
            else:
                checkpoint(stage="CREATING")
                file_id = transport.create(prepared["title"])
            checkpoint(file_id=file_id, stage="STAGING")
        read = transport.read(file_id)
        if (read.get("mime_type") != DOC_MIME or read.get("private_verified") is not True
                or read.get("title") != prepared["title"]):
            raise PackageError("DOCUMENT_PRIVATE_IDENTITY_UNVERIFIED")
        actual = document_bytes(read["raw"])
        expected = prepared["text"].encode("utf-8")
        if actual != expected:
            if actual or read.get("parent_ids") != [transport.staging_folder_id] or not read.get("revision"):
                raise PackageError("DOCUMENT_CONTENT_CONFLICT")
            checkpoint(stage="FILLING")
            transport.fill(file_id, prepared["text"], read["revision"])
            read = transport.read(file_id)
        if (document_bytes(read["raw"]) != expected or digest(expected) != prepared["sha256"]
                or read.get("mime_type") != DOC_MIME or read.get("private_verified") is not True):
            raise PackageError("DOCUMENT_READBACK_MISMATCH")
        from .inbox_client import INBOX_ID
        def published(readback):
            return (prepared["folder_id"] in readback.get("parent_ids", [])
                    or (prepared["folder_id"] == INBOX_ID and readback.get("verified_processed_parent") is True))
        if not published(read):
            checkpoint(stage="PUBLISHING")
            transport.move(file_id, prepared["folder_id"])
            read = transport.read(file_id)
        if (document_bytes(read["raw"]) != expected or read.get("private_verified") is not True
                or read.get("title") != prepared["title"] or read.get("mime_type") != DOC_MIME
                or not published(read)):
            raise PackageError("DOCUMENT_PUBLISH_READBACK_MISMATCH")
        checkpoint(stage="DELIVERED")
        return dict(journal)
    except (PermissionError,) as error:
        checkpoint(stage="PERMISSION_DENIED")
        raise error
    except Exception as error:
        from .drive_transport import TowerTransportError
        if isinstance(error, TowerTransportError) and error.retry_condition == "OPERATOR_REAUTHORIZATION":
            checkpoint(stage="PERMISSION_DENIED")
            raise
        if isinstance(error, (TimeoutError, TowerTransportError)):
            checkpoint(stage="OUTCOME_UNKNOWN")
            return dict(journal)
        raise


class NativeDocsTransport:
    """Reference adapter for an already-authorized Google user session.

    ChatGPT can perform the same operations with its native Drive/Docs tools.
    The adapter never loads a credential or grants access. Its checkpoint callback
    must save the journal outside the disposable execution environment.
    """
    def __init__(self, session, *, checkpoint, processed_folder_id: str | None = None):
        from .drive_transport import DriveInbox
        self.session, self.checkpoint = session, checkpoint
        self.inbox = DriveInbox(session=session)
        self.processed_folder_id = processed_folder_id
        self.staging_folder_id = self._metadata("root")["id"]

    def _request(self, method, url, *, action, **kwargs):
        from .drive_transport import DriveTower
        response = DriveTower._call(action, lambda: getattr(self.session, method)(url, timeout=60, **kwargs))
        return DriveTower._check(response, action)

    def _metadata(self, file_id):
        if not isinstance(file_id, str) or not _DRIVE_ID.fullmatch(file_id):
            raise PackageError("DOCUMENT_ID_INVALID")
        meta = self._request("get", "https://www.googleapis.com/drive/v3/files/" + file_id,
                             action="DOC_METADATA", params={"fields": "id,name,mimeType,parents,trashed,permissions(type,role)",
                                                            "supportsAllDrives": "true"}).json()
        if (meta.get("trashed") is not False or (file_id != "root" and meta.get("id") != file_id)
                or not meta.get("permissions") or any(p.get("type") != "user" for p in meta["permissions"])):
            raise PackageError("DOCUMENT_PRIVATE_IDENTITY_UNVERIFIED")
        return meta

    def verify_destination(self, folder_id):
        return self._metadata(folder_id).get("mimeType") == self.inbox.FOLDER

    def lookup(self, title):
        query = "name = '" + self.inbox._quote(title) + "' and trashed = false"
        return [entry["id"] for entry in self.inbox._query(query)]

    def create(self, title):
        result = self._request("post", "https://docs.googleapis.com/v1/documents", action="DOC_CREATE",
                               json={"title": title}).json()
        return result["documentId"]

    def read(self, file_id):
        meta = self._metadata(file_id)
        if meta.get("mimeType") != DOC_MIME:
            raise PackageError("DOCUMENT_MIME_INVALID")
        document = self._request("get", "https://docs.googleapis.com/v1/documents/" + file_id,
                                 action="DOC_READ", params={"includeTabsContent": "true"}).json()
        if document.get("documentId") != file_id or not document.get("revisionId"):
            raise PackageError("DOCUMENT_REVISION_IDENTITY_UNVERIFIED")
        tabs = document.get("tabs")
        if not isinstance(tabs, list) or len(tabs) != 1 or tabs[0].get("childTabs"):
            raise PackageError("DOCUMENT_SINGLE_TAB_REQUIRED")
        text = []
        for block in tabs[0].get("documentTab", {}).get("body", {}).get("content", []):
            if "sectionBreak" in block:
                continue
            if "paragraph" not in block:
                raise PackageError("DOCUMENT_PLAIN_TEXT_REQUIRED")
            for element in block["paragraph"].get("elements", []):
                if "textRun" not in element:
                    raise PackageError("DOCUMENT_PLAIN_TEXT_REQUIRED")
                text.append(element["textRun"]["content"])
        processed = False
        if self.processed_folder_id and self.processed_folder_id in meta.get("parents", []):
            from .inbox_client import INBOX_ID
            parent = self._metadata(self.processed_folder_id)
            processed = parent.get("name") == "processed" and INBOX_ID in parent.get("parents", [])
        return {"raw": "".join(text).encode("utf-8"), "revision": document.get("revisionId"),
                "title": meta.get("name"),
                "mime_type": DOC_MIME, "parent_ids": meta.get("parents", []),
                "private_verified": True, "verified_processed_parent": processed}

    def fill(self, file_id, text, revision):
        self._request("post", "https://docs.googleapis.com/v1/documents/" + file_id + ":batchUpdate",
                      action="DOC_FILL", json={"writeControl": {"requiredRevisionId": revision},
                                               "requests": [{"insertText": {"location": {"index": 1}, "text": text}}]})

    def move(self, file_id, folder_id):
        if not self.verify_destination(folder_id):
            raise PackageError("DOCUMENT_DESTINATION_UNVERIFIED")
        current = self._metadata(file_id)
        if current.get("parents") != [self.staging_folder_id]:
            raise PackageError("DOCUMENT_STAGING_PARENT_MISMATCH")
        self._request("patch", "https://www.googleapis.com/drive/v3/files/" + file_id, action="DOC_MOVE",
                      params={"addParents": folder_id, "removeParents": self.staging_folder_id,
                              "supportsAllDrives": "true"}, json={})


def confirm_application(tower: dict, prepared: dict, *, expected_effects: list[dict]) -> dict:
    """Require both the exact private receipt and explicit effects in a valid Tower."""
    from .inbox_client import receipt_status
    from .live_tower import verify_live_tower
    revision = verify_live_tower(tower)
    status = receipt_status(tower, prepared)
    if status["stage"] not in {"APPLIED", "ALREADY_APPLIED"}:
        return status
    if not isinstance(expected_effects, list) or not expected_effects:
        raise PackageError("EXPECTED_EFFECT_READBACK_REQUIRED")
    def contains(actual, expected):
        if isinstance(expected, dict):
            return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
        if isinstance(expected, list):
            return isinstance(actual, list) and all(any(contains(a, e) for a in actual) for e in expected)
        return type(actual) is type(expected) and actual == expected
    for effect in expected_effects:
        if (type(effect) is not dict or set(effect) != {"path", "contains"}
                or not isinstance(effect["contains"], dict) or not effect["contains"]):
            raise PackageError("EXPECTED_EFFECT_INVALID")
        actual = tower.get("files", {}).get(effect["path"], {}).get("value")
        if not contains(actual, effect["contains"]):
            raise PackageError("TOWER_EFFECT_READBACK_MISSING")
    return {**status, "stage": "TOWER_APPLIED_READBACK", "tower_revision": revision,
            "entity_readback_required": False}


def validate_references(refs: list[dict]) -> list[dict]:
    if not isinstance(refs, list) or not 1 <= len(refs) <= 16:
        raise PackageError("ARTIFACT_REFERENCES_INVALID")
    seen = set()
    for ref in refs:
        if type(ref) is not dict or set(ref) != {"file_id", "folder_id", "campaign_id", "artifact_id", "package_sha256"}:
            raise PackageError("ARTIFACT_REFERENCE_FIELDS_INVALID")
        if (any(not isinstance(ref[k], str) or not _DRIVE_ID.fullmatch(ref[k]) for k in ("file_id", "folder_id"))
                or any(not isinstance(ref[k], str) or not _TOKEN.fullmatch(ref[k]) for k in ("artifact_id", "campaign_id"))
                or not isinstance(ref["package_sha256"], str) or not _HASH.fullmatch(ref["package_sha256"])
                or ref["artifact_id"] in seen):
            raise PackageError("ARTIFACT_REFERENCE_INVALID")
        seen.add(ref["artifact_id"])
    return refs


def catalog_requests(root: Path, item: dict, reader) -> list[dict]:
    """Writer-only metadata catalog; original evidence bytes stay in private Docs."""
    from .tower_paths import entity_path
    refs = validate_references(item["artifact_packages"])
    if item.get("_inbox_source") != "DRIVE":
        raise PackageError("ARTIFACT_PACKAGES_REQUIRE_PRIVATE_DRIVE")
    if reader is None:
        raise PackageUnavailable("ARTIFACT_READER_REQUIRED")
    requests = []
    for ref in refs:
        package = reader(ref)
        validate_package(package)
        if (digest(canonical(package)) != ref["package_sha256"]
                or package["artifact_id"] != ref["artifact_id"] or package["campaign_id"] != ref["campaign_id"]):
            raise PackageError("ARTIFACT_REFERENCE_HASH_MISMATCH")
        name = "ARTIFACT_PACKAGE::" + ref["artifact_id"]
        changes = {"kind": CONTRACT, "status": "RECORDED", "private": True, "visibility": "PRIVATE",
                   **ref, "created_at": package["created_at"], "producer_role": package["producer_role"],
                   "provenance": package["provenance"],
                   "files": [{k: v for k, v in f.items() if k != "content_b64"} for f in package["files"]]}
        path = entity_path(root, "artifact", name)
        if path.is_file():
            current = json.loads(path.read_text(encoding="utf-8"))
            if any(current.get(k) != v for k, v in changes.items()):
                raise PackageError("ARTIFACT_IDENTITY_CONFLICT")
            continue
        requests.append({"request_id": "REQ-PACKAGE-" + hashlib.sha256(name.encode()).hexdigest()[:32],
                         "entity_kind": "artifact", "entity_name": name, "expected_version": 0,
                         "writer_role": "LEARNER", "event_type": "ARTIFACT_PACKAGE_RECORDED", "changes": changes})
    return requests


def catalog_readback(root: Path, request: dict) -> bool:
    from .tower_paths import entity_path
    try:
        record = json.loads(entity_path(root, "artifact", request["entity_name"]).read_text(encoding="utf-8"))
        return all(record.get(k) == v for k, v in request["changes"].items())
    except (OSError, ValueError, KeyError):
        return False


def main(argv: list[str]) -> int:
    """artifact pack MANIFEST.json PACKAGE.json | verify PACKAGE.json | restore PACKAGE.json DIR | document PACKAGE.json FOLDER PLAN.json"""
    if len(argv) == 3 and argv[0] == "pack":
        manifest_path = Path(argv[1])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = [{"name": f["name"], "mime_type": f["mime_type"],
                  "content": (manifest_path.parent / f["path"]).read_bytes()} for f in manifest.pop("files")]
        Path(argv[2]).write_bytes(canonical(pack(**manifest, files=files)))
    elif len(argv) in {2, 3} and argv[0] in {"verify", "restore"}:
        package = parse_package(Path(argv[1]).read_bytes())
        if argv[0] == "restore":
            if len(argv) != 3:
                return 2
            destination = Path(argv[2])
            destination.mkdir(parents=True, exist_ok=True)
            for f in package["files"]:
                with (destination / f["name"]).open("xb") as output:
                    output.write(base64.b64decode(f["content_b64"], validate=True))
    elif len(argv) == 4 and argv[0] == "document":
        package = parse_package(Path(argv[1]).read_bytes())
        prepared = prepare_document(canonical(package), stable_id=package["artifact_id"], folder_id=argv[2])
        Path(argv[3]).write_bytes(canonical(prepared))
    else:
        print(main.__doc__)
        return 2
    print(json.dumps({"contract": CONTRACT, "status": "LOCAL_VERIFIED"}))
    return 0
