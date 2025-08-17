"""Tests for experiment functionality."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
from multiarrangement.core.experiment import MultiarrangementExperiment


class TestMultiarrangementExperiment:
    """Test cases for MultiarrangementExperiment class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.video_dir = Path(self.temp_dir) / "videos"
        self.video_dir.mkdir()
        
        # Create dummy video files
        self.video_files = []
        for i in range(5):
            video_file = self.video_dir / f"video_{i:03d}.avi"
            video_file.write_text("dummy video content")
            self.video_files.append(video_file)
            
        # Create batch file
        self.batch_file = Path(self.temp_dir) / "batches.txt"
        with open(self.batch_file, 'w') as f:
            f.write("0,1,2\n")
            f.write("1,2,3\n")
            f.write("2,3,4\n")
            
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_initialization_valid(self):
        """Test valid experiment initialization."""
        experiment = MultiarrangementExperiment(
            video_directory=str(self.video_dir),
            batch_file=str(self.batch_file),
            participant_id="test_participant"
        )
        
        assert experiment.participant_id == "test_participant"
        assert len(experiment.video_files) == 5
        assert len(experiment.batches) == 3
        assert experiment.current_batch_index == 0
        
    def test_initialization_missing_video_dir(self):
        """Test initialization with missing video directory."""
        with pytest.raises(FileNotFoundError):
            MultiarrangementExperiment(
                video_directory="/nonexistent/path",
                batch_file=str(self.batch_file),
                participant_id="test_participant"
            )
            
    def test_initialization_missing_batch_file(self):
        """Test initialization with missing batch file."""
        with pytest.raises(FileNotFoundError):
            MultiarrangementExperiment(
                video_directory=str(self.video_dir),
                batch_file="/nonexistent/batches.txt",
                participant_id="test_participant"
            )
            
    def test_get_current_batch_videos(self):
        """Test getting current batch videos."""
        experiment = MultiarrangementExperiment(
            video_directory=str(self.video_dir),
            batch_file=str(self.batch_file),
            participant_id="test_participant"
        )
        
        batch_videos = experiment.get_current_batch_videos()
        assert len(batch_videos) == 3  # First batch has indices 0,1,2
        
    def test_advance_to_next_batch(self):
        """Test advancing to next batch."""
        experiment = MultiarrangementExperiment(
            video_directory=str(self.video_dir),
            batch_file=str(self.batch_file),
            participant_id="test_participant"
        )
        
        # Should have next batch
        has_next = experiment.advance_to_next_batch()
        assert has_next
        assert experiment.current_batch_index == 1
        
        # Advance to last batch
        experiment.advance_to_next_batch()
        assert experiment.current_batch_index == 2
        
        # Should not have next batch
        has_next = experiment.advance_to_next_batch()
        assert not has_next
        assert experiment.experiment_completed
        
    def test_record_arrangement(self):
        """Test recording video arrangement."""
        experiment = MultiarrangementExperiment(
            video_directory=str(self.video_dir),
            batch_file=str(self.batch_file),
            participant_id="test_participant"
        )
        
        # Mock video positions
        positions = {
            "video_000": (100, 100),
            "video_001": (200, 200), 
            "video_002": (300, 300)
        }
        
        # Record arrangement
        experiment.record_arrangement(positions)
        
        # Check that distances were calculated
        rdm = experiment.rdm_df
        assert not rdm.loc["video_000", "video_001"] == 0  # Should have distance
        assert rdm.loc["video_000", "video_000"] == 0  # Diagonal should be 0
        
    def test_get_progress(self):
        """Test getting experiment progress."""
        experiment = MultiarrangementExperiment(
            video_directory=str(self.video_dir),
            batch_file=str(self.batch_file),
            participant_id="test_participant"
        )
        
        current, total = experiment.get_progress()
        assert current == 1  # First batch (1-indexed)
        assert total == 3  # Total of 3 batches
        
    @patch('multiarrangement.core.experiment.Path.mkdir')
    @patch('pandas.DataFrame.to_excel')
    @patch('numpy.save')
    def test_save_results(self, mock_np_save, mock_to_excel, mock_mkdir):
        """Test saving experiment results."""
        experiment = MultiarrangementExperiment(
            video_directory=str(self.video_dir),
            batch_file=str(self.batch_file),
            participant_id="test_participant"
        )
        
        experiment.save_results()
        
        # Verify that save methods were called
        mock_mkdir.assert_called()
        mock_to_excel.assert_called()
        mock_np_save.assert_called()
