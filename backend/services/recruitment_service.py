
"""Coordinate applicant preselection in GamePath Recruit."""

from backend.models.applicant import Applicant
from backend.structures.binary_tree import BinaryDecisionTree


class RecruitmentService:
    """Connect applicant profiles with binary tree evaluation."""

    def __init__(self, tree: BinaryDecisionTree) -> None:
        self._tree = tree

    def preselect(
        self,
        applicant: Applicant,
    ) -> dict[str, object]:
        """Evaluate an applicant and determine the next step."""
        if not isinstance(applicant, Applicant):
            raise TypeError("An Applicant instance is required.")

        result = self._tree.evaluate(applicant.to_profile())

        is_preselected = result["status"] == "preselected"

        if is_preselected:
            next_step = (
                "request_human_vod_review"
                if applicant.vod_reference is not None
                else "submit_vod"
            )
        else:
            next_step = "follow_guidance"

        return {
            "applicant_id": applicant.applicant_id,
            "game_name": applicant.game_name,
            **result,
            "eligible_for_vod_review": is_preselected,
            "next_step": next_step,
        }
