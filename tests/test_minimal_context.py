import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.live_tower import build_live_tower_payload
from runtime.nexo_agent_api.memory import Snapshot,digest
from runtime.nexo_agent_api.pulse_context import prepare_context
from runtime.nexo_agent_api.test_public_projection import _tower
from runtime.nexo_agent_api.service import AgentService


def encode(bundle):
    bundle=copy.deepcopy(bundle)
    rev='sha256:'+digest(bundle['files'])
    bundle.update(revision=rev,state_fingerprint=rev,file_count=len(bundle['files']))
    return json.dumps(bundle,ensure_ascii=False,sort_keys=True).encode()


class MinimalContextTests(unittest.TestCase):
    def base(self,work):
        root=_tower(Path(work)/'TOWER_V06')
        control=json.loads((root/'CONTROL.json').read_text())
        control['truth_owner']='TOWER_V06@GOOGLE_DRIVE_PRIVATE'
        control['historical_bloat']='x'*30000
        (root/'CONTROL.json').write_text(json.dumps(control))
        return root,build_live_tower_payload(root,updated_at='2026-10-12T00:00:00Z')

    def test_bootstrap_preserves_operational_reference_without_full_control(self):
        with tempfile.TemporaryDirectory() as work:
            root,_=self.base(work)
            view=AgentService(root).bootstrap('ADVISOR')
            self.assertNotIn('historical_bloat',view['control'])
            self.assertEqual(view['control_reference']['authority_ref'],'CONTROL.json')
            self.assertEqual(view['control']['truth_owner'],'TOWER_V06@GOOGLE_DRIVE_PRIVATE')

    def test_cursor_detects_resolution_target_change_and_authority_revision(self):
        with tempfile.TemporaryDirectory() as work:
            root,bundle=self.base(work)
            bundle['files']['evolution/board.json']={'encoding':'json','value':{'posts':[{'id':'P','to':'ENGINEER','text':'hello'}]}}
            path=Path(work)/'source.json';path.write_bytes(encode(bundle))
            first=prepare_context(Snapshot.read(path),'ADVISOR')
            again=prepare_context(Snapshot.read(path),'ADVISOR',cursor=first['cursor'])
            self.assertFalse(again['context_changed']);self.assertFalse(again['execution_authorization'])
            bundle['files']['evolution/board.json']['value']['posts'][0]['resolved_at']='2026-10-12T01:00:00Z'
            path.write_bytes(encode(bundle))
            changed=prepare_context(Snapshot.read(path),'ADVISOR',cursor=first['cursor'])
            self.assertIn('board:P',changed['changed'])
            bundle['files']['CONTROL.json']['value']['revoked_autonomy_mandates']=['NEW-REVOCATION']
            path.write_bytes(encode(bundle))
            invalidated=prepare_context(Snapshot.read(path),'ADVISOR',cursor=changed['cursor'])
            self.assertTrue(invalidated['cursor_reset'])

    def test_mcp_outage_cannot_block_existing_native_writer_board_effect(self):
        with tempfile.TemporaryDirectory() as work:
            root,bundle=self.base(work)
            item={'kind':'BOARD_POST','source':'ENGINEER','created_at':'2026-10-12T00:00:00Z',
                  'intent_id':'native-without-mcp','payload':{'id':'POST-NATIVE','to':'EXECUTOR','text':'verified private delivery','private':True}}
            with patch('socket.create_connection',side_effect=AssertionError('MCP/network dependency')):
                packed,report=apply_to_tower(encode(bundle),[item])
            self.assertFalse(report['rejected'])
            posts=json.loads(packed)['files']['evolution/board.json']['value']['posts']
            self.assertTrue(any(row['id']=='POST-NATIVE' for row in posts))

    def test_equal_board_text_with_distinct_evidence_is_not_discarded(self):
        with tempfile.TemporaryDirectory() as work:
            _,bundle=self.base(work)
            items=[{'kind':'BOARD_POST','source':'ENGINEER','created_at':'2026-10-12T00:00:00Z','intent_id':str(i),
                    'payload':{'id':'P'+str(i),'to':'EXECUTOR','text':'input prepared','refs':['artifact:'+str(i)],'private':True}} for i in range(2)]
            packed,report=apply_to_tower(encode(bundle),items)
            posts=json.loads(packed)['files']['evolution/board.json']['value']['posts']
            self.assertTrue({'P0','P1'} <= {row['id'] for row in posts})
            self.assertFalse(report['rejected'])

    def test_false_document_receipt_never_becomes_applied_without_board_effect(self):
        with tempfile.TemporaryDirectory() as work:
            _,bundle=self.base(work)
            item={'kind':'BOARD_POST','source':'ENGINEER','created_at':'2026-10-12T00:00:00Z','intent_id':'missing-effect',
                  'payload':{'id':'NEVER-CREATED','to':'EXECUTOR','text':'must actually exist'}}
            with patch('runtime.nexo_agent_api.gpt_writer.apply_requests',return_value=[{'accepted':True,'readback':'PASS'}]):
                _,report=apply_to_tower(encode(bundle),[item])
            self.assertTrue(report['rejected'])
            outcomes=[row for row in report['operation_receipts'] if row['intent_id']=='missing-effect']
            self.assertTrue(outcomes)
            self.assertFalse(any(row['outcome']=='APPLIED' for row in outcomes))


class TargetContextPrivacyTests(unittest.TestCase):
    base = MinimalContextTests.base
    def test_target_board_contains_only_recipient_and_acl_authorized_posts(self):
        with tempfile.TemporaryDirectory() as work:
            _, bundle = self.base(work)
            bundle['files']['evolution/board.json'] = {'encoding':'json','value':{'private_admin_note':'hidden','posts':[
                {'id':'OWN','to':'ENGINEER','private':True,'text':'allowed'},
                {'id':'OTHER','to':'EXECUTOR','private':True,'text':'other-private'},
                {'id':'ACL','to':'ALL','allowed_roles':['EXECUTOR'],'text':'acl-private'},
                {'id':'ALL','to':'ALL','text':'common'}]}}
            path = Path(work)/'source.json';path.write_bytes(encode(bundle))
            result = prepare_context(Snapshot.read(path),'ADVISOR',target_refs=['evolution/board.json'])
            posts = result['changed']['evolution/board.json']['value']['value']['posts']
            self.assertEqual({p['id'] for p in posts},{'OWN','ALL'})
            serialized = json.dumps(result)
            self.assertNotIn('other-private',serialized);self.assertNotIn('acl-private',serialized)
            self.assertNotIn('private_admin_note',serialized)

    def test_explicit_targets_cannot_bypass_ownership_acl_or_retained_authority(self):
        with tempfile.TemporaryDirectory() as work:
            _, bundle = self.base(work)
            cases = {
                'entities/work/OTHER.json':{'id':'OTHER','owner_role':'EXECUTOR','status':'READY'},
                'entities/test/ACL.json':{'id':'ACL','allowed_roles':['EXECUTOR'],'data':[1,2]},
                'entities/result/PRIVATE.json':{'id':'PRIVATE','private':True,'writer_role':'EXECUTOR'},
                'events/day/OTHER.json':{'handoff_id':'OTHER','to_role':'EXECUTOR','state':'PENDING'},
                'events/migrations/control-history.json':{'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE'},
            }
            for path, value in cases.items():bundle['files'][path]={'encoding':'json','value':value}
            path=Path(work)/'source.json';path.write_bytes(encode(bundle));snapshot=Snapshot.read(path)
            for target in [*cases,'CONTROL.json']:
                with self.subTest(target=target):
                    with self.assertRaisesRegex(ValueError,'CONTEXT_TARGET_FORBIDDEN'):
                        prepare_context(snapshot,'ADVISOR',target_refs=[target])

    def test_authorized_science_target_preserves_numbers_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as work:
            _,bundle=self.base(work)
            target='entities/test/OWN.json'
            bundle['files'][target]={'encoding':'json','value':{'id':'OWN','allowed_roles':['ENGINEER'],
                'result':[1.234,4.567],'contract':{'alpha':0.01},'private_key':'must-not-leak'}}
            path=Path(work)/'source.json';path.write_bytes(encode(bundle))
            result=prepare_context(Snapshot.read(path),'ADVISOR',target_refs=[target])
            payload=result['changed'][target]['value']['value']
            self.assertEqual(payload['result'],[1.234,4.567]);self.assertEqual(payload['contract'],{'alpha':0.01})
            self.assertNotIn('must-not-leak',json.dumps(result))


class HandoffDeltaTests(unittest.TestCase):
    def test_event_handoff_transitions_are_visible_in_role_deltas(self):
        with tempfile.TemporaryDirectory() as work:
            fixture=MinimalContextTests();_,bundle=fixture.base(work)
            bundle['files']['events/day/A.json']={'encoding':'json','value':{'handoff_id':'H','to_role':'ADVISOR','state':'PENDING'}}
            path=Path(work)/'source.json';path.write_bytes(encode(bundle))
            first=prepare_context(Snapshot.read(path),'ENGINEER')
            self.assertEqual(first['changed']['handoff:H']['value']['state'],'PENDING')
            bundle['files']['events/day/B.json']={'encoding':'json','value':{'handoff_id':'H','to_role':'ADVISOR','state':'DONE'}}
            path.write_bytes(encode(bundle))
            changed=prepare_context(Snapshot.read(path),'ENGINEER',cursor=first['cursor'])
            self.assertEqual(changed['changed']['handoff:H']['value']['state'],'DONE')

    def test_handoff_cache_updates_and_rolls_back_with_receipt_transaction(self):
        from runtime.nexo_agent_api import operation_receipts as receipts,handoff
        with tempfile.TemporaryDirectory() as work:
            root=Path(work);events=root/'events/day';events.mkdir(parents=True)
            (events/'A.json').write_text(json.dumps({'handoff_id':'old','to_role':'ADVISOR','state':'PENDING'}))
            with receipts.receipt_transaction(root):
                before=handoff._handoff_events(root)
                checkpoint=receipts.receipt_savepoint(root)
                created=handoff._write_event(root,{'handoff_id':'new','to_role':'ADVISOR','state':'PENDING'})
                self.assertEqual(len(handoff._handoff_events(root)),2)
                for path in root.glob('events/**/*.json'):
                    if path.name.startswith(created['event_id']):path.unlink()
                receipts.restore_receipt_savepoint(root,checkpoint)
                self.assertEqual(handoff._handoff_events(root),before)
                with receipts.receipt_transaction(root) as nested:
                    self.assertIsNotNone(nested.handoff_cache['entries'])
