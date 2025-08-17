"""
Command-line interface for multiarrangement experiments.
"""

import argparse
import sys
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from pathlib import Path
from typing import Optional

from .core.experiment import MultiarrangementExperiment
from .core.batch_generator import BatchGenerator
from .ui.interface import MultiarrangementInterface
from .ui.fullscreen_interface import FullscreenInterface
from .utils.file_utils import get_video_files, validate_batch_configuration, load_batches


def get_participant_id() -> str:
    """Get participant ID using a GUI dialog."""
    root = tk.Tk()
    root.withdraw()
    
    participant_id = simpledialog.askstring(
        "Participant ID", 
        "Enter participant number or ID:",
        parent=root
    )
    
    root.destroy()
    
    if not participant_id:
        print("No participant ID provided. Exiting.")
        sys.exit(1)
        
    return participant_id


def select_video_directory() -> Path:
    """Select video directory using file dialog."""
    root = tk.Tk()
    root.withdraw()
    
    directory = filedialog.askdirectory(
        title="Select video directory",
        initialdir=Path.cwd()
    )
    
    root.destroy()
    
    if not directory:
        print("No video directory selected. Exiting.")
        sys.exit(1)
        
    return Path(directory)


def select_batch_file() -> Path:
    """Select batch configuration file using file dialog."""
    root = tk.Tk()
    root.withdraw()
    
    batch_file = filedialog.askopenfilename(
        title="Select batch configuration file",
        initialdir=Path.cwd(),
        filetypes=[
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
    )
    
    root.destroy()
    
    if not batch_file:
        print("No batch file selected. Exiting.")
        sys.exit(1)
        
    return Path(batch_file)


def main():
    """Main CLI entry point for windowed multiarrangement experiment."""
    parser = argparse.ArgumentParser(
        description="Run multiarrangement video similarity experiment"
    )
    
    parser.add_argument(
        "--video-dir",
        type=str,
        help="Directory containing video files"
    )
    
    parser.add_argument(
        "--batch-file",
        type=str,
        help="Batch configuration file"
    )
    
    parser.add_argument(
        "--participant-id",
        type=str,
        help="Participant ID (if not provided, will prompt)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="Participantdata",
        help="Output directory for results (default: Participantdata)"
    )
    
    parser.add_argument(
        "--no-randomize",
        action="store_true",
        help="Don't randomize video order"
    )
    
    args = parser.parse_args()
    
    # Get parameters
    if args.video_dir:
        video_dir = Path(args.video_dir)
    else:
        video_dir = select_video_directory()
        
    if args.batch_file:
        batch_file = Path(args.batch_file)
    else:
        batch_file = select_batch_file()
        
    if args.participant_id:
        participant_id = args.participant_id
    else:
        participant_id = get_participant_id()
        
    # Validate inputs
    if not video_dir.exists():
        print(f"Error: Video directory does not exist: {video_dir}")
        sys.exit(1)
        
    if not batch_file.exists():
        print(f"Error: Batch file does not exist: {batch_file}")
        sys.exit(1)
        
    try:
        # Create experiment
        experiment = MultiarrangementExperiment(
            video_directory=str(video_dir),
            batch_file=str(batch_file),
            participant_id=participant_id,
            output_directory=args.output_dir,
            randomize_videos=not args.no_randomize
        )
        
        # Create and run interface
        interface = MultiarrangementInterface(experiment)
        interface.run()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main_fullscreen():
    """Main CLI entry point for fullscreen multiarrangement experiment."""
    parser = argparse.ArgumentParser(
        description="Run fullscreen multiarrangement video similarity experiment"
    )
    
    parser.add_argument(
        "--video-dir",
        type=str,
        help="Directory containing video files"
    )
    
    parser.add_argument(
        "--batch-file",
        type=str,
        help="Batch configuration file"
    )
    
    parser.add_argument(
        "--participant-id",
        type=str,
        help="Participant ID (if not provided, will prompt)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="Participantdata",
        help="Output directory for results (default: Participantdata)"
    )
    
    parser.add_argument(
        "--no-randomize",
        action="store_true",
        help="Don't randomize video order"
    )
    
    args = parser.parse_args()
    
    # Get parameters (same as main but fullscreen)
    if args.video_dir:
        video_dir = Path(args.video_dir)
    else:
        video_dir = select_video_directory()
        
    if args.batch_file:
        batch_file = Path(args.batch_file)
    else:
        batch_file = select_batch_file()
        
    if args.participant_id:
        participant_id = args.participant_id
    else:
        participant_id = get_participant_id()
        
    # Validate inputs
    if not video_dir.exists():
        print(f"Error: Video directory does not exist: {video_dir}")
        sys.exit(1)
        
    if not batch_file.exists():
        print(f"Error: Batch file does not exist: {batch_file}")
        sys.exit(1)
        
    try:
        # Create experiment
        experiment = MultiarrangementExperiment(
            video_directory=str(video_dir),
            batch_file=str(batch_file),
            participant_id=participant_id,
            output_directory=args.output_dir,
            randomize_videos=not args.no_randomize
        )
        
        # Create and run fullscreen interface
        interface = FullscreenInterface(experiment)
        interface.run()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def batch_generator_cli():
    """CLI for batch generator tool."""
    parser = argparse.ArgumentParser(
        description="Generate optimized batch configurations for multiarrangement experiments"
    )
    
    parser.add_argument(
        "n_videos",
        type=int,
        help="Number of videos"
    )
    
    parser.add_argument(
        "batch_size",
        type=int,
        help="Number of videos per batch"
    )
    
    parser.add_argument(
        "--algorithm",
        choices=["hybrid", "optimal", "greedy", "brute_force"],
        default="hybrid",
        help="Algorithm to use (default: hybrid - tries optimal then greedy C then Python greedy)"
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        help="Output file for batch configuration"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible results"
    )
    
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the generated batches"
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if args.batch_size < 2:
        print("Error: Batch size must be at least 2")
        sys.exit(1)
        
    if args.batch_size > args.n_videos:
        print("Error: Batch size cannot be larger than number of videos")
        sys.exit(1)
        
    # Set default output file if not provided
    if not args.output_file:
        args.output_file = f"batches_{args.n_videos}videos_batchsize{args.batch_size}.txt"
        
    try:
        # Create batch generator
        generator = BatchGenerator(
            n_videos=args.n_videos,
            batch_size=args.batch_size,
            seed=args.seed
        )
        
        print(f"Generating batches for {args.n_videos} videos, batch size {args.batch_size}")
        print(f"Algorithm: {args.algorithm}")
        print(f"Schönheim lower bound: {generator.calculate_schonheim_lower_bound()}")
        
        # Generate batches using the specified algorithm
        batches = generator.optimize_batches(algorithm=args.algorithm)
            
        print(f"Generated {len(batches)} batches")
        
        # Validate if requested
        if args.validate:
            validation = generator.validate_batches(batches)
            print("\nValidation results:")
            print(f"  Coverage complete: {validation['coverage_complete']}")
            print(f"  Pairs covered: {validation['pairs_covered']}/{validation['total_pairs_needed']}")
            print(f"  Efficiency: {validation['efficiency']:.3f}")
            
            if not validation['coverage_complete']:
                print(f"  Missing pairs: {validation['pairs_missing']}")
                
        # Save batches
        generator.save_batches(batches, Path(args.output_file))
        print(f"Saved to: {args.output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
