"""Exact source-pointer checks, not citations accepted by declaration."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest
from tests.test_continuity_enxame import Lab
from runtime.nexo_agent_api.memory import Snapshot, digest
from runtime.nexo_agent_api.continuity_context import context
from runtime.nexo_agent_api.retrieval import resolve_pointer

spec = importlib.util.spec_from_file_location('benchmark', Path(__file__).parents[1] / 'scripts/benchmark_continuity_retrieval.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)

@pytest.fixture
def source(tmp_path):
    lab = Lab(tmp_path / 'root')
    tower = lab.tower
    tower['files']['contracts/SYNTHETIC.json']['value'] = {
        'entity_version': 3, 'posts': [{'version': 2, 'text': 'Synthetic nested evidence'}],
        'escaped/key': {'~field': {'entity_version': 4, 'text': 'Escaped pointer'}}}
    tower['revision'] = tower['state_fingerprint'] = 'sha256:' + digest(tower['files'])
    path = tmp_path / 'snapshot.json'
    path.write_text(json.dumps(tower))
    return Snapshot.read(path)


def hit(s, pointer=''):
    path = 'contracts/SYNTHETIC.json'
    target = resolve_pointer(s.payload['files'][path]['value'], pointer)
    return {'citation': {'path': path, 'json_pointer': pointer,
            'source_id': s.source_id, 'tower_revision': s.revision,
            'entity_version': str(target.get('entity_version') or target.get('version') or 'unversioned'),
            'content_sha256': digest(target)}}

@pytest.mark.parametrize('pointer', ['', '/posts/0', '/escaped~1key/~0field'])
def test_exact_source_object_verified(source, pointer):
    assert benchmark.citation_valid(source, hit(source, pointer))

@pytest.mark.parametrize('field,value', [
    ('source_id', 'another-tower'), ('tower_revision', 'sha256:' + '0' * 64),
    ('content_sha256', '0' * 64), ('entity_version', '99'),
    ('json_pointer', '/posts/3'), ('json_pointer', '/posts/00'),
    ('json_pointer', '/missing'), ('json_pointer', None), ('path', 'missing.json')])
def test_nested_citation_is_not_silently_skipped(source, field, value):
    h = hit(source, '/posts/0')
    h['citation'][field] = value
    assert not benchmark.citation_valid(source, h)


def test_owner_context_citation_resolves_whole_record_and_separate_excerpt(tmp_path):
    lab = Lab(tmp_path / 'root')
    lab.apply('NEXO_MEMORY_ENTRY', 'CHATGPT', {'event_id': 'a', 'scope': 'WORK',
        'category': 'USER_PREFERENCE', 'text': 'Synthetic preferred format', 'sources': []})
    path = tmp_path / 'snapshot.json'
    path.write_bytes(lab.raw)
    s = Snapshot.read(path)
    h = context(s, scope='WORK')['hits'][0]
    c = h['citation']
    assert benchmark.citation_valid(s, h)
    target = s.payload['files'][c['path']]['value']
    assert resolve_pointer(target, c['excerpt_json_pointer']) == h['text']
