
"""Unit tests for SQLite VOD review persistence."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.models.applicant import Applicant
from backend.models.vod_review import (
    ReviewDecision,
    SkillScores,
    VodReview,
)
from backend.repositories.applicant_repository import ApplicantRepository
from backend.repositories.vod_review_repository import VodReviewRepository
from backend.storage.database import Database


def make_review(**changes) -> VodReview:
    """Create a valid review with optional overrides."""
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
        "decision": ReviewDecision.MORE_EVIDENCE,
        "feedback": "Se necesita otra partida.",
    }

    data.update(changes)
    return VodReview(**data)


class TestVodReviewRepository(unittest.TestCase):
    """Verify VOD review persistence and history."""

    def setUp(self) -> None:
        """Create an isolated database with sample users."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.database = Database(
            Path(temporary.name) / "gamepath_test.sqlite3"
        )
        self.database.initialize()

        applicants = ApplicantRepository(self.database)

        applicants.add(
            Applicant(
                applicant_id="ASP-001",
                game_name="JugadorUno",
                daily_play_hours=6,
                peak_rank="Diamante",
                accepts_training=True,
                vod_reference="vods/demo.mp4",
            )
        )

        applicants.add(
            Applicant(
                applicant_id="ASP-002",
                game_name="JugadorDos",
                daily_play_hours=5,
                peak_rank="Oro",
                accepts_training=True,
                vod_reference="vods/second.mp4",
            )
        )

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO reviewers (
                    reviewer_id,
                    display_name
                )
                VALUES (?, ?)
                """,
                ("REC-001", "ReclutadorDemo"),
            )

        self.repository = VodReviewRepository(self.database)

    def test_save_and_retrieve_review(self):
        """Preserve a review after saving it."""
        review = make_review()

        review_id = self.repository.add(review)
        recovered = self.repository.get_by_id(review_id)

        self.assertEqual(recovered, review)
        self.assertIsInstance(review_id, int)

    def test_generated_ids_are_distinct(self):
        """Assign an independent ID to each review."""
        first_id = self.repository.add(make_review())
        second_id = self.repository.add(make_review())

        self.assertLess(first_id, second_id)

    def test_get_by_id_not_found(self):
        """Return None for a missing review."""
        self.assertIsNone(self.repository.get_by_id(999))

    def test_history_newest_first(self):
        """Return reviews in descending insertion order."""
        first = make_review()

        second = make_review(
            decision=ReviewDecision.APPROVED,
            feedback="Aprobado en una nueva revision.",
        )

        self.repository.add(first)
        self.repository.add(second)

        history = self.repository.get_for_applicant("ASP-001")

        self.assertEqual(history, (second, first))

    def test_latest_review(self):
        """Return the most recently inserted review."""
        self.repository.add(make_review())

        latest_review = make_review(
            decision=ReviewDecision.APPROVED,
            feedback="Admitido para comenzar entrenamiento.",
        )

        self.repository.add(latest_review)

        recovered = self.repository.get_latest_for_applicant(
            "ASP-001"
        )

        self.assertEqual(recovered, latest_review)

    def test_empty_history_and_latest(self):
        """Handle applicants without recorded reviews."""
        history = self.repository.get_for_applicant("ASP-002")
        latest = self.repository.get_latest_for_applicant(
            "ASP-002"
        )

        self.assertEqual(history, ())
        self.assertIsNone(latest)

    def test_applicant_histories_isolated(self):
        """Avoid mixing reviews from different applicants."""
        first = make_review()

        second = make_review(
            applicant_id="ASP-002",
            vod_reference="vods/second.mp4",
            decision=ReviewDecision.REJECTED,
        )

        self.repository.add(first)
        self.repository.add(second)

        self.assertEqual(
            self.repository.get_for_applicant("ASP-001"),
            (first,),
        )
        self.assertEqual(
            self.repository.get_for_applicant("ASP-002"),
            (second,),
        )

    def test_scores_and_feedback_restored(self):
        """Preserve the six skill scores and feedback."""
        scores = SkillScores(
            aim=5,
            game_sense=1,
            rotations=3,
            macro=4,
            micro=2,
            communication=5,
        )

        review = make_review(
            scores=scores,
            feedback="Evaluacion detallada de habilidades.",
        )

        review_id = self.repository.add(review)
        recovered = self.repository.get_by_id(review_id)

        self.assertEqual(recovered.scores, scores)
        self.assertEqual(recovered.feedback, review.feedback)

    def test_data_survives_reopening_repository(self):
        """Recover saved data through a new repository."""
        review = make_review()
        review_id = self.repository.add(review)

        another_repository = VodReviewRepository(
            self.database
        )

        self.assertEqual(
            another_repository.get_by_id(review_id),
            review,
        )

    def test_reject_non_review(self):
        """Only accept actual VodReview instances."""
        for value in (None, {}, "approved"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.repository.add(value)

    def test_invalid_review_id(self):
        """Reject invalid review identifiers."""
        for value in (0, -1, True, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.repository.get_by_id(value)

    def test_invalid_history_applicant_id(self):
        """Validate identifiers used for history queries."""
        for value in ("", "   ", None, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.repository.get_for_applicant(value)

    def test_invalid_latest_applicant_id(self):
        """Validate identifiers for latest-review queries."""
        for value in ("", "   ", None, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.repository.get_latest_for_applicant(value)

    def test_fk_rejects_missing_applicant(self):
        """Reject a review linked to an unknown applicant."""
        review = make_review(applicant_id="ASP-999")

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.add(review)

    def test_fk_rejects_missing_reviewer(self):
        """Reject a review linked to an unknown reviewer."""
        review = make_review(reviewer_id="REC-999")

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.add(review)

    def test_failed_insert_preserves_saved_review(self):
        """Keep existing reviews after a failed insertion."""
        original = make_review()

        self.repository.add(original)

        invalid = make_review(
            reviewer_id="REC-999",
            decision=ReviewDecision.APPROVED,
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.add(invalid)

        self.assertEqual(
            self.repository.get_for_applicant("ASP-001"),
            (original,),
        )


if __name__ == "__main__":
    unittest.main()
