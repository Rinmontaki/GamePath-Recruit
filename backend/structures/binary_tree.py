
"""Evaluate player profiles using a binary decision tree."""

import math
from collections.abc import Mapping

from backend.structures.node import (
    Condition,
    DecisionNode,
    ResultNode,
    TreeNode,
)


RANK_ORDER = (
    "hierro",
    "bronce",
    "plata",
    "oro",
    "platino",
    "diamante",
    "ascendente",
    "inmortal",
    "radiante",
)


class BinaryDecisionTree:
    """Traverse a binary tree to classify an applicant."""

    def __init__(self, root: TreeNode) -> None:
        self.root = root

    def evaluate(
        self,
        profile: Mapping[str, object],
    ) -> dict[str, object]:
        """Evaluate a profile and return its decision path."""
        current_node = self.root
        decision_path = []

        while isinstance(current_node, DecisionNode):
            answer = self._check_condition(
                current_node.condition,
                profile,
            )

            decision_path.append({
                "node_id": current_node.node_id,
                "question": current_node.question,
                "answer": "Sí" if answer else "No",
            })

            current_node = (
                current_node.left
                if answer
                else current_node.right
            )

        if not isinstance(current_node, ResultNode):
            raise TypeError("The tree must end in a result node.")

        return {
            "node_id": current_node.node_id,
            "status": current_node.status,
            "classification": current_node.classification,
            "reason": current_node.reason,
            "recommendation": current_node.recommendation,
            "decision_path": decision_path,
        }

    def _check_condition(
        self,
        condition: Condition,
        profile: Mapping[str, object],
    ) -> bool:
        """Evaluate a supported condition without using eval."""
        field = condition.field

        if field not in profile:
            raise ValueError(f"Missing profile field: {field}")

        actual = profile[field]
        expected = condition.value

        if field == "daily_play_hours":
            self._validate_hours(actual)
            self._validate_hours(expected)

            return self._compare(
                actual,
                expected,
                condition.operator,
            )

        if field == "accepts_training":
            if type(actual) is not bool or type(expected) is not bool:
                raise ValueError("Training acceptance must be boolean.")

            if condition.operator != "==":
                raise ValueError("Invalid training condition operator.")

            return actual == expected

        if field == "peak_rank":
            actual_level = self._rank_level(actual)
            expected_level = self._rank_level(expected)

            return self._compare(
                actual_level,
                expected_level,
                condition.operator,
            )

        raise ValueError(f"Unsupported condition field: {field}")

    @staticmethod
    def _validate_hours(value: object) -> None:
        """Require a finite number of hours between 0 and 24."""
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not 0 <= value <= 24
        ):
            raise ValueError(
                "Daily hours must be a number between 0 and 24."
            )

    @staticmethod
    def _rank_level(rank: object) -> int:
        """Convert a VALORANT rank into its ordered level."""
        if not isinstance(rank, str):
            raise ValueError("Peak rank must be a string.")

        normalized_rank = rank.strip().casefold()

        if normalized_rank not in RANK_ORDER:
            raise ValueError(f"Unknown VALORANT rank: {rank}")

        return RANK_ORDER.index(normalized_rank)

    @staticmethod
    def _compare(
        actual: int | float,
        expected: int | float,
        operator: str,
    ) -> bool:
        """Compare values using supported operators."""
        if operator == ">=":
            return actual >= expected

        if operator == "==":
            return actual == expected

        raise ValueError(f"Unsupported operator: {operator}")
