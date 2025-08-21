# Multiarrangement — Video & Audio Similarity Arrangement Toolkit

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Multiarrangement is a Python toolkit for collecting human similarity judgements by arranging stimuli (videos or audio) on a 2D canvas. The spatial arrangement encodes perceived similarity and is converted into a full Representational Dissimilarity Matrix (RDM) for downstream analysis.

Two complementary experiment paradigms are supported:

- Set‑Cover (fixed batches): Precompute batches that efficiently cover pairs; run them in a controlled sequence.
- Adaptive LTW (Lift‑the‑Weakest): After each trial, select the next subset that maximizes evidence gain for the weakest‑evidence pairs, with optional inverse‑MDS refinement.

The package ships with windowed and fullscreen UIs, packaged demo media (15 videos and 15 audios), instruction videos, bundled LJCR covering‑design cache (offline‑first), CLIs, and Python APIs.

## What’s Included

- Package code: `multiarrangement/*` (UI, core, adaptive LTW), `coverlib/*` (covering‑design tools)
- Demo media (installed): `multiarrangement/15videos/*`, `multiarrangement/15audios/*`, `multiarrangement/sample_audio/*`, and `multiarrangement/demovids/*`
- LJCR cache (installed): `multiarrangement/ljcr_cache/*.txt` used by covering‑design CLIs by default (offline‑first)
- Source only (not in wheel): `24videos/`, `58videos/`, tests, legacy scripts, large examples

## Install

From source:

```bash
git clone https://github.com/UYildiz12/Multiarrangement-for-videos.git
cd Multiarrangement-for-videos
pip install -e .[coverlib]
```

Requirements: Python 3.8+, NumPy ≥ 1.20, pandas ≥ 1.3, pygame ≥ 2.0, opencv‑python ≥ 4.5, openpyxl ≥ 3.0. The optional extra `[coverlib]` installs `requests/urllib3` for the `covergen` CLI.

## Demos

- Set‑cover (fixed batches):

```bash
multiarrangement-demo
```

- Adaptive LTW (Lift‑the‑Weakest):

```bash
multiarrangement-demo-adaptive
```

Both demos use the packaged `15videos` and show default instruction screens (with bundled instruction clips).

## CLI Usage

- Windowed experiment (set‑cover):

```bash
multiarrangement --video-dir ./videos --batch-file ./batches.txt --participant-id P001
```

- Fullscreen experiment (set‑cover):

```bash
multiarrangement-fullscreen --video-dir ./videos --batch-file ./batches.txt --participant-id P001
```

- Adaptive LTW experiment:

```bash
multiarrangement-adaptive \
  --input-dir ./videos \
  --participant-id P001 \
  --fullscreen \
  --evidence-threshold 0.35 \
  --min-subset-size 4 \
  --max-subset-size 6 \
  --use-inverse-mds
```

- Batch generation (set‑cover):

```bash
multiarrangement-batch-generator 24 8 --algorithm hybrid --validate --output-file batches_24x8.txt
```

- Covering‑design optimizers (offline‑first using the bundled cache):

```bash
# Fixed k
optimize-cover --v 24 --k 8 --offline-only --outfile cover_v24_k8.txt

# Flexible shrink‑only (min size 3)
optimize-cover-flex --v 24 --k 8 --min-k-size 3 --offline-only --outfile cover_v24_var.txt

# Prefetch more LJCR cache entries
optimize-cover --bulk-download --v-min 10 --v-max 40 --k-min 3 --k-max 8
```

Notes:

- If Tk is not available, pass `--video-dir`, `--batch-file`, and `--participant-id` rather than using GUI dialogs.
- Both cover CLIs default `--cache-dir` to the packaged cache under `multiarrangement/ljcr_cache` and can run fully offline for cached (v,k).

## Python API

### Set‑Cover Experiment

```python
import multiarrangement as ma

# Build batches for 24 items, size 8
batches = ma.create_batches(24, 8)

# Run experiment (English, windowed)
results = ma.multiarrangement(
    input_dir="./videos",
    batches=batches,
    output_dir="./results",
    fullscreen=False,
    language="en",
    instructions="default"  # or None, or ["Custom", "lines"]
)
results.vis(title="Set‑Cover RDM")
results.savefig("results/rdm_setcover.png", title="Set‑Cover RDM")
```

### Adaptive LTW Experiment (with optional inverse‑MDS)

```python
import multiarrangement as ma

results = ma.multiarrangement_adaptive(
    input_dir="./videos",
    output_dir="./results",
    fullscreen=True,
    evidence_threshold=0.35,   # stop when min pair evidence ≥ threshold
    min_subset_size=4,
    max_subset_size=6,
    use_inverse_mds=True,      # optional inverse‑MDS refinement
    inverse_mds_max_iter=15,
    inverse_mds_step_c=0.3,
    inverse_mds_tol=1e-4,
)
results.vis(title="Adaptive LTW RDM")
results.savefig("results/rdm_adaptive.png", title="Adaptive LTW RDM")

### Run the examples

We include four examples for both paradigms (video/audio). They save heatmaps to `./results`.

- From an installed package (recommended): run the in‑package example modules
  - `python -m multiarrangement.examples.setcover_video`
  - `python -m multiarrangement.examples.setcover_audio`
  - `python -m multiarrangement.examples.ltw_video`
  - `python -m multiarrangement.examples.ltw_audio`
  - These examples auto‑resolve the packaged media and create `./results` if missing.

- From the repo root (developer use): run the top‑level scripts
  - `python setcover_video.py`
  - `python setcover_audio.py`
  - `python ltw_video.py`
  - `python ltw_audio.py`
  - These scripts assume you are in the repo root where `15videos/` and `15audios/` exist.
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
- Tk missing: supply `--video-dir`, `--batch-file`, and `--participant-id` on the command line.
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
