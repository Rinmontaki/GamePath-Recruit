
"""Dijkstra shortest-path algorithm for GamePath Recruit."""

import heapq
from collections.abc import Iterable
from dataclasses import dataclass

from backend.structures.graph import (
    DirectedWeightedGraph,
    GraphEdge,
)


@dataclass(frozen=True)
class PathResult:
    """Represent a valid minimum-cost preparation route."""

    nodes: tuple[str, ...]
    activities: tuple[str, ...]
    total_hours: float


def dijkstra(
    graph: DirectedWeightedGraph,
    target: str,
    granted_requirements: Iterable[str] = (),
) -> PathResult | None:
    """Find the minimum-cost path from entry to target."""
    granted = frozenset(granted_requirements)

    if not graph.can_enter(granted):
        raise PermissionError(
            "Recruiter admission is required to enter the graph."
        )

    start = graph.entry_node

    graph.get_node(start)
    graph.get_node(target)

    distances: dict[str, float] = {start: 0.0}
    previous: dict[str, tuple[str, GraphEdge]] = {}

    priority_queue: list[tuple[float, str]] = [
        (0.0, start)
    ]

    while priority_queue:
        current_cost, current = heapq.heappop(
            priority_queue
        )

        if current_cost > distances[current]:
            continue

        if current == target:
            break

        for edge in graph.available_edges(current, granted):
            new_cost = current_cost + edge.weight_hours
            neighbor = edge.target

            if new_cost < distances.get(
                neighbor, float("inf")
            ):
                distances[neighbor] = new_cost
                previous[neighbor] = (current, edge)

                heapq.heappush(
                    priority_queue,
                    (new_cost, neighbor),
                )

    if target not in distances:
        return None

    return _reconstruct_path(
        start,
        target,
        distances[target],
        previous,
    )


def _reconstruct_path(
    start: str,
    target: str,
    total_hours: float,
    previous: dict[str, tuple[str, GraphEdge]],
) -> PathResult:
    """Recover the ordered nodes and activities."""
    nodes = [target]
    activities = []
    current = target

    while current != start:
        parent, edge = previous[current]

        nodes.append(parent)
        activities.append(edge.activity)
        current = parent

    nodes.reverse()
    activities.reverse()

    return PathResult(
        nodes=tuple(nodes),
        activities=tuple(activities),
        total_hours=total_hours,
    )
