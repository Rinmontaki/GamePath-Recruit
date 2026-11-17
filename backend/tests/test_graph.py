
"""Unit tests for the GamePath Recruit weighted graph."""

import json
import tempfile
import unittest
from pathlib import Path

from backend.loaders.graph_loader import load_graph
from backend.structures.graph import (
    DirectedWeightedGraph,
    GraphEdge,
    GraphNode,
)


class TestDirectedWeightedGraph(unittest.TestCase):
    """Validate graph structure, weights and access requirements."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "training_graph.json"
        )
        cls.graph = load_graph(cls.graph_path)

    def _new_graph(self) -> DirectedWeightedGraph:
        """Create a minimal graph for isolated tests."""
        graph = DirectedWeightedGraph(
            graph_id="test_graph",
            entry_node="A",
        )

        graph.add_node(GraphNode("A", "test", "Start"))
        graph.add_node(GraphNode("B", "test", "End"))

        return graph

    def _load_modified_json(self, data: dict):
        """Load modified graph data from a temporary file."""
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "graph.json"

            file_path.write_text(
                json.dumps(data),
                encoding="utf-8",
            )

            return load_graph(file_path)

    def _read_graph_data(self) -> dict:
        """Read the original JSON without modifying it."""
        return json.loads(
            self.graph_path.read_text(encoding="utf-8")
        )

    def test_graph_counts(self):
        self.assertEqual(self.graph.node_count, 9)
        self.assertEqual(self.graph.edge_count, 9)

    def test_initial_training_branches(self):
        edges = self.graph.outgoing_edges("training_00")

        destinations = {
            edge.target: edge.weight_hours
            for edge in edges
        }

        self.assertEqual(
            destinations,
            {
                "training_10": 2,
                "training_01": 3,
            },
        )

    def test_training_progression(self):
        aim_edges = self.graph.outgoing_edges("training_10")
        tactical_edges = self.graph.outgoing_edges("training_01")

        self.assertEqual(len(aim_edges), 1)
        self.assertEqual(len(tactical_edges), 1)

        self.assertEqual(aim_edges[0].target, "training_11")
        self.assertEqual(tactical_edges[0].target, "training_11")

        self.assertEqual(aim_edges[0].weight_hours, 3)
        self.assertEqual(tactical_edges[0].weight_hours, 2)

    def test_both_skills_required_for_reevaluation(self):
        completed = self.graph.get_node("training_11")

        self.assertEqual(
            completed.completed,
            {"aim": True, "tactics": True},
        )

        edges = self.graph.outgoing_edges("training_11")

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].target, "reevaluation")

        initial_targets = {
            edge.target
            for edge in self.graph.outgoing_edges("training_00")
        }

        self.assertNotIn("reevaluation", initial_targets)

    def test_entry_requires_recruiter_approval(self):
        self.assertFalse(self.graph.can_enter())

        self.assertTrue(
            self.graph.can_enter(
                ("recruiter_admission_approved",)
            )
        )

    def test_reevaluation_requires_human_approval(self):
        blocked = self.graph.available_edges("reevaluation")

        approved = self.graph.available_edges(
            "reevaluation",
            ("human_reevaluation_approved",),
        )

        self.assertEqual(len(blocked), 0)
        self.assertEqual(len(approved), 1)

        self.assertEqual(
            approved[0].target,
            "opportunities",
        )

    def test_monetization_opportunities(self):
        edges = self.graph.outgoing_edges("opportunities")

        destinations = {
            edge.target: edge.weight_hours
            for edge in edges
        }

        self.assertEqual(
            destinations,
            {
                "tournaments": 1,
                "tryouts": 2,
                "sponsorships": 2,
            },
        )

    def test_duplicate_node_is_rejected(self):
        graph = self._new_graph()

        with self.assertRaises(ValueError):
            graph.add_node(
                GraphNode("A", "test", "Duplicate")
            )

    def test_duplicate_edge_is_rejected(self):
        graph = self._new_graph()

        edge = GraphEdge("A", "B", "Training", 2)
        graph.add_edge(edge)

        with self.assertRaises(ValueError):
            graph.add_edge(edge)

    def test_invalid_weights_are_rejected(self):
        invalid_weights = [
            -1,
            float("nan"),
            float("inf"),
            True,
            "two",
        ]

        for weight in invalid_weights:
            with self.subTest(weight=weight):
                graph = self._new_graph()

                with self.assertRaises(ValueError):
                    graph.add_edge(
                        GraphEdge("A", "B", "Training", weight)
                    )

    def test_unknown_endpoints_are_rejected(self):
        graph = self._new_graph()

        with self.assertRaises(ValueError):
            graph.add_edge(
                GraphEdge("X", "B", "Training", 2)
            )

        with self.assertRaises(ValueError):
            graph.add_edge(
                GraphEdge("A", "X", "Training", 2)
            )

    def test_loader_rejects_missing_entry_node(self):
        data = self._read_graph_data()
        data["entry_node"] = "nonexistent"

        with self.assertRaises(ValueError):
            self._load_modified_json(data)

    def test_loader_rejects_unknown_destination(self):
        data = self._read_graph_data()
        data["edges"][0]["to"] = "nonexistent"

        with self.assertRaises(ValueError):
            self._load_modified_json(data)

    def test_loader_requires_directed_graph(self):
        data = self._read_graph_data()
        data["directed"] = False

        with self.assertRaises(ValueError):
            self._load_modified_json(data)


if __name__ == "__main__":
    unittest.main()
