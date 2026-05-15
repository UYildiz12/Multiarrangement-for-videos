from __future__ import annotations

from itertools import combinations

from coverlib.balanced import balance_sort_key, normalized_balance_metrics


def _all_pairs(v: int) -> list[list[int]]:
    return [[i, j] for i, j in combinations(range(v), 2)]


def test_normalized_metrics_are_zero_for_ideal_pair_distribution():
    blocks = _all_pairs(6) + [[0, 1], [0, 2], [0, 3]]

    metrics = normalized_balance_metrics(6, 2, blocks)

    assert metrics.complete is True
    assert metrics.lambda_max == 2
    assert metrics.ideal_lambda_max == 2
    assert metrics.lambda_max_ratio == 1.0
    assert metrics.normalized_pair_sumsq_excess == 0.0


def test_normalized_metrics_penalize_concentrated_repeated_pairs():
    evenly_spread = _all_pairs(6) + [[0, 1], [0, 2], [0, 3]]
    concentrated = _all_pairs(6) + [[0, 1], [0, 1], [0, 1]]

    even_metrics = normalized_balance_metrics(6, 2, evenly_spread)
    concentrated_metrics = normalized_balance_metrics(6, 2, concentrated)

    assert even_metrics.lambda_max_ratio == 1.0
    assert concentrated_metrics.lambda_max_ratio == 2.0
    assert even_metrics.normalized_pair_sumsq_excess == 0.0
    assert concentrated_metrics.normalized_pair_sumsq_excess > 0.0
    assert balance_sort_key(6, 2, evenly_spread) < balance_sort_key(6, 2, concentrated)


def test_normalized_metrics_report_missing_pair_fraction_as_hard_failure():
    blocks = [[0, 1], [0, 2], [0, 3]]

    metrics = normalized_balance_metrics(6, 2, blocks)

    assert metrics.complete is False
    assert metrics.missing_pairs == 12
    assert metrics.missing_pair_fraction == 12 / 15
    assert balance_sort_key(6, 2, blocks)[0] == 1
