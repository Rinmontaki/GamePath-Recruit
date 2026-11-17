
"""Represent human VOD evaluations in GamePath Recruit."""

from dataclasses import dataclass, fields
from enum import Enum


class ReviewDecision(str, Enum):
    """Possible outcomes of a human VOD review."""

    APPROVED = "approved"
    MORE_EVIDENCE = "more_evidence"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class SkillScores:
    """Store competitive skill scores on a 1-to-5 scale."""

    aim: int
    game_sense: int
    rotations: int
    macro: int
    micro: int
    communication: int

    def __post_init__(self) -> None:
        """Validate all skill ratings."""
        for field in fields(self):
            score = getattr(self, field.name)

            if type(score) is not int or not 1 <= score <= 5:
                raise ValueError(
                    f"{field.name} must be an integer from 1 to 5."
                )


@dataclass(frozen=True, slots=True)
class VodReview:
    """Record an explicitly assigned human evaluation."""

    applicant_id: str
    reviewer_id: str
    vod_reference: str
    scores: SkillScores
    decision: ReviewDecision
    feedback: str

    def __post_init__(self) -> None:
        """Validate the review record."""
        required_text = (
            "applicant_id",
            "reviewer_id",
            "vod_reference",
            "feedback",
        )

        for field_name in required_text:
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Invalid required field: {field_name}"
                )

        if not isinstance(self.scores, SkillScores):
            raise TypeError("A SkillScores instance is required.")

        if not isinstance(self.decision, ReviewDecision):
            raise TypeError("Invalid review decision.")

    @property
    def is_approved(self) -> bool:
        """Report the recorded human decision."""
        return self.decision is ReviewDecision.APPROVED
