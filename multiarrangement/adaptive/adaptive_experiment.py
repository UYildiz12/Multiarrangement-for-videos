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
    min_subset_size: int = 3
    max_subset_size: Optional[int] = None
    time_cost_exponent: float = 1.5
    arena_max: float = 1.0
    use_inverse_mds: bool = True
    inverse_mds_max_iter: int = 15
    inverse_mds_tol: float = 1e-4
    inverse_mds_step_c: float = 0.3


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
        self.current_subset_indices: List[int] = list(range(self.n))  # trial 1: all items
        self.trials: List[TrialArrangement] = []
        self.trial_counter = 0
        self.experiment_completed = False
        self.start_time = time.time()

        # Estimations
        self.D_est = np.zeros((self.n, self.n), dtype=float)
        self.W = np.zeros((self.n, self.n), dtype=float)

        self.video_processor = VideoProcessor()

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
        self.D_est, self.W = estimate_rdm_weighted_average(self.n, self.trials)
        # Optional inverse-MDS refinement
        if self.config.use_inverse_mds:
            self.D_est = refine_rdm_inverse_mds(
                self.D_est,
                self.trials,
                max_iter=self.config.inverse_mds_max_iter,
                tol=self.config.inverse_mds_tol,
                step_c=self.config.inverse_mds_step_c,
            )

    def advance_to_next_batch(self) -> bool:
        self.trial_counter += 1

        # Check termination conditions
        if self._time_up():
            self.experiment_completed = True
            return False

        # Evidence criterion: min off-diagonal W >= threshold
        iu = np.triu_indices(self.n, 1)
        if iu[0].size > 0:
            min_w = float(np.min(self.W[iu]))
            if min_w >= self.config.evidence_threshold:
                self.experiment_completed = True
                return False

        # Choose next subset via lift-the-weakest
        next_subset = select_next_subset_lift_weakest(
            self.D_est,
            self.W,
            utility_exponent=self.config.utility_exponent,
            time_cost_exponent=self.config.time_cost_exponent,
            arena_max=self.config.arena_max,
            min_size=self.config.min_subset_size,
            max_size=self.config.max_subset_size or self.n,
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
