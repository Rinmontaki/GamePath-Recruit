
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Condition:
    field: str
    operator: str
    value: str | int | float | bool


@dataclass(frozen=True)
class ResultNode:
    node_id: str
    status: str
    classification: str
    reason: str
    recommendation: str

    @property
    def is_leaf(self) -> bool:
        return True


@dataclass(frozen=True)
class DecisionNode:
    node_id: str
    question: str
    condition: Condition
    left: TreeNode
    right: TreeNode

    @property
    def is_leaf(self) -> bool:
        return False


TreeNode = DecisionNode | ResultNode
