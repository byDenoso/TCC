"""Scientific gates and historical isolation of the public cosmology read model."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('cosmology_state', Path(__file__).with_name('cosmology_state.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
build = module.build_cosmology_state


class CosmologyStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def frontier(self, result, id='energia-escura'):
        return next(f for f in result['frontiers'] if f['id'] == id)
    def test_initial_frontiers_traceable_nulls_and_bounded_history(self):
        result = build(self.root, [], [], [])
        self.assertEqual(8, len(result['frontiers']))
        self.assertLess(len(result['historical_tests']), 20)
        for id in ['energia-escura', 'h0', 'crescimento-s8']:
            front = self.frontier(result, id)
            self.assertTrue(front['key_evidence'])
            self.assertTrue(all(e['provenance']['row_sha256'] for e in front['key_evidence']))
        energy = self.frontier(result)
        self.assertTrue(any('Pantheon+' in e['meaning'] and e['verdict'] == 'REFUTED' for e in energy['key_evidence']))
        self.assertIn('REFUTED', {e['verdict'] for e in energy['key_evidence']})
        self.assertIn('CONFIRMED', {e['verdict'] for e in energy['key_evidence']})
        self.assertEqual(result, build(self.root, [], [], []))
    def test_operational_and_promoted_do_not_change_global_state(self):
        for status in ['READY', 'RUNNING', 'CHECKPOINTED', 'BLOCKED', 'DRAFT', 'DONE']:
            test = {'id': 'DE', 'question': 'dark energy', 'status': status, 'verdict': 'PROMOTED', 'semantic': {'result_meaning': 'Sinal isolado de 2σ.'}}
            f = self.frontier(build(self.root, [test], [], []))
            self.assertEqual('TENSION', f['state'])
            self.assertFalse(any(e['synthesis_eligible'] for e in f['key_evidence'] if e['id'] == 'DE'))
    def test_current_tower_supersedes_history_without_erasing_it(self):
        test = {'id': 'T-UCP26-001', 'question': 'Pantheon dark energy', 'status': 'DONE', 'review_state': 'CONTESTED', 'semantic': {'result_meaning': 'Interpretação atual em disputa.'}}
        result = build(self.root, [test], [], [])
        f = self.frontier(result)
        self.assertEqual('REVIEW', next(e for e in f['key_evidence'] if e['id'] == test['id'])['verdict'])
        self.assertTrue(next(e for e in f['historical_lessons'] if e['id'] == test['id'])['superseded_by_current'])
        self.assertNotIn(test['id'], {t['id'] for t in result['historical_tests']})
    def test_global_transition_requires_audited_independent_material_closure(self):
        tests = [{'id': id, 'question': 'dark energy ' + id, 'status': 'DONE', 'review_state': 'CONFIRMED', 'prereg': {'hash': id}, 'semantic': {'result_meaning': 'Resultado no escopo congelado.'}} for id in ['A', 'B']]
        path = self.root / 'evolution/cosmology_state.json'; path.parent.mkdir()
        override = {'id': 'energia-escura', 'state': 'SOLID', 'summary': 'Síntese registrada na Tower.', 'evidence_ids': ['A', 'B'], 'scope': 'GLOBAL_SYNTHESIS', 'material': True, 'global_significance_reviewed': True, 'independent_support': True}
        path.write_text(json.dumps({'frontiers': [override]}))
        self.assertEqual('SOLID', self.frontier(build(self.root, tests, [], []))['state'])
        tests[1]['review_state'] = 'PENDING_REVIEW'
        self.assertEqual('TENSION', self.frontier(build(self.root, tests, [], []))['state'])
    def test_privacy_and_campaign_links(self):
        tests = [{'id':'PRIVATE','private':True,'question':'dark energy'}, {'id':'ACTIVE','question':'dark energy','status':'READY','campaign_id':'C'}]
        f = self.frontier(build(self.root, tests, [{'campaign_id':'C'}], [{'roadmap_id':'R','test_ids':['ACTIVE']}]))
        self.assertEqual(['C'], f['campaign_ids'])
        self.assertEqual(['R'], f['roadmap_ids'])
        self.assertEqual(['ACTIVE'], [t['id'] for t in f['active_tests']])
    def test_dedup_preserves_opposite_decisions(self):
        common = {'cosmology_material': True, 'question':'dark energy independent question', 'status':'DONE', 'prereg':{'hash':'frozen'}, 'semantic':{'result_meaning':'Escopo científico.'}}
        tests = [dict(common, id='A', review_state='CONFIRMED'), dict(common, id='B', review_state='CONFIRMED'), dict(common,id='C',review_state='REFUTED')]
        evidence = self.frontier(build(self.root, tests, [], []))['key_evidence']
        grouped = next(e for e in evidence if e['id']=='A')
        self.assertEqual(['A','B'], grouped['member_ids'])
        self.assertTrue(any(e['id']=='C' and e['verdict']=='REFUTED' for e in evidence))

if __name__ == '__main__':
    unittest.main()
