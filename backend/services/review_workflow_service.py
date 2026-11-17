
"""Coordinate validated VOD review persistence."""

from backend.models.vod_review import VodReview
from backend.repositories.applicant_repository import (
    ApplicantRepository,
)
from backend.repositories.vod_review_repository import (
    VodReviewRepository,
)
from backend.services.vod_review_service import (
    VodReviewService,
)
from backend.storage.database import Database


class ReviewWorkflowService:
    """Validate and persist human recruitment decisions."""

    def __init__(
        self,
        database: Database,
        review_service: VodReviewService,
    ) -> None:
        """Configure the persistence workflow."""
        if not isinstance(database, Database):
            raise TypeError("A Database instance is required.")

        if not isinstance(review_service, VodReviewService):
            raise TypeError("A VodReviewService is required.")

        self._database = database
        self._review_service = review_service
        self._applicants = ApplicantRepository(database)
        self._reviews = VodReviewRepository(database)

    def record_review(
        self,
        review: VodReview,
        *,
        authenticated_reviewer_id: str,
    ) -> int:
        """Validate a review before saving it in SQLite."""
        if not isinstance(review, VodReview):
            raise TypeError("A VodReview instance is required.")

        applicant = self._applicants.get_by_id(
            review.applicant_id
        )

        if applicant is None:
            raise ValueError(
                "The applicant is not registered."
            )

        with self._database.connection() as connection:
            reviewer = connection.execute(
                """
                SELECT is_active
                FROM reviewers
                WHERE reviewer_id = ?
                """,
                (authenticated_reviewer_id,),
            ).fetchone()

        if reviewer is None or reviewer["is_active"] != 1:
            raise PermissionError(
                "An active reviewer is required."
            )

        self._review_service.evaluate_review(
            applicant,
            review,
            authenticated_reviewer_id,
        )

        return self._reviews.add(review)
