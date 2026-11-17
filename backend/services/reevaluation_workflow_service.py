
"""Coordinate human reevaluations after completed training."""

from backend.services.training_workflow_service import (
    TrainingWorkflowService,
)
from backend.storage.database import Database


class ReevaluationWorkflowService:
    """Validate and persist human training reevaluations."""

    def __init__(
        self,
        database: Database,
        training_workflow_service: TrainingWorkflowService,
        authorized_reviewer_ids: set[str] | frozenset[str],
    ) -> None:
        """Configure database and reviewer permissions."""
        if not isinstance(database, Database):
            raise TypeError("A Database instance is required.")

        if not isinstance(
            training_workflow_service,
            TrainingWorkflowService,
        ):
            raise TypeError(
                "A TrainingWorkflowService instance is required."
            )

        if (
            not isinstance(authorized_reviewer_ids, (set, frozenset))
            or not authorized_reviewer_ids
            or any(
                not isinstance(value, str) or not value.strip()
                for value in authorized_reviewer_ids
            )
        ):
            raise ValueError(
                "A non-empty set of reviewer IDs is required."
            )

        self._database = database
        self._training_workflow = training_workflow_service
        self._authorized_reviewers = frozenset(
            authorized_reviewer_ids
        )

    def record_reevaluation(
        self,
        applicant_id: str,
        *,
        approved: bool,
        feedback: str,
        authenticated_reviewer_id: str,
    ) -> int:
        """Persist a reevaluation linked to its current VOD."""
        self._validate_identifier(applicant_id, "Applicant ID")
        self._validate_identifier(
            authenticated_reviewer_id,
            "Reviewer ID",
        )

        if type(approved) is not bool:
            raise ValueError(
                "The reevaluation decision must be boolean."
            )

        if not isinstance(feedback, str) or not feedback.strip():
            raise ValueError(
                "Reevaluation feedback cannot be empty."
            )

        reviewer_id = authenticated_reviewer_id
        self._validate_reviewer(reviewer_id)

        plan = self._training_workflow.plan_for_applicant(
            applicant_id
        )

        if (
            plan.start_node != "training_11"
            or plan.pending_skills
        ):
            raise PermissionError(
                "Verified training must be completed "
                "before human reevaluation."
            )

        with self._database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            current_review = connection.execute(
                """
                SELECT
                    v.review_id,
                    v.decision,
                    v.vod_reference,
                    a.vod_reference AS applicant_vod
                FROM vod_reviews AS v
                JOIN applicants AS a
                    ON a.applicant_id = v.applicant_id
                WHERE v.applicant_id = ?
                ORDER BY v.review_id DESC
                LIMIT 1
                """,
                (applicant_id,),
            ).fetchone()

            if (
                current_review is None
                or current_review["decision"] != "approved"
                or current_review["vod_reference"]
                != current_review["applicant_vod"]
            ):
                raise PermissionError(
                    "A current approved VOD review is required."
                )

            reviewer = connection.execute(
                """
                SELECT is_active
                FROM reviewers
                WHERE reviewer_id = ?
                """,
                (reviewer_id,),
            ).fetchone()

            if reviewer is None or reviewer["is_active"] != 1:
                raise PermissionError(
                    "An active reviewer account is required."
                )

            cursor = connection.execute(
                """
                INSERT INTO reevaluations (
                    applicant_id,
                    reviewer_id,
                    vod_review_id,
                    approved,
                    feedback
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    applicant_id,
                    reviewer_id,
                    current_review["review_id"],
                    int(approved),
                    feedback,
                ),
            )

            reevaluation_id = cursor.lastrowid

        if reevaluation_id is None:
            raise RuntimeError(
                "The reevaluation ID could not be obtained."
            )

        return reevaluation_id

    def _validate_reviewer(self, reviewer_id: str) -> None:
        """Require an authorized and active reviewer."""
        if reviewer_id not in self._authorized_reviewers:
            raise PermissionError(
                "The reviewer is not authorized."
            )

        with self._database.connection() as connection:
            reviewer = connection.execute(
                """
                SELECT is_active
                FROM reviewers
                WHERE reviewer_id = ?
                """,
                (reviewer_id,),
            ).fetchone()

        if reviewer is None or reviewer["is_active"] != 1:
            raise PermissionError(
                "An active reviewer account is required."
            )

    @staticmethod
    def _validate_identifier(
        value: str,
        field_name: str,
    ) -> None:
        """Require a non-empty identifier."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{field_name} must be a non-empty string."
            )
