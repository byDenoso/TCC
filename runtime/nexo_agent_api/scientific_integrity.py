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
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .tower_paths import entity_path

POLICY = 'SCIENTIFIC_INTEGRITY_V1'
ACTIVE = {'QUEUED', 'DISPATCH_PENDING', 'DISPATCHED', 'RUNNING'}
TERMINAL = {'DONE', 'RESULT', 'VERIFIED', 'COMPLETED', 'REJECTED', 'ARCHIVED', 'CANCELLED', 'CANCELED'}
EXECUTION_PHASE_RECONCILIATION_POLICY = 'EXECUTION_PHASE_RECONCILIATION_V1'
EXECUTION_PHASE_SOURCE_PROOF_CONTRACT = 'EXECUTION_PHASE_SOURCE_PROOF_V1'
EXECUTION_PHASE_CLOSED = 'COMPLETED'
EXECUTION_PHASE_EVENT_TARGETS = {
    'TEST_QUEUED': {'QUEUED'},
    'TEST_DISPATCH_PENDING': {'DISPATCH_PENDING'},
    'TEST_DISPATCHED': {'DISPATCHED'},
    'TEST_RUNNING': {'RUNNING'},
    'TEST_RUNTIME_FAILURE': {'READY', 'BLOCKED_INPUT'},
    'TEST_INPUT_UNAVAILABLE': {'BLOCKED_INPUT'},
    'TEST_RESULT_RECORDED': {EXECUTION_PHASE_CLOSED},
}
class _RunnerBatteryStatusToken:
    def __deepcopy__(self, memo):
        return self


RUNNER_BATTERY_STATUS_TOKEN = _RunnerBatteryStatusToken()
WRITER_DISPATCH_TOKEN = _RunnerBatteryStatusToken()
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
    try:
        path = entity_path(root, 'test', test_id)
    except ValueError:
        return {}
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


def _phase_reconciliation_protected(test: dict) -> bool:
    """Keep CAMB/MCMC and cosmology test records outside this repair."""
    identity_fields = ('id', 'domain', 'target_domain', 'roadmap_id', 'campaign_id',
                       'test_group_id', 'recipe', 'execution_recipe')
    values = [str(test.get(key) or '').upper() for key in identity_fields]
    if any(value in {'COSMOLOGY', 'COSMOLOGIA', 'OBSERVATIONAL_COSMOLOGY'} for value in values[1:3]):
        return True
    return any(re.search(r'(^|[^A-Z0-9])(?:CAMB|MCMC)([^A-Z0-9]|$)', value) for value in values)


def _trusted_source_git_root() -> Path:
    """Return this package's checkout for read-only source-proof verification."""
    return Path(__file__).resolve().parents[2]


def _source_battery_envelopes(value: Any):
    if isinstance(value, dict):
        kind = str(value.get('kind') or value.get('type') or value.get('event_type') or '').upper().replace('-', '_')
        payload = value.get('payload') if isinstance(value.get('payload'), dict) else value
        if kind in {'TEST_BATTERY', 'BATTERY'} and isinstance(payload, dict) and isinstance(payload.get('tests'), list):
            yield payload
        for child in value.values():
            yield from _source_battery_envelopes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _source_battery_envelopes(child)


def _verified_original_submission(battery_id: str, submission_fingerprint: Any,
                                  proof: Any) -> tuple[dict | None, str | None]:
    """Re-read one immutable inbox Git blob and bind it to the stored hash.

    A caller-supplied proof is only a locator. The Writer rechecks the remote
    inbox ref, commit ancestry, blob bytes, full envelope hash, battery ID,
    exact test payload, and the canonical source submission fingerprint.
    """
    if not isinstance(proof, dict) or proof.get('contract') != EXECUTION_PHASE_SOURCE_PROOF_CONTRACT:
        return None, 'BATTERY_ORIGINAL_SUBMISSION_PROOF_REQUIRED'
    submitted_specs = proof.get('submitted_specs')
    if proof.get('battery_id') != battery_id or not isinstance(submitted_specs, list):
        return None, 'BATTERY_SOURCE_PROOF_IDENTITY_INVALID'
    try:
        submitted_fingerprint = digest(submitted_specs)
    except (TypeError, ValueError):
        return None, 'BATTERY_SOURCE_PROOF_PAYLOAD_INVALID'
    if (submitted_fingerprint != submission_fingerprint
            or proof.get('submission_fingerprint') != submission_fingerprint):
        return None, 'BATTERY_SOURCE_PROOF_FINGERPRINT_MISMATCH'

    artifacts = proof.get('source_artifacts')
    # A source proof must identify one unambiguous immutable request artifact.
    if not isinstance(artifacts, list) or len(artifacts) != 1 or not isinstance(artifacts[0], dict):
        return None, 'BATTERY_SOURCE_PROOF_AMBIGUOUS'
    artifact = artifacts[0]
    repository = artifact.get('repository')
    git_ref = artifact.get('git_ref')
    commit = artifact.get('commit')
    object_id = artifact.get('object_id')
    source_path = artifact.get('path')
    source_sha256 = artifact.get('source_sha256')
    if (repository != 'TCC' or git_ref != 'refs/remotes/origin/nexo-inbox'
            or not isinstance(commit, str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', commit)
            or not isinstance(object_id, str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', object_id)
            or not isinstance(source_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', source_sha256)
            or not isinstance(source_path, str)
            or not (source_path.startswith('inbox/')
                    or source_path.startswith('nexo-inbox/')
                    or source_path.startswith('nexo_persist/requests/'))
            or '\\' in source_path or any(part in {'', '.', '..'} for part in source_path.split('/'))):
        return None, 'BATTERY_SOURCE_PROOF_REFERENCE_INVALID'

    repo_root = _trusted_source_git_root()
    try:
        reachable = subprocess.run(
            ['git', '-C', str(repo_root), 'merge-base', '--is-ancestor', commit, git_ref],
            capture_output=True, check=False, timeout=10)
        if reachable.returncode != 0:
            return None, 'BATTERY_SOURCE_PROOF_COMMIT_NOT_REACHABLE'
        blob = subprocess.run(
            ['git', '-C', str(repo_root), 'cat-file', 'blob', object_id],
            capture_output=True, check=False, timeout=10)
        if blob.returncode != 0 or hashlib.sha256(blob.stdout).hexdigest() != source_sha256:
            return None, 'BATTERY_SOURCE_PROOF_BLOB_HASH_MISMATCH'
        committed = subprocess.run(
            ['git', '-C', str(repo_root), 'show', f'{commit}:{source_path}'],
            capture_output=True, check=False, timeout=10)
        if (committed.returncode != 0 or committed.stdout != blob.stdout
                or hashlib.sha256(committed.stdout).hexdigest() != source_sha256):
            return None, 'BATTERY_SOURCE_PROOF_COMMIT_READBACK_MISMATCH'
        source_document = json.loads(committed.stdout.decode('utf-8'))
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError, ValueError):
        return None, 'BATTERY_SOURCE_PROOF_UNAVAILABLE'

    matches = [payload for payload in _source_battery_envelopes(source_document)
               if payload.get('battery_id') == battery_id
               and payload.get('tests') == submitted_specs]
    if len(matches) != 1:
        return None, 'BATTERY_SOURCE_PROOF_ENVELOPE_NOT_UNIQUE'
    normalized = {
        'contract': EXECUTION_PHASE_SOURCE_PROOF_CONTRACT,
        'battery_id': battery_id,
        'submission_fingerprint': submitted_fingerprint,
        'submitted_specs': submitted_specs,
        'source_artifacts': [{
            'repository': repository, 'git_ref': git_ref, 'commit': commit,
            'object_id': object_id, 'path': source_path, 'source_sha256': source_sha256,
        }],
    }
    return normalized, None


def execution_phase_reconciliation_evidence(
        root: Path, test: dict, *, source_submission_proof: dict | None = None
) -> tuple[dict | None, list[str]]:
    """Return exact, revalidatable proof for closing one legacy RUNNING phase.

    A terminal status by itself is deliberately insufficient. The reservation,
    frozen experiment, runner observation, result, and completed battery must
    all identify the same attempt.
    """
    reasons: list[str] = []
    test_id = str(test.get('id') or '')
    status = str(test.get('status') or test.get('state') or '').upper()
    if status not in TERMINAL or not terminal(test) or not test.get('verdict'):
        reasons.append('TERMINAL_RESULT_REQUIRED')
    if str(test.get('execution_phase') or '').upper() != 'RUNNING':
        reasons.append('LEGACY_RUNNING_PHASE_REQUIRED')
    if test.get('execution_phase_reconciliation'):
        reasons.append('RECONCILIATION_METADATA_ALREADY_PRESENT')
    if _phase_reconciliation_protected(test):
        reasons.append('PROTECTED_CAMB_MCMC_SCOPE')
    version = test.get('entity_version')
    if type(version) is not int or version < 1:
        reasons.append('SOURCE_ENTITY_VERSION_REQUIRED')
    if not test_id:
        reasons.append('TEST_ID_REQUIRED')

    battery_id = str(test.get('battery_id') or '')
    attempt_id = str(test.get('attempt_id') or '')
    run_ref = str(test.get('run_ref') or '')
    execution_recipe_sha = str(test.get('execution_recipe_sha256') or '')
    reproducibility = test.get('reproducibility') if isinstance(test.get('reproducibility'), dict) else {}
    if not battery_id:
        reasons.append('BATTERY_ID_REQUIRED')
    if not re.fullmatch(r'attempt-[0-9a-f]{32}', attempt_id):
        reasons.append('ATTEMPT_ID_INVALID')
    if not RUN_REF.fullmatch(run_ref):
        reasons.append('RUN_REF_INVALID')
    if not re.fullmatch(r'[0-9a-f]{64}', execution_recipe_sha):
        reasons.append('EXECUTION_RECIPE_HASH_INVALID')
    if test.get('execution_observation') != 'GITHUB_JOB_STEP':
        reasons.append('RUNNER_STEP_OBSERVATION_REQUIRED')
    started_at = timestamp(test.get('started_at'))
    executed_at = timestamp(test.get('executed_at'))
    if started_at is None:
        reasons.append('RUNNER_STEP_START_REQUIRED')
    if executed_at is None:
        reasons.append('RESULT_EXECUTION_TIME_REQUIRED')
    if any(reproducibility.get(key) != value for key, value in (
            ('battery_id', battery_id), ('attempt_id', attempt_id), ('run_ref', run_ref),
            ('recipe_sha256', execution_recipe_sha))):
        reasons.append('RESULT_ATTEMPT_PROVENANCE_MISMATCH')

    try:
        registry = batteries(root)
    except (OSError, ValueError, TypeError):
        registry = []
        reasons.append('BATTERY_REGISTRY_UNAVAILABLE')
    matches = [battery for battery in registry if isinstance(battery, dict) and battery.get('id') == battery_id]
    battery = matches[0] if len(matches) == 1 else {}
    if len(matches) != 1:
        reasons.append('BATTERY_MATCH_NOT_UNIQUE')

    spec = None
    completed_at = None
    verified_external_submission = None
    if battery:
        if battery.get('mandate_id') and (battery.get('started_tests') or {}).get(test_id) != test.get('started_at'):
            reasons.append('RUNNER_TEST_START_COMMITMENT_REQUIRED')
        if str(battery.get('status') or '').upper() != 'DONE':
            reasons.append('BATTERY_NOT_TERMINAL')
        if battery.get('execution_observation') != 'GITHUB_RUN_AND_ARTIFACT':
            reasons.append('RUNNER_COMPLETION_OBSERVATION_REQUIRED')
        if str(battery.get('conclusion') or '').lower() != 'success':
            reasons.append('RUNNER_SUCCESS_CONCLUSION_REQUIRED')
        if type(battery.get('ok')) is not int or battery.get('ok') < 1:
            reasons.append('BATTERY_SUCCESS_COUNT_REQUIRED')
        submitted_specs = battery.get('submitted_specs')
        if submitted_specs is None:
            verified_external_submission, source_error = _verified_original_submission(
                battery_id, battery.get('submission_fingerprint'), source_submission_proof)
            if source_error:
                reasons.append(source_error)
            else:
                submitted_specs = verified_external_submission.get('submitted_specs')
        else:
            try:
                submission_fingerprint = digest(submitted_specs) if isinstance(submitted_specs, list) else None
            except (TypeError, ValueError):
                submission_fingerprint = None
            if battery.get('submission_fingerprint') != submission_fingerprint:
                reasons.append('BATTERY_SUBMISSION_FINGERPRINT_MISMATCH')
        if battery.get('run_ref') != run_ref or not RUN_REF.fullmatch(str(battery.get('run_ref') or '')):
            reasons.append('BATTERY_RUN_REF_MISMATCH')
        completed_at = timestamp(battery.get('completed_at'))
        done_at = timestamp(battery.get('done_at'))
        if completed_at is None or done_at is None or completed_at != done_at:
            reasons.append('BATTERY_COMPLETION_TIME_INVALID')
        battery_tests = battery.get('tests') or []
        specs = [entry for entry in battery_tests
                 if isinstance(entry, dict) and entry.get('test_id') == test_id]
        spec = specs[0] if len(specs) == 1 else None
        if len(specs) != 1:
            reasons.append('BATTERY_ATTEMPT_SPEC_NOT_UNIQUE')
        if isinstance(submitted_specs, list) and isinstance(battery_tests, list):
            source_ids = [entry.get('test_id') for entry in submitted_specs if isinstance(entry, dict)]
            if (len(source_ids) != len(submitted_specs) or len(source_ids) != len(battery_tests)
                    or len(set(source_ids)) != len(source_ids)):
                reasons.append('BATTERY_SUBMISSION_MEMBERSHIP_MISMATCH')
            else:
                for source_spec, attempt_spec in zip(submitted_specs, battery_tests):
                    try:
                        timeout_min = max(1, min(int(source_spec.get('timeout_min') or 30), 340))
                    except (TypeError, ValueError, OverflowError):
                        reasons.append('BATTERY_SUBMISSION_TIMEOUT_INVALID')
                        break
                    if (source_spec.get('test_id') != attempt_spec.get('test_id')
                            or source_spec.get('recipe') != attempt_spec.get('recipe')
                            or source_spec.get('params') != attempt_spec.get('params')
                            or attempt_spec.get('timeout_min') != timeout_min):
                        reasons.append('BATTERY_SUBMISSION_ATTEMPT_BINDING_MISMATCH')
                        break
    if spec:
        binding = test.get('data_binding') or test.get('input_binding') or {}
        inputs = binding.get('inputs') if isinstance(binding, dict) else None
        if spec.get('attempt_id') != attempt_id:
            reasons.append('BATTERY_ATTEMPT_ID_MISMATCH')
        if spec.get('prereg_hash') != test.get('prereg_hash') or not test.get('prereg_hash'):
            reasons.append('BATTERY_PREREG_HASH_MISMATCH')
        if spec.get('recipe') != test.get('recipe') or spec.get('params') != test.get('recipe_params'):
            reasons.append('BATTERY_RECIPE_BINDING_MISMATCH')
        if spec.get('recipe_sha256') != execution_recipe_sha or spec.get('inputs') != inputs:
            reasons.append('BATTERY_EXECUTION_HASH_OR_INPUT_MISMATCH')
        if test.get('prereg_hash'):
            from .evolution import prereg_hash
            if test.get('prereg_hash') != prereg_hash(test_id, test):
                reasons.append('FROZEN_PREREG_HASH_MISMATCH')
        expected_fingerprint = execution_fingerprint(test, str(spec.get('recipe_sha256') or ''),
                                                     spec.get('param_preflight'))
        if spec.get('execution_fingerprint') != expected_fingerprint:
            reasons.append('ATTEMPT_FINGERPRINT_MISMATCH')
        readiness = test.get('readiness') if isinstance(test.get('readiness'), dict) else {}
        if readiness.get('param_preflight') != spec.get('param_preflight'):
            reasons.append('ATTEMPT_PREFLIGHT_MISMATCH')

    if started_at and executed_at and executed_at < started_at:
        reasons.append('RESULT_PRECEDES_ATTEMPT_START')
    if executed_at and completed_at and executed_at > completed_at:
        reasons.append('RESULT_FOLLOWS_RUNNER_COMPLETION')
    if reasons:
        return None, sorted(set(reasons))

    try:
        battery_fingerprint = digest(battery)
    except (TypeError, ValueError):
        return None, ['BATTERY_RECORD_NOT_CANONICAL']
    evidence = {
        'battery_id': battery_id,
        'attempt_id': attempt_id,
        'run_ref': run_ref,
        'recipe_sha256': execution_recipe_sha,
        'prereg_hash': str(test.get('prereg_hash')),
        'execution_fingerprint': str(spec.get('execution_fingerprint')),
        'battery_fingerprint': battery_fingerprint,
        'started_at': str(test.get('started_at')),
        'executed_at': str(test.get('executed_at')),
        'completed_at': str(battery.get('completed_at')),
    }
    if verified_external_submission is not None:
        evidence['source_submission_proof'] = verified_external_submission
    return evidence, []


def _terminal_result_attempt_evidence(root: Path, current: dict, request: dict) -> tuple[dict | None, list[str]]:
    """Revalidate a new terminal result against its already recorded runner attempt.

    The result mutation is applied after the canonical battery DONE update.  We
    therefore combine the existing RUNNING entity with the proposed result,
    while asking the same strict attempt validator used by historical phase
    reconciliation to verify the current battery, attempt, runner receipt,
    frozen input binding, and result timestamps.
    """
    if str(current.get('execution_phase') or '').upper() != 'RUNNING':
        return None, ['CURRENT_ATTEMPT_NOT_RUNNING']
    if str(current.get('status') or current.get('state') or '').upper() != 'RUNNING':
        return None, ['CURRENT_TEST_NOT_RUNNING']
    expected_version = request.get('expected_version')
    if type(expected_version) is not int or expected_version != current.get('entity_version'):
        return None, ['CURRENT_ENTITY_VERSION_MISMATCH']
    changes = request.get('changes')
    if not isinstance(changes, dict) or changes.get('execution_phase') != EXECUTION_PHASE_CLOSED:
        return None, ['TERMINAL_RESULT_MUST_CLOSE_EXECUTION_PHASE']
    merged = {**current, **changes, 'execution_phase': 'RUNNING'}
    return execution_phase_reconciliation_evidence(root, merged)


def _reservation_attempt(root: Path, test: dict) -> tuple[dict | None, dict | None]:
    """Resolve exactly one canonical battery/spec matching a test attempt."""
    battery_id = str(test.get('battery_id') or '')
    test_id = str(test.get('id') or '')
    attempt_id = str(test.get('attempt_id') or '')
    if not battery_id or not test_id or not attempt_id:
        return None, None
    try:
        matches = [battery for battery in batteries(root)
                   if isinstance(battery, dict) and battery.get('id') == battery_id]
    except (OSError, ValueError, TypeError):
        return None, None
    if len(matches) != 1:
        return None, None
    battery = matches[0]
    specs = [spec for spec in battery.get('tests') or []
             if isinstance(spec, dict) and spec.get('test_id') == test_id]
    if len(specs) != 1:
        return None, None
    spec = specs[0]
    binding = test.get('data_binding') or test.get('input_binding') or {}
    inputs = binding.get('inputs') if isinstance(binding, dict) else None
    if (spec.get('attempt_id') != attempt_id
            or spec.get('prereg_hash') != test.get('prereg_hash')
            or spec.get('recipe') != test.get('recipe')
            or spec.get('params') != test.get('recipe_params')
            or spec.get('recipe_sha256') != test.get('execution_recipe_sha256')
            or spec.get('inputs') != inputs):
        return None, None
    try:
        fingerprint = execution_fingerprint(test, str(spec.get('recipe_sha256') or ''),
                                            spec.get('param_preflight'))
    except (KeyError, TypeError, ValueError):
        return None, None
    if spec.get('execution_fingerprint') != fingerprint:
        return None, None
    return battery, spec


def _failure_phase_attempt_proof(root: Path, request: dict, current: dict,
                                 next_test: dict, event: str,
                                 target: str) -> bool:
    """Verify a runner-backed operational failure without inventing science.

    Unlike successful result closure, this path may preserve a legacy
    reservation with no attempt fingerprint or a current test whose input
    binding disappeared after dispatch. The private battery receipt binds the
    exact DONE runner event, one immutable battery spec, and the exact failed
    result entry. Missing current provenance is tolerated only here; any
    present provenance must still match the retained spec.
    """
    changes = request.get('changes')
    failure = next_test.get('last_runtime_failure')
    if not isinstance(changes, dict) or not isinstance(failure, dict):
        return False
    allowed_changes = {
        'status', 'state', 'execution_phase', 'execution',
        'runtime_failure_count', 'last_runtime_failure', 'blocker', 'readiness',
    }
    if set(changes) - allowed_changes:
        return False
    allowed_failure_fields = {
        'battery_id', 'attempt_id', 'recipe_sha256', 'run_ref', 'at', 'class',
        'reason', 'failure_stage', 'detail', 'param_preflight', 'log_tail',
        'runner_result_sha256', 'runner_spec_sha256', 'runner_result_kind',
    }
    if set(failure) - allowed_failure_fields:
        return False
    if target not in {'READY', 'BLOCKED_INPUT'}:
        return False
    if event == 'TEST_INPUT_UNAVAILABLE':
        if target != 'BLOCKED_INPUT' or failure.get('class') != 'INPUT_UNAVAILABLE':
            return False
    elif event == 'TEST_RUNTIME_FAILURE':
        if failure.get('class') == 'INPUT_UNAVAILABLE':
            return False
    else:
        return False

    battery_id = str(current.get('battery_id') or '')
    test_id = str(current.get('id') or '')
    current_status = str(current.get('status') or current.get('state') or '').upper()
    current_phase = str(current.get('execution_phase') or '').upper()
    if (not battery_id or not test_id or failure.get('battery_id') != battery_id
            or (current_status not in ACTIVE and current_phase not in ACTIVE)):
        return False
    try:
        matches = [battery for battery in batteries(root)
                   if isinstance(battery, dict) and battery.get('id') == battery_id]
    except (OSError, ValueError, TypeError):
        return False
    if len(matches) != 1:
        return False
    battery = matches[0]
    specs = [spec for spec in battery.get('tests') or []
             if isinstance(spec, dict) and spec.get('test_id') == test_id]
    if len(specs) != 1:
        return False
    spec = specs[0]

    run_ref = str(battery.get('run_ref') or '')
    completed = timestamp(battery.get('completed_at'))
    failed_count = battery.get('failed')
    if (str(battery.get('status') or '').upper() != 'DONE'
            or battery.get('execution_observation') != 'GITHUB_RUN_AND_ARTIFACT'
            or not RUN_REF.fullmatch(run_ref)
            or completed is None
            or completed != timestamp(battery.get('done_at'))
            or type(failed_count) is not int or failed_count < 1
            or battery.get('run_ref') != failure.get('run_ref')
            or timestamp(failure.get('at')) != completed):
        return False

    prereg_hash = str(current.get('prereg_hash') or '')
    recipe = str(current.get('recipe') or '')
    params = current.get('recipe_params')
    if (not prereg_hash or spec.get('prereg_hash') != prereg_hash
            or not recipe or spec.get('recipe') != recipe
            or not isinstance(params, dict) or spec.get('params') != params):
        return False
    spec_attempt = spec.get('attempt_id')
    current_attempt = current.get('attempt_id')
    if (bool(spec_attempt) != bool(current_attempt)
            or (spec_attempt and spec_attempt != current_attempt)
            or failure.get('attempt_id') != spec_attempt):
        return False
    spec_recipe_sha = spec.get('recipe_sha256')
    current_recipe_sha = current.get('execution_recipe_sha256')
    if (bool(spec_recipe_sha) != bool(current_recipe_sha)
            or (spec_recipe_sha and spec_recipe_sha != current_recipe_sha)
            or failure.get('recipe_sha256') != spec_recipe_sha):
        return False

    binding = current.get('data_binding') or current.get('input_binding')
    current_inputs = binding.get('inputs') if isinstance(binding, dict) else None
    if current_inputs is not None and spec.get('inputs') != current_inputs:
        return False
    spec_fingerprint = spec.get('execution_fingerprint')
    if spec_fingerprint:
        if current_inputs is not None:
            try:
                recomputed = execution_fingerprint(current, str(spec_recipe_sha or ''),
                                                   spec.get('param_preflight'))
            except (KeyError, TypeError, ValueError):
                return False
            if recomputed != spec_fingerprint:
                return False
    elif spec_attempt or spec_recipe_sha:
        # New reservations carry the fingerprint. Its absence is accepted
        # only for the explicitly legacy, no-attempt/no-recipe-hash case.
        return False

    receipts = battery.get('phase_failure_receipts')
    if not isinstance(receipts, list):
        return False
    receipt_matches = [row for row in receipts
                       if isinstance(row, dict) and row.get('test_id') == test_id]
    if len(receipt_matches) != 1:
        return False
    receipt = receipt_matches[0]
    spec_sha = 'sha256:' + digest(spec)
    result_sha = str(receipt.get('result_sha256') or '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', result_sha):
        return False
    if (receipt.get('battery_id') != battery_id
            or receipt.get('spec_sha256') != spec_sha
            or receipt.get('result_sha256') != failure.get('runner_result_sha256')
            or receipt.get('spec_sha256') != failure.get('runner_spec_sha256')
            or receipt.get('receipt_kind') != failure.get('runner_result_kind')
            or receipt.get('run_ref') != run_ref
            or receipt.get('completed_at') != battery.get('completed_at')
            or receipt.get('done_at') != battery.get('done_at')
            or receipt.get('attempt_id') != spec_attempt
            or receipt.get('recipe_sha256') != spec_recipe_sha
            or receipt.get('prereg_hash') != prereg_hash
            or receipt.get('recipe') != recipe
            or receipt.get('params_sha256') != 'sha256:' + digest(spec.get('params'))
            or receipt.get('failure_class') != failure.get('class')
            or receipt.get('failure_stage') != failure.get('failure_stage')
            or receipt.get('event_type') != event
            or receipt.get('phase_target') != target):
        return False
    if receipt.get('receipt_kind') not in {'RUNNER_FAILURE_ENTRY', 'RUNNER_RESULTS_MISSING'}:
        return False
    return True


def _phase_transition_proof(root: Path, request: dict, current: dict, next_test: dict,
                            current_phase: str, next_state: str) -> str | None:
    """Fail closed unless a phase change matches its one supported event and evidence."""
    changes = request.get('changes')
    if not isinstance(changes, dict):
        return 'EXECUTION_PHASE_CHANGES_INVALID'
    target = str(changes.get('execution_phase') or '').upper()
    event = str(request.get('event_type') or '')
    if target == EXECUTION_PHASE_CLOSED and event != 'TEST_RESULT_RECORDED':
        return 'EXECUTION_PHASE_CLOSURE_REQUIRES_VERIFIED_RESULT'
    allowed = EXECUTION_PHASE_EVENT_TARGETS.get(event)
    if allowed is None or target not in allowed:
        return 'EXECUTION_PHASE_EVENT_TARGET_INVALID'
    if request.get('writer_role') != 'EXECUTOR':
        return 'EXECUTION_PHASE_EXECUTOR_REQUIRED'
    expected_version = request.get('expected_version')
    if type(expected_version) is not int or expected_version != current.get('entity_version'):
        return 'EXECUTION_PHASE_SOURCE_VERSION_INVALID'
    if event != 'TEST_RESULT_RECORDED' and next_state != target:
        return 'EXECUTION_PHASE_STATUS_MISMATCH'
    if event == 'TEST_RESULT_RECORDED':
        proof, _reasons = _terminal_result_attempt_evidence(root, current, request)
        return None if proof is not None else 'EXECUTION_PHASE_RESULT_PROOF_REQUIRED'
    if event in {'TEST_RUNTIME_FAILURE', 'TEST_INPUT_UNAVAILABLE'}:
        return (None if _failure_phase_attempt_proof(root, request, current,
                                                     next_test, event, target)
                else 'EXECUTION_PHASE_FAILURE_PROOF_REQUIRED')

    phase_sources = {
        'TEST_QUEUED': {'', 'READY'},
        'TEST_DISPATCH_PENDING': {'QUEUED', 'DISPATCH_PENDING'},
        'TEST_DISPATCHED': {'QUEUED', 'DISPATCH_PENDING', 'DISPATCHED'},
        'TEST_RUNNING': {'QUEUED', 'DISPATCH_PENDING', 'DISPATCHED', 'RUNNING'},
        'TEST_RUNTIME_FAILURE': ACTIVE,
        'TEST_INPUT_UNAVAILABLE': ACTIVE,
    }
    source_status = str(current.get('status') or current.get('state') or '').upper()
    if (event in phase_sources and current_phase not in phase_sources[event]
            and source_status not in phase_sources[event]):
        return 'EXECUTION_PHASE_SOURCE_STATE_INVALID'

    battery, spec = _reservation_attempt(root, next_test)
    if battery is None or spec is None:
        return 'EXECUTION_PHASE_RESERVATION_PROOF_REQUIRED'
    battery_status = str(battery.get('status') or '').upper()
    if event == 'TEST_QUEUED' and battery_status != 'QUEUED':
        return 'EXECUTION_PHASE_QUEUED_RESERVATION_REQUIRED'
    if event == 'TEST_DISPATCH_PENDING':
        if battery_status != 'DISPATCH_PENDING' or battery.get('dispatch_confirmation') != 'PENDING_EXTERNAL_ACK':
            return 'EXECUTION_PHASE_DISPATCH_PENDING_PROOF_REQUIRED'
    if event == 'TEST_DISPATCHED':
        if (battery_status != 'DISPATCHED'
                or battery.get('dispatch_confirmation') != 'EXTERNAL_RUN_IDENTIFIED'
                or battery.get('run_ref') != next_test.get('run_ref')
                or not RUN_REF.fullmatch(str(next_test.get('run_ref') or ''))):
            return 'EXECUTION_PHASE_DISPATCH_PROOF_REQUIRED'
    if event == 'TEST_RUNNING':
        if (battery_status != 'RUNNING'
                or battery.get('run_ref') != next_test.get('run_ref')
                or not RUN_REF.fullmatch(str(next_test.get('run_ref') or ''))
                or next_test.get('execution_observation') != 'GITHUB_JOB_STEP'
                or (battery.get('started_tests') or {}).get(str(next_test.get('id') or '')) != next_test.get('started_at')
                or timestamp(next_test.get('started_at')) is None):
            return 'RUNNER_STEP_EVIDENCE_REQUIRED'
    return None


def _guard_execution_phase_reconciliation(root: Path, request: dict) -> dict | None:
    test_id = str(request.get('entity_name') or '')
    current = entity(root, test_id)
    changes = request.get('changes')
    expected_version = request.get('expected_version')
    if (isinstance(changes, dict)
            and request.get('writer_role') == 'EXECUTOR'
            and type(expected_version) is int
            and set(changes) == {'execution_phase', 'execution_phase_reconciliation'}
            and changes.get('execution_phase') == EXECUTION_PHASE_CLOSED
            and current.get('execution_phase') == EXECUTION_PHASE_CLOSED
            and current.get('execution_phase_reconciliation') == changes.get('execution_phase_reconciliation')):
        record = changes.get('execution_phase_reconciliation') or {}
        evidence = record.get('evidence') if isinstance(record, dict) else None
        identity = {'test_id': test_id, 'source_entity_version': expected_version, 'evidence': evidence}
        replay_id = 'REQ-EXEC-PHASE-' + digest(identity)[:32]
        if (isinstance(record, dict)
                and record.get('policy') == EXECUTION_PHASE_RECONCILIATION_POLICY
                and record.get('source_entity_version') == expected_version
                and request.get('request_id') == replay_id
                and str(current.get('status') or current.get('state') or '').upper() in TERMINAL):
            return {'request_id': request.get('request_id'), 'accepted': True, 'status': 'NO_OP',
                    'reason': 'EXECUTION_PHASE_RECONCILIATION_ALREADY_APPLIED',
                    'entity_version': current.get('entity_version'), 'readback': 'PASS'}
    valid_shape = (
        request.get('writer_role') == 'EXECUTOR'
        and type(expected_version) is int
        and isinstance(changes, dict)
        and set(changes) == {'execution_phase', 'execution_phase_reconciliation'}
        and (changes or {}).get('execution_phase') == EXECUTION_PHASE_CLOSED
    )
    source_proof = None
    if isinstance(changes, dict):
        reconciliation = changes.get('execution_phase_reconciliation')
        recorded_evidence = reconciliation.get('evidence') if isinstance(reconciliation, dict) else None
        source_proof = recorded_evidence.get('source_submission_proof') if isinstance(recorded_evidence, dict) else None
    proof, reasons = execution_phase_reconciliation_evidence(
        root, current, source_submission_proof=source_proof)
    expected_record = {
        'policy': EXECUTION_PHASE_RECONCILIATION_POLICY,
        'justification': 'MATCHED_TERMINAL_RUNNER_ATTEMPT',
        'source_entity_version': expected_version,
        'evidence': proof,
    }
    if (not valid_shape or expected_version != current.get('entity_version') or proof is None
            or (changes or {}).get('execution_phase_reconciliation') != expected_record):
        details = reasons or ['RECONCILIATION_REQUEST_OR_SOURCE_VERSION_INVALID']
        return {'request_id': request.get('request_id'), 'accepted': False,
                'issue': {'code': 'EXECUTION_PHASE_RECONCILIATION_INVALID',
                          'entity_name': test_id, 'details': details}}
    return None


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


def _readiness_contract_view(test: dict) -> dict:
    """Expose legacy readiness names from the equivalent structured contract.

    This is a read-only view: it copies only values already present in the
    frozen scientific declaration and never writes aliases back to the TEST.
    The hash/reference/timestamp freeze proof is checked separately below.
    """
    view = dict(test)
    input_contract = test.get('input_contract')
    input_contract = input_contract if isinstance(input_contract, dict) else {}
    operator = test.get('environment_operator_contract')
    operator = operator if isinstance(operator, dict) else {}
    estimator = test.get('estimator_contract')
    null_contract = test.get('null_contract')

    if not view.get('question'):
        question = test.get('scientific_question')
        if isinstance(question, str) and question.strip():
            view['question'] = question
    if not view.get('null') and isinstance(null_contract, dict) and null_contract:
        view['null'] = null_contract
    if not view.get('rival'):
        rival = input_contract.get('clustering_de_extension')
        if isinstance(rival, dict) and rival:
            view['rival'] = rival

    if not view.get('method'):
        mechanism = test.get('mechanism')
        if (isinstance(mechanism, str) and mechanism.strip()
                and input_contract and isinstance(estimator, dict) and estimator
                and operator):
            view['method'] = {
                'mechanism': mechanism,
                'input_contract': input_contract,
                'estimator_contract': estimator,
                'environment_operator_contract': operator,
            }

    decision_contract = test.get('decision_contract')
    method = view.get('method')
    if isinstance(decision_contract, (dict, list, str)) and decision_contract and method:
        if isinstance(method, dict):
            method = dict(method)
            method['decision_contract'] = decision_contract
        else:
            method = {'declared_method': method, 'decision_contract': decision_contract}
        view['method'] = method

    if not view.get('dataset_and_selection'):
        observation = operator.get('observational_recovery')
        primary_environment = operator.get('primary_environment')
        sampling = input_contract.get('observational_sampling')
        environment_template = input_contract.get('environment_template')
        if (isinstance(sampling, str) and sampling.strip()
                and isinstance(environment_template, str) and environment_template.strip()
                and isinstance(observation, dict)
                and observation.get('dataset') and observation.get('selection')
                and isinstance(primary_environment, dict)
                and primary_environment.get('product')
                and (primary_environment.get('source') or primary_environment.get('density_file'))):
            view['dataset_and_selection'] = {
                'observational_sampling': sampling,
                'environment_template': environment_template,
                'observational_recovery': observation,
                'primary_environment': primary_environment,
            }
    # A hybrid record can retain a legacy method while getting only its question
    # from the structured declaration. Bind every consumed structured input,
    # not just whichever field supplied the missing alias. Keep legacy hashes
    # unchanged and do not manufacture a missing method from this wrapper.
    aliases = ('question', 'null', 'rival', 'method', 'dataset_and_selection')
    if view.get('method') and any(not test.get(key) and view.get(key) for key in aliases):
        declaration_keys = ('scientific_question', 'mechanism', 'null_contract',
                            'input_contract', 'estimator_contract',
                            'environment_operator_contract', 'decision_contract')
        view['method'] = {
            'declared_method': view['method'],
            'structured_declaration': {key: test[key] for key in declaration_keys if key in test},
        }
    return view


def _verified_legacy_dependency(root: Path, dependency_id: str, dependency: dict) -> bool:
    """Resolve legacy DONE dependencies only from matched scientific RUN/RESULT/EVIDENCE readback.

    The old H0HOM tests keep their verified run chain in scientific_result, not
    executed_at/verdict. A DONE flag or a copied scientific_result alone is not
    execution proof; missing or contradictory primary records fail closed.
    """
    if str(dependency.get('state') or dependency.get('status') or '') != 'DONE':
        return False
    scientific = dependency.get('scientific_result')
    if not isinstance(scientific, dict) or scientific.get('status') != 'VERIFIED':
        return False
    run_id, result_id, evidence_id, artifact_ref = (
        scientific.get(key) for key in ('run_ref', 'result_ref', 'evidence_ref', 'artifact_ref')
    )
    if not (isinstance(run_id, str) and re.fullmatch(r'RUN-[A-Za-z0-9_-]+', run_id)
            and isinstance(result_id, str) and re.fullmatch(r'RESULT-[A-Za-z0-9_-]+', result_id)
            and isinstance(evidence_id, str) and re.fullmatch(r'EVIDENCE-[A-Za-z0-9_-]+', evidence_id)
            and isinstance(artifact_ref, str) and re.fullmatch(
                r'TOWER_V06/runtime/artifacts/[A-Za-z0-9_-]+\.json', artifact_ref)):
        return False
    try:
        run = read(root, 'runtime/runs/' + run_id + '.json')
        result = read(root, 'runtime/results/' + result_id + '.json')
        evidence = read(root, 'runtime/evidence/' + evidence_id + '.json')
        artifact = read(root, artifact_ref.removeprefix('TOWER_V06/'))
    except (OSError, ValueError, TypeError):
        return False
    return (
        run.get('run_id') == run_id and run.get('result_id') == result_id
        and run.get('evidence_id') == evidence_id
        and run.get('work_id') == 'WORK::' + dependency_id
        and run.get('status') == 'VERIFIED' and run.get('readback_status') == 'PASS'
        and result.get('id') == result_id and result.get('run_id') == run_id
        and result.get('evidence_ref') == evidence_id
        and result.get('work_id') == 'WORK::' + dependency_id
        and result.get('status') == 'COMPLETE'
        and isinstance(result.get('scientific_closure'), dict)
        and result['scientific_closure'].get('complete') is True
        and evidence.get('id') == evidence_id and evidence.get('run_id') == run_id
        and evidence.get('source_id') == dependency_id
        and evidence.get('validation_status') == 'PASS'
        and evidence.get('verification_scope') == 'SCIENTIFIC'
        and artifact.get('test_id') == dependency_id
        and artifact.get('status') == 'TERMINAL'
        and result.get('scientific_decision') == scientific.get('decision') == artifact.get('decision')
    )


def readiness(root: Path, test: dict, *, ignore_reservation: bool = False) -> dict:
    from .evolution import prereg_hash
    reasons = []
    if terminal(test):
        reasons.append('TERMINAL_TEST')
    frozen_view = _readiness_contract_view(test)
    structured_fields = ('question', 'null', 'rival', 'method', 'dataset_and_selection')
    uses_structured_fallback = any(
        not test.get(key) and bool(frozen_view.get(key)) for key in structured_fields
    )
    for key in FROZEN[:-1]:
        if not frozen_view.get(key):
            reasons.append('MISSING_' + key.upper())
    has_freeze_proof = bool(test.get('prereg_hash')) and bool(
        test.get('prereg_ref') or timestamp(test.get('frozen_at'))
    )
    if uses_structured_fallback:
        if not has_freeze_proof:
            reasons.extend(('FROZEN_DESIGN_UNVERIFIED', 'STRUCTURED_DESIGN_UNVERIFIED'))
        elif test['prereg_hash'] != prereg_hash(str(test.get('id') or ''), frozen_view):
            # Keep the global legacy hash schema. Structured-only declarations
            # are verified by feeding their normalized fields through that
            # same eight-field schema; a hash over the unnormalized record does
            # not bind those scientific inputs.
            reasons.append('FROZEN_DESIGN_CHANGED')
    elif not has_freeze_proof:
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
    preflight = None
    if valid_name and isinstance(params, dict) and recipe_root.is_dir():
        from .parameter_admission import validate
        preflight = validate(recipe, params, binding.get('inputs') if isinstance(binding, dict) else [], recipe_root)
        if preflight is not None:
            reasons.extend(preflight['reasons'])
    dependencies = test.get('depends_on') or []
    if not isinstance(dependencies, list):
        reasons.append('DEPENDENCIES_INVALID')
    else:
        for dependency_id in dependencies:
            dependency = entity(root, str(dependency_id))
            if not ((dependency.get('executed_at') and dependency.get('verdict'))
                    or _verified_legacy_dependency(root, str(dependency_id), dependency)):
                reasons.append('DEPENDENCY_UNRESOLVED')
                break
    if test.get('blocker'):
        reasons.append('BLOCKER_PRESENT')
    if not ignore_reservation and (str(test.get('id')) in active_tests(root)
                                  or str(test.get('status') or '').upper() in ACTIVE):
        reasons.append('ACTIVE_ATTEMPT')
    result = {'policy': POLICY, 'eligible': not reasons, 'reasons': sorted(set(reasons)),
            'recipe_sha256': recipe_hash, 'input_scope': 'RECORDED_BINDING_NOT_NETWORK_ATTESTATION',
            'recipe_scope': 'SYNTAX_AND_SMOKE_SPEC_PRESENT' if preflight is None else 'VERSIONED_PARAMETER_PREFLIGHT'}
    if preflight is not None:
        result['param_preflight'] = preflight
    return result


def execution_fingerprint(test: dict, recipe_sha: str, param_preflight: dict | None = None) -> str:
    binding = test.get('data_binding') or test.get('input_binding') or {}
    value = {**{key: test.get(key) for key in FROZEN}, 'recipe': test.get('recipe'),
                   'params': test.get('recipe_params'), 'recipe_sha256': recipe_sha,
                   'inputs': binding.get('inputs')}
    if test.get('gene_id'):
        value.update({key: test.get(key) for key in ('gene_id', 'gene_arm', 'gene_plan_sha256')})
    if param_preflight is not None:
        from .parameter_admission import commitment
        value['param_preflight'] = commitment(param_preflight)
    return digest(value)


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


def _guard_terminal_work_reconcile(root: Path, request: dict) -> dict | None:
    """Revalidate the linked TEST at mutation time, not only at proposal time."""
    work_name = str(request.get('entity_name') or '')
    work_path = entity_path(root, 'work', work_name)
    try:
        work = json.loads(work_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        work = {}
    if not isinstance(work, dict):
        work = {}
    changes = request.get('changes')
    evidence = changes.get('completion_evidence') if isinstance(changes, dict) else None
    raw_test_id = work.get('test_id')
    test_id = raw_test_id if isinstance(raw_test_id, str) else ''
    try:
        test = entity(root, test_id) if test_id else {}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        test = {}
    if not isinstance(test, dict):
        test = {}
    state = str(test.get('status') or test.get('state') or '').upper()
    from .semantics import is_private, resolve
    test_private = bool(test.get('private')) or (bool(test_id) and is_private(resolve(test, entity_id=test_id)))
    work_private = bool(work.get('private')) or (bool(work_name) and is_private(resolve(work, entity_id=work_name)))
    test_version = test.get('entity_version')
    work_version = work.get('entity_version')
    versions_valid = (type(test_version) is int and test_version > 0
                      and type(work_version) is int and work_version > 0)
    expected_evidence = {
        'kind': 'TERMINAL_TEST_STATE_OBSERVED',
        'test_id': test_id,
        'test_entity_version': test_version,
        'test_status': state,
        'test_verdict': test.get('verdict'),
    }
    expected_changes = {
        'status': 'DONE',
        'operational_status': 'DONE',
        'closure_reason': 'TEST_ENTITY_ALREADY_TERMINAL',
        'completion_evidence': expected_evidence,
    }
    valid = (
        bool(test_id)
        and isinstance(changes, dict)
        and isinstance(evidence, dict)
        and versions_valid
        # tower_apply supplies expected_version; AgentService calls this guard
        # again only after its own CAS check and intentionally omits it.
        and ('expected_version' not in request or request.get('expected_version') == work_version)
        and work_name == 'WORK::' + test_id
        and work.get('id') == work_name
        and str(work.get('owner_role') or '').upper() == 'EXECUTOR'
        and str(work.get('status') or '').upper() == 'READY'
        and terminal(test)
        and test_id not in active_tests(root)
        and not test_private
        and not work_private
        and evidence == expected_evidence
        and changes == expected_changes
    )
    if valid:
        return None
    return {
        'request_id': request.get('request_id'),
        'accepted': False,
        'issue': {'code': 'WORK_TERMINAL_TEST_EVIDENCE_INVALID', 'entity_name': work_name},
    }


def _guard_terminal_recovery_reconcile(root: Path, request: dict) -> dict | None:
    """Supersede stale dependency-recovery WORKs without changing science."""
    work_name = str(request.get('entity_name') or '')
    try:
        work = json.loads(entity_path(root, 'work', work_name).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        work = {}
    if not isinstance(work, dict):
        work = {}
    changes = request.get('changes')
    evidence = changes.get('completion_evidence') if isinstance(changes, dict) else None
    test_id = work.get('test_id') if isinstance(work.get('test_id'), str) else ''
    try:
        test = entity(root, test_id) if test_id else {}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        test = {}
    if not isinstance(test, dict):
        test = {}

    roadmap_id = str(test.get('roadmap_id') or '')
    roadmap_state = ''
    if roadmap_id:
        roadmap_path = root / 'roadmaps' / f'{roadmap_id}.json'
        try:
            roadmap = json.loads(roadmap_path.read_text(encoding='utf-8')) if roadmap_path.is_file() else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            roadmap = {}
        if isinstance(roadmap, dict):
            roadmap_state = str(roadmap.get('status') or roadmap.get('state') or roadmap.get('semantic_state') or '').upper()

    terminal_roadmap = {'CLOSED', 'DONE', 'ARCHIVED', 'COMPLETE', 'COMPLETED', 'STOPPED', 'REJECTED'}
    reason = ('TEST_ENTITY_ALREADY_TERMINAL' if terminal(test)
              else 'ROADMAP_ALREADY_TERMINAL' if roadmap_state in terminal_roadmap
              else '')
    test_version = test.get('entity_version')
    work_version = work.get('entity_version')
    expected_evidence = {
        'kind': 'RECOVERY_SCOPE_TERMINAL_OBSERVED',
        'test_id': test_id,
        'test_entity_version': test_version,
        'test_status': str(test.get('status') or test.get('state') or '').upper(),
        'roadmap_id': test.get('roadmap_id'),
        'roadmap_state': roadmap_state,
    }
    expected_changes = {
        'status': 'SUPERSEDED',
        'operational_status': 'SUPERSEDED',
        'closure_reason': reason,
        'completion_evidence': expected_evidence,
    }
    from .semantics import is_private, resolve
    test_private = bool(test.get('private')) or (bool(test_id) and is_private(resolve(test, entity_id=test_id)))
    work_private = bool(work.get('private')) or (bool(work_name) and is_private(resolve(work, entity_id=work_name)))
    work_terminal = str(work.get('status') or '').upper() in {
        'DONE', 'VERIFIED', 'REJECTED', 'FAILED', 'SUPERSEDED', 'CANCELLED', 'CANCELED',
        'ARCHIVED', 'COMPLETED', 'CLOSED_VERIFIED', 'DISCARDED', 'WITHDRAWN',
    }
    valid = (
        bool(test_id)
        and reason
        and request.get('writer_role') == 'ADVISOR'
        and isinstance(changes, dict)
        and isinstance(evidence, dict)
        and type(test_version) is int and test_version > 0
        and type(work_version) is int and work_version > 0
        and ('expected_version' not in request or request.get('expected_version') == work_version)
        and work.get('id') == work_name
        and work.get('kind') == 'DEPENDENCY_RECOVERY'
        and (work.get('recovery') or {}).get('policy') == 'EXECUTION_RECOVERY_V1'
        and work.get('test_id') == test_id
        and not work_terminal
        and test_id not in active_tests(root)
        and not test_private
        and not work_private
        and evidence == expected_evidence
        and changes == expected_changes
    )
    if valid:
        return None
    return {
        'request_id': request.get('request_id'),
        'accepted': False,
        'issue': {'code': 'RECOVERY_TERMINAL_SCOPE_EVIDENCE_INVALID', 'entity_name': work_name},
    }


def guard_transition(root: Path, request: dict) -> dict | None:
    if request.get('event_type') == 'TEST_EXECUTION_PHASE_RECONCILED':
        if request.get('entity_kind') == 'test':
            return _guard_execution_phase_reconciliation(root, request)
        return {'request_id': request.get('request_id'), 'accepted': False,
                'issue': {'code': 'EXECUTION_PHASE_RECONCILIATION_TARGET_INVALID'}}
    if (request.get('entity_kind') == 'work'
            and request.get('event_type') == 'WORK_RECONCILED_TERMINAL_TEST'):
        return _guard_terminal_work_reconcile(root, request)
    if (request.get('entity_kind') == 'work'
            and request.get('event_type') == 'DEPENDENCY_RECOVERY_RECONCILED_TERMINAL_SCOPE'):
        return _guard_terminal_recovery_reconcile(root, request)
    if request.get('entity_kind') != 'test':
        return None
    test_id = str(request.get('entity_name') or '')
    current = entity(root, test_id)
    changes = request.get('changes') or {}
    issue = None
    if not isinstance(changes, dict):
        issue = 'INVALID_TEST_CHANGES'
        changes = {}
    if current and {'id', 'entity_id', 'entity_version'}.intersection(changes):
        issue = 'PROTECTED_FIELD_MUTATION'
    elif not current:
        if changes.get('id') not in (None, test_id) or changes.get('entity_id') not in (None, test_id) or 'entity_version' in changes:
            issue = 'IDENTITY_MISMATCH'
    next_test = {**current, **changes, "id": test_id}
    states = {str(next_test[k]).upper() for k in ('status', 'state') if next_test.get(k)}
    next_state = str(next_test.get('status') or next_test.get('state') or '').upper()
    current_phase = str(current.get('execution_phase') or '').upper()
    status_enters_terminal = any(
        key in changes and str(changes.get(key) or '').upper() in TERMINAL
        and str(current.get(key) or '').upper() != str(changes.get(key) or '').upper()
        for key in ('status', 'state'))
    status_enters_active = any(
        key in changes and str(changes.get(key) or '').upper() in ACTIVE
        and str(current.get(key) or '').upper() != str(changes.get(key) or '').upper()
        for key in ('status', 'state'))
    status_leaves_active = any(
        key in changes and str(current.get(key) or '').upper() in ACTIVE
        and str(current.get(key) or '').upper() != str(changes.get(key) or '').upper()
        for key in ('status', 'state'))
    result_fields = ('verdict', 'scientific_verdict', 'executed_at', 'result',
                     'statistics', 'decision', 'result_summary', 'reproducibility')
    result_payload_changed = any(
        key in changes and changes.get(key) != current.get(key) for key in result_fields)
    terminal_result_payload = status_enters_terminal or result_payload_changed
    # A stale DRAFT may be archived by maintenance, but that lifecycle change
    # is not a scientific result. Keep the exception narrower than the general
    # terminal-result path and bind it to the existing entity version.
    stale_draft_archive = False
    if current and request.get('event_type') == 'TEST_ARCHIVED':
        current_states = {str(current.get(key) or '').upper()
                          for key in ('status', 'state') if current.get(key) not in (None, '')}
        expected_version = request.get('expected_version')
        entity_version = current.get('entity_version')
        archived_at = timestamp(changes.get('archived_at'))
        created_at = timestamp(current.get('created_at') or current.get('frozen_at'))
        try:
            from .evolution import STALE_DRAFT_DAYS
        except ImportError:
            STALE_DRAFT_DAYS = 21
        try:
            has_active_reservation = test_id in active_tests(root)
        except (OSError, ValueError, TypeError):
            has_active_reservation = True
        stale_draft_archive = bool(
            current_states == {'DRAFT'}
            and request.get('writer_role') == 'ADVISOR'
            and type(expected_version) is int and type(entity_version) is int
            and expected_version == entity_version
            and set(changes) == {'status', 'state', 'archive_reason', 'archived_at'}
            and str(changes.get('status') or '').upper() == 'ARCHIVED'
            and str(changes.get('state') or '').upper() == 'ARCHIVED'
            and changes.get('archive_reason') == 'stale_draft'
            and archived_at is not None and created_at is not None
            and archived_at - created_at >= timedelta(days=STALE_DRAFT_DAYS)
            and archived_at <= datetime.now(timezone.utc) + timedelta(minutes=5)
            and not has_active_reservation
            and not any(str(current.get(key) or '').upper() in ACTIVE
                        for key in ('status', 'state', 'execution_phase'))
            and not any(current.get(key) not in (None, '', [], {})
                        for key in ('verdict', 'scientific_verdict', 'executed_at', 'result',
                                    'statistics', 'decision', 'result_summary',
                                    'reproducibility', 'battery_id', 'attempt_id', 'run_ref'))
        )
    phase_changed = ('execution_phase' in changes
                     and changes.get('execution_phase') != current.get('execution_phase'))
    if phase_changed:
        phase_issue = _phase_transition_proof(
            root, request, current, next_test, current_phase, next_state)
        if phase_issue:
            issue = phase_issue
    elif status_enters_active or (status_leaves_active and not terminal_result_payload):
        # Lifecycle status and execution phase move together only through the
        # corresponding proof-bearing event; caller-supplied runner fields do
        # not authorize entering or leaving an active status by themselves.
        issue = 'EXECUTION_PHASE_TRANSITION_REQUIRED'
    elif terminal_result_payload:
        # Imported results remain supported for genuinely unattempted records.
        # An active reservation/attempt cannot be bypassed by choosing another
        # event or omitting execution_phase from a terminal-looking mutation.
        event = str(request.get('event_type') or '')
        has_result_payload = any(
            changes.get(key) not in (None, '', [], {})
            for key in ('verdict', 'scientific_verdict', 'decision', 'result_summary',
                        'statistics', 'result', 'reproducibility'))
        if not stale_draft_archive and (event != 'TEST_RESULT_RECORDED' or not has_result_payload):
            issue = 'TERMINAL_STATUS_REQUIRES_RESULT_EVENT'
        try:
            active_attempt = test_id in active_tests(root)
        except (OSError, ValueError, TypeError):
            active_attempt = True
        current_status_active = any(
            str(current.get(key) or '').upper() in ACTIVE for key in ('status', 'state'))
        if not stale_draft_archive and (current_phase in ACTIVE or current_status_active or active_attempt):
            issue = 'EXECUTION_PHASE_RESULT_PROOF_REQUIRED'
    if (current and terminal(current) and 'execution_phase' in changes
            and changes['execution_phase'] != current.get('execution_phase')):
        issue = 'TERMINAL_ATTEMPT_PHASE_IMMUTABLE'
    scientific = any(record.get('mandate_id') or str(record.get('domain') or '').upper() in {'SCIENCE', 'COSMOLOGY', 'COSMOLOGIA', 'OBSERVATIONAL_COSMOLOGY'}
                     for record in (current, next_test))
    if not scientific:
        return {'request_id': request.get('request_id'), 'accepted': False, 'issue': {'code': issue, 'entity_name': test_id}} if issue else None
    if issue is None and (current.get('battery_id') or current.get('attempt_id') or next_test.get('mandate_id')) and any(
            key in changes and changes[key] != current.get(key) for key in ('started_at', 'execution_observation', 'run_ref')):
        if request.get('_runner_observation_authority') is not RUNNER_BATTERY_STATUS_TOKEN:
            issue = 'RUNNER_OBSERVATION_METADATA_WRITER_ONLY'
        elif current.get('started_at') and changes.get('started_at', current['started_at']) != current['started_at'] and not (
                request.get('event_type') == 'TEST_QUEUED' and next_test.get('attempt_id') != current.get('attempt_id')
                and changes.get('started_at') is None and changes.get('execution_observation') is None
                and changes.get('run_ref') is None and _reservation_attempt(root, next_test)[0] is not None):
            issue = 'RUNNER_START_COMMITMENT_IMMUTABLE'
    if any(key in changes and changes[key] != current.get(key)
           for key in ('reviews', 'contests', 'mechanical_contest_verdict', 'review_validation')):
        from .autonomy import WRITER_AUTHORITY
        if request.get('_scientific_review_authority') is not WRITER_AUTHORITY:
            issue = 'CANONICAL_REVIEW_LEDGER_WRITER_ONLY'
    if len(states) > 1 and any(k in changes for k in ('status', 'state')):
        issue = 'INCONSISTENT_TEST_STATES'
    result_fields = ('verdict', 'scientific_verdict', 'executed_at', 'result', 'statistics', 'decision', 'result_summary', 'reproducibility')
    if current and terminal(current):
        if next_state in ACTIVE | {'READY', 'DRAFT'} and next_state != str(current.get('status') or current.get('state') or '').upper():
            issue = 'TERMINAL_TEST_CANNOT_REOPEN'
        if any(k in changes and changes[k] != current.get(k) for k in result_fields):
            issue = 'TERMINAL_RESULT_IMMUTABLE'
    if current.get('prereg_hash') and any(k in changes and changes[k] != current.get(k) for k in (*FROZEN, 'prereg_hash', 'independence', 'independence_fingerprint', 'gene_id', 'gene_arm', 'gene_plan_sha256')):
        issue = 'FROZEN_DEFINITION_IMMUTABLE'
    if current.get('mandate_id') and any(k in changes and changes[k] != current.get(k)
                                       for k in ('mandate_id', 'question_id', 'domain', 'public_data_only', 'visibility')):
        issue = 'AUTONOMY_SCOPE_IMMUTABLE'
    if str(current.get('id')) in active_tests(root) and any(k in changes and changes[k] != current.get(k) for k in ('recipe', 'recipe_params', 'data_binding')):
        issue = 'ACTIVE_EXECUTION_BINDING_IMMUTABLE'
    if next_state == 'READY' and any(k in changes for k in ('status', 'state', 'recipe', 'recipe_params', 'data_binding')):
        check = readiness(root, next_test)
        if not check['eligible'] and issue is None:
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
    runner_status_authorized = request.get('_runner_battery_status_token') is RUNNER_BATTERY_STATUS_TOKEN
    runner_fields = ('status', 'dispatch_requested_at', 'dispatch_confirmation', 'dispatched_at', 'started_tests',
                     'run_ref', 'completed_at', 'done_at', 'execution_observation',
                     'conclusion', 'ok', 'failed', 'phase_failure_receipts')
    phase_order = {'QUEUED': 0, 'DISPATCH_PENDING': 1, 'DISPATCHED': 2, 'RUNNING': 3, 'DONE': 4}
    seen, attempts, fingerprints = set(), set(), set()
    for battery in proposed:
        if not isinstance(battery, dict) or not battery.get('id') or battery['id'] in seen:
            problem = 'BATTERY_ID_INVALID_OR_DUPLICATE'; break
        seen.add(battery['id'])
        old = existing.get(battery['id'])
        if old and (old.get('mandate_id') or battery.get('mandate_id')) and any(
                old.get(key) != battery.get(key) for key in
                ('mandate_id', 'mandate_revision', 'parallelism', 'created_at', 'source_revision', 'package_json', 'package_sha256')):
            problem = 'FROZEN_SCOPED_BATTERY_METADATA_IMMUTABLE'; break
        if old and old.get('tests') != battery.get('tests'):
            problem = 'FROZEN_BATTERY_SPEC_IMMUTABLE'; break
        if old and any(old.get(key) != battery.get(key) for key in runner_fields):
            old_status = str(old.get('status') or '').upper()
            new_status = str(battery.get('status') or '').upper()
            if old_status == 'DONE' and old.get('phase_failure_receipts') != battery.get('phase_failure_receipts'):
                problem = 'BATTERY_FAILURE_RECEIPTS_IMMUTABLE'; break
            if not runner_status_authorized:
                problem = 'BATTERY_STATUS_WRITER_PROOF_REQUIRED'; break
            if (old_status not in phase_order or new_status not in phase_order
                    or phase_order[new_status] < phase_order[old_status]):
                problem = 'BATTERY_STATUS_TRANSITION_INVALID'; break
        if not old and battery.get('status') != 'QUEUED':
            problem = 'NEW_BATTERY_MUST_BE_QUEUED'; break
        specs = battery.get('tests')
        if not isinstance(specs, list) or not specs or not all(isinstance(t, dict) for t in specs):
            problem = 'BATTERY_TESTS_INVALID'; break
        if not old and (battery.get('mandate_id') or any(entity(root, str(spec.get('test_id') or '')).get('mandate_id') for spec in specs)):
            from .autonomy import WRITER_AUTHORITY
            if request.get('_autonomy_authority') is not WRITER_AUTHORITY:
                problem = 'AUTONOMY_RESERVATION_REQUIRES_WRITER_CONVERTER'; break
        newly_done = str(battery.get('status') or '').upper() == 'DONE' and (
            old is None or str(old.get('status') or '').upper() != 'DONE')
        if newly_done:
            failure_receipts = battery.get('phase_failure_receipts', [])
            failed_count = battery.get('failed', 0)
            if (not runner_status_authorized or type(failed_count) is not int or failed_count < 0
                    or not isinstance(failure_receipts, list)
                    or len(failure_receipts) != failed_count):
                problem = 'BATTERY_FAILURE_RECEIPTS_REQUIRED'; break
            receipt_commitment = request.get('_runner_phase_failure_receipt_sha256')
            if failure_receipts and receipt_commitment != 'sha256:' + digest(failure_receipts):
                problem = 'BATTERY_FAILURE_RECEIPT_COMMITMENT_INVALID'; break
            if not failure_receipts and receipt_commitment is not None:
                problem = 'BATTERY_FAILURE_RECEIPT_COMMITMENT_INVALID'; break
            spec_by_id = {str(spec.get('test_id') or ''): spec for spec in specs}
            receipt_ids = set()
            for receipt in failure_receipts:
                if not isinstance(receipt, dict):
                    problem = 'BATTERY_FAILURE_RECEIPT_INVALID'; break
                test_id = str(receipt.get('test_id') or '')
                spec = spec_by_id.get(test_id)
                if not test_id or spec is None or test_id in receipt_ids:
                    problem = 'BATTERY_FAILURE_RECEIPT_MEMBERSHIP_INVALID'; break
                receipt_ids.add(test_id)
                if (receipt.get('receipt_kind') not in {'RUNNER_FAILURE_ENTRY', 'RUNNER_RESULTS_MISSING'}
                        or receipt.get('battery_id') != battery.get('id')
                        or receipt.get('spec_sha256') != 'sha256:' + digest(spec)
                        or not re.fullmatch(r'sha256:[0-9a-f]{64}', str(receipt.get('result_sha256') or ''))
                        or receipt.get('attempt_id') != spec.get('attempt_id')
                        or receipt.get('recipe_sha256') != spec.get('recipe_sha256')
                        or receipt.get('prereg_hash') != spec.get('prereg_hash')
                        or receipt.get('recipe') != spec.get('recipe')
                        or receipt.get('params_sha256') != 'sha256:' + digest(spec.get('params'))
                        or receipt.get('run_ref') != battery.get('run_ref')
                        or receipt.get('completed_at') != battery.get('completed_at')
                        or receipt.get('done_at') != battery.get('done_at')
                        or receipt.get('event_type') not in {'TEST_RUNTIME_FAILURE', 'TEST_INPUT_UNAVAILABLE'}
                        or receipt.get('phase_target') not in {'READY', 'BLOCKED_INPUT'}
                        or (receipt.get('event_type') == 'TEST_INPUT_UNAVAILABLE'
                            and (receipt.get('failure_class') != 'INPUT_UNAVAILABLE'
                                 or receipt.get('phase_target') != 'BLOCKED_INPUT'))
                        or (receipt.get('event_type') == 'TEST_RUNTIME_FAILURE'
                            and receipt.get('failure_class') not in {'TRANSIENT', 'RECIPE_BUG', 'TEST'})):
                    problem = 'BATTERY_FAILURE_RECEIPT_BINDING_INVALID'; break
            if problem:
                break
        elif battery.get('phase_failure_receipts'):
            # A failure-phase receipt is meaningful only as part of the exact
            # verified transition that first closes this runner attempt.
            if not old or old.get('phase_failure_receipts') != battery.get('phase_failure_receipts'):
                problem = 'BATTERY_FAILURE_RECEIPT_TRANSITION_INVALID'; break
        for spec in specs:
            tid = str(spec.get('test_id') or '')
            if not old:
                test = entity(root, tid)
                check = readiness(root, test)
                if not check['eligible'] or test.get('status') != 'READY' or spec.get('recipe') != test.get('recipe') or spec.get('params') != test.get('recipe_params') or spec.get('recipe_sha256') != check['recipe_sha256']:
                    problem = 'BATTERY_ADMISSION_FAILED'; break
                if spec.get('param_preflight') != check.get('param_preflight'):
                    problem = 'PARAM_PREFLIGHT_RESERVATION_MISMATCH'; break
                if not spec.get('attempt_id') or spec.get('execution_fingerprint') != execution_fingerprint(test, check['recipe_sha256'], check.get('param_preflight')):
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
    if any(b.get('mandate_id') and bid not in seen for bid, b in existing.items()):
        problem = 'SCOPED_RESERVATION_HISTORY_CANNOT_BE_DROPPED'
    if problem:
        return {'request_id':request.get('request_id'), 'accepted':False, 'issue':{'code':problem}}
    return None
