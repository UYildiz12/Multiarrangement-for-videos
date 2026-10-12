import numpy as np

from multiarrangement.adaptive.lift_weakest import TrialArrangement, estimate_rdm_weighted_average


def _trials(points, subsets, scales):
    """Arrangements that show the true points of each subset, each at its own arbitrary scale."""
    return [TrialArrangement(subset=list(s), positions={i: (float(points[i, 0] * c), float(points[i, 1] * c)) for i in s})
            for s, c in zip(subsets, scales)]


def _true_rdm(points):
    return np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)


def _corr(a, b):
    """Correlation over the observed pairs (unobserved pairs are zero in the estimate)."""
    iu = np.triu_indices(a.shape[0], 1)
    seen = a[iu] > 0
    return float(np.corrcoef(a[iu][seen], b[iu][seen])[0, 1])


def test_linked_trials_recover_the_truth_closely_whatever_their_scales():
    rng = np.random.default_rng(1)
    points = rng.standard_normal((10, 2))
    subsets = [[0, 1, 2, 3, 4], [3, 4, 5, 6, 7], [6, 7, 8, 9, 0], [9, 0, 1, 2, 5], [1, 3, 5, 7, 9], [0, 2, 4, 6, 8]]
    for mode in ('rms', 'max', 'k2012'):
        # arrangements fill the arena, so trial scales differ moderately
        D, _ = estimate_rdm_weighted_average(10, _trials(points, subsets, [1.0, 1.2, 0.9, 1.1, 0.85, 1.15]), weight_mode=mode)
        assert _corr(D, _true_rdm(points)) > 0.99, mode


def test_equal_scales_are_recovered_exactly():
    rng = np.random.default_rng(6)
    points = rng.standard_normal((8, 2))
    subsets = [[0, 1, 2, 3], [2, 3, 4, 5], [4, 5, 6, 7], [6, 7, 0, 1], [0, 2, 4, 6]]
    D, _ = estimate_rdm_weighted_average(8, _trials(points, subsets, [1.0] * 5), weight_mode='rms')
    assert _corr(D, _true_rdm(points)) > 1 - 1e-9


def test_result_does_not_depend_on_the_iteration_cap():
    rng = np.random.default_rng(2)
    points = rng.standard_normal((9, 2))
    subsets = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 1, 2], [3, 4, 5]]
    trials = _trials(points + 0.1 * rng.standard_normal((9, 2)), subsets, [1.0, 2.0, 0.7, 1.3, 0.9, 1.1, 1.6, 0.8])
    a, _ = estimate_rdm_weighted_average(9, trials, weight_mode='rms', max_iter=1)
    b, _ = estimate_rdm_weighted_average(9, trials, weight_mode='rms', max_iter=1000)
    assert np.allclose(a, b)


def test_trials_sharing_no_pair_keep_the_arena_scale():
    rng = np.random.default_rng(3)
    points = rng.standard_normal((6, 2))
    subsets = [[0, 1, 2], [3, 4, 5]]
    D, _ = estimate_rdm_weighted_average(6, _trials(points, subsets, [1.0, 1.0]), weight_mode='rms')
    raw = _true_rdm(points)
    within = [(0, 1), (0, 2), (1, 2), (3, 4), (3, 5), (4, 5)]
    ratios = [D[i, j] / raw[i, j] for i, j in within]
    assert np.allclose(ratios, ratios[0])


def test_repeated_schedule_matches_single_schedule_without_noise():
    rng = np.random.default_rng(4)
    points = rng.standard_normal((7, 2))
    subsets = [[0, 1, 2, 3], [3, 4, 5, 6], [0, 2, 4, 6]]
    once, _ = estimate_rdm_weighted_average(7, _trials(points, subsets, [1, 1, 1]), weight_mode='rms')
    twice, _ = estimate_rdm_weighted_average(7, _trials(points, subsets * 2, [1, 1.1, 0.9, 1.2, 1, 0.8]), weight_mode='rms')
    assert _corr(once, twice) > 0.99


def test_robust_options_run():
    rng = np.random.default_rng(5)
    points = rng.standard_normal((8, 2))
    subsets = [[0, 1, 2, 3], [2, 3, 4, 5], [4, 5, 6, 7], [6, 7, 0, 1]]
    trials = _trials(points + 0.05 * rng.standard_normal((8, 2)), subsets, [1, 1.2, 1, 0.9])
    for method in ('winsor', 'huber', 'resid_huber', 'winsor_resid_huber'):
        D, W = estimate_rdm_weighted_average(8, trials, weight_mode='rms', robust_method=method)
        assert np.all(np.isfinite(D)) and D.shape == (8, 8) and np.allclose(D, D.T), method
        assert _corr(D, _true_rdm(points)) > 0.9, method
