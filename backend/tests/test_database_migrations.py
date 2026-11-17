
"""Regression tests for legacy SQLite schema migrations."""

import sqlite3
import tempfile
import unittest

from pathlib import Path
from contextlib import closing

from backend.repositories.training_progress_repository import (
    TrainingProgressRepository,
)
from backend.storage.database import Database


LEGACY_SCHEMA = """
CREATE TABLE applicants (
    applicant_id TEXT PRIMARY KEY,
    game_name TEXT NOT NULL,
    daily_play_hours REAL NOT NULL,
    peak_rank TEXT NOT NULL,
    accepts_training INTEGER NOT NULL,
    current_rank TEXT,
    preferred_role TEXT,
    vod_reference TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reviewers (
    reviewer_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE vod_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    vod_reference TEXT NOT NULL,
    decision TEXT NOT NULL,
    aim INTEGER NOT NULL,
    game_sense INTEGER NOT NULL,
    rotations INTEGER NOT NULL,
    macro INTEGER NOT NULL,
    micro INTEGER NOT NULL,
    communication INTEGER NOT NULL,
    feedback TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (applicant_id)
        REFERENCES applicants(applicant_id),
    FOREIGN KEY (reviewer_id)
        REFERENCES reviewers(reviewer_id)
);

CREATE TABLE skill_completions (
    completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id TEXT NOT NULL,
    skill TEXT NOT NULL CHECK (skill IN ('aim', 'tactics')),
    verified_by TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (applicant_id, skill),
    FOREIGN KEY (applicant_id)
        REFERENCES applicants(applicant_id),
    FOREIGN KEY (verified_by)
        REFERENCES reviewers(reviewer_id)
);

CREATE TABLE reevaluations (
    reevaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    approved INTEGER NOT NULL CHECK (approved IN (0, 1)),
    feedback TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (applicant_id)
        REFERENCES applicants(applicant_id),
    FOREIGN KEY (reviewer_id)
        REFERENCES reviewers(reviewer_id)
);

CREATE INDEX idx_skill_completions_applicant
    ON skill_completions(applicant_id);
"""


class TestDatabaseMigrations(unittest.TestCase):
    """Verify that historical records survive schema upgrades."""

    def setUp(self) -> None:
        """Create a populated database using the legacy schema."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.path = Path(temporary.name) / "legacy.sqlite3"

        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(LEGACY_SCHEMA)

            connection.execute(
                """
                INSERT INTO applicants (
                    applicant_id,
                    game_name,
                    daily_play_hours,
                    peak_rank,
                    accepts_training,
                    vod_reference
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "ASP-001",
                    "JugadorLegacy",
                    6,
                    "Diamante",
                    1,
                    "vods/first.mp4",
                ),
            )

            connection.execute(
                """
                INSERT INTO reviewers (
                    reviewer_id, display_name, is_active
                )
                VALUES (?, ?, ?)
                """,
                ("REC-001", "Reclutador", 1),
            )

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
                    "vods/first.mp4",
                    "approved",
                    4, 3, 3, 4, 4, 3,
                    "Admission approved.",
                ),
            )

            connection.executemany(
                """
                INSERT INTO skill_completions (
                    applicant_id, skill, verified_by
                )
                VALUES (?, ?, ?)
                """,
                (
                    ("ASP-001", "aim", "REC-001"),
                    ("ASP-001", "tactics", "REC-001"),
                ),
            )

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
                    "REC-001",
                    1,
                    "Historical approval.",
                ),
            )

        self.database = Database(self.path)

    def test_migration_preserves_historical_records(self):
        """Preserve existing records without granting old progress."""
        self.database.initialize()
        self.database.initialize()

        with self.database.connection() as connection:
            skill_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(skill_completions)"
                )
            }

            reevaluation_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(reevaluations)"
                )
            }

            skills = connection.execute(
                """
                SELECT completion_id, skill, vod_review_id
                FROM skill_completions
                ORDER BY completion_id
                """
            ).fetchall()

            reevaluations = connection.execute(
                """
                SELECT reevaluation_id, approved, vod_review_id
                FROM reevaluations
                """
            ).fetchall()

            violations = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

        self.assertIn("vod_review_id", skill_columns)
        self.assertIn("vod_review_id", reevaluation_columns)

        self.assertEqual(
            [tuple(row) for row in skills],
            [
                (1, "aim", None),
                (2, "tactics", None),
            ],
        )

        self.assertEqual(
            [tuple(row) for row in reevaluations],
            [(1, 1, None)],
        )

        self.assertEqual(violations, [])

        progress = TrainingProgressRepository(
            self.database
        ).get_for_applicant("ASP-001")

        self.assertEqual(
            progress.completed_skills,
            frozenset(),
        )

    def test_new_cycle_after_migration_is_independent(self):
        """Allow new skills while preserving unassigned legacy data."""
        self.database.initialize()

        with self.database.connection() as connection:
            connection.execute(
                """
                UPDATE applicants
                SET vod_reference = ?
                WHERE applicant_id = ?
                """,
                ("vods/second.mp4", "ASP-001"),
            )

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
                    "ASP-001",
                    "REC-001",
                    "vods/second.mp4",
                    "approved",
                    4, 3, 3, 4, 4, 3,
                    "Second admission.",
                ),
            )

            new_review_id = cursor.lastrowid

        repository = TrainingProgressRepository(self.database)

        self.assertEqual(
            repository.get_for_applicant(
                "ASP-001"
            ).current_node_id,
            "training_00",
        )

        repository.add_completion(
            "ASP-001", "aim", "REC-001"
        )
        repository.add_completion(
            "ASP-001", "tactics", "REC-001"
        )

        progress = repository.get_for_applicant("ASP-001")

        self.assertEqual(
            progress.current_node_id,
            "training_11",
        )

        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT vod_review_id, skill
                FROM skill_completions
                WHERE applicant_id = ?
                """,
                ("ASP-001",),
            ).fetchall()

        legacy = [
            row for row in rows
            if row["vod_review_id"] is None
        ]

        current = [
            row for row in rows
            if row["vod_review_id"] == new_review_id
        ]

        self.assertEqual(len(rows), 4)
        self.assertEqual(len(legacy), 2)
        self.assertEqual(len(current), 2)
        self.assertEqual(
            {row["skill"] for row in current},
            {"aim", "tactics"},
        )


if __name__ == "__main__":
    unittest.main()
