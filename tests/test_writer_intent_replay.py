"""Regression: terminal intents are not replayed at each Writer tick."""
import unittest
from runtime.nexo_agent_api.operational_control import OperationalWorker, digest


class Store:
    def __init__(self, work):
        self.work = work

    def get(self, work_id):
        return self.work

    def all(self):
        return [self.work]


class TickRepeatTest(unittest.TestCase):
    def test_skips_matching_stale_and_continues_progress(self):
        intent = {"work_id": "w1", "id": "op-test", "contract": "NEXO_OPERATIONAL_INTENT_V1", "action": "request_execution"}
        work = {"id": "w1", "state": "BLOCKED", "processed": {intent["id"]: {
            "intent_sha256": digest(intent), "disposition": "STALE_VERSION"
        }}}
        worker = object.__new__(OperationalWorker)
        worker.store = Store(work)
        called = []
        worker.handle = lambda x: called.append(x) or {"state": "REJECTED"}
        worker.progress = lambda work_id: {"state": "BLOCKED"}
        report = worker.tick([intent])
        self.assertEqual(report["terminal_replays_skipped"], 1)
        self.assertEqual(report["intents"], [])
        self.assertEqual(report["progress"], [{"work_id": "w1", "state": "BLOCKED"}])
        self.assertFalse(called)

    def test_changed_payload_remains_subject_to_full_validation(self):
        intent = {"work_id": "w1", "id": "op-test", "contract": "NEXO_OPERATIONAL_INTENT_V1", "action": "claim_work"}
        stored = {"work_id": "w1", "id": "op-test", "contract": "NEXO_OPERATIONAL_INTENT_V1", "action": "request_execution"}
        work = {"id": "w1", "state": "BLOCKED", "processed": {"op-test": {
            "intent_sha256": digest(stored), "disposition": "STALE_VERSION"
        }}}
        worker = object.__new__(OperationalWorker)
        worker.store = Store(work)
        called = []
        worker.handle = lambda x: called.append(x) or {"state": "REJECTED"}
        worker.progress = lambda work_id: {"state": "BLOCKED"}
        report = worker.tick([intent])
        self.assertEqual(report["terminal_replays_skipped"], 0)
        self.assertEqual(called, [intent])
