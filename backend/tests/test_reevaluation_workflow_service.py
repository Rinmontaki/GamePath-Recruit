
"""Unit tests for human reevaluation workflows."""

import tempfile
import unittest
from pathlib import Path

from backend.loaders.graph_loader import load_graph
from backend.loaders.tree_loader import load_tree
from backend.models.applicant import Applicant
from backend.models.vod_review import (
    ReviewDecision,
    SkillScores,
    VodReview,
)
from backend.repositories.applicant_repository import (
    ApplicantRepository,
)
from backend.repositories.vod_review_repository import (
    VodReviewRepository,
)
from backend.services.recruitment_service import RecruitmentService
from backend.services.reevaluation_workflow_service import (
    ReevaluationWorkflowService,
)
from backend.services.review_workflow_service import (
    ReviewWorkflowService,
)
from backend.services.training_completion_workflow_service import (
    TrainingCompletionWorkflowService,
)
from backend.services.training_service import TrainingService
from backend.services.training_workflow_service import (
    TrainingWorkflowService,
)
from backend.services.vod_review_service import VodReviewService
from backend.storage.database import Database
from backend.structures.binary_tree import BinaryDecisionTree


class TestReevaluationWorkflowService(unittest.TestCase):
    """Verify reevaluation authorization and persistence."""

    def setUp(self) -> None:
        """Prepare an isolated recruitment environment."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.db_path = Path(temporary.name) / "gamepath_test.sqlite3"
        self.database = Database(self.db_path)
        self.database.initialize()

        applicants = ApplicantRepository(self.database)

        self.vod_paths = {
            "ASP-001": "vods/first.mp4",
            "ASP-002": "vods/second.mp4",
        }

        for applicant_id, vod in self.vod_paths.items():
            applicants.add(
                Applicant(
                    applicant_id=applicant_id,
                    game_name=f"Jugador-{applicant_id}",
                    daily_play_hours=6,
                    peak_rank="Diamante",
                    accepts_training=True,
                    vod_reference=vod,
                )
            )

        with self.database.connection() as connection:
            connection.executemany(
                """
                INSERT INTO reviewers (
                    reviewer_id,
                    display_name,
                    is_active
                )
                VALUES (?, ?, ?)
                """,
                (
                    ("REC-001", "Autorizado", 1),
                    ("REC-002", "SinPermiso", 1),
                    ("REC-003", "Inactivo", 0),
                ),
            )

        authorized = {
            "REC-001",
            "REC-003",
            "REC-999",
        }

        data_dir = Path(__file__).resolve().parents[1] / "data"

        tree = BinaryDecisionTree(
            load_tree(data_dir / "profile_tree.json")
        )
        recruitment = RecruitmentService(tree)

        review_service = VodReviewService(
            recruitment_service=recruitment,
            authorized_reviewer_ids=authorized,
        )

        self.review_workflow = ReviewWorkflowService(
            self.database,
            review_service,
        )

        training_service = TrainingService(
            graph=load_graph(data_dir / "training_graph.json"),
            review_service=review_service,
        )

        self.training_workflow = TrainingWorkflowService(
            self.database,
            training_service,
        )

        self.completion_workflow = TrainingCompletionWorkflowService(
            self.database,
            self.training_workflow,
            authorized,
        )

        self.workflow = ReevaluationWorkflowService(
            self.database,
            self.training_workflow,
            authorized,
        )

        self.reviews = VodReviewRepository(self.database)

        self.scores = SkillScores(
            aim=4,
            game_sense=3,
            rotations=3,
            macro=4,
            micro=4,
            communication=3,
        )

    def make_review(
        self,
        applicant_id="ASP-001",
        decision=ReviewDecision.APPROVED,
        vod_reference=None,
    ) -> VodReview:
        """Build a review for an existing applicant."""
        if vod_reference is None:
            vod_reference = self.vod_paths[applicant_id]

        return VodReview(
            applicant_id=applicant_id,
            reviewer_id="REC-001",
            vod_reference=vod_reference,
            scores=self.scores,
            decision=decision,
            feedback="Evaluacion humana del aspirante.",
        )

    def admit(self, applicant_id="ASP-001") -> None:
        """Persist a valid admission."""
        self.review_workflow.record_review(
            self.make_review(applicant_id=applicant_id),
            authenticated_reviewer_id="REC-001",
        )

    def complete_training(
        self,
        applicant_id="ASP-001",
        skills=("aim", "tactics"),
    ) -> None:
        """Record selected training skills."""
        for skill in skills:
            self.completion_workflow.record_completion(
                applicant_id,
                skill,
                authenticated_reviewer_id="REC-001",
            )

    def prepare(self, applicant_id="ASP-001") -> None:
        """Admit an applicant and complete training."""
        self.admit(applicant_id)
        self.complete_training(applicant_id)

    def record(
        self,
        approved=True,
        applicant_id="ASP-001",
        reviewer_id="REC-001",
        feedback="Reevaluacion completada.",
    ) -> int:
        """Persist a human reevaluation."""
        return self.workflow.record_reevaluation(
            applicant_id,
            approved=approved,
            feedback=feedback,
            authenticated_reviewer_id=reviewer_id,
        )

    def history(self, applicant_id="ASP-001"):
        """Retrieve reevaluations in descending ID order."""
        with self.database.connection() as connection:
            return connection.execute(
                """
                SELECT *
                FROM reevaluations
                WHERE applicant_id = ?
                ORDER BY reevaluation_id DESC
                """,
                (applicant_id,),
            ).fetchall()

    def test_without_admission_is_blocked(self):
        """Require an approved VOD before reevaluation."""
        with self.assertRaises(PermissionError):
            self.record()

        self.assertEqual(len(self.history()), 0)

    def test_training_not_started_is_blocked(self):
        """An admitted applicant must still finish training."""
        self.admit()

        with self.assertRaises(PermissionError):
            self.record()

        self.assertEqual(len(self.history()), 0)

    def test_only_aim_is_insufficient(self):
        """Block reevaluation after completing only aim."""
        self.admit()
        self.complete_training(skills=("aim",))

        with self.assertRaises(PermissionError):
            self.record()

    def test_only_tactics_is_insufficient(self):
        """Block reevaluation after completing only tactics."""
        self.admit()
        self.complete_training(skills=("tactics",))

        with self.assertRaises(PermissionError):
            self.record()

    def test_approved_reevaluation_is_persisted(self):
        """Save an explicit human approval."""
        self.prepare()

        review_id = self.record(
            approved=True,
            feedback="Cumple los criterios.",
        )

        rows = self.history()

        self.assertEqual(review_id, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["approved"], 1)
        self.assertEqual(rows[0]["reviewer_id"], "REC-001")
        self.assertEqual(
            rows[0]["feedback"],
            "Cumple los criterios.",
        )

    def test_rejected_reevaluation_is_persisted(self):
        """Save a human rejection without granting approval."""
        self.prepare()

        review_id = self.record(
            approved=False,
            feedback="Debe mejorar comunicacion.",
        )

        rows = self.history()

        self.assertEqual(review_id, 1)
        self.assertEqual(rows[0]["approved"], 0)

    def test_multiple_decisions_preserve_history(self):
        """Keep prior decisions after a new reevaluation."""
        self.prepare()

        first_id = self.record(
            approved=False,
            feedback="Primera revision.",
        )
        second_id = self.record(
            approved=True,
            feedback="Segunda revision.",
        )

        rows = self.history()

        self.assertLess(first_id, second_id)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["approved"], 1)
        self.assertEqual(rows[1]["approved"], 0)

    def test_applicant_histories_are_independent(self):
        """Never mix reevaluations from different applicants."""
        self.prepare("ASP-001")
        self.prepare("ASP-002")

        self.record(
            approved=True,
            applicant_id="ASP-001",
        )
        self.record(
            approved=False,
            applicant_id="ASP-002",
        )

        first = self.history("ASP-001")
        second = self.history("ASP-002")

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0]["approved"], 1)
        self.assertEqual(second[0]["approved"], 0)

    def test_unauthorized_reviewer_is_blocked(self):
        """An active reviewer still needs authorization."""
        self.prepare()

        with self.assertRaises(PermissionError):
            self.record(reviewer_id="REC-002")

        self.assertEqual(len(self.history()), 0)

    def test_inactive_reviewer_is_blocked(self):
        """An allowlisted inactive reviewer cannot reevaluate."""
        self.prepare()

        with self.assertRaises(PermissionError):
            self.record(reviewer_id="REC-003")

        self.assertEqual(len(self.history()), 0)

    def test_unknown_reviewer_is_blocked(self):
        """A reviewer ID must also exist in the database."""
        self.prepare()

        with self.assertRaises(PermissionError):
            self.record(reviewer_id="REC-999")

        self.assertEqual(len(self.history()), 0)

    def test_approved_must_be_boolean(self):
        """Reject integers, strings and absent decisions."""
        self.prepare()

        for value in (1, 0, None, "True", "False"):
            with self.subTest(approved=value):
                with self.assertRaises(ValueError):
                    self.record(approved=value)

        self.assertEqual(len(self.history()), 0)

    def test_feedback_must_not_be_empty(self):
        """Require meaningful reevaluation feedback."""
        self.prepare()

        for feedback in ("", "   ", None, 123):
            with self.subTest(feedback=feedback):
                with self.assertRaises(ValueError):
                    self.record(feedback=feedback)

        self.assertEqual(len(self.history()), 0)

    def test_invalid_applicant_identifiers(self):
        """Reject malformed applicant identifiers."""
        for applicant_id in ("", "   ", None, 123):
            with self.subTest(applicant_id=applicant_id):
                with self.assertRaises(ValueError):
                    self.record(applicant_id=applicant_id)

    def test_invalid_reviewer_identifiers(self):
        """Reject malformed reviewer identifiers."""
        for reviewer_id in ("", "   ", None, 123):
            with self.subTest(reviewer_id=reviewer_id):
                with self.assertRaises(ValueError):
                    self.record(reviewer_id=reviewer_id)

    def test_unknown_applicant_is_rejected(self):
        """Block reevaluations for missing applicants."""
        with self.assertRaises(ValueError):
            self.record(applicant_id="ASP-999")

        self.assertEqual(len(self.history("ASP-999")), 0)

    def test_latest_vod_rejection_blocks_reevaluation(self):
        """A newer rejection invalidates the admission."""
        self.prepare()

        self.review_workflow.record_review(
            self.make_review(
                decision=ReviewDecision.REJECTED,
            ),
            authenticated_reviewer_id="REC-001",
        )

        with self.assertRaises(PermissionError):
            self.record()

        self.assertEqual(len(self.history()), 0)

    def test_more_evidence_blocks_reevaluation(self):
        """Require a current approved VOD decision."""
        self.prepare()

        self.review_workflow.record_review(
            self.make_review(
                decision=ReviewDecision.MORE_EVIDENCE,
            ),
            authenticated_reviewer_id="REC-001",
        )

        with self.assertRaises(PermissionError):
            self.record()

    def test_mismatched_stored_vod_is_rejected(self):
        """Reject a more recent review for the wrong VOD."""
        self.prepare()

        self.reviews.add(
            self.make_review(
                vod_reference="vods/incorrect.mp4",
            )
        )

        with self.assertRaises(ValueError):
            self.record()

        self.assertEqual(len(self.history()), 0)

    def test_reevaluation_survives_database_reopening(self):
        """Verify actual SQLite persistence."""
        self.prepare()

        review_id = self.record(
            feedback="Persistencia comprobada.",
        )

        reopened_database = Database(self.db_path)

        with reopened_database.connection() as connection:
            row = connection.execute(
                """
                SELECT approved, feedback
                FROM reevaluations
                WHERE reevaluation_id = ?
                """,
                (review_id,),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["approved"], 1)
        self.assertEqual(
            row["feedback"],
            "Persistencia comprobada.",
        )

    def test_invalid_constructor_dependencies(self):
        """Require valid dependencies and reviewer permissions."""
        with self.assertRaises(TypeError):
            ReevaluationWorkflowService(
                None,
                self.training_workflow,
                {"REC-001"},
            )

        with self.assertRaises(TypeError):
            ReevaluationWorkflowService(
                self.database,
                None,
                {"REC-001"},
            )

        for authorized in (
            set(),
            [],
            {" "},
            {"REC-001", 123},
        ):
            with self.subTest(authorized=authorized):
                with self.assertRaises(ValueError):
                    ReevaluationWorkflowService(
                        self.database,
                        self.training_workflow,
                        authorized,
                    )

    def test_failed_validation_preserves_history(self):
        """An invalid operation must not insert another row."""
        self.prepare()

        self.record(
            approved=False,
            feedback="Primera decision.",
        )

        with self.assertRaises(ValueError):
            self.record(feedback=" ")

        rows = self.history()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["approved"], 0)
        self.assertEqual(
            rows[0]["feedback"],
            "Primera decision.",
        )


if __name__ == "__main__":
    unittest.main()
