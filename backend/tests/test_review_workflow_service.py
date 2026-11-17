
"""Unit tests for the VOD review persistence workflow."""

import tempfile
import unittest
from pathlib import Path

from backend.loaders.tree_loader import load_tree
from backend.models.applicant import Applicant
from backend.models.vod_review import (
    ReviewDecision,
    SkillScores,
    VodReview,
)
from backend.repositories.applicant_repository import (
    ApplicantRepository,
)
from backend.repositories.vod_review_repository import (
    VodReviewRepository,
)
from backend.services.recruitment_service import RecruitmentService
from backend.services.review_workflow_service import (
    ReviewWorkflowService,
)
from backend.services.vod_review_service import VodReviewService
from backend.storage.database import Database
from backend.structures.binary_tree import BinaryDecisionTree


class TestReviewWorkflowService(unittest.TestCase):
    """Verify human review validation before persistence."""

    def setUp(self) -> None:
        """Create isolated applicants, reviewers and services."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.database = Database(
            Path(temporary.name) / "gamepath_test.sqlite3"
        )
        self.database.initialize()

        applicants = ApplicantRepository(self.database)

        profiles = (
            ("ASP-001", 6, "Diamante", True, "vods/first.mp4"),
            ("ASP-002", 5, "Oro", True, "vods/second.mp4"),
            ("ASP-003", 3, "Oro", True, "vods/third.mp4"),
            ("ASP-004", 6, "Diamante", False, "vods/fourth.mp4"),
            ("ASP-005", 6, "Diamante", True, None),
        )

        for applicant_id, hours, rank, accepts, vod in profiles:
            applicants.add(
                Applicant(
                    applicant_id=applicant_id,
                    game_name=f"Jugador-{applicant_id}",
                    daily_play_hours=hours,
                    peak_rank=rank,
                    accepts_training=accepts,
                    vod_reference=vod,
                )
            )

        with self.database.connection() as connection:
            connection.executemany(
                """
                INSERT INTO reviewers (
                    reviewer_id,
                    display_name,
                    is_active
                )
                VALUES (?, ?, ?)
                """,
                (
                    ("REC-001", "ReclutadorUno", 1),
                    ("REC-002", "ReclutadorDos", 1),
                    ("REC-003", "ReclutadorInactivo", 0),
                    ("REC-004", "ReclutadorSinPermiso", 1),
                ),
            )

        tree_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "profile_tree.json"
        )

        tree = BinaryDecisionTree(load_tree(tree_path))
        recruitment = RecruitmentService(tree)

        self.validation = VodReviewService(
            recruitment_service=recruitment,
            authorized_reviewer_ids={"REC-001", "REC-002"},
        )

        self.workflow = ReviewWorkflowService(
            self.database,
            self.validation,
        )

        self.reviews = VodReviewRepository(self.database)

        self.scores = SkillScores(
            aim=4,
            game_sense=3,
            rotations=2,
            macro=3,
            micro=4,
            communication=3,
        )

    def make_review(self, **changes) -> VodReview:
        """Create a valid review with optional overrides."""
        data = {
            "applicant_id": "ASP-001",
            "reviewer_id": "REC-001",
            "vod_reference": "vods/first.mp4",
            "scores": self.scores,
            "decision": ReviewDecision.APPROVED,
            "feedback": "Evaluacion realizada por el reclutador.",
        }

        data.update(changes)
        return VodReview(**data)

    def record(
        self,
        review: VodReview | None = None,
        reviewer_id: str = "REC-001",
    ) -> int:
        """Record a review with the default reviewer."""
        if review is None:
            review = self.make_review()

        return self.workflow.record_review(
            review,
            authenticated_reviewer_id=reviewer_id,
        )

    def test_approved_review_is_persisted(self):
        """Persist a valid human approval."""
        review = self.make_review()

        review_id = self.record(review)

        self.assertIsInstance(review_id, int)
        self.assertEqual(
            self.reviews.get_by_id(review_id),
            review,
        )

    def test_more_evidence_review_is_persisted(self):
        """Preserve a request for additional evidence."""
        review = self.make_review(
            decision=ReviewDecision.MORE_EVIDENCE
        )

        self.record(review)

        latest = self.reviews.get_latest_for_applicant(
            "ASP-001"
        )

        self.assertEqual(latest, review)
        self.assertFalse(latest.is_approved)

    def test_rejected_review_is_persisted(self):
        """Allow an authorized recruiter to record rejection."""
        review = self.make_review(
            decision=ReviewDecision.REJECTED
        )

        self.record(review)

        latest = self.reviews.get_latest_for_applicant(
            "ASP-001"
        )

        self.assertEqual(latest, review)
        self.assertFalse(latest.is_approved)

    def test_history_preserves_multiple_decisions(self):
        """Retain previous reviews instead of replacing them."""
        first = self.make_review(
            decision=ReviewDecision.MORE_EVIDENCE
        )

        second = self.make_review(
            decision=ReviewDecision.APPROVED,
            feedback="Aprobado tras nueva revision.",
        )

        first_id = self.record(first)
        second_id = self.record(second)

        history = self.reviews.get_for_applicant("ASP-001")

        self.assertLess(first_id, second_id)
        self.assertEqual(history, (second, first))

    def test_applicant_histories_are_independent(self):
        """Do not mix reviews belonging to different players."""
        first = self.make_review()

        second = self.make_review(
            applicant_id="ASP-002",
            vod_reference="vods/second.mp4",
            decision=ReviewDecision.REJECTED,
        )

        self.record(first)
        self.record(second)

        self.assertEqual(
            self.reviews.get_for_applicant("ASP-001"),
            (first,),
        )
        self.assertEqual(
            self.reviews.get_for_applicant("ASP-002"),
            (second,),
        )

    def test_unknown_applicant_is_rejected(self):
        """Do not save reviews for unregistered applicants."""
        review = self.make_review(applicant_id="ASP-999")

        with self.assertRaises(ValueError):
            self.record(review)

        self.assertIsNone(
            self.reviews.get_latest_for_applicant("ASP-999")
        )

    def test_insufficient_availability_is_rejected(self):
        """Reject reviews for applicants below the threshold."""
        review = self.make_review(
            applicant_id="ASP-003",
            vod_reference="vods/third.mp4",
        )

        with self.assertRaises(ValueError):
            self.record(review)

    def test_training_refusal_is_rejected(self):
        """Reject reviews without training commitment."""
        review = self.make_review(
            applicant_id="ASP-004",
            vod_reference="vods/fourth.mp4",
        )

        with self.assertRaises(ValueError):
            self.record(review)

    def test_missing_applicant_vod_is_rejected(self):
        """Require a VOD associated with the applicant."""
        review = self.make_review(
            applicant_id="ASP-005",
            vod_reference="vods/not_registered.mp4",
        )

        with self.assertRaises(ValueError):
            self.record(review)

    def test_mismatched_vod_is_rejected(self):
        """Reject a VOD different from the registered one."""
        review = self.make_review(
            vod_reference="vods/another_match.mp4"
        )

        with self.assertRaises(ValueError):
            self.record(review)

    def test_unknown_reviewer_is_blocked(self):
        """Block reviews attributed to an unknown reviewer."""
        review = self.make_review(
            reviewer_id="REC-999"
        )

        with self.assertRaises(PermissionError):
            self.record(review, reviewer_id="REC-999")

    def test_inactive_reviewer_is_blocked(self):
        """Block reviews made by an inactive reviewer."""
        review = self.make_review(
            reviewer_id="REC-003"
        )

        with self.assertRaises(PermissionError):
            self.record(review, reviewer_id="REC-003")

    def test_active_reviewer_without_permission_is_blocked(self):
        """Require reviewer authorization, not only activity."""
        review = self.make_review(
            reviewer_id="REC-004"
        )

        with self.assertRaises(PermissionError):
            self.record(review, reviewer_id="REC-004")

    def test_reviewer_impersonation_is_blocked(self):
        """Require the reviewer identity to match the record."""
        review = self.make_review(
            reviewer_id="REC-002"
        )

        with self.assertRaises(PermissionError):
            self.record(review, reviewer_id="REC-001")

    def test_invalid_review_type_is_rejected(self):
        """Reject objects other than VodReview."""
        for value in ({}, "approved", 123):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.workflow.record_review(
                        value,
                        authenticated_reviewer_id="REC-001",
                    )

    def test_failed_validation_preserves_database(self):
        """Keep stored history unchanged after invalid review."""
        valid_review = self.make_review()
        self.record(valid_review)

        invalid_review = self.make_review(
            vod_reference="vods/incorrect.mp4"
        )

        with self.assertRaises(ValueError):
            self.record(invalid_review)

        self.assertEqual(
            self.reviews.get_for_applicant("ASP-001"),
            (valid_review,),
        )

    def test_constructor_dependencies_are_validated(self):
        """Require valid database and review service objects."""
        with self.assertRaises(TypeError):
            ReviewWorkflowService(None, self.validation)

        with self.assertRaises(TypeError):
            ReviewWorkflowService(self.database, None)


if __name__ == "__main__":
    unittest.main()
