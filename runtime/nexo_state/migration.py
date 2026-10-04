"""Lossless Tower -> SQLite shadow import. No Drive, Actions or live write path.

The canonical source is archived byte-for-byte. Normalized objects retain full
legacy payloads; an export overlays those objects onto the immutable archive.
Historical contradictions are findings, never implicit state corrections.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

MAX_BYTES = 64 * 1024 * 1024
CONTRACT = 'NEXO_TOWER_LIVE_V1'
ROOT_KINDS = {
    'entities/test/': 'test', 'entities/hypothesis/': 'hypothesis',
    'entities/work/': 'work', 'entities/artifact/': 'artifact',
    'contracts/': 'contract', 'runtime/results/': 'result',
    'runtime/artifacts/': 'artifact', 'runtime/runs/': 'run',
    'runtime/evidence/': 'evidence', 'events/': 'event',
    'operations/receipts/': 'legacy_receipt',
    'mutations/receipts/': 'legacy_receipt', 'roadmaps/': 'roadmap',
    'recipes/': 'recipe',
}
ID_FIELDS = ('id', 'entity_id', 'receipt_id', 'request_id', 'incident_id',
             'run_id', 'result_id', 'artifact_id', 'event_id', 'contract_id')
LINK_FIELDS = {
    'hypothesis_id': 'hypothesis', 'contests_test_id': 'test',
    'parent_test_id': 'test', 'test_id': 'test', 'test_ids': 'test',
    'roadmap_id': 'roadmap', 'run_id': 'run', 'work_id': 'work',
    'result_id': 'result', 'artifact_id': 'artifact',
    'depends_on': None, 'dependencies': None,
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(raw: bytes) -> str:
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_json_key')
        result[key] = value
    return result


def decode(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_BYTES:
        raise ValueError('snapshot_size_limit')
    if raw.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('expanded_snapshot_size_limit')
    def reject_constant(value: str) -> None:
        raise ValueError('non_finite_json_number')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                       parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError('snapshot_must_be_object')
    # Also rejects float overflow such as 1e999.
    canonical(value)
    return value


def validate(bundle: dict[str, Any]) -> str:
    expected = {
        'contract': CONTRACT, 'authority': 'TOWER_V06',
        'storage': 'GOOGLE_DRIVE_PRIVATE',
        'truth_owner': 'TOWER_V06@GOOGLE_DRIVE_PRIVATE',
        'write_model': 'IN_PLACE_FILE_REVISION_CAS_READBACK',
    }
    if any(bundle.get(k) != v for k, v in expected.items()):
        raise ValueError('unsupported_source_authority')
    files = bundle.get('files')
    if not isinstance(files, dict) or type(bundle.get('file_count')) is not int:
        raise ValueError('invalid_files_collection')
    if bundle['file_count'] != len(files) or not bundle.get('stable_file_id'):
        raise ValueError('source_identity_or_count_mismatch')
    for path, entry in files.items():
        if (not isinstance(path, str) or not path or '\\' in path or '\x00' in path
                or PurePosixPath(path).is_absolute() or '..' in path.split('/')
                or path != str(PurePosixPath(path)) or not isinstance(entry, dict)):
            raise ValueError('invalid_logical_path_or_entry')
    # Same canonical files digest as runtime.nexo_agent_api.live_tower.
    return digest(canonical(files).encode('utf-8'))


@contextmanager
def connect(path: str | Path, *, readonly: bool = False,
            timeout: float = 2.0) -> Iterator[sqlite3.Connection]:
    path = Path(path).resolve()
    target = path.as_uri() + '?mode=ro' if readonly else str(path)
    con = sqlite3.connect(target, uri=readonly, timeout=timeout,
                          isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('PRAGMA busy_timeout=' + str(max(0, int(timeout * 1000))))
        if readonly:
            con.execute('PRAGMA query_only=ON')
        else:
            con.execute('PRAGMA synchronous=FULL')
        yield con
    finally:
        con.close()


def initialize(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('database_symlink_not_allowed')
    with connect(path) as con:
        # Reject a foreign/newer schema before modifying it.
        exists = con.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone()
        if exists:
            version = con.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if not version or version[0] != '1':
                raise ValueError('unsupported_schema_version')
        elif con.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
            raise ValueError('not_a_nexo_database')
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript(Path(__file__).with_name('schema.sql').read_text())
    os.chmod(path, 0o600)


def identity(payload: dict[str, Any]) -> str | None:
    return next((payload[k] for k in ID_FIELDS
                 if isinstance(payload.get(k), str) and payload[k]), None)


def candidates(path: str, entry: dict[str, Any]):
    if entry.get('encoding') != 'json' or not isinstance(entry.get('value'), dict):
        return
    value = entry['value']
    for prefix, kind in ROOT_KINDS.items():
        if path.startswith(prefix):
            yield kind, (), value
            # Test reviews are retained inside the test, not independently mutable.
            return
    embedded = {'evolution/board.json': ('posts', 'board_post'),
                'evolution/incidents.json': ('incidents', 'incident')}
    if path in embedded:
        field, kind = embedded[path]
        for i, payload in enumerate(value.get(field, [])):
            if isinstance(payload, dict):
                yield kind, (field, i), payload
    if path == 'evolution/batteries.json':
        for i, battery in enumerate(value.get('batteries', [])):
            if isinstance(battery, dict):
                for j, payload in enumerate(battery.get('tests', [])):
                    if isinstance(payload, dict):
                        yield 'attempt_observation', ('batteries', i, 'tests', j), payload


def _insert_object(con: sqlite3.Connection, path: str, kind: str,
                   pointer: tuple, payload: dict[str, Any]) -> None:
    pointer_json = canonical(pointer)
    key = path + '#' + pointer_json
    eid = payload.get('attempt_id') if kind == 'attempt_observation' else identity(payload)
    if not isinstance(eid, str):
        eid = None
    version = payload.get('entity_version')
    # The CAS version is separate from the preserved, potentially absent source field.
    version = version if type(version) is int and version > 0 else 1
    con.execute('INSERT INTO objects(object_key,kind,entity_id,source_path,pointer_json,payload_json,version) VALUES(?,?,?,?,?,?,?)',
                (key, kind, eid, path, pointer_json, canonical(payload), version))
    if eid is None:
        con.execute('INSERT INTO migration_findings(code,source_key,detail_json) VALUES(?,?,?)',
                    ('MISSING_EXPLICIT_ID', key, '{}'))
    if kind == 'test' and payload.get('state') == 'DONE' and payload.get('execution_phase') == 'RUNNING':
        con.execute('INSERT INTO migration_findings(code,source_key,detail_json) VALUES(?,?,?)',
                    ('TERMINAL_TEST_RUNNING_ATTEMPT', key, '{}'))
    for field, target_kind in LINK_FIELDS.items():
        if field not in payload:
            continue
        values = payload[field] if isinstance(payload[field], list) else [payload[field]]
        for ordinal, target in enumerate(values):
            con.execute('INSERT INTO relations VALUES(?,?,?,?,?,?)',
                        (key, field, ordinal, target_kind,
                         target if isinstance(target, str) else None, canonical(target)))


def import_tower(db: str | Path, raw: bytes, *, expected_sha256: str) -> dict:
    if digest(raw) != expected_sha256:
        raise ValueError('snapshot_sha256_mismatch')
    bundle = decode(raw)
    computed = validate(bundle)
    initialize(db)
    with connect(db) as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            old = con.execute('SELECT raw_sha256 FROM snapshot').fetchone()
            if old:
                if old[0] != expected_sha256:
                    raise ValueError('database_already_imported_different_snapshot')
                con.rollback()
                return inventory(db)
            if con.execute('SELECT 1 FROM objects LIMIT 1').fetchone():
                raise ValueError('database_not_empty')
            con.execute('INSERT INTO snapshot VALUES(1,?,?,?,?,?,?)',
                        (raw, expected_sha256, bundle.get('revision'), computed,
                         canonical({k: v for k, v in bundle.items() if k != 'files'}),
                         datetime.now(timezone.utc).isoformat()))
            for path, entry in sorted(bundle['files'].items()):
                encoded = canonical(entry)
                con.execute('INSERT INTO legacy_documents VALUES(?,?,?)',
                            (path, encoded, digest(encoded.encode())))
                for kind, pointer, payload in candidates(path, entry):
                    _insert_object(con, path, kind, pointer, payload)
            if bundle.get('revision') != computed or bundle.get('state_fingerprint') != computed:
                con.execute('INSERT INTO migration_findings(code,detail_json) VALUES(?,?)',
                            ('DECLARED_FINGERPRINT_MISMATCH', '{}'))
            con.execute("INSERT INTO migration_findings(code,source_key,detail_json) SELECT 'DUPLICATE_ENTITY_ID',MIN(object_key),json_object('kind',kind,'count',COUNT(*)) FROM objects WHERE entity_id IS NOT NULL AND kind!='attempt_observation' GROUP BY kind,entity_id HAVING COUNT(*)>1")
            con.commit()
        except BaseException:
            con.rollback()
            raise
    return inventory(db)


def _export(con: sqlite3.Connection) -> dict:
    row = con.execute('SELECT header_json FROM snapshot').fetchone()
    if not row:
        raise ValueError('snapshot_not_imported')
    result = json.loads(row[0])
    files = {r['path']: json.loads(r['entry_json'])
             for r in con.execute('SELECT * FROM legacy_documents ORDER BY path')}
    for obj in con.execute('SELECT source_path,pointer_json,payload_json FROM objects ORDER BY source_path,pointer_json'):
        pointer = json.loads(obj['pointer_json'])
        value = json.loads(obj['payload_json'])
        entry = files[obj['source_path']]
        if not pointer:
            entry['value'] = value
        else:
            target = entry['value']
            for part in pointer[:-1]:
                target = target[part]
            target[pointer[-1]] = value
    result['files'] = files
    return result


def export_tower(db: str | Path) -> dict:
    with connect(db, readonly=True) as con:
        con.execute('BEGIN')
        return _export(con)


def compare(db: str | Path, raw: bytes) -> dict:
    original = decode(raw)
    exported = export_tower(db)
    original_files, current_files = original['files'], exported['files']
    changed = [p for p in sorted(original_files.keys() & current_files.keys())
               if canonical(original_files[p]) != canonical(current_files[p])]
    missing = sorted(original_files.keys() - current_files.keys())
    added = sorted(current_files.keys() - original_files.keys())
    header_equal = canonical({k:v for k,v in original.items() if k!='files'}) == canonical({k:v for k,v in exported.items() if k!='files'})
    return {'equal': header_equal and not (changed or missing or added),
            'header_equal': header_equal, 'changed_paths': changed,
            'missing_paths': missing, 'added_paths': added,
            'source_files': len(original_files), 'exported_files': len(current_files),
            'source_content_sha256': digest(canonical(original).encode()),
            'exported_content_sha256': digest(canonical(exported).encode())}


def inventory(db: str | Path) -> dict:
    with connect(db, readonly=True) as con:
        con.execute('BEGIN')
        snap = con.execute('SELECT raw_sha256,declared_revision,computed_revision FROM snapshot').fetchone()
        counts = dict(con.execute('SELECT kind,COUNT(*) FROM objects GROUP BY kind'))
        findings = dict(con.execute('SELECT code,COUNT(*) FROM migration_findings GROUP BY code'))
        unresolved = con.execute('SELECT COUNT(*) FROM relations r WHERE target_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM objects o WHERE o.entity_id=r.target_id AND (r.target_kind IS NULL OR o.kind=r.target_kind))').fetchone()[0]
        return {'mode': con.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()[0],
                'source': dict(snap) if snap else None,
                'files': con.execute('SELECT COUNT(*) FROM legacy_documents').fetchone()[0],
                'objects_by_kind': counts, 'findings': findings,
                'unresolved_reference_observations': unresolved,
                'integrity_check': con.execute('PRAGMA integrity_check').fetchone()[0],
                'foreign_key_violations': len(con.execute('PRAGMA foreign_key_check').fetchall())}


def backup(db: str | Path, destination: str | Path, *, timeout: float = 30.0) -> dict:
    """SQLite Online Backup API; publish a complete, verified new file only."""
    if timeout <= 0:
        raise ValueError('backup_timeout_must_be_positive')
    if Path(destination).is_symlink():
        raise ValueError('backup_destination_must_be_new')
    destination = Path(destination).resolve()
    if destination == Path(db).resolve() or destination.exists():
        raise ValueError('backup_destination_must_be_new')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.nexo-backup-', dir=destination.parent)
    os.close(fd)
    temp = Path(name)
    try:
        with connect(db, readonly=True) as src:
            dst = sqlite3.connect(temp)
            try:
                deadline = time.monotonic() + timeout
                def progress(status: int, remaining: int, total: int) -> None:
                    if time.monotonic() > deadline:
                        raise TimeoutError('backup_deadline_exceeded')
                src.backup(dst, pages=256, sleep=0.05, progress=progress)
                if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or dst.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('backup_integrity_failure')
                dst.execute('PRAGMA journal_mode=DELETE')
            finally:
                dst.close()
        with temp.open('rb') as stream:
            os.fsync(stream.fileno())
        # Same-filesystem exclusive publication; concurrent writers cannot overwrite.
        os.link(temp, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return {'path': str(destination), 'sha256': digest(destination.read_bytes()),
                'integrity_check': 'ok'}
    finally:
        temp.unlink(missing_ok=True)


def restore(source: str | Path, destination: str | Path) -> dict:
    # Restoring is also a consistent copy, into a new path; never replaces a live DB.
    with connect(source, readonly=True) as con:
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('restore_source_corrupt')
        row = con.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if not row or row[0] != '1':
            raise ValueError('unsupported_restore_schema')
    return backup(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('import', 'compare', 'export', 'inventory', 'backup', 'restore'):
        p = sub.add_parser(name)
        p.add_argument('--db', required=True)
        if name in ('import', 'compare'):
            p.add_argument('--source', required=True)
        if name == 'import':
            p.add_argument('--expected-sha256', required=True)
        if name in ('export', 'backup', 'restore'):
            p.add_argument('--destination', required=True)
    a = parser.parse_args()
    if a.command == 'import':
        result = import_tower(a.db, Path(a.source).read_bytes(), expected_sha256=a.expected_sha256)
    elif a.command == 'compare':
        result = compare(a.db, Path(a.source).read_bytes())
    elif a.command == 'export':
        payload = canonical(export_tower(a.db)).encode() + b'\n'
        fd = os.open(a.destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        result = {'path': a.destination, 'sha256': digest(payload)}
    elif a.command == 'inventory':
        result = inventory(a.db)
    else:
        result = (backup if a.command == 'backup' else restore)(a.db, a.destination)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if a.command == 'compare' and not result['equal']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
