
"""Unit tests for SQLite training progress persistence."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.models.applicant import Applicant
from backend.repositories.applicant_repository import (
    ApplicantRepository,
)
from backend.repositories.training_progress_repository import (
    TrainingProgressRepository,
)
from backend.storage.database import Database


class TestTrainingProgressRepository(unittest.TestCase):
    """Verify persistent and independent training progress."""

    def setUp(self) -> None:
        """Create an isolated database for every test."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.db_path = (
            Path(temporary.name) / "gamepath_test.sqlite3"
        )

        self.database = Database(self.db_path)
        self.database.initialize()

        applicants = ApplicantRepository(self.database)

        for applicant_id in ("ASP-001", "ASP-002"):
            applicants.add(
                Applicant(
                    applicant_id=applicant_id,
                    game_name=f"Jugador-{applicant_id}",
                    daily_play_hours=6,
                    peak_rank="Diamante",
                    accepts_training=True,
                )
            )

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO reviewers (
                    reviewer_id,
                    display_name,
                    is_active
                )
                VALUES (?, ?, ?)
                """,
                ("REC-001", "ReclutadorActivo", 1),
            )

            connection.execute(
                """
                INSERT INTO reviewers (
                    reviewer_id,
                    display_name,
                    is_active
                )
                VALUES (?, ?, ?)
                """,
                ("REC-002", "ReclutadorInactivo", 0),
            )

        self.repository = TrainingProgressRepository(
            self.database
        )

    def complete(
        self,
        skill: str,
        applicant_id: str = "ASP-001",
        reviewer_id: str = "REC-001",
    ) -> None:
        """Store a skill completion using test defaults."""
        self.repository.add_completion(
            applicant_id=applicant_id,
            skill=skill,
            verified_by=reviewer_id,
        )

    def test_initial_progress(self):
        """Existing applicants begin without completed skills."""
        progress = self.repository.get_for_applicant(
            "ASP-001"
        )

        self.assertEqual(
            progress.current_node_id,
            "training_00",
        )
        self.assertEqual(progress.completed_skills, frozenset())
        self.assertFalse(progress.is_training_complete)

    def test_complete_aim(self):
        """Completing aim produces training_10."""
        self.complete("aim")

        progress = self.repository.get_for_applicant(
            "ASP-001"
        )

        self.assertEqual(progress.current_node_id, "training_10")
        self.assertEqual(
            progress.pending_skills,
            frozenset({"tactics"}),
        )

    def test_complete_tactics(self):
        """Completing tactics produces training_01."""
        self.complete("tactics")

        progress = self.repository.get_for_applicant(
            "ASP-001"
        )

        self.assertEqual(progress.current_node_id, "training_01")
        self.assertEqual(
            progress.pending_skills,
            frozenset({"aim"}),
        )

    def test_complete_both_skills(self):
        """Completing both skills produces training_11."""
        self.complete("aim")
        self.complete("tactics")

        progress = self.repository.get_for_applicant(
            "ASP-001"
        )

        self.assertEqual(progress.current_node_id, "training_11")
        self.assertTrue(progress.is_training_complete)
        self.assertEqual(progress.pending_skills, frozenset())

    def test_applicant_progress_is_independent(self):
        """Never mix completed skills between applicants."""
        self.complete("aim", applicant_id="ASP-001")
        self.complete("tactics", applicant_id="ASP-002")

        first = self.repository.get_for_applicant("ASP-001")
        second = self.repository.get_for_applicant("ASP-002")

        self.assertEqual(first.current_node_id, "training_10")
        self.assertEqual(second.current_node_id, "training_01")

    def test_unknown_applicant_returns_none(self):
        """Return None if the applicant does not exist."""
        progress = self.repository.get_for_applicant(
            "ASP-999"
        )

        self.assertIsNone(progress)

    def test_completion_requires_existing_applicant(self):
        """Reject completions for unknown applicants."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.complete(
                "aim",
                applicant_id="ASP-999",
            )

    def test_unknown_reviewer_is_blocked(self):
        """An unregistered reviewer cannot record progress."""
        with self.assertRaises(PermissionError):
            self.complete(
                "aim",
                reviewer_id="REC-999",
            )

        progress = self.repository.get_for_applicant(
            "ASP-001"
        )
        self.assertEqual(progress.current_node_id, "training_00")

    def test_inactive_reviewer_is_blocked(self):
        """An inactive reviewer cannot complete a pending skill."""
        with self.assertRaises(PermissionError):
            self.complete(
                "aim",
                reviewer_id="REC-002",
            )

        progress = self.repository.get_for_applicant(
            "ASP-001"
        )
        self.assertEqual(progress.current_node_id, "training_00")

    def test_duplicate_completion_is_rejected(self):
        """Reject duplicate completions without changing progress."""
        self.complete("aim")

        with self.assertRaises(sqlite3.IntegrityError):
            self.complete("aim")

        with self.database.connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM skill_completions
                WHERE applicant_id = ?
                """,
                ("ASP-001",),
            ).fetchone()[0]

        self.assertEqual(count, 1)

    def test_invalid_skills_are_rejected(self):
        """Reject unsupported or incorrectly typed skills."""
        invalid_skills = (
            "",
            "AIM",
            "aim ",
            "rotations",
            None,
            123,
        )

        for skill in invalid_skills:
            with self.subTest(skill=skill):
                with self.assertRaises(ValueError):
                    self.complete(skill)

    def test_invalid_applicant_id_on_completion(self):
        """Require a valid applicant identifier."""
        for applicant_id in ("", "   ", None, 123):
            with self.subTest(applicant_id=applicant_id):
                with self.assertRaises(ValueError):
                    self.complete(
                        "aim",
                        applicant_id=applicant_id,
                    )

    def test_invalid_reviewer_id_on_completion(self):
        """Require a valid reviewer identifier."""
        for reviewer_id in ("", "   ", None, 123):
            with self.subTest(reviewer_id=reviewer_id):
                with self.assertRaises(ValueError):
                    self.complete(
                        "aim",
                        reviewer_id=reviewer_id,
                    )

    def test_invalid_lookup_id(self):
        """Reject invalid identifiers in progress queries."""
        for applicant_id in ("", "   ", None, 123):
            with self.subTest(applicant_id=applicant_id):
                with self.assertRaises(ValueError):
                    self.repository.get_for_applicant(
                        applicant_id
                    )

    def test_progress_survives_repository_recreation(self):
        """Recover saved progress using a new repository."""
        self.complete("aim")

        another_repository = TrainingProgressRepository(
            Database(self.db_path)
        )

        progress = another_repository.get_for_applicant(
            "ASP-001"
        )

        self.assertEqual(progress.current_node_id, "training_10")
        self.assertEqual(
            progress.completed_skills,
            frozenset({"aim"}),
        )

    def test_completion_stores_reviewer_identity(self):
        """Preserve the reviewer ID and skill in SQLite."""
        self.complete("tactics")

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT skill, verified_by
                FROM skill_completions
                WHERE applicant_id = ?
                """,
                ("ASP-001",),
            ).fetchone()

        self.assertEqual(row["skill"], "tactics")
        self.assertEqual(row["verified_by"], "REC-001")

    def test_repository_requires_database(self):
        """Reject invalid database dependencies."""
        with self.assertRaises(TypeError):
            TrainingProgressRepository(None)


if __name__ == "__main__":
    unittest.main()
