
"""Unit tests for depth-first graph traversal."""

import unittest
from pathlib import Path

from backend.algorithms.dfs import dfs
from backend.loaders.graph_loader import load_graph
from backend.structures.graph import (
    DirectedWeightedGraph,
    GraphEdge,
    GraphNode,
)


class TestDFS(unittest.TestCase):
    """Verify depth-first traversal and access restrictions."""

    @classmethod
    def setUpClass(cls) -> None:
        graph_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "training_graph.json"
        )

        cls.graph = load_graph(graph_path)

    def test_access_without_admission(self):
        """Reject traversal without recruiter admission."""
        with self.assertRaises(PermissionError):
            dfs(self.graph)

    def test_reevaluation_does_not_replace_admission(self):
        """Reevaluation approval alone cannot open the graph."""
        with self.assertRaises(PermissionError):
            dfs(
                self.graph,
                ("human_reevaluation_approved",),
            )

    def test_traversal_with_admission(self):
        """Visit training states in depth-first order."""
        result = dfs(
            self.graph,
            ("recruiter_admission_approved",),
        )

        expected = (
            "training_00",
            "training_10",
            "training_11",
            "reevaluation",
            "training_01",
        )

        self.assertEqual(result, expected)

    def test_traversal_with_both_approvals(self):
        """Reach all nodes when both permissions are available."""
        result = dfs(
            self.graph,
            (
                "recruiter_admission_approved",
                "human_reevaluation_approved",
            ),
        )

        expected = (
            "training_00",
            "training_10",
            "training_11",
            "reevaluation",
            "opportunities",
            "tournaments",
            "tryouts",
            "sponsorships",
            "training_01",
        )

        self.assertEqual(result, expected)

    def test_opportunities_remain_blocked(self):
        """Do not enter opportunities without human approval."""
        result = dfs(
            self.graph,
            ("recruiter_admission_approved",),
        )

        blocked_nodes = {
            "opportunities",
            "tournaments",
            "tryouts",
            "sponsorships",
        }

        self.assertTrue(blocked_nodes.isdisjoint(result))

    def test_shared_node_visited_once(self):
        """Avoid processing convergent paths repeatedly."""
        result = dfs(
            self.graph,
            ("recruiter_admission_approved",),
        )

        self.assertEqual(result.count("training_11"), 1)
        self.assertEqual(len(result), len(set(result)))

    def test_graph_with_cycle(self):
        """Prevent infinite traversal when edges form a cycle."""
        graph = DirectedWeightedGraph(
            graph_id="cycle_test",
            entry_node="A",
        )

        for node_id in ("A", "B", "C"):
            graph.add_node(
                GraphNode(node_id, "test", node_id)
            )

        graph.add_edge(GraphEdge("A", "B", "A to B", 1))
        graph.add_edge(GraphEdge("B", "C", "B to C", 1))
        graph.add_edge(GraphEdge("C", "A", "C to A", 1))

        self.assertEqual(dfs(graph), ("A", "B", "C"))

    def test_disconnected_node_is_not_visited(self):
        """Exclude nodes unreachable from the entry point."""
        graph = DirectedWeightedGraph(
            graph_id="disconnected_test",
            entry_node="A",
        )

        for node_id in ("A", "B", "X"):
            graph.add_node(
                GraphNode(node_id, "test", node_id)
            )

        graph.add_edge(GraphEdge("A", "B", "A to B", 1))

        self.assertEqual(dfs(graph), ("A", "B"))
        self.assertNotIn("X", dfs(graph))

    def test_depth_first_order(self):
        """Follow one branch before exploring its sibling."""
        graph = DirectedWeightedGraph(
            graph_id="depth_test",
            entry_node="A",
        )

        for node_id in ("A", "B", "C", "D"):
            graph.add_node(
                GraphNode(node_id, "test", node_id)
            )

        graph.add_edge(GraphEdge("A", "B", "A to B", 1))
        graph.add_edge(GraphEdge("A", "C", "A to C", 1))
        graph.add_edge(GraphEdge("B", "D", "B to D", 1))

        self.assertEqual(
            dfs(graph),
            ("A", "B", "D", "C"),
        )

    def test_invalid_entry_node(self):
        """Reject a graph without its configured entry node."""
        graph = DirectedWeightedGraph(
            graph_id="invalid_test",
            entry_node="missing",
        )

        with self.assertRaises(ValueError):
            dfs(graph)


if __name__ == "__main__":
    unittest.main()
