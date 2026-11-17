
"""Coordinate authorized training skill completions."""

from backend.models.training_progress import TrainingProgress
from backend.repositories.training_progress_repository import (
    TrainingProgressRepository,
)
from backend.services.training_workflow_service import (
    TrainingWorkflowService,
)
from backend.storage.database import Database


class TrainingCompletionWorkflowService:
    """Validate training admission before recording progress."""

    def __init__(
        self,
        database: Database,
        training_workflow_service: TrainingWorkflowService,
        authorized_reviewer_ids: set[str] | frozenset[str],
    ) -> None:
        """Configure persistence and reviewer permissions."""
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
                not isinstance(reviewer_id, str)
                or not reviewer_id.strip()
                for reviewer_id in authorized_reviewer_ids
            )
        ):
            raise ValueError(
                "A non-empty set of reviewer IDs is required."
            )

        self._database = database
        self._training_workflow = training_workflow_service
        self._progress = TrainingProgressRepository(database)
        self._authorized_reviewers = frozenset(
            authorized_reviewer_ids
        )

    def record_completion(
        self,
        applicant_id: str,
        skill: str,
        *,
        authenticated_reviewer_id: str,
    ) -> TrainingProgress:
        """Validate and persist one completed training skill."""
        if (
            not isinstance(applicant_id, str)
            or not applicant_id.strip()
        ):
            raise ValueError("A valid applicant ID is required.")

        if not isinstance(skill, str) or not skill.strip():
            raise ValueError("A valid training skill is required.")

        if (
            not isinstance(authenticated_reviewer_id, str)
            or not authenticated_reviewer_id.strip()
        ):
            raise ValueError("A valid reviewer ID is required.")

        self._validate_reviewer(authenticated_reviewer_id)

        plan = self._training_workflow.plan_for_applicant(
            applicant_id
        )

        if skill not in plan.pending_skills:
            raise ValueError(
                "The skill is unsupported or already completed."
            )

        self._progress.add_completion(
            applicant_id=applicant_id,
            skill=skill,
            verified_by=authenticated_reviewer_id,
        )

        progress = self._progress.get_for_applicant(
            applicant_id
        )

        if progress is None:
            raise RuntimeError(
                "Training progress could not be recovered."
            )

        return progress

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
