"""Synthetic protocol paths through the actual Writer. No astronomical inference."""
import copy,json
import pytest
from runtime.nexo_agent_api import enxame
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.live_tower import build_live_tower_payload
from runtime.nexo_agent_api.memory import Snapshot,documents,digest
from runtime.nexo_agent_api.retrieval import import_documents
from runtime.nexo_agent_api.inbox_client import prepare
AT='2026-10-07T12:00:00Z';SCOPE='RM-SYNTHETIC-PROTOCOL'
SPEC={k:'Synthetic software fixture: '+k for k in enxame.ESSENTIAL}
SPEC['requirements']={k:{'status':'NOT_APPLICABLE','reason':'Software fixture only; no astronomical inference.'} for k in enxame.DESIGN_FIELDS};SPEC['gaps']=[]
class Lab:
 def __init__(self,root):
  root.mkdir();self.root=root;self.n=0
  (root/'CONTROL.json').write_text(json.dumps({'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE'}))
  (root/'roadmaps').mkdir();(root/'roadmaps'/(SCOPE+'.json')).write_text(json.dumps({'id':SCOPE,'state':'ACTIVE','entity_version':1}))
  (root/'contracts').mkdir();(root/'contracts'/'SYNTHETIC.json').write_text(json.dumps({'purpose':'Synthetic protocol evidence'}))
  self.source={'path':'contracts/SYNTHETIC.json','sha256':digest(json.loads((root/'contracts'/'SYNTHETIC.json').read_text()))}
  self.raw=json.dumps(build_live_tower_payload(root)).encode()
 @property
 def tower(self):return json.loads(self.raw)
 def view(self):
  events=[v['value'] for p,v in self.tower['files'].items() if p.startswith(enxame.EVENT_ROOT+'/')]
  return enxame.derive(sorted(events,key=lambda e:e['sequence']))
 def apply(self,kind,role,payload):
  self.n+=1;ident='synthetic-intent-'+str(self.n)
  env={'kind':kind,'source':role,'intent_id':ident,'created_at':AT,'payload':payload};prepare(env,runtime_role=role,allowed_kinds={kind})
  raw,report=apply_to_tower(self.raw,[{**env,'_inbox_source':'DRIVE','_inbox_name':ident+'.json','_inbox_id':ident}])
  if raw:self.raw=raw
  return report
 def event(self,role,kind,body,cid='card-1',sv=None,eid=None):
  payload={'event_id':eid or 'synthetic-event-'+str(self.n+1),'event_type':kind,'scope_id':SCOPE,'scope_version':1,'card_id':cid,'expected_head':self.view()['head'],'body':body,'sources':[self.source]}
  if sv is not None:payload['spec_version']=sv
  return self.apply('ENXAME_EVENT',role,payload)
 def mature(self):
  for role,kind,body,sv in [('A1','CLAIM',{'claim':'Synthetic claim'},None),('A2','SPEC',{'spec':SPEC},1),('A3','ENDOSSO',{'rationale':'Adversarial fixture review'},1),('A1','ENDOSSO',{'rationale':'Claim preserved'},1)]:
   report=self.event(role,kind,body,sv=sv);assert not report['rejected'],report
 def freeze(self):return self.event('A5','FREEZE',{'spec_sha256':digest(SPEC)},sv=1)
 def register(self,proposed='caller-id'):
  return self.apply('ENXAME_REGISTER_TEST','A5',{'scope_id':SCOPE,'scope_version':1,'card_id':'card-1','spec_version':1,'spec_sha256':digest(SPEC),'expected_head':self.view()['head'],'proposed_test_id':proposed})
@pytest.fixture
def lab(tmp_path):return Lab(tmp_path/'tower')
def test_full_pipeline_unique_registry_and_explicit_readback(lab):
 lab.mature();assert not lab.freeze()['rejected'];report=lab.register();assert not report['rejected'],report
 tests=[v['value'] for k,v in lab.tower['files'].items() if k.startswith('entities/test/')];assert len(tests)==1;test=tests[0]
 assert test['status']=='DRAFT' and test['scientific_evidence']==[] and not test.get('verdict') and not test.get('recipe')
 assert test['prereg_hash'] and test['prereg_ref'] and not test['readiness']['eligible'] and test['preparation']['next_owner']=='ADVISOR'
 assert not lab.register('different-retry-id')['rejected'];assert len([k for k in lab.tower['files'] if k.startswith('entities/test/')])==1
 report=lab.event('A5','REGISTRO',{'test_id':test['id'],'readback':{'source_revision':lab.tower['revision'],'entity_version':test['entity_version'],'content_sha256':digest(test)}},sv=1);assert not report['rejected'],report
 assert lab.view()['cards']['card-1']['state']=='REGISTRADO' and not lab.view()['execution_triggered']
 assert not lab.event('A5','FIM',{},cid=None)['rejected'];assert lab.event('A1','CLAIM',{'claim':'Silent reopening forbidden'},cid='card-2')['rejected']
def test_spec_revision_invalidates_endorsements(lab):
 lab.mature();assert not lab.event('A2','SPEC',{'spec':{**SPEC,'question':'New synthetic question'}},sv=2)['rejected']
 assert lab.view()['cards']['card-1']['endorsements']=={};assert lab.freeze()['rejected']
def test_objection_only_resolved_by_author_accepting_current_response(lab):
 lab.mature();lab.event('A3','OBJECAO',{'text':'Synthetic uncontrolled dependency'},sv=1,eid='objection');assert lab.freeze()['rejected']
 lab.event('A2','RESPOSTA',{'objection_id':'objection','text':'Source-linked correction'},sv=1)
 assert lab.event('A1','ENDOSSO',{'rationale':'Cannot impersonate A3','resolves':['objection']},sv=1)['rejected']
 assert not lab.event('A3','ENDOSSO',{'rationale':'Accepted','resolves':['objection']},sv=1)['rejected'];assert not lab.freeze()['rejected']
def test_partial_spec_cannot_freeze(lab):
 lab.event('A1','CLAIM',{'claim':'Synthetic'});lab.event('A2','SPEC',{'spec':{'question':'Partial','gaps':['input catalog']}},sv=1)
 lab.event('A3','ENDOSSO',{'rationale':'Partial review'},sv=1);lab.event('A1','ENDOSSO',{'rationale':'Claim corresponds'},sv=1)
 assert lab.freeze()['rejected'];assert 'input catalog' in lab.view()['cards']['card-1']['gaps']
def test_event_retry_and_changed_payload(lab):
 p={'event_id':'stable','event_type':'CLAIM','scope_id':SCOPE,'scope_version':1,'card_id':'card-1','expected_head':None,'body':{'claim':'Synthetic'},'sources':[lab.source]}
 assert not lab.apply('ENXAME_EVENT','A1',p)['rejected'];assert not lab.apply('ENXAME_EVENT','A1',p)['rejected'];assert len(lab.view()['events'])==1
 changed=copy.deepcopy(p);changed['body']['claim']='Changed';assert lab.apply('ENXAME_EVENT','A1',changed)['rejected'];assert len(lab.view()['events'])==1
def test_registration_rejects_asserted_pass_without_readback(lab):
 lab.mature();lab.freeze();lab.register();tid=next(v['value']['id'] for k,v in lab.tower['files'].items() if k.startswith('entities/test/'))
 assert lab.event('A5','REGISTRO',{'test_id':tid,'readback':'PASS'},sv=1)['rejected'];assert lab.view()['cards']['card-1']['registration'] is None
def test_role_source_hash_and_version_are_enforced(lab):
 assert lab.event('A4','CLAIM',{'claim':'Not A1'})['rejected'];lab.event('A1','CLAIM',{'claim':'Synthetic'});assert lab.event('A2','SPEC',{'spec':SPEC},sv=5)['rejected']
 p={'event_id':'bad-source','event_type':'SPEC','scope_id':SCOPE,'scope_version':1,'card_id':'card-1','spec_version':1,'expected_head':lab.view()['head'],'body':{'spec':SPEC},'sources':[{**lab.source,'sha256':'0'*64}]};assert lab.apply('ENXAME_EVENT','A2',p)['rejected']
@pytest.mark.parametrize('scope',['PERSONAL','WORK','SCIENCE','CLIENT:SYNTHETIC'])
def test_memory_history_and_scope_isolation(lab,scope):
 p={'event_id':'preference','scope':scope,'category':'USER_PREFERENCE','text':'Synthetic preference','sources':[]};assert not lab.apply('NEXO_MEMORY_ENTRY','DENER',p)['rejected']
 first=next(v['value'] for v in lab.tower['files'].values() if v.get('value',{}).get('kind')=='NEXO_MEMORY_ENTRY')
 correction={**p,'event_id':'correction','text':'Corrected','supersedes_record_id':first['id']};assert not lab.apply('NEXO_MEMORY_ENTRY','DENER',correction)['rejected'];assert not lab.apply('NEXO_MEMORY_ENTRY','DENER',correction)['rejected']
 assert lab.apply('NEXO_MEMORY_ENTRY','DENER',{**correction,'scope':'WORK' if scope!='WORK' else 'PERSONAL','event_id':'cross-scope'})['rejected']
 records=[v['value'] for v in lab.tower['files'].values() if v.get('value',{}).get('kind')=='NEXO_MEMORY_ENTRY'];assert len(records)==2 and all(r['private'] and r['allowed_roles']==[] and r['payload']['scientific_authority'] is False for r in records)
def test_project_material_progress_evidence_and_retry(lab):
 p={'event_id':'create','project_id':'general','title':'Synthetic document','scope':'WORK','action':'CREATED','text':'Simple project','expected_previous':None,'sources':[]};report=lab.apply('NEXO_PROJECT_EVENT','CHATGPT',p);assert not report['rejected'],report
 assert not lab.apply('NEXO_PROJECT_EVENT','CHATGPT',p)['rejected'];first=next(v['value']['id'] for v in lab.tower['files'].values() if v.get('value',{}).get('kind')=='NEXO_PROJECT_EVENT')
 progress={**p,'event_id':'progress','action':'PROGRESS','expected_previous':first,'text':'Material progress'};assert lab.apply('NEXO_PROJECT_EVENT','CHATGPT',progress)['rejected'];progress['sources']=[lab.source]
 assert not lab.apply('NEXO_PROJECT_EVENT','CHATGPT',progress)['rejected'];assert not lab.apply('NEXO_PROJECT_EVENT','CHATGPT',progress)['rejected']
def test_private_human_principal_does_not_abort_other_documents(tmp_path):
 root=tmp_path/'root';root.mkdir();(root/'CONTROL.json').write_text(json.dumps({'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE'}));(root/'evolution').mkdir();(root/'evolution'/'board.json').write_text(json.dumps({'posts':[{'id':'human','private':True,'to':'DENER','text':'Private owner fixture'},{'id':'agent','private':True,'to':'LEARNER','text':'Agent fixture'}]}));p=tmp_path/'tower.json';p.write_text(json.dumps(build_live_tower_payload(root)))
 for importer in (documents,import_documents):
  docs,_=importer(Snapshot.read(p));assert next(d for d in docs if d.object_id=='human').allowed_roles==[];assert next(d for d in docs if d.object_id=='agent').allowed_roles==['LEARNER']
def test_unknown_typed_identifier_abstains_instead_of_fuzzy_substitution(lab,tmp_path):
 from runtime.nexo_agent_api.retrieval import Retrieval
 (lab.root/'entities/test').mkdir(parents=True,exist_ok=True)
 (lab.root/'entities/test/T-KNOWN.json').write_text(json.dumps({'id':'T-KNOWN','kind':'TEST','status':'DRAFT','question':'TEST::DOES-NOT-EXIST appears in untrusted source text.'}))
 path=tmp_path/'snapshot.json';path.write_text(json.dumps(build_live_tower_payload(lab.root)))
 engine=Retrieval(tmp_path/'cache.db');engine.sync(Snapshot.read(path))
 for query in ('T-NONEXISTENT','TEST::DOES-NOT-EXIST','DATASET::missing-20261007'):
  answer=engine.search(query,'LEARNER');assert answer['mode']=='exact' and not answer['hits']
