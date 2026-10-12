"""Local adaptive runs express distances in arena-radius units, independent of the screen size."""
import importlib.util
import sys
from unittest import mock

import numpy as np

# The interface modules import pygame and OpenCV at module level; the method tested here uses neither.
for _name in ("pygame", "cv2"):
    if importlib.util.find_spec(_name) is None:
        sys.modules.setdefault(_name, mock.MagicMock())

from multiarrangement.adaptive.adaptive_experiment import AdaptiveConfig, AdaptiveMultiarrangementExperiment  # noqa: E402


def _experiment(n):
    exp = AdaptiveMultiarrangementExperiment.__new__(AdaptiveMultiarrangementExperiment)
    exp.n = n
    exp.video_names = [f"v{i}" for i in range(n)]
    exp.trials = []
    exp.config = AdaptiveConfig(use_inverse_mds=False)
    exp.seen = np.zeros(n, dtype=bool)
    exp.recent = np.zeros(n)
    exp.inclusion_counts = np.zeros(n, dtype=int)
    exp.D_est = np.zeros((n, n))
    exp.W_raw = np.zeros((n, n))
    exp.W_sched = np.zeros((n, n))
    return exp


def _run(scale):
    rng = np.random.default_rng(3)
    exp = _experiment(6)
    center, radius = (700.0 * scale, 500.0 * scale), 355.0 * scale
    for subset in ([0, 1, 2, 3], [2, 3, 4, 5], [0, 2, 4, 5]):
        exp.current_subset_indices = subset
        pts = rng.uniform(-0.8, 0.8, size=(len(subset), 2))
        positions = {f"v{i}": (center[0] + radius * p[0], center[1] + radius * p[1]) for i, p in zip(subset, pts)}
        exp.record_arrangement(positions, arena_center=center, arena_radius=radius)
    return exp


def test_estimates_and_evidence_do_not_depend_on_screen_size():
    small, large = _run(1.0), _run(2.0)
    assert np.allclose(small.D_est, large.D_est)
    assert np.allclose(small.W_raw, large.W_raw)
    assert np.allclose(small.W_sched, large.W_sched)
