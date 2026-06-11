"""Tests for batch generation functionality."""

import math
import subprocess
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace

import pytest
from coverlib.balanced import balance_sort_key, improve_pair_balance
from multiarrangement.core.batch_generator import BatchGenerator
from multiarrangement.utils.file_utils import validate_batch_configuration


class TestBatchGenerator:
    """Test cases for BatchGenerator class."""
    
    def test_initialization(self):
        """Test BatchGenerator initialization."""
        generator = BatchGenerator(n_videos=10, batch_size=3)
        assert generator.n_videos == 10
        assert generator.batch_size == 3
        assert generator.video_indices == list(range(10))
        
    def test_invalid_parameters(self):
        """Test BatchGenerator with invalid parameters."""
        with pytest.raises(ValueError):
            BatchGenerator(n_videos=5, batch_size=1)  # batch_size too small
            
        with pytest.raises(ValueError):
            BatchGenerator(n_videos=3, batch_size=5)  # batch_size too large
            
    def test_schonheim_lower_bound(self):
        """Test Schönheim lower bound calculation."""
        generator = BatchGenerator(n_videos=7, batch_size=3)
        bound = generator.calculate_schonheim_lower_bound()
        assert isinstance(bound, int)
        assert bound > 0
        
    def test_generate_all_pairs(self):
        """Test generation of all video pairs."""
        generator = BatchGenerator(n_videos=4, batch_size=2)
        pairs = generator.generate_all_pairs()
        expected_pairs = {(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)}
        assert pairs == expected_pairs
        
    def test_greedy_algorithm_small(self):
        """Test greedy algorithm with small example."""
        generator = BatchGenerator(n_videos=6, batch_size=3, seed=42)
        batches = generator.greedy_algorithm()
        
        # Validate the result
        validation = generator.validate_batches(batches)
        assert validation['coverage_complete']
        assert len(batches) >= generator.calculate_schonheim_lower_bound()
        
    def test_batch_validation(self):
        """Test batch validation functionality."""
        generator = BatchGenerator(n_videos=5, batch_size=3)
        
        # Valid batches
        batches = [[0, 1, 2], [0, 3, 4], [1, 3, 4], [2, 3, 4]]
        validation = generator.validate_batches(batches)
        assert validation['coverage_complete']
        
        # Invalid batches (missing pairs)
        incomplete_batches = [[0, 1, 2], [3, 4, 0]]
        validation = generator.validate_batches(incomplete_batches)
        assert not validation['coverage_complete']
        assert validation['pairs_missing'] > 0

    def test_balanced_algorithm_reduces_worst_pair_repetition(self):
        """Balanced mode should improve pair evidence without adding trials."""
        generator = BatchGenerator(n_videos=24, batch_size=6, seed=123)
        minimal_batches = generator.optimize_batches(algorithm="hybrid", seed=123)
        balanced_batches = generator.optimize_batches(algorithm="balanced", seed=123)

        def pair_counts(batches):
            counts = {}
            for batch in batches:
                for pair in combinations(batch, 2):
                    key = tuple(sorted(pair))
                    counts[key] = counts.get(key, 0) + 1
            return counts

        minimal_counts = pair_counts(minimal_batches)
        balanced_counts = pair_counts(balanced_batches)

        assert set(minimal_counts) == set(combinations(range(24), 2))
        assert set(balanced_counts) == set(combinations(range(24), 2))
        assert len(balanced_batches) == len(minimal_batches)
        assert max(minimal_counts.values()) >= 6
        assert max(balanced_counts.values()) <= 5

    def test_optimize_batches_defaults_to_balanced_algorithm(self):
        """Direct package defaults should use same-trial balanced set-cover."""
        generator = BatchGenerator(n_videos=24, batch_size=6, seed=123)

        assert generator.optimize_batches(seed=123) == generator.optimize_batches(
            algorithm="balanced",
            seed=123,
        )

    def test_pair_balance_local_search_can_escape_coverage_preserving_trap(self):
        """Temporary-violation local search should reduce avoidable pair hot spots."""
        batches = [
            [0, 1, 2],
            [0, 1, 3],
            [0, 1, 4],
            [0, 1, 5],
            [2, 3, 4],
            [2, 3, 5],
            [2, 4, 5],
            [3, 4, 5],
        ]

        improved = improve_pair_balance(
            6,
            3,
            batches,
            seed=22,
            target_lmax=2,
            attempts=2,
            iterations=5000,
            seconds_per_attempt=2,
        )

        def pair_counts(batches):
            counts = {}
            for batch in batches:
                for pair in combinations(batch, 2):
                    key = tuple(sorted(pair))
                    counts[key] = counts.get(key, 0) + 1
            return counts

        counts = pair_counts(improved)
        assert set(counts) == set(combinations(range(6), 2))
        assert max(counts.values()) <= 2

    def test_balanced_cover_score_uses_normalized_metric(self):
        """Package scoring should share the size-normalized cover metric."""
        generator = BatchGenerator(n_videos=6, batch_size=2, seed=42)
        all_pairs = [[i, j] for i, j in combinations(range(6), 2)]
        evenly_spread = all_pairs + [[0, 1], [0, 2], [0, 3]]

        assert generator._balanced_cover_score(evenly_spread) == balance_sort_key(6, 2, evenly_spread)

    def test_exact_pair_design_is_already_balanced_enough(self):
        """An exact lambda-1 design should not be penalized because all pairs are at lambda_max."""
        generator = BatchGenerator(n_videos=6, batch_size=2, seed=42)
        all_pairs = [[i, j] for i, j in combinations(range(6), 2)]

        assert generator._is_already_balanced_enough(all_pairs) is True

    def test_optimal_script_prefers_packaged_copy(self, monkeypatch, tmp_path):
        """The packaged optimize script should win over a stale cwd copy."""
        generator = BatchGenerator(n_videos=6, batch_size=3, seed=42)
        legacy_script = tmp_path / "optimize_cover_pure.py"
        legacy_script.write_text("raise SystemExit('legacy copy should not run')", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        package_script = Path(__import__("multiarrangement").__file__).resolve().parent / "optimize_cover_pure.py"
        called = {}

        def fake_run(cmd, **kwargs):
            called["script"] = Path(cmd[1]).resolve()
            output_file = Path(cmd[cmd.index("--outfile") + 1])
            output_file.write_text("0 1 2\n0 3 4\n1 3 5\n2 4 5\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        batches = generator._try_optimize_cover_pure(tmp_path)

        assert called["script"] == package_script.resolve()
        assert batches


class TestFileUtils:
    """Test cases for file utility functions."""
    
    def test_validate_batch_configuration_valid(self):
        """Test validation of valid batch configuration."""
        batches = [[0, 1, 2], [1, 2, 3], [0, 3, 4]]
        num_videos = 5
        
        # Should not raise an exception
        validate_batch_configuration(batches, num_videos)
        
    def test_validate_batch_configuration_invalid_indices(self):
        """Test validation with invalid indices."""
        batches = [[0, 1, 5]]  # Index 5 is out of range
        num_videos = 5
        
        with pytest.raises(ValueError):
            validate_batch_configuration(batches, num_videos)
            
    def test_validate_batch_configuration_duplicates(self):
        """Test validation with duplicate indices in batch."""
        batches = [[0, 1, 1]]  # Duplicate index 1
        num_videos = 5
        
        with pytest.raises(ValueError):
            validate_batch_configuration(batches, num_videos)
            
    def test_validate_batch_configuration_empty_batch(self):
        """Test validation with empty batch."""
        batches = [[]]  # Empty batch
        num_videos = 5
        
        with pytest.raises(ValueError):
            validate_batch_configuration(batches, num_videos)


class TestExactDesignFastPath:
    """The hybrid path must use exact constructions when (v, k) admits one."""

    def test_projective_plane_size_is_perfect(self):
        generator = BatchGenerator(n_videos=13, batch_size=4)
        batches = generator.optimize_batches_hybrid(prefer_optimal=True)
        assert len(batches) == 13
        counts = {}
        for batch in batches:
            for a, b in combinations(sorted(batch), 2):
                counts[(a, b)] = counts.get((a, b), 0) + 1
        assert len(counts) == 13 * 12 // 2
        assert set(counts.values()) == {1}
