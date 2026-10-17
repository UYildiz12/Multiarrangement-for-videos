"""Hosted Lift-the-Weakest options: avoid_anchor_reuse is honoured (off by default) and arena_max is forwarded."""
import numpy as np

from app.routers.sessions import _hosted_ltw_options
from ma_core.lift_weakest import select_next_subset_lift_weakest


def test_previous_anchor_is_kept_by_default():
    opts = _hosted_ltw_options({}, {"last_anchor_pair": (0, 1)})
    assert opts["avoid_anchor_pair"] is None
    assert opts["arena_max"] == 1.0


def test_previous_anchor_is_avoided_when_enabled():
    opts = _hosted_ltw_options({"avoid_anchor_reuse": True, "arena_max": 2.0}, {"last_anchor_pair": (0, 1)})
    assert opts["avoid_anchor_pair"] == (0, 1)
    assert opts["arena_max"] == 2.0


def test_weakest_pair_anchors_the_next_trial_by_default():
    n = 6
    D = np.ones((n, n)) - np.eye(n)
    W = np.ones((n, n)) - np.eye(n)
    W[0, 1] = W[1, 0] = 0.01  # the uniquely weakest pair
    opts = _hosted_ltw_options({}, {"last_anchor_pair": (0, 1)})
    subset = select_next_subset_lift_weakest(D, W, min_size=3, max_size=3, **opts)
    assert sorted(subset[:2]) == [0, 1]
