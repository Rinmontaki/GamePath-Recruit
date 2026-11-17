
"""Coordinate persistent training plans in GamePath Recruit."""

from backend.repositories.applicant_repository import (
    ApplicantRepository,
)
from backend.repositories.training_progress_repository import (
    TrainingProgressRepository,
)
from backend.repositories.vod_review_repository import (
    VodReviewRepository,
)
from backend.services.training_service import (
    TrainingPlan,
    TrainingService,
)
from backend.storage.database import Database


class TrainingWorkflowService:
    """Build training plans using persisted applicant records."""

    def __init__(
        self,
        database: Database,
        training_service: TrainingService,
    ) -> None:
        """Configure the persistent training workflow."""
        if not isinstance(database, Database):
            raise TypeError("A Database instance is required.")

        if not isinstance(training_service, TrainingService):
            raise TypeError("A TrainingService is required.")

        self._database = database
        self._training_service = training_service
        self._applicants = ApplicantRepository(database)
        self._reviews = VodReviewRepository(database)
        self._progress = TrainingProgressRepository(database)

    def plan_for_applicant(
        self,
        applicant_id: str,
    ) -> TrainingPlan:
        """Calculate training from persisted applicant data."""
        if (
            not isinstance(applicant_id, str)
            or not applicant_id.strip()
        ):
            raise ValueError("A valid applicant ID is required.")

        applicant = self._applicants.get_by_id(applicant_id)

        if applicant is None:
            raise ValueError("The applicant is not registered.")

        review = self._reviews.get_latest_for_applicant(
            applicant_id
        )

        if review is None:
            raise PermissionError(
                "A human admission review is required."
            )

        with self._database.connection() as connection:
            reviewer = connection.execute(
                """
                SELECT is_active
                FROM reviewers
                WHERE reviewer_id = ?
                """,
                (review.reviewer_id,),
            ).fetchone()

        if reviewer is None or reviewer["is_active"] != 1:
            raise PermissionError(
                "The reviewer's account is not active."
            )

        progress = self._progress.get_for_applicant(
            applicant_id
        )

        if progress is None:
            raise ValueError(
                "Training progress could not be retrieved."
            )

        return self._training_service.plan_to_reevaluation(
            applicant=applicant,
            review=review,
            progress=progress,
            authenticated_reviewer_id=review.reviewer_id,
        )
