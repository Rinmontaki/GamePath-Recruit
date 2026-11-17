
"""Persist and retrieve human VOD review records."""

import sqlite3

from backend.models.vod_review import (
    ReviewDecision,
    SkillScores,
    VodReview,
)
from backend.storage.database import Database


class VodReviewRepository:
    """Manage VOD reviews stored in SQLite."""

    def __init__(self, database: Database) -> None:
        if not isinstance(database, Database):
            raise TypeError("A Database instance is required.")

        self._database = database

    def add(self, review: VodReview) -> int:
        """Save a review and return its database ID."""
        if not isinstance(review, VodReview):
            raise TypeError("A VodReview instance is required.")

        with self._database.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO vod_reviews (
                    applicant_id,
                    reviewer_id,
                    vod_reference,
                    decision,
                    aim,
                    game_sense,
                    rotations,
                    macro,
                    micro,
                    communication,
                    feedback
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.applicant_id,
                    review.reviewer_id,
                    review.vod_reference,
                    review.decision.value,
                    review.scores.aim,
                    review.scores.game_sense,
                    review.scores.rotations,
                    review.scores.macro,
                    review.scores.micro,
                    review.scores.communication,
                    review.feedback,
                ),
            )

            return cursor.lastrowid

    def get_by_id(self, review_id: int) -> VodReview | None:
        """Find a VOD review by its database ID."""
        if type(review_id) is not int or review_id <= 0:
            raise ValueError("A positive review ID is required.")

        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM vod_reviews
                WHERE review_id = ?
                """,
                (review_id,),
            ).fetchone()

        if row is None:
            return None

        return self._to_review(row)

    def get_for_applicant(
        self,
        applicant_id: str,
    ) -> tuple[VodReview, ...]:
        """Get an applicant's reviews, newest first."""
        self._validate_applicant_id(applicant_id)

        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM vod_reviews
                WHERE applicant_id = ?
                ORDER BY review_id DESC
                """,
                (applicant_id,),
            ).fetchall()

        return tuple(
            self._to_review(row)
            for row in rows
        )

    def get_latest_for_applicant(
        self,
        applicant_id: str,
    ) -> VodReview | None:
        """Retrieve the latest recorded review."""
        self._validate_applicant_id(applicant_id)

        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM vod_reviews
                WHERE applicant_id = ?
                ORDER BY review_id DESC
                LIMIT 1
                """,
                (applicant_id,),
            ).fetchone()

        if row is None:
            return None

        return self._to_review(row)

    @staticmethod
    def _validate_applicant_id(applicant_id: str) -> None:
        """Validate the applicant identifier."""
        if (
            not isinstance(applicant_id, str)
            or not applicant_id.strip()
        ):
            raise ValueError("A valid applicant ID is required.")

    @staticmethod
    def _to_review(row: sqlite3.Row) -> VodReview:
        """Convert a database row into a VodReview."""
        scores = SkillScores(
            aim=row["aim"],
            game_sense=row["game_sense"],
            rotations=row["rotations"],
            macro=row["macro"],
            micro=row["micro"],
            communication=row["communication"],
        )

        return VodReview(
            applicant_id=row["applicant_id"],
            reviewer_id=row["reviewer_id"],
            vod_reference=row["vod_reference"],
            scores=scores,
            decision=ReviewDecision(row["decision"]),
            feedback=row["feedback"],
        )
