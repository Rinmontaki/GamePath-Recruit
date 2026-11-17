
"""Unit tests for the GamePath Recruit binary decision tree."""

import unittest
from pathlib import Path

from backend.loaders.tree_loader import load_tree
from backend.structures.binary_tree import BinaryDecisionTree


class TestBinaryDecisionTree(unittest.TestCase):
    """Verify applicant classification and decision paths."""

    @classmethod
    def setUpClass(cls) -> None:
        tree_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "profile_tree.json"
        )

        root = load_tree(tree_path)
        cls.tree = BinaryDecisionTree(root)

    def evaluate_profile(
        self,
        daily_hours=6,
        accepts_training=True,
        peak_rank="Inmortal",
    ):
        """Evaluate a profile using the default test values."""
        profile = {
            "daily_play_hours": daily_hours,
            "accepts_training": accepts_training,
            "peak_rank": peak_rank,
        }

        return self.tree.evaluate(profile)

    def test_advanced_preselection(self):
        result = self.evaluate_profile(
            daily_hours=6,
            peak_rank="Inmortal",
        )

        self.assertEqual(result["node_id"], "L01")
        self.assertEqual(
            result["classification"],
            "Preselección avanzada",
        )

    def test_development_preselection(self):
        result = self.evaluate_profile(
            daily_hours=5,
            peak_rank="Oro",
        )

        self.assertEqual(result["node_id"], "L02")

    def test_foundation_training(self):
        result = self.evaluate_profile(
            peak_rank="Plata",
        )

        self.assertEqual(result["node_id"], "L03")

    def test_training_commitment(self):
        result = self.evaluate_profile(
            accepts_training=False,
            peak_rank="Radiante",
        )

        self.assertEqual(result["node_id"], "L04")

    def test_insufficient_availability(self):
        result = self.evaluate_profile(
            daily_hours=4,
            peak_rank="Radiante",
        )

        self.assertEqual(result["node_id"], "L05")

    def test_exact_five_hour_threshold(self):
        result = self.evaluate_profile(
            daily_hours=5,
        )

        self.assertEqual(result["node_id"], "L01")

    def test_below_five_hour_threshold(self):
        result = self.evaluate_profile(
            daily_hours=4.99,
        )

        self.assertEqual(result["node_id"], "L05")

    def test_diamond_rank_boundary(self):
        result = self.evaluate_profile(
            peak_rank="Diamante",
        )

        self.assertEqual(result["node_id"], "L01")

    def test_decision_path(self):
        result = self.evaluate_profile(
            daily_hours=5,
            peak_rank="Diamante",
        )

        visited_ids = [
            step["node_id"]
            for step in result["decision_path"]
        ]

        self.assertEqual(
            visited_ids,
            ["D01", "D02", "D03", "D04"],
        )

        self.assertTrue(
            all(
                step["answer"] == "Sí"
                for step in result["decision_path"]
            )
        )

    def test_early_termination(self):
        result = self.evaluate_profile(
            daily_hours=3,
            accepts_training=False,
            peak_rank="Radiante",
        )

        self.assertEqual(result["node_id"], "L05")
        self.assertEqual(
            len(result["decision_path"]),
            1,
        )

    def test_result_has_explanation(self):
        result = self.evaluate_profile(
            daily_hours=3,
        )

        self.assertTrue(result["reason"])
        self.assertTrue(result["recommendation"])

    def test_invalid_hours(self):
        invalid_values = [
            -1,
            25,
            float("nan"),
            float("inf"),
            True,
            "cinco",
        ]

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.evaluate_profile(
                        daily_hours=value,
                    )

    def test_invalid_rank(self):
        with self.assertRaises(ValueError):
            self.evaluate_profile(
                peak_rank="Rango inexistente",
            )

    def test_invalid_training_answer(self):
        with self.assertRaises(ValueError):
            self.evaluate_profile(
                accepts_training="Sí",
            )

    def test_missing_profile_field(self):
        profile = {
            "daily_play_hours": 6,
            "peak_rank": "Oro",
        }

        with self.assertRaises(ValueError):
            self.tree.evaluate(profile)


if __name__ == "__main__":
    unittest.main()
