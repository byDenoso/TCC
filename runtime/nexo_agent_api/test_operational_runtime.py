"""Operational conformance: actual recipe/Writer; fake external I/O."""
from __future__ import annotations
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from runtime.nexo_agent_api.operational_control import (
    INTENT, REPOSITORY, SCOPE, WORKFLOW, OperationalError, OperationalWorker,
    TowerWriterStore, digest, initialize_work, role_context, run_frozen,
    validate_definition, verify_run, require, apply_to_tower,
)
from runtime.nexo_agent_api.operational_prompts import PROMPTS
from runtime.nexo_agent_api.operational_bootstrap import canonical_config, freeze_rollout
from runtime.nexo_agent_api.operational_transports import BoundedDrive, verified_result_archive
from runtime.nexo_agent_api.live_tower import publish_live_tower, LIVE_TOWER_NAME, read_live_tower_bytes, verify_live_tower

RECIPE = (Path(__file__).parents[1] / 'nexo_execution/operational_sum.py').read_bytes()
DATA = b'{"contract":"NEXO_DRIVE_OPERATIONAL_CONTROL_V1","values":[1,2,3]}\n'
INPUT = {'source_storage':'GOOGLE_DRIVE_PRIVATE','file_id':'1Cr7L6bbVlOqB0HUvYett0xkhRS-NWRWr',
         'version':'0B9ZwoXbzaIA-dURSU09VT3BkanJvNlBlSDN5RjZUTUFOYnVRPQ','sha256':digest(DATA)}
WORK_ID = 'OPERATIONAL-CONTROL-DRIVE-SUM-V1'
PRINCIPAL = 'a'*64


def definition(identity=WORK_ID):
    return {'id':identity,'role':'EXECUTOR','scope':SCOPE,'scientific_result_eligible':False,
            'recipe':{'id':'drive-sum-mean-v1','sha256':digest(RECIPE),
                      'drive':{'file_id':'unit-recipe','version':'unit-revision','sha256':digest(RECIPE)}},
            'input':copy.deepcopy(INPUT),'known_result':{'count':3,'sum':6,'mean':2},
            'code':{'repository':REPOSITORY,'sha':'b'*40,'files':{WORKFLOW:'c'*64,'scripts/nexo_operational_package.py':'d'*64}},
            'destinations':{'packages':'unit-packages','results':'unit-results'}}


class LocalTower:
    def __init__(self):
        self.writes = 0
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'CONTROL.json').write_text(json.dumps({'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE',
                                                       'write_model':'IN_PLACE_FILE_REVISION_CAS_READBACK'}))
            publish_live_tower(root)
            self.raw = (root/LIVE_TOWER_NAME).read_bytes()
    def download(self,cache=False):return self.raw,self.raw
    def compare_and_swap(self,head,raw):
        require(head==self.raw,'UNIT_CAS_CONFLICT')
        verify_live_tower(read_live_tower_bytes(raw))
        self.raw=raw;self.writes+=1
        return {'readback':'PASS'}


class MemoryDrive:
    def __init__(self):self.files={INPUT['file_id']:DATA};self.writes=0;self.error=None
    def read_frozen(self,reference):
        if self.error:raise self.error
        raw=self.files[reference['file_id']]
        require(digest(raw)==reference['sha256'],'DRIVE_BODY_HASH_MISMATCH')
        return raw
    def put_immutable(self,parent,name,raw):
        key=parent+'/'+name
        if key in self.files:require(self.files[key]==raw,'IMMUTABLE_CONTENT_CONFLICT')
        else:self.files[key]=raw;self.writes+=1
        return {'file_id':key,'version':'unit-revision','parent_id':parent,'sha256':digest(raw)}


class FakeActions:
    def __init__(self,drive):self.drive=drive;self.runs=[];self.dispatches=0;self.timeout=False;self.tamper=False
    def preflight(self,work):return work['definition']['code']['sha']
    def find_runs(self,work):return copy.deepcopy(self.runs)
    def dispatch(self,work):
        self.dispatches+=1
        self.runs=[{'id':123456,'run_attempt':1,'repository':{'full_name':REPOSITORY},
                    'head_repository':{'full_name':REPOSITORY},'head_branch':'main',
                    'head_sha':work['outbox']['execution_sha'],'path':WORKFLOW,'event':'workflow_dispatch',
                    'status':'completed','conclusion':'success','display_title':'nexo-op-'+work['outbox']['key']}]
        if self.timeout:raise TimeoutError('Unit test: accepted POST, response lost')
    def get_run(self,identity):return copy.deepcopy(self.runs[0])
    def result(self,run,work):
        package=json.loads(self.drive.read_frozen(work['package']))
        result=run_frozen(package,work['package']['sha256'],DATA,RECIPE)
        result['executed_at']='2026-10-03T00:00:00Z'
        if self.tamper:result['result']['sum']=999
        return result


class Rig:
    def __init__(self,definitions=None):
        self.tower=LocalTower();self.store=TowerWriterStore(self.tower);self.drive=MemoryDrive();self.actions=FakeActions(self.drive)
        self.worker=OperationalWorker(self.store,self.drive,self.actions,recipe_loader=lambda _:RECIPE)
        for item in definitions or [definition()]:self.store.save(initialize_work(item),0)
    def intent(self,action='request_execution',identity=WORK_ID,principal=PRINCIPAL):
        work=self.store.get(identity)
        body={'contract':INTENT,'action':action,'work_id':identity,'principal':principal,
              'role_session':role_context(work,PROMPTS[work['role']]),'expected_version':work['version']}
        return {**body,'id':'op-'+digest(body)[:48]}
    def complete(self):
        self.worker.tick([self.intent()]);self.worker.tick([])
        return self.store.get(WORK_ID)


class OperationalConformance(unittest.TestCase):
    def test_one_request_executes_actual_recipe_and_actual_writer(self):
        rig=Rig();work=rig.complete()
        self.assertEqual(work['state'],'REGISTERED');self.assertEqual(work['receipt']['readback'],'PASS')
        self.assertEqual(work['result']['body']['result'],{'count':3,'sum':6.0,'mean':2.0,'known_result_matched':True})
        files=read_live_tower_bytes(rig.tower.raw)['files']
        self.assertFalse(any(name.startswith('entities/test/') for name in files))
        receipts=[v['value'] for v in files.values() if v.get('value',{}).get('kind')=='OPERATIONAL_RECEIPT']
        self.assertEqual(len(receipts),1);self.assertIs(receipts[0]['payload']['scientific_result_eligible'],False)
    def test_repeat_is_idempotent_and_does_not_dispatch_twice(self):
        rig=Rig();intent=rig.intent();rig.worker.tick([intent]);rig.worker.tick([intent]);writes=rig.tower.writes
        result=rig.worker.handle(intent)
        self.assertTrue(result['idempotent']);self.assertEqual(rig.tower.writes,writes);self.assertEqual(rig.actions.dispatches,1)
    def test_lost_post_response_reconciles_existing_run(self):
        rig=Rig();rig.actions.timeout=True;rig.worker.tick([rig.intent()]);rig.worker.tick([])
        self.assertEqual(rig.store.get(WORK_ID)['state'],'REGISTERED');self.assertEqual(rig.actions.dispatches,1)
    def test_bad_hash_blocks_only_its_item(self):
        bad=definition('OPERATIONAL-CONTROL-BAD-HASH');bad['input']['sha256']='f'*64
        rig=Rig([bad,definition()]);rig.worker.tick([rig.intent(identity=bad['id']),rig.intent()]);rig.worker.tick([])
        self.assertEqual(rig.store.get(bad['id'])['state'],'BLOCKED');self.assertEqual(rig.store.get(WORK_ID)['state'],'REGISTERED')
    def test_missing_recipe_blocks_only_its_item(self):
        bad=definition('OPERATIONAL-CONTROL-MISSING');bad['recipe']['drive']=None
        rig=Rig([bad,definition()]);rig.worker.tick([rig.intent()]);rig.worker.tick([])
        self.assertEqual(rig.store.get(bad['id'])['state'],'BLOCKED');self.assertEqual(rig.store.get(WORK_ID)['state'],'REGISTERED')
    def test_operational_control_does_not_need_approval_metadata(self):
        item=definition();self.assertNotIn('review',item);validate_definition(item)
    def test_scientific_work_is_not_implicitly_enabled(self):
        item=definition();item['scope']='SCIENCE'
        with self.assertRaisesRegex(OperationalError,'SCIENCE_NOT_ADMITTED'):validate_definition(item)
    def test_arbitrary_recipe_with_matching_hash_is_not_allowlisted(self):
        item=definition();item['recipe']['sha256']='f'*64
        with self.assertRaisesRegex(OperationalError,'RECIPE_HASH_NOT_ALLOWLISTED'):validate_definition(item)
    def test_private_input_cannot_be_substituted(self):
        item=definition();item['input']['file_id']='another-private-file'
        with self.assertRaisesRegex(OperationalError,'INPUT_NOT_ALLOWLISTED'):validate_definition(item)
    def test_changed_known_result_is_not_a_passing_criterion(self):
        item=definition();item['known_result']['sum']=7
        with self.assertRaisesRegex(OperationalError,'KNOWN_RESULT'):validate_definition(item)
    def test_second_claim_cannot_destroy_owner_work(self):
        rig=Rig();rig.worker.handle(rig.intent('claim_work'));out=rig.worker.handle(rig.intent('claim_work',principal='b'*64))
        self.assertEqual(out['state'],'WORK_ALREADY_CLAIMED');self.assertEqual(rig.store.get(WORK_ID)['owner'],PRINCIPAL)
    def test_stale_version_does_not_mutate(self):
        rig=Rig();old=rig.intent();rig.worker.handle(rig.intent('claim_work'));writes=rig.tower.writes
        self.assertEqual(rig.worker.handle(old)['state'],'VERSION_CONFLICT');self.assertEqual(rig.tower.writes,writes)
    def test_forged_prompt_context_rejected_before_side_effect(self):
        rig=Rig();intent=rig.intent();intent['role_session']['context_sha256']='f'*64
        intent['id']='op-'+digest({k:v for k,v in intent.items() if k!='id'})[:48]
        with self.assertRaisesRegex(OperationalError,'CONTEXT_OR_PROMPT'):rig.worker.handle(intent)
        self.assertEqual(rig.actions.dispatches,0);self.assertEqual(rig.drive.writes,0)
    def test_retryable_input_failure_preserves_intent_version(self):
        rig=Rig();intent=rig.intent();rig.drive.error=OperationalError('DRIVE_TEMPORARY_FAILURE',retryable=True)
        rig.worker.handle(intent);self.assertEqual(rig.store.get(WORK_ID)['version'],intent['expected_version'])
        rig.drive.error=None;rig.worker.tick([intent]);rig.worker.tick([]);self.assertEqual(rig.store.get(WORK_ID)['state'],'REGISTERED')
    def test_wrong_run_origin_and_commit_never_register(self):
        for key,value in [('head_branch','feature'),('head_sha','f'*40),('event','pull_request'),('conclusion','failure')]:
            with self.subTest(key=key):
                rig=Rig();rig.worker.tick([rig.intent()]);run=copy.deepcopy(rig.actions.runs[0]);run[key]=value
                with self.assertRaises(OperationalError):verify_run(run,rig.store.get(WORK_ID))
    def test_result_hash_tamper_blocks_recording(self):
        rig=Rig();rig.actions.tamper=True;rig.worker.tick([rig.intent()]);rig.worker.tick([])
        self.assertEqual(rig.store.get(WORK_ID)['state'],'BLOCKED');self.assertIsNone(rig.store.get(WORK_ID)['receipt'])
    def test_dedicated_input_reader_does_not_use_writer_for_fixture(self):
        rig=Rig();observed=[]
        def reader(reference):observed.append(reference['file_id']);return DATA
        original=rig.drive.read_frozen
        def writer(reference):
            self.assertNotEqual(reference['file_id'],INPUT['file_id']);return original(reference)
        rig.drive.read_frozen=writer;rig.worker.input_loader=reader
        rig.worker.handle(rig.intent());self.assertEqual(observed,[INPUT['file_id'],INPUT['file_id']])
    def test_subprocess_environment_has_no_inherited_credential(self):
        rig=Rig();import runtime.nexo_agent_api.operational_control as control
        original=control.subprocess.run
        def checked(*args,**kwargs):
            self.assertEqual(kwargs['env'],{'LANG':'C.UTF-8'});return original(*args,**kwargs)
        with patch.object(control.subprocess,'run',side_effect=checked):rig.complete()
    def test_canonical_config_installs_once_and_never_overwrites(self):
        tower=LocalTower();store=TowerWriterStore(tower);config={'contract':'NEXO_OPERATIONAL_RUNTIME_V1','enabled':False}
        self.assertEqual(store.install_config(config),config);writes=tower.writes
        self.assertEqual(store.install_config({'changed':True}),config);self.assertEqual(writes,tower.writes)
        self.assertEqual(canonical_config(read_live_tower_bytes(tower.raw)),config)
    def test_raw_gateway_cannot_install_operational_config(self):
        tower=LocalTower();request={'request_id':'unit-forged-config','entity_kind':'artifact',
          'entity_name':'OPERATIONAL-CONTROL-RUNTIME-V1','expected_version':0,'writer_role':'LEARNER',
          'event_type':'OPERATIONAL_RUNTIME_INSTALLED','material':True,
          'changes':{'kind':'NEXO_OPERATIONAL_RUNTIME_V1','status':'RECORDED','payload':{'enabled':True}}}
        _,report=apply_to_tower(tower.raw,[request]);self.assertFalse(report.get('applied'))
    def test_rollout_outside_main_writer_fails_before_git(self):
        with self.assertRaisesRegex(OperationalError,'SINGLETON_WRITER'):freeze_rollout({},Path('.'),{})
    def test_artifact_wrong_archive_hash_and_traversal_rejected(self):
        rig=Rig();rig.worker.tick([rig.intent()]);work=rig.store.get(WORK_ID);run=rig.actions.runs[0]
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as archive:archive.writestr('../result.json',b'{}')
        raw=b.getvalue();metadata={'workflow_run':{'id':run['id'],'head_sha':run['head_sha']},
          'name':f"operational-result-{run['id']}-1",'expired':False,'digest':'sha256:'+digest(raw)}
        with self.assertRaisesRegex(OperationalError,'MEMBERS_INVALID'):verified_result_archive(raw,metadata,run,work)
        metadata['digest']='sha256:'+'0'*64
        with self.assertRaisesRegex(OperationalError,'DIGEST_MISMATCH'):verified_result_archive(raw,metadata,run,work)
    def test_drive_root_is_never_an_allowed_destination(self):
        with self.assertRaisesRegex(OperationalError,'ROOT_WRITE_FORBIDDEN'):BoundedDrive(object(),allowed_folders={'root'})


if __name__=='__main__':unittest.main()
