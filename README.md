# Multiarr - Video Similarity Arrangement Task

## Overview
Multiarr is a psychological experiment tool that allows participants to arrange videos based on perceived similarity. Videos are presented as interactive circles that can be dragged around in a circular arena. The spatial arrangement of these videos represents the participant's perception of similarity - videos placed closer together are considered more similar, while those placed further apart are considered more different.

## Features
- Fullscreen interactive interface
- Video playback on double-click
- Drag-and-drop arrangement of video thumbnails
- Automatic data collection and storage
- Batch processing of video sets
- Representational Dissimilarity Matrix (RDM) generation

## Requirements
- Python 3.6+
- PyGame
- OpenCV (cv2)
- NumPy
- Pandas
- Tkinter
- Jupyter Notebook (for post-processing)

## Installation
1. Clone this repository
2. Install the required dependencies:
```
pip install pygame opencv-python numpy pandas jupyter
```
3. Ensure you have Tkinter installed (usually comes with Python)

## Directory Structure
```
Multiarr/
├── Multiarrangement_fullscreen.py  # Main fullscreen application
├── Multiarrangement.py             # Alternative non-fullscreen version
├── Batchmaker_bruteforce.py        # Bruteforce batch generation algorithm
├── Batchmaker_greedy.py            # Greedy batch generation algorithm
├── Rescaling_Notebook.ipynb        # User-friendly post-processing notebook
├── Rescaling after experiment.ipynb # Original post-processing notebook
├── generate_example_data.py        # Script to generate example data
├── batches_*videos_batchsize*.txt  # Batch configuration files (examples)
├── 58videos/                       # Directory containing 58 video files
├── 24videos/                       # Directory containing 24 video files
├── 15videos/                       # Directory containing 15 video files
├── demovids/                       # Directory containing demo videos
├── ExampleData/                    # Directory containing example data
└── Participantdata/                # Output directory (created automatically)
    ├── participant_1_results.xlsx
    ├── participant_1_rdm.npy
    └── ...
```

## Video Files
The program expects video files to be in a directory named according to the number of videos you're using (e.g., "58videos", "24videos", etc.), with the videos named as numbers (e.g., "1.mp4", "2.mp4", etc.). These numbers should correspond to the indices in the batch file.

You can use different video sets by:
1. Creating a directory with the appropriate name (e.g., "32videos")
2. Placing your videos in that directory with numeric names
3. Generating a batch file for that specific number of videos
4. Modifying the video path in the main script if needed

## Batch Configuration
The batch file (e.g., `batches_25videos_batchsize8.txt`) should contain comma-separated lists of video indices, with each line representing a batch. For example:
```
1,5,8,12,15,18,22,25
2,6,9,13,16,19,23,26
...
```

### Generating Batch Files
Users should generate their own batch files based on their specific requirements for video count and batch size. The provided batch files are just examples.

Two algorithms are available for batch generation:

1. **Bruteforce Algorithm** (`Batchmaker_bruteforce.py`): Minimizes the total number of batches needed to ensure all pairs of videos appear together at least once. This produces the optimal solution but can be computationally intensive for large video sets. Works well for up to 32 videos.

2. **Greedy Algorithm** (`Batchmaker_greedy.py`): Much more efficient for large video sets but may not produce the minimum number of batches. Recommended for experiments with many videos.

To generate a batch file:

#### Using Bruteforce Algorithm:
```
python Batchmaker_bruteforce.py
```
You can modify the video count and batch size by editing these lines in the script:
```python
# Number of videos in your dataset
my_list = list(range(0,25))
# How many should appear in the screen at once
batch_size = 8
```

#### Using Greedy Algorithm:
```
python Batchmaker_greedy.py
```
You can modify the video count and batch size by editing these lines in the script:
```python
# Number of videos in your dataset
n_videos = 25
# How many should appear in the screen at once
batch_size = 8
```

Both scripts will generate a file named `batches_[number_of_videos]videos_batchsize[batch_size].txt` that can be used with the main application.

## Usage
1. Run the main script:
```
python Multiarrangement_fullscreen.py
```
2. Enter the participant number when prompted
3. Read the instructions and press any key to begin
4. For each batch:
   - Drag videos to arrange them by similarity
   - Double-click a video to play it
   - Press the "Done" button in the left corner when satisfied with the arrangement
5. Results will be saved automatically in the "Participantdata" directory

## Alternative Version
An alternative non-fullscreen version is available:
```
python Multiarrangement.py
```
This version provides similar functionality but runs in a windowed mode instead of fullscreen.

## Data Output
For each participant, two files are generated:
1. `participant_X_results.xlsx`: Contains pairwise distances between all videos
2. `participant_X_rdm.npy`: Numpy array containing the Representational Dissimilarity Matrix

## Post-Processing
After collecting data from participants, you can use the included Jupyter notebooks for post-processing:

### Rescaling Notebook
```
jupyter notebook "Rescaling_Notebook.ipynb"
```
This is a rescaling notebook that:
- Uses relative paths instead of absolute paths
- Includes detailed documentation and explanations
- Provides visualization of both original and rescaled data

## Controls
- **Left-click and drag**: Move a video
- **Double-click**: Play a video
