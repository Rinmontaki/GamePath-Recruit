
"""Configure SQLite persistence for GamePath Recruit."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS applicants (
    applicant_id TEXT PRIMARY KEY,
    game_name TEXT NOT NULL,
    daily_play_hours REAL NOT NULL
        CHECK (daily_play_hours BETWEEN 0 AND 24),
    peak_rank TEXT NOT NULL,
    accepts_training INTEGER NOT NULL
        CHECK (accepts_training IN (0, 1)),
    current_rank TEXT,
    preferred_role TEXT,
    vod_reference TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reviewers (
    reviewer_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS vod_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    vod_reference TEXT NOT NULL,
    decision TEXT NOT NULL
        CHECK (
            decision IN (
                'approved',
                'more_evidence',
                'rejected'
            )
        ),
    aim INTEGER NOT NULL CHECK (aim BETWEEN 1 AND 5),
    game_sense INTEGER NOT NULL
        CHECK (game_sense BETWEEN 1 AND 5),
    rotations INTEGER NOT NULL
        CHECK (rotations BETWEEN 1 AND 5),
    macro INTEGER NOT NULL CHECK (macro BETWEEN 1 AND 5),
    micro INTEGER NOT NULL CHECK (micro BETWEEN 1 AND 5),
    communication INTEGER NOT NULL
        CHECK (communication BETWEEN 1 AND 5),
    feedback TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (applicant_id)
        REFERENCES applicants(applicant_id),
    FOREIGN KEY (reviewer_id)
        REFERENCES reviewers(reviewer_id)
);


CREATE TABLE IF NOT EXISTS skill_completions (
    completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id TEXT NOT NULL,
    skill TEXT NOT NULL
        CHECK (skill IN ('aim', 'tactics')),
    verified_by TEXT NOT NULL,
    vod_review_id INTEGER
        REFERENCES vod_reviews(review_id),
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (applicant_id, vod_review_id, skill),
    FOREIGN KEY (applicant_id)
        REFERENCES applicants(applicant_id),
    FOREIGN KEY (verified_by)
        REFERENCES reviewers(reviewer_id)
);


CREATE TABLE IF NOT EXISTS reevaluations (
    reevaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    vod_review_id INTEGER
        REFERENCES vod_reviews(review_id),
    approved INTEGER NOT NULL CHECK (approved IN (0, 1)),
    feedback TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (applicant_id)
        REFERENCES applicants(applicant_id),
    FOREIGN KEY (reviewer_id)
        REFERENCES reviewers(reviewer_id)
);

CREATE INDEX IF NOT EXISTS idx_vod_reviews_applicant
    ON vod_reviews(applicant_id);

CREATE INDEX IF NOT EXISTS idx_skill_completions_applicant
    ON skill_completions(applicant_id);

CREATE INDEX IF NOT EXISTS idx_reevaluations_applicant
    ON reevaluations(applicant_id);
"""


class Database:
    """Manage SQLite connections and initial schema."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Open, commit or roll back, and close a connection."""
        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    
    
    def initialize(self) -> None:
        """Initialize and migrate existing SQLite tables."""
        with self.connection() as connection:
            connection.executescript(SCHEMA)
            connection.execute("BEGIN IMMEDIATE")

            skill_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(skill_completions)"
                ).fetchall()
            }

            if "vod_review_id" not in skill_columns:
                connection.execute(
                    """
                    CREATE TABLE skill_completions_v2 (
                        completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        applicant_id TEXT NOT NULL,
                        skill TEXT NOT NULL
                            CHECK (skill IN ('aim', 'tactics')),
                        verified_by TEXT NOT NULL,
                        vod_review_id INTEGER
                            REFERENCES vod_reviews(review_id),
                        completed_at TEXT NOT NULL
                            DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (
                            applicant_id,
                            vod_review_id,
                            skill
                        ),
                        FOREIGN KEY (applicant_id)
                            REFERENCES applicants(applicant_id),
                        FOREIGN KEY (verified_by)
                            REFERENCES reviewers(reviewer_id)
                    )
                    """
                )

                connection.execute(
                    """
                    INSERT INTO skill_completions_v2 (
                        completion_id,
                        applicant_id,
                        skill,
                        verified_by,
                        completed_at
                    )
                    SELECT
                        completion_id,
                        applicant_id,
                        skill,
                        verified_by,
                        completed_at
                    FROM skill_completions
                    """
                )

                connection.execute(
                    "DROP TABLE skill_completions"
                )

                connection.execute(
                    """
                    ALTER TABLE skill_completions_v2
                    RENAME TO skill_completions
                    """
                )

            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                    idx_skill_completions_legacy_unique
                ON skill_completions (applicant_id, skill)
                WHERE vod_review_id IS NULL
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_skill_completions_applicant
                ON skill_completions (applicant_id)
                """
            )

            reevaluation_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(reevaluations)"
                ).fetchall()
            }

            if "vod_review_id" not in reevaluation_columns:
                connection.execute(
                    """
                    ALTER TABLE reevaluations
                    ADD COLUMN vod_review_id INTEGER
                    REFERENCES vod_reviews(review_id)
                    """
                )
