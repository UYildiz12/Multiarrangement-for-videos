"""Arithmetic filters and graph models for ideal-concurrence schedules."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set, Tuple

from .certificates import ideal_concurrence_profile


Edge = Tuple[int, int]


@dataclass(frozen=True)
class ExcessTarget:
    v: int
    k: int
    b: int
    baseline_concurrence: int
    high_pair_count: int
    representation: str
    graph_edge_count: int
    degree_residue: int
    degree_sequence: Tuple[int, ...]
    graphical: bool
    arithmetic_feasible: bool


def is_graphical(degrees: Sequence[int]) -> bool:
    """Havel-Hakimi graphicality test for a simple undirected graph."""
    work = [int(degree) for degree in degrees]
    if any(degree < 0 or degree >= len(work) for degree in work):
        return False
    if sum(work) % 2:
        return False
    while True:
        work = sorted((degree for degree in work if degree), reverse=True)
        if not work:
            return True
        degree = work.pop(0)
        if degree > len(work):
            return False
        for index in range(degree):
            work[index] -= 1
            if work[index] < 0:
                return False


def _permitted_degrees(v: int, modulus: int, residue: int) -> Tuple[int, ...]:
    return tuple(
        degree
        for degree in range(v)
        if degree % modulus == residue % modulus
    )


def balanced_residue_degree_sequence(
    v: int,
    total_degree: int,
    *,
    modulus: int,
    residue: int,
) -> Optional[Tuple[int, ...]]:
    """Find the most even permitted degree sequence with the required sum."""
    if total_degree < 0 or total_degree > v * (v - 1) or total_degree % 2:
        return None
    permitted = _permitted_degrees(v, modulus, residue)
    if not permitted:
        return None

    # Dynamic programming stores the lexicographically smallest descending
    # sequence for each reachable (vertex count, sum).  The final comparison
    # prefers the smallest maximum and then the full descending profile.
    states = {(0, 0): tuple()}
    for count in range(v):
        next_states = {}
        for (_, current_sum), sequence in states.items():
            for degree in permitted:
                new_sum = current_sum + degree
                remaining = v - count - 1
                if new_sum > total_degree:
                    continue
                if new_sum + remaining * permitted[0] > total_degree:
                    continue
                if new_sum + remaining * permitted[-1] < total_degree:
                    continue
                candidate = tuple(sorted(sequence + (degree,), reverse=True))
                key = (count + 1, new_sum)
                incumbent = next_states.get(key)
                if incumbent is None or candidate < incumbent:
                    next_states[key] = candidate
        states = next_states
        if not states:
            return None
    return states.get((v, total_degree))


def analyze_excess_target(v: int, k: int, b: int) -> ExcessTarget:
    """Return the sparse excess/leave arithmetic model for ideal balance."""
    if not 2 <= k <= v or b < 0:
        raise ValueError("invalid schedule parameters")
    pair_count = math.comb(v, 2)
    pair_slots = b * math.comb(k, 2)
    baseline, high_pair_count = divmod(pair_slots, pair_count)
    excess_edges = high_pair_count
    leave_edges = pair_count - high_pair_count
    if excess_edges <= leave_edges:
        representation = "excess"
        edge_count = excess_edges
        residue = (-baseline * (v - 1)) % (k - 1)
    else:
        representation = "leave"
        edge_count = leave_edges
        residue = ((baseline + 1) * (v - 1)) % (k - 1)

    degree_sequence = balanced_residue_degree_sequence(
        v,
        2 * edge_count,
        modulus=k - 1,
        residue=residue,
    )
    graphical = degree_sequence is not None and is_graphical(degree_sequence)
    arithmetic_feasible = (
        pair_slots >= pair_count
        and degree_sequence is not None
        and graphical
        and (b * k) >= v
    )
    return ExcessTarget(
        v=v,
        k=k,
        b=b,
        baseline_concurrence=baseline,
        high_pair_count=high_pair_count,
        representation=representation,
        graph_edge_count=edge_count,
        degree_residue=residue,
        degree_sequence=degree_sequence or tuple(),
        graphical=graphical,
        arithmetic_feasible=arithmetic_feasible,
    )


def realize_degree_sequence(degrees: Sequence[int]) -> Optional[Tuple[Edge, ...]]:
    """Construct one labeled graph realizing ``degrees`` by Havel-Hakimi."""
    if not is_graphical(degrees):
        return None
    work = [(int(degree), vertex) for vertex, degree in enumerate(degrees)]
    edges: Set[Edge] = set()
    while True:
        work.sort(key=lambda row: (-row[0], row[1]))
        degree, vertex = work[0]
        if degree == 0:
            break
        work = work[1:]
        if degree > len(work):
            return None
        for index in range(degree):
            neighbor_degree, neighbor = work[index]
            if neighbor_degree <= 0:
                return None
            edge = (vertex, neighbor) if vertex < neighbor else (neighbor, vertex)
            edges.add(edge)
            work[index] = (neighbor_degree - 1, neighbor)
    return tuple(sorted(edges))


def graph_from_ideal_schedule(
    v: int,
    k: int,
    blocks: Sequence[Sequence[int]],
) -> Tuple[str, Tuple[Edge, ...]]:
    """Extract the excess or leave graph from an ideal fixed-b schedule."""
    target = analyze_excess_target(v, k, len(blocks))
    counts = {(left, right): 0 for left in range(v) for right in range(left + 1, v)}
    for block in blocks:
        for edge in itertools.combinations(sorted(int(item) for item in block), 2):
            counts[edge] += 1
    if tuple(sorted(counts.values(), reverse=True)) != ideal_concurrence_profile(
        v,
        k,
        len(blocks),
    ):
        raise ValueError("schedule does not have the ideal concurrence profile")
    if target.representation == "excess":
        graph = tuple(
            edge
            for edge, count in counts.items()
            if count == target.baseline_concurrence + 1
        )
    else:
        graph = tuple(
            edge
            for edge, count in counts.items()
            if count == target.baseline_concurrence
        )
    return target.representation, tuple(sorted(graph))

