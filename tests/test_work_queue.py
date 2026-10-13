import copy
import unittest

from runtime.nexo_agent_api.work_queue import derive_work_queue


def entry(value):
    return {'encoding': 'json', 'value': value}


class WorkQueueTests(unittest.TestCase):
    def test_ready_work_with_explicit_human_gate_cannot_continue_or_auto_retry(self):
        work={'id':'W','status':'READY','owner_role':'ADVISOR',
              'human_action_required':True,'dependency_class':'HUMAN_DECISION_REQUIRED',
              'dependency_classes':['HUMAN_DECISION_REQUIRED'],'auto_retry_eligible':True,
              'next_action':'WAIT_FOR_EXPLICIT_OPERATOR_DECISION'}
        files={'entities/work/W.json':entry(work)}
        row=derive_work_queue(files)[0]
        self.assertEqual(row['first_exclusion_reason'],'WAIT_HUMAN_DECISION')
        self.assertEqual(row['next_step'],'WAIT_HUMAN_DECISION')
        self.assertFalse(row['actionable']);self.assertFalse(row['execution_authorization'])
        for field in ('human_action_required','dependency_class','dependency_classes','auto_retry_eligible','next_action'):
            self.assertEqual(row[field],work[field])
        work['status']='DONE'
        self.assertEqual(derive_work_queue(files)[0]['first_exclusion_reason'],'WORK_TERMINAL')

    def test_ambiguous_work_identity_is_never_actionable_or_a_satisfied_dependency(self):
        files = {'entities/work/W1.json': entry({'id':'W','status':'READY','owner_role':'EXECUTOR'}),
                 'entities/work/W2.json': entry({'id':'W','status':'DONE','owner_role':'EXECUTOR'}),
                 'entities/work/NEXT.json': entry({'id':'NEXT','status':'READY','owner_role':'EXECUTOR','depends_on':['W']})}
        rows=derive_work_queue(files)
        self.assertFalse(any(row['actionable'] for row in rows))
        next_row=next(row for row in rows if row['id']=='NEXT')
        self.assertEqual(next_row['dependencies'][0]['state'],'AMBIGUOUS')

    def test_parallel_pending_does_not_recreate_wait_for_accepted_owner(self):
        files = {'entities/work/W.json': entry({'id': 'W', 'status': 'READY', 'owner_role': 'EXECUTOR', 'entity_version': 2}),
                 'events/day/1.json': entry({'handoff_id': 'accepted', 'entity_ref': 'W', 'to_role': 'EXECUTOR', 'state': 'ACK', 'entity_version': 1}),
                 'events/day/2.json': entry({'handoff_id': 'parallel', 'entity_ref': 'W', 'to_role': 'EXECUTOR', 'state': 'PENDING'})}
        row = derive_work_queue(files)[0]
        self.assertEqual(row['acceptance'], 'ACCEPTED')
        self.assertIsNone(row['first_exclusion_reason'])
        self.assertFalse(row['execution_authorization'])
        self.assertEqual(derive_work_queue(files), derive_work_queue(dict(reversed(list(files.items())))))

    def test_done_work_cannot_be_selected_from_historical_ready_handoff(self):
        files = {'entities/work/W.json': entry({'id': 'W', 'status': 'DONE', 'owner_role': 'EXECUTOR'}),
                 'events/day/1.json': entry({'handoff_id': 'old', 'entity_ref': 'W', 'to_role': 'EXECUTOR', 'state': 'ACK', 'work_envelope': {'status': 'READY'}}),
                 'entities/test/T.json': entry({'id': 'T', 'status': 'READY'})}
        row = derive_work_queue(files)[0]
        self.assertEqual(row['first_exclusion_reason'], 'WORK_TERMINAL')
        self.assertFalse(row['actionable'])
        self.assertEqual(len(derive_work_queue(files)), 1)

    def test_dependency_identity_and_first_exclusion_are_stable(self):
        files = {'entities/work/W.json': entry({'id': 'W', 'status': 'READY', 'owner_role': 'EXECUTOR', 'depends_on': ['WORK::EXACT']}),
                 'entities/work/OTHER.json': entry({'id': 'WORK::OTHER', 'status': 'DONE', 'owner_role': 'EXECUTOR'})}
        row = next(row for row in derive_work_queue(files) if row['id'] == 'W')
        self.assertEqual(row['dependencies'], [{'ref': 'WORK::EXACT', 'state': 'UNKNOWN', 'satisfied': False}])
        self.assertEqual(row['first_exclusion_reason'], 'WAIT_DEPENDENCY')
        files['entities/work/EXACT.json'] = entry({'id': 'WORK::EXACT', 'status': 'FAILED', 'owner_role': 'EXECUTOR'})
        self.assertFalse(next(row for row in derive_work_queue(files) if row['id'] == 'W')['actionable'])
        files['entities/work/EXACT.json']['value']['status'] = 'VERIFIED'
        self.assertTrue(next(row for row in derive_work_queue(files) if row['id'] == 'W')['actionable'])

    def test_recovery_acceptance_requires_current_fingerprint_generation_and_source(self):
        event = {'handoff_id': 'H', 'request_id': 'R', 'from_role': 'ADVISOR', 'to_role': 'EXECUTOR',
                 'entity_ref': 'W', 'state': 'ACK', 'handoff_type': 'BLOCKER_RECOVERY',
                 'recovery_fingerprint': 'frozen', 'work_envelope': {'test_id': 'T', 'recovery': {'route_generation': 2}}}
        work = {'id': 'W', 'status': 'WAIT_DEPENDENCY', 'owner_role': 'EXECUTOR', 'kind': 'DEPENDENCY_RECOVERY', 'test_id': 'T',
                'recovery': {'target_role': 'EXECUTOR', 'fingerprint': 'frozen', 'route_generation': 2,
                             'ownership_state': 'ACCEPTED', 'reasons': ['RECIPE_BINDING_MISSING'],
                             'acceptance_source': {key: event[key] for key in ('handoff_id', 'request_id', 'from_role', 'to_role')}}}
        pending = {**event, 'state': 'PENDING', 'handoff_id': 'PARALLEL'}
        files = {'entities/work/W.json': entry(work), 'events/day/1.json': entry(event), 'events/day/2.json': entry(pending)}
        row = derive_work_queue(files)[0]
        self.assertTrue(row['actionable'])
        self.assertEqual(row['readiness_reasons'], ['RECIPE_BINDING_MISSING'])
        for field, value in [('fingerprint', 'different'), ('route_generation', 3), ('acceptance_source', {})]:
            mutated = copy.deepcopy(files)
            mutated['entities/work/W.json']['value']['recovery'][field] = value
            changed = derive_work_queue(mutated)[0]
            self.assertEqual(changed['acceptance'], 'ASSIGNED_UNACCEPTED')
            self.assertEqual(changed['first_exclusion_reason'], 'WAIT_ACCEPTANCE')
            self.assertFalse(changed['actionable'])


if __name__ == '__main__':
    unittest.main()
