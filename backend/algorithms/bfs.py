
"""Breadth-first traversal for GamePath Recruit."""

from collections import deque
from collections.abc import Iterable

from backend.structures.graph import DirectedWeightedGraph


def bfs(
    graph: DirectedWeightedGraph,
    granted_requirements: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return reachable node IDs in breadth-first order."""
    granted = frozenset(granted_requirements)

    if not graph.can_enter(granted):
        raise PermissionError(
            "Recruiter admission is required to enter the graph."
        )

    start = graph.entry_node
    graph.get_node(start)

    queue = deque([start])
    visited = {start}
    traversal = []

    while queue:
        current = queue.popleft()
        traversal.append(current)

        for edge in graph.available_edges(current, granted):
            neighbor = edge.target

            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return tuple(traversal)
