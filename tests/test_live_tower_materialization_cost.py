"""Materialization keeps validation and byte fidelity without redundant hashing."""
import gzip
import json
from unittest.mock import patch

import pytest

from runtime.nexo_agent_api import live_tower
from runtime.nexo_agent_api.memory import digest


def payload():
    owner = 'TOWER_V06@GOOGLE_DRIVE_PRIVATE'
    files = {
        'CONTROL.json': {'encoding': 'json', 'value': {'truth_owner': owner}},
        'entities/test/TEST::synthetic.json': {'encoding': 'json', 'value': {
            'id': 'TEST::synthetic', 'kind': 'TEST', 'status': 'DRAFT'}},
        'contracts/example.json': {'encoding': 'json', 'value': {'a': 1.25}},
        'runtime/note.txt': {'encoding': 'text', 'data': 'Preserve these bytes\n'},
        'runtime/carried.bin': {'encoding': 'base64', 'data': 'AAEC'},
    }
    fingerprint = 'sha256:' + digest(files)
    return dict(contract=live_tower.LIVE_TOWER_CONTRACT, authority='TOWER_V06',
                truth_owner=owner, storage='GOOGLE_DRIVE_PRIVATE',
                write_model='IN_PLACE_FILE_REVISION_CAS_READBACK',
                stable_file_id=live_tower.LIVE_TOWER_FILE_ID,
                revision=fingerprint, state_fingerprint=fingerprint,
                updated_at='2026-10-07T12:00:00Z', file_count=len(files), files=files)


@pytest.mark.parametrize('compressed', [False, True])
def test_one_verification_preserves_raw_base_and_metadata(tmp_path, compressed):
    data = payload()
    raw = json.dumps(data).encode()
    if compressed:
        raw = gzip.compress(raw)
    verifier = live_tower.verify_live_tower
    with patch.object(live_tower, 'verify_live_tower', wraps=verifier) as checked:
        root, metadata = live_tower.materialize_live_tower(raw, tmp_path / 'tower')
    assert checked.call_count == 1
    assert metadata['tower_revision'] == metadata['source_state_fingerprint'] == data['revision']
    assert (root / live_tower.LIVE_TOWER_NAME).read_bytes() == raw
    assert (root / 'runtime/note.txt').read_bytes() == b'Preserve these bytes\n'
    repacked = live_tower.build_live_tower_payload(root, base=data)
    assert repacked['files'] == data['files']


@pytest.mark.parametrize('field,value', [
    ('authority', 'DERIVED'), ('storage', 'PUBLIC'),
    ('truth_owner', 'another-owner'), ('write_model', 'UNSAFE'),
    ('contract', 'INVALID'), ('file_count', 999), ('stable_file_id', ''),
])
def test_invalid_header_still_fails_before_creating_destination(tmp_path, field, value):
    data = payload()
    data[field] = value
    destination = tmp_path / 'tower'
    with pytest.raises(ValueError):
        live_tower.materialize_live_tower(json.dumps(data).encode(), destination)
    assert not destination.exists()


def test_control_mismatch_still_rejected(tmp_path):
    data = payload()
    data['files']['CONTROL.json']['value']['truth_owner'] = 'wrong-owner'
    data['revision'] = data['state_fingerprint'] = 'sha256:' + digest(data['files'])
    with pytest.raises(ValueError, match='CONTROL truth_owner'):
        live_tower.materialize_live_tower(json.dumps(data).encode(), tmp_path / 'tower')


def test_path_escape_still_rejected(tmp_path):
    data = payload()
    data['files']['../escape.txt'] = {'encoding': 'text', 'data': 'must not escape'}
    data['file_count'] = len(data['files'])
    data['revision'] = data['state_fingerprint'] = 'sha256:' + digest(data['files'])
    with pytest.raises(ValueError, match='unsafe live Tower path'):
        live_tower.materialize_live_tower(json.dumps(data).encode(), tmp_path / 'tower')
    assert not (tmp_path / 'escape.txt').exists()


def test_legacy_stale_header_keeps_computed_revision_and_warning(tmp_path, capsys):
    data = payload()
    computed = data['revision']
    data['revision'] = data['state_fingerprint'] = 'legacy-stale-header'
    _, metadata = live_tower.materialize_live_tower(json.dumps(data).encode(), tmp_path / 'tower')
    assert metadata['tower_revision'] == computed
    assert 'LIVE_TOWER_DECLARED_FINGERPRINT_STALE' in capsys.readouterr().err
