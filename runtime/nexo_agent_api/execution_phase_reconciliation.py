"""Read-only dry-run planning for legacy terminal attempts left in RUNNING.

The planner emits ordinary, versioned Writer mutation requests only when the
test, frozen attempt, runner observation, result, and completed battery agree.
It never writes the Tower. Callers must keep the generated report private and
submit any approved request through the canonical Writer.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from . import scientific_integrity as integrity
from .live_tower import materialize_live_tower, read_live_tower_bytes, verify_live_tower

POLICY = integrity.EXECUTION_PHASE_RECONCILIATION_POLICY
EVENT_TYPE = 'TEST_EXECUTION_PHASE_RECONCILED'


def _tests(root: Path) -> tuple[list[dict[str, Any]], int]:
    directory = root / 'entities' / 'test'
    values: list[dict[str, Any]] = []
    unreadable = 0
    for path in sorted(directory.glob('*.json')) if directory.is_dir() else []:
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            unreadable += 1
            continue
        if isinstance(value, dict):
            values.append(value)
        else:
            unreadable += 1
    return values, unreadable


def _request(test: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    test_id = str(test['id'])
    version = test['entity_version']
    record = {
        'policy': POLICY,
        'justification': 'MATCHED_TERMINAL_RUNNER_ATTEMPT',
        'source_entity_version': version,
        'evidence': evidence,
    }
    identity = {'test_id': test_id, 'source_entity_version': version, 'evidence': evidence}
    return {
        'request_id': 'REQ-EXEC-PHASE-' + integrity.digest(identity)[:32],
        'entity_kind': 'test',
        'entity_name': test_id,
        'expected_version': version,
        'writer_role': 'EXECUTOR',
        'event_type': EVENT_TYPE,
        'changes': {
            'execution_phase': integrity.EXECUTION_PHASE_CLOSED,
            'execution_phase_reconciliation': record,
        },
    }


def build_reconciliation_plan(
        root: str | Path, *, source_revision: str | None = None,
        submission_proofs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a private dry-run report from an already materialized Tower root."""
    root = Path(root)
    tests, unreadable = _tests(root)
    requests: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    protected = 0
    terminal_running = 0

    for test in tests:
        if str(test.get('execution_phase') or '').upper() != 'RUNNING' or not integrity.terminal(test):
            continue
        terminal_running += 1
        battery_id = str(test.get('battery_id') or '')
        source_proof = (submission_proofs or {}).get(battery_id)
        evidence, reasons = integrity.execution_phase_reconciliation_evidence(
            root, test, source_submission_proof=source_proof)
        test_id = str(test.get('id') or '')
        if evidence is not None:
            requests.append(_request(test, evidence))
        else:
            if 'PROTECTED_CAMB_MCMC_SCOPE' in reasons:
                protected += 1
            conflicts.append({
                'entity_name': test_id,
                'source_entity_version': test.get('entity_version'),
                'reasons': reasons,
            })

    requests.sort(key=lambda request: request['entity_name'])
    conflicts.sort(key=lambda item: item['entity_name'])
    return {
        'policy': POLICY,
        'mode': 'DRY_RUN',
        'source_revision': source_revision,
        'summary': {
            'tests_scanned': len(tests),
            'unreadable_tests': unreadable,
            'terminal_running': terminal_running,
            'proposal_count': len(requests),
            'conflict_count': len(conflicts),
            'protected_camb_mcmc_count': protected,
        },
        'requests': requests,
        'conflicts': conflicts,
    }


def plan_bundle(bundle_path: str | Path, *,
                submission_proofs: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Read a canonical Tower bundle and return a plan without modifying it."""
    raw = Path(bundle_path).read_bytes()
    bundle = read_live_tower_bytes(raw)
    revision = verify_live_tower(bundle)
    with tempfile.TemporaryDirectory(prefix='nexo-execution-phase-plan-') as temporary:
        root, _ = materialize_live_tower(raw, Path(temporary) / 'TOWER_V06')
        return build_reconciliation_plan(root, source_revision=revision,
                                         submission_proofs=submission_proofs)


def _load_submission_proofs(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if (not isinstance(value, dict) or value.get('contract') != 'EXECUTION_PHASE_SOURCE_PROOFS_V1'
            or not isinstance(value.get('proofs'), dict)):
        raise ValueError('EXECUTION_PHASE_SOURCE_PROOF_LEDGER_INVALID')
    return {str(key): proof for key, proof in value['proofs'].items() if isinstance(proof, dict)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tower_bundle', help='Canonical local Tower bundle; it is read only.')
    parser.add_argument('--output', required=True, help='Private path for the detailed dry-run report.')
    parser.add_argument('--submission-proofs', help='Private exact-source proof ledger; Git references are revalidated.')
    args = parser.parse_args(argv)
    source = Path(args.tower_bundle)
    output = Path(args.output)
    if source.resolve() == output.resolve():
        parser.error('--output must not overwrite the Tower bundle')
    try:
        submission_proofs = _load_submission_proofs(args.submission_proofs)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(f'cannot load submission proof ledger: {type(exc).__name__}')
    report = plan_bundle(source, submission_proofs=submission_proofs)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)
    print(json.dumps({'mode': report['mode'], 'source_revision': report['source_revision'],
                      'summary': report['summary'], 'report_written': str(output)},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
