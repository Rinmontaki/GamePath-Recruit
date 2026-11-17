
"""Unit tests for human VOD evaluation models."""

import unittest
from dataclasses import FrozenInstanceError

from backend.models.vod_review import (
    ReviewDecision,
    SkillScores,
    VodReview,
)


def make_scores(**changes) -> SkillScores:
    """Create valid skill scores with optional overrides."""
    data = {
        "aim": 4,
        "game_sense": 3,
        "rotations": 2,
        "macro": 3,
        "micro": 4,
        "communication": 3,
    }

    data.update(changes)
    return SkillScores(**data)


def make_review(**changes) -> VodReview:
    """Create a valid VOD review for testing."""
    data = {
        "applicant_id": "ASP-001",
        "reviewer_id": "REC-001",
        "vod_reference": "vods/demo.mp4",
        "scores": make_scores(),
        "decision": ReviewDecision.MORE_EVIDENCE,
        "feedback": "Se necesita otra partida.",
    }

    data.update(changes)
    return VodReview(**data)


class TestVodReview(unittest.TestCase):
    """Verify skill scores and human review records."""

    def test_more_evidence_decision(self):
        """More evidence must not count as approval."""
        review = make_review()

        self.assertEqual(
            review.decision,
            ReviewDecision.MORE_EVIDENCE,
        )
        self.assertFalse(review.is_approved)

    def test_approved_decision(self):
        """Recognize an explicit human approval."""
        review = make_review(
            decision=ReviewDecision.APPROVED,
            feedback="Aprobado para continuar.",
        )

        self.assertTrue(review.is_approved)
        self.assertEqual(review.applicant_id, "ASP-001")

    def test_rejected_decision(self):
        """A rejection must not grant admission."""
        review = make_review(
            decision=ReviewDecision.REJECTED,
            feedback="No cumple los criterios de evaluación.",
        )

        self.assertFalse(review.is_approved)

    def test_boundary_scores(self):
        """Accept the minimum and maximum valid scores."""
        for score in (1, 5):
            with self.subTest(score=score):
                scores = SkillScores(
                    aim=score,
                    game_sense=score,
                    rotations=score,
                    macro=score,
                    micro=score,
                    communication=score,
                )

                self.assertEqual(scores.aim, score)

    def test_invalid_score_values(self):
        """Reject scores outside the permitted scale."""
        invalid_values = (
            0,
            6,
            -1,
            2.5,
            True,
            "4",
            None,
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    make_scores(aim=value)

    def test_every_skill_is_validated(self):
        """Apply score validation to all six skills."""
        skill_names = (
            "aim",
            "game_sense",
            "rotations",
            "macro",
            "micro",
            "communication",
        )

        for skill_name in skill_names:
            with self.subTest(skill=skill_name):
                with self.assertRaises(ValueError):
                    make_scores(**{skill_name: 0})

    def test_required_text_fields(self):
        """Reject empty or invalid review information."""
        invalid_cases = (
            {"applicant_id": ""},
            {"reviewer_id": "   "},
            {"vod_reference": ""},
            {"feedback": ""},
            {"reviewer_id": 123},
        )

        for changes in invalid_cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    make_review(**changes)

    def test_scores_instance_required(self):
        """Require an actual SkillScores instance."""
        with self.assertRaises(TypeError):
            make_review(scores={"aim": 5})

    def test_decision_enum_required(self):
        """Reject unvalidated decision strings."""
        with self.assertRaises(TypeError):
            make_review(decision="approved")

    def test_models_are_immutable(self):
        """Prevent modifying review records directly."""
        scores = make_scores()
        review = make_review()

        with self.assertRaises(FrozenInstanceError):
            scores.aim = 5

        with self.assertRaises(FrozenInstanceError):
            review.decision = ReviewDecision.APPROVED


if __name__ == "__main__":
    unittest.main()
