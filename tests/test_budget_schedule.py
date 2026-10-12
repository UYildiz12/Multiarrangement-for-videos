"""Fixed schedules with a chosen number of trials (create_batches(..., n_trials=...))."""
import itertools

import pytest

import multiarrangement as ma
from multiarrangement.core.budget import budget_schedule
from multiarrangement.core.schedule_cache import load_indexed_schedule


def _pairs(blocks):
    return {p for b in blocks for p in itertools.combinations(sorted(b), 2)}


@pytest.mark.parametrize("factor", [1.5, 2.0])
def test_budget_schedule_covers_every_pair_with_exact_count(factor):
    v, k = 24, 6
    compact = load_indexed_schedule(v, k, mode="compact")
    target = int(round(factor * len(compact)))
    blocks = budget_schedule(v, k, target, seed=7)
    assert len(blocks) == target
    assert all(len(set(b)) == k and 0 <= min(b) and max(b) < v for b in blocks)
    assert len(_pairs(blocks)) == v * (v - 1) // 2
    assert blocks == budget_schedule(v, k, target, seed=7)


def test_budget_schedule_needs_the_compact_count():
    compact = load_indexed_schedule(24, 6, mode="compact")
    with pytest.raises(ValueError):
        budget_schedule(24, 6, len(compact) - 1)


def test_create_batches_n_trials():
    batches = ma.create_batches(24, 6, n_trials=40, seed=3)
    assert len(batches) == 40
    assert len(_pairs(batches)) == 24 * 23 // 2
    with pytest.raises(ValueError):
        ma.create_batches(24, 6, n_trials=40, max_extra_fraction=0.25)
    with pytest.raises(ValueError):
        ma.create_batches(24, 6, n_trials=40, algorithm="hybrid")


@pytest.mark.parametrize("v,k,target", [(7, 3, 14), (9, 3, 24), (7, 3, 35), (36, 8, 54)])
def test_budget_schedule_repeats_no_trial(v, k, target):
    for seed in (1, 2, 3):
        blocks = budget_schedule(v, k, target, seed=seed)
        assert len(blocks) == target
        assert len({tuple(sorted(b)) for b in blocks}) == target
        assert len(_pairs(blocks)) == v * (v - 1) // 2


def test_budget_schedule_picks_the_lower_average_variance():
    # (80,8): the compact cover has 122 trials. At 244 trials stacking a relabelled copy of it shows every pair at
    # least twice; at 183 trials the flatter 136-trial cover extended by greedy trials is the better candidate.
    def lam(blocks):
        c = {}
        for b in blocks:
            for p in itertools.combinations(sorted(b), 2):
                c[p] = c.get(p, 0) + 1
        return c
    two = lam(budget_schedule(80, 8, 244, seed=1))
    assert len(two) == 80 * 79 // 2 and min(two.values()) >= 2
    one_half = lam(budget_schedule(80, 8, 183, seed=1))
    assert len(one_half) == 80 * 79 // 2 and max(one_half.values()) <= 3
    with pytest.raises(ValueError):
        budget_schedule(7, 3, 36)
