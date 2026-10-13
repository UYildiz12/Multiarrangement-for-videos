"""Hosted set-cover fusion: the 'auto' default picks max-normalized fusion for once-covered schedules and
scale-aligned fusion when pairs repeat."""
import numpy as np

from ma_core import fuse_setcover
from ma_core.lift_weakest import TrialArrangement

FANO = [[0, 1, 2], [0, 3, 4], [0, 5, 6], [1, 3, 5], [1, 4, 6], [2, 3, 6], [2, 4, 5]]


def _trials(blocks, seed=0):
    rng = np.random.default_rng(seed)
    points = rng.normal(size=(7, 2))
    out = []
    for i, B in enumerate(blocks):
        scale = 0.5 + 0.1 * i  # layouts at different scales, as when arena use varies
        out.append(TrialArrangement(subset=list(B), positions={j: tuple(scale * points[j]) for j in B},
                                    arena_center=(0.0, 0.0), arena_radius=1.0))
    return out


def test_auto_matches_max_when_pairs_are_shown_once():
    trials = _trials(FANO)
    auto, _ = fuse_setcover(7, trials)
    explicit, _ = fuse_setcover(7, trials, weight_mode="max")
    assert np.allclose(auto, explicit)


def test_auto_matches_rms_when_pairs_repeat():
    trials = _trials(FANO + FANO)
    auto, _ = fuse_setcover(7, trials)
    explicit, _ = fuse_setcover(7, trials, weight_mode="rms")
    assert np.allclose(auto, explicit)
