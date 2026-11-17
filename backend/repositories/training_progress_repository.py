
"""Persist individual training progress in GamePath Recruit."""

from backend.models.training_progress import (
    SUPPORTED_SKILLS,
    TrainingProgress,
)
from backend.storage.database import Database


class TrainingProgressRepository:
    """Manage completed training skills stored in SQLite."""

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
        """Store a skill completion attributed to a reviewer."""
        self._validate_identifier(applicant_id, "Applicant ID")
        self._validate_identifier(verified_by, "Reviewer ID")

        if not isinstance(skill, str) or skill not in SUPPORTED_SKILLS:
            raise ValueError("Unsupported training skill.")

        with self._database.connection() as connection:
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

            connection.execute(
                """
                INSERT INTO skill_completions (
                    applicant_id,
                    skill,
                    verified_by
                )
                VALUES (?, ?, ?)
                """,
                (
                    applicant_id,
                    skill,
                    verified_by,
                ),
            )

    def get_for_applicant(
        self,
        applicant_id: str,
    ) -> TrainingProgress | None:
        """Rebuild an applicant's progress from stored records."""
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

            rows = connection.execute(
                """
                SELECT skill
                FROM skill_completions
                WHERE applicant_id = ?
                ORDER BY skill
                """,
                (applicant_id,),
            ).fetchall()

        completed_skills = frozenset(
            row["skill"] for row in rows
        )

        return TrainingProgress(
            applicant_id=applicant_id,
            completed_skills=completed_skills,
        )

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
