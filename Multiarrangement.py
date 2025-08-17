#!/usr/bin/env python3
"""
Legacy Multiarrangement script - now calls the library function.
Maintained for backward compatibility.

This script runs the multiarrangement experiment using the same configuration
as the original script but now uses the refactored library interface.
"""

import multiarrangement as ml
import os

def main():
    """Legacy main function - now uses the library interface."""
    
    # Configuration (can be modified for different setups)
    input_dir = os.path.join(os.path.dirname(__file__), "58videos")
    batch_file = os.path.join(os.path.dirname(__file__), 'batches_58videos_batchsize8.txt')
    output_dir = os.path.join(os.path.dirname(__file__), "results")
    
    print("Starting Multiarrangement Experiment (Legacy Script)")
    print("=" * 60)
    print(f"Input directory: {input_dir}")
    print(f"Batch file: {batch_file}")
    print(f"Output directory: {output_dir}")
    print()
    
    try:
        # Run the experiment using the library function
        result_file = ml.multiarrangement(
            input_dir=input_dir,
            batches=batch_file,  # Use existing batch file
            output_dir=output_dir,
            show_first_frames=True,
            fullscreen=True
        )
        
        print(f"\nExperiment completed successfully!")
        print(f"Results saved to: {result_file}")
        
    except Exception as e:
        print(f"Error running experiment: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())