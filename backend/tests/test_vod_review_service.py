
"""Unit tests for the human VOD review service."""

import unittest
from pathlib import Path

from backend.loaders.tree_loader import load_tree
from backend.models.applicant import Applicant
from backend.models.vod_review import (
    ReviewDecision,
    SkillScores,
    VodReview,
)
from backend.services.recruitment_service import RecruitmentService
from backend.services.vod_review_service import VodReviewService
from backend.structures.binary_tree import BinaryDecisionTree


def make_applicant(**changes) -> Applicant:
    """Create a valid applicant for testing."""
    data = {
        "applicant_id": "ASP-001",
        "game_name": "JugadorDemo",
        "daily_play_hours": 6,
        "peak_rank": "Diamante",
        "accepts_training": True,
        "vod_reference": "vods/demo.mp4",
    }

    data.update(changes)
    return Applicant(**data)


def make_review(**changes) -> VodReview:
    """Create a human VOD review for testing."""
    data = {
        "applicant_id": "ASP-001",
        "reviewer_id": "REC-001",
        "vod_reference": "vods/demo.mp4",
        "scores": SkillScores(
            aim=4,
            game_sense=3,
            rotations=2,
            macro=3,
            micro=4,
            communication=3,
        ),
        "decision": ReviewDecision.APPROVED,
        "feedback": "Evaluacion completada.",
    }

    data.update(changes)
    return VodReview(**data)


class TestVodReviewService(unittest.TestCase):
    """Verify review validation and admission decisions."""

    @classmethod
    def setUpClass(cls) -> None:
        tree_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "profile_tree.json"
        )

        tree = BinaryDecisionTree(load_tree(tree_path))
        cls.recruitment = RecruitmentService(tree)

        cls.service = VodReviewService(
            recruitment_service=cls.recruitment,
            authorized_reviewer_ids={"REC-001", "REC-002"},
        )

    def evaluate(
        self,
        applicant=None,
        review=None,
        reviewer_id="REC-001",
    ):
        """Evaluate using valid defaults."""
        return self.service.evaluate_review(
            applicant if applicant is not None else make_applicant(),
            review if review is not None else make_review(),
            authenticated_reviewer_id=reviewer_id,
        )

    def test_approved_review(self):
        result = self.evaluate()

        self.assertEqual(result["decision"], "approved")
        self.assertTrue(result["admission_approved"])
        self.assertEqual(result["next_step"], "start_training")

    def test_more_evidence_review(self):
        review = make_review(
            decision=ReviewDecision.MORE_EVIDENCE
        )

        result = self.evaluate(review=review)

        self.assertFalse(result["admission_approved"])
        self.assertEqual(
            result["next_step"],
            "submit_additional_vod",
        )

    def test_rejected_review(self):
        review = make_review(
            decision=ReviewDecision.REJECTED
        )

        result = self.evaluate(review=review)

        self.assertFalse(result["admission_approved"])
        self.assertEqual(result["next_step"], "follow_guidance")

    def test_high_scores_do_not_approve_automatically(self):
        scores = SkillScores(5, 5, 5, 5, 5, 5)
        review = make_review(
            scores=scores,
            decision=ReviewDecision.REJECTED,
        )

        result = self.evaluate(review=review)

        self.assertFalse(result["admission_approved"])

    def test_development_player_can_be_reviewed(self):
        applicant = make_applicant(peak_rank="Oro")

        result = self.evaluate(applicant=applicant)

        self.assertTrue(result["admission_approved"])
        self.assertEqual(
            result["classification"],
            "Preselección desarrollo",
        )

    def test_non_preselected_applicants_are_rejected(self):
        invalid_profiles = (
            {"daily_play_hours": 3},
            {"peak_rank": "Plata"},
            {"accepts_training": False},
        )

        for changes in invalid_profiles:
            with self.subTest(changes=changes):
                applicant = make_applicant(**changes)

                with self.assertRaises(ValueError):
                    self.evaluate(applicant=applicant)

    def test_missing_vod(self):
        applicant = make_applicant(vod_reference=None)

        with self.assertRaises(ValueError):
            self.evaluate(applicant=applicant)

    def test_mismatched_vod(self):
        review = make_review(
            vod_reference="vods/another_match.mp4"
        )

        with self.assertRaises(ValueError):
            self.evaluate(review=review)

    def test_mismatched_applicant(self):
        review = make_review(applicant_id="ASP-999")

        with self.assertRaises(ValueError):
            self.evaluate(review=review)

    def test_unauthorized_reviewer(self):
        with self.assertRaises(PermissionError):
            self.evaluate(reviewer_id="REC-999")

    def test_reviewer_impersonation(self):
        review = make_review(reviewer_id="REC-002")

        with self.assertRaises(PermissionError):
            self.evaluate(
                review=review,
                reviewer_id="REC-001",
            )

    def test_invalid_applicant_type(self):
        with self.assertRaises(TypeError):
            self.service.evaluate_review(
                {"applicant_id": "ASP-001"},
                make_review(),
                authenticated_reviewer_id="REC-001",
            )

    def test_invalid_review_type(self):
        with self.assertRaises(TypeError):
            self.service.evaluate_review(
                make_applicant(),
                {"decision": "approved"},
                authenticated_reviewer_id="REC-001",
            )

    def test_result_contains_scores_and_feedback(self):
        result = self.evaluate()

        self.assertEqual(result["scores"]["aim"], 4)
        self.assertEqual(result["scores"]["rotations"], 2)
        self.assertEqual(
            result["feedback"],
            "Evaluacion completada.",
        )
        self.assertEqual(result["reviewer_id"], "REC-001")

    def test_service_constructor_validation(self):
        with self.assertRaises(TypeError):
            VodReviewService(
                recruitment_service=None,
                authorized_reviewer_ids={"REC-001"},
            )

        for reviewers in (set(), "REC-001"):
            with self.subTest(reviewers=reviewers):
                with self.assertRaises(ValueError):
                    VodReviewService(
                        recruitment_service=self.recruitment,
                        authorized_reviewer_ids=reviewers,
                    )


if __name__ == "__main__":
    unittest.main()
