from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from .combinatorics import block_pairs, schonheim_lb
from .fetchers import fetch_ljcr_cover
from .cache import get_seed_blocks, save_blocks_file
from .optimizer import CoverOptimizer

@dataclass
class CoverResult:
    v: int
    k: int
    blocks: List[Tuple[int,...]]  # 0-based
    b: int
    lmax: int
    hist: Dict[int,int]
    sumsq: int

def generate_cover(
    v: int,
    k: int,
    *,
    passes: int = 12,
    greedy_trials: int = 2,
    forbid_above: int = 2,
    group_rounds: int = 12,
    group_time: float = 10.0,
    group_cands: int = 100,
    cache_dir: Optional[str] = None,
    offline_only: bool = False,
    seed_file: Optional[str] = None,
    seed: int = 12345,
) -> CoverResult:
    """High-level API: fetch/cache seed, then rebalance and return result (0-based blocks)."""
    from .repair import coverage_from_blocks  # local import to avoid cycles

    if seed_file:
        path = Path(seed_file)
        from .cache import read_blocks_file
        blocks = read_blocks_file(path, v, k)
    else:
        if cache_dir:
            cache = Path(cache_dir)
        else:
            try:
                import multiarrangement
                cache = Path(multiarrangement.__file__).parent / "ljcr_cache"
            except Exception:
                cache = Path("ljcr_cache")
        blocks = get_seed_blocks(v, k, cache, offline_first=True, offline_only=offline_only, fetcher=fetch_ljcr_cover)

    counts, _ = coverage_from_blocks(v, blocks)
    if min(counts) < 1:
        from .repair import repair_to_coverage
        blocks = repair_to_coverage(v, k, blocks)

    opt = CoverOptimizer(v, blocks, seed=seed)
    forbid = None if forbid_above < 0 else forbid_above
    opt.local_search(passes=passes, forbid_above=forbid, greedy_trials=greedy_trials)

    improved = True
    r = group_rounds
    while r>0 and improved:
        r -= 1
        lnow = opt.lambda_max()
        if lnow <= 2: break
        improved = opt.reduce_lmax_group(target=lnow-1, time_limit=group_time,
                                         max_pairs_considered=20, candidates_per_block=group_cands)

    return CoverResult(v=v, k=k, blocks=opt.blocks, b=len(opt.blocks), lmax=opt.lambda_max(), hist=opt.histogram(), sumsq=opt.sumsq())
