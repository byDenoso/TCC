"""Owner context on real Writer output. Every test uses synthetic contents."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import pytest

from test_continuity_enxame import Lab, AT
from runtime.nexo_agent_api import continuity_cli
from runtime.nexo_agent_api.continuity_context import context
from runtime.nexo_agent_api.live_tower import materialize_live_tower
from runtime.nexo_agent_api.memory import Snapshot, digest, documents
from runtime.nexo_agent_api.public_projection import build_public_projection
from runtime.nexo_agent_api.retrieval import BM25, import_documents


@pytest.fixture
def lab(tmp_path):
    return Lab(tmp_path / 'root')


def snapshot(lab, tmp_path):
    path = tmp_path / 'snapshot.json'
    path.write_bytes(lab.raw)
    return Snapshot.read(path)


def entry(lab, eid, text='Synthetic context', scope='WORK', **extra):
    payload = {'event_id': eid, 'scope': scope, 'category': 'USER_PREFERENCE',
               'text': text, 'sources': [], **extra}
    report = lab.apply('NEXO_MEMORY_ENTRY', 'CHATGPT', payload)
    assert not report['rejected'], report
    return 'MEMORY-' + digest([scope, eid])[:40]


def project(lab, eid, action='CREATED', previous=None, project_id='demo', **extra):
    body = {'event_id': eid, 'scope': 'WORK', 'project_id': project_id,
            'title': 'Synthetic document', 'action': action, 'text': action,
            'expected_previous': previous, 'sources': [], **extra}
    report = lab.apply('NEXO_PROJECT_EVENT', 'CHATGPT', body)
    assert not report['rejected'], report
    return 'PROJECT-EVENT-' + digest(['WORK', eid])[:40]


def change_source(lab, path, value):
    tower = lab.tower
    if value is None:
        del tower['files'][path]
    else:
        tower['files'][path] = {'encoding': 'json', 'value': value}
    tower['file_count'] = len(tower['files'])
    tower['revision'] = tower['state_fingerprint'] = 'sha256:' + digest(tower['files'])
    lab.raw = json.dumps(tower).encode()


def test_current_memory_replaces_old_and_exact_keeps_history(lab, tmp_path):
    old = entry(lab, 'old', 'Use older version')
    new = entry(lab, 'new', 'Use corrected version', supersedes_record_id=old)
    s = snapshot(lab, tmp_path)
    result = context(s, scope='WORK')
    assert [h['id'] for h in result['hits']] == [new]
    assert result['counts']['memories'] == 2 and result['counts']['current_memories'] == 1
    retired = context(s, scope='WORK', query=old)['hits'][0]
    assert retired['state'] == 'SUPERSEDED' and retired['superseded_by'] == new
    assert len(context(s, scope='WORK', include_history=True)['hits']) == 2


def test_future_correction_does_not_replace_current_early(lab, tmp_path):
    old = entry(lab, 'old', 'Current')
    new = entry(lab, 'future', 'Future', supersedes_record_id=old, valid_from='2026-10-09T00:00:00Z')
    s = snapshot(lab, tmp_path)
    assert [x['id'] for x in context(s, scope='WORK', at=AT)['hits']] == [old]
    assert [x['id'] for x in context(s, scope='WORK', at='2026-10-10T00:00:00Z')['hits']] == [new]


def test_expiration_does_not_resurrect_replaced_memory(lab, tmp_path):
    old = entry(lab, 'old')
    entry(lab, 'new', supersedes_record_id=old, valid_until='2026-10-08T00:00:00Z')
    result = context(snapshot(lab, tmp_path), scope='WORK', at='2026-10-10T00:00:00Z')
    assert result['hits'] == [] and result['counts']['memories'] == 2


def test_effective_correction_chain_does_not_leave_two_current_versions(lab, tmp_path):
    a = entry(lab, 'a')
    b = entry(lab, 'b', supersedes_record_id=a, valid_from='2026-10-10T00:00:00Z')
    c = entry(lab, 'c', supersedes_record_id=b, valid_from='2026-10-08T00:00:00Z')
    result = context(snapshot(lab, tmp_path), scope='WORK', at='2026-10-09T00:00:00Z')
    assert [h['id'] for h in result['hits']] == [c]


def test_contradictions_remain_contested(lab, tmp_path):
    a = entry(lab, 'a', 'Rule A')
    b = entry(lab, 'b', 'Rule B', contradicts=[a])
    result = context(snapshot(lab, tmp_path), scope='WORK')
    assert {h['id'] for h in result['hits']} == {a, b}
    assert {h['state'] for h in result['hits']} == {'CONTESTED'}
    assert result['counts']['contested_memories'] == 2
    assert all(not h['scientific_authority'] for h in result['hits'])


@pytest.mark.parametrize('scope', ['PERSONAL', 'SCIENCE', 'CLIENT:ALPHA', 'CLIENT:BETA'])
def test_explicit_scopes_never_leak_other_records(lab, tmp_path, scope):
    entry(lab, 'private', 'OTHER_SCOPE_SENTINEL', scope=scope)
    own = entry(lab, 'own', 'Work record')
    result = context(snapshot(lab, tmp_path), scope='WORK')
    assert [h['id'] for h in result['hits']] == [own]
    assert 'OTHER_SCOPE_SENTINEL' not in json.dumps(result)
    assert result['counts']['records'] == 1


@pytest.mark.parametrize('scope', ['', '*', 'ALL', 'CLIENT:', '../WORK'])
def test_scope_is_required_not_inferred(lab, tmp_path, scope):
    with pytest.raises(ValueError, match='SCOPE'):
        context(snapshot(lab, tmp_path), scope=scope)


def test_exact_unknown_identifier_never_matches_mention(lab, tmp_path):
    entry(lab, 'a', 'MEMORY-DOES-NOT-EXIST is mentioned in this text')
    result = context(snapshot(lab, tmp_path), scope='WORK', query='MEMORY-DOES-NOT-EXIST')
    assert result['mode'] == 'exact' and result['hits'] == []


def test_shared_bm25_is_used_without_score_fusion(lab, tmp_path):
    a = entry(lab, 'a', 'calibracao calibracao catalogo')
    entry(lab, 'b', 'geometria universo')
    result = context(snapshot(lab, tmp_path), scope='WORK', query='calibração')
    expected = BM25(['calibracao calibracao catalogo ', 'geometria universo ']).score('calibração')
    assert result['mode'] == 'lexical' and result['hits'][0]['id'] == a
    assert result['hits'][0]['scores']['bm25'] == pytest.approx(expected[0])


@pytest.mark.parametrize('value,status', [({'purpose': 'Changed'}, 'SOURCE_CHANGED'),
                                         (None, 'SOURCE_UNAVAILABLE_IN_SNAPSHOT')])
def test_source_drift_suspends_evidence_support(lab, tmp_path, value, status):
    entry(lab, 'lesson', 'Lesson', category='OPERATIONAL_LESSON',
          sources=[lab.source], applicability='Synthetic protocol only')
    change_source(lab, lab.source['path'], value)
    result = context(snapshot(lab, tmp_path), scope='WORK')
    assert result['source_warnings'] == [status]
    assert result['hits'][0]['support_state'] == 'REVALIDATION_REQUIRED'
    assert result['hits'][0]['requires_source_review']
    assert not result['hits'][0]['scientific_authority']


def test_every_hit_has_exact_canonical_content_reference(lab, tmp_path):
    entry(lab, 'a', sources=[lab.source])
    s = snapshot(lab, tmp_path)
    for hit in context(s, scope='WORK')['hits']:
        citation = hit['citation']
        record = s.payload['files'][citation['path']]['value']
        assert citation['content_sha256'] == digest(record)
        assert citation['entity_version'] == record['entity_version']
        assert citation['tower_revision'] == s.revision
        assert hit['source_checks'][0]['state'] == 'VERIFIED_IN_SNAPSHOT'


def test_redaction_preserves_hash_of_original(lab, tmp_path):
    entry(lab, 'a', 'Bearer abc123.secret and https://example.invalid/file?token=hidden')
    s = snapshot(lab, tmp_path)
    hit = context(s, scope='WORK')['hits'][0]
    assert 'abc123.secret' not in hit['text'] and 'hidden' not in hit['text'] and hit['redacted']
    assert hit['citation']['content_sha256'] == digest(s.payload['files'][hit['citation']['path']]['value'])


def test_projection_and_runtime_roles_do_not_gain_owner_access(lab, tmp_path):
    entry(lab, 'secret', 'OWNER_ONLY_SENTINEL')
    s = snapshot(lab, tmp_path)
    for importer in (documents, import_documents):
        docs, _ = importer(s)
        candidates = [d for d in docs if 'OWNER_ONLY_SENTINEL' in d.text]
        assert candidates and all(d.allowed_roles == [] for d in candidates)
    root, _ = materialize_live_tower(lab.raw, tmp_path / 'materialized')
    public = build_public_projection(root)
    assert 'OWNER_ONLY_SENTINEL' not in json.dumps(public)
    assert 'OWNER_ONLY_SENTINEL' in json.dumps(context(s, scope='WORK'))


def test_project_context_keeps_pending_decision_across_progress(lab, tmp_path):
    first = project(lab, 'created', owner='DENER', next_action='Review draft')
    decision = project(lab, 'decision', action='DECISION_REQUIRED', previous=first,
                       decision='Choose release', next_action='Select one')
    latest = project(lab, 'progress', action='PROGRESS', previous=decision, sources=[lab.source])
    result = context(snapshot(lab, tmp_path), scope='WORK', query='demo')
    head = result['hits'][0]
    assert head['id'] == latest and head['state'] == 'DECISION_REQUIRED'
    assert head['owner'] == 'DENER' and head['pending_decision']['record_id'] == decision
    assert head['event_count'] == 3 and len(result['hits']) == 1
    project(lab, 'resolved', action='DECISION', previous=latest, sources=[lab.source])
    assert context(snapshot(lab, tmp_path), scope='WORK')['counts']['decisions_required'] == 0


def test_project_delivery_retains_its_own_source_and_completion(lab, tmp_path):
    first = project(lab, 'created', next_action='Deliver')
    delivery = project(lab, 'delivery', action='DELIVERY', previous=first, sources=[lab.source],
                       delivery={'source_path': lab.source['path'], 'title': 'Fixture'})
    done = project(lab, 'done', action='COMPLETED', previous=delivery, sources=[lab.source])
    head = context(snapshot(lab, tmp_path), scope='WORK')['hits'][0]
    assert head['state'] == 'COMPLETED' and head['next_action'] is None
    assert head['deliveries'][0]['record_id'] == delivery and head['id'] == done
    project(lab, 'reopen', action='REOPENED', previous=done, sources=[lab.source], next_action='Revise')
    assert context(snapshot(lab, tmp_path), scope='WORK')['hits'][0]['state'] == 'ACTIVE'


def test_project_malformed_predecessor_is_not_silently_sorted(lab, tmp_path):
    first = project(lab, 'created')
    second = project(lab, 'progress', action='PROGRESS', previous=first, sources=[lab.source])
    path = 'entities/artifact/' + second + '.json'
    value = copy.deepcopy(lab.tower['files'][path]['value'])
    value['payload']['expected_previous'] = 'not-the-predecessor'
    change_source(lab, path, value)
    with pytest.raises(ValueError, match='PROJECT_SEQUENCE'):
        context(snapshot(lab, tmp_path), scope='WORK')


def test_mutation_after_snapshot_read_is_detected(lab, tmp_path):
    entry(lab, 'a')
    s = snapshot(lab, tmp_path)
    s.payload['files'][lab.source['path']]['value']['purpose'] = 'tampered after verification'
    with pytest.raises(ValueError, match='SOURCE_CHANGED_AFTER_READ'):
        context(s, scope='WORK')


def test_context_does_not_modify_canonical_bytes(lab, tmp_path):
    entry(lab, 'a')
    s = snapshot(lab, tmp_path)
    before = copy.deepcopy(s.payload)
    result = context(s, scope='WORK', at=AT)
    assert s.payload == before
    assert not result['scientific_execution'] and not result['scheduler_mutation']
    assert result['historical_knowledge_reconstructed'] is False
    assert result['temporal_semantics'] == 'DECLARED_VALIDITY_WITHIN_SUPPLIED_SNAPSHOT'


def test_context_expected_revision_is_enforced(lab, tmp_path):
    with pytest.raises(ValueError, match='REVISION_CHANGED'):
        context(snapshot(lab, tmp_path), scope='WORK', expected_revision='sha256:stale')


def test_pagination_roundtrip_and_stale_revision(lab, tmp_path):
    for i in range(3):
        assert not lab.event('A1', 'CANARIO', {'text': 'Synthetic'}, cid=None)['rejected']
    path = tmp_path / 'tower.json'; path.write_bytes(lab.raw)
    first = continuity_cli.inspect(path, limit=1)
    second = continuity_cli.inspect(path, after=first['next_offset'], limit=1,
                                    expected_revision=first['source_revision'])
    assert first['events'][0]['event_id'] != second['events'][0]['event_id']
    assert first['page_context']['expected_revision'] == first['source_revision']
    assert not lab.event('A1', 'CANARIO', {'text': 'Changed source'}, cid=None)['rejected']
    path.write_bytes(lab.raw)
    with pytest.raises(ValueError, match='REVISION_CHANGED'):
        continuity_cli.inspect(path, after=second['next_offset'], expected_revision=first['source_revision'])


@pytest.mark.parametrize('limit', [0, -1, 101, True, 1.5])
def test_context_bounds(lab, tmp_path, limit):
    with pytest.raises(ValueError, match='BOUNDS'):
        context(snapshot(lab, tmp_path), scope='WORK', limit=limit)


def test_missing_snapshot_is_not_empty_context(tmp_path):
    with pytest.raises(FileNotFoundError):
        Snapshot.read(tmp_path / 'missing.json')
