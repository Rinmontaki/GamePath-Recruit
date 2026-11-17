
"""Unit tests for breadth-first graph traversal."""

import unittest
from pathlib import Path

from backend.algorithms.bfs import bfs
from backend.loaders.graph_loader import load_graph
from backend.structures.graph import (
    DirectedWeightedGraph,
    GraphEdge,
    GraphNode,
)


class TestBFS(unittest.TestCase):
    """Verify breadth-first traversal and access rules."""

    @classmethod
    def setUpClass(cls) -> None:
        graph_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "training_graph.json"
        )

        cls.graph = load_graph(graph_path)

    def test_access_without_admission(self):
        """Reject traversal without recruiter approval."""
        with self.assertRaises(PermissionError):
            bfs(self.graph)

    def test_reevaluation_approval_without_admission(self):
        """Reevaluation approval cannot replace admission."""
        with self.assertRaises(PermissionError):
            bfs(
                self.graph,
                ("human_reevaluation_approved",),
            )

    def test_traversal_with_admission(self):
        """Reach training and reevaluation states."""
        result = bfs(
            self.graph,
            ("recruiter_admission_approved",),
        )

        expected = (
            "training_00",
            "training_10",
            "training_01",
            "training_11",
            "reevaluation",
        )

        self.assertEqual(result, expected)

    def test_traversal_with_both_approvals(self):
        """Reach all graph nodes when gates are enabled."""
        result = bfs(
            self.graph,
            (
                "recruiter_admission_approved",
                "human_reevaluation_approved",
            ),
        )

        expected = (
            "training_00",
            "training_10",
            "training_01",
            "training_11",
            "reevaluation",
            "opportunities",
            "tournaments",
            "tryouts",
            "sponsorships",
        )

        self.assertEqual(result, expected)

    def test_opportunities_remain_blocked(self):
        """Exclude opportunities without reevaluation approval."""
        result = bfs(
            self.graph,
            ("recruiter_admission_approved",),
        )

        self.assertNotIn("opportunities", result)
        self.assertNotIn("tournaments", result)
        self.assertNotIn("tryouts", result)
        self.assertNotIn("sponsorships", result)

    def test_repeated_destinations_are_visited_once(self):
        """Visit shared training states only once."""
        result = bfs(
            self.graph,
            ("recruiter_admission_approved",),
        )

        self.assertEqual(result.count("training_11"), 1)
        self.assertEqual(len(result), len(set(result)))

    def test_graph_with_cycle(self):
        """Avoid infinite traversal in a cyclic graph."""
        graph = DirectedWeightedGraph(
            graph_id="cycle_test",
            entry_node="A",
        )

        for node_id in ("A", "B", "C"):
            graph.add_node(
                GraphNode(node_id, "test", node_id)
            )

        graph.add_edge(
            GraphEdge("A", "B", "Go to B", 1)
        )
        graph.add_edge(
            GraphEdge("B", "A", "Return to A", 1)
        )
        graph.add_edge(
            GraphEdge("B", "C", "Go to C", 1)
        )

        self.assertEqual(
            bfs(graph),
            ("A", "B", "C"),
        )

    def test_invalid_entry_node(self):
        """Reject traversal when the entry node is absent."""
        graph = DirectedWeightedGraph(
            graph_id="invalid_test",
            entry_node="missing",
        )

        with self.assertRaises(ValueError):
            bfs(graph)

    def test_result_is_immutable_tuple(self):
        """Return an ordered tuple of visited node IDs."""
        result = bfs(
            self.graph,
            ("recruiter_admission_approved",),
        )

        self.assertIsInstance(result, tuple)


if __name__ == "__main__":
    unittest.main()
