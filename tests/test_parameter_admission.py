"""Catalog preflight commitment and typed operational failure integration."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from runtime.nexo_agent_api import evolution as e, scientific_integrity as s
from runtime.nexo_agent_api import parameter_admission as p
from runtime.nexo_agent_api.execution_recovery import _route
from runtime.nexo_agent_api.inbox_apply import ProposalError, _result_request
from runtime.nexo_agent_api.tower_apply import apply_requests
from tests.test_scientific_integrity import install_fixture_catalog, store_fixture_test, save, NOW, END

VALIDATOR = '''import hashlib,json
from pathlib import Path
def validate_params(recipe, params, inputs, recipe_root):
    manifest=Path(recipe_root)/'preflight'/(recipe+'.json')
    reasons=[] if params.get('seed')==17 else ['DATA_RELEASE_PARAM_MISMATCH']
    return {'contract':'RECIPE_PARAM_PREFLIGHT_V1','eligible':not reasons,'reasons':reasons,
            'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
'''


@pytest.fixture
def context(tmp_path, monkeypatch):
    root=tmp_path/'tower'; recipes=tmp_path/'recipes'
    install_fixture_catalog(recipes,monkeypatch,'audit_recipe','w0wa_bao_sn_multi')
    save(root,'CONTROL.json',{'mode':'ACTIVE','truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE'})
    save(recipes,'preflight/audit_recipe.json',{'contract':p.CONTRACT})
    (recipes/'recipe_param_preflight.py').write_text(VALIDATOR)
    test=store_fixture_test(root,'TEST-PARAM')
    return root,recipes,test


def reserve(context):
    root,recipes,test=context
    body={'battery_id':'bat-param','tests':[{'test_id':test['id'],'recipe':test['recipe'],'params':test['recipe_params']}]}
    requests=e.battery_requests({'created_at':NOW},body,root)
    receipts=apply_requests(root,requests)
    assert all(r['accepted'] for r in receipts),receipts
    return s.batteries(root)[0]


def completion(context,entry):
    root,_,test=context
    current=s.entity(root,test['id'])
    if current.get('status') != 'RUNNING' or current.get('execution_phase') != 'RUNNING':
        start=e.battery_status_requests({'_inbox_source':'RUNNER_OBSERVATION','created_at':NOW},
            {'battery_id':'bat-param','status':'RUNNING','run_ref':'actions/runs/123',
             'started_tests':{test['id']:NOW}},root,_result_request)
        receipts=apply_requests(root,start)
        assert all(r.get('accepted',True) for r in receipts),receipts
    return e.battery_status_requests({'_inbox_source':'RUNNER_OBSERVATION'},
        {'battery_id':'bat-param','status':'DONE','run_ref':'actions/runs/123','completed_at':END,
         'conclusion':'success','results':[entry]},root,_result_request)


def test_required_recipe_fails_closed_without_manifest(context):
    root,recipes,test=context
    test.update(recipe='w0wa_bao_sn_multi')
    check=s.readiness(root,test)
    assert not check['eligible']
    assert 'PREFLIGHT_CONTRACT_MISSING' in check['reasons']
    assert check['recipe_scope']=='VERSIONED_PARAMETER_PREFLIGHT'


def test_unmigrated_recipe_retains_explicit_weaker_scope(context):
    root,recipes,test=context
    (recipes/'preflight/audit_recipe.json').unlink()
    check=s.readiness(root,test)
    assert check['eligible']
    assert check['recipe_scope']=='SYNTAX_AND_SMOKE_SPEC_PRESENT'
    assert 'param_preflight' not in check


def test_parameter_rejection_reaches_queue_and_recovery_route(context):
    root,recipes,test=context
    test['recipe_params']={'seed':18}
    save(root,'entities/test/TEST-PARAM.json',test)
    check=s.readiness(root,test)
    assert not check['eligible']
    assert check['reasons']==['DATA_RELEASE_PARAM_MISMATCH']
    assert e.family_battery_items(root)==[]
    assert _route(check['reasons'])[0]=='LEARNER'
    assert _route(['PREFLIGHT_CONTRACT_MISSING'])[0]=='ADVISOR'


@pytest.mark.parametrize('code', [
    'UNSUPPORTED_COMPILATIONS', 'UNSUPPORTED_DATA_RELEASE', 'UNSUPPORTED_RECIPE_MODE',
    'UNSUPPORTED_RECIPE_PARAMS', 'UNUSED_RECIPE_PARAMS', 'RECIPE_PARAMS_INVALID',
    'RECIPE_PRIORS_INVALID', 'RECIPE_HOLDOUTS_INVALID', 'FROZEN_RECIPE_PARAMS_MISMATCH',
])
def test_frozen_parameter_errors_route_to_scientist_before_input_or_recipe_repair(code):
    role, action = _route([code, 'INPUT_PROVENANCE_INCOMPLETE', 'RECIPE_BINDING_MISSING'])
    assert role == 'LEARNER'
    assert 'Preservar os parâmetros congelados' in action


def test_verified_receipt_is_committed_at_reservation(context):
    root,recipes,test=context
    check=s.readiness(root,test)
    assert check['eligible']
    battery=reserve(context);spec=battery['tests'][0]
    assert spec['param_preflight']==check['param_preflight']
    assert spec['execution_fingerprint']==s.execution_fingerprint(test,check['recipe_sha256'],check['param_preflight'])
    assert len(spec['param_preflight']['validator_sha256'])==64


def test_validator_or_manifest_byte_changes_change_execution_identity(context):
    root,recipes,test=context
    before=s.readiness(root,test)
    first=s.execution_fingerprint(test,before['recipe_sha256'],before['param_preflight'])
    with (recipes/'recipe_param_preflight.py').open('a') as h:h.write('\n# revised validator\n')
    revised=s.readiness(root,test)
    second=s.execution_fingerprint(test,revised['recipe_sha256'],revised['param_preflight'])
    save(recipes,'preflight/audit_recipe.json',{'contract':p.CONTRACT,'version':2})
    manifest=s.readiness(root,test)
    third=s.execution_fingerprint(test,manifest['recipe_sha256'],manifest['param_preflight'])
    assert len({first,second,third})==3


def test_stale_preflight_cannot_commit_reservation(context):
    root,recipes,test=context
    body={'battery_id':'bat-param','tests':[{'test_id':test['id'],'recipe':test['recipe'],'params':test['recipe_params']}]}
    requests=e.battery_requests({},body,root)
    with (recipes/'recipe_param_preflight.py').open('a') as h:h.write('\n# changed after preparing reservation\n')
    rejected=s.guard_batteries(root,requests[0])
    assert rejected['issue']['code']=='PARAM_PREFLIGHT_RESERVATION_MISMATCH'
    assert s.batteries(root)==[]


@pytest.mark.parametrize('change,reason',[
    ("'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()",'PREFLIGHT_RECEIPT_HASH_MISMATCH'),
    ("'eligible':not reasons",'PREFLIGHT_VALIDATOR_ERROR'),
])
def test_invalid_validator_receipt_fails_closed(context,change,reason):
    root,recipes,test=context
    replacement="'manifest_sha256':'wrong'" if 'manifest_sha256' in change else "'eligible':'yes'"
    (recipes/'recipe_param_preflight.py').write_text(VALIDATOR.replace(change,replacement))
    check=s.readiness(root,test)
    assert not check['eligible']
    assert reason in check['reasons']


def test_validator_exception_is_structured(context):
    root,recipes,test=context
    (recipes/'recipe_param_preflight.py').write_text('raise RuntimeError("broken validator")')
    assert s.readiness(root,test)['reasons']==['PREFLIGHT_VALIDATOR_ERROR']


def test_successful_receipt_must_match_reserved_preflight(context):
    root,_,_=context;spec=reserve(context)['tests'][0]
    entry={'test_id':'TEST-PARAM','ok':True,'attempt_id':spec['attempt_id'],'recipe_sha256':spec['recipe_sha256'],
           'result':{'verdict':'INCONCLUSIVE','summary':'Actual isolated result'},'param_preflight':spec['param_preflight']}
    assert completion(context,entry)
    for invalid in (None,{**spec['param_preflight'],'validator_sha256':'f'*64},{**spec['param_preflight'],'eligible':False}):
        with pytest.raises(ProposalError,match='RESULT_PARAM_PREFLIGHT_MISMATCH'):
            completion(context,{**entry,'param_preflight':invalid})


def test_operational_input_failure_records_blocker_without_scientific_result(context):
    root,_,test=context;spec=reserve(context)['tests'][0]
    entry={'test_id':test['id'],'ok':False,'attempt_id':spec['attempt_id'],'recipe_sha256':spec['recipe_sha256'],
           'operational_status':'INPUT_UNAVAILABLE','operational_reason':'DATA_RELEASE_PARAM_MISMATCH',
           'failure_stage':'PARAM_PREFLIGHT','param_preflight':{**spec['param_preflight'],'eligible':False,'reasons':['DATA_RELEASE_PARAM_MISMATCH']}}
    receipts=apply_requests(root,completion(context,entry))
    assert all(r['accepted'] for r in receipts),receipts
    current=s.entity(root,test['id'])
    assert current['status']=='BLOCKED_INPUT'
    assert current['blocker']=='RUNTIME_INPUT_UNAVAILABLE:DATA_RELEASE_PARAM_MISMATCH'
    for key in ('executed_at','verdict','result','statistics'):
        assert key not in current
    assert current['prereg_hash']==test['prereg_hash']
    assert not s.readiness(root,current)['eligible']
    assert completion(context,entry)==[]


@pytest.mark.parametrize('changes',[
    {'ok':True}, {'result':{'verdict':'INCONCLUSIVE'}}, {'attempt_id':'other'},
    {'recipe_sha256':'f'*64}, {'operational_reason':'free form error'},
])
def test_operational_failure_cannot_smuggle_result_or_wrong_attempt(context,changes):
    spec=reserve(context)['tests'][0]
    entry={'test_id':'TEST-PARAM','ok':False,'attempt_id':spec['attempt_id'],'recipe_sha256':spec['recipe_sha256'],
           'operational_status':'INPUT_UNAVAILABLE','operational_reason':'DATA_RELEASE_PARAM_MISMATCH',**changes}
    with pytest.raises(ProposalError):completion(context,entry)


def test_legacy_reserved_attempt_can_finish_without_retroactive_preflight(context):
    root,recipes,test=context
    (recipes/'preflight/audit_recipe.json').unlink()
    spec=reserve(context)['tests'][0]
    assert 'param_preflight' not in spec
    save(recipes,'preflight/audit_recipe.json',{'contract':p.CONTRACT})
    entry={'test_id':'TEST-PARAM','ok':True,'attempt_id':spec['attempt_id'],'recipe_sha256':spec['recipe_sha256'],
           'result':{'verdict':'INCONCLUSIVE','summary':'Legacy reservation result'}}
    assert completion(context,entry)
