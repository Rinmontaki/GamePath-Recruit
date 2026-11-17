
"""Control access to competitive opportunities using SQLite."""

from dataclasses import dataclass

from backend.algorithms.dijkstra import dijkstra
from backend.services.training_workflow_service import (
    TrainingWorkflowService,
)
from backend.storage.database import Database
from backend.structures.graph import DirectedWeightedGraph


@dataclass(frozen=True, slots=True)
class OpportunityRoute:
    """Represent preparation for an available opportunity."""

    applicant_id: str
    opportunity_id: str
    label: str
    nodes: tuple[str, ...]
    activities: tuple[str, ...]
    estimated_hours: float


class OpportunitiesWorkflowService:
    """Unlock graph opportunities after valid human reevaluation."""

    def __init__(
        self,
        database: Database,
        training_workflow_service: TrainingWorkflowService,
        graph: DirectedWeightedGraph,
        authorized_reviewer_ids: set[str] | frozenset[str],
    ) -> None:
        """Configure persistence, graph and permissions."""
        if not isinstance(database, Database):
            raise TypeError("A Database instance is required.")

        if not isinstance(
            training_workflow_service,
            TrainingWorkflowService,
        ):
            raise TypeError(
                "A TrainingWorkflowService is required."
            )

        if not isinstance(graph, DirectedWeightedGraph):
            raise TypeError(
                "A DirectedWeightedGraph is required."
            )

        if (
            not isinstance(authorized_reviewer_ids, (set, frozenset))
            or not authorized_reviewer_ids
            or any(
                not isinstance(item, str) or not item.strip()
                for item in authorized_reviewer_ids
            )
        ):
            raise ValueError(
                "A non-empty set of reviewer IDs is required."
            )

        self._database = database
        self._training_workflow = training_workflow_service
        self._graph = graph
        self._authorized_reviewers = frozenset(
            authorized_reviewer_ids
        )

    def get_available_opportunities(
        self,
        applicant_id: str,
    ) -> tuple[OpportunityRoute, ...]:
        """Get preparation routes after valid human approval."""
        if (
            not isinstance(applicant_id, str)
            or not applicant_id.strip()
        ):
            raise ValueError("A valid applicant ID is required.")

        plan = self._training_workflow.plan_for_applicant(
            applicant_id
        )

        if plan.start_node != "training_11" or plan.pending_skills:
            raise PermissionError(
                "Training must be completed first."
            )

        with self._database.connection() as connection:
            
            reevaluation = connection.execute(
                """
                SELECT
                    r.approved,
                    r.reviewer_id,
                    r.vod_review_id,
                    v.is_active,
                    (
                        SELECT MAX(vr.review_id)
                        FROM vod_reviews AS vr
                        WHERE vr.applicant_id = r.applicant_id
                    ) AS latest_vod_review_id
                FROM reevaluations AS r
                JOIN reviewers AS v
                    ON v.reviewer_id = r.reviewer_id
                WHERE r.applicant_id = ?
                ORDER BY r.reevaluation_id DESC
                LIMIT 1
                """,
                (applicant_id,),
            ).fetchone()

        if reevaluation is None:
            raise PermissionError(
                "A human reevaluation is required."
            )

        if reevaluation["approved"] != 1:
            raise PermissionError(
                "The latest reevaluation was not approved."
            )

        if (
            reevaluation["reviewer_id"]
            not in self._authorized_reviewers
            or reevaluation["is_active"] != 1
        ):
            raise PermissionError(
                "The reevaluation reviewer is not authorized "
                "or is inactive."
            )
        
        if (
            reevaluation["vod_review_id"] is None
            or reevaluation["vod_review_id"]
            != reevaluation["latest_vod_review_id"]
        ):
            raise PermissionError(
                "The reevaluation does not belong "
                "to the current VOD admission."
            )

        granted_requirements = (
            "recruiter_admission_approved",
            "human_reevaluation_approved",
        )

        routes = []

        for edge in self._graph.outgoing_edges("opportunities"):
            node = self._graph.get_node(edge.target)

            if node.node_type != "opportunity":
                continue

            path = dijkstra(
                graph=self._graph,
                target=node.node_id,
                granted_requirements=granted_requirements,
                start_node="reevaluation",
            )

            if path is None:
                raise ValueError(
                    f"No route exists to {node.node_id}."
                )

            routes.append(
                OpportunityRoute(
                    applicant_id=applicant_id,
                    opportunity_id=node.node_id,
                    label=node.label,
                    nodes=path.nodes,
                    activities=path.activities,
                    estimated_hours=path.total_hours,
                )
            )

        if not routes:
            raise ValueError(
                "No opportunity nodes are configured."
            )

        return tuple(routes)
