"""Failure observations release reservations without asserting scientific execution."""
from runtime.nexo_agent_api import evolution as e, scientific_integrity as s
from runtime.nexo_agent_api.inbox_apply import _result_request
from runtime.nexo_agent_api.tower_apply import apply_requests
from tests.test_scientific_integrity import install_fixture_catalog, store_fixture_test, save, NOW, END


def prepared(tmp_path,monkeypatch):
    root=tmp_path/'tower'
    install_fixture_catalog(tmp_path/'recipes',monkeypatch,'audit_recipe')
    save(root,'CONTROL.json',{'mode':'ACTIVE'})
    test=store_fixture_test(root,'TEST-RETRY')
    body={'battery_id':'bat-retry','tests':[{'test_id':test['id'],'recipe':test['recipe'],'params':test['recipe_params']}]}
    assert all(r['accepted'] for r in apply_requests(root,e.battery_requests({},body,root)))
    return root,test


def finish(root):
    body={'battery_id':'bat-retry','status':'DONE','run_ref':'actions/runs/123','completed_at':END,'conclusion':'failure',
          'results':[{'test_id':'TEST-RETRY','ok':False,'failure_stage':'PREPARE','log_tail':'failure before scientific execution'}]}
    return e.battery_status_requests({'_inbox_source':'RUNNER_OBSERVATION'},body,root,_result_request)


def test_failed_attempt_with_lost_inputs_closes_and_blocks_instead_of_staying_active(tmp_path,monkeypatch):
    root,original=prepared(tmp_path,monkeypatch)
    current=s.entity(root,original['id']);current.pop('data_binding')
    save(root,'entities/test/TEST-RETRY.json',current)
    receipts=apply_requests(root,finish(root))
    assert all(r['accepted'] for r in receipts),receipts
    after=s.entity(root,original['id'])
    assert s.batteries(root)[0]['status']=='DONE'
    assert not s.active_tests(root)
    assert after['status']==after['state']==after['execution_phase']=='BLOCKED_INPUT'
    assert after['readiness']['reasons']==['INPUT_PROVENANCE_INCOMPLETE']
    assert after['last_runtime_failure']['run_ref']=='actions/runs/123'
    assert after['last_runtime_failure']['at']==END
    assert after['last_runtime_failure']['failure_stage']=='PREPARE'
    assert all(after.get(k)==original.get(k) for k in (*s.FROZEN,'prereg_hash','verdict','executed_at','statistics'))
    assert finish(root)==[]


def test_legacy_reservation_without_attempt_is_closed_without_creating_one(tmp_path,monkeypatch):
    root,original=prepared(tmp_path,monkeypatch)
    battery=s.batteries(root)[0]
    for key in ('attempt_id','recipe_sha256','execution_fingerprint'):
        battery['tests'][0].pop(key,None)
    battery.update(status='DISPATCHED',run_ref='github-actions')
    save(root,e.BATTERIES_DOC,{'batteries':[battery]})
    current=s.entity(root,original['id'])
    for key in ('attempt_id','execution_recipe_sha256','data_binding'):current.pop(key,None)
    current.update(status='RUNNING',state='RUNNING')
    save(root,'entities/test/TEST-RETRY.json',current)
    receipts=apply_requests(root,finish(root))
    assert all(r['accepted'] for r in receipts),receipts
    after=s.entity(root,original['id']);closed=s.batteries(root)[0]
    assert closed['tests']==battery['tests']
    assert closed['status']=='DONE' and closed['failed']==1 and closed['ok']==0
    assert after['status']=='BLOCKED_INPUT'
    assert 'attempt_id' not in after and 'attempt_id' not in after['last_runtime_failure']
    assert 'executed_at' not in after and 'verdict' not in after


def test_prepared_failed_attempt_can_retry_only_with_real_readiness(tmp_path,monkeypatch):
    root,_=prepared(tmp_path,monkeypatch)
    receipts=apply_requests(root,finish(root))
    assert all(r['accepted'] for r in receipts),receipts
    after=s.entity(root,'TEST-RETRY')
    assert after['status']==after['execution_phase']=='READY'
    assert after['readiness']['eligible']
    assert len(e.family_battery_items(root))==1
