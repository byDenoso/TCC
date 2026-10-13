"""Canonical namespace lookups must never turn into fuzzy replacements."""
import json
import pytest
from test_continuity_enxame import Lab
from runtime.nexo_agent_api.memory import Snapshot, digest
from runtime.nexo_agent_api.retrieval import Retrieval

@pytest.fixture
def engine(tmp_path):
    lab = Lab(tmp_path / 'root')
    t = lab.tower
    t['files']['evolution/board.json'] = {'encoding':'json','value': {'posts': [
        {'id':'BP-ARCHIVED-20261007', 'status':'ARCHIVED', 'text':'Synthetic board record'},
        {'id':'BP-VISIBLE-20261007', 'status':'RECORDED', 'text':
         'ARTIFACT::MISSING-X BOARD_POST::MISSING-X MEMORY_ENTRY::MISSING-X BP-ARCHIVED-20261007 Synthetic board record'}]}}
    t['file_count'] = len(t['files'])
    t['revision'] = t['state_fingerprint'] = 'sha256:' + digest(t['files'])
    path=tmp_path/'snapshot.json'; path.write_text(json.dumps(t))
    engine=Retrieval(tmp_path/'index.db'); engine.sync(Snapshot.read(path))
    return engine

@pytest.mark.parametrize('query', ['ARTIFACT::MISSING-X','BOARD_POST::MISSING-X',
                                  'MEMORY_ENTRY::MISSING-X','FUTURE_KIND::MISSING-X'])
def test_all_typed_namespaces_absent_abstain(engine,query):
    answer=engine.search(query,'LEARNER')
    assert answer['mode']=='exact' and not answer['hits']


def test_archived_identity_cannot_substitute_visible_post(engine):
    answer=engine.search('BOARD_POST::BP-ARCHIVED-20261007','LEARNER')
    assert answer['mode']=='exact' and answer['hits']==[]
    historical=engine.search('BOARD_POST::BP-ARCHIVED-20261007','LEARNER',include_inactive=True)
    assert [h['id'] for h in historical['hits']]==['BOARD_POST::BP-ARCHIVED-20261007']


def test_ordinary_phrase_does_not_become_typed_lookup(engine):
    answer=engine.search('Synthetic board record','LEARNER')
    assert answer['mode']=='lexical' and answer['hits']
