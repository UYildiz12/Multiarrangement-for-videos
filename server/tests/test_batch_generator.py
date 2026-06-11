"""
Tests for the batch generator core algorithms.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from itertools import combinations

import pytest
from coverlib.balanced import balance_sort_key
from ma_core.batch_generator import BatchGenerator, generate_batches, _balanced_cover_score, _resolve_ljcr_cache_dir


class TestBatchGenerator:
    """Tests for BatchGenerator class."""

    def test_init_valid(self):
        """Test valid initialization."""
        gen = BatchGenerator(n_items=12, batch_size=4, seed=42)
        assert gen.n_items == 12
        assert gen.batch_size == 4
        assert len(gen.item_indices) == 12

    def test_init_batch_size_too_small(self):
        """Test that batch size < 2 is rejected."""
        with pytest.raises(ValueError, match="at least 2"):
            BatchGenerator(n_items=10, batch_size=1)

    def test_init_batch_size_too_large(self):
        """Test that batch size > n_items is rejected."""
        with pytest.raises(ValueError, match="cannot be larger"):
            BatchGenerator(n_items=5, batch_size=10)

    def test_schonheim_bound(self):
        """Test Schönheim lower bound calculation."""
        gen = BatchGenerator(n_items=12, batch_size=4)
        bound = gen.calculate_schonheim_lower_bound()
        # For v=12, k=4: ceil(12/4) * ceil(11/3) = 3 * 4 = 12
        assert bound == 12

    def test_generate_all_pairs(self):
        """Test pair generation."""
        gen = BatchGenerator(n_items=4, batch_size=2)
        pairs = gen.generate_all_pairs()
        # 4 choose 2 = 6 pairs
        assert len(pairs) == 6
        assert (0, 1) in pairs
        assert (2, 3) in pairs

    def test_get_pairs_in_batch(self):
        """Test getting pairs from a batch."""
        gen = BatchGenerator(n_items=10, batch_size=4)
        batch = [0, 2, 5, 7]
        pairs = gen.get_pairs_in_batch(batch)
        # 4 choose 2 = 6 pairs
        assert len(pairs) == 6
        assert (0, 2) in pairs
        assert (5, 7) in pairs

    def test_generate_batches_covers_all_pairs(self):
        """Test that generated batches cover all pairs."""
        gen = BatchGenerator(n_items=12, batch_size=4, seed=42)
        batches = gen.generate_batches(restarts=16)
        
        # Validate coverage
        validation = gen.validate_batches(batches)
        assert validation['coverage_complete'] is True
        assert validation['pairs_missing'] == 0

    def test_generate_batches_deterministic_with_seed(self):
        """Test that same seed produces same batches."""
        gen1 = BatchGenerator(n_items=10, batch_size=4, seed=123)
        gen2 = BatchGenerator(n_items=10, batch_size=4, seed=123)
        
        batches1 = gen1.generate_batches(restarts=8)
        batches2 = gen2.generate_batches(restarts=8)
        
        assert len(batches1) == len(batches2)
        for b1, b2 in zip(batches1, batches2):
            assert sorted(b1) == sorted(b2)

    def test_generate_batches_efficiency(self):
        """Test that batches are reasonably efficient."""
        gen = BatchGenerator(n_items=15, batch_size=6, seed=42)
        batches = gen.generate_batches(restarts=32)
        
        validation = gen.validate_batches(batches)
        bound = gen.calculate_schonheim_lower_bound()
        
        # Should be within 50% of lower bound
        assert len(batches) <= bound * 1.5
        assert validation['efficiency'] >= 0.5


class TestGenerateBatchesFunction:
    """Tests for the convenience function."""

    def test_resolve_ljcr_cache_dir_prefers_package_cache(self, monkeypatch, tmp_path):
        """Server should reuse the packaged LJCR cache when available."""
        package_dir = tmp_path / "fake_multiarrangement"
        expected = package_dir / "ljcr_cache"
        expected.mkdir(parents=True)
        monkeypatch.setitem(sys.modules, "multiarrangement", SimpleNamespace(__file__=str(package_dir / "__init__.py")))

        assert _resolve_ljcr_cache_dir() == expected
        assert expected.exists()

    def test_generate_batches_basic(self):
        """Test basic batch generation."""
        batches = generate_batches(n_items=8, batch_size=4, seed=42)
        
        assert len(batches) > 0
        for batch in batches:
            assert len(batch) == 4
            assert all(0 <= idx < 8 for idx in batch)

    def test_generate_batches_coverage(self):
        """Test that all pairs are covered."""
        batches = generate_batches(n_items=10, batch_size=5, seed=42, restarts=16)
        
        # Collect all covered pairs
        covered = set()
        for batch in batches:
            for i, a in enumerate(batch):
                for b in batch[i+1:]:
                    covered.add((min(a, b), max(a, b)))
        
        # Should have all 45 pairs covered
        expected_pairs = 10 * 9 // 2
        assert len(covered) == expected_pairs

    def test_balanced_generation_flattens_pair_hot_spots(self):
        """Server balanced mode should improve balance without adding trials."""
        batches = generate_batches(n_items=40, batch_size=6, seed=123, restarts=64, algorithm="balanced")

        counts = {}
        for batch in batches:
            for pair in combinations(batch, 2):
                key = tuple(sorted(pair))
                counts[key] = counts.get(key, 0) + 1

        assert set(counts) == set(combinations(range(40), 2))
        assert len(batches) == 55
        assert max(counts.values()) <= 6

    def test_generate_batches_defaults_to_balanced_algorithm(self):
        """Server defaults should use same-trial balanced set-cover."""
        assert generate_batches(n_items=24, batch_size=6, seed=123, restarts=64) == generate_batches(
            n_items=24,
            batch_size=6,
            seed=123,
            restarts=64,
            algorithm="balanced",
        )

    def test_balanced_cover_score_uses_normalized_metric(self):
        """Server scoring should share the size-normalized cover metric."""
        all_pairs = [[i, j] for i, j in combinations(range(6), 2)]
        evenly_spread = all_pairs + [[0, 1], [0, 2], [0, 3]]

        assert _balanced_cover_score(6, 2, evenly_spread) == balance_sort_key(6, 2, evenly_spread)

    def test_exact_pair_design_is_already_balanced_enough(self):
        """An exact lambda-1 design should not be penalized because all pairs are at lambda_max."""
        from ma_core.batch_generator import _is_already_balanced_enough

        all_pairs = [[i, j] for i, j in combinations(range(6), 2)]

        assert _is_already_balanced_enough(6, 2, all_pairs) is True


class TestEdgeCases:
    """Edge case tests."""

    def test_minimum_size(self):
        """Test with minimum valid inputs."""
        batches = generate_batches(n_items=3, batch_size=2, seed=42)
        
        # Need 3 batches to cover 3 pairs
        validation = BatchGenerator(3, 2).validate_batches(batches)
        assert validation['coverage_complete'] is True

    def test_batch_equals_items(self):
        """Test when batch size equals number of items."""
        batches = generate_batches(n_items=5, batch_size=5, seed=42)
        
        # Should need only 1 batch
        assert len(batches) == 1
        assert sorted(batches[0]) == [0, 1, 2, 3, 4]

    def test_large_input(self):
        """Test with larger input (performance check)."""
        batches = generate_batches(n_items=24, batch_size=8, seed=42, restarts=8)
        
        validation = BatchGenerator(24, 8).validate_batches(batches)
        assert validation['coverage_complete'] is True


class TestExactDesignFastPath:
    """The optimal path must use exact constructions when (v, k) admits one."""

    def test_projective_plane_size_is_perfect(self):
        batches = generate_batches(57, 8, seed=1, algorithm="optimal")
        assert len(batches) == 57
        counts = {}
        for batch in batches:
            for a, b in combinations(sorted(batch), 2):
                counts[(a, b)] = counts.get((a, b), 0) + 1
        assert len(counts) == 57 * 56 // 2
        assert set(counts.values()) == {1}
