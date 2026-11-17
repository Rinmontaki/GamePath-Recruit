
"""Unit tests for persistent graph-based training workflows."""

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
from backend.services.recruitment_service import RecruitmentService
from backend.services.review_workflow_service import (
    ReviewWorkflowService,
)
from backend.services.training_service import TrainingService
from backend.services.training_workflow_service import (
    TrainingWorkflowService,
)
from backend.services.vod_review_service import VodReviewService
from backend.storage.database import Database
from backend.structures.binary_tree import BinaryDecisionTree


class TestTrainingWorkflowService(unittest.TestCase):
    """Verify training plans reconstructed from SQLite."""

    def setUp(self) -> None:
        """Create isolated database records and services."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.database = Database(
            Path(temporary.name) / "gamepath_test.sqlite3"
        )
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
                    ("REC-001", "ReclutadorUno", 1),
                    ("REC-002", "ReclutadorDos", 1),
                    ("REC-003", "SinPermiso", 1),
                    ("REC-004", "Inactivo", 0),
                ),
            )

        data_dir = (
            Path(__file__).resolve().parents[1] / "data"
        )

        tree = BinaryDecisionTree(
            load_tree(data_dir / "profile_tree.json")
        )

        recruitment = RecruitmentService(tree)

        review_service = VodReviewService(
            recruitment_service=recruitment,
            authorized_reviewer_ids={
                "REC-001",
                "REC-002",
                "REC-004",
            },
        )

        self.review_workflow = ReviewWorkflowService(
            self.database,
            review_service,
        )

        training_service = TrainingService(
            graph=load_graph(data_dir / "training_graph.json"),
            review_service=review_service,
        )

        self.workflow = TrainingWorkflowService(
            self.database,
            training_service,
        )

        self.reviews = VodReviewRepository(self.database)
        self.progress = TrainingProgressRepository(self.database)

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
        decision=ReviewDecision.APPROVED,
        applicant_id="ASP-001",
        reviewer_id="REC-001",
        vod_reference=None,
    ) -> VodReview:
        """Create a review for an applicant."""
        if vod_reference is None:
            vod_reference = self.vod_paths[applicant_id]

        return VodReview(
            applicant_id=applicant_id,
            reviewer_id=reviewer_id,
            vod_reference=vod_reference,
            scores=self.scores,
            decision=decision,
            feedback="Evaluacion realizada por el reclutador.",
        )

    def approve(
        self,
        applicant_id="ASP-001",
        reviewer_id="REC-001",
    ) -> None:
        """Record an approved review through the workflow."""
        review = self.make_review(
            applicant_id=applicant_id,
            reviewer_id=reviewer_id,
        )

        self.review_workflow.record_review(
            review,
            authenticated_reviewer_id=reviewer_id,
        )

    def test_invalid_applicant_identifier(self):
        """Reject invalid applicant IDs."""
        for applicant_id in ("", "   ", None, 123):
            with self.subTest(applicant_id=applicant_id):
                with self.assertRaises(ValueError):
                    self.workflow.plan_for_applicant(applicant_id)

    def test_unknown_applicant(self):
        """Reject applicants missing from SQLite."""
        with self.assertRaises(ValueError):
            self.workflow.plan_for_applicant("ASP-999")

    def test_no_admission_review(self):
        """Block training before human admission."""
        with self.assertRaises(PermissionError):
            self.workflow.plan_for_applicant("ASP-001")

    def test_initial_route(self):
        """Calculate the complete route after admission."""
        self.approve()

        plan = self.workflow.plan_for_applicant("ASP-001")

        self.assertEqual(plan.applicant_id, "ASP-001")
        self.assertEqual(plan.start_node, "training_00")
        self.assertEqual(plan.target_node, "reevaluation")
        self.assertEqual(plan.estimated_hours, 6.0)
        self.assertEqual(
            plan.pending_skills,
            ("aim", "tactics"),
        )

    def test_route_after_aim(self):
        """Use persisted aim progress to reduce the route."""
        self.approve()
        self.progress.add_completion(
            "ASP-001", "aim", "REC-001"
        )

        plan = self.workflow.plan_for_applicant("ASP-001")

        self.assertEqual(plan.start_node, "training_10")
        self.assertEqual(plan.estimated_hours, 4.0)
        self.assertEqual(plan.pending_skills, ("tactics",))

    def test_route_after_tactics(self):
        """Use persisted tactics progress."""
        self.approve()
        self.progress.add_completion(
            "ASP-001", "tactics", "REC-001"
        )

        plan = self.workflow.plan_for_applicant("ASP-001")

        self.assertEqual(plan.start_node, "training_01")
        self.assertEqual(plan.estimated_hours, 3.0)
        self.assertEqual(plan.pending_skills, ("aim",))

    def test_route_after_both_skills(self):
        """Only reevaluation preparation remains."""
        self.approve()

        self.progress.add_completion(
            "ASP-001", "aim", "REC-001"
        )
        self.progress.add_completion(
            "ASP-001", "tactics", "REC-001"
        )

        plan = self.workflow.plan_for_applicant("ASP-001")

        self.assertEqual(plan.start_node, "training_11")
        self.assertEqual(
            plan.nodes,
            ("training_11", "reevaluation"),
        )
        self.assertEqual(plan.estimated_hours, 1.0)
        self.assertEqual(plan.pending_skills, ())

    def test_rejected_review_blocks_training(self):
        """Block training when the human decision is rejection."""
        self.review_workflow.record_review(
            self.make_review(ReviewDecision.REJECTED),
            authenticated_reviewer_id="REC-001",
        )

        with self.assertRaises(PermissionError):
            self.workflow.plan_for_applicant("ASP-001")

    def test_more_evidence_blocks_training(self):
        """Block training while more evidence is requested."""
        self.review_workflow.record_review(
            self.make_review(ReviewDecision.MORE_EVIDENCE),
            authenticated_reviewer_id="REC-001",
        )

        with self.assertRaises(PermissionError):
            self.workflow.plan_for_applicant("ASP-001")

    def test_latest_rejection_overrides_approval(self):
        """The latest review determines current admission."""
        self.approve()

        self.review_workflow.record_review(
            self.make_review(ReviewDecision.REJECTED),
            authenticated_reviewer_id="REC-001",
        )

        with self.assertRaises(PermissionError):
            self.workflow.plan_for_applicant("ASP-001")

    def test_second_authorized_reviewer(self):
        """Accept a valid review from another authorized reviewer."""
        self.approve(reviewer_id="REC-002")

        plan = self.workflow.plan_for_applicant("ASP-001")

        self.assertEqual(plan.start_node, "training_00")
        self.assertEqual(plan.estimated_hours, 6.0)

    def test_inactive_reviewer_blocks_existing_review(self):
        """Apply the current active-reviewer policy."""
        self.approve()

        with self.database.connection() as connection:
            connection.execute(
                """
                UPDATE reviewers
                SET is_active = 0
                WHERE reviewer_id = ?
                """,
                ("REC-001",),
            )

        with self.assertRaises(PermissionError):
            self.workflow.plan_for_applicant("ASP-001")

    def test_reviewer_without_permission(self):
        """Reject a persisted review from an unauthorized reviewer."""
        self.reviews.add(
            self.make_review(reviewer_id="REC-003")
        )

        with self.assertRaises(PermissionError):
            self.workflow.plan_for_applicant("ASP-001")

    def test_mismatched_stored_vod(self):
        """Reject a persisted review for the wrong recording."""
        self.reviews.add(
            self.make_review(
                vod_reference="vods/incorrect.mp4"
            )
        )

        with self.assertRaises(ValueError):
            self.workflow.plan_for_applicant("ASP-001")

    def test_unqualified_applicant_with_stored_review(self):
        """Do not trust a review that bypassed preselection."""
        self.reviews.add(
            self.make_review(applicant_id="ASP-003")
        )

        with self.assertRaises(ValueError):
            self.workflow.plan_for_applicant("ASP-003")

    def test_applicant_progress_is_independent(self):
        """Calculate separate routes from independent records."""
        self.approve("ASP-001")
        self.approve("ASP-002")

        self.progress.add_completion(
            "ASP-001", "aim", "REC-001"
        )

        first = self.workflow.plan_for_applicant("ASP-001")
        second = self.workflow.plan_for_applicant("ASP-002")

        self.assertEqual(first.start_node, "training_10")
        self.assertEqual(first.estimated_hours, 4.0)
        self.assertEqual(second.start_node, "training_00")
        self.assertEqual(second.estimated_hours, 6.0)

    def test_invalid_dependencies(self):
        """Require valid database and training service objects."""
        with self.assertRaises(TypeError):
            TrainingWorkflowService(
                None,
                self.workflow._training_service,
            )

        with self.assertRaises(TypeError):
            TrainingWorkflowService(
                self.database,
                None,
            )


if __name__ == "__main__":
    unittest.main()
