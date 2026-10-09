"""Snapshot inspection reuses chain validation; readiness keeps the full reader."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.nexo_agent_api import continuity_cli, enxame
from runtime.nexo_agent_api.memory import digest
from tests.test_continuity_enxame import Lab, SCOPE


def saved(lab, tmp_path):
    path = tmp_path / 'snapshot.json'
    path.write_bytes(lab.raw)
    return path


def test_empty_protocol_does_not_unpack_whole_tower(tmp_path):
    lab = Lab(tmp_path / 'root')
    path = saved(lab, tmp_path)
    with patch.object(continuity_cli, 'materialize_live_tower', side_effect=AssertionError('unexpected unpack')):
        result = continuity_cli.inspect(path)
    assert result['events'] == [] and result['records'] == []
    assert result['prepared_tests'] == [] and not result['scientific_execution']


def test_protocol_uses_same_validation_as_materialized_reader(tmp_path):
    lab = Lab(tmp_path / 'root')
    lab.mature()
    path = saved(lab, tmp_path)
    with patch.object(continuity_cli, 'materialize_live_tower', side_effect=AssertionError('unexpected unpack')):
        fast = continuity_cli.inspect(path)
    with patch.object(continuity_cli, '_snapshot_view', return_value=None):
        disk = continuity_cli.inspect(path)
    assert fast == disk
    assert len(fast['events']) == 4


def test_bad_event_hash_is_not_reported_as_empty(tmp_path):
    lab = Lab(tmp_path / 'root')
    lab.event('A1', 'CLAIM', {'claim': 'Synthetic'})
    tower = lab.tower
    name = next(k for k in tower['files'] if k.startswith(enxame.EVENT_ROOT + '/'))
    tower['files'][name]['value']['sha256'] = '0' * 64
    tower['revision'] = tower['state_fingerprint'] = 'sha256:' + digest(tower['files'])
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(tower))
    with pytest.raises(ValueError, match='BOARD_CONTENT_INVALID'):
        continuity_cli.inspect(path)


def test_registered_test_keeps_full_readiness_reader(tmp_path):
    lab = Lab(tmp_path / 'root')
    lab.mature()
    assert not lab.freeze()['rejected']
    assert not lab.register()['rejected']
    path = saved(lab, tmp_path)
    original = continuity_cli.materialize_live_tower
    with patch.object(continuity_cli, 'materialize_live_tower', wraps=original) as materialize:
        result = continuity_cli.inspect(path)
    assert materialize.call_count == 1
    assert len(result['prepared_tests']) == 1
    assert not result['prepared_tests'][0]['current_readiness']['eligible']
    assert result['prepared_tests'][0]['scientific_evidence'] == []


def test_text_encoded_event_uses_legacy_reader(tmp_path):
    lab = Lab(tmp_path / 'root')
    lab.event('A1', 'CLAIM', {'claim': 'Synthetic'})
    tower = lab.tower
    name = next(k for k in tower['files'] if k.startswith(enxame.EVENT_ROOT + '/'))
    value = tower['files'][name]['value']
    tower['files'][name] = {'encoding': 'text', 'data': json.dumps(value)}
    tower['revision'] = tower['state_fingerprint'] = 'sha256:' + digest(tower['files'])
    path = tmp_path / 'legacy.json'
    path.write_text(json.dumps(tower))
    original = continuity_cli.materialize_live_tower
    with patch.object(continuity_cli, 'materialize_live_tower', wraps=original) as materialize:
        result = continuity_cli.inspect(path)
    assert materialize.call_count == 1 and result['events'] == [value]


def test_filtered_snapshot_matches_filtered_disk(tmp_path):
    lab = Lab(tmp_path / 'root')
    lab.mature()
    path = saved(lab, tmp_path)
    fast = continuity_cli.inspect(path, scope='not-this-scope', scope_version=1)
    with patch.object(continuity_cli, '_snapshot_view', return_value=None):
        disk = continuity_cli.inspect(path, scope='not-this-scope', scope_version=1)
    assert fast == disk and fast['total_events'] == 0
