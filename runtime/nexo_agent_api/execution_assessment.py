"""Append-only operational assessments of explicitly approved runner observations.

The collector fetches the pinned artifact; the Writer binds that evidence to the
unchanged canonical observation. A raw verdict remains an auditable raw verdict.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import scientific_integrity as integrity

CONTRACT = 'EXECUTION_OBSERVATION_ASSESSMENT_V1'
OPERATION = 'EXECUTION_OBSERVATION_ASSESSMENT'
WRITE_TOKEN = object()  # cannot be supplied by a serialized mutation request
OBSERVATION_FIELDS = ('verdict', 'decision', 'statistics', 'result_summary', 'executed_at', 'reproducibility')
SOURCE_FIELDS = ('artifact_id', 'run_ref', 'archive_sha256', 'member_sha256')
APPROVAL_FIELDS = {'test_id', 'battery_id', 'run_ref', 'artifact_id', 'archive_sha256', 'member_sha256',
                   'attempt_id', 'recipe_sha256', 'expected_observation_hash', 'expected_version'}
CLASSIFICATION = 'OPERATIONAL_FAILURE_RECORDED_AS_RESULT'


class AssessmentError(ValueError):
    pass


def observation_hash(test: dict) -> str:
    return integrity.digest({key: test.get(key) for key in OBSERVATION_FIELDS})


def _validate_evidence(test: dict, approved: dict, source: dict) -> None:
    if (not isinstance(approved, dict) or set(approved) != APPROVAL_FIELDS or not isinstance(source, dict)
            or set(source) != set(SOURCE_FIELDS) | {'member_name', 'member_utf8'}):
        raise AssessmentError('ASSESSMENT_EVIDENCE_INVALID')
    if approved.get('test_id') != test.get('id'):
        raise AssessmentError('ASSESSMENT_FOREIGN_TEST')
    if type(approved.get('expected_version')) is not int or approved['expected_version'] < 1:
        raise AssessmentError('ASSESSMENT_VERSION_REQUIRED')
    if (type(approved.get('artifact_id')) is not int or approved['artifact_id'] <= 0
            or not integrity.RUN_REF.fullmatch(str(approved.get('run_ref') or ''))):
        raise AssessmentError('ASSESSMENT_SOURCE_INVALID')
    for key in ('archive_sha256', 'member_sha256', 'recipe_sha256', 'expected_observation_hash'):
        if not re.fullmatch('[0-9a-f]{64}', str(approved.get(key) or '')):
            raise AssessmentError('ASSESSMENT_SOURCE_INVALID')
    if any(source.get(key) != approved[key] for key in SOURCE_FIELDS):
        raise AssessmentError('ASSESSMENT_ARTIFACT_MISMATCH')
    raw = source.get('member_utf8')
    if source.get('member_name') != 'battery-results.json' or not isinstance(raw, str) or len(raw.encode('utf-8')) > 1_000_000:
        raise AssessmentError('ASSESSMENT_MEMBER_INVALID')
    if hashlib.sha256(raw.encode('utf-8')).hexdigest() != approved['member_sha256']:
        raise AssessmentError('ASSESSMENT_MEMBER_HASH_MISMATCH')
    try:
        entries = json.loads(raw)['results']
        rows = [row for row in entries if isinstance(row, dict) and row.get('test_id') == test['id']]
    except (ValueError, KeyError, TypeError) as exc:
        raise AssessmentError('ASSESSMENT_MEMBER_INVALID') from exc
    if not isinstance(entries, list) or len(rows) != 1:
        raise AssessmentError('ASSESSMENT_RECEIPT_MEMBERSHIP_MISMATCH')
    row = rows[0]
    result = row.get('result') or {}
    reproducibility = test.get('reproducibility') or {}
    if (not isinstance(result, dict) or row.get('ok') is not True
            or result.get('decision') != 'INPUT_OR_FIT_UNAVAILABLE'
            or result.get('verdict') != 'INCONCLUSIVE'
            or test.get('decision') != result['decision'] or test.get('verdict') != result['verdict']):
        raise AssessmentError('ASSESSMENT_NOT_TECHNICAL_FAILURE')
    # These approved historical failures have only consumed-source metadata,
    # not a scientific estimate or robustness statistic.
    statistics = result.get('statistics') or {}
    if not isinstance(statistics, dict) or set(statistics) - {'data_sources'}:
        raise AssessmentError('ASSESSMENT_SCIENTIFIC_STATISTICS_PRESENT')
    observed = {'statistics': test.get('statistics'), 'summary': test.get('result_summary'), 'at': test.get('executed_at')}
    recorded = {'statistics': result.get('statistics'), 'summary': result.get('summary'), 'at': row.get('executed_at')}
    try:
        same_observation = integrity.digest(observed) == integrity.digest(recorded)
    except (ValueError, TypeError) as exc:
        raise AssessmentError('ASSESSMENT_OBSERVATION_INVALID') from exc
    if not same_observation:
        raise AssessmentError('ASSESSMENT_OBSERVATION_MISMATCH')
    if (not isinstance(reproducibility, dict)
            or any(reproducibility.get(key) != approved[key] for key in ('battery_id', 'run_ref', 'attempt_id', 'recipe_sha256'))
            or any(row.get(key) != approved[key] for key in ('attempt_id', 'recipe_sha256'))
            or not approved.get('attempt_id')):
        raise AssessmentError('ASSESSMENT_FOREIGN_ATTEMPT')
    try:
        matches = observation_hash(test) == approved['expected_observation_hash']
    except (ValueError, TypeError) as exc:
        raise AssessmentError('ASSESSMENT_OBSERVATION_INVALID') from exc
    if not matches:
        raise AssessmentError('ASSESSMENT_OBSERVATION_CHANGED')


def public_assessment(test: dict) -> dict | None:
    assessment = test.get('execution_assessment')
    if not isinstance(assessment, dict):
        return None
    if (assessment.get('contract') != CONTRACT or assessment.get('source') != 'WRITER_VERIFIED_RUNNER_RECEIPT'
            or assessment.get('classification') != CLASSIFICATION
            or assessment.get('scientific_result_eligible') is not False
            or assessment.get('reason_code') != 'INPUT_OR_FIT_UNAVAILABLE'
            or integrity.timestamp(assessment.get('recorded_at')) is None):
        return None
    approved, source = assessment.get('approved'), assessment.get('evidence')
    try:
        _validate_evidence(test, approved, source)
        if assessment.get('evidence_fingerprint') != integrity.digest({'approved': approved, 'source': source}):
            return None
    except (AssessmentError, ValueError, TypeError, KeyError):
        return None
    return {key: assessment[key] for key in ('contract', 'classification', 'scientific_result_eligible', 'reason_code', 'recorded_at')}


def has_valid_operational_exclusion(test: dict) -> bool:
    """Unknown labels cannot exclude a record or assert scientific validity."""
    return public_assessment(test) is not None


def apply_assessment(root: Path, body: dict) -> dict:
    from .service import AgentService
    if not isinstance(body, dict):
        raise AssessmentError('ASSESSMENT_ENVELOPE_INVALID')
    approved, source = body.get('approved'), body.get('source')
    if not isinstance(approved, dict):
        raise AssessmentError('ASSESSMENT_EVIDENCE_INVALID')
    current = integrity.entity(root, str(approved.get('test_id') or ''))
    _validate_evidence(current, approved, source)
    fingerprint = integrity.digest({'approved': approved, 'source': source})
    previous = current.get('execution_assessment')
    if 'execution_assessment' in current:
        if public_assessment(current) is not None and previous.get('evidence_fingerprint') == fingerprint:
            return {'accepted': True, 'status': 'NO_OP', 'reason': 'ASSESSMENT_ALREADY_RECORDED'}
        raise AssessmentError('EXECUTION_ASSESSMENT_IMMUTABLE')
    assessment = {'contract': CONTRACT, 'source': 'WRITER_VERIFIED_RUNNER_RECEIPT',
                  'classification': CLASSIFICATION, 'scientific_result_eligible': False,
                  'reason_code': 'INPUT_OR_FIT_UNAVAILABLE',
                  'recorded_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                  'approved': approved, 'evidence': source, 'evidence_fingerprint': fingerprint}
    return AgentService(root).mutate('test', current['id'], expected_version=approved['expected_version'],
        changes={'execution_assessment': assessment}, writer_role='EXECUTOR',
        event_type='EXECUTION_OBSERVATION_ASSESSED', _execution_assessment_token=WRITE_TOKEN)
