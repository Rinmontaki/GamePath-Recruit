
"""Persist training progress by VOD admission cycle."""

from backend.models.training_progress import (
    SUPPORTED_SKILLS,
    TrainingProgress,
)
from backend.storage.database import Database


class TrainingProgressRepository:
    """Manage completed skills for each VOD review cycle."""

    def __init__(self, database: Database) -> None:
        """Receive the application's database."""
        if not isinstance(database, Database):
            raise TypeError("A Database instance is required.")

        self._database = database

    def add_completion(
        self,
        applicant_id: str,
        skill: str,
        verified_by: str,
    ) -> None:
        """Store a skill for the current VOD review cycle."""
        self._validate_identifier(applicant_id, "Applicant ID")
        self._validate_identifier(verified_by, "Reviewer ID")

        if not isinstance(skill, str) or skill not in SUPPORTED_SKILLS:
            raise ValueError("Unsupported training skill.")

        with self._database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            reviewer = connection.execute(
                """
                SELECT is_active
                FROM reviewers
                WHERE reviewer_id = ?
                """,
                (verified_by,),
            ).fetchone()

            if reviewer is None or reviewer["is_active"] != 1:
                raise PermissionError(
                    "An active reviewer is required."
                )

            vod_review_id = self._latest_review_id(
                connection,
                applicant_id,
            )

            connection.execute(
                """
                INSERT INTO skill_completions (
                    applicant_id,
                    skill,
                    verified_by,
                    vod_review_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    applicant_id,
                    skill,
                    verified_by,
                    vod_review_id,
                ),
            )

    def get_for_applicant(
        self,
        applicant_id: str,
    ) -> TrainingProgress | None:
        """Read progress belonging to the latest VOD cycle."""
        self._validate_identifier(applicant_id, "Applicant ID")

        with self._database.connection() as connection:
            applicant = connection.execute(
                """
                SELECT 1
                FROM applicants
                WHERE applicant_id = ?
                """,
                (applicant_id,),
            ).fetchone()

            if applicant is None:
                return None

            vod_review_id = self._latest_review_id(
                connection,
                applicant_id,
            )

            if vod_review_id is None:
                rows = connection.execute(
                    """
                    SELECT skill
                    FROM skill_completions
                    WHERE applicant_id = ?
                      AND vod_review_id IS NULL
                    ORDER BY skill
                    """,
                    (applicant_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT skill
                    FROM skill_completions
                    WHERE applicant_id = ?
                      AND vod_review_id = ?
                    ORDER BY skill
                    """,
                    (applicant_id, vod_review_id),
                ).fetchall()

        return TrainingProgress(
            applicant_id=applicant_id,
            completed_skills=frozenset(
                row["skill"] for row in rows
            ),
        )

    @staticmethod
    def _latest_review_id(connection, applicant_id: str) -> int | None:
        """Find the latest recorded review for an applicant."""
        row = connection.execute(
            """
            SELECT review_id
            FROM vod_reviews
            WHERE applicant_id = ?
            ORDER BY review_id DESC
            LIMIT 1
            """,
            (applicant_id,),
        ).fetchone()

        return None if row is None else row["review_id"]

    @staticmethod
    def _validate_identifier(
        value: str,
        field_name: str,
    ) -> None:
        """Reject empty or incorrectly typed identifiers."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{field_name} must be a non-empty string."
            )
