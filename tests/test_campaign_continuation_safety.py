"""Campaign completion requires explicit closure and independently reviewed results."""
import json
import tempfile
from pathlib import Path
from unittest import TestCase, main

from runtime.nexo_agent_api.campaign_continuation import CampaignFrontierResolver
from runtime.nexo_agent_api.tower_paths import entity_path


class CampaignContinuationSafetyTests(TestCase):
    def resolve(self, *, campaign=None, tests=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.store(root, 'test_group', 'CAMP-SYNTHETIC',
                       {'id':'CAMP-SYNTHETIC', 'status':'ACTIVE', **(campaign or {})})
            for test in tests or []:
                self.store(root, 'test', test['id'],
                           {'campaign_id':'CAMP-SYNTHETIC', **test})
            return CampaignFrontierResolver(root).resolve('CAMP-SYNTHETIC')

    @staticmethod
    def store(root, kind, entity_id, value):
        path = entity_path(root, kind, entity_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def test_done_without_independent_review_is_not_terminal(self):
        result = self.resolve(tests=[{'id':'T1','status':'DONE'}, {'id':'T2','status':'DONE'}])
        self.assertEqual(result['status'], 'ACTIVE')
        self.assertFalse(result['terminal'])
        self.assertFalse(result['review_complete'])
        self.assertTrue(result['execution_complete'])
        self.assertEqual(result['pending_review'], ['T1','T2'])
        self.assertEqual(result['next_action'], 'REQUEST_INDEPENDENT_REVIEW')

    def test_reviewed_protocol_waits_for_explicit_closure(self):
        result = self.resolve(tests=[{'id':'T1','status':'DONE','review_state':'CONFIRMED'},
                                     {'id':'T2','status':'DONE','review_state':'REFUTED'}])
        self.assertTrue(result['review_complete'])
        self.assertFalse(result['terminal'])
        self.assertEqual(result['next_action'], 'REQUEST_CLOSURE_DECISION')

    def test_explicitly_closed_campaign_stays_terminal(self):
        result = self.resolve(campaign={'status':'CLOSED'}, tests=[{'id':'T1','status':'DONE'}])
        self.assertTrue(result['terminal'])
        self.assertEqual(result['status'], 'TERMINAL')
        self.assertEqual(result['terminal_source'], 'EXPLICIT_CAMPAIGN_STATE')
        self.assertFalse(result['review_complete'])

    def test_terminal_test_does_not_skip_other_comparisons(self):
        result = self.resolve(campaign={'terminal_test_ids':['T1']}, tests=[
            {'id':'T1','status':'DONE','review_state':'CONFIRMED'},
            {'id':'T2','status':'READY'}])
        self.assertFalse(result['execution_complete'])
        self.assertFalse(result['review_complete'])
        self.assertFalse(result['terminal'])
        self.assertEqual(result['next_test_ids'], ['T2'])

    def test_declared_test_missing_from_snapshot_is_not_silently_complete(self):
        result = self.resolve(campaign={'terminal_test_ids':['MISSING']}, tests=[
            {'id':'T1','status':'DONE','review_state':'CONFIRMED'}])
        self.assertFalse(result['execution_complete'])
        self.assertEqual(result['unresolved_declared_tests'], ['MISSING'])
        self.assertFalse(result['terminal'])

    def test_empty_campaign_has_no_vacuous_completion(self):
        result = self.resolve()
        self.assertFalse(result['execution_complete'])
        self.assertFalse(result['terminal'])
        self.assertFalse(result['review_complete'])


if __name__ == '__main__':
    main()
