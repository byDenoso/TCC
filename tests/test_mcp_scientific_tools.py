import unittest
from pathlib import Path

from nexo_control_plane.mcp_scientific_tools import (
    submit_scientific_tests_tool,
    tool_descriptor,
)


class FakeApplication:
    def __init__(self):
        self.calls = []

    def submit_utterance(self, utterance, source="chat", defaults=None):
        self.calls.append((utterance, source, defaults or {}))
        return [
            {
                "test_id": "T-CHAT-001",
                "fingerprint": "sha256:abc",
                "state": "DISPATCHED",
                "correlation_id": "CORR-001",
                "dispatch_ref": "github:commit:123",
                "canonical_readback": True,
            }
        ]


class MCPScientificToolTests(unittest.TestCase):
    def test_descriptor_exposes_expected_tool_name_and_no_credentials(self):
        descriptor = tool_descriptor()
        self.assertEqual(descriptor["name"], "nexo_submit_scientific_tests_v1")
        schema = descriptor["inputSchema"]
        self.assertIn("utterance", schema["properties"])
        flattened = repr(schema).lower()
        for forbidden in ("token", "password", "secret", "credential"):
            self.assertNotIn(forbidden, flattened)

    def test_missing_utterance_is_rejected(self):
        with self.assertRaises(ValueError):
            submit_scientific_tests_tool({}, lambda: FakeApplication())

    def test_tool_delegates_to_same_application_contract(self):
        app = FakeApplication()
        result = submit_scientific_tests_tool(
            {
                "utterance": "Teste X; Teste Y",
                "source": "chat",
                "defaults": {"test_group_id": "TEST_GROUP::ADHOC::CHAT-SCIENCE"},
            },
            lambda: app,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(len(result["tests"]), 1)
        self.assertEqual(result["tests"][0]["state"], "DISPATCHED")
        self.assertEqual(
            app.calls,
            [("Teste X; Teste Y", "chat", {"test_group_id": "TEST_GROUP::ADHOC::CHAT-SCIENCE"})],
        )

    def test_tool_rejects_non_execution_utterance_before_service(self):
        app = FakeApplication()
        with self.assertRaises(ValueError):
            submit_scientific_tests_tool(
                {"utterance": "O que acha do teste X?"},
                lambda: app,
            )
        self.assertEqual(app.calls, [])

    def test_runtime_docs_freeze_mcp_tool_and_tower_first_invariant(self):
        control_docs = Path("nexo_control_plane/README.md").read_text(encoding="utf-8")
        dispatch_docs = Path("nexo_dispatch/README.md").read_text(encoding="utf-8")
        combined = control_docs + "\n" + dispatch_docs
        self.assertIn("nexo_submit_scientific_tests_v1", combined)
        self.assertIn("TOWER_FIRST_DISPATCH", combined)
        self.assertIn("byDenoso/NEXO-Obsidian-Vault@main:TOWER_V06", combined)


if __name__ == "__main__":
    unittest.main()
