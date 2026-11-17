
"""Unit tests for graph-based training services."""

import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from backend.loaders.graph_loader import load_graph
from backend.loaders.tree_loader import load_tree
from backend.models.applicant import Applicant
from backend.models.training_progress import TrainingProgress
from backend.models.vod_review import (
    ReviewDecision,
    SkillScores,
    VodReview,
)
from backend.services.recruitment_service import RecruitmentService
from backend.services.training_service import TrainingService
from backend.services.vod_review_service import VodReviewService
from backend.structures.binary_tree import BinaryDecisionTree


def make_applicant(**changes) -> Applicant:
    """Create a valid applicant for training tests."""
    data = {
        "applicant_id": "ASP-001",
        "game_name": "JugadorDemo",
        "daily_play_hours": 6,
        "peak_rank": "Diamante",
        "accepts_training": True,
        "vod_reference": "vods/demo.mp4",
    }

    data.update(changes)
    return Applicant(**data)


def make_review(**changes) -> VodReview:
    """Create an approved human review."""
    data = {
        "applicant_id": "ASP-001",
        "reviewer_id": "REC-001",
        "vod_reference": "vods/demo.mp4",
        "scores": SkillScores(
            aim=4,
            game_sense=3,
            rotations=2,
            macro=3,
            micro=4,
            communication=3,
        ),
        "decision": ReviewDecision.APPROVED,
        "feedback": "Admitido para entrenamiento.",
    }

    data.update(changes)
    return VodReview(**data)


def make_progress(
    skills=frozenset(),
    applicant_id="ASP-001",
) -> TrainingProgress:
    """Create applicant training progress."""
    return TrainingProgress(
        applicant_id=applicant_id,
        completed_skills=skills,
    )


class TestTrainingService(unittest.TestCase):
    """Verify training routes and admission restrictions."""

    @classmethod
    def setUpClass(cls) -> None:
        data_dir = (
            Path(__file__).resolve().parents[1]
            / "data"
        )

        tree = BinaryDecisionTree(
            load_tree(data_dir / "profile_tree.json")
        )

        recruitment = RecruitmentService(tree)

        cls.review_service = VodReviewService(
            recruitment_service=recruitment,
            authorized_reviewer_ids={"REC-001"},
        )

        cls.graph = load_graph(
            data_dir / "training_graph.json"
        )

        cls.service = TrainingService(
            graph=cls.graph,
            review_service=cls.review_service,
        )

    def calculate(
        self,
        applicant=None,
        review=None,
        progress=None,
        reviewer_id="REC-001",
    ):
        """Calculate a plan with valid default inputs."""
        return self.service.plan_to_reevaluation(
            applicant if applicant is not None else make_applicant(),
            review if review is not None else make_review(),
            progress if progress is not None else make_progress(),
            authenticated_reviewer_id=reviewer_id,
        )

    def test_initial_training_route(self):
        """Calculate the complete preparation route."""
        plan = self.calculate()

        self.assertEqual(plan.start_node, "training_00")
        self.assertEqual(plan.target_node, "reevaluation")
        self.assertEqual(
            plan.nodes,
            (
                "training_00",
                "training_10",
                "training_11",
                "reevaluation",
            ),
        )
        self.assertEqual(plan.estimated_hours, 6.0)

    def test_route_after_aim(self):
        """Skip aim when already completed."""
        progress = make_progress(
            frozenset({"aim"})
        )

        plan = self.calculate(progress=progress)

        self.assertEqual(plan.start_node, "training_10")
        self.assertEqual(plan.estimated_hours, 4.0)
        self.assertEqual(
            plan.pending_skills,
            ("tactics",),
        )

    def test_route_after_tactics(self):
        """Skip tactics when already completed."""
        progress = make_progress(
            frozenset({"tactics"})
        )

        plan = self.calculate(progress=progress)

        self.assertEqual(plan.start_node, "training_01")
        self.assertEqual(plan.estimated_hours, 3.0)
        self.assertEqual(
            plan.pending_skills,
            ("aim",),
        )

    def test_route_after_both_skills(self):
        """Require only reevaluation preparation."""
        progress = make_progress(
            frozenset({"aim", "tactics"})
        )

        plan = self.calculate(progress=progress)

        self.assertEqual(
            plan.nodes,
            ("training_11", "reevaluation"),
        )
        self.assertEqual(plan.pending_skills, ())
        self.assertEqual(plan.estimated_hours, 1.0)

    def test_activities_match_graph_edges(self):
        """Ensure calculated activities exist in the graph."""
        plan = self.calculate()

        self.assertEqual(
            len(plan.activities),
            len(plan.nodes) - 1,
        )

        for source, target, activity in zip(
            plan.nodes,
            plan.nodes[1:],
            plan.activities,
        ):
            edges = self.graph.outgoing_edges(source)

            self.assertTrue(
                any(
                    edge.target == target
                    and edge.activity == activity
                    for edge in edges
                )
            )

    def test_training_plan_is_immutable(self):
        """Prevent direct modification of a calculated plan."""
        plan = self.calculate()

        with self.assertRaises(FrozenInstanceError):
            plan.estimated_hours = 100

    def test_rejected_review_blocks_training(self):
        """Reject training when the human review is negative."""
        review = make_review(
            decision=ReviewDecision.REJECTED
        )

        with self.assertRaises(PermissionError):
            self.calculate(review=review)

    def test_more_evidence_blocks_training(self):
        """Prevent training while further evidence is needed."""
        review = make_review(
            decision=ReviewDecision.MORE_EVIDENCE
        )

        with self.assertRaises(PermissionError):
            self.calculate(review=review)

    def test_unauthorized_reviewer(self):
        """Reject a reviewer without permission."""
        with self.assertRaises(PermissionError):
            self.calculate(reviewer_id="REC-999")

    def test_reviewer_identity_mismatch(self):
        """Reject a review attributed to another reviewer."""
        review = make_review(
            reviewer_id="REC-002"
        )

        with self.assertRaises(PermissionError):
            self.calculate(review=review)

    def test_progress_belongs_to_another_applicant(self):
        """Reject another player's progress."""
        progress = make_progress(
            frozenset({"aim"}),
            applicant_id="ASP-999",
        )

        with self.assertRaises(ValueError):
            self.calculate(progress=progress)

    def test_missing_applicant_vod(self):
        """Require the applicant's VOD reference."""
        applicant = make_applicant(
            vod_reference=None
        )

        with self.assertRaises(ValueError):
            self.calculate(applicant=applicant)

    def test_vod_reference_mismatch(self):
        """Reject a review of a different VOD."""
        review = make_review(
            vod_reference="vods/another.mp4"
        )

        with self.assertRaises(ValueError):
            self.calculate(review=review)

    def test_unqualified_applicant(self):
        """Prevent training without successful preselection."""
        applicant = make_applicant(
            daily_play_hours=3
        )

        with self.assertRaises(ValueError):
            self.calculate(applicant=applicant)

    def test_invalid_input_types(self):
        """Reject invalid applicant and progress objects."""
        with self.assertRaises(TypeError):
            self.service.plan_to_reevaluation(
                {"applicant_id": "ASP-001"},
                make_review(),
                make_progress(),
                authenticated_reviewer_id="REC-001",
            )

        with self.assertRaises(TypeError):
            self.service.plan_to_reevaluation(
                make_applicant(),
                make_review(),
                {"completed_skills": ["aim"]},
                authenticated_reviewer_id="REC-001",
            )

    def test_constructor_validation(self):
        """Require the graph and VOD review service."""
        with self.assertRaises(TypeError):
            TrainingService(
                graph=None,
                review_service=self.review_service,
            )

        with self.assertRaises(TypeError):
            TrainingService(
                graph=self.graph,
                review_service=None,
            )


if __name__ == "__main__":
    unittest.main()
