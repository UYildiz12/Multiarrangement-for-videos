"""
Tests for the lift-the-weakest adaptive selection algorithms.
"""

import numpy as np
import pytest

from ma_core.lift_weakest import (
    TrialArrangement,
    compute_evidence_matrix,
    estimate_rdm_weighted_average,
    select_next_subset_lift_weakest,
    get_min_evidence,
    check_stopping_criterion,
)


class TestSmacofConvergence:
    """Regression: SMACOF must iterate to convergence, not stop after one step."""

    def test_smacof_converges_beyond_first_iteration(self):
        from ma_core.lift_weakest import _smacof_mds_2d

        rng = np.random.default_rng(7)
        X_true = rng.standard_normal((12, 2))
        D = np.sqrt(((X_true[:, None, :] - X_true[None, :, :]) ** 2).sum(axis=2))
        D_noisy = D + rng.uniform(0, 0.8, size=D.shape)
        D_noisy = (D_noisy + D_noisy.T) / 2
        np.fill_diagonal(D_noisy, 0.0)

        X = _smacof_mds_2d(D_noisy)
        Dhat = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(axis=2))
        iu = np.triu_indices(12, 1)
        stress = float(np.sum((Dhat[iu] - D_noisy[iu]) ** 2))
        # A single Guttman step from the classical-MDS start scores ~5.52 on
        # this instance; converged SMACOF reaches ~5.27.
        assert stress < 5.4


class TestTrialArrangement:
    """Tests for TrialArrangement dataclass."""

    def test_create_trial(self):
        """Test creating a trial arrangement."""
        trial = TrialArrangement(
            subset=[0, 1, 2],
            positions={0: (100.0, 100.0), 1: (200.0, 100.0), 2: (150.0, 200.0)}
        )
        assert trial.subset == [0, 1, 2]
        assert trial.positions[0] == (100.0, 100.0)


class TestComputeEvidenceMatrix:
    """Tests for evidence matrix computation."""

    def test_empty_trials(self):
        """Test with no trials."""
        W = compute_evidence_matrix(5, [])
        assert W.shape == (5, 5)
        assert np.all(W == 0)

    def test_single_trial(self):
        """Test with a single trial."""
        trial = TrialArrangement(
            subset=[0, 1],
            positions={0: (0.0, 0.0), 1: (100.0, 0.0)}
        )
        W = compute_evidence_matrix(3, [trial], weight_mode="max", alpha=2.0)
        
        # max-normalized distance is 1, weight is 1^2 = 1
        assert W[0, 1] == pytest.approx(1.0)
        assert W[1, 0] == pytest.approx(1.0)
        assert W[0, 2] == 0  # Not in trial
        assert np.diag(W).sum() == 0  # Diagonal is zero

    def test_multiple_trials(self):
        """Test evidence accumulation across trials."""
        trials = [
            TrialArrangement(
                subset=[0, 1],
                positions={0: (0.0, 0.0), 1: (100.0, 0.0)}
            ),
            TrialArrangement(
                subset=[0, 1],
                positions={0: (0.0, 0.0), 1: (50.0, 0.0)}
            ),
        ]
        W = compute_evidence_matrix(3, trials, weight_mode="max", alpha=2.0)
        
        # Each trial max-normalizes to 1, so total = 1^2 + 1^2 = 2
        assert W[0, 1] == pytest.approx(2.0)


class TestEstimateRDM:
    """Tests for RDM estimation."""

    def test_single_trial_rdm(self):
        """Test RDM from a single trial."""
        trial = TrialArrangement(
            subset=[0, 1, 2],
            positions={0: (0.0, 0.0), 1: (100.0, 0.0), 2: (0.0, 100.0)}
        )
        D, W = estimate_rdm_weighted_average(3, [trial])
        
        assert D.shape == (3, 3)
        assert np.diag(D).sum() == 0
        # Check symmetry
        assert np.allclose(D, D.T)

    def test_multiple_trials_rdm(self):
        """Test RDM converges with multiple trials."""
        np.random.seed(42)
        n = 5
        # Create synthetic trials with some structure
        trials = []
        for _ in range(10):
            subset = list(np.random.choice(n, size=3, replace=False))
            positions = {
                idx: (float(np.random.uniform(0, 500)), float(np.random.uniform(0, 500)))
                for idx in subset
            }
            trials.append(TrialArrangement(subset=subset, positions=positions))
        
        D, W = estimate_rdm_weighted_average(n, trials)
        
        assert D.shape == (n, n)
        assert np.allclose(D, D.T)
        assert np.all(np.diag(D) == 0)
        # Evidence should be accumulated
        assert np.sum(W) > 0

    def test_arena_geometry_makes_raw_weighting_scale_invariant(self):
        """Equivalent layouts in different arena sizes should produce the same evidence."""
        small = TrialArrangement(
            subset=[0, 1, 2],
            positions={0: (300.0, 300.0), 1: (580.0, 300.0), 2: (300.0, 580.0)},
            arena_center=(300.0, 300.0),
            arena_radius=280.0,
        )
        large = TrialArrangement(
            subset=[0, 1, 2],
            positions={0: (375.0, 375.0), 1: (730.0, 375.0), 2: (375.0, 730.0)},
            arena_center=(375.0, 375.0),
            arena_radius=355.0,
        )

        D_small, W_small = estimate_rdm_weighted_average(3, [small], weight_mode="k2012")
        D_large, W_large = estimate_rdm_weighted_average(3, [large], weight_mode="k2012")

        np.testing.assert_allclose(D_small, D_large, atol=1e-9)
        np.testing.assert_allclose(W_small, W_large, atol=1e-9)


class TestSelectNextSubset:
    """Tests for lift-the-weakest subset selection."""

    def test_basic_selection(self):
        """Test basic subset selection."""
        n = 6
        D = np.random.rand(n, n)
        D = (D + D.T) / 2
        np.fill_diagonal(D, 0)
        
        W = np.zeros((n, n))  # No evidence yet
        
        subset = select_next_subset_lift_weakest(
            D, W, min_size=3, max_size=4
        )
        
        assert len(subset) >= 3
        assert len(subset) <= 4
        assert len(set(subset)) == len(subset)  # No duplicates

    def test_respects_min_size(self):
        """Test that min_size is respected."""
        n = 8
        D = np.ones((n, n)) - np.eye(n)
        W = np.zeros((n, n))
        
        subset = select_next_subset_lift_weakest(
            D, W, min_size=5, max_size=6
        )
        
        assert len(subset) >= 5

    def test_respects_max_size(self):
        """Test that max_size is respected."""
        n = 10
        D = np.ones((n, n)) - np.eye(n)
        W = np.zeros((n, n))
        
        subset = select_next_subset_lift_weakest(
            D, W, min_size=3, max_size=4
        )
        
        assert len(subset) <= 4

    def test_prioritizes_weak_pairs(self):
        """Test that weak-evidence pairs are prioritized."""
        n = 5
        D = np.ones((n, n)) - np.eye(n)
        
        # Create uneven evidence: pair (2, 3) has less evidence
        W = np.ones((n, n)) * 100
        W[2, 3] = W[3, 2] = 1.0  # Weak pair
        np.fill_diagonal(W, 0)
        
        subset = select_next_subset_lift_weakest(
            D, W, min_size=2, max_size=4
        )
        
        # The weak pair should be in the subset
        assert 2 in subset and 3 in subset


class TestStoppingCriterion:
    """Tests for stopping criterion functions."""

    def test_get_min_evidence(self):
        """Test minimum evidence extraction."""
        W = np.array([
            [0, 10, 20],
            [10, 0, 5],
            [20, 5, 0]
        ], dtype=float)
        
        min_ev = get_min_evidence(W)
        assert min_ev == 5.0

    def test_check_stopping_below_threshold(self):
        """Test stopping when below threshold."""
        W = np.array([
            [0, 0.5, 0.2],
            [0.5, 0, 0.1],
            [0.2, 0.1, 0]
        ], dtype=float)
        # min=0.1 < 0.35
        assert not check_stopping_criterion(W, threshold=0.35)

    def test_check_stopping_above_threshold(self):
        """Test stopping when above threshold."""
        W = np.array([
            [0, 0.5, 0.4],
            [0.5, 0, 0.6],
            [0.4, 0.6, 0]
        ], dtype=float)
        # min=0.4 >= 0.35
        assert check_stopping_criterion(W, threshold=0.35)


class TestIntegration:
    """Integration tests for the full adaptive loop."""

    def test_simple_adaptive_loop(self):
        """Test a simple adaptive experiment loop."""
        n = 6
        np.random.seed(42)
        
        # Start with uniform RDM
        D = np.ones((n, n)) - np.eye(n)
        W = np.zeros((n, n))
        
        trials = []
        max_trials = 20
        
        for trial_idx in range(max_trials):
            # Select next subset
            subset = select_next_subset_lift_weakest(
                D, W, min_size=3, max_size=4
            )
            
            # Simulate an arrangement (random positions)
            positions = {
                idx: (float(np.random.uniform(0, 500)), float(np.random.uniform(0, 500)))
                for idx in subset
            }
            
            trial = TrialArrangement(subset=subset, positions=positions)
            trials.append(trial)
            
            # Update RDM and evidence
            D, W = estimate_rdm_weighted_average(n, trials)
            
            # Check stopping
            if check_stopping_criterion(W, threshold=0.35):
                break
        
        # Should have completed some trials
        assert len(trials) >= 1
        # RDM should be filled
        assert not np.all(D == 0)
