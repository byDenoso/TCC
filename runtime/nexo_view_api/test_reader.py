"""Tests for the NEXO Tower reader."""

from __future__ import annotations

import unittest

from .reader import TowerReader


class TowerReaderTests(unittest.TestCase):
    def test_graph_data(self) -> None:
        reader = TowerReader("tower_template")
        payload = reader.graph_data("GRAPH::OPS::AUTOMATION_PIPELINE")
        self.assertEqual(payload["renderer"], "react_flow")
        self.assertGreater(len(payload["nodes"]), 0)

    def test_snapshot_lists_graphs(self) -> None:
        reader = TowerReader("tower_template")
        snapshot = reader.snapshot()
        self.assertIn("GRAPH::OPS::AUTOMATION_PIPELINE", snapshot["graphs"])


if __name__ == "__main__":
    unittest.main()
