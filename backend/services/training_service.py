
"""Coordinate graph-based training plans in GamePath Recruit."""

from dataclasses import dataclass

from backend.algorithms.dijkstra import dijkstra
from backend.models.applicant import Applicant
from backend.models.training_progress import TrainingProgress
from backend.models.vod_review import VodReview
from backend.services.vod_review_service import VodReviewService
from backend.structures.graph import DirectedWeightedGraph


@dataclass(frozen=True, slots=True)
class TrainingPlan:
    """Represent a calculated preparation route."""

    applicant_id: str
    start_node: str
    target_node: str
    nodes: tuple[str, ...]
    activities: tuple[str, ...]
    estimated_hours: float
    pending_skills: tuple[str, ...]


class TrainingService:
    """Generate training routes for admitted applicants."""

    def __init__(
        self,
        graph: DirectedWeightedGraph,
        review_service: VodReviewService,
    ) -> None:
        if not isinstance(graph, DirectedWeightedGraph):
            raise TypeError("A DirectedWeightedGraph is required.")

        if not isinstance(review_service, VodReviewService):
            raise TypeError("A VodReviewService is required.")

        self._graph = graph
        self._review_service = review_service

    def plan_to_reevaluation(
        self,
        applicant: Applicant,
        review: VodReview,
        progress: TrainingProgress,
        *,
        authenticated_reviewer_id: str,
    ) -> TrainingPlan:
        """Calculate preparation remaining before reevaluation."""
        if not isinstance(applicant, Applicant):
            raise TypeError("An Applicant instance is required.")

        if not isinstance(progress, TrainingProgress):
            raise TypeError("A TrainingProgress instance is required.")

        if progress.applicant_id != applicant.applicant_id:
            raise ValueError(
                "Training progress belongs to another applicant."
            )

        validated_review = self._review_service.evaluate_review(
            applicant,
            review,
            authenticated_reviewer_id,
        )

        if not validated_review["admission_approved"]:
            raise PermissionError(
                "Human recruiter approval is required."
            )

        start_node = progress.current_node_id
        graph_node = self._graph.get_node(start_node)

        expected_skills = {
            "aim": "aim" in progress.completed_skills,
            "tactics": "tactics" in progress.completed_skills,
        }

        if graph_node.completed != expected_skills:
            raise ValueError(
                "Training progress does not match the graph state."
            )

        path = dijkstra(
            self._graph,
            target="reevaluation",
            granted_requirements=(
                "recruiter_admission_approved",
            ),
            start_node=start_node,
        )

        if path is None:
            raise ValueError(
                "No valid training route to reevaluation exists."
            )

        return TrainingPlan(
            applicant_id=applicant.applicant_id,
            start_node=start_node,
            target_node="reevaluation",
            nodes=path.nodes,
            activities=path.activities,
            estimated_hours=path.total_hours,
            pending_skills=tuple(
                sorted(progress.pending_skills)
            ),
        )
