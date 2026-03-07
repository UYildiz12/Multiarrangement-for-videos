"""Tests for batch generation functionality."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
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
