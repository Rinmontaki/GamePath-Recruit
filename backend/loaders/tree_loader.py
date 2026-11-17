
"""Build a binary decision tree from a JSON file."""

import json
from pathlib import Path

from backend.structures.node import (
    Condition,
    DecisionNode,
    ResultNode,
    TreeNode,
)


def load_tree(file_path: str | Path) -> TreeNode:
    """Load and validate a binary tree from JSON."""
    with Path(file_path).open("r", encoding="utf-8") as file:
        tree_data = json.load(file)

    return _build_node(tree_data, set())


def _build_node(
    node_data: object,
    visited_ids: set[str],
) -> TreeNode:
    """Recursively build a decision or result node."""
    if not isinstance(node_data, dict):
        raise ValueError("Each node must be a JSON object.")

    node_id = _required_text(node_data, "node_id")

    if node_id in visited_ids:
        raise ValueError(f"Duplicate node ID: {node_id}")

    visited_ids.add(node_id)

    node_type = node_data.get("type")

    if node_type == "decision":
        return _build_decision(node_data, node_id, visited_ids)

    if node_type == "result":
        return _build_result(node_data, node_id)

    raise ValueError(f"Unknown node type: {node_type}")


def _build_decision(
    node_data: dict,
    node_id: str,
    visited_ids: set[str],
) -> DecisionNode:
    """Build a decision with exactly two children."""
    question = _required_text(node_data, "question")

    condition_data = node_data.get("condition")

    if not isinstance(condition_data, dict):
        raise ValueError(
            f"Node {node_id} requires a valid condition."
        )

    condition = _build_condition(condition_data)

    if "left" not in node_data or "right" not in node_data:
        raise ValueError(
            f"Node {node_id} requires left and right children."
        )

    left_child = _build_node(node_data["left"], visited_ids)
    right_child = _build_node(node_data["right"], visited_ids)

    return DecisionNode(
        node_id=node_id,
        question=question,
        condition=condition,
        left=left_child,
        right=right_child,
    )


def _build_condition(condition_data: dict) -> Condition:
    """Validate and construct a condition."""
    field = _required_text(condition_data, "field")
    operator = _required_text(condition_data, "operator")
    value = condition_data.get("value")

    if operator not in {">=", "=="}:
        raise ValueError(f"Unsupported operator: {operator}")

    if type(value) not in (str, int, float, bool):
        raise ValueError(f"Invalid value for condition: {field}")

    if isinstance(value, str) and not value.strip():
        raise ValueError(f"Empty condition value: {field}")

    return Condition(
        field=field,
        operator=operator,
        value=value,
    )


def _build_result(
    node_data: dict,
    node_id: str,
) -> ResultNode:
    """Build a terminal node without children."""
    if "left" in node_data or "right" in node_data:
        raise ValueError(
            f"Result node {node_id} cannot have children."
        )

    return ResultNode(
        node_id=node_id,
        status=_required_text(node_data, "status"),
        classification=_required_text(
            node_data, "classification"
        ),
        reason=_required_text(node_data, "reason"),
        recommendation=_required_text(
            node_data, "recommendation"
        ),
    )


def _required_text(data: dict, field: str) -> str:
    """Read and validate a required text field."""
    value = data.get(field)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid field: {field}")

    return value.strip()
