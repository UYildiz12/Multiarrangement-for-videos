from __future__ import annotations

import coverlib.symmetry as symmetry


FANO = [
    (0, 1, 2),
    (0, 3, 4),
    (0, 5, 6),
    (1, 3, 5),
    (1, 4, 6),
    (2, 3, 6),
    (2, 4, 5),
]


def test_symmetry_wrapper_returns_certified_strict_candidate(monkeypatch):
    plan = {
        "model": "plain",
        "s": 1,
        "g": 7,
        "m": 1,
        "r": 0,
        "bprime": 7,
    }
    monkeypatch.setattr(symmetry, "enumerate_anneal_plans", lambda *args: [plan])
    monkeypatch.setattr(
        symmetry,
        "anneal_plan",
        lambda *args: ([(0, 1, 2)], [], FANO, None, None, None),
    )

    candidates = symmetry.search_symmetry_candidates(
        7,
        3,
        max_blocks=7,
        budget_seconds=1.0,
    )

    assert len(candidates) == 1
    assert candidates[0].blocks == tuple(sorted(FANO))
    assert candidates[0].lambda_cap == 1
    assert candidates[0].model == "plain"


def test_zero_budget_is_a_clean_bounded_search_miss():
    assert symmetry.search_symmetry_candidates(
        7,
        3,
        max_blocks=7,
        budget_seconds=0.0,
    ) == ()
