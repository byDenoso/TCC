"""Create-only client for the existing Writer; connector callbacks retain authorization.

No Tower writes, credential discovery, transport fallback, or retry loop. The
caller must persist the returned journal across pulses before attempting delivery.
"""
from __future__ import annotations

import json
import threading
from typing import Any
from uuid import uuid4

from .operation_receipts import payload_hash, envelope_effect_id
from .drive_transport import DriveInbox, DriveTower, TowerTransportError

INBOX_ID = "1NxhMy_HiGmHX2XHNLDDTRzqUoYY07HYR"
_delivery_lock = threading.RLock()


class InboxCreateRejected(RuntimeError):
    """Definitive Drive create rejection, without a private response body."""
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"DRIVE_INBOX_CREATE_REJECTED:{status_code}")


def prepare(envelope: dict, *, runtime_role: str, allowed_kinds: set[str]) -> dict:
    if not isinstance(envelope, dict) or any(k.startswith("_") for k in envelope):
        raise ValueError("UNTRUSTED_TRANSPORT_METADATA")
    if envelope.get("source") != runtime_role or envelope.get("kind") not in allowed_kinds:
        raise PermissionError("OPERATION_NOT_AUTHORIZED")
    identity = envelope.get("intent_id")
    # Reject rather than trim: the approved identity participates in hashes and
    # must already match the Writer's stripped receipt identity.
    if (not isinstance(identity, str) or not identity or identity != identity.strip()
            or len(identity) > 200):
        raise ValueError("STABLE_INTENT_ID_REQUIRED")
    if not isinstance(envelope.get("payload"), dict) or not envelope.get("created_at"):
        raise ValueError("ENVELOPE_SCHEMA_INVALID")
    raw = json.dumps(envelope, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > 1024 * 1024:
        raise ValueError("ENVELOPE_TOO_LARGE_USE_RUNTIME_ARTIFACTS")
    digest = payload_hash(envelope)
    return {"intent_id": identity, "payload_sha256": digest,
            "filename": "nexo-" + envelope_effect_id(identity) + ".json", "raw": raw}


def receipt_status(tower: dict, prepared: dict) -> dict:
    rows = []
    for path, entry in tower.get("files", {}).items():
        row = entry.get("value", {})
        if (path.startswith("operations/receipts/") and row.get("intent_id") == prepared["intent_id"]
                and row.get("effect_id") == envelope_effect_id(prepared["intent_id"])):
            rows.append(row)
    rows.sort(key=lambda r: (r.get("observed_at", ""), r.get("receipt_id", "")))
    if not rows:
        return {"stage": "UNOBSERVED", "receipt": None, "tower_revision": tower.get("revision")}
    row = rows[-1]
    if row.get("payload_sha256") != prepared["payload_sha256"]:
        raise ValueError("INTENT_PAYLOAD_CONFLICT")
    return {"stage": row.get("outcome"), "receipt": row,
            "tower_revision": tower.get("revision"), "entity_readback_required": row.get("outcome") == "APPLIED"}


def deliver(prepared: dict, transport: Any, *, tower: dict, journal: dict | None = None) -> dict:
    """transport: can_write, lookup(filename, inbox), create(raw, filename, inbox), read(id).

    lookup must inspect root and processed exhaustively and fail on partial reads.
    read returns {raw, mime_type, parent_ids}. A timeout is an unknown outcome;
    subsequent calls may reconcile it but never create automatically.
    """
    with _delivery_lock:
        status = receipt_status(tower, prepared)
        if status["receipt"]:
            return status
        if not transport.can_write:
            raise PermissionError("DRIVE_WRITE_PERMISSION_REQUIRED")
        if journal and journal.get('stage')=='PERMISSION_DENIED':
            raise PermissionError('OPERATOR_REAUTHORIZATION_REQUIRED')
        if journal and (journal.get("intent_id") != prepared["intent_id"]
                        or journal.get("payload_sha256") != prepared["payload_sha256"]):
            raise ValueError("JOURNAL_IDENTITY_CONFLICT")
        if journal and journal.get("stage") == "CREATE_REJECTED":
            return dict(journal)
        found = transport.lookup(prepared["filename"], INBOX_ID)
        if len(found) > 1:
            raise ValueError("INBOX_DUPLICATE_FILES_REQUIRE_RECONCILIATION")
        base = {k: prepared[k] for k in ("intent_id", "payload_sha256", "filename")}
        if found:
            file_id = found[0]
        elif journal and journal.get("stage") in {"SENDING", "OUTCOME_UNKNOWN", "DELIVERED"}:
            return {**base, "stage": "OUTCOME_UNKNOWN", "retry": "RECONCILE_ONLY"}
        else:
            # Persist SENDING before invoking a remote create. The mutable journal
            # lets a caller checkpoint it through its authorized storage callback.
            if journal is None:
                raise ValueError("DURABLE_DELIVERY_JOURNAL_REQUIRED")
            journal.update({**base, "stage": "SENDING"})
            transport.checkpoint(journal)
            try:
                file_id = transport.create(prepared["raw"], prepared["filename"], INBOX_ID)
            except InboxCreateRejected as error:
                journal.update({"stage": "CREATE_REJECTED", "status_code": error.status_code,
                                "retry": "OPERATOR_CORRECTION"})
                transport.checkpoint(journal)
                return dict(journal)
            except (TimeoutError, TowerTransportError) as error:
                if isinstance(error,TowerTransportError) and error.retry_condition=='OPERATOR_REAUTHORIZATION':
                    journal.update({'stage':'PERMISSION_DENIED','retry':'OPERATOR_REAUTHORIZATION'})
                    transport.checkpoint(journal)
                    raise
                journal.update({"stage": "OUTCOME_UNKNOWN"})
                transport.checkpoint(journal)
                return {**base, "stage": "OUTCOME_UNKNOWN", "retry": "RECONCILE_ONLY"}
        readback = transport.read(file_id)
        if readback.get("raw") != prepared["raw"] or readback.get("mime_type") != "application/json":
            raise ValueError("INBOX_READBACK_MISMATCH")
        if INBOX_ID not in readback.get("parent_ids", []) and not readback.get("verified_processed_parent"):
            raise ValueError("INBOX_READBACK_PARENT_MISMATCH")
        result = {**base, "stage": "DELIVERED", "file_id": file_id, "receipt": None}
        if journal is not None:
            journal.update(result)
            transport.checkpoint(journal)
        return result


class DriveInboxClientTransport:
    """Existing authenticated Drive session, pinned folders, raw multipart create.

    checkpoint must durably save the journal in the caller's authorized runtime.
    This adapter never discovers credentials or changes sharing or Tower bytes.
    """
    def __init__(self, session: Any, *, can_write: bool, checkpoint):
        self.can_write=can_write
        self.inbox=DriveInbox(session=session,folder_id=INBOX_ID)
        self.checkpoint=checkpoint
    def lookup(self, filename: str, inbox: str) -> list[str]:
        if inbox!=self.inbox._inbox():raise ValueError('INBOX_ID_MISMATCH')
        processed=self.inbox._folder('processed',inbox)
        parents=[inbox]+([processed] if processed else [])
        where=' or '.join("'"+self.inbox._quote(parent)+"' in parents" for parent in parents)
        query="name = '"+self.inbox._quote(filename)+"' and trashed = false and ("+where+")"
        return [row['id'] for row in self.inbox._query(query)]
    def create(self, raw: bytes, filename: str, inbox: str) -> str:
        if not self.can_write:raise PermissionError('DRIVE_WRITE_PERMISSION_REQUIRED')
        if inbox!=self.inbox._inbox():raise ValueError('INBOX_ID_MISMATCH')
        boundary='nexo-'+uuid4().hex
        metadata=json.dumps({'name':filename,'mimeType':'application/json','parents':[inbox]}).encode()
        body=(b'--'+boundary.encode()+b'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+metadata+
              b'\r\n--'+boundary.encode()+b'\r\nContent-Type: application/json\r\n\r\n'+raw+
              b'\r\n--'+boundary.encode()+b'--\r\n')
        response=DriveTower._call('INBOX_CREATE',lambda:self.inbox.session.post(
            'https://www.googleapis.com/upload/drive/v3/files',
            params={'uploadType':'multipart','supportsAllDrives':'true','fields':'id'},data=body,
            headers={'Content-Type':'multipart/related; boundary='+boundary},timeout=60))
        if 400 <= response.status_code < 500 and response.status_code not in {401,403,408,425,429}:
            raise InboxCreateRejected(response.status_code)
        response=DriveTower._check(response,'INBOX_CREATE')
        return response.json()['id']
    def read(self,file_id: str) -> dict:
        meta=self.inbox._metadata(file_id)
        processed=self.inbox._folder('processed',INBOX_ID)
        if meta.get('trashed') or meta.get('id')!=file_id:raise ValueError('INBOX_READBACK_INVALID')
        return {'raw':self.inbox._content(meta),'mime_type':meta.get('mimeType'),
                'parent_ids':meta.get('parents',[]),'verified_processed_parent':bool(processed and processed in meta.get('parents',[]))}
