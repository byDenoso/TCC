"""Writer admission, complete-family annotations and provenance checks.

These checks do not infer scientific independence from wording or prove remote
execution from a state label. Missing evidence is explicit and never positive.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .tower_paths import entity_path

POLICY = 'SCIENTIFIC_INTEGRITY_V1'
ACTIVE = {'QUEUED', 'DISPATCH_PENDING', 'DISPATCHED', 'RUNNING'}
TERMINAL = {'DONE', 'RESULT', 'VERIFIED', 'COMPLETED', 'REJECTED', 'ARCHIVED', 'CANCELLED', 'CANCELED'}
FROZEN = ('question', 'null', 'rival', 'method', 'dataset_and_selection', 'success_criteria', 'kill_criteria', 'claim_boundary')
RESULT_FIELDS = {'result_meaning', 'result_meaning_source', 'verdict_plain', 'summary_plain', 'result',
                 'scientific_result', 'statistics', 'verdict', 'decision', 'executed_at',
                 'review_state', 'reviews', 'contests', 'fdr', 'mechanical_contest_verdict'}
RUN_REF = re.compile(r'^(?:https://github[.]com/byDenoso/Pantheon/)?actions/runs/([1-9][0-9]*)$')


class IntegrityError(ValueError):
    pass


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def read(root: Path, relative: str) -> dict:
    path = root / relative
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise IntegrityError('INVALID_CANONICAL_OBJECT:' + relative)
    return data


def entity(root: Path, test_id: str) -> dict:
    path = entity_path(root, 'test', test_id)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def timestamp(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def terminal(test: dict) -> bool:
    return (str(test.get('status') or test.get('state') or '').upper() in TERMINAL
            or test.get('review_state') in {'CONFIRMED', 'REFUTED', 'ARCHIVED'}
            or bool(test.get('verdict')) or bool(test.get('executed_at')))


def batteries(root: Path) -> list[dict]:
    return read(root, 'evolution/batteries.json').get('batteries') or []


def active_tests(root: Path) -> set[str]:
    return {str(t.get('test_id')) for b in batteries(root) if b.get('status') in ACTIVE
            for t in b.get('tests') or [] if isinstance(t, dict)}


def valid_inputs(inputs: Any) -> bool:
    if not isinstance(inputs, list) or not inputs:
        return False
    for item in inputs:
        if not isinstance(item, dict) or not item.get('name'):
            return False
        if item.get('kind') == 'generated':
            if item.get('seed') is None or not item.get('generator'):
                return False
        elif not str(item.get('url') or '').startswith('https://') or not item.get('version'):
            return False
        if not re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', str(item.get('sha256') or '')):
            return False
    return True


def readiness(root: Path, test: dict, *, ignore_reservation: bool = False) -> dict:
    from .evolution import prereg_hash
    reasons = []
    if terminal(test):
        reasons.append('TERMINAL_TEST')
    for key in FROZEN[:-1]:
        if not test.get(key):
            reasons.append('MISSING_' + key.upper())
    if not test.get('prereg_hash') or not (test.get('prereg_ref') or timestamp(test.get('frozen_at'))):
        reasons.append('FROZEN_DESIGN_UNVERIFIED')
    elif test['prereg_hash'] != prereg_hash(str(test.get('id') or ''), test):
        reasons.append('FROZEN_DESIGN_CHANGED')
    recipe, params = str(test.get('recipe') or ''), test.get('recipe_params')
    valid_name = bool(re.fullmatch(r'[a-z0-9_]{2,40}', recipe))
    if not valid_name or not isinstance(params, dict):
        reasons.append('RECIPE_BINDING_MISSING')
    recipe_root = Path(os.environ.get('NEXO_RECIPE_ROOT', 'nexo-one/executor-runtime/recipes'))
    recipe_hash = None
    if not recipe_root.is_dir():
        reasons.append('RECIPE_CATALOG_UNAVAILABLE')
    elif valid_name:
        code, smoke = recipe_root / (recipe + '.py'), recipe_root / 'smoke' / (recipe + '.json')
        if not code.is_file() or not smoke.is_file():
            reasons.append('RECIPE_OR_SMOKE_MISSING')
        else:
            try:
                raw = code.read_bytes()
                compile(raw, str(code), 'exec')
                json.loads(smoke.read_text(encoding='utf-8'))
                recipe_hash = hashlib.sha256(raw).hexdigest()
            except (SyntaxError, ValueError):
                reasons.append('RECIPE_OR_SMOKE_INVALID')
    binding = test.get('data_binding') or test.get('input_binding') or {}
    if not isinstance(binding, dict) or binding.get('status') != 'BOUND' or not valid_inputs(binding.get('inputs')):
        reasons.append('INPUT_PROVENANCE_INCOMPLETE')
    dependencies = test.get('depends_on') or []
    if not isinstance(dependencies, list):
        reasons.append('DEPENDENCIES_INVALID')
    else:
        for dependency_id in dependencies:
            dependency = entity(root, str(dependency_id))
            if not dependency.get('executed_at') or not dependency.get('verdict'):
                reasons.append('DEPENDENCY_UNRESOLVED')
                break
    if test.get('blocker'):
        reasons.append('BLOCKER_PRESENT')
    if not ignore_reservation and (str(test.get('id')) in active_tests(root)
                                  or str(test.get('status') or '').upper() in ACTIVE):
        reasons.append('ACTIVE_ATTEMPT')
    return {'policy': POLICY, 'eligible': not reasons, 'reasons': sorted(set(reasons)),
            'recipe_sha256': recipe_hash, 'input_scope': 'RECORDED_BINDING_NOT_NETWORK_ATTESTATION',
            'recipe_scope': 'SYNTAX_AND_SMOKE_SPEC_PRESENT'}


def execution_fingerprint(test: dict, recipe_sha: str) -> str:
    binding = test.get('data_binding') or test.get('input_binding') or {}
    return digest({**{key: test.get(key) for key in FROZEN}, 'recipe': test.get('recipe'),
                   'params': test.get('recipe_params'), 'recipe_sha256': recipe_sha,
                   'inputs': binding.get('inputs')})


def p_value(test: dict) -> float | None:
    result = test.get('result') if isinstance(test.get('result'), dict) else {}
    for holder in (result, test.get('statistics'), result.get('statistics')):
        if not isinstance(holder, dict):
            continue
        for key in ('p_value', 'p', 'pvalue'):
            raw = holder.get(key)
            if isinstance(raw, bool):
                continue
            try:
                value = float(raw)
            except (ValueError, TypeError):
                continue
            if math.isfinite(value) and 0 <= value <= 1:
                return value
    return None


def fdr_annotations(tests: list[dict], q: float = .1) -> dict[str, dict]:
    """BH over the complete materialized roadmap, never over selected positives.

    A changing roadmap is not an online-FDR procedure. Annotations explicitly
    describe this scope and never update a scientific verdict.
    """
    groups, output = {}, {}
    for test in tests:
        if test.get('roadmap_id') and not test.get('contests_test_id') and not test.get('decoy'):
            groups.setdefault(str(test['roadmap_id']), []).append(test)
    for family, members in groups.items():
        values = [(p_value(test), test) for test in members]
        measured = sorted(((p, test) for p, test in values if p is not None), key=lambda pair: (pair[0], str(pair[1]['id'])))
        n, complete = len(members), len(measured) == len(members)
        adjusted, current = {}, 1.
        for rank in range(len(measured), 0, -1):
            p, test = measured[rank - 1]
            current = min(current, p * n / rank)
            adjusted[str(test['id'])] = current
        for test in members:
            value = adjusted.get(str(test['id']))
            output[str(test['id'])] = {
                'method': 'BH', 'policy': 'FULL_ROADMAP_FAMILY_V2', 'family_id': family,
                'membership': 'MATERIALIZED_ROADMAP_SNAPSHOT', 'n': n, 'n_observed': len(measured),
                'n_missing': n - len(measured), 'q': q,
                'q_value': round(value, 8) if complete and value is not None else None,
                'survives': bool(value <= q) if complete and value is not None else None,
                'coverage': 'COMPLETE' if complete else 'INCOMPLETE',
                'claim_effect': 'ANNOTATION_ONLY',
                'assumptions': 'FIXED_FAMILY_INDEPENDENCE_OR_PRDS; NOT_ONLINE_FDR',
            }
    return output


def independence(parent: dict, attack: dict, root: Path | None = None) -> dict:
    """Check a frozen declaration and resolvable provenance, not scientific truth."""
    from .evolution import prereg_hash
    declaration = attack.get('independence') or {}
    if not isinstance(declaration, dict):
        declaration = {}
    reasons = []
    fields = {'data': 'dataset_and_selection', 'method': 'method', 'cohort': 'dataset_and_selection', 'implementation': 'recipe'}
    axis = declaration.get('axis')
    if axis not in fields:
        reasons.append('INDEPENDENCE_AXIS_REQUIRED')
    else:
        key = fields[axis]
        a, b = parent.get(key), attack.get(key)
        if not a or not b or digest(a) == digest(b):
            reasons.append('INDEPENDENT_AXIS_NOT_DISTINCT')
    refs = declaration.get('evidence_refs')
    if not isinstance(refs, list) or not refs:
        reasons.append('INDEPENDENCE_EVIDENCE_REQUIRED')
    elif root is None:
        reasons.append('INDEPENDENCE_PROVENANCE_NOT_RESOLVED')
    else:
        for reference in refs:
            if not isinstance(reference, str):
                reasons.append('INDEPENDENCE_REFERENCE_INVALID'); break
            path = (root / reference).resolve()
            if not path.is_relative_to(root.resolve()) or not reference.startswith(('entities/evidence/', 'entities/artifact/', 'runtime/artifacts/')) or not path.is_file():
                reasons.append('INDEPENDENCE_REFERENCE_UNRESOLVED'); break
    if declaration.get('on_pass') not in {'CONFIRMED', 'REFUTED'} or declaration.get('on_fail') not in {'CONFIRMED', 'REFUTED'} or declaration.get('on_pass') == declaration.get('on_fail'):
        reasons.append('ATTACK_POLARITY_REQUIRED')
    frozen, declared, executed = timestamp(attack.get('frozen_at')), timestamp(declaration.get('frozen_at')), timestamp(attack.get('executed_at'))
    if frozen is None or declared is None or declared > frozen or (executed is not None and frozen > executed):
        reasons.append('INDEPENDENCE_NOT_FROZEN')
    if attack.get('prereg_hash') != prereg_hash(str(attack.get('id') or ''), attack):
        reasons.append('ATTACK_DESIGN_UNVERIFIED')
    if attack.get('independence_fingerprint') != digest(declaration):
        reasons.append('INDEPENDENCE_COMMITMENT_UNVERIFIED')
    return {'policy': POLICY, 'eligible': not reasons, 'axis': axis, 'reasons': sorted(set(reasons)),
            'scope': 'FROZEN_DECLARATION_AND_RESOLVED_PROVENANCE_NOT_SCIENTIFIC_PROOF'}


def clean_result_fields(value: dict) -> dict:
    return {key: val for key, val in value.items() if key not in RESULT_FIELDS}


def public_execution_summary(root: Path, tests: list[dict]) -> dict:
    from .semantics import is_private, resolve
    public = [test for test in tests if not test.get('private') and not is_private(resolve(test, entity_id=str(test.get('id') or '')))]
    counts = {name: 0 for name in ('ready_verified', 'ready_unverified', 'queued', 'dispatch_pending', 'dispatched',
                                  'running_verified', 'running_unverified', 'completed', 'review_unverified', 'fdr_complete', 'fdr_incomplete')}
    for test in public:
        state = str(test.get('status') or test.get('state') or '').upper()
        attestation = test.get('readiness') or {}
        if state == 'READY':
            counts['ready_verified' if attestation.get('policy') == POLICY and attestation.get('eligible') else 'ready_unverified'] += 1
        elif state in {'QUEUED', 'DISPATCH_PENDING', 'DISPATCHED'}:
            counts[state.lower()] += 1
        elif state == 'RUNNING':
            started = timestamp(test.get('started_at'))
            verified = test.get('execution_observation') == 'GITHUB_JOB_STEP' and started and RUN_REF.fullmatch(str(test.get('run_ref') or ''))
            counts['running_verified' if verified else 'running_unverified'] += 1
        if test.get('verdict') and timestamp(test.get('executed_at')):
            counts['completed'] += 1
        if test.get('review_state') == 'CONFIRMED' and not (test.get('review_validation') or {}).get('eligible'):
            counts['review_unverified'] += 1
        fdr = test.get('fdr') or {}
        if fdr:
            counts['fdr_complete' if fdr.get('policy') == 'FULL_ROADMAP_FAMILY_V2' and fdr.get('coverage') == 'COMPLETE' else 'fdr_incomplete'] += 1
    return {'policy': POLICY, 'scope': 'PUBLIC_TESTS_ONLY', 'authority': 'TOWER_DERIVED', 'counts': counts,
            'throughput_per_hour': None, 'throughput_status': 'NOT_MEASURED',
            'counts_are_historical_totals': True, 'ready_scope': 'SPEC_AND_RECORDED_INPUT_BINDING',
            'independence_scope': 'DECLARATION_AND_PROVENANCE_NOT_SCIENTIFIC_PROOF'}


def guard_transition(root: Path, request: dict) -> dict | None:
    if request.get('entity_kind') != 'test':
        return None
    test_id = str(request.get('entity_name') or '')
    current = entity(root, test_id)
    changes = request.get('changes') or {}
    issue = 'PROTECTED_FIELD_MUTATION' if isinstance(changes, dict) and {'id', 'entity_id', 'entity_version'}.intersection(changes) else None
    if not isinstance(changes, dict):
        issue = 'INVALID_TEST_CHANGES'
        changes = {}
    next_test = {**current, **changes, "id": test_id}
    states = {str(next_test[k]).upper() for k in ('status', 'state') if next_test.get(k)}
    next_state = str(next_test.get('status') or next_test.get('state') or '').upper()
    if len(states) > 1 and any(k in changes for k in ('status', 'state')):
        issue = 'INCONSISTENT_TEST_STATES'
    result_fields = ('verdict', 'scientific_verdict', 'executed_at', 'result', 'statistics', 'decision', 'result_summary', 'reproducibility')
    if current and terminal(current):
        if next_state in ACTIVE | {'READY', 'DRAFT'} and next_state != str(current.get('status') or current.get('state') or '').upper():
            issue = 'TERMINAL_TEST_CANNOT_REOPEN'
        if any(k in changes and changes[k] != current.get(k) for k in result_fields):
            issue = 'TERMINAL_RESULT_IMMUTABLE'
    if current.get('prereg_hash') and any(k in changes and changes[k] != current.get(k) for k in (*FROZEN, 'prereg_hash', 'independence', 'independence_fingerprint')):
        issue = 'FROZEN_DEFINITION_IMMUTABLE'
    if str(current.get('id')) in active_tests(root) and any(k in changes and changes[k] != current.get(k) for k in ('recipe', 'recipe_params', 'data_binding')):
        issue = 'ACTIVE_EXECUTION_BINDING_IMMUTABLE'
    if next_state == 'READY' and any(k in changes for k in ('status', 'state', 'recipe', 'recipe_params', 'data_binding')):
        check = readiness(root, next_test)
        if not check['eligible']:
            issue = 'READY_INVARIANT:' + ','.join(check['reasons'])
    if next_state in ACTIVE and any(k in changes for k in ('status', 'state', 'battery_id', 'attempt_id')):
        battery = next((b for b in batteries(root) if b.get('id') == next_test.get('battery_id')), {})
        spec = next((t for t in battery.get('tests') or [] if t.get('test_id') == test_id), {})
        if not spec or spec.get('attempt_id') != next_test.get('attempt_id'):
            issue = 'CURRENT_RESERVATION_REQUIRED'
        if next_state == 'RUNNING' and (next_test.get('execution_observation') != 'GITHUB_JOB_STEP' or not timestamp(next_test.get('started_at')) or not RUN_REF.fullmatch(str(next_test.get('run_ref') or ''))):
            issue = 'RUNNER_STEP_EVIDENCE_REQUIRED'
    review = changes.get('review_state')
    if review in {'CONFIRMED', 'REFUTED'} and review != current.get('review_state'):
        if not (changes.get('decoy') is True and request.get('event_type') == 'DECOY_REVEALED'):
            from .evolution import _attack_outcome
            declaration = changes.get('mechanical_contest_verdict') or {}
            attack = entity(root, str(declaration.get('contest_test_id') or ''))
            validation = independence(current, attack, root)
            outcome = _attack_outcome(attack)
            expected = (attack.get('independence') or {}).get('on_pass' if outcome == 'CONFIRMED' else 'on_fail') if outcome else None
            if attack.get('contests_test_id') != test_id or not validation['eligible'] or not timestamp(attack.get('executed_at')) or expected != review:
                issue = 'REVIEW_EVIDENCE_REQUIRED'
    if issue:
        return {'request_id': request.get('request_id'), 'accepted': False, 'issue': {'code': issue, 'entity_name': test_id}}
    return None


def guard_batteries(root: Path, request: dict) -> dict | None:
    if request.get('document') != 'evolution/batteries.json':
        return None
    existing = {b['id']: b for b in batteries(root)}
    proposed = (request.get('merge') or {}).get('batteries')
    problem = None
    if not isinstance(proposed, list):
        proposed = []
        problem = 'BATTERY_REGISTRY_INVALID'
    seen, attempts, fingerprints = set(), set(), set()
    for battery in proposed:
        if not isinstance(battery, dict) or not battery.get('id') or battery['id'] in seen:
            problem = 'BATTERY_ID_INVALID_OR_DUPLICATE'; break
        seen.add(battery['id'])
        old = existing.get(battery['id'])
        if old and old.get('tests') != battery.get('tests'):
            problem = 'FROZEN_BATTERY_SPEC_IMMUTABLE'; break
        if not old and battery.get('status') != 'QUEUED':
            problem = 'NEW_BATTERY_MUST_BE_QUEUED'; break
        specs = battery.get('tests')
        if not isinstance(specs, list) or not specs or not all(isinstance(t, dict) for t in specs):
            problem = 'BATTERY_TESTS_INVALID'; break
        for spec in specs:
            tid = str(spec.get('test_id') or '')
            if not old:
                test = entity(root, tid)
                check = readiness(root, test)
                if not check['eligible'] or test.get('status') != 'READY' or spec.get('recipe') != test.get('recipe') or spec.get('params') != test.get('recipe_params') or spec.get('recipe_sha256') != check['recipe_sha256']:
                    problem = 'BATTERY_ADMISSION_FAILED'; break
                if not spec.get('attempt_id') or spec.get('execution_fingerprint') != execution_fingerprint(test, check['recipe_sha256']):
                    problem = 'ATTEMPT_FINGERPRINT_MISMATCH'; break
            if battery.get('status') in ACTIVE:
                fingerprint = spec.get('execution_fingerprint')
                if tid in attempts or (fingerprint and fingerprint in fingerprints):
                    # Historical duplicates remain visible; new reservations cannot add one.
                    prior_count = sum(t.get('test_id') == tid for b in existing.values() if b.get('status') in ACTIVE for t in b.get('tests') or [])
                    if not old or prior_count < 2:
                        problem = 'DUPLICATE_ACTIVE_EXECUTION'; break
                attempts.add(tid)
                if fingerprint:
                    fingerprints.add(fingerprint)
        if problem:
            break
    if any(b.get('status') in ACTIVE and bid not in seen for bid,b in existing.items()):
        problem = 'ACTIVE_RESERVATION_CANNOT_BE_DROPPED'
    if problem:
        return {'request_id':request.get('request_id'), 'accepted':False, 'issue':{'code':problem}}
    return None
