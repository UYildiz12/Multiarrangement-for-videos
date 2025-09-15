"""
Core experimental functionality for multiarrangement tasks.
"""

import os
import random
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from ..utils.file_utils import get_resource_path, load_batches
from ..utils.video_processing import VideoProcessor
from ..utils.data_processing import DataProcessor


class MultiarrangementExperiment:
    """
    Main class for running multiarrangement experiments.
    
    This class handles the core experimental logic, data collection,
    and participant management for video similarity arrangement tasks.
    """
    
    def __init__(
        self, 
        video_directory: str,
        batch_file: str,
        participant_id: Optional[str] = None,
        output_directory: str = "Participantdata",
        randomize_videos: bool = True
    ):
        """
        Initialize the multiarrangement experiment.
        
        Args:
            video_directory: Path to directory containing video files
            batch_file: Path to batch configuration file
            participant_id: Unique identifier for participant
            output_directory: Directory to save results
            randomize_videos: Whether to randomize video order
        """
        self.video_directory = Path(video_directory)
        self.batch_file = Path(batch_file)
        self.participant_id = participant_id
        self.output_directory = Path(output_directory)
        self.randomize_videos = randomize_videos
        
        # Initialize components
        self.video_processor = VideoProcessor()
        self.data_processor = DataProcessor()
        
        # Load video files and batches
        self._load_videos()
        self._load_batches()
        self._initialize_data_structures()
        
    def _load_videos(self) -> None:
        """Load media files (video/image/audio) from the specified directory."""
        if not self.video_directory.exists():
            raise FileNotFoundError(f"Video directory not found: {self.video_directory}")
            
        # Get supported media files
        video_extensions = {'.avi', '.mp4', '.mov', '.mkv', '.wmv'}
        audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
        exts = video_extensions | audio_extensions | image_extensions
        self.video_files = [f.name for f in self.video_directory.iterdir() if f.suffix.lower() in exts]
        
        if not self.video_files:
            raise ValueError(f"No supported media files found in {self.video_directory}")
            
        # Extract video names (without extension)
        self.video_names = [
            os.path.splitext(video_file)[0] 
            for video_file in self.video_files
        ]
        
        if self.randomize_videos:
            # Create a shuffled mapping but keep it consistent for the session
            random.shuffle(self.video_files)
            
    def _load_batches(self) -> None:
        """Load batch configuration from file."""
        if not self.batch_file.exists():
            raise FileNotFoundError(f"Batch file not found: {self.batch_file}")
            
        self.batches = load_batches(self.batch_file)
        
        # Validate batch indices against available videos
        max_index = len(self.video_files) - 1
        for i, batch in enumerate(self.batches):
            for video_index in batch:
                if video_index > max_index:
                    raise ValueError(
                        f"Batch {i} contains index {video_index} but only "
                        f"{len(self.video_files)} videos available (max index: {max_index})"
                    )
                    
    def _initialize_data_structures(self) -> None:
        """Initialize data structures for collecting results."""
        # Create RDM dataframe
        self.rdm_df = pd.DataFrame(
            columns=self.video_names, 
            index=self.video_names
        )
        np.fill_diagonal(self.rdm_df.values, 0)
        
        # Track experiment state
        self.current_batch_index = 0
        self.experiment_completed = False
        
    def get_current_batch_videos(self) -> List[str]:
        """Get the video files for the current batch."""
        if self.current_batch_index >= len(self.batches):
            return []
            
        batch_indices = self.batches[self.current_batch_index]
        return [self.video_files[i] for i in batch_indices]
        
    def get_video_path(self, video_filename: str) -> Path:
        """Get the full path to a video file."""
        return self.video_directory / video_filename
        
    def record_arrangement(self, video_positions: Dict[str, Tuple[float, float]]) -> None:
        """
        Record the spatial arrangement of videos for the current batch.
        
        Args:
            video_positions: Dictionary mapping video filenames to (x, y) positions
        """
        batch_videos = self.get_current_batch_videos()
        video_names = [os.path.splitext(video)[0] for video in batch_videos]
        
        # Calculate pairwise distances
        for i in range(len(video_names)):
            for j in range(i + 1, len(video_names)):
                video_i = video_names[i]
                video_j = video_names[j]
                
                if video_i in video_positions and video_j in video_positions:
                    pos_i = video_positions[video_i]
                    pos_j = video_positions[video_j]
                    
                    # Calculate Euclidean distance
                    distance = np.sqrt((pos_i[0] - pos_j[0])**2 + (pos_i[1] - pos_j[1])**2)
                    
                    # Handle multiple measurements (averaging)
                    current_value = self.rdm_df.loc[video_i, video_j]
                    if pd.isna(current_value):
                        self.rdm_df.loc[video_i, video_j] = distance
                        self.rdm_df.loc[video_j, video_i] = distance
                    else:
                        # Average with existing value
                        if isinstance(current_value, list):
                            current_value.append(distance)
                            avg_distance = np.mean(current_value)
                        else:
                            avg_distance = np.mean([current_value, distance])
                        
                        self.rdm_df.loc[video_i, video_j] = avg_distance
                        self.rdm_df.loc[video_j, video_i] = avg_distance
                        
    def advance_to_next_batch(self) -> bool:
        """
        Advance to the next batch.
        
        Returns:
            True if there is a next batch, False if experiment is complete
        """
        self.current_batch_index += 1
        if self.current_batch_index >= len(self.batches):
            self.experiment_completed = True
            return False
        return True
        
    def is_experiment_complete(self) -> bool:
        """Check if all batches have been completed."""
        return self.experiment_completed
        
    def get_progress(self) -> Tuple[int, int]:
        """Get current progress as (current_batch, total_batches)."""
        return (self.current_batch_index + 1, len(self.batches))
        
    def save_results(self, output_dir: Optional[Path] = None) -> None:
        """
        Save experimental results to files.
        
        Args:
            output_dir: Optional custom output directory
        """
        if output_dir is None:
            output_dir = self.output_directory
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.participant_id:
            base_filename = f"participant_{self.participant_id}"
        else:
            base_filename = "multiarrangement_results"
            
        # Save Excel file with distance matrix
        excel_path = output_dir / f"{base_filename}_results.xlsx"
        self.rdm_df.to_excel(excel_path)
        
        # Save numpy array with RDM
        rdm_array = self.rdm_df.values.astype(float)
        npy_path = output_dir / f"{base_filename}_rdm.npy"
        np.save(npy_path, rdm_array)
        
        print(f"Results saved to {output_dir}")
        print(f"  - Excel file: {excel_path}")
        print(f"  - NumPy array: {npy_path}")
        
    def get_experiment_summary(self) -> Dict[str, Any]:
        """Get a summary of the experiment configuration and progress."""
        return {
            "video_directory": str(self.video_directory),
            "batch_file": str(self.batch_file),
            "participant_id": self.participant_id,
            "total_videos": len(self.video_files),
            "total_batches": len(self.batches),
            "current_batch": self.current_batch_index + 1,
            "experiment_completed": self.experiment_completed,
            "output_directory": str(self.output_directory)
        }
