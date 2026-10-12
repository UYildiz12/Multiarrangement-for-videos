from __future__ import annotations

from collections import Counter

from coverlib.constructions import projective_plane
from coverlib.excess import (
    analyze_excess_target,
    graph_from_ideal_schedule,
    realize_degree_sequence,
)


def test_one_point_extension_excess_arithmetic_matches_certificate():
    target = analyze_excess_target(58, 8, 66)

    assert target.representation == "excess"
    assert target.graph_edge_count == 195
    assert target.degree_residue == 6
    assert Counter(target.degree_sequence) == Counter({6: 52, 13: 6})
    assert target.graphical
    assert target.arithmetic_feasible
    edges = realize_degree_sequence(target.degree_sequence)
    assert edges is not None
    assert len(edges) == 195


def test_exact_design_has_empty_excess_graph():
    representation, edges = graph_from_ideal_schedule(
        7,
        3,
        projective_plane(2),
    )

    assert representation == "excess"
    assert edges == ()
