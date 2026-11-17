
"""Unit tests for GamePath Recruit SQLite persistence."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.storage.database import Database


class TestDatabase(unittest.TestCase):
    """Verify database schema, constraints, and transactions."""

    def setUp(self) -> None:
        """Create an isolated database for each test."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.path = (
            Path(temporary.name)
            / "data"
            / "gamepath.sqlite3"
        )

        self.database = Database(self.path)
        self.database.initialize()

    @staticmethod
    def insert_applicant(
        connection,
        applicant_id="ASP-001",
        hours=6,
    ) -> None:
        """Insert a sample applicant."""
        connection.execute(
            """
            INSERT INTO applicants (
                applicant_id,
                game_name,
                daily_play_hours,
                peak_rank,
                accepts_training
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                applicant_id,
                "JugadorDemo",
                hours,
                "Diamante",
                1,
            ),
        )

    @staticmethod
    def insert_reviewer(
        connection,
        reviewer_id="REC-001",
    ) -> None:
        """Insert a sample reviewer."""
        connection.execute(
            """
            INSERT INTO reviewers (
                reviewer_id,
                display_name
            )
            VALUES (?, ?)
            """,
            (reviewer_id, "ReclutadorDemo"),
        )

    @staticmethod
    def insert_review(
        connection,
        decision="approved",
        aim=4,
    ) -> None:
        """Insert a sample VOD review."""
        connection.execute(
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
                "ASP-001",
                "REC-001",
                "vods/demo.mp4",
                decision,
                aim,
                3,
                2,
                3,
                4,
                3,
                "Evaluacion completada.",
            ),
        )

    def test_creates_expected_tables(self):
        """Create all five application tables."""
        expected = {
            "applicants",
            "reviewers",
            "vod_reviews",
            "skill_completions",
            "reevaluations",
        }

        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()

        self.assertEqual(
            {row["name"] for row in rows},
            expected,
        )

    def test_initialization_is_idempotent(self):
        """Allow repeated initialization."""
        self.database.initialize()
        self.database.initialize()

        with self.database.connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                """
            ).fetchone()["total"]

        self.assertEqual(count, 5)

    def test_creates_database_directory(self):
        """Create the database directory automatically."""
        self.assertTrue(self.path.parent.is_dir())
        self.assertTrue(self.path.is_file())

    def test_foreign_keys_are_enabled(self):
        """Enable SQLite foreign-key checks."""
        with self.database.connection() as connection:
            enabled = connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]

        self.assertEqual(enabled, 1)

    def test_row_factory_supports_column_names(self):
        """Read SQL results using column names."""
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT 42 AS result"
            ).fetchone()

        self.assertIsInstance(row, sqlite3.Row)
        self.assertEqual(row["result"], 42)

    def test_transaction_commits_changes(self):
        """Persist data after a successful transaction."""
        with self.database.connection() as connection:
            self.insert_applicant(connection)

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT game_name
                FROM applicants
                WHERE applicant_id = ?
                """,
                ("ASP-001",),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["game_name"], "JugadorDemo")

    def test_transaction_rolls_back_on_error(self):
        """Discard changes when a transaction fails."""
        with self.assertRaises(RuntimeError):
            with self.database.connection() as connection:
                self.insert_applicant(connection)
                raise RuntimeError("Simulated failure")

        with self.database.connection() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM applicants"
            ).fetchone()[0]

        self.assertEqual(count, 0)

    def test_rejects_invalid_play_hours(self):
        """Reject hours outside the database range."""
        for hours in (-1, 25):
            with self.subTest(hours=hours):
                with self.assertRaises(sqlite3.IntegrityError):
                    with self.database.connection() as connection:
                        self.insert_applicant(
                            connection,
                            applicant_id=f"ASP-{hours}",
                            hours=hours,
                        )

    def test_vod_review_requires_existing_references(self):
        """Reject reviews without registered entities."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.database.connection() as connection:
                self.insert_review(connection)

    def test_rejects_invalid_vod_review_values(self):
        """Validate review decisions and skill scores."""
        with self.database.connection() as connection:
            self.insert_applicant(connection)
            self.insert_reviewer(connection)

        invalid_cases = (
            ("invalid_decision", 4),
            ("approved", 0),
            ("approved", 6),
        )

        for decision, aim in invalid_cases:
            with self.subTest(decision=decision, aim=aim):
                with self.assertRaises(sqlite3.IntegrityError):
                    with self.database.connection() as connection:
                        self.insert_review(
                            connection,
                            decision=decision,
                            aim=aim,
                        )

    def test_skill_completion_constraints(self):
        """Reject duplicate or unsupported skill records."""
        with self.database.connection() as connection:
            self.insert_applicant(connection)
            self.insert_reviewer(connection)

            connection.execute(
                """
                INSERT INTO skill_completions (
                    applicant_id,
                    skill,
                    verified_by
                )
                VALUES (?, ?, ?)
                """,
                ("ASP-001", "aim", "REC-001"),
            )

        for skill in ("aim", "rotations"):
            with self.subTest(skill=skill):
                with self.assertRaises(sqlite3.IntegrityError):
                    with self.database.connection() as connection:
                        connection.execute(
                            """
                            INSERT INTO skill_completions (
                                applicant_id,
                                skill,
                                verified_by
                            )
                            VALUES (?, ?, ?)
                            """,
                            ("ASP-001", skill, "REC-001"),
                        )

        with self.database.connection() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM skill_completions"
            ).fetchone()[0]

        self.assertEqual(count, 1)

    def test_reevaluation_constraints(self):
        """Validate reviewer references and approval values."""
        with self.database.connection() as connection:
            self.insert_applicant(connection)
            self.insert_reviewer(connection)

        invalid_cases = (
            ("REC-999", 1),
            ("REC-001", 2),
        )

        for reviewer_id, approved in invalid_cases:
            with self.subTest(
                reviewer_id=reviewer_id,
                approved=approved,
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    with self.database.connection() as connection:
                        connection.execute(
                            """
                            INSERT INTO reevaluations (
                                applicant_id,
                                reviewer_id,
                                approved,
                                feedback
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                "ASP-001",
                                reviewer_id,
                                approved,
                                "Evaluacion de prueba.",
                            ),
                        )


if __name__ == "__main__":
    unittest.main()
