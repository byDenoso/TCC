"""Future contest generation never repairs or changes an existing frozen design."""
import copy
import json

import pytest

from runtime.nexo_agent_api.evolution import family_contest_items
from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
from runtime.nexo_agent_api.tower_apply import apply_requests
from runtime.nexo_agent_api.tower_paths import entity_path


def put(root, test):
    path = entity_path(root, 'test', test['id'])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(test))
    return path


def parent(root, comps, tried=False, test_id='FAM-A'):
    test = {'id': test_id, 'kind': 'TEST', 'status': 'DONE', 'verdict': 'PROMOTED',
            'review_state': 'PENDING_REVIEW', 'family_id': 'F', 'recipe': 'w0wa_bao_sn_multi',
            'question': 'Frozen question', 'null': 'n', 'rival': 'r', 'method': 'm',
            'success_criteria': 's', 'kill_criteria': 'k', 'prereg_hash': 'unchanged',
            'recipe_params': {'mode': 'redshift_jackknife', 'compilations': comps,
                              'bands': [[0, .2]], 'priors': {'omega_m': [.3, .01]}}}
    if tried:
        test['contests'] = [{'contest_test_id': test_id + '-OLD'}]
        put(root, {'id': test_id + '-OLD', 'kind': 'TEST', 'verdict': 'INCONCLUSIVE'})
    return test, put(root, test)


@pytest.mark.parametrize('comps', [
    ['des_sn5yr', 'union3'], ['pantheon_plus', 'union3'],
    ['pantheon_plus', 'des_sn5yr', 'union3'],
    ['union3', 'union3'], ['pantheon_plus', 'union3', 'union3'],
    ['pantheon_plus'], [], None, 'des_sn5yr', ['unknown', 'des_sn5yr'], [{}],
])
@pytest.mark.parametrize('tried', [False, True])
def test_unsupported_swap_abstains_without_touching_frozen_parent(tmp_path, comps, tried):
    test, path = parent(tmp_path, comps, tried)
    before = path.read_bytes()
    [signal] = family_contest_items(tmp_path)
    assert signal['kind'] == 'LEARNING_SIGNAL'
    assert signal['payload']['signals'][0]['code'] == 'ROBOT_CONTEST_NO_DISTINCT_COMPILATION'
    assert signal['payload']['signals'][0]['test_id'] == test['id']
    requests = proposal_to_requests(signal, tmp_path)
    assert all(r['entity_kind'] == 'artifact' for r in requests)
    assert all(row['accepted'] for row in apply_requests(tmp_path, requests))
    assert family_contest_items(tmp_path) == []  # recorded reason is not reissued per pulse
    assert path.read_bytes() == before


@pytest.mark.parametrize('tried', [False, True])
@pytest.mark.parametrize('comps', [['pantheon_plus', 'des_sn5yr'], ['des_sn5yr', 'pantheon_plus']])
def test_valid_swap_preserves_cardinality_order_and_all_other_parameters(tmp_path, tried, comps):
    test, path = parent(tmp_path, comps, tried)
    before = path.read_bytes()
    [item] = family_contest_items(tmp_path)
    assert item['kind'] == 'CONTEST'
    attack = item['payload']['contest_test']
    expected = copy.deepcopy(test['recipe_params'])
    expected['compilations'] = ['union3' if c == 'des_sn5yr' else c for c in comps]
    assert attack['recipe_params'] == expected
    assert len(set(attack['recipe_params']['compilations'])) == len(comps)
    for field in ('question', 'null', 'rival', 'method', 'success_criteria', 'kill_criteria'):
        assert attack[field] == test[field]
    assert path.read_bytes() == before


def test_active_attack_still_blocks_generation(tmp_path):
    test, _ = parent(tmp_path, ['des_sn5yr', 'union3'], True)
    put(tmp_path, {'id': test['id'] + '-OLD', 'kind': 'TEST', 'status': 'RUNNING'})
    assert family_contest_items(tmp_path) == []


def test_persisted_signals_do_not_starve_later_valid_contests(tmp_path):
    for index in range(8):
        parent(tmp_path, ['des_sn5yr', 'union3'], test_id=f'A{index}')
    parent(tmp_path, ['pantheon_plus', 'des_sn5yr'], test_id='Z')
    items = family_contest_items(tmp_path)
    contests = [item for item in items if item['kind'] == 'CONTEST']
    assert len(contests) == 1
    assert contests[0]['payload']['test_id'] == 'Z'
    assert len([item for item in items if item['kind'] == 'LEARNING_SIGNAL']) <= 5
