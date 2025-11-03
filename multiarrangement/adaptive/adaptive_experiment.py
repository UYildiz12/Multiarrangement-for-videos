"""
Adaptive experiment class integrating the lift-the-weakest algorithm
with the existing UI expectations.

This class provides the same interface methods used by MultiarrangementInterface/
FullscreenInterface: get_current_batch_videos, record_arrangement, advance_to_next_batch,
save_results, etc., but chooses the next subset adaptively after each trial.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import time
import numpy as np
import pandas as pd
import os

from ..utils.video_processing import VideoProcessor
from ..utils.file_utils import get_video_files
from .lift_weakest import (
    TrialArrangement,
    estimate_rdm_weighted_average,
    select_next_subset_lift_weakest,
    refine_rdm_inverse_mds,
)


@dataclass
class AdaptiveConfig:
    evidence_threshold: float = 0.5  # stop when min pair evidence >= threshold
    utility_exponent: float = 10.0   # d in u(w)=1-exp(-d w)
    time_limit_seconds: Optional[float] = None  # total wall time limit
    target_time_seconds: Optional[float] = None  # per-trial target time (soft, enforced with tolerance)
    target_time_tolerance: float = 0.05         # allowable fractional overshoot
    min_subset_size: int = 3
    max_subset_size: Optional[int] = None
    time_cost_exponent: float = 1.5
    arena_max: float = 1.0
    use_inverse_mds: bool = True
    inverse_mds_max_iter: int = 15
    inverse_mds_tol: float = 1e-4
    inverse_mds_step_c: float = 0.3
    # New policy controls
    evidence_alpha: float = 2.0                # exponent for evidence weights
    unseen_boost: float = 0.0                 # add to utility for unseen items
    recency_penalty: float = 0.0              # penalize recently used items
    recency_decay: float = 0.85               # decay multiplier per trial for recency state
    stress_weight: float = 0.0                # weight for local stress heuristic
    max_jaccard: Optional[float] = None       # hard cap on Jaccard overlap vs. last subset
    overlap_penalty: float = 0.0              # soft penalty on overlap
    duration_cost_weight: float = 0.0         # add duration-weighted cost
    duration_cost_cap_per_item: Optional[float] = None  # cap per-item duration cost (sec)
    robust_method: Optional[str] = None       # 'winsor' | 'huber' | None
    robust_winsor_high: float = 0.98          # winsor high cutoff for normalized distances
    robust_huber_c: float = 0.9               # huber c threshold for normalized distances
    evidence_weight_mode: str = 'k2012'       # 'max' | 'rms' | 'k2012' (default: 'k2012')
    # Long-clip safeguards
    long_clip_threshold_seconds: Optional[float] = None
    min_long_clip_inclusion_rate: float = 0.0
    long_clip_boost: float = 0.0
    stop_on_utility: bool = False             # compare threshold on u(W)=1-exp(-dW) instead of raw W
    avoid_anchor_reuse: bool = False          # avoid reusing the exact previous anchor pair
    cold_start_require_unseen_trials: int = 0 # require at least one unseen in early trials


class AdaptiveMultiarrangementExperiment:
    """Adaptive experiment with lift-the-weakest subset selection."""

    def __init__(
        self,
        input_directory: str,
        participant_id: Optional[str] = None,
        output_directory: str = "Participantdata",
        config: Optional[AdaptiveConfig] = None,
        mode: str = "video",
        language: str = "en",
    ):
        self.input_directory = Path(input_directory)
        self.participant_id = participant_id
        self.output_directory = Path(output_directory)
        self.config = config or AdaptiveConfig()
        self.mode = mode
        self.language = language

        if not self.input_directory.exists():
            raise FileNotFoundError(f"Input directory not found: {self.input_directory}")

        # Load media files
        self.video_files = [p.name for p in get_video_files(self.input_directory)]
        if not self.video_files:
            # If no videos, allow audio files based on extension check
            supported = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}
            self.video_files = [f for f in os.listdir(self.input_directory) if Path(f).suffix.lower() in supported]

        if not self.video_files:
            raise ValueError(f"No supported media files found in {self.input_directory}")

        self.n = len(self.video_files)
        self.video_names = [os.path.splitext(f)[0] for f in self.video_files]
        self.index_map = {i: i for i in range(self.n)}

        # Debug/diagnostic: warn when too few media files are detected
        if self.n < 3:
            print(f"[warning] Only {self.n} media file(s) detected in '{self.input_directory}'. "
                  f"Adaptive subsets may repeat the same pair. "
                  f"Check file extensions or pass a broader extension list.")
        else:
            # Diagnostic: list a few detected files
            sample = ', '.join(self.video_files[:5])
            print(f"[info] Detected {self.n} media files. First few: {sample}")

        # State
        try:
            import os as _os
            self.rng_seed = int.from_bytes(_os.urandom(8), 'little')
        except Exception:
            self.rng_seed = None
        self.current_subset_indices: List[int] = list(range(self.n))  # trial 1: all items
        self.trials: List[TrialArrangement] = []
        self.trial_counter = 0
        self.experiment_completed = False
        self.start_time = time.time()

        # Estimations
        self.D_est = np.zeros((self.n, self.n), dtype=float)
        self.W = np.zeros((self.n, self.n), dtype=float)

        self.video_processor = VideoProcessor()
        # Policy state: seen, recent, durations
        self.seen = np.zeros((self.n,), dtype=bool)
        self.recent = np.zeros((self.n,), dtype=float)
        self.last_subset: Optional[List[int]] = None
        self.last_anchor_pair: Optional[Tuple[int, int]] = None
        self.durations = self._estimate_durations()
        # Long-clip mask and inclusion counts
        self.inclusion_counts = np.zeros((self.n,), dtype=int)
        thr = self.config.long_clip_threshold_seconds
        self.long_clip_mask = None
        if thr is not None:
            try:
                self.long_clip_mask = (self.durations >= float(thr))
            except Exception:
                self.long_clip_mask = None

    def _estimate_durations(self) -> np.ndarray:
        """Estimate per-item review durations (in seconds) for time-aware costs.

        Videos: from OpenCV props (frames/fps). Images: small constant (0.5s).
        Audio: try WAV via wave; else fallback to small constant (3s).
        """
        import cv2, wave, contextlib
        out = np.zeros((self.n,), dtype=float)
        for i, fn in enumerate(self.video_files):
            p = self.get_video_path(fn)
            ext = str(p.suffix).lower()
            try:
                if ext in {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}:
                    out[i] = 0.5
                elif ext in {'.mp3', '.ogg', '.flac', '.aac', '.m4a'}:
                    # Unknown compressed length without external libs; fallback
                    out[i] = 3.0
                elif ext in {'.wav'}:
                    with contextlib.closing(wave.open(str(p), 'r')) as f:
                        frames = f.getnframes(); rate = f.getframerate()
                        out[i] = float(frames) / float(rate) if rate > 0 else 3.0
                else:
                    cap = cv2.VideoCapture(str(p))
                    if cap.isOpened():
                        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        out[i] = float(frames / fps) if fps and fps > 0 else 5.0
                    else:
                        out[i] = 5.0
                    try:
                        cap.release()
                    except Exception:
                        pass
            except Exception:
                out[i] = 3.0
        return out

    # --- UI contract methods ---
    def get_current_batch_videos(self) -> List[str]:
        return [self.video_files[i] for i in self.current_subset_indices]

    def get_video_path(self, video_filename: str) -> Path:
        return self.input_directory / video_filename

    def record_arrangement(self, video_positions_by_name: Dict[str, Tuple[float, float]]) -> None:
        # Map back to global indices
        positions_by_idx: Dict[int, Tuple[float, float]] = {}
        for idx in self.current_subset_indices:
            name = self.video_names[idx]
            if name in video_positions_by_name:
                positions_by_idx[idx] = video_positions_by_name[name]

        # Save this trial result
        self.trials.append(TrialArrangement(subset=list(self.current_subset_indices), positions=positions_by_idx))

        # Re-estimate D and W using all trials so far
        self.D_est, self.W = estimate_rdm_weighted_average(
            self.n,
            self.trials,
            alpha=float(self.config.evidence_alpha),
            robust_method=self.config.robust_method,
            robust_winsor_high=float(self.config.robust_winsor_high),
            robust_huber_c=float(self.config.robust_huber_c),
            weight_mode=str(self.config.evidence_weight_mode),
        )
        # Optional inverse-MDS refinement
        if self.config.use_inverse_mds:
            self.D_est = refine_rdm_inverse_mds(
                self.D_est,
                self.trials,
                max_iter=self.config.inverse_mds_max_iter,
                tol=self.config.inverse_mds_tol,
                step_c=self.config.inverse_mds_step_c,
            )
        # Update policy state: mark seen and update recency with decay
        if positions_by_idx:
            sel = list(positions_by_idx.keys())
            self.seen[sel] = True
            # decay then bump
            self.recent *= float(self.config.recency_decay)
            self.recent[sel] += 1.0
            # Track inclusion counts
            for idx in sel:
                if 0 <= idx < self.n:
                    self.inclusion_counts[idx] += 1

    def advance_to_next_batch(self) -> bool:
        self.trial_counter += 1

        # Check termination conditions
        if self._time_up():
            self.experiment_completed = True
            return False

        # Evidence criterion: either min W >= threshold or min u(W) >= threshold
        iu = np.triu_indices(self.n, 1)
        if iu[0].size > 0:
            if self.config.stop_on_utility:
                # u(W) = 1 - exp(-d W)
                d = float(self.config.utility_exponent)
                u_vals = 1.0 - np.exp(-d * self.W[iu])
                min_u = float(np.min(u_vals))
                if min_u >= self.config.evidence_threshold:
                    self.experiment_completed = True
                    return False
            else:
                min_w = float(np.min(self.W[iu]))
                if min_w >= self.config.evidence_threshold:
                    self.experiment_completed = True
                    return False

        # Choose next subset via lift-the-weakest
        # Set optional avoidance of the last anchor pair
        avoid_pair = self.last_anchor_pair if self.config.avoid_anchor_reuse else None
        next_subset = select_next_subset_lift_weakest(
            self.D_est,
            self.W,
            utility_exponent=self.config.utility_exponent,
            time_cost_exponent=self.config.time_cost_exponent,
            arena_max=self.config.arena_max,
            min_size=self.config.min_subset_size,
            max_size=self.config.max_subset_size or self.n,
            seen=self.seen,
            recent=self.recent,
            last_subset=self.last_subset,
            avoid_anchor_pair=avoid_pair,
            max_jaccard=self.config.max_jaccard,
            overlap_penalty=self.config.overlap_penalty,
            recency_penalty=self.config.recency_penalty,
            unseen_boost=self.config.unseen_boost,
            stress_weight=self.config.stress_weight,
            durations=self.durations,
            duration_cost_weight=self.config.duration_cost_weight,
            target_time_seconds=self.config.target_time_seconds,
            target_time_tolerance=self.config.target_time_tolerance,
            duration_cost_cap_per_item=self.config.duration_cost_cap_per_item,
            inclusion_counts=self.inclusion_counts,
            long_clip_mask=self.long_clip_mask,
            min_long_clip_inclusion_rate=self.config.min_long_clip_inclusion_rate,
            long_clip_boost=self.config.long_clip_boost,
            trials_so_far=self.trial_counter,
            require_unseen=(self.trial_counter < int(self.config.cold_start_require_unseen_trials)),
        )

        # Diagnostic: print chosen subset size and a few names
        try:
            names = [self.video_names[i] for i in next_subset]
            print(f"[info] Trial {self.trial_counter}: selected subset size {len(next_subset)}: {names[:5]}{'...' if len(names)>5 else ''}")
        except Exception:
            pass

        # Safety fallback: if selector failed, sample a mid-sized random subset
        if not next_subset or len(next_subset) < self.config.min_subset_size:
            k = max(self.config.min_subset_size, min(6, self.n))
            next_subset = list(range(min(self.n, k)))

        # Avoid repeating the exact same subset
        if set(next_subset) == set(self.current_subset_indices) and len(next_subset) < self.n:
            # Add one new item if available
            remaining = [i for i in range(self.n) if i not in next_subset]
            if remaining:
                next_subset = next_subset + [remaining[0]]

        self.current_subset_indices = next_subset
        self.last_subset = list(next_subset)
        # Update last anchor pair from the first two indices (selection starts from anchors)
        if len(next_subset) >= 2:
            a, b = int(next_subset[0]), int(next_subset[1])
            self.last_anchor_pair = (min(a, b), max(a, b))
        return True

    def is_experiment_complete(self) -> bool:
        return self.experiment_completed

    def get_progress(self) -> Tuple[int, int]:
        # Unknown total trials in advance; report current trial count and 0 as placeholder total
        return (self.trial_counter + 1, 0)

    def save_results(self, output_dir: Optional[Path] = None) -> None:
        if output_dir is None:
            output_dir = self.output_directory
        output_dir.mkdir(parents=True, exist_ok=True)

        base = f"participant_{self.participant_id}" if self.participant_id else "adaptive_results"
        # Save RDM
        df = pd.DataFrame(self.D_est, index=self.video_names, columns=self.video_names)
        df.to_excel(output_dir / f"{base}_results.xlsx")
        np.save(output_dir / f"{base}_rdm.npy", self.D_est.astype(float))
        # Save evidence matrix
        np.save(output_dir / f"{base}_evidence.npy", self.W.astype(float))
        # Save metadata (subsets per trial)
        meta = {
            "participant_id": self.participant_id,
            "n_items": int(self.n),
            # Ensure JSON-serializable Python ints for trial indices
            "trials": [[int(i) for i in t.subset] for t in self.trials],
            "evidence_threshold": float(self.config.evidence_threshold),
            "utility_exponent": float(self.config.utility_exponent),
            "rng_seed": int(self.rng_seed) if self.rng_seed is not None else None,
        }
        import json
        with open(output_dir / f"{base}_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        print(f"Results saved to {output_dir}")

    # --- Helpers ---
    def _time_up(self) -> bool:
        if self.config.time_limit_seconds is None:
            return False
        return (time.time() - self.start_time) >= self.config.time_limit_seconds
