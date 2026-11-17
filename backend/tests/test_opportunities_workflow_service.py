
"""Unit tests for graph-based opportunity access."""

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
from backend.repositories.applicant_repository import ApplicantRepository
from backend.repositories.vod_review_repository import VodReviewRepository
from backend.services.opportunities_workflow_service import (
    OpportunitiesWorkflowService,
)
from backend.services.reevaluation_workflow_service import (
    ReevaluationWorkflowService,
)
from backend.services.recruitment_service import RecruitmentService
from backend.services.review_workflow_service import ReviewWorkflowService
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


class TestOpportunitiesWorkflowService(unittest.TestCase):
    """Verify opportunity access using persisted decisions."""

    def setUp(self) -> None:
        """Prepare isolated applicants and workflow services."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.db_path = Path(temporary.name) / "test.sqlite3"
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
                    ("REC-001", "ReclutadorPrincipal", 1),
                    ("REC-002", "SinAutorizacion", 1),
                    ("REC-003", "SegundoAutorizado", 1),
                    ("REC-004", "Inactivo", 0),
                ),
            )

        self.authorized = {
            "REC-001",
            "REC-003",
            "REC-004",
        }

        data_dir = Path(__file__).resolve().parents[1] / "data"

        self.graph = load_graph(
            data_dir / "training_graph.json"
        )

        tree = BinaryDecisionTree(
            load_tree(data_dir / "profile_tree.json")
        )

        recruitment = RecruitmentService(tree)

        review_service = VodReviewService(
            recruitment_service=recruitment,
            authorized_reviewer_ids=self.authorized,
        )

        self.review_workflow = ReviewWorkflowService(
            self.database,
            review_service,
        )

        self.training_workflow = TrainingWorkflowService(
            self.database,
            TrainingService(self.graph, review_service),
        )

        self.completion_workflow = (
            TrainingCompletionWorkflowService(
                self.database,
                self.training_workflow,
                self.authorized,
            )
        )

        self.reevaluation_workflow = ReevaluationWorkflowService(
            self.database,
            self.training_workflow,
            self.authorized,
        )

        self.workflow = OpportunitiesWorkflowService(
            self.database,
            self.training_workflow,
            self.graph,
            self.authorized,
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
        reviewer_id="REC-001",
        vod_reference=None,
    ) -> VodReview:
        """Build a VOD review for an applicant."""
        if vod_reference is None:
            vod_reference = self.vod_paths[applicant_id]

        return VodReview(
            applicant_id=applicant_id,
            reviewer_id=reviewer_id,
            vod_reference=vod_reference,
            scores=self.scores,
            decision=decision,
            feedback="Evaluacion competitiva.",
        )

    def admit(
        self,
        applicant_id="ASP-001",
        decision=ReviewDecision.APPROVED,
    ) -> None:
        """Record a validated VOD review."""
        self.review_workflow.record_review(
            self.make_review(
                applicant_id=applicant_id,
                decision=decision,
            ),
            authenticated_reviewer_id="REC-001",
        )

    def complete(
        self,
        applicant_id="ASP-001",
        skills=("aim", "tactics"),
    ) -> None:
        """Complete selected skills through the workflow."""
        for skill in skills:
            self.completion_workflow.record_completion(
                applicant_id,
                skill,
                authenticated_reviewer_id="REC-001",
            )

    def prepare(self, applicant_id="ASP-001") -> None:
        """Admit an applicant and complete training."""
        self.admit(applicant_id)
        self.complete(applicant_id)

    def reevaluate(
        self,
        approved=True,
        applicant_id="ASP-001",
        reviewer_id="REC-001",
    ) -> int:
        """Record a human reevaluation."""
        return self.reevaluation_workflow.record_reevaluation(
            applicant_id,
            approved=approved,
            feedback="Decision humana verificada.",
            authenticated_reviewer_id=reviewer_id,
        )

    def unlock(self, applicant_id="ASP-001") -> None:
        """Prepare and approve an applicant."""
        self.prepare(applicant_id)
        self.reevaluate(
            approved=True,
            applicant_id=applicant_id,
        )

    def routes(self, applicant_id="ASP-001"):
        """Request available opportunity preparation routes."""
        return self.workflow.get_available_opportunities(
            applicant_id
        )

    def test_invalid_applicant_identifiers(self):
        """Reject malformed applicant IDs."""
        for value in ("", "   ", None, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.routes(value)

    def test_unknown_applicant(self):
        """Reject access for unregistered applicants."""
        with self.assertRaises(ValueError):
            self.routes("ASP-999")

    def test_without_admission(self):
        """Require an approved VOD review."""
        with self.assertRaises(PermissionError):
            self.routes()

    def test_training_not_started(self):
        """An admission alone is not sufficient."""
        self.admit()

        with self.assertRaises(PermissionError):
            self.routes()

    def test_only_aim_completed(self):
        """Block opportunities when tactics is pending."""
        self.admit()
        self.complete(skills=("aim",))

        with self.assertRaises(PermissionError):
            self.routes()

    def test_only_tactics_completed(self):
        """Block opportunities when aim is pending."""
        self.admit()
        self.complete(skills=("tactics",))

        with self.assertRaises(PermissionError):
            self.routes()

    def test_without_reevaluation(self):
        """Training completion does not grant opportunities."""
        self.prepare()

        with self.assertRaises(PermissionError):
            self.routes()

    def test_rejected_reevaluation(self):
        """Require an explicit positive human decision."""
        self.prepare()
        self.reevaluate(approved=False)

        with self.assertRaises(PermissionError):
            self.routes()

    def test_approved_reevaluation_unlocks_three_routes(self):
        """Unlock exactly the configured opportunity nodes."""
        self.unlock()

        routes = self.routes()

        self.assertEqual(len(routes), 3)

        expected = {
            "tournaments": 1.0,
            "tryouts": 2.0,
            "sponsorships": 2.0,
        }

        self.assertEqual(
            {route.opportunity_id for route in routes},
            set(expected),
        )

        for route in routes:
            with self.subTest(opportunity=route.opportunity_id):
                self.assertEqual(
                    route.estimated_hours,
                    expected[route.opportunity_id],
                )
                self.assertEqual(route.applicant_id, "ASP-001")

    def test_routes_follow_graph_transitions(self):
        """Each path must go through the opportunity gateway."""
        self.unlock()

        routes = self.routes()

        for route in routes:
            with self.subTest(opportunity=route.opportunity_id):
                self.assertEqual(
                    route.nodes,
                    (
                        "reevaluation",
                        "opportunities",
                        route.opportunity_id,
                    ),
                )
                self.assertEqual(len(route.activities), 2)
                self.assertTrue(route.label.strip())

    def test_approval_after_previous_rejection(self):
        """Use the latest approved reevaluation."""
        self.prepare()
        self.reevaluate(approved=False)
        self.reevaluate(approved=True)

        self.assertEqual(len(self.routes()), 3)

    def test_new_rejection_revokes_access(self):
        """A later rejection overrides previous approval."""
        self.unlock()
        self.reevaluate(approved=False)

        with self.assertRaises(PermissionError):
            self.routes()

    def test_vod_rejection_revokes_access(self):
        """A newer rejected VOD invalidates admission."""
        self.unlock()

        self.admit(
            decision=ReviewDecision.REJECTED
        )

        with self.assertRaises(PermissionError):
            self.routes()

    def test_more_evidence_revokes_access(self):
        """A newer request for evidence blocks access."""
        self.unlock()

        self.admit(
            decision=ReviewDecision.MORE_EVIDENCE
        )

        with self.assertRaises(PermissionError):
            self.routes()

    def test_inactive_vod_reviewer_blocks_access(self):
        """Apply the current reviewer-active policy."""
        self.unlock()

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
            self.routes()

    def test_inactive_reevaluation_reviewer_blocks_access(self):
        """Recheck the reviewer who approved reevaluation."""
        self.prepare()
        self.reevaluate(
            approved=True,
            reviewer_id="REC-003",
        )

        with self.database.connection() as connection:
            connection.execute(
                """
                UPDATE reviewers
                SET is_active = 0
                WHERE reviewer_id = ?
                """,
                ("REC-003",),
            )

        with self.assertRaises(PermissionError):
            self.routes()

    def test_unauthorized_stored_reevaluation(self):
        """Reject approvals inserted by unauthorized reviewers."""
        self.prepare()

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
                    "REC-002",
                    1,
                    "Registro no autorizado.",
                ),
            )

        with self.assertRaises(PermissionError):
            self.routes()

    def test_one_applicant_cannot_use_anothers_approval(self):
        """Do not transfer approval between applicants."""
        self.unlock("ASP-001")
        self.prepare("ASP-002")

        self.assertEqual(len(self.routes("ASP-001")), 3)

        with self.assertRaises(PermissionError):
            self.routes("ASP-002")

    def test_independent_approved_applicants(self):
        """Build separate routes for two approved applicants."""
        self.unlock("ASP-001")
        self.unlock("ASP-002")

        first = self.routes("ASP-001")
        second = self.routes("ASP-002")

        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)

        self.assertTrue(
            all(route.applicant_id == "ASP-001" for route in first)
        )
        self.assertTrue(
            all(route.applicant_id == "ASP-002" for route in second)
        )

    def test_corrupted_stored_vod_blocks_access(self):
        """Never trust a mismatched VOD inserted directly."""
        self.unlock()

        self.reviews.add(
            self.make_review(
                vod_reference="vods/incorrect.mp4"
            )
        )

        with self.assertRaises(ValueError):
            self.routes()

    def test_unqualified_applicant_cannot_bypass_tree(self):
        """Reject direct SQL approvals for ineligible players."""
        self.reviews.add(
            self.make_review(applicant_id="ASP-003")
        )

        with self.database.connection() as connection:
            connection.executemany(
                """
                INSERT INTO skill_completions (
                    applicant_id,
                    skill,
                    verified_by
                )
                VALUES (?, ?, ?)
                """,
                (
                    ("ASP-003", "aim", "REC-001"),
                    ("ASP-003", "tactics", "REC-001"),
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
                    "ASP-003",
                    "REC-001",
                    1,
                    "Aprobacion insertada directamente.",
                ),
            )

        with self.assertRaises(ValueError):
            self.routes("ASP-003")

    def test_opportunities_survive_database_reopening(self):
        """Read stored decisions using a reopened database."""
        self.unlock()

        reopened = OpportunitiesWorkflowService(
            Database(self.db_path),
            self.training_workflow,
            self.graph,
            self.authorized,
        )

        routes = reopened.get_available_opportunities(
            "ASP-001"
        )

        self.assertEqual(len(routes), 3)

    def test_invalid_constructor_dependencies(self):
        """Require valid database, training service and graph."""
        with self.assertRaises(TypeError):
            OpportunitiesWorkflowService(
                None,
                self.training_workflow,
                self.graph,
                self.authorized,
            )

        with self.assertRaises(TypeError):
            OpportunitiesWorkflowService(
                self.database,
                None,
                self.graph,
                self.authorized,
            )

        with self.assertRaises(TypeError):
            OpportunitiesWorkflowService(
                self.database,
                self.training_workflow,
                None,
                self.authorized,
            )

    def test_invalid_reviewer_permissions(self):
        """Reject malformed reviewer authorization collections."""
        for authorized in (
            set(),
            [],
            {" "},
            {"REC-001", 123},
        ):
            with self.subTest(authorized=authorized):
                with self.assertRaises(ValueError):
                    OpportunitiesWorkflowService(
                        self.database,
                        self.training_workflow,
                        self.graph,
                        authorized,
                    )
    
    
    def test_new_vod_cycle_invalidates_previous_reevaluation(self):
        """Do not reuse reevaluation approval for a new VOD."""
        self.unlock("ASP-001")

        self.assertEqual(len(self.routes("ASP-001")), 3)

        with self.database.connection() as connection:
            connection.execute(
                """
                UPDATE applicants
                SET vod_reference = ?
                WHERE applicant_id = ?
                """,
                ("vods/new_cycle.mp4", "ASP-001"),
            )

        new_review = self.make_review(
            applicant_id="ASP-001",
            vod_reference="vods/new_cycle.mp4",
        )

        self.review_workflow.record_review(
            new_review,
            authenticated_reviewer_id="REC-001",
        )

        with self.assertRaises(PermissionError):
            self.routes("ASP-001")
   


if __name__ == "__main__":
    unittest.main()
