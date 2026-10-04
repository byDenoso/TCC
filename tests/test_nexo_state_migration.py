import copy
import gzip
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from runtime.nexo_state import migration as m


def fixture():
    test = {'id': 'T-1', 'entity_version': 3, 'state': 'DONE',
            'status': 'DONE', 'execution_phase': 'RUNNING',
            'review_state': 'CONTESTED', 'hypothesis_id': 'H-1',
            'depends_on': ['MISSING', {'external': 'preserve'}],
            'unknown': {'nested': [1, 2.0, None, '\u00e7']}}
    files = {
        'entities/test/T-1.json': {'encoding': 'json', 'value': test},
        'entities/hypothesis/H-1.json': {'encoding': 'json', 'value': {'id': 'H-1', 'entity_version': 2}},
        'contracts/C-1.json': {'encoding': 'json', 'value': {'contract_id': 'C-1', 'version': 'v1'}},
        'evolution/board.json': {'encoding': 'json', 'value': {'posts': [{'id': 'B-1', 'from': 'LEARNER', 'to': 'ADVISOR', 'text': 'Hello', 'resolved_at': None}], 'extra': 42}},
        'evolution/incidents.json': {'encoding': 'json', 'value': {'incidents': [{'incident_id': 'I-1', 'next_owner': 'LEARNER', 'state': 'OPEN', 'closed_at': None}]}},
        'evolution/batteries.json': {'encoding': 'json', 'value': {'batteries': [{'id': 'BAT-1', 'tests': [{'test_id': 'T-1', 'attempt_id': 'A-1', 'seed': 2}, {'test_id': 'T-1', 'attempt_id': 'A-2', 'seed': 3}]}]}},
        'operations/receipts/R-1.json': {'encoding': 'json', 'value': {'receipt_id': 'R-1', 'intent_id': 'operation-1', 'outcome': 'APPLIED'}},
        'private/unknown.bin': {'encoding': 'future_format', 'value': {'opaque': ['keep', 1]}},
        'README.md': {'encoding': 'text', 'data': 'preserve\nbytes in logical file'},
    }
    fingerprint = m.digest(m.canonical(files).encode())
    return {'contract': m.CONTRACT, 'authority': 'TOWER_V06',
            'truth_owner': 'TOWER_V06@GOOGLE_DRIVE_PRIVATE',
            'storage': 'GOOGLE_DRIVE_PRIVATE',
            'write_model': 'IN_PLACE_FILE_REVISION_CAS_READBACK',
            'stable_file_id': 'synthetic-only', 'revision': fingerprint,
            'state_fingerprint': fingerprint, 'file_count': len(files),
            'files': files, 'unknown_header': {'keep': True}}


def source_bytes(bundle=None):
    return (json.dumps(bundle if bundle is not None else fixture(), ensure_ascii=False, indent=2) + '\n').encode()


def imported(tmp_path, raw=None):
    raw = source_bytes() if raw is None else raw
    db = tmp_path / 'state.sqlite'
    m.import_tower(db, raw, expected_sha256=m.digest(raw))
    return db, raw


def test_lossless_round_trip(tmp_path):
    db, raw = imported(tmp_path)
    comparison = m.compare(db, raw)
    assert comparison['equal']
    assert comparison['changed_paths'] == []
    assert m.export_tower(db) == fixture()
    with m.connect(db, readonly=True) as con:
        assert con.execute('SELECT raw FROM snapshot').fetchone()[0] == raw
        assert con.execute('SELECT COUNT(*) FROM tests').fetchone()[0] == 1
        assert con.execute('SELECT COUNT(*) FROM attempt_observations').fetchone()[0] == 2
        row = con.execute('SELECT * FROM tests').fetchone()
        assert (row['scientific_state'], row['attempt_state'], row['review_state']) == ('DONE', 'RUNNING', 'CONTESTED')


def test_same_import_is_idempotent(tmp_path):
    db, raw = imported(tmp_path)
    before = m.inventory(db)
    assert m.import_tower(db, raw, expected_sha256=m.digest(raw)) == before


def test_changed_import_conflicts(tmp_path):
    db, raw = imported(tmp_path)
    changed = fixture(); changed['unknown_header'] = False
    new = source_bytes(changed)
    with pytest.raises(ValueError, match='different_snapshot'):
        m.import_tower(db, new, expected_sha256=m.digest(new))
    assert m.compare(db, raw)['equal']


def test_hash_is_verified_before_creation(tmp_path):
    with pytest.raises(ValueError, match='sha256_mismatch'):
        m.import_tower(tmp_path/'x.sqlite', source_bytes(), expected_sha256='sha256:bad')
    assert not (tmp_path/'x.sqlite').exists()


def test_header_digest_discrepancy_is_not_repaired(tmp_path):
    bundle = fixture(); bundle['revision'] = 'sha256:historical'; bundle['state_fingerprint'] = 'sha256:historical'
    db, raw = imported(tmp_path, source_bytes(bundle))
    assert m.compare(db, raw)['equal']
    assert m.inventory(db)['findings']['DECLARED_FINGERPRINT_MISMATCH'] == 1


def test_historical_disagreement_and_missing_refs_are_visible(tmp_path):
    db, _ = imported(tmp_path)
    report = m.inventory(db)
    assert report['findings']['TERMINAL_TEST_RUNNING_ATTEMPT'] == 1
    assert report['unresolved_reference_observations'] == 1
    assert report['mode'] == 'shadow'


def test_duplicate_id_is_preserved_and_reported(tmp_path):
    bundle = fixture()
    bundle['files']['entities/test/T-duplicate.json'] = copy.deepcopy(bundle['files']['entities/test/T-1.json'])
    bundle['file_count'] += 1
    db, raw = imported(tmp_path, source_bytes(bundle))
    assert m.inventory(db)['findings']['DUPLICATE_ENTITY_ID'] == 1
    assert m.inventory(db)['objects_by_kind']['test'] == 2
    assert m.compare(db, raw)['equal']


def test_missing_id_is_not_invented(tmp_path):
    bundle = fixture(); del bundle['files']['entities/test/T-1.json']['value']['id']
    db, raw = imported(tmp_path, source_bytes(bundle))
    with m.connect(db, readonly=True) as con:
        assert con.execute('SELECT entity_id FROM tests').fetchone()[0] is None
    assert m.compare(db, raw)['equal']


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'a/../b', 'a\\b', './a', 'a//b', 'bad\x00name'])
def test_unsafe_logical_paths_rejected(tmp_path, path):
    bundle = fixture(); bundle['files'][path] = {'encoding': 'text', 'value': 'x'}; bundle['file_count'] += 1
    with pytest.raises(ValueError, match='logical_path'):
        imported(tmp_path, source_bytes(bundle))


@pytest.mark.parametrize('bad', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}', b'[]'])
def test_ambiguous_json_rejected(bad):
    with pytest.raises(ValueError):
        m.decode(bad)


def test_gzip_source_is_retained_exactly(tmp_path):
    raw = gzip.compress(source_bytes())
    db, _ = imported(tmp_path, raw)
    assert m.compare(db, raw)['equal']
    with m.connect(db, readonly=True) as con:
        assert con.execute('SELECT raw FROM snapshot').fetchone()[0] == raw


def test_rollback_on_mid_import_failure(tmp_path, monkeypatch):
    original = m._insert_object
    calls = 0
    def fail(*args):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError('simulated crash')
        return original(*args)
    monkeypatch.setattr(m, '_insert_object', fail)
    with pytest.raises(RuntimeError, match='simulated'):
        imported(tmp_path)
    with m.connect(tmp_path/'state.sqlite', readonly=True) as con:
        for table in ('snapshot', 'objects', 'legacy_documents', 'relations'):
            assert con.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] == 0


def test_backup_wal_restore_and_compare(tmp_path):
    db, raw = imported(tmp_path)
    backup = tmp_path/'backup.sqlite'; restored = tmp_path/'restored.sqlite'
    with m.connect(db) as writer:
        writer.execute('PRAGMA wal_autocheckpoint=0')
        writer.execute("INSERT INTO metadata VALUES ('wal_sentinel','committed')")
        writer.execute('BEGIN IMMEDIATE')
        writer.execute("INSERT INTO metadata VALUES ('uncommitted','not-visible')")
        m.backup(db, backup)
        writer.rollback()
    m.restore(backup, restored)
    assert m.compare(restored, raw)['equal']
    with m.connect(restored, readonly=True) as con:
        assert con.execute("SELECT value FROM metadata WHERE key='wal_sentinel'").fetchone()[0] == 'committed'
        assert con.execute("SELECT 1 FROM metadata WHERE key='uncommitted'").fetchone() is None


def test_backup_refuses_overwrite_and_self(tmp_path):
    db, _ = imported(tmp_path)
    dest = tmp_path/'exists'; dest.write_bytes(b'keep')
    for path in (dest, db):
        with pytest.raises(ValueError, match='must_be_new'):
            m.backup(db, path)
    assert dest.read_bytes() == b'keep'


def test_restore_rejects_non_database(tmp_path):
    bad = tmp_path/'bad'; bad.write_bytes(b'not sqlite')
    with pytest.raises(sqlite3.DatabaseError):
        m.restore(bad, tmp_path/'restored')
    assert not (tmp_path/'restored').exists()


def test_archive_is_immutable(tmp_path):
    db, _ = imported(tmp_path)
    with m.connect(db) as con:
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            con.execute("UPDATE legacy_documents SET entry_json='{}'")
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            con.execute('DELETE FROM snapshot')


def test_detects_mutated_payload_in_export(tmp_path):
    db, raw = imported(tmp_path)
    with m.connect(db) as con:
        con.execute("UPDATE objects SET payload_json=json_set(payload_json,'$.state','CHANGED') WHERE kind='test'")
    result = m.compare(db, raw)
    assert not result['equal']
    assert result['changed_paths'] == ['entities/test/T-1.json']


def test_concurrent_same_snapshot_import(tmp_path):
    db = tmp_path/'state.sqlite'; raw = source_bytes(); m.initialize(db)
    def run(_):
        return m.import_tower(db, raw, expected_sha256=m.digest(raw))
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,b = list(pool.map(run, range(2)))
    assert a == b
    assert m.compare(db, raw)['equal']


def test_rejects_future_or_foreign_schema(tmp_path):
    db = tmp_path/'state.sqlite'; m.initialize(db)
    with m.connect(db) as con:
        con.execute("UPDATE metadata SET value='999' WHERE key='schema_version'")
    with pytest.raises(ValueError, match='schema_version'):
        m.initialize(db)
    foreign = tmp_path/'foreign.sqlite'
    with sqlite3.connect(foreign) as con:
        con.execute('CREATE TABLE foreign_table(x)')
    with pytest.raises(ValueError, match='not_a_nexo'):
        m.initialize(foreign)


def test_backup_deadline_cleans_temporary_file(tmp_path, monkeypatch):
    db, _ = imported(tmp_path)
    ticks = iter([0.0, 50.0])
    monkeypatch.setattr(m.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(TimeoutError, match='deadline'):
        m.backup(db, tmp_path/'backup.sqlite', timeout=1)
    assert not (tmp_path/'backup.sqlite').exists()
    assert list(tmp_path.glob('.nexo-backup-*')) == []


def test_backup_refuses_dangling_symlink(tmp_path):
    db, _ = imported(tmp_path)
    dest = tmp_path/'link'; dest.symlink_to(tmp_path/'not-created')
    with pytest.raises(ValueError, match='must_be_new'):
        m.backup(db, dest)
    assert not (tmp_path/'not-created').exists()
