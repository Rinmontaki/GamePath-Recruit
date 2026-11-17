
"""Unit tests for SQLite applicant persistence."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.models.applicant import Applicant
from backend.repositories.applicant_repository import (
    ApplicantRepository,
)
from backend.storage.database import Database


def make_applicant(**changes) -> Applicant:
    """Create a valid applicant with optional overrides."""
    data = {
        "applicant_id": "ASP-001",
        "game_name": "JugadorDemo",
        "daily_play_hours": 6,
        "peak_rank": "Diamante",
        "accepts_training": True,
        "current_rank": "Platino",
        "preferred_role": "Duelista",
        "vod_reference": "vods/demo.mp4",
    }

    data.update(changes)
    return Applicant(**data)


class TestApplicantRepository(unittest.TestCase):
    """Verify applicant storage and retrieval."""

    def setUp(self) -> None:
        """Prepare an isolated SQLite database."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.db_path = (
            Path(temporary.name)
            / "gamepath_test.sqlite3"
        )

        self.database = Database(self.db_path)
        self.database.initialize()

        self.repository = ApplicantRepository(
            self.database
        )

    def test_empty_repository(self):
        """Return an empty collection before insertion."""
        result = self.repository.get_all()

        self.assertEqual(result, ())
        self.assertIsInstance(result, tuple)

    def test_save_and_retrieve_applicant(self):
        """Preserve all applicant fields."""
        applicant = make_applicant()

        self.repository.add(applicant)

        recovered = self.repository.get_by_id("ASP-001")

        self.assertEqual(recovered, applicant)
        self.assertIsInstance(recovered, Applicant)

    def test_optional_fields_can_be_null(self):
        """Preserve absent optional profile fields."""
        applicant = make_applicant(
            current_rank=None,
            preferred_role=None,
            vod_reference=None,
        )

        self.repository.add(applicant)

        recovered = self.repository.get_by_id("ASP-001")

        self.assertEqual(recovered, applicant)
        self.assertIsNone(recovered.vod_reference)

    def test_false_training_commitment(self):
        """Preserve a False boolean after database storage."""
        applicant = make_applicant(
            accepts_training=False
        )

        self.repository.add(applicant)

        recovered = self.repository.get_by_id("ASP-001")

        self.assertIs(recovered.accepts_training, False)

    def test_get_all_is_ordered(self):
        """Retrieve applicants ordered by their IDs."""
        for applicant_id in ("ASP-003", "ASP-001", "ASP-002"):
            self.repository.add(
                make_applicant(applicant_id=applicant_id)
            )

        applicants = self.repository.get_all()

        self.assertEqual(
            tuple(item.applicant_id for item in applicants),
            ("ASP-001", "ASP-002", "ASP-003"),
        )

    def test_missing_applicant(self):
        """Return None when the identifier is unknown."""
        result = self.repository.get_by_id("ASP-999")

        self.assertIsNone(result)

    def test_duplicate_applicant_is_rejected(self):
        """Reject duplicates without replacing existing data."""
        original = make_applicant()
        duplicate = make_applicant(
            game_name="OtroJugador"
        )

        self.repository.add(original)

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.add(duplicate)

        self.assertEqual(
            self.repository.get_by_id("ASP-001"),
            original,
        )
        self.assertEqual(len(self.repository.get_all()), 1)

    def test_add_requires_applicant(self):
        """Reject dictionaries and unrelated objects."""
        invalid_values = (
            None,
            {"applicant_id": "ASP-001"},
            "ASP-001",
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.repository.add(value)

    def test_invalid_lookup_identifier(self):
        """Reject invalid applicant lookup IDs."""
        invalid_ids = (
            "",
            "   ",
            None,
            123,
        )

        for applicant_id in invalid_ids:
            with self.subTest(applicant_id=applicant_id):
                with self.assertRaises(ValueError):
                    self.repository.get_by_id(applicant_id)

    def test_applicants_remain_independent(self):
        """Store separate profiles without mixing their data."""
        first = make_applicant()

        second = make_applicant(
            applicant_id="ASP-002",
            game_name="JugadorCasual",
            daily_play_hours=3,
            peak_rank="Oro",
            vod_reference=None,
        )

        self.repository.add(first)
        self.repository.add(second)

        self.assertEqual(
            self.repository.get_by_id("ASP-001"),
            first,
        )
        self.assertEqual(
            self.repository.get_by_id("ASP-002"),
            second,
        )

    def test_data_survives_repository_recreation(self):
        """Retrieve stored data using a new repository instance."""
        applicant = make_applicant()

        self.repository.add(applicant)

        new_database = Database(self.db_path)
        new_repository = ApplicantRepository(new_database)

        recovered = new_repository.get_by_id("ASP-001")

        self.assertEqual(recovered, applicant)

    def test_lookup_uses_sql_parameters(self):
        """Treat SQL-looking input as a literal identifier."""
        self.repository.add(make_applicant())

        malicious_id = "ASP-001' OR '1'='1"

        result = self.repository.get_by_id(malicious_id)

        self.assertIsNone(result)
        self.assertEqual(len(self.repository.get_all()), 1)


if __name__ == "__main__":
    unittest.main()
