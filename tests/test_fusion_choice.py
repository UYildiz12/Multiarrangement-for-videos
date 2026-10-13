"""The 'auto' fusion default: scale-aligned when pairs repeat on average at least 1.1 times, max-normalized otherwise."""
from itertools import combinations

from multiarrangement.core.fusion_choice import (AUTO_MIN_VIEWS_PER_PAIR, mean_views_per_pair,
                                                 resolve_setcover_weight_mode)
from multiarrangement.core.schedule_cache import load_indexed_schedule


def test_explicit_modes_pass_through():
    for mode in ("max", "rms", "k2012"):
        assert resolve_setcover_weight_mode(mode, 10, [[0, 1, 2]]) == mode


def test_mean_views_counts_pair_views():
    # the 7 lines of the Fano plane show each of the 21 pairs exactly once
    fano = [[0, 1, 2], [0, 3, 4], [0, 5, 6], [1, 3, 5], [1, 4, 6], [2, 3, 6], [2, 4, 5]]
    assert mean_views_per_pair(7, fano) == 1.0
    assert mean_views_per_pair(7, fano + fano) == 2.0
    assert resolve_setcover_weight_mode("auto", 7, fano) == "max"
    assert resolve_setcover_weight_mode("auto", 7, fano + fano) == "rms"


def test_threshold_is_inclusive():
    v = 5
    pairs = [list(p) for p in combinations(range(v), 2)]  # 10 trials of 2 items, each pair once
    extra = pairs[:1]  # one repeated pair: 11 views over 10 pairs = 1.1
    assert mean_views_per_pair(v, pairs + extra) >= AUTO_MIN_VIEWS_PER_PAIR
    assert resolve_setcover_weight_mode("auto", v, pairs + extra) == "rms"


def test_compact_schedules_mostly_resolve_to_max():
    # large compact covers show nearly every pair once; a doubled one shows each pair at least twice
    comp = load_indexed_schedule(99, 6, mode="compact")
    assert resolve_setcover_weight_mode("auto", 99, comp) == "max"
    assert resolve_setcover_weight_mode("auto", 99, comp + comp) == "rms"
