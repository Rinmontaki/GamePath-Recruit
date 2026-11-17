
"""Depth-first traversal for GamePath Recruit."""

from collections.abc import Iterable

from backend.structures.graph import DirectedWeightedGraph


def dfs(
    graph: DirectedWeightedGraph,
    granted_requirements: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return reachable node IDs in depth-first order."""
    granted = frozenset(granted_requirements)

    if not graph.can_enter(granted):
        raise PermissionError(
            "Recruiter admission is required to enter the graph."
        )

    start = graph.entry_node
    graph.get_node(start)

    stack = [start]
    visited: set[str] = set()
    traversal: list[str] = []

    while stack:
        current = stack.pop()

        if current in visited:
            continue

        visited.add(current)
        traversal.append(current)

        edges = graph.available_edges(current, granted)

        for edge in reversed(edges):
            if edge.target not in visited:
                stack.append(edge.target)

    return tuple(traversal)
