"""The direct scientific route cannot depend on a legacy recipe file."""
from copy import deepcopy
import json

from runtime.nexo_agent_api import evolution, scientific_integrity as integrity
from runtime.nexo_agent_api.execution_recovery import reconcile_requests


def _fixture(root):
    for folder in ('entities/test', 'entities/artifact', 'entities/work'):
        (root / folder).mkdir(parents=True)
    (root / 'CONTROL.json').write_text(json.dumps({
        'execution_routing': 'LEAN_NO_CONTRACT_DIRECT_RUNTIME',
        'scientific_runtime': 'CHATGPT_RUNTIME',
    }))
    test = {
        'id': 'T-SYNTHETIC-DIRECT-001', 'kind': 'TEST', 'domain': 'SCIENCE',
        'question': 'Does the toy observable differ from the declared null?',
        'null': 'No effect', 'rival': 'A positive effect',
        'method': 'Frozen deterministic statistic with fixed cut and parameter',
        'dataset_and_selection': 'One pinned synthetic array, full selection',
        'success_criteria': 'A fixed positive threshold',
        'kill_criteria': 'A fixed null threshold',
        'claim_boundary': 'Synthetic fixture only', 'prereg_ref': 'FROZEN_FIXTURE',
        'status': 'BLOCKED_INPUT', 'state': 'BLOCKED_INPUT',
        'blocker': 'RECIPE_BINDING_MISSING',
        'data_binding': {'status': 'BOUND', 'inputs': [{
            'kind': 'generated', 'name': 'fixture', 'seed': 42,
            'generator': 'deterministic fixture', 'sha256': 'a' * 64,
        }]},
        'entity_version': 1,
        'readiness': {'policy': integrity.POLICY, 'eligible': False,
                      'reasons': ['RECIPE_BINDING_MISSING']},
    }
    test['prereg_hash'] = evolution.prereg_hash(test['id'], test)
    (root / 'entities/test' / (test['id'] + '.json')).write_text(json.dumps(test))
    return test


def test_direct_accepts_frozen_without_recipe(tmp_path):
    test = _fixture(tmp_path)
    decision = integrity.readiness(tmp_path, test)
    assert decision['eligible'] and not decision['reasons']
    assert decision['recipe_sha256'] is None
    assert decision['recipe_scope'] == 'DIRECT_FROZEN_CONTRACT_NO_RECIPE_GATE'


def test_scientific_guards_remain(tmp_path):
    test = _fixture(tmp_path)
    changed = deepcopy(test)
    changed['data_binding'] = {'status': 'PARTIAL', 'inputs': []}
    changed['blocker'] = None
    assert 'INPUT_PROVENANCE_INCOMPLETE' in integrity.readiness(tmp_path, changed)['reasons']
    changed = deepcopy(test)
    changed['null'] = 'Post-hoc alternative'
    changed['blocker'] = None
    assert 'FROZEN_DESIGN_CHANGED' in integrity.readiness(tmp_path, changed)['reasons']


def test_legacy_recipe_still_required(tmp_path):
    test = _fixture(tmp_path)
    (tmp_path / 'CONTROL.json').write_text(json.dumps({
        'execution_routing': 'LEGACY_RECIPE_RUNNER',
        'scientific_runtime': 'CHATGPT_RUNTIME',
    }))
    assert 'RECIPE_BINDING_MISSING' in integrity.readiness(tmp_path, test)['reasons']


def test_explicit_recipe_fails_without_catalog(tmp_path):
    test = _fixture(tmp_path)
    test.update(blocker=None, recipe='pinned_recipe', recipe_params={})
    assert 'RECIPE_CATALOG_UNAVAILABLE' in integrity.readiness(tmp_path, test)['reasons']


def test_existing_writer_reconciles_stale_blocker(tmp_path):
    test = _fixture(tmp_path)
    requests = reconcile_requests(
        tmp_path, readiness_evaluator=lambda root, item, baseline: baseline())
    target = [r for r in requests if r.get('entity_name') == test['id']
              and r.get('entity_kind') == 'test']
    assert len(target) == 1
    assert target[0]['changes']['status'] == 'READY'
    assert target[0]['changes']['blocker'] is None


def test_recipe_less_test_not_admitted_to_batch_runner(tmp_path):
    test = _fixture(tmp_path)
    test.update(status='READY', state='READY', blocker=None)
    (tmp_path / 'entities/test' / (test['id'] + '.json')).write_text(json.dumps(test))
    batch = {'id': 'synthetic-only-test', 'status': 'QUEUED', 'tests': [{
        'test_id': test['id'], 'recipe': None, 'params': None,
        'recipe_sha256': None, 'attempt_id': 'a', 'execution_fingerprint': 'b',
    }]}
    outcome = integrity.guard_batteries(tmp_path, {
        'document': 'evolution/batteries.json', 'merge': {'batteries': [batch]},
    })
    assert outcome['issue']['code'] == 'BATTERY_RECIPE_REQUIRED'
