#!/usr/bin/env python3
"""Paired private Tower receipt/GC benchmark; output aggregates only."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.nexo_agent_api import operation_receipts as receipts, tower_gc as gc
from runtime.nexo_agent_api.live_tower import materialize_live_tower


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tower')
    parser.add_argument('report')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--queries', type=int, default=24)
    args = parser.parse_args()
    if args.repeats < 1 or args.queries < 1:
        parser.error('positive repeats/queries required')
    raw = Path(args.tower).read_bytes()
    original = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix='nexo-gc-benchmark-') as work:
        root, metadata = materialize_live_tower(raw, Path(work) / 'TOWER_V06')
        rows = receipts.load_receipts(root)
        chosen = rows[-args.queries:]
        timings = {'before_ms': [], 'after_ms': []}
        scan_counts = []
        for _ in range(args.repeats):
            started = time.perf_counter()
            baseline = [receipts.latest_receipt(root, intent=row['intent_id'], payload_sha256=row['payload_sha256'], effect=row['effect_id']) for row in chosen]
            timings['before_ms'].append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            with receipts.receipt_transaction(root) as index:
                actual = [receipts.latest_receipt(root, intent=row['intent_id'], payload_sha256=row['payload_sha256'], effect=row['effect_id']) for row in chosen]
                scan_counts.append(index.full_scans)
            timings['after_ms'].append((time.perf_counter() - started) * 1000)
            if actual != baseline:
                raise RuntimeError('RECEIPT_DECISIONS_DIVERGED')
        started = time.perf_counter()
        plan = gc.plan_gc(raw)
        dry_run_ms = (time.perf_counter() - started) * 1000
        backup, backup_receipt = gc.prepare_backup(raw)
        started = time.perf_counter()
        if gc.restore_backup(backup, backup_receipt) != raw:
            raise RuntimeError('BACKUP_RESTORE_DIVERGED')
        restore_ms = (time.perf_counter() - started) * 1000
    if hashlib.sha256(Path(args.tower).read_bytes()).hexdigest() != original:
        raise RuntimeError('SOURCE_CHANGED')
    result = {'mode': 'ISOLATED_READ_ONLY', 'source_unchanged': True,
              'tower_revision': metadata['tower_revision'], 'receipts': len(rows),
              'queries_per_transaction': len(chosen), 'repeats': args.repeats,
              'cache_condition': 'same local materialization; warm filesystem; cold transaction index',
              'baseline_full_scans_per_transaction': len(chosen), 'indexed_full_scans_per_transaction': scan_counts,
              'receipt_decision_equality': True, **timings,
              'before_median_ms': statistics.median(timings['before_ms']),
              'after_median_ms': statistics.median(timings['after_ms']),
              'dry_run_ms': dry_run_ms, 'dry_run': plan['summary'],
              'raw_tower_bytes': len(raw), 'exact_backup_bytes': len(backup),
              'backup_restore_success': True, 'backup_restore_ms': restore_ms,
              'active_bytes_saved': 0, 'total_bytes_saved': 0,
              'limits': ['receipt lookup workload, not a complete apply_to_tower throughput benchmark',
                         'backup compression is not active Tower compaction or net storage savings',
                         'consumer coverage and independent code review still required before activation']}
    target=Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
