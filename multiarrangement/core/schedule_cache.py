"""Validated cached selection shared by the desktop and hosted schedulers."""

from pathlib import Path
from typing import List, Optional
import math


def load_indexed_schedule(
    n_items: int,
    batch_size: int,
    *,
    mode: str,
    max_extra_fraction: float = 0.0,
) -> Optional[List[List[int]]]:
    """Select the stored objective optimum within the explicit cached trial budget.

    These are best known portfolio choices; global optimality requires the
    individual schedule certificate. Missing or invalid assets return no cover.
    """
    import multiarrangement as ma
    from coverlib.frontier import select_frontier_cover

    package = Path(ma.__file__).resolve().parent
    compact = select_frontier_cover(n_items, batch_size, package_dir=package, mode="compact")
    if compact is None or not compact.certificate.complete or not compact.certificate.simple:
        return None
    if mode == "compact":
        selected = compact
    elif mode == "balanced":
        extra = float(max_extra_fraction)
        if not math.isfinite(extra) or extra < 0:
            raise ValueError("max_extra_fraction must be finite and nonnegative")
        limit = compact.certificate.b + math.floor(compact.certificate.b * extra)
        selected = select_frontier_cover(n_items, batch_size, package_dir=package,
                                         mode="balanced", max_blocks=limit)
    else:
        raise ValueError("mode must be compact or balanced")
    if selected is None or not selected.certificate.complete or not selected.certificate.simple:
        return None
    return [list(block) for block in selected.blocks]
