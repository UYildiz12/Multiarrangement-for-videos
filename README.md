# Multiarrangement - Video & Audio Similarity Arrangement Task

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Multiarrangement is a comprehensive Python package for conducting psychological experiments where participants arrange videos or audio files based on perceived similarity. The package provides both windowed and fullscreen interactive interfaces where stimuli are presented as draggable circles in a circular arena. The spatial arrangement represents the participant's perception of similarity, generating Representational Dissimilarity Matrices (RDMs) for analysis.

## Features

- **Modern Package Structure**: Properly organized Python package with modular components
- **Dual Interface Modes**: Both windowed and fullscreen experiment interfaces
- **Multi-Modal Support**: Support for both video and audio stimuli
- **Interactive Arrangement**: Drag-and-drop interface with real-time feedback
- **Advanced Batch Generation**: Three-tier optimization system for creating balanced stimulus batches
- **Comprehensive Data Export**: Multiple output formats (Excel, CSV, NumPy arrays)
- **CLI Tools**: Command-line interfaces for all major functions
- **Data Validation**: Built-in validation for batch configurations and experimental data
- **Extensible Design**: Easy to customize and extend for specific research needs
- **Covering Design Optimization**: Advanced algorithms for optimal experimental design

## Installation

### From PyPI (when published)
```bash
pip install multiarrangement
```

### From Source
```bash
git clone https://github.com/UYildiz12/Multiarrangement-for-videos.git
cd Multiarrangement-for-videos
pip install -e .
```

### Requirements
- Python 3.8+
- NumPy >= 1.20.0
- Pandas >= 1.3.0
- Pygame >= 2.0.0
- OpenCV-Python >= 4.5.0
- openpyxl >= 3.0.0

### Optional Dependencies
For covering design optimization:
```bash
pip install multiarrangement[coverlib]
```

## Quick Start

### Basic Usage

1. **Run an experiment**:
```bash
# Windowed mode
multiarrangement

# Fullscreen mode
multiarrangement-fullscreen

# With specific parameters
multiarrangement --video-dir ./videos --batch-file ./batches.txt --participant-id P001
```

2. **Generate batch configurations**:
```bash
# Generate batches using hybrid approach (recommended)
multiarrangement-batch-generator 25 8 --algorithm hybrid --output-file my_batches.txt

# Use specific algorithms
multiarrangement-batch-generator 25 8 --algorithm optimal    # Try optimal only
multiarrangement-batch-generator 25 8 --algorithm greedy     # Python greedy only
```

3. **Use as a Python library**:

#### Minimal Example: Video Similarity Arrangement
```python
import multiarrangement as ma

# Create batches for 24 videos, batch size 8
batches = ma.create_batches(24, 8)

# Run video experiment (English instructions)
result_file = ma.multiarrangement(
    input_dir="./videos",
    batches=batches,
    output_dir="./results"
)
print("Results saved to:", result_file)
```

#### Minimal Example: Audio Similarity Arrangement
```python
import multiarrangement as ma

# Create batches for 24 audio files, batch size 8
batches = ma.create_batches(24, 8)

# Run audio experiment (Turkish instructions)
result_file = ma.multiarrangement(
    input_dir="./audio",
    batches=batches,
    output_dir="./results",
    mode="audio",           # Specify audio mode
    language="tr"           # Turkish instructions
)
print("Results saved to:", result_file)
```

#### Customizing Instructions
You can control the instructions shown before the experiment using the `instructions` argument:

- `instructions="default"` (or omit): Shows the standard instructions (with videos/images for video mode).
- `instructions=None`: Skips instructions entirely.
- `instructions=[...]`: Shows a custom list of instruction strings, centered on the screen. (Media is not shown for custom instructions.)

```python
# Custom instructions example
custom_instructions = [
    "Welcome to the custom experiment!",
    "Arrange the stimuli as you wish.",
    "Press SPACE to continue."
]

result_file = ma.multiarrangement(
    input_dir=input_dir,
    batches=batches,
    output_dir="./results",
    instructions=custom_instructions
)
```

#### Language and Mode
- The experiment automatically detects whether you are running a video or audio arrangement based on the input directory contents.
- You can set the instruction language with `language="en"` (English, default) or `language="tr"` (Turkish).

## Package Structure
```
multiarrangement/
├── __init__.py                     # Main package exports
├── cli.py                          # Command-line interfaces
├── experiment_runner.py             # High-level experiment runner
├── core/                           # Core experiment functionality
│   ├── __init__.py
│   ├── experiment.py               # Main experiment class
│   └── batch_generator.py          # Batch generation algorithms
├── ui/                             # User interface components
│   ├── __init__.py
│   ├── interface.py                # Base and windowed interface
│   └── fullscreen_interface.py     # Fullscreen interface
├── utils/                          # Utility modules
│   ├── __init__.py
│   ├── video_processing.py         # Video handling utilities
│   ├── data_processing.py          # Data analysis utilities
│   └── file_utils.py               # File and path utilities
├── data/                           # Package data files
│   ├── batches_*.txt               # Example batch configurations
│   └── img1.PNG                    # Interface assets
└── optimize_cover_*.py             # Covering design optimization

coverlib/                           # Covering design library
├── __init__.py
├── api.py                          # API for covering designs
├── cache.py                        # Caching system
├── cli.py                          # CLI for covering designs
├── combinatorics.py                # Combinatorial utilities
├── fetchers.py                     # Data fetching utilities
├── optimizer.py                    # Optimization algorithms
└── repair.py                       # Solution repair utilities

Additional Files:
├── Greedy_gen.c                    # C implementation of greedy algorithm
├── greedy_gen.exe                  # Compiled greedy algorithm
├── New_Greedy_1.py                 # Python greedy implementation
├── optimize_cover_pure.py          # Pure Python covering optimizer
└── Multiarrangement.py             # Legacy standalone script
```

## Stimulus Organization

The package supports flexible stimulus organization:

### Supported Video Formats
- `.avi`, `.mp4`, `.mov`, `.mkv`, `.wmv`, `.flv`, `.webm`

### Supported Audio Formats
- `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`

### Directory Structure
Stimuli can be organized in any directory structure. The package will automatically detect files and map them to batch indices. Example:

```
videos/
├── video_001.mp4
├── video_002.avi
├── action_walking.mp4
└── action_running.mp4

audio/
├── sound_001.wav
├── sound_002.mp3
├── music_sample.ogg
└── speech_sample.flac
```

### Batch Configuration
Batch files specify which stimuli appear together. Format examples:

```
# Simple comma-separated format
0,1,2,3
4,5,6,7
1,3,5,7

# Comments and empty lines are ignored
# Batch 1: similar actions
0,2,4,6
# Batch 2: different actions  
1,3,5,7
```

## Advanced Batch Generation

The package includes a sophisticated three-tier batch generation system:

### 🏆 Hybrid Approach (Recommended)
```bash
multiarrangement-batch-generator 25 8 --algorithm hybrid
```

**Tier 1: Optimal Solutions** (`optimize_cover_pure.py`)
- Fetches optimal covering designs from LJCR database
- Uses advanced local search and DFS optimization
- Produces mathematically optimal solutions when available
- May not work for all parameter combinations

**Tier 2: High-Performance Greedy** (`Greedy_gen.c`)
- Fast compiled C implementation with bitsets and max-heap
- Works for any valid parameters (n ≤ 255)
- Significantly faster than Python implementations
- Always finds a solution, though not necessarily optimal

**Tier 3: Python Fallback** (Pure Python)
- Always available, no dependencies
- Works on any platform
- Reasonable performance for small to medium datasets

### Algorithm Selection
```bash
# Try all tiers (recommended)
--algorithm hybrid

# Optimal only (fails if not available)
--algorithm optimal  

# High-performance C only
--algorithm greedy

# Python implementation only 
--algorithm brute_force  # Small datasets only
```

### Using Covering Design Library
```bash
# Generate covering designs directly
covergen 25 8 --output-file covering.txt

# Optimize existing designs
optimize-cover input.txt --output-file optimized.txt
```

## Legacy Scripts

For backward compatibility, several legacy scripts are included:

### Standalone Multiarrangement
```bash
python Multiarrangement.py
```
This provides a windowed interface similar to the main package.

### Greedy Algorithm Scripts
```bash
# Python greedy implementation
python New_Greedy_1.py

# C implementation (Windows executable)
./greedy_gen.exe
```

## Data Output

For each participant, multiple files are generated:
1. `participant_X_results.xlsx`: Contains pairwise distances between all stimuli
2. `participant_X_rdm.npy`: Numpy array containing the Representational Dissimilarity Matrix
3. `participant_X_distances.csv`: CSV format of the distance matrix

## Post-Processing

After collecting data from participants, you can use the included Jupyter notebook for post-processing:

### Rescaling Notebook
```bash
jupyter notebook "Rescaling_Notebook.ipynb"
```
This notebook provides:
- Detailed documentation and explanations
- Visualization of the data from the multiarrangement task
- Statistical analysis tools
- Data export capabilities

## Demo Videos and Data Sources

### Demo Videos
The package includes demo videos from the following source:

**A Large Video Set of Natural Human Actions for Visual and Cognitive Neuroscience Studies and Its Validation with fMRI**

*Reference:* Urgen, B. A., Nizamoğlu, H., Eroğlu, A., & Orban, G. A. (2023). A Large Video Set of Natural Human Actions for Visual and Cognitive Neuroscience Studies and Its Validation with fMRI. *Brain Sciences*, *13*(1), 61. https://doi.org/10.3390/brainsci13010061

The demo videos included in this package are derived from this dataset and are used for:
- **Instruction videos**: `demovids/` folder contains videos demonstrating the interface controls
- **Example datasets**: `15videos/`, `24videos/`, and `58videos/` folders contain sample video sets for testing and demonstration

### Sample Audio
The `sample_audio/` directory contains example audio files for testing audio arrangement experiments.

## Controls

### Video Mode
- **Left-click and drag**: Move a video circle
- **Double-click**: Play a video
- **Spacebar**: Continue to next batch
- **Escape**: Exit experiment

### Audio Mode
- **Left-click and drag**: Move an audio circle
- **Double-click**: Play a sound
- **Spacebar**: Continue to next batch
- **Escape**: Exit experiment

## Example Data

The `ExampleData/` directory contains:
- `participant_example.xlsx`: Example participant data
- `participant_example_rescaled.xlsx`: Example rescaled data

## Testing

Run the test suite:
```bash
pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use this package in your research, please cite both this package and the original video dataset:

*Citation information will be added soon.*

## Support

For issues and questions:
- Check the [Issues](https://github.com/UYildiz12/Multiarrangement-for-videos/issues) page
- Review the documentation in the code
- Contact the maintainers

## Updating Your Package on PyPI

After publishing, you can update your package at any time:
1. Make your changes in the codebase.
2. Increment the version number in `pyproject.toml` (and/or `setup.py`).
3. Build and upload the new version to PyPI using `twine`.
4. Users can upgrade with `pip install --upgrade multiarrangement`.

Repeat as needed for bug fixes and new features.
