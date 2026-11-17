
"""Persist and retrieve GamePath Recruit applicants."""

import sqlite3

from backend.models.applicant import Applicant
from backend.storage.database import Database


class ApplicantRepository:
    """Manage applicant records stored in SQLite."""

    def __init__(self, database: Database) -> None:
        """Receive the application's database."""
        if not isinstance(database, Database):
            raise TypeError("A Database instance is required.")

        self._database = database

    def add(self, applicant: Applicant) -> None:
        """Save a new applicant in the database."""
        if not isinstance(applicant, Applicant):
            raise TypeError("An Applicant instance is required.")

        with self._database.connection() as connection:
            connection.execute(
                """
                INSERT INTO applicants (
                    applicant_id,
                    game_name,
                    daily_play_hours,
                    peak_rank,
                    accepts_training,
                    current_rank,
                    preferred_role,
                    vod_reference
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    applicant.applicant_id,
                    applicant.game_name,
                    applicant.daily_play_hours,
                    applicant.peak_rank,
                    int(applicant.accepts_training),
                    applicant.current_rank,
                    applicant.preferred_role,
                    applicant.vod_reference,
                ),
            )

    def get_by_id(self, applicant_id: str) -> Applicant | None:
        """Retrieve an applicant using their unique ID."""
        if (
            not isinstance(applicant_id, str)
            or not applicant_id.strip()
        ):
            raise ValueError("A valid applicant ID is required.")

        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    applicant_id,
                    game_name,
                    daily_play_hours,
                    peak_rank,
                    accepts_training,
                    current_rank,
                    preferred_role,
                    vod_reference
                FROM applicants
                WHERE applicant_id = ?
                """,
                (applicant_id,),
            ).fetchone()

        if row is None:
            return None

        return self._to_applicant(row)

    def get_all(self) -> tuple[Applicant, ...]:
        """Retrieve all applicants ordered by identifier."""
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    applicant_id,
                    game_name,
                    daily_play_hours,
                    peak_rank,
                    accepts_training,
                    current_rank,
                    preferred_role,
                    vod_reference
                FROM applicants
                ORDER BY applicant_id
                """
            ).fetchall()

        return tuple(
            self._to_applicant(row)
            for row in rows
        )

    @staticmethod
    def _to_applicant(row: sqlite3.Row) -> Applicant:
        """Convert a database row into an Applicant."""
        return Applicant(
            applicant_id=row["applicant_id"],
            game_name=row["game_name"],
            daily_play_hours=row["daily_play_hours"],
            peak_rank=row["peak_rank"],
            accepts_training=bool(row["accepts_training"]),
            current_rank=row["current_rank"],
            preferred_role=row["preferred_role"],
            vod_reference=row["vod_reference"],
        )
