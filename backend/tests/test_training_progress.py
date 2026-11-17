
"""Unit tests for individual training progress."""

import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from backend.loaders.graph_loader import load_graph
from backend.models.training_progress import (
    SUPPORTED_SKILLS,
    TrainingProgress,
)


class TestTrainingProgress(unittest.TestCase):
    """Verify training states and progress validation."""

    @classmethod
    def setUpClass(cls) -> None:
        graph_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "training_graph.json"
        )

        cls.graph = load_graph(graph_path)

    def test_initial_progress(self):
        """A new applicant starts without completed skills."""
        progress = TrainingProgress("ASP-001")

        self.assertEqual(
            progress.completed_skills,
            frozenset(),
        )
        self.assertEqual(
            progress.current_node_id,
            "training_00",
        )
        self.assertFalse(progress.is_training_complete)

    def test_only_aim_completed(self):
        """Completing aim leads to training_10."""
        progress = TrainingProgress(
            "ASP-001",
            frozenset({"aim"}),
        )

        self.assertEqual(
            progress.current_node_id,
            "training_10",
        )
        self.assertEqual(
            progress.pending_skills,
            frozenset({"tactics"}),
        )
        self.assertFalse(progress.is_training_complete)

    def test_only_tactics_completed(self):
        """Completing tactics leads to training_01."""
        progress = TrainingProgress(
            "ASP-001",
            frozenset({"tactics"}),
        )

        self.assertEqual(
            progress.current_node_id,
            "training_01",
        )
        self.assertEqual(
            progress.pending_skills,
            frozenset({"aim"}),
        )
        self.assertFalse(progress.is_training_complete)

    def test_both_skills_completed(self):
        """Both skills lead to the final training state."""
        progress = TrainingProgress(
            "ASP-001",
            frozenset({"aim", "tactics"}),
        )

        self.assertEqual(
            progress.current_node_id,
            "training_11",
        )
        self.assertEqual(
            progress.pending_skills,
            frozenset(),
        )
        self.assertTrue(progress.is_training_complete)

    def test_graph_state_consistency(self):
        """Every computed state must match the graph JSON."""
        cases = (
            frozenset(),
            frozenset({"aim"}),
            frozenset({"tactics"}),
            frozenset({"aim", "tactics"}),
        )

        for completed in cases:
            with self.subTest(completed=completed):
                progress = TrainingProgress(
                    "ASP-001",
                    completed,
                )

                node = self.graph.get_node(
                    progress.current_node_id
                )

                self.assertEqual(
                    node.completed,
                    {
                        "aim": "aim" in completed,
                        "tactics": "tactics" in completed,
                    },
                )

    def test_completed_and_pending_partition(self):
        """Completed and pending skills cover all skills."""
        cases = (
            frozenset(),
            frozenset({"aim"}),
            frozenset({"tactics"}),
            SUPPORTED_SKILLS,
        )

        for completed in cases:
            with self.subTest(completed=completed):
                progress = TrainingProgress(
                    "ASP-001",
                    completed,
                )

                self.assertEqual(
                    progress.completed_skills
                    | progress.pending_skills,
                    SUPPORTED_SKILLS,
                )

                self.assertFalse(
                    progress.completed_skills
                    & progress.pending_skills
                )

    def test_invalid_applicant_id(self):
        """Reject invalid applicant identifiers."""
        invalid_ids = (
            "",
            "   ",
            None,
            123,
        )

        for applicant_id in invalid_ids:
            with self.subTest(applicant_id=applicant_id):
                with self.assertRaises(ValueError):
                    TrainingProgress(applicant_id)

    def test_completed_skills_requires_frozenset(self):
        """Reject mutable or incorrectly typed collections."""
        invalid_values = (
            set(),
            ["aim"],
            ("aim",),
            "aim",
            None,
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    TrainingProgress(
                        "ASP-001",
                        value,
                    )

    def test_invalid_skill_values(self):
        """Reject empty or non-string skill identifiers."""
        invalid_values = (
            None,
            "",
            "   ",
            123,
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    TrainingProgress(
                        "ASP-001",
                        frozenset({value}),
                    )

    def test_unsupported_skills(self):
        """Reject skills not represented by the current graph."""
        invalid_cases = (
            frozenset({"movement"}),
            frozenset({"AIM"}),
            frozenset({"aim", "rotations"}),
        )

        for skills in invalid_cases:
            with self.subTest(skills=skills):
                with self.assertRaises(ValueError):
                    TrainingProgress(
                        "ASP-001",
                        skills,
                    )

    def test_progress_is_immutable(self):
        """Prevent directly changing recorded progress."""
        progress = TrainingProgress(
            "ASP-001",
            frozenset({"aim"}),
        )

        with self.assertRaises(FrozenInstanceError):
            progress.completed_skills = frozenset(
                {"aim", "tactics"}
            )

    def test_applicants_have_independent_progress(self):
        """Progress must belong to its own applicant."""
        first = TrainingProgress(
            "ASP-001",
            frozenset({"aim"}),
        )

        second = TrainingProgress(
            "ASP-002",
            frozenset({"tactics"}),
        )

        self.assertNotEqual(
            first.applicant_id,
            second.applicant_id,
        )
        self.assertNotEqual(
            first.current_node_id,
            second.current_node_id,
        )


if __name__ == "__main__":
    unittest.main()
