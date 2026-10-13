"""Default fusion estimator for fixed (set-cover) schedules.

``'auto'`` resolves to scale-aligned fusion (``'rms'``) when the schedule shows pairs on average at least
``AUTO_MIN_VIEWS_PER_PAIR`` times, and to per-trial max-normalized fusion (``'max'``) otherwise.

Scale-aligned fusion fits each trial's scale from the pairs it shares with other trials. When most pairs are shown
once, as in compact schedules, few pairs link the trials, so most trial scales are not estimated and stay at the arena
scale. That is correct when participants spread every layout over the arena, but not when the share of the arena they
use varies from trial to trial. In the simulations of the accompanying paper (simulations/sim_arena.py), with
participants who fill the arena, use 70-100% of it or use 40-100% of it, this rule had the smallest mean excess error
over the better estimator of the rules tested, below always using scale-aligned fusion; schedules with 1.5 or 2
times the compact number of trials always resolve to scale-aligned fusion, which won in every condition there.
"""
from math import comb
from typing import Iterable, Sequence

AUTO_MIN_VIEWS_PER_PAIR = 1.1


def mean_views_per_pair(n_items: int, subsets: Iterable[Sequence[int]]) -> float:
    """Total number of pair views in the trials divided by the number of pairs."""
    pairs = comb(int(n_items), 2)
    if pairs == 0:
        return 0.0
    return sum(comb(len(set(s)), 2) for s in subsets) / pairs


def resolve_setcover_weight_mode(mode: str, n_items: int, subsets: Iterable[Sequence[int]]) -> str:
    """Return the fusion estimator to use: ``mode`` itself unless it is ``'auto'``."""
    if str(mode) != "auto":
        return str(mode)
    return "rms" if mean_views_per_pair(n_items, subsets) >= AUTO_MIN_VIEWS_PER_PAIR else "max"
