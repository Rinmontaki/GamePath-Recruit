
"""Unit tests for authorized training completion workflows."""

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
from backend.repositories.training_progress_repository import (
    TrainingProgressRepository,
)
from backend.repositories.vod_review_repository import (
    VodReviewRepository,
)
from backend.services.recruitment_service import (
    RecruitmentService,
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


class TestTrainingCompletionWorkflowService(unittest.TestCase):
    """Verify admission and authorization before progress changes."""

    def setUp(self) -> None:
        """Build independent SQLite and service instances."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.db_path = (
            Path(temporary.name) / "gamepath_test.sqlite3"
        )

        self.database = Database(self.db_path)
        self.database.initialize()

        applicants = ApplicantRepository(self.database)

        profiles = (
            ("ASP-001", 6, "Diamante", "vods/first.mp4"),
            ("ASP-002", 5, "Oro", "vods/second.mp4"),
            ("ASP-003", 3, "Oro", "vods/third.mp4"),
        )

        self.vod_paths = {}

        for applicant_id, hours, rank, vod in profiles:
            applicants.add(
                Applicant(
                    applicant_id=applicant_id,
                    game_name=f"Jugador-{applicant_id}",
                    daily_play_hours=hours,
                    peak_rank=rank,
                    accepts_training=True,
                    vod_reference=vod,
                )
            )
            self.vod_paths[applicant_id] = vod

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

        data_dir = (
            Path(__file__).resolve().parents[1] / "data"
        )

        tree = BinaryDecisionTree(
            load_tree(data_dir / "profile_tree.json")
        )

        recruitment = RecruitmentService(tree)

        authorized = {
            "REC-001",
            "REC-003",
            "REC-999",
        }

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

        self.workflow = TrainingCompletionWorkflowService(
            database=self.database,
            training_workflow_service=self.training_workflow,
            authorized_reviewer_ids=authorized,
        )

        self.progress = TrainingProgressRepository(
            self.database
        )

        self.reviews = VodReviewRepository(self.database)

        self.scores = SkillScores(
            aim=4,
            game_sense=3,
            rotations=2,
            macro=3,
            micro=4,
            communication=3,
        )

    def make_review(
        self,
        applicant_id="ASP-001",
        decision=ReviewDecision.APPROVED,
        vod_reference=None,
    ) -> VodReview:
        """Create a human review for an applicant."""
        if vod_reference is None:
            vod_reference = self.vod_paths[applicant_id]

        return VodReview(
            applicant_id=applicant_id,
            reviewer_id="REC-001",
            vod_reference=vod_reference,
            scores=self.scores,
            decision=decision,
            feedback="Revision humana registrada.",
        )

    def record_review(
        self,
        applicant_id="ASP-001",
        decision=ReviewDecision.APPROVED,
    ) -> None:
        """Save a validated review through the workflow."""
        review = self.make_review(
            applicant_id=applicant_id,
            decision=decision,
        )

        self.review_workflow.record_review(
            review,
            authenticated_reviewer_id="REC-001",
        )

    def complete(
        self,
        skill="aim",
        applicant_id="ASP-001",
        reviewer_id="REC-001",
    ):
        """Record a training completion using test defaults."""
        return self.workflow.record_completion(
            applicant_id=applicant_id,
            skill=skill,
            authenticated_reviewer_id=reviewer_id,
        )

    def assert_no_progress(self, applicant_id="ASP-001"):
        """Verify that no training skills were stored."""
        progress = self.progress.get_for_applicant(applicant_id)

        self.assertIsNotNone(progress)
        self.assertEqual(
            progress.completed_skills,
            frozenset(),
        )

    def test_aim_completion_after_admission(self):
        """Allow aim completion after valid admission."""
        self.record_review()

        progress = self.complete("aim")

        self.assertEqual(
            progress.current_node_id,
            "training_10",
        )
        self.assertEqual(
            progress.completed_skills,
            frozenset({"aim"}),
        )

    def test_tactics_completion_after_admission(self):
        """Allow tactics to be completed before aim."""
        self.record_review()

        progress = self.complete("tactics")

        self.assertEqual(
            progress.current_node_id,
            "training_01",
        )

    def test_both_skills_completed(self):
        """Reach training_11 after both verified activities."""
        self.record_review()

        self.complete("aim")
        progress = self.complete("tactics")

        self.assertEqual(
            progress.current_node_id,
            "training_11",
        )
        self.assertTrue(progress.is_training_complete)

        plan = self.training_workflow.plan_for_applicant(
            "ASP-001"
        )

        self.assertEqual(plan.estimated_hours, 1.0)

    def test_completion_survives_repository_recreation(self):
        """Load a recorded skill through a new repository."""
        self.record_review()
        self.complete("aim")

        another_repository = TrainingProgressRepository(
            Database(self.db_path)
        )

        recovered = another_repository.get_for_applicant(
            "ASP-001"
        )

        self.assertEqual(
            recovered.completed_skills,
            frozenset({"aim"}),
        )

    def test_no_admission_blocks_completion(self):
        """Block progress before an admission decision."""
        with self.assertRaises(PermissionError):
            self.complete("aim")

        self.assert_no_progress()

    def test_rejected_review_blocks_completion(self):
        """Reject progress when the latest review rejects."""
        self.record_review(
            decision=ReviewDecision.REJECTED
        )

        with self.assertRaises(PermissionError):
            self.complete("aim")

        self.assert_no_progress()

    def test_more_evidence_blocks_completion(self):
        """Reject progress while more evidence is required."""
        self.record_review(
            decision=ReviewDecision.MORE_EVIDENCE
        )

        with self.assertRaises(PermissionError):
            self.complete("aim")

        self.assert_no_progress()

    def test_latest_rejection_blocks_completion(self):
        """Use the most recent review to determine admission."""
        self.record_review(
            decision=ReviewDecision.APPROVED
        )

        self.record_review(
            decision=ReviewDecision.REJECTED
        )

        with self.assertRaises(PermissionError):
            self.complete("aim")

        self.assert_no_progress()

    def test_unknown_applicant_is_rejected(self):
        """Reject progress for nonexistent applicants."""
        with self.assertRaises(ValueError):
            self.complete(
                "aim",
                applicant_id="ASP-999",
            )

    def test_unqualified_stored_approval_is_rejected(self):
        """Reject an approval that bypassed preselection."""
        self.reviews.add(
            self.make_review(applicant_id="ASP-003")
        )

        with self.assertRaises(ValueError):
            self.complete(
                "aim",
                applicant_id="ASP-003",
            )

        self.assert_no_progress("ASP-003")

    def test_active_unauthorized_reviewer_is_blocked(self):
        """Being active is insufficient without permission."""
        self.record_review()

        with self.assertRaises(PermissionError):
            self.complete(
                "aim",
                reviewer_id="REC-002",
            )

        self.assert_no_progress()

    def test_inactive_authorized_reviewer_is_blocked(self):
        """An allowlisted but inactive reviewer cannot advance."""
        self.record_review()

        with self.assertRaises(PermissionError):
            self.complete(
                "aim",
                reviewer_id="REC-003",
            )

        self.assert_no_progress()

    def test_unknown_authorized_reviewer_is_blocked(self):
        """An allowlisted ID must still exist in SQLite."""
        self.record_review()

        with self.assertRaises(PermissionError):
            self.complete(
                "aim",
                reviewer_id="REC-999",
            )

        self.assert_no_progress()

    def test_duplicate_completion_is_rejected(self):
        """Never record the same skill twice."""
        self.record_review()
        self.complete("aim")

        with self.assertRaises(ValueError):
            self.complete("aim")

        progress = self.progress.get_for_applicant(
            "ASP-001"
        )

        self.assertEqual(
            progress.completed_skills,
            frozenset({"aim"}),
        )

    def test_invalid_skills_are_rejected(self):
        """Reject invalid or unsupported training skills."""
        self.record_review()

        for skill in (
            "",
            " ",
            "AIM",
            "aim ",
            "rotations",
            None,
            123,
        ):
            with self.subTest(skill=skill):
                with self.assertRaises(ValueError):
                    self.complete(skill)

        self.assert_no_progress()

    def test_invalid_applicant_identifiers(self):
        """Reject invalid applicant identifiers."""
        for applicant_id in ("", "   ", None, 123):
            with self.subTest(applicant_id=applicant_id):
                with self.assertRaises(ValueError):
                    self.complete(
                        "aim",
                        applicant_id=applicant_id,
                    )

    def test_invalid_reviewer_identifiers(self):
        """Reject malformed reviewer identifiers."""
        for reviewer_id in ("", "   ", None, 123):
            with self.subTest(reviewer_id=reviewer_id):
                with self.assertRaises(ValueError):
                    self.complete(
                        "aim",
                        reviewer_id=reviewer_id,
                    )

    def test_applicant_progress_remains_independent(self):
        """Keep progress separate for different applicants."""
        self.record_review("ASP-001")
        self.record_review("ASP-002")

        first = self.complete(
            "aim",
            applicant_id="ASP-001",
        )

        second = self.complete(
            "tactics",
            applicant_id="ASP-002",
        )

        self.assertEqual(
            first.current_node_id,
            "training_10",
        )
        self.assertEqual(
            second.current_node_id,
            "training_01",
        )

    def test_reviewer_identity_is_persisted(self):
        """Store the verifier associated with a completion."""
        self.record_review()
        self.complete("aim")

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT skill, verified_by
                FROM skill_completions
                WHERE applicant_id = ?
                """,
                ("ASP-001",),
            ).fetchone()

        self.assertEqual(row["skill"], "aim")
        self.assertEqual(row["verified_by"], "REC-001")

    def test_invalid_constructor_dependencies(self):
        """Require valid services and reviewer permissions."""
        with self.assertRaises(TypeError):
            TrainingCompletionWorkflowService(
                None,
                self.training_workflow,
                {"REC-001"},
            )

        with self.assertRaises(TypeError):
            TrainingCompletionWorkflowService(
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
                    TrainingCompletionWorkflowService(
                        self.database,
                        self.training_workflow,
                        authorized,
                    )

    def test_mismatched_stored_vod_blocks_completion(self):
        """Do not trust an approval linked to another recording."""
        self.reviews.add(
            self.make_review(
                vod_reference="vods/incorrect.mp4"
            )
        )

        with self.assertRaises(ValueError):
            self.complete("aim")

        self.assert_no_progress()


if __name__ == "__main__":
    unittest.main()
