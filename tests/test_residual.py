from __future__ import annotations

from coverlib.certificates import balanced_sort_key, certify_schedule
from coverlib.residual import exact_neighborhood_repair, generate_residual_candidates, solve_residual_exact


FANO = (
    (0, 1, 2),
    (0, 3, 4),
    (0, 5, 6),
    (1, 3, 5),
    (1, 4, 6),
    (2, 3, 6),
    (2, 4, 5),
)


def test_enumerated_but_truncated_pool_is_not_exhaustive():
    # All 35 triples are enumerated, but only five survive the pool limit.
    candidates, exhaustive = generate_residual_candidates(
        7, 3, (), [1] * 21, [1] * 21, candidate_limit=5,
    )
    assert len(candidates) == 5
    assert not exhaustive
    candidates, exhaustive = generate_residual_candidates(
        7, 3, (), [1] * 21, [1] * 21, candidate_limit=35,
    )
    assert len(candidates) == 35
    assert exhaustive


def test_interrupted_exhaustive_search_does_not_return_a_certificate():
    assert solve_residual_exact(
        7, 3, (), blocks_to_add=7, lambda_cap=1, node_limit=0,
    ) is None


def test_exact_residual_builds_fano_plane_from_empty_core():
    result = solve_residual_exact(
        7,
        3,
        (),
        blocks_to_add=7,
        lambda_cap=1,
        time_limit_seconds=2.0,
    )

    assert result is not None
    assert result.exhaustive_pool
    certificate = certify_schedule(7, 3, result.blocks)
    assert certificate.complete
    assert certificate.lambda_max == 1
    assert certificate.b == 7


def test_exact_neighborhood_repair_strictly_lowers_lambda():
    concentrated = (
        (0, 2, 5),
        (1, 3, 4),
        (0, 1, 3),
        (1, 2, 3),
        (2, 4, 5),
        (1, 3, 5),
        (0, 3, 4),
    )
    result = exact_neighborhood_repair(
        6,
        3,
        concentrated,
        max_removed_blocks=2,
        time_limit_seconds=2.0,
    )

    assert result is not None
    before = certify_schedule(6, 3, concentrated)
    after = certify_schedule(6, 3, result.blocks)
    assert before.lambda_max == 4
    assert after.lambda_max == 3
    assert balanced_sort_key(6, 3, result.blocks) < balanced_sort_key(
        6,
        3,
        concentrated,
    )
