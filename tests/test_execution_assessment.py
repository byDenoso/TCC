"""Audit overlays preserve raw observations and exclude only verified failures."""
import copy
import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.nexo_agent_api import execution_assessment as a, discovery
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, read_live_tower_bytes
from runtime.nexo_agent_api.public_projection import build_public_projection
from runtime.nexo_agent_api.service import AgentService, TowerAgentIssue
from runtime.nexo_agent_api.scientific_integrity import FROZEN
from tests.test_scientific_integrity import fixture, save


@pytest.fixture
def context(tmp_path):
    root=tmp_path/'tower'
    save(root,'CONTROL.json',{'mode':'ACTIVE','truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE'})
    test=fixture('TEST-AUDIT')
    test.update(status='DONE',state='DONE',verdict='INCONCLUSIVE',decision='INPUT_OR_FIT_UNAVAILABLE',
                executed_at='2026-09-30T10:01:00Z',result_summary='Calculation stopped before fitting',
                statistics={'data_sources':[{'url':'https://example.org/frozen','sha256':'a'*64}]},
                reproducibility={'battery_id':'bat-audit','run_ref':'actions/runs/123',
                                 'attempt_id':'attempt-'+'a'*32,'recipe_sha256':'b'*64})
    save(root,'entities/test/TEST-AUDIT.json',test)
    result={'verdict':test['verdict'],'decision':test['decision'],'statistics':test['statistics'],'summary':test['result_summary']}
    row={'test_id':test['id'],'ok':True,'result':result,'attempt_id':test['reproducibility']['attempt_id'],
         'recipe_sha256':'b'*64,'executed_at':test['executed_at']}
    raw=json.dumps({'results':[row]},indent=2)+'\n'
    approved={'test_id':test['id'],'battery_id':'bat-audit','run_ref':'actions/runs/123','artifact_id':456,
              'archive_sha256':'c'*64,'member_sha256':hashlib.sha256(raw.encode()).hexdigest(),
              'attempt_id':row['attempt_id'],'recipe_sha256':'b'*64,
              'expected_observation_hash':a.observation_hash(test),'expected_version':1}
    source={key:approved[key] for key in a.SOURCE_FIELDS}
    source.update(member_name='battery-results.json',member_utf8=raw)
    return root,test,{'approved':approved,'source':source}


def current(root):
    return json.loads((root/'entities/test/TEST-AUDIT.json').read_text())


def apply(root,body,source='RUNNER_OBSERVATION'):
    raw=json.dumps(build_live_tower_payload(root)).encode()
    with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
        packed,report=apply_to_tower(raw,[{'nexo_operation':a.OPERATION,'_inbox_source':source,'assessment':body}])
    return read_live_tower_bytes(packed or raw),report


def test_assessment_appends_only_overlay_with_real_writer_time(context):
    root,old,body=context
    before=copy.deepcopy(old)
    result=a.apply_assessment(root,body)
    assert result['accepted']
    after=current(root)
    assert after['entity_version']==2
    assert all(before.get(k)==after.get(k) for k in (*FROZEN,'prereg_hash','recipe','recipe_params',*a.OBSERVATION_FIELDS))
    assert set(a.public_assessment(after))=={'contract','classification','scientific_result_eligible','reason_code','recorded_at'}
    assert a.has_valid_operational_exclusion(after)
    assert after['execution_assessment']['recorded_at'] != old['executed_at']


def test_exact_replay_is_noop_without_new_event_or_version(context):
    root,_,body=context
    a.apply_assessment(root,body);before=current(root);events=list((root/'events').rglob('*.json'))
    assert a.apply_assessment(root,body)['status']=='NO_OP'
    assert current(root)==before
    assert list((root/'events').rglob('*.json'))==events


@pytest.mark.parametrize('field,value',[
    ('artifact_id',999),('run_ref','actions/runs/999'),('archive_sha256','d'*64),('member_sha256','d'*64),
    ('member_name','another.json'),('member_utf8','{"results": []}')])
def test_forged_artifact_metadata_or_bytes_are_rejected(context,field,value):
    root,old,body=context;body['source'][field]=value
    with pytest.raises(a.AssessmentError):a.apply_assessment(root,body)
    assert current(root)==old


def test_foreign_attempt_cannot_annotate_current_observation(context):
    root,old,body=context
    body['approved']['attempt_id']='attempt-'+'d'*32
    with pytest.raises(a.AssessmentError,match='FOREIGN_ATTEMPT'):a.apply_assessment(root,body)
    assert current(root)==old


def test_foreign_test_cannot_borrow_receipt(context):
    root,old,body=context
    data=json.loads(body['source']['member_utf8']);data['results'][0]['test_id']='OTHER'
    raw=json.dumps(data);body['source']['member_utf8']=raw
    body['source']['member_sha256']=body['approved']['member_sha256']=hashlib.sha256(raw.encode()).hexdigest()
    with pytest.raises(a.AssessmentError,match='MEMBERSHIP'):a.apply_assessment(root,body)
    assert current(root)==old


def test_legitimate_inconclusive_result_is_not_reclassified(context):
    root,test,body=context
    test['decision']='MIXED_TRACER_ROBUSTNESS';save(root,'entities/test/TEST-AUDIT.json',test)
    with pytest.raises(a.AssessmentError,match='NOT_TECHNICAL_FAILURE'):a.apply_assessment(root,body)
    assert not a.has_valid_operational_exclusion(current(root))


def test_stale_observation_hash_and_version_both_fail_closed(context):
    root,test,body=context
    body['approved']['expected_observation_hash']='0'*64
    with pytest.raises(a.AssessmentError,match='OBSERVATION_CHANGED'):a.apply_assessment(root,body)
    body['approved']['expected_observation_hash']=a.observation_hash(test)
    test['entity_version']=2;save(root,'entities/test/TEST-AUDIT.json',test)
    with pytest.raises(TowerAgentIssue,match='Entity version changed'):a.apply_assessment(root,body)
    assert current(root)==test


def test_concurrent_change_before_cas_is_rejected(context):
    root,_,body=context;mutate=AgentService.mutate
    def race(service,*args,**kwargs):
        test=current(root);test['entity_version']+=1
        save(root,'entities/test/TEST-AUDIT.json',test)
        return mutate(service,*args,**kwargs)
    with patch.object(AgentService,'mutate',race),pytest.raises(TowerAgentIssue,match='Entity version changed'):
        a.apply_assessment(root,body)
    assert 'execution_assessment' not in current(root)


def test_raw_serialized_mutation_cannot_write_or_remove_overlay(context):
    root,_,body=context
    with pytest.raises(TowerAgentIssue,match='requires verified runner'):
        AgentService(root).mutate('test','TEST-AUDIT',expected_version=1,changes={'execution_assessment':{}},writer_role='EXECUTOR',event_type='EXECUTION_OBSERVATION_ASSESSED')
    a.apply_assessment(root,body)
    with pytest.raises(TowerAgentIssue,match='requires verified runner'):
        AgentService(root).mutate('test','TEST-AUDIT',expected_version=2,changes={'execution_assessment':None},writer_role='EXECUTOR',event_type='EXECUTION_OBSERVATION_ASSESSED')


@pytest.mark.parametrize('source',['GITHUB','DRIVE','GATEWAY',''])
def test_only_internal_collector_can_submit_operation(context,source):
    root,_,body=context
    output,report=apply(root,body,source)
    assert report['rejected'][0]['reason']['code']=='VERIFIED_RUNNER_OBSERVATION_REQUIRED'
    assert 'execution_assessment' not in output['files']['entities/test/TEST-AUDIT.json']['value']


def test_trusted_operation_survives_packing_and_public_projection(context):
    root,_,body=context
    output,report=apply(root,body)
    assert not report['rejected'],report
    test=output['files']['entities/test/TEST-AUDIT.json']['value']
    assert a.public_assessment(test)
    a.apply_assessment(root,body)
    projection=build_public_projection(root,tower_revision='sha256:'+'a'*64)
    projected=next(t for t in projection['tests'] if t['id']=='TEST-AUDIT')
    assert projected['verdict']=='INCONCLUSIVE'
    assert projected['execution_assessment']==a.public_assessment(current(root))
    assert 'member_utf8' not in json.dumps(projection)
    assert 'archive_sha256' not in json.dumps(projected['execution_assessment'])


def test_tampered_or_unknown_overlay_does_not_exclude_other_records(context):
    root,test,body=context
    test['execution_assessment']={'contract':'UNKNOWN','scientific_result_eligible':False}
    assert a.public_assessment(test) is None and not a.has_valid_operational_exclusion(test)
    a.apply_assessment(root,body);test=current(root)
    test['execution_assessment']['evidence']['artifact_id']=999
    assert a.public_assessment(test) is None and not a.has_valid_operational_exclusion(test)


def test_learning_excludes_only_validated_technical_observations(context):
    root,test,body=context
    legitimate=copy.deepcopy(test);legitimate.update(id='LEGIT',decision='MIXED_TRACER_ROBUSTNESS')
    unknown=copy.deepcopy(legitimate);unknown['execution_assessment']={'contract':'UNKNOWN','scientific_result_eligible':False}
    a.apply_assessment(root,body)
    evaluated=discovery.learning_loop([current(root),legitimate,unknown])['evaluated']
    assert evaluated['cases']==2 and evaluated['excluded_operational']==1
    assert discovery.autonomy_metrics([current(root),legitimate,unknown])['metrics']['results']['numerator']==3


def test_unknown_existing_overlay_is_not_silently_replaced(context):
    root,test,body=context
    test['execution_assessment']={}
    save(root,'entities/test/TEST-AUDIT.json',test)
    with pytest.raises(a.AssessmentError,match='IMMUTABLE'):a.apply_assessment(root,body)
    assert current(root)==test


def test_first_accepted_overlay_survives_later_envelope_rollback(context):
    root,_,body=context
    raw=json.dumps(build_live_tower_payload(root)).encode()
    bad=copy.deepcopy(body);bad['source']['artifact_id']=999
    with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
        packed,report=apply_to_tower(raw,[
            {'nexo_operation':a.OPERATION,'_inbox_source':'RUNNER_OBSERVATION','assessment':body},
            {'nexo_operation':a.OPERATION,'_inbox_source':'RUNNER_OBSERVATION','assessment':bad}])
    assert len(report['rejected'])==1
    files=read_live_tower_bytes(packed)['files']
    test=files['entities/test/TEST-AUDIT.json']['value']
    assert a.public_assessment(test)
    events=[v['value'] for p,v in files.items() if p.startswith('events/') and v.get('value',{}).get('event_type')=='EXECUTION_OBSERVATION_ASSESSED']
    assert len(events)==1
