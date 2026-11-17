
"""Unit tests for Dijkstra's shortest-path algorithm."""

import unittest
from pathlib import Path

from backend.algorithms.dijkstra import dijkstra, PathResult
from backend.loaders.graph_loader import load_graph
from backend.structures.graph import (
    DirectedWeightedGraph,
    GraphEdge,
    GraphNode,
)


class TestDijkstra(unittest.TestCase):
    """Verify minimum-cost routes and access restrictions."""

    @classmethod
    def setUpClass(cls) -> None:
        graph_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "training_graph.json"
        )

        cls.graph = load_graph(graph_path)

        cls.admission = (
            "recruiter_admission_approved",
        )

        cls.approved = (
            "recruiter_admission_approved",
            "human_reevaluation_approved",
        )

    @staticmethod
    def create_graph(node_ids):
        """Create a graph for isolated algorithm tests."""
        graph = DirectedWeightedGraph(
            graph_id="test_graph",
            entry_node=node_ids[0],
        )

        for node_id in node_ids:
            graph.add_node(
                GraphNode(node_id, "test", node_id)
            )

        return graph

    def test_access_without_admission(self):
        """Reject routes without recruiter admission."""
        with self.assertRaises(PermissionError):
            dijkstra(self.graph, "training_11")

    def test_reevaluation_does_not_replace_admission(self):
        """Reevaluation permission alone is insufficient."""
        with self.assertRaises(PermissionError):
            dijkstra(
                self.graph,
                "tournaments",
                ("human_reevaluation_approved",),
            )

    def test_minimum_training_cost(self):
        """Complete both training skills in five hours."""
        result = dijkstra(
            self.graph,
            "training_11",
            self.admission,
        )

        self.assertIsInstance(result, PathResult)
        self.assertEqual(result.total_hours, 5.0)

        self.assertIn(
            result.nodes,
            (
                ("training_00", "training_10", "training_11"),
                ("training_00", "training_01", "training_11"),
            ),
        )

    def test_training_activities(self):
        """Return the activities forming the selected path."""
        result = dijkstra(
            self.graph,
            "training_11",
            self.admission,
        )

        self.assertEqual(len(result.activities), 2)

        self.assertEqual(
            set(result.activities),
            {
                "Completar entrenamiento de aim",
                "Completar entrenamiento táctico",
            },
        )

    def test_reevaluation_preparation_cost(self):
        """Include one hour for reevaluation preparation."""
        result = dijkstra(
            self.graph,
            "reevaluation",
            self.admission,
        )

        self.assertEqual(result.total_hours, 6.0)
        self.assertEqual(
            result.nodes[-2:],
            ("training_11", "reevaluation"),
        )

    def test_opportunities_blocked_without_approval(self):
        """Prevent access to monetization preparation."""
        for target in (
            "opportunities",
            "tournaments",
            "tryouts",
            "sponsorships",
        ):
            with self.subTest(target=target):
                result = dijkstra(
                    self.graph,
                    target,
                    self.admission,
                )

                self.assertIsNone(result)

    def test_monetization_route_costs(self):
        """Verify preparation costs for all opportunities."""
        expected_costs = {
            "tournaments": 7.0,
            "tryouts": 8.0,
            "sponsorships": 8.0,
        }

        for target, expected in expected_costs.items():
            with self.subTest(target=target):
                result = dijkstra(
                    self.graph,
                    target,
                    self.approved,
                )

                self.assertIsNotNone(result)
                self.assertEqual(
                    result.total_hours,
                    expected,
                )

    def test_tournament_route(self):
        """Reach tournaments through the human review gate."""
        result = dijkstra(
            self.graph,
            "tournaments",
            self.approved,
        )

        self.assertEqual(
            result.nodes,
            (
                "training_00",
                "training_10",
                "training_11",
                "reevaluation",
                "opportunities",
                "tournaments",
            ),
        )

        self.assertEqual(
            len(result.activities),
            len(result.nodes) - 1,
        )

    def test_unknown_target(self):
        """Reject destinations absent from the graph."""
        with self.assertRaises(ValueError):
            dijkstra(
                self.graph,
                "unknown_destination",
                self.admission,
            )

    def test_unreachable_target(self):
        """Return None for an existing disconnected node."""
        graph = self.create_graph(("A", "B"))

        result = dijkstra(graph, "B")

        self.assertIsNone(result)

    def test_start_equals_target(self):
        """Return a zero-cost path to the starting node."""
        graph = self.create_graph(("A",))

        result = dijkstra(graph, "A")

        self.assertEqual(result.nodes, ("A",))
        self.assertEqual(result.activities, ())
        self.assertEqual(result.total_hours, 0.0)

    def test_cheaper_indirect_route(self):
        """Prefer lower total cost over fewer edges."""
        graph = self.create_graph(("A", "B", "C"))

        graph.add_edge(
            GraphEdge("A", "B", "Direct route", 9)
        )
        graph.add_edge(
            GraphEdge("A", "C", "First activity", 1)
        )
        graph.add_edge(
            GraphEdge("C", "B", "Second activity", 2)
        )

        result = dijkstra(graph, "B")

        self.assertEqual(
            result.nodes,
            ("A", "C", "B"),
        )
        self.assertEqual(result.total_hours, 3.0)

    def test_zero_cost_edges_and_cycles(self):
        """Handle valid zero weights without infinite loops."""
        graph = self.create_graph(("A", "B", "C"))

        graph.add_edge(
            GraphEdge("A", "B", "Free transition", 0)
        )
        graph.add_edge(
            GraphEdge("B", "A", "Return to A", 0)
        )
        graph.add_edge(
            GraphEdge("B", "C", "Preparation", 2)
        )

        result = dijkstra(graph, "C")

        self.assertEqual(
            result.nodes,
            ("A", "B", "C"),
        )
        self.assertEqual(result.total_hours, 2.0)
        
        
    def test_custom_start_after_aim(self):
        """Plan from the state where aim is completed."""
        result = dijkstra(
            self.graph,
            "reevaluation",
            self.admission,
            start_node="training_10",
        )

        self.assertEqual(
            result.nodes,
            ("training_10", "training_11", "reevaluation"),
        )
        self.assertEqual(result.total_hours, 4.0)

    def test_custom_start_after_tactics(self):
        """Plan from the state where tactics are completed."""
        result = dijkstra(
            self.graph,
            "reevaluation",
            self.admission,
            start_node="training_01",
        )

        self.assertEqual(
            result.nodes,
            ("training_01", "training_11", "reevaluation"),
        )
        self.assertEqual(result.total_hours, 3.0)

    def test_custom_start_requires_admission(self):
        """Changing the start must not bypass admission."""
        with self.assertRaises(PermissionError):
            dijkstra(
                self.graph,
                "reevaluation",
                start_node="training_11",
            )

    def test_invalid_custom_start(self):
        """Reject a starting node absent from the graph."""
        with self.assertRaises(ValueError):
            dijkstra(
                self.graph,
                "reevaluation",
                self.admission,
                start_node="unknown_node",
            )



if __name__ == "__main__":
    unittest.main()
