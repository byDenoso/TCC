"""Regressions for observed gaps; use only synthetic Tower files."""
import json
import pytest
from test_continuity_enxame import Lab
from runtime.nexo_agent_api import continuity_cli
from runtime.nexo_agent_api.memory import Snapshot


def create_project(lab):
    body = {'event_id': 'created', 'project_id': 'demo', 'scope': 'WORK',
            'title': 'Synthetic project', 'action': 'CREATED', 'text': 'Start',
            'sources': [], 'expected_previous': None}
    assert not lab.apply('NEXO_PROJECT_EVENT', 'CHATGPT', body)['rejected']
    record = next(e['value'] for e in lab.tower['files'].values()
                  if e.get('value', {}).get('kind') == 'NEXO_PROJECT_EVENT')
    return body, record


def test_reopen_requires_a_completed_project(tmp_path):
    lab = Lab(tmp_path / 'root')
    body, record = create_project(lab)
    report = lab.apply('NEXO_PROJECT_EVENT', 'CHATGPT', {
        **body, 'event_id': 'reopen', 'action': 'REOPENED',
        'expected_previous': record['id'], 'sources': [lab.source],
    })
    assert report['rejected'], 'An active project cannot be reopened.'


def test_inspect_requires_a_revision_for_continued_pages(tmp_path):
    lab = Lab(tmp_path / 'root')
    tower = tmp_path / 'tower.json'
    tower.write_bytes(lab.raw)
    with pytest.raises(ValueError, match='REVISION'):
        continuity_cli.inspect(tower, after=1)


def test_inspect_uses_the_same_bytes_it_verified(tmp_path, monkeypatch):
    lab = Lab(tmp_path / 'root')
    before = lab.raw
    assert not lab.event('A1', 'CANARIO', {'text': 'Synthetic'}, cid=None)['rejected']
    after = lab.raw
    tower = tmp_path / 'tower.json'
    tower.write_bytes(before)
    original = Snapshot.read

    def replace_after_read(path, *args, **kwargs):
        snapshot = original(path, *args, **kwargs)
        tower.write_bytes(after)
        return snapshot

    monkeypatch.setattr(Snapshot, 'read', staticmethod(replace_after_read))
    result = continuity_cli.inspect(tower)
    assert result['source_revision'] == json.loads(before)['revision']
    assert result['total_events'] == 0, 'Never pair old provenance with new content.'
