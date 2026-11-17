
"""Unit tests for applicant models and recruitment services."""

import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from backend.loaders.tree_loader import load_tree
from backend.models.applicant import Applicant
from backend.services.recruitment_service import RecruitmentService
from backend.structures.binary_tree import BinaryDecisionTree


def make_applicant(**changes) -> Applicant:
    """Create an applicant with overridable test values."""
    data = {
        "applicant_id": "ASP-001",
        "game_name": "JugadorDemo",
        "daily_play_hours": 6,
        "peak_rank": "Diamante",
        "accepts_training": True,
    }

    data.update(changes)
    return Applicant(**data)


class TestApplicant(unittest.TestCase):
    """Verify applicant creation and data validation."""

    def test_profile_mapping(self):
        applicant = make_applicant()

        self.assertEqual(
            applicant.to_profile(),
            {
                "daily_play_hours": 6,
                "peak_rank": "Diamante",
                "accepts_training": True,
            },
        )

    def test_below_threshold_is_valid(self):
        applicant = make_applicant(daily_play_hours=3)

        self.assertEqual(applicant.daily_play_hours, 3)

    def test_invalid_required_fields(self):
        invalid_cases = (
            {"applicant_id": ""},
            {"game_name": "   "},
            {"peak_rank": ""},
        )

        for changes in invalid_cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    make_applicant(**changes)

    def test_invalid_hours(self):
        invalid_hours = (
            -1,
            25,
            float("nan"),
            float("inf"),
            True,
            "cinco",
        )

        for hours in invalid_hours:
            with self.subTest(hours=hours):
                with self.assertRaises(ValueError):
                    make_applicant(daily_play_hours=hours)

    def test_invalid_training_acceptance(self):
        with self.assertRaises(ValueError):
            make_applicant(accepts_training="Sí")

    def test_invalid_optional_fields(self):
        invalid_cases = (
            {"current_rank": "   "},
            {"preferred_role": ""},
            {"vod_reference": 123},
        )

        for changes in invalid_cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    make_applicant(**changes)

    def test_applicant_is_immutable(self):
        applicant = make_applicant()

        with self.assertRaises(FrozenInstanceError):
            applicant.game_name = "NuevoNombre"


class TestRecruitmentService(unittest.TestCase):
    """Verify preselection and next-step decisions."""

    @classmethod
    def setUpClass(cls) -> None:
        tree_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "profile_tree.json"
        )

        tree = BinaryDecisionTree(load_tree(tree_path))
        cls.service = RecruitmentService(tree)

    def test_advanced_without_vod(self):
        result = self.service.preselect(make_applicant())

        self.assertEqual(result["node_id"], "L01")
        self.assertTrue(result["eligible_for_vod_review"])
        self.assertEqual(result["next_step"], "submit_vod")

    def test_advanced_with_vod(self):
        applicant = make_applicant(
            vod_reference="vods/demo.mp4"
        )

        result = self.service.preselect(applicant)

        self.assertEqual(
            result["next_step"],
            "request_human_vod_review",
        )

    def test_development_preselection(self):
        applicant = make_applicant(
            daily_play_hours=5,
            peak_rank="Oro",
        )

        result = self.service.preselect(applicant)

        self.assertEqual(result["node_id"], "L02")
        self.assertTrue(result["eligible_for_vod_review"])

    def test_insufficient_availability(self):
        applicant = make_applicant(daily_play_hours=3)

        result = self.service.preselect(applicant)

        self.assertEqual(result["node_id"], "L05")
        self.assertFalse(result["eligible_for_vod_review"])
        self.assertEqual(result["next_step"], "follow_guidance")

    def test_training_commitment_pending(self):
        applicant = make_applicant(
            accepts_training=False
        )

        result = self.service.preselect(applicant)

        self.assertEqual(result["node_id"], "L04")
        self.assertFalse(result["eligible_for_vod_review"])

    def test_foundation_guidance(self):
        applicant = make_applicant(peak_rank="Plata")

        result = self.service.preselect(applicant)

        self.assertEqual(result["node_id"], "L03")
        self.assertEqual(result["next_step"], "follow_guidance")

    def test_reject_non_applicant(self):
        with self.assertRaises(TypeError):
            self.service.preselect({"peak_rank": "Oro"})

    def test_invalid_rank_is_rejected(self):
        applicant = make_applicant(
            peak_rank="RangoInexistente"
        )

        with self.assertRaises(ValueError):
            self.service.preselect(applicant)

    def test_result_contains_decision_path(self):
        result = self.service.preselect(make_applicant())

        visited = [
            step["node_id"]
            for step in result["decision_path"]
        ]

        self.assertEqual(
            visited,
            ["D01", "D02", "D03", "D04"],
        )
        self.assertEqual(result["applicant_id"], "ASP-001")
        self.assertTrue(result["recommendation"])


if __name__ == "__main__":
    unittest.main()
