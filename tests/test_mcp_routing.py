"""Synthetic proofs exercise the Writer; none represents a real MCP canary."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from runtime.nexo_agent_api import autonomy,mcp_routing as routing
from runtime.nexo_agent_api.control_compat import control_from_bundle,prepare_migration
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.inbox_apply import ProposalError,proposal_to_requests
from runtime.nexo_agent_api.live_tower import build_live_tower_payload,materialize_live_tower
from runtime.nexo_agent_api.memory import Snapshot,digest
from runtime.nexo_agent_api.pulse_context import prepare_context
from runtime.nexo_agent_api.tower_apply import apply_document

ENDPOINT='https://mcp.example.test/mcp'
OBSERVED='2026-10-13T01:00:00Z'
AT='2026-10-13T02:00:00Z'


class McpRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.work=Path(self.tmp.name)
        root=self.work/'tower';root.mkdir()
        self.control={'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE',
                      'write_model':'IN_PLACE_FILE_REVISION_CAS_READBACK',
                      'hosted_mcp_current_endpoint':'https://legacy.example.test/mcp',
                      'hosted_mcp_current_storage_backend':'LEGACY_NONCANONICAL_GITHUB_BACKEND',
                      'hosted_mcp_cutover_requirements':['DIRECT_CHATGPT_CANARY_PASS','CANONICAL_STATE_TOOL_PARITY'],
                      'hosted_mcp_migration_target':'DRIVE_NATIVE_MCP_SPEC__STATELESS_EXECUTOR',
                      'mcp_runtime_model':'STATELESS_EXECUTOR_READS_DRIVE',
                      'mcp_spec_storage':'GOOGLE_DRIVE_PRIVATE','mcp_tower_resolution':'STABLE_FILE_ID',
                      'mcp_tool_routes':{'executor_tool':'https://old-operational.example.test/mcp'},
                      'autonomy_mandate':{'status':'PREPARED_INACTIVE'}}
        (root/'CONTROL.json').write_text(json.dumps(self.control))
        (root/'entities/artifact').mkdir(parents=True)
        (root/'entities/artifact/SCIENCE.json').write_text(json.dumps({'id':'SCIENCE','payload':{'frozen':[1,2,3]}}))
        self.raw=json.dumps(build_live_tower_payload(root,updated_at=OBSERVED)).encode()
        path=self.work/'snapshot.json';path.write_bytes(self.raw);self.snapshot=Snapshot.read(path)
        tools=[{'name':name,'inputSchema':{'type':'object','properties':{}},
                'annotations':{'readOnlyHint':True,'destructiveHint':False}} for name in sorted(routing.TOOLS)]
        self.catalog={'endpoint':ENDPOINT,'source_file_id':routing.SOURCE_ID,'role':'LEARNER',
                      'tools':tools,'sha256':digest(tools),'observed_at':OBSERVED}
        self.canary={'runtime':'CHATGPT_CONNECTED_MCP','endpoint':ENDPOINT,'source_file_id':routing.SOURCE_ID,
                     'role':'LEARNER','tool':'nexo_capabilities','catalog_sha256':self.catalog['sha256'],
                     'observed_at':OBSERVED,'receipt_ref':'SYNTHETIC_TEST_ONLY','readback':'PASS'}
        self.capabilities={'status':'AUTHENTICATED','roles':['LEARNER'],
                           'source_mode':'DRIVE_REVISION_VERIFIED_PRIVATE_SCOPED_D1',
                           'source':{'source_id':routing.SOURCE_ID,'revision':self.snapshot.revision,
                                     'source_sha256':self.snapshot.raw_sha256},
                           'authorization_revision':self.snapshot.revision,
                           'read_only':True,'writes_enabled':False,'external_model_calls':False,
                           'other_runtimes_authorized':False,'connection_scope':'this_authenticated_runtime_only',
                           'supported_tools':sorted(routing.TOOLS),
                           'validity_start':'2026-10-13T00:00:00Z','validity_end':'2026-10-14T00:00:00Z'}
        self.canary.update(capabilities=self.capabilities,capabilities_sha256=digest(self.capabilities))
        clock=patch.object(routing,'_now',return_value=datetime.fromisoformat(AT.replace('Z','+00:00')))
        clock.start();self.addCleanup(clock.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def envelope(self,snapshot=None):
        snapshot=snapshot or self.snapshot
        canary=copy.deepcopy(self.canary)
        canary['capabilities']['source'].update(revision=snapshot.revision,source_sha256=snapshot.raw_sha256)
        canary['capabilities']['authorization_revision']=snapshot.revision
        canary['capabilities_sha256']=digest(canary['capabilities'])
        item=routing.prepare(snapshot,ENDPOINT,catalog=self.catalog,canary=canary,
                             created_at=AT,approval_ref='SYNTHETIC_AUTHORIZATION_ONLY')['envelope']
        return {**item,'_inbox_source':'DRIVE','_inbox_id':'synthetic-mcp-route-file','_inbox_name':'route.json'}

    def apply(self,item,raw=None):
        return apply_to_tower(raw or self.raw,[item],verified_human_intents=frozenset({autonomy.envelope_hash(item)}))

    def test_authenticated_route_changes_only_four_reads_and_preserves_primary_gates_science(self):
        packed,report=self.apply(self.envelope())
        self.assertFalse(report['rejected']);self.assertTrue(packed)
        updated=json.loads(packed);control=control_from_bundle(updated)
        for key,value in self.control.items():
            if key!='mcp_tool_routes':self.assertEqual(control[key],value)
        self.assertEqual(control['mcp_tool_routes']['executor_tool'],self.control['mcp_tool_routes']['executor_tool'])
        self.assertEqual({name:control['mcp_tool_routes'][name] for name in routing.TOOLS},
                         {name:ENDPOINT for name in routing.TOOLS})
        self.assertEqual(control['hosted_mcp_scientific_read_endpoint'],ENDPOINT)
        self.assertEqual(updated['files']['entities/artifact/SCIENCE.json'],json.loads(self.raw)['files']['entities/artifact/SCIENCE.json'])
        self.assertFalse(any('mcp_routes.json' in path for path in updated['files']))
        repeated,replay=self.apply(self.envelope(),packed)
        self.assertFalse(replay['rejected'])
        self.assertEqual(control_from_bundle(json.loads(repeated or packed)),control)
        self.assertTrue(all(row['outcome']=='ALREADY_APPLIED' for row in replay['operation_receipts']))

    def test_drive_source_and_forged_authority_cannot_authenticate_human(self):
        item=self.envelope();item['_autonomy_human_authority']='HUMAN'
        packed,report=apply_to_tower(self.raw,[item])
        self.assertTrue(report['rejected'])
        self.assertIn('AUTHENTICATED_HUMAN_MCP_ROUTE_REQUIRED',str(report['rejected']))
        self.assertEqual(control_from_bundle(json.loads(packed or self.raw)),self.control)

    def test_pending_preparation_never_invents_catalog_or_connected_canary(self):
        draft=routing.prepare(self.snapshot,ENDPOINT,created_at=AT,approval_ref='SYNTHETIC_AUTHORIZATION_ONLY')
        self.assertEqual(draft['status'],'PENDING_CONNECTION')
        self.assertEqual(draft['blockers'],['MCP_CATALOG_REQUIRED','MCP_CONNECTED_CANARY_REQUIRED'])
        self.assertIsNone(draft['envelope'])
        self.assertIsNone(draft['candidate']['catalog']);self.assertIsNone(draft['candidate']['canary'])
        self.assertFalse(draft['endpoint_observed']);self.assertFalse(draft['human_authenticated'])
        item=self.envelope();item['payload']['canary']=None
        packed,report=self.apply(item)
        self.assertIn('MCP_CONNECTED_CANARY_REQUIRED',str(report['rejected']))
        self.assertEqual(control_from_bundle(json.loads(packed or self.raw)),self.control)

    def test_catalog_scope_hash_canary_and_canonical_source_are_bound(self):
        cases=[('catalog',{'sha256':'0'*64},'MCP_CATALOG_HASH_MISMATCH'),
               ('catalog',{'role':'EXECUTOR'},'MCP_CATALOG_SCOPE_MISMATCH'),
               ('canary',{'runtime':'HTTP_SMOKE_ONLY'},'MCP_CONNECTED_CANARY_UNVERIFIED'),
               ('canary',{'catalog_sha256':'0'*64},'MCP_CONNECTED_CANARY_UNVERIFIED'),
               ('source_read',{'file_id':'other-tower'},'MCP_ROUTE_SOURCE_READ_INVALID'),
               ('source_read',{'route_sha256':'0'*64},'MCP_ROUTE_REVISION_CONFLICT'),
               ('source_read',{'tower_revision':'sha256:'+'0'*64},'MCP_ROUTE_CANONICAL_SOURCE_MISMATCH')]
        for field,patch,error in cases:
            with self.subTest(field=field,patch=patch):
                item=self.envelope();item['payload'][field].update(patch)
                packed,report=self.apply(item)
                self.assertIn(error,str(report['rejected']))
                self.assertEqual(control_from_bundle(json.loads(packed or self.raw)),self.control)
        item=self.envelope();item['payload']['tool_names'].append('request_execution')
        self.assertIn('MCP_ROUTE_SCOPE_INVALID',str(self.apply(item)[1]['rejected']))

    def test_generic_merges_and_stale_converter_request_are_rejected(self):
        root,_=materialize_live_tower(self.raw,self.work/'materialized')
        request={'document':'CONTROL.json','merge':{'hosted_mcp_scientific_read_endpoint':ENDPOINT},
                 '_mcp_route_authority':'HUMAN'}
        self.assertFalse(apply_document(root,request)['accepted'])
        item=autonomy.attach_human_authority(self.envelope(),{autonomy.envelope_hash(self.envelope())})
        routed=proposal_to_requests(item,root)[0]
        current=json.loads((root/'CONTROL.json').read_text());current['mcp_tool_routes']['executor_tool']='https://changed.example.test/mcp'
        (root/'CONTROL.json').write_text(json.dumps(current))
        self.assertEqual(apply_document(root,routed)['issue']['code'],'MCP_ROUTE_REVISION_CONFLICT')
        self.assertNotIn(routing.ACTION,autonomy.ACTIONS)

    def test_canary_rejects_refreshing_binding_errors_discovery_and_wrong_capabilities(self):
        cases=[({'status':'INDEX_REFRESHING'},'MCP_CANARY_CAPABILITIES_NOT_AUTHENTICATED'),
               ({'status':'binding_unavailable'},'MCP_CANARY_CAPABILITIES_NOT_AUTHENTICATED'),
               ({'status':'READY'},'MCP_CANARY_CAPABILITIES_NOT_AUTHENTICATED'),
               ({'roles':['EXECUTOR']},'MCP_CANARY_CAPABILITIES_NOT_AUTHENTICATED'),
               ({'writes_enabled':True},'MCP_CANARY_CAPABILITIES_NOT_AUTHENTICATED'),
               ({'source':{'source_id':'other-tower'}},'MCP_CANARY_CAPABILITIES_SOURCE_MISMATCH'),
               ({'validity_end':'2026-10-13T01:30:00Z'},'MCP_CANARY_CAPABILITIES_EXPIRED')]
        for change,error in cases:
            with self.subTest(change=change):
                item=self.envelope();caps=item['payload']['canary']['capabilities'];caps.update(change)
                item['payload']['canary']['capabilities_sha256']=digest(caps)
                packed,report=self.apply(item)
                self.assertIn(error,str(report['rejected']))
                self.assertEqual(control_from_bundle(json.loads(packed or self.raw)),self.control)
        item=self.envelope();item['payload']['canary']['capabilities_sha256']='0'*64
        self.assertIn('MCP_CANARY_CAPABILITIES_HASH_MISMATCH',str(self.apply(item)[1]['rejected']))

    def test_control_compat_rehearsal_preserves_route_and_route_change_invalidates_cursor(self):
        first=prepare_context(self.snapshot,'LEARNER')
        packed,_=self.apply(self.envelope());path=self.work/'changed.json';path.write_bytes(packed)
        delta=prepare_context(Snapshot.read(path),'LEARNER',cursor=first['cursor'])
        self.assertTrue(delta['cursor_reset'])
        migrated,_=prepare_migration(self.raw);source=self.work/'migrated.json';source.write_bytes(migrated)
        item=self.envelope(Snapshot.read(source))
        changed,report=self.apply(item,migrated)
        self.assertFalse(report['rejected'])
        self.assertNotIn('CONTROL.json',json.loads(changed)['files'])
        new_control=control_from_bundle(json.loads(changed))
        self.assertEqual(new_control['hosted_mcp_scientific_read_endpoint'],ENDPOINT)
        self.assertEqual(new_control['hosted_mcp_current_endpoint'],self.control['hosted_mcp_current_endpoint'])


if __name__=='__main__':
    unittest.main()
