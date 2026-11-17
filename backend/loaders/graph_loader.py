
"""Load a directed weighted graph from a JSON file."""

import json
from pathlib import Path

from backend.structures.graph import (
    DirectedWeightedGraph,
    GraphEdge,
    GraphNode,
)


def load_graph(file_path: str | Path) -> DirectedWeightedGraph:
    """Load and construct a directed weighted graph."""
    with Path(file_path).open("r", encoding="utf-8") as file:
        graph_data = json.load(file)

    if not isinstance(graph_data, dict):
        raise ValueError("Graph data must be a JSON object.")

    if graph_data.get("directed") is not True:
        raise ValueError("The graph must be directed.")

    if graph_data.get("weighted") is not True:
        raise ValueError("The graph must be weighted.")

    graph = DirectedWeightedGraph(
        graph_id=_required_text(graph_data, "graph_id"),
        entry_node=_required_text(graph_data, "entry_node"),
        entry_requirements=_read_requirements(
            graph_data.get("entry_requirements", [])
        ),
        weight_unit=_required_text(graph_data, "weight_unit"),
    )

    nodes = _required_list(graph_data, "nodes")
    edges = _required_list(graph_data, "edges")

    if not nodes:
        raise ValueError("The graph must contain nodes.")

    for node_data in nodes:
        graph.add_node(_build_node(node_data))

    for edge_data in edges:
        graph.add_edge(_build_edge(edge_data))

    graph.validate()

    return graph


def _build_node(node_data: object) -> GraphNode:
    """Build and validate a graph node."""
    if not isinstance(node_data, dict):
        raise ValueError("Each node must be a JSON object.")

    completed = node_data.get("completed")

    if completed is not None:
        if not isinstance(completed, dict):
            raise ValueError("Completed skills must be an object.")

        if any(
            not isinstance(skill, str)
            or not skill.strip()
            or type(value) is not bool
            for skill, value in completed.items()
        ):
            raise ValueError("Invalid completed skills.")

    return GraphNode(
        node_id=_required_text(node_data, "id"),
        node_type=_required_text(node_data, "type"),
        label=_required_text(node_data, "label"),
        completed=completed,
    )


def _build_edge(edge_data: object) -> GraphEdge:
    """Build a directed edge with weight and requirements."""
    if not isinstance(edge_data, dict):
        raise ValueError("Each edge must be a JSON object.")

    return GraphEdge(
        source=_required_text(edge_data, "from"),
        target=_required_text(edge_data, "to"),
        activity=_required_text(edge_data, "activity"),
        weight_hours=edge_data.get("weight_hours"),
        requirements=_read_requirements(
            edge_data.get("requirements", [])
        ),
    )


def _read_requirements(value: object) -> tuple[str, ...]:
    """Validate and return requirement identifiers."""
    if not isinstance(value, list):
        raise ValueError("Requirements must be a list.")

    if any(
        not isinstance(item, str) or not item.strip()
        for item in value
    ):
        raise ValueError("Invalid requirement identifier.")

    if len(value) != len(set(value)):
        raise ValueError("Duplicate requirements are not allowed.")

    return tuple(value)


def _required_list(data: dict, field: str) -> list:
    """Read a required JSON list."""
    value = data.get(field)

    if not isinstance(value, list):
        raise ValueError(f"Missing or invalid list: {field}")

    return value


def _required_text(data: dict, field: str) -> str:
    """Read a required non-empty text field."""
    value = data.get(field)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid field: {field}")

    return value.strip()
