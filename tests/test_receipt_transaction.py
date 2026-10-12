"""A transaction must read once, preserve decisions and forget rollback writes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import operation_receipts as receipts
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.test_public_projection import _tower
from runtime.nexo_agent_api.live_tower import build_live_tower_payload


class ReceiptTransactionTests(unittest.TestCase):
    def row(self, i=0, outcome='APPLIED', intent='same', effect='effect', payload=1):
        return receipts.build_receipt(intent=intent, payload_sha256=receipts.payload_hash(payload), effect=effect,
            outcome=outcome, source_revision='before', result_revision='after',
            occurred_at=f'2026-10-12T00:00:{i:02d}Z', observed_at='2026-10-12T00:00:00Z',
            retry_condition={'kind':'SOURCE_REVISION_CHANGED','source_revision':'before'} if outcome=='DEFERRED_DEPENDENCY' else None)

    def test_decisions_match_uncached_legacy_and_sorted_ties(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            for i, state in enumerate(['APPLIED', 'REJECTED_TERMINAL', 'DEFERRED_DEPENDENCY', 'APPLIED']):
                row = self.row(i, state, payload=i%2)
                receipts.persist_receipt(root, row)
            legacy = root / receipts.LEGACY_RECEIPT_ROOT
            legacy.mkdir(parents=True)
            (legacy / 'legacy.json').write_text(json.dumps(self.row(5, 'REJECTED_TERMINAL', 'old', payload=7)))
            def queries():
                return [receipts.load_receipts(root), receipts.latest_receipt(root, intent='same', payload_sha256=receipts.payload_hash(1), effect='effect'),
                    receipts.envelope_receipts(root, intent='same'),
                    receipts.terminal_payload_conflict(root, intent='same', payload_sha256=receipts.payload_hash(9), effect='effect', supersedes=None),
                    receipts.terminal_payload_conflict(root, intent='new', payload_sha256=receipts.payload_hash(9), effect='effect', supersedes=self.row(5,'REJECTED_TERMINAL','old',payload=7)['receipt_id'])]
            baseline = queries()
            with patch.object(receipts, '_load_receipts_uncached', wraps=receipts._load_receipts_uncached) as scans:
                with receipts.receipt_transaction(root) as index:
                    self.assertEqual(queries(), baseline)
                    self.assertEqual(queries(), baseline)
                    self.assertEqual(index.full_scans, 1)
                self.assertEqual(scans.call_count, 1)

    def test_persistence_immediate_idempotent_and_rollback_without_rescan(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work)
            receipts.persist_receipt(root, self.row(2))
            with receipts.receipt_transaction(root) as index:
                checkpoint=receipts.receipt_savepoint(root)
                added=self.row(1, 'REJECTED_TERMINAL', payload=9)
                path=receipts.persist_receipt(root, added)
                receipts.persist_receipt(root, added)
                self.assertEqual(len(receipts.load_receipts(root)), 2)
                self.assertEqual(receipts.latest_receipt(root,intent='same',payload_sha256=receipts.payload_hash(9),effect='effect'),added)
                path.unlink()
                receipts.restore_receipt_savepoint(root, checkpoint)
                self.assertIsNone(receipts.latest_receipt(root,intent='same',payload_sha256=receipts.payload_hash(9),effect='effect'))
                self.assertEqual(len(receipts.load_receipts(root)),1)
                self.assertEqual(index.full_scans,1)
            self.assertEqual(receipts.load_receipts(root),[self.row(2)])

    def test_failed_transaction_and_new_revision_do_not_reuse_memory(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work)
            path=receipts.persist_receipt(root,self.row())
            with self.assertRaises(RuntimeError),receipts.receipt_transaction(root):
                receipts.load_receipts(root)
                raise RuntimeError('CAS failed')
            path.unlink()
            receipts.persist_receipt(root,self.row(3,payload=5))
            with receipts.receipt_transaction(root) as index:
                self.assertEqual(receipts.load_receipts(root),[self.row(3,payload=5)])
                self.assertEqual(index.full_scans,1)

    def test_unreadable_ledger_never_becomes_cache_miss(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work)
            directory=root/receipts.RECEIPT_ROOT
            directory.mkdir(parents=True)
            (directory/'invalid.json').write_text('not json')
            with receipts.receipt_transaction(root),self.assertRaises(receipts.OperationReceiptError):
                receipts.latest_receipt(root,intent='same',payload_sha256=receipts.payload_hash(1),effect='effect')

    def test_actual_writer_shares_one_index_across_multiple_envelopes(self):
        with tempfile.TemporaryDirectory() as work:
            root=_tower(Path(work)/'TOWER_V06')
            control=json.loads((root/'CONTROL.json').read_text())
            control['truth_owner']='TOWER_V06@GOOGLE_DRIVE_PRIVATE'
            (root/'CONTROL.json').write_text(json.dumps(control))
            raw=json.dumps(build_live_tower_payload(root)).encode()
            items=[{'document':'CONTROL.json','role':'ADVISOR','intent_id':str(i),'changes':{'truth_owner':'FORGED'}} for i in range(5)]
            packed,report=apply_to_tower(raw,items)
            self.assertEqual(report['receipt_index']['full_scans'],1)
            self.assertEqual(len(report['rejected']),5)
            self.assertIsNotNone(packed)
