"""Deterministic admission and statistical checks; no network or alternate state store."""
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
TERMINAL = {'DONE', 'RESULT', 'COMPLETED', 'REJECTED', 'ARCHIVED', 'CANCELLED', 'CANCELED'}
CLOSED_REVIEW = {'CONFIRMED', 'REFUTED', 'ARCHIVED'}
ACTIVE_BATTERY = {'QUEUED', 'DISPATCH_PENDING', 'DISPATCHED', 'RUNNING'}
FROZEN = ('question', 'null', 'rival', 'method', 'dataset_and_selection', 'success_criteria', 'kill_criteria')
RESULT_FIELDS = {'result_meaning', 'result_meaning_source', 'verdict_plain', 'summary_plain',
                 'result', 'scientific_result', 'statistics', 'verdict', 'decision', 'executed_at',
                 'review_state', 'reviews', 'contests', 'fdr', 'mechanical_contest_verdict'}
RUN_REF = re.compile(r'^(?:https://github[.]com/byDenoso/Pantheon/)?actions/runs/([1-9][0-9]*)$')

def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()

def read(root: Path, relative: str) -> dict:
    path = root / relative
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    return value if isinstance(value, dict) else {}

def entity(root: Path, test_id: str) -> dict:
    path = entity_path(root, 'test', test_id)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

def terminal(test: dict) -> bool:
    return (str(test.get('status') or test.get('state') or '').upper() in TERMINAL
            or str(test.get('review_state') or '').upper() in CLOSED_REVIEW
            or bool(test.get('verdict')) or bool(test.get('executed_at')))

def active_tests(root: Path, exclude_battery: str = '') -> set[str]:
    return {str(t.get('test_id')) for b in read(root, 'evolution/batteries.json').get('batteries', [])
            if b.get('id') != exclude_battery and b.get('status') in ACTIVE_BATTERY
            for t in b.get('tests', []) if isinstance(t, dict)}

def readiness(root: Path, test: dict, *, ignore_reservation: bool = False) -> dict:
    """READY is relative to recorded input validation, never a promise of network uptime."""
    reasons = []
    if terminal(test):
        reasons.append('TERMINAL_TEST')
    for key in FROZEN:
        if not test.get(key):
            reasons.append('MISSING_' + key.upper())
    if not test.get('prereg_hash') or timestamp(test.get('frozen_at') or (test.get('prereg') or {}).get('at')) is None:
        reasons.append('FROZEN_DESIGN_UNVERIFIED')
    if test.get('prereg_hash'):
        from .evolution import prereg_hash
        if test['prereg_hash'] != prereg_hash(str(test.get('id') or ''), test):
            reasons.append('FROZEN_DESIGN_CHANGED')
    recipe = str(test.get('recipe') or '')
    params = test.get('recipe_params')
    if not re.fullmatch(r'[a-z0-9_]{2,40}', recipe) or not isinstance(params, dict):
        reasons.append('RECIPE_BINDING_MISSING')
    recipe_root = Path(os.environ.get('NEXO_RECIPE_ROOT', 'nexo-one/executor-runtime/recipes'))
    code = recipe_root / (recipe + '.py')
    smoke = recipe_root / 'smoke' / (recipe + '.json')
    recipe_sha = None
    if not recipe_root.is_dir():
        reasons.append('RECIPE_CATALOG_UNAVAILABLE')
    elif not code.is_file() or not smoke.is_file():
        reasons.append('RECIPE_OR_SMOKE_MISSING')
    else:
        try:
            raw = code.read_bytes()
            compile(raw, str(code), 'exec')
            json.loads(smoke.read_text(encoding='utf-8'))
            recipe_sha = hashlib.sha256(raw).hexdigest()
        except (SyntaxError, ValueError):
            reasons.append('RECIPE_OR_SMOKE_INVALID')
    binding = test.get('data_binding') or test.get('input_binding') or {}
    if not isinstance(binding, dict) or binding.get('status') != 'BOUND' or not valid_inputs(binding.get('inputs')):
        reasons.append('INPUT_AVAILABILITY_UNVERIFIED')
    dependencies = test.get('depends_on') or []
    if not isinstance(dependencies, list):
        reasons.append('DEPENDENCIES_INVALID')
        dependencies = []
    for dep_id in dependencies:
        dependency = entity(root, str(dep_id))
        if not terminal(dependency) or str(dependency.get('status') or '').upper() in {'ARCHIVED', 'CANCELLED', 'CANCELED'}:
            reasons.append('DEPENDENCY_UNRESOLVED')
            break
    if test.get('blocker') or str(test.get('status') or '').startswith(('WAIT', 'BLOCKED')):
        reasons.append('BLOCKER_PRESENT')
    if not ignore_reservation and (str(test.get('id')) in active_tests(root)
                                  or str(test.get('status') or '').upper() in {'RUNNING', 'QUEUED', 'DISPATCH_PENDING', 'DISPATCHED'}):
        reasons.append('ACTIVE_ATTEMPT')
    return {'policy': POLICY, 'eligible': not reasons, 'reasons': sorted(set(reasons)),
            'recipe_sha256': recipe_sha, 'input_scope': 'RECORDED_BINDING_REQUIRES_RUNNER_PREFLIGHT'}

def p_value(test: dict) -> float | None:
    result = test.get('result') if isinstance(test.get('result'), dict) else {}
    for holder in (result, test.get('statistics'), result.get('statistics')):
        if not isinstance(holder, dict):
            continue
        for key in ('p_value', 'p', 'pvalue'):
            value = holder.get(key)
            if isinstance(value, bool):
                continue
            try:
                value = float(value)
            except (ValueError, TypeError):
                continue
            if math.isfinite(value) and 0 <= value <= 1:
                return value
    return None

def fdr_annotations(tests: list[dict], q: float = .1) -> dict[str, dict]:
    """Full roadmap family, including negative results; incomplete coverage never passes."""
    groups = {}
    for test in tests:
        if test.get('roadmap_id') and not test.get('contests_test_id') and not test.get('decoy'):
            groups.setdefault(str(test['roadmap_id']), []).append(test)
    out = {}
    for family, group in groups.items():
        measured = [(p_value(t), t) for t in group]
        valid = sorted(((p, t) for p, t in measured if p is not None), key=lambda pair: (pair[0], str(pair[1]['id'])))
        total = len(group)
        complete = len(valid) == total
        running, adjusted = 1., {}
        for rank in range(len(valid), 0, -1):
            p, test = valid[rank - 1]
            running = min(running, p * total / rank)
            adjusted[str(test['id'])] = running
        for test in group:
            value = adjusted.get(str(test['id']))
            out[str(test['id'])] = {
                'method': 'BH', 'policy': 'FULL_ROADMAP_FAMILY_V2', 'family_id': family,
                'n': total, 'n_observed': len(valid), 'n_missing': total - len(valid), 'q': q,
                'q_value': round(value, 8) if complete and value is not None else None,
                'survives': bool(value <= q) if complete and value is not None else None,
                'coverage': 'COMPLETE' if complete else 'INCOMPLETE',
                'claim_effect': 'ANNOTATION_ONLY',
                'assumptions': 'FIXED_FAMILY_INDEPENDENCE_OR_PRDS; NOT_ONLINE_FDR',
            }
    return out

def independence(parent: dict, attack: dict) -> dict:
    """A different string is insufficient: require a frozen declared axis and evidence refs."""
    declaration = attack.get('independence') or {}
    if not isinstance(declaration, dict):
        declaration = {}
    reasons = []
    axis = declaration.get('axis')
    fields = {'data': 'dataset_and_selection', 'method': 'method', 'cohort': 'dataset_and_selection',
              'implementation': 'recipe'}
    if axis not in fields:
        reasons.append('INDEPENDENCE_AXIS_REQUIRED')
    else:
        key = fields[axis]
        a, b = parent.get(key), attack.get(key)
        if not a or not b or digest(a) == digest(b):
            reasons.append('INDEPENDENT_AXIS_NOT_DISTINCT')
    refs = declaration.get('evidence_refs')
    if not isinstance(refs, list) or not refs or not all(isinstance(x, str) and x.strip() for x in refs):
        reasons.append('INDEPENDENCE_EVIDENCE_REQUIRED')
    if declaration.get('on_pass') not in {'CONFIRMED', 'REFUTED'} or declaration.get('on_fail') not in {'CONFIRMED', 'REFUTED'} or declaration.get('on_pass') == declaration.get('on_fail'):
        reasons.append('ATTACK_POLARITY_REQUIRED')
    frozen, declared, executed = (timestamp(attack.get('frozen_at')), timestamp(declaration.get('frozen_at')), timestamp(attack.get('executed_at')))
    if frozen is None or declared is None or declared > frozen or (executed is not None and frozen > executed):
        reasons.append('INDEPENDENCE_NOT_FROZEN')
    if not attack.get('prereg_hash'):
        reasons.append('ATTACK_DESIGN_UNVERIFIED')
    else:
        from .evolution import prereg_hash
        if attack['prereg_hash'] != prereg_hash(str(attack.get('id') or ''), attack):
            reasons.append('ATTACK_DESIGN_CHANGED')
    if attack.get('independence_fingerprint') != digest(declaration):
        reasons.append('INDEPENDENCE_COMMITMENT_UNVERIFIED')
    return {'policy': POLICY, 'eligible': not reasons, 'reasons': reasons, 'axis': axis,
            'scope': 'DECLARED_AXIS_AND_PROVENANCE_NOT_AUTOMATIC_SCIENTIFIC_PROOF'}

def clean_result_fields(value: dict) -> dict:
    return {k: v for k, v in value.items() if k not in RESULT_FIELDS}


def timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def valid_inputs(inputs: Any) -> bool:
    if not isinstance(inputs, list) or not inputs:
        return False
    for value in inputs:
        if not isinstance(value, dict) or not value.get('name'):
            return False
        if value.get('kind') == 'generated':
            if value.get('seed') is None or not value.get('generator'):
                return False
        elif not str(value.get('url') or '').startswith('https://') or not value.get('version'):
            return False
        if not re.fullmatch(r'(sha256:)?[0-9a-f]{64}', str(value.get('sha256') or '')):
            return False
    return True


def guard_transition(root: Path, request: dict) -> dict | None:
    """Return a structured refusal for forbidden test transitions, including raw requests."""
    if request.get('entity_kind') != 'test':
        return None
    test_id = str(request.get('entity_name') or '')
    current = entity(root, test_id)
    changes = request.get('changes') or {}
    if not isinstance(changes, dict):
        return {'accepted':False, 'issue':{'code':'INVALID_TEST_CHANGES'}}
    next_test = {**current, **changes, 'id': test_id}
    next_state = str(next_test.get('status') or next_test.get('state') or '').upper()
    issue = None
    if current and terminal(current) and any(k in changes and changes[k] != current.get(k)
                                            for k in ('status', 'state', 'verdict', 'executed_at', 'result', 'statistics', 'decision', 'result_summary', 'reproducibility')):
        issue = 'TERMINAL_TEST_IMMUTABLE'
    elif current.get('prereg_hash') and any(k in changes and changes[k] != current.get(k) for k in (*FROZEN, 'claim_boundary', 'independence', 'independence_fingerprint')):
        issue = 'FROZEN_TEST_DEFINITION_IMMUTABLE'
    elif (str(current.get('id')) in active_tests(root)) and any(k in changes and changes[k] != current.get(k) for k in ('recipe', 'recipe_params', 'data_binding')):
        issue = 'ACTIVE_EXECUTION_BINDING_IMMUTABLE'
    elif next_state == 'READY' and (not current or current.get('status') != 'READY' or
                                  any(k in changes for k in ('recipe', 'recipe_params', 'data_binding', *FROZEN))):
        check = readiness(root, next_test)
        if not check['eligible']:
            issue = 'READY_INVARIANT:' + ','.join(check['reasons'])
    elif next_state in {'QUEUED', 'DISPATCH_PENDING', 'DISPATCHED', 'RUNNING'} and any(k in changes for k in ('state','status','attempt_id','battery_id')):
        battery = next((b for b in read(root, 'evolution/batteries.json').get('batteries', [])
                        if b.get('id') == next_test.get('battery_id')), {})
        spec = next((t for t in battery.get('tests', []) if t.get('test_id') == test_id), {})
        if not spec or spec.get('attempt_id') != next_test.get('attempt_id'):
            issue = 'ATTEMPT_RESERVATION_REQUIRED'
        elif next_state == 'RUNNING' and (not RUN_REF.fullmatch(str(battery.get('run_ref') or '')) or not timestamp(battery.get('started_at'))):
            issue = 'RUNNER_START_EVIDENCE_REQUIRED'
    if changes.get('review_state') in {'CONFIRMED', 'REFUTED'} and changes['review_state'] != current.get('review_state') and not (changes.get('decoy') is True and request.get('event_type') == 'DECOY_REVEALED'):
        verdict = changes.get('mechanical_contest_verdict') or {}
        attack = entity(root, str(verdict.get('contest_test_id') or ''))
        valid = independence(current, attack)
        from .evolution import _attack_outcome
        outcome = _attack_outcome(attack)
        required = (attack.get('independence') or {}).get('on_pass' if outcome == 'CONFIRMED' else 'on_fail') if outcome else None
        if attack.get('contests_test_id') != test_id or not valid['eligible'] or timestamp(attack.get('executed_at')) is None or required != changes['review_state']:
            issue = 'REVIEW_EVIDENCE_REQUIRED'
    if issue:
        return {'request_id': request.get('request_id'), 'accepted': False,
                'issue': {'code': issue, 'entity_name': test_id}}
    return None


def public_execution_summary(root: Path, tests: list[dict]) -> dict:
    """Read persisted attestations only; no private IDs, parameters, URLs or second read model."""
    from .semantics import is_private, resolve
    public = [t for t in tests if not t.get('private') and not is_private(resolve(t, entity_id=str(t.get('id') or '')))]
    counts = {k: 0 for k in ('ready_verified', 'ready_unverified', 'queued', 'dispatch_pending',
                            'dispatched', 'running_verified', 'running_unverified', 'completed',
                            'review_unverified', 'fdr_complete', 'fdr_incomplete')}
    for test in public:
        state = str(test.get('status') or test.get('state') or '').upper()
        attestation = test.get('readiness') or {}
        if state == 'READY':
            counts['ready_verified' if attestation.get('policy') == POLICY and attestation.get('eligible') else 'ready_unverified'] += 1
        elif state in {'QUEUED', 'DISPATCH_PENDING', 'DISPATCHED'}:
            counts[state.lower()] += 1
        elif state == 'RUNNING':
            counts['running_verified' if test.get('execution_phase') == 'RUNNING' and timestamp(test.get('started_at')) and RUN_REF.fullmatch(str(test.get('run_ref') or '')) else 'running_unverified'] += 1
        if test.get('verdict') and timestamp(test.get('executed_at')):
            counts['completed'] += 1
        if test.get('review_state') == 'CONFIRMED' and not (test.get('review_validation') or {}).get('eligible'):
            counts['review_unverified'] += 1
        fdr = test.get('fdr') or {}
        if fdr:
            counts['fdr_complete' if fdr.get('policy') == 'FULL_ROADMAP_FAMILY_V2' and fdr.get('coverage') == 'COMPLETE' else 'fdr_incomplete'] += 1
    return {'policy': POLICY, 'scope': 'PUBLIC_TESTS_ONLY', 'authority': 'TOWER_DERIVED',
            'counts': counts, 'throughput_per_hour': None,
            'throughput_status': 'NOT_MEASURED', 'counts_are_historical_totals': True,
            'ready_definition': 'FROZEN_DESIGN_RECIPE_AND_RECORDED_INPUT_PROVENANCE',
            'network_availability': 'RECHECK_AT_EXECUTION'}


def execution_fingerprint(test: dict, recipe_sha: str | None) -> str:
    binding = test.get('data_binding') or test.get('input_binding') or {}
    return digest({**{key:test.get(key) for key in (*FROZEN, 'claim_boundary')},
                   'recipe':test.get('recipe'), 'params':test.get('recipe_params'),
                   'recipe_sha256':recipe_sha, 'inputs':binding.get('inputs')})


def guard_batteries(root: Path, request: dict) -> dict | None:
    if request.get('document') != 'evolution/batteries.json':
        return None
    old = {b['id']: b for b in read(root, 'evolution/batteries.json').get('batteries', [])}
    proposed = (request.get('merge') or {}).get('batteries')
    if not isinstance(proposed, list):
        return {'accepted':False, 'issue':{'code':'BATTERY_REGISTRY_INVALID'}}
    seen_ids, active_ids, active_fingerprints = set(), set(), set()
    error = None
    for battery in proposed:
        if not isinstance(battery, dict) or not battery.get('id') or battery['id'] in seen_ids:
            error = 'BATTERY_ID_DUPLICATE_OR_INVALID'; break
        seen_ids.add(battery['id'])
        prior = old.get(battery['id'])
        if prior and battery.get('tests') != prior.get('tests'):
            error = 'FROZEN_BATTERY_SPEC_IMMUTABLE'; break
        if not prior and battery.get('status') != 'QUEUED':
            error = 'NEW_BATTERY_MUST_BE_QUEUED'; break
        if not isinstance(battery.get('tests'), list) or not battery['tests'] or not all(isinstance(t, dict) for t in battery['tests']):
            error = 'BATTERY_TESTS_INVALID'; break
        for spec in battery['tests']:
            tid = str(spec.get('test_id') or '')
            if not prior:
                test = entity(root, tid)
                check = readiness(root, test)
                if test.get('status') != 'READY' or not check['eligible'] or spec.get('recipe') != test.get('recipe') or spec.get('params') != test.get('recipe_params') or spec.get('recipe_sha256') != check['recipe_sha256']:
                    error = 'BATTERY_ADMISSION_FAILED'; break
            if battery.get('status') in ACTIVE_BATTERY:
                key = spec.get('execution_fingerprint')
                if tid in active_ids or (key and key in active_fingerprints):
                    # Preserve pre-existing legacy duplicates without admitting any new one.
                    prior_occurrences = sum(t.get('test_id') == tid for b in old.values() if b.get('status') in ACTIVE_BATTERY for t in b.get('tests', []))
                    if not prior or prior_occurrences < 2:
                        error = 'DUPLICATE_ACTIVE_EXECUTION'; break
                active_ids.add(tid)
                if key:
                    active_fingerprints.add(key)
        if error:
            break
    if any(b.get('status') in ACTIVE_BATTERY and bid not in seen_ids for bid,b in old.items()):
        error = 'ACTIVE_RESERVATION_CANNOT_BE_DROPPED'
    if error:
        return {'request_id':request.get('request_id'), 'accepted':False, 'issue':{'code':error}}
    return None
