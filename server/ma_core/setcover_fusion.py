"""
Set-cover fusion utilities for web backend.

Implements the same fusion modes as the desktop library:
- max: per-trial max-normalized distances with weights (d/max)^alpha
- rms: RMS-matched weighted average
- k2012: raw center-distance weights + RMS-matched numerator
Optional robust weighting and inverse-MDS refinement.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple
import math
import numpy as np

from .lift_weakest import (
    TrialArrangement,
    estimate_rdm_weighted_average,
    refine_rdm_inverse_mds,
)


def _pairwise_distances_from_positions(
    subset: list[int],
    positions: dict[int, tuple[float, float]],
    arena_center: tuple[float, float] | None = None,
    arena_radius: float | None = None,
) -> np.ndarray:
    m = len(subset)
    D = np.zeros((m, m), dtype=float)
    for i in range(m):
        xi, yi = positions[subset[i]]
        xi, yi = _normalize_point(xi, yi, arena_center, arena_radius)
        for j in range(i + 1, m):
            xj, yj = positions[subset[j]]
            xj, yj = _normalize_point(xj, yj, arena_center, arena_radius)
            d = float(np.hypot(xi - xj, yi - yj))
            D[i, j] = D[j, i] = d
    return D


def _normalize_point(
    x: float,
    y: float,
    arena_center: tuple[float, float] | None,
    arena_radius: float | None,
) -> tuple[float, float]:
    if arena_center is None or arena_radius is None:
        return x, y
    radius = float(arena_radius)
    if not math.isfinite(radius) or radius <= 1e-12:
        return x, y
    cx, cy = arena_center
    return (x - float(cx)) / radius, (y - float(cy)) / radius


def fuse_setcover(
    n_items: int,
    trials: Iterable[TrialArrangement],
    *,
    weight_mode: str = "max",
    alpha: float = 2.0,
    robust_method: Optional[str] = None,
    robust_winsor_high: float = 0.98,
    robust_huber_c: float = 0.9,
    use_inverse_mds: bool = False,
    inverse_mds_max_iter: int = 15,
    inverse_mds_step_c: float = 0.3,
    inverse_mds_tol: float = 1e-4,
) -> Tuple[np.ndarray, np.ndarray]:
    """Fuse set-cover trials into a full RDM and evidence matrix."""
    trials = list(trials)
    if n_items <= 0:
        return np.zeros((0, 0), dtype=float), np.zeros((0, 0), dtype=float)

    # max-normalized fusion (matches experiment_runner)
    if weight_mode == "max":
        Num = np.zeros((n_items, n_items), dtype=float)
        W = np.zeros((n_items, n_items), dtype=float)

        _robust_winsor = (robust_method == "winsor")
        _robust_huber = (robust_method == "huber")

        for t in trials:
            subset = list(t.subset)
            if len(subset) < 2 or not t.positions:
                continue
            D_sub = _pairwise_distances_from_positions(subset, t.positions, t.arena_center, t.arena_radius)
            iu = np.triu_indices(len(subset), 1)
            maxd = float(np.max(D_sub[iu])) if iu[0].size else 0.0
            norm = (1.0 / maxd) if maxd > 1e-12 else 0.0

            for a in range(len(subset)):
                ia = subset[a]
                for b in range(a + 1, len(subset)):
                    ib = subset[b]
                    dnorm = D_sub[a, b] * norm
                    if _robust_winsor:
                        hi = float(robust_winsor_high)
                        if hi > 0.0:
                            dnorm = min(dnorm, hi)
                    if _robust_huber:
                        c = float(robust_huber_c)
                        if dnorm <= 0.0:
                            w = 0.0
                        else:
                            wfactor = 1.0 if dnorm <= c else (c / dnorm)
                            w = (dnorm ** float(alpha)) * wfactor
                    else:
                        w = dnorm ** float(alpha)

                    Num[ia, ib] += w * dnorm
                    Num[ib, ia] += w * dnorm
                    W[ia, ib] += w
                    W[ib, ia] += w

        with np.errstate(divide="ignore", invalid="ignore"):
            D_hat = np.divide(Num, W, out=np.zeros_like(Num), where=W > 0)
        np.fill_diagonal(D_hat, 0.0)

        # Final RMS renormalization for max mode
        try:
            iu = np.triu_indices_from(D_hat, k=1)
            rms = float(np.sqrt(np.mean(D_hat[iu] * D_hat[iu]))) if iu[0].size else 0.0
            if rms > 1e-12:
                D_hat *= (1.0 / rms)
                np.fill_diagonal(D_hat, 0.0)
        except Exception:
            pass

    else:
        # rms or k2012
        D_hat, W = estimate_rdm_weighted_average(
            n_items,
            trials,
            alpha=float(alpha),
            robust_method=robust_method,
            robust_winsor_high=float(robust_winsor_high),
            robust_huber_c=float(robust_huber_c),
            weight_mode=str(weight_mode),
        )
        np.fill_diagonal(D_hat, 0.0)

    # Optional inverse-MDS refinement
    if use_inverse_mds and trials:
        try:
            D_hat = refine_rdm_inverse_mds(
                D_hat,
                trials,
                max_iter=int(inverse_mds_max_iter),
                tol=float(inverse_mds_tol),
                step_c=float(inverse_mds_step_c),
            )
            np.fill_diagonal(D_hat, 0.0)
        except Exception:
            pass

    return D_hat, W
