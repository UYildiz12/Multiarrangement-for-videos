# Multiarrangement — Video & Audio Similarity Arrangement Toolkit

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Multiarrangement is a Python toolkit for collecting human similarity judgements by arranging stimuli (videos or audio) on a 2D canvas. The spatial arrangement encodes perceived similarity and is converted into a full Representational Dissimilarity Matrix (RDM) for downstream analysis.

Two complementary experiment paradigms are supported:

- Set‑Cover (fixed batches): Precompute batches that efficiently cover pairs; run them in a controlled sequence.
- Adaptive LTW (Lift‑the‑Weakest): After each trial, select the next subset that maximizes evidence gain for the weakest‑evidence pairs, with optional inverse‑MDS refinement.

The package ships with windowed and fullscreen UIs, packaged demo media (15 videos and 15 audios), instruction videos, bundled LJCR covering‑design cache, and Python APIs.

## Quick Demo

![Multiarrangement Demo](similar_demo.gif)

*Demo showing the Multiarrangement interface for collecting similarity judgments*



## What’s Included

- Package code: `multiarrangement/*` (UI, core, adaptive LTW), `coverlib/*` (covering‑design tools)
- Demo media (installed):
  - Videos: `multiarrangement/15videos/*`
  - Images: `multiarrangement/15images/*`
  - Audio:  `multiarrangement/15audios/*`, `multiarrangement/sample_audio/*`
  - Instruction clips: `multiarrangement/demovids/*`
- LJCR cache (installed): `multiarrangement/ljcr_cache/*.txt` used by covering‑design CLIs by default (offline‑first)

## Install

### Using uv 
```bash
uv pip install multiarrangement
```

### Using pip
```bash
pip install multiarrangement
```

Requirements: Python 3.8+, NumPy ≥ 1.20, pandas ≥ 1.3, pygame ≥ 2.0, opencv‑python ≥ 4.5, openpyxl ≥ 3.0.




 
## Python API


Set‑cover Demo (fixed batches):

```python
import multiarrangement as ma

ma.demo()

```

Adaptive LTW Demo (Lift‑the‑Weakest):

```python
import multiarrangement as ma

ma.demo_adaptive()

```

Both demos use the packaged `15videos` and show default instruction screens (with bundled instruction clips).

Image/Audio Demos (package assets):

```python
import multiarrangement as ma

# Audio-only demos
ma.demo_audio()             # set‑cover
ma.demo_audio_adaptive()    # adaptive LTW

# Image-only demos (uses packaged 15images; if missing, auto‑generates from 15videos)
ma.demo_image()             # set‑cover
ma.demo_image_adaptive()    # adaptive LTW
```

## The simplest way to use Multiarrangement is with the minimum arguments
```python

import multiarrangement as ma

input_dir = "path/to/input/directory"

output_dir = "path/to/output/directory"

batches = ma.create_batches(ma.auto_detect_stimuli(input_dir), 8)
# For variable-size batches instead, set flex=True:
# batches = ma.create_batches(ma.auto_detect_stimuli(input_dir), 8, flex=True)
results = ma.multiarrangement(input_dir, batches, output_dir)
results.vis()
results.savefig(f"{output_dir}/rdm_setcover.png", title="Set‑Cover RDM")

```

Or if you'd like to use the LTW algorithm

```python

import multiarrangement as ma

input_dir = "path/to/input/directory"
output_dir = "path/to/output/directory"

results = ma.multiarrangement_adaptive(input_dir, output_dir)
results.vis()
results.savefig(f"{output_dir}/rdm_adaptive.png", title="Adaptive LTW RDM")


```

Results file will be available via .xlsx and .csv versions in "datetime.xlsx/csv" format at output directory.

Notes:
- Image stimuli are supported alongside video/audio. The UI will show image‑specific instructions for image‑only folders.
- If a directory mixes media types (e.g., images + videos), a confirmation prompt appears so you can cancel or proceed.

### Set‑Cover Experiment (More detailed)

```python
import multiarrangement as ma

# Build batches for 24 items, size 8 (hybrid by default)
# Fixed-size batches (flex=False)
batches = ma.create_batches(24, 8, seed=42, flex=False)
# Or variable-size batches (shrink-only):
# batches = ma.create_batches(24, 8, seed=42, flex=True)

# Run experiment (English, windowed)
results = ma.multiarrangement(
    input_dir="./videos",   #Where your videos or audios are
    batches=batches,
    output_dir="./results", #Where your results will appear 
    show_first_frames=True,
    fullscreen=False,
    language="en", # Or tr if you'd like Turkish instructions
    instructions="default"  # or None, or ["Custom", "lines"]
)
results.vis(title="Set‑Cover RDM")
results.savefig("results/rdm_setcover.png", title="Set‑Cover RDM")
```

### Adaptive LTW Experiment  (More detailed) 

```python
import multiarrangement as ma

results = ma.multiarrangement_adaptive(
    input_dir="./videos",
    output_dir="./results",
    participant_id="participant",
    fullscreen=True,
    language="en",
    evidence_threshold=0.35,   # stop when min pair evidence ≥ threshold
    utility_exponent=10.0,
    time_limit_minutes=None,
    min_subset_size=4,
    max_subset_size=6,
    use_inverse_mds=True,      # optional inverse‑MDS refinement
    inverse_mds_max_iter=15,
    inverse_mds_step_c=0.3,
    inverse_mds_tol=1e-4,
    instructions="default",
)
results.vis(title="Adaptive LTW RDM")
results.savefig("results/rdm_adaptive.png", title="Adaptive LTW RDM")

```

### Run the examples

We include four examples for both paradigms (video/audio). They save heatmaps to `./results`.

```bash
# Set-cover examples
python -m multiarrangement.examples.setcover_video
python -m multiarrangement.examples.setcover_audio

# Adaptive LTW examples  
python -m multiarrangement.examples.ltw_video
python -m multiarrangement.examples.ltw_audio
```
These examples auto‑resolve the packaged media and create `./results` if missing.

### CLI Demos

```bash
# Video demos
multiarrangement-demo
multiarrangement-demo-adaptive

# Audio demos
multiarrangement-demo-audio
multiarrangement-demo-audio-adaptive

# Image demos
multiarrangement-demo-image
multiarrangement-demo-image-adaptive
```

### Custom Instructions (both paradigms)

```python
custom = [
    "Welcome to the lab.",
    "Drag each item inside the white circle.",
    "Double‑click to play/replay.",
    "Press SPACE to continue."
]

# Set‑cover
ma.multiarrangement(
    input_dir="./videos",
    batches=batches,
    output_dir="./results",
    instructions=custom,    # show these lines instead of defaults
)

# Adaptive LTW
ma.multiarrangement_adaptive(
    input_dir="./videos",
    output_dir="./results",
    instructions=custom,    # also supported here
)
```

Key ideas:

- Evidence is normalized per trial: `w_ij = (d_ij / max_d)^2` so absolute pixel scale does not dominate.
- Next subset is chosen greedily to maximize (utility gain)/(time cost), starting from the globally weakest‑evidence pair.
- Optional inverse‑MDS refinement reduces arrangement prediction error across trials.

## Instruction Screens

- Default instructions include short videos (bundled in `demovids/`) showing drag, double‑click, and completion.
- To skip instructions, pass `instructions=None`. To customize, pass a list of strings.

## Outputs

- Set‑cover: `participant_<id>_results.xlsx`, `participant_<id>_rdm.npy`, CSV (optional)
- Adaptive LTW: `adaptive_results_results.xlsx`, `adaptive_results_rdm.npy`, `adaptive_results_evidence.npy`, `adaptive_results_meta.json`

## Covering Designs

- Two optimizers are provided:
  - `optimize-cover`: fixed k; cache‑first LJCR seed, repair/prune, local search + group DFS
  - `optimize-cover-flex`: shrink‑only; starts from fixed k and may reduce block sizes down to `--min-k-size`
- Both prefer the installed cache path by default and support `--seed-file` to run from your own seeds.

## Troubleshooting

- Pygame/OpenCV: on minimal Linux, install SDL2 and video codecs via your package manager.
- Audio playback: Windows uses Windows Media Player (fallback), macOS `afplay`, Linux `paplay`/`aplay`.

## References

- Inverse MDS (adaptive refinement):
  - Kriegeskorte, N., & Mur, M. (2012). Inverse MDS: optimizing the stimulus arrangements for pairwise dissimilarity measures. Frontiers in Psychology, 3, 245. https://doi.org/10.3389/fpsyg.2012.00245
- Demo video dataset:
  - Urgen, B. A., Nizamoğlu, H., Eroğlu, A., & Orban, G. A. (2023). A large video set of natural human actions for visual and cognitive neuroscience studies and its validation with fMRI. Brain Sciences, 13(1), 61. https://doi.org/10.3390/brainsci13010061

## License

MIT License. See `LICENSE`.

## Contributing

Issues and PRs are welcome. Please add tests for new functionality and keep changes focused.
