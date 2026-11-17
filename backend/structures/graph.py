
"""Directed weighted graph for GamePath Recruit."""

import math
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class GraphNode:
    """Represent a training state or opportunity."""

    node_id: str
    node_type: str
    label: str
    completed: dict[str, bool] | None = None


@dataclass(frozen=True)
class GraphEdge:
    """Represent a directed transition with a cost."""

    source: str
    target: str
    activity: str
    weight_hours: float
    requirements: tuple[str, ...] = ()


class DirectedWeightedGraph:
    """Store a directed weighted graph using adjacency lists."""

    def __init__(
        self,
        graph_id: str,
        entry_node: str,
        entry_requirements: tuple[str, ...] = (),
        weight_unit: str = "hours_of_preparation",
    ) -> None:
        self.graph_id = graph_id
        self.entry_node = entry_node
        self.entry_requirements = entry_requirements
        self.weight_unit = weight_unit

        self._nodes: dict[str, GraphNode] = {}
        self._adjacency: dict[str, list[GraphEdge]] = {}

    def add_node(self, node: GraphNode) -> None:
        """Register a unique node in the graph."""
        if not node.node_id.strip():
            raise ValueError("Node ID cannot be empty.")

        if node.node_id in self._nodes:
            raise ValueError(
                f"Duplicate node: {node.node_id}"
            )

        self._nodes[node.node_id] = node
        self._adjacency[node.node_id] = []

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed edge between existing nodes."""
        if edge.source not in self._nodes:
            raise ValueError(
                f"Unknown source node: {edge.source}"
            )

        if edge.target not in self._nodes:
            raise ValueError(
                f"Unknown target node: {edge.target}"
            )

        if (
            type(edge.weight_hours) not in (int, float)
            or not math.isfinite(edge.weight_hours)
            or edge.weight_hours < 0
        ):
            raise ValueError(
                "Edge weight must be a finite nonnegative number."
            )

        if any(
            existing.target == edge.target
            for existing in self._adjacency[edge.source]
        ):
            raise ValueError(
                f"Duplicate edge: {edge.source} -> {edge.target}"
            )

        self._adjacency[edge.source].append(edge)

    def get_node(self, node_id: str) -> GraphNode:
        """Retrieve a node by its identifier."""
        if node_id not in self._nodes:
            raise ValueError(f"Unknown node: {node_id}")

        return self._nodes[node_id]

    def outgoing_edges(
        self,
        node_id: str,
    ) -> tuple[GraphEdge, ...]:
        """Return every outgoing edge, including restricted ones."""
        self.get_node(node_id)
        return tuple(self._adjacency[node_id])

    def available_edges(
        self,
        node_id: str,
        granted_requirements: Iterable[str] = (),
    ) -> tuple[GraphEdge, ...]:
        """Return edges whose requirements are satisfied."""
        granted = set(granted_requirements)

        return tuple(
            edge
            for edge in self.outgoing_edges(node_id)
            if set(edge.requirements).issubset(granted)
        )

    def can_enter(
        self,
        granted_requirements: Iterable[str] = (),
    ) -> bool:
        """Check whether the graph entry requirements are met."""
        granted = set(granted_requirements)

        return set(self.entry_requirements).issubset(granted)

    def validate(self) -> None:
        """Verify that the configured entry node exists."""
        if self.entry_node not in self._nodes:
            raise ValueError(
                f"Unknown entry node: {self.entry_node}"
            )

    @property
    def node_count(self) -> int:
        """Return the number of registered nodes."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Return the total number of directed edges."""
        return sum(
            len(edges)
            for edges in self._adjacency.values()
        )
