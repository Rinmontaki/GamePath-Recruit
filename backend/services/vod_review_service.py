
"""Validate human VOD reviews in GamePath Recruit."""

from collections.abc import Iterable
from dataclasses import asdict

from backend.models.applicant import Applicant
from backend.models.vod_review import (
    ReviewDecision,
    VodReview,
)
from backend.services.recruitment_service import RecruitmentService


class VodReviewService:
    """Coordinate and validate human recruitment reviews."""

    def __init__(
        self,
        recruitment_service: RecruitmentService,
        authorized_reviewer_ids: Iterable[str],
    ) -> None:
        if not isinstance(
            recruitment_service,
            RecruitmentService,
        ):
            raise TypeError("A RecruitmentService is required.")

        if isinstance(authorized_reviewer_ids, str):
            raise ValueError("Reviewer IDs must be a collection.")

        reviewers = frozenset(authorized_reviewer_ids)

        if not reviewers or any(
            not isinstance(item, str) or not item.strip()
            for item in reviewers
        ):
            raise ValueError("Invalid authorized reviewers.")

        self._recruitment = recruitment_service
        self._authorized_reviewers = reviewers

    def evaluate_review(
        self,
        applicant: Applicant,
        review: VodReview,
        authenticated_reviewer_id: str,
    ) -> dict[str, object]:
        """Validate a review and report its admission outcome."""
        if not isinstance(applicant, Applicant):
            raise TypeError("An Applicant instance is required.")

        if not isinstance(review, VodReview):
            raise TypeError("A VodReview instance is required.")

        self._validate_reviewer(
            review.reviewer_id,
            authenticated_reviewer_id,
        )

        if review.applicant_id != applicant.applicant_id:
            raise ValueError(
                "The review belongs to a different applicant."
            )

        if applicant.vod_reference is None:
            raise ValueError("The applicant has no VOD reference.")

        if review.vod_reference != applicant.vod_reference:
            raise ValueError(
                "The review does not match the applicant VOD."
            )

        preselection = self._recruitment.preselect(applicant)

        if not preselection["eligible_for_vod_review"]:
            raise ValueError(
                "The applicant is not eligible for VOD review."
            )

        next_steps = {
            ReviewDecision.APPROVED: "start_training",
            ReviewDecision.MORE_EVIDENCE: "submit_additional_vod",
            ReviewDecision.REJECTED: "follow_guidance",
        }

        return {
            "applicant_id": applicant.applicant_id,
            "reviewer_id": review.reviewer_id,
            "vod_reference": review.vod_reference,
            "classification": preselection["classification"],
            "decision": review.decision.value,
            "admission_approved": review.is_approved,
            "next_step": next_steps[review.decision],
            "scores": asdict(review.scores),
            "feedback": review.feedback,
        }

    def _validate_reviewer(
        self,
        review_reviewer_id: str,
        authenticated_reviewer_id: str,
    ) -> None:
        """Check the provided reviewer identity and permissions."""
        if authenticated_reviewer_id not in self._authorized_reviewers:
            raise PermissionError(
                "The reviewer is not authorized."
            )

        if review_reviewer_id != authenticated_reviewer_id:
            raise PermissionError(
                "The review identity does not match the reviewer."
            )
