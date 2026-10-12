from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .cache import get_seed_blocks
from .certificates import certify_schedule, compact_sort_key
from .constructions import certified_compact_cover, structured_cover_candidates
from .fetchers import fetch_ljcr_cover
from .frontier import select_frontier_cover
from .optimizer import CoverOptimizer
from .refinement import improve_item_balance


@dataclass
class CoverResult:
    v: int
    k: int
    blocks: List[Tuple[int, ...]]  # 0-based
    b: int
    lmax: int
    hist: Dict[int,int]
    sumsq: int
    source: str = "search"
    certificate: Optional[dict] = None


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
    """Generate a compact cover, preferring deterministic certified constructions."""
    from .repair import coverage_from_blocks  # local import to avoid cycles

    if seed_file:
        path = Path(seed_file)
        from .cache import read_blocks_file

        blocks = read_blocks_file(path, v, k)
        source = "seed_file"
    else:
        constructed = certified_compact_cover(v, k)
        if constructed is not None:
            blocks = list(constructed.blocks)
            certificate = certify_schedule(v, k, blocks, source=constructed.source)
            return CoverResult(
                v=v,
                k=k,
                blocks=blocks,
                b=len(blocks),
                lmax=certificate.lambda_max,
                hist=dict(certificate.pair_histogram),
                sumsq=sum(count * count * frequency for count, frequency in certificate.pair_histogram),
                source=constructed.source,
                certificate=certificate.to_dict(),
            )
        package_dir: Optional[Path] = None
        try:
            import multiarrangement

            package_dir = Path(multiarrangement.__file__).resolve().parent
        except Exception:
            local_package = Path("multiarrangement")
            if local_package.exists():
                package_dir = local_package.resolve()

        frontier = (
            select_frontier_cover(
                v,
                k,
                package_dir=package_dir,
                mode="compact",
            )
            if package_dir is not None
            else None
        )
        if frontier is not None:
            blocks = list(frontier.blocks)
            source = f"frontier:{frontier.source}"
        else:
            blocks = []
            source = "greedy_repair"

        if cache_dir:
            cache = Path(cache_dir)
        else:
            cache = (
                package_dir / "ljcr_cache"
                if package_dir is not None
                else Path("ljcr_cache")
            )
        if not blocks:
            try:
                blocks = get_seed_blocks(
                    v,
                    k,
                    cache,
                    offline_first=True,
                    offline_only=offline_only,
                    fetcher=fetch_ljcr_cover,
                )
                source = "ljcr_or_cache"
            except Exception:
                if offline_only:
                    raise
                blocks = []
                source = "greedy_repair"

    counts, _ = coverage_from_blocks(v, blocks)
    if min(counts) < 1:
        from .repair import repair_to_coverage
        blocks = repair_to_coverage(v, k, blocks)

    incumbent_blocks = [tuple(block) for block in blocks]
    opt = CoverOptimizer(v, blocks, seed=seed)
    forbid = None if forbid_above < 0 else forbid_above
    opt.local_search(passes=passes, forbid_above=forbid, greedy_trials=greedy_trials)

    improved = True
    r = group_rounds
    while r > 0 and improved:
        r -= 1
        lnow = opt.lambda_max()
        if lnow <= 2:
            break
        improved = opt.reduce_lmax_group(
            target=lnow - 1,
            time_limit=group_time,
            max_pairs_considered=20,
            candidates_per_block=group_cands,
        )

    result_blocks = opt.blocks
    result_source = source
    result_key = compact_sort_key(v, k, result_blocks)
    incumbent_key = compact_sort_key(v, k, incumbent_blocks)
    if incumbent_key < result_key:
        result_blocks = incumbent_blocks
        result_key = incumbent_key
    for constructed in structured_cover_candidates(v, k):
        candidate_key = compact_sort_key(v, k, constructed.blocks)
        if candidate_key < result_key:
            result_blocks = list(constructed.blocks)
            result_source = constructed.source
            result_key = candidate_key

    refined = [tuple(block) for block in improve_item_balance(v, k, result_blocks)]
    if compact_sort_key(v, k, refined) < result_key:
        result_blocks = refined
        result_source += ":item_refinement"
    certificate = certify_schedule(v, k, result_blocks, source=result_source)
    return CoverResult(
        v=v,
        k=k,
        blocks=result_blocks,
        b=len(result_blocks),
        lmax=certificate.lambda_max,
        hist=dict(certificate.pair_histogram),
        sumsq=sum(
            count * count * frequency
            for count, frequency in certificate.pair_histogram
        ),
        source=result_source,
        certificate=certificate.to_dict(),
    )
