"""
Batch generation algorithms for the Multiarrangement web API.

This module provides algorithms to generate optimal batches of stimuli that ensure
all pairs appear together at least once while minimizing the total number of batches.

Extracted from the original multiarrangement.core.batch_generator module,
stripped of pygame/opencv dependencies for server-side use.
"""

import itertools
import logging
import math
import os
import random
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_logger = logging.getLogger(__name__)
_warned_keys: Set[str] = set()


def _warn_once(key: str, message: str) -> None:
    """Warn once per process for degraded-math fallbacks (avoids log spam)."""
    if key not in _warned_keys:
        _warned_keys.add(key)
        _logger.warning(message)


class BatchGenerator:
    """
    Generate optimized batches for multiarrangement experiments.
    
    Uses a greedy covering algorithm with multiple restarts to find
    near-optimal batch configurations.
    """
    
    def __init__(self, n_items: int, batch_size: int, seed: Optional[int] = None):
        """
        Initialize the batch generator.
        
        Args:
            n_items: Total number of stimuli
            batch_size: Number of stimuli per batch
            seed: Random seed for reproducible results
        """
        self.n_items = n_items
        self.batch_size = batch_size
        self.item_indices = list(range(n_items))
        self.seed = seed
        
        if seed is not None:
            random.seed(seed)
            
        if batch_size < 2:
            raise ValueError("Batch size must be at least 2")
        if batch_size > n_items:
            raise ValueError("Batch size cannot be larger than number of items")
            
    def calculate_schonheim_lower_bound(self) -> int:
        """
        Calculate the Schönheim lower bound for the minimum number of batches needed.
        
        Returns:
            Theoretical minimum number of batches
        """
        v = self.n_items
        k = self.batch_size
        return math.ceil((v / k) * math.ceil((v - 1) / (k - 1)))
        
    def generate_all_pairs(self) -> Set[Tuple[int, int]]:
        """Generate all possible pairs of item indices."""
        return set(itertools.combinations(self.item_indices, 2))
        
    def get_pairs_in_batch(self, batch: List[int]) -> Set[Tuple[int, int]]:
        """Get all pairs within a batch (ordered consistently)."""
        pairs = set()
        for i in range(len(batch)):
            for j in range(i + 1, len(batch)):
                a, b = batch[i], batch[j]
                if a > b:
                    a, b = b, a
                pairs.add((a, b))
        return pairs
    
    def generate_batches(self, restarts: int = 64) -> List[List[int]]:
        """
        Generate optimized batches using greedy covering with restarts.
        
        Args:
            restarts: Number of random restarts to try
            
        Returns:
            List of batches (each batch is a list of item indices)
        """
        rng = random.Random(self.seed)
        best_batches = None
        best_len = float('inf')
        
        for _ in range(restarts):
            batches = self._greedy_cover_once(rng)
            batches = self._remove_redundant(batches)
            batches = self._repair_missing_pairs(batches, rng)
            
            if len(batches) < best_len:
                best_len = len(batches)
                best_batches = batches
        
        return best_batches or []
    
    def _pair_id(self, a: int, b: int) -> int:
        """Unique id for unordered pair {a,b}."""
        if a > b:
            a, b = b, a
        return a * (2 * self.n_items - a - 1) // 2 + (b - a - 1)
    
    def _greedy_cover_once(self, rng: random.Random) -> List[List[int]]:
        """Single greedy covering pass using bitsets."""
        # Initialize bitset rows - each row represents uncovered pairs for that item
        rows = [(((1 << self.n_items) - 1) ^ (1 << i)) for i in range(self.n_items)]
        uncovered = self.n_items * (self.n_items - 1) // 2
        batches = []
        
        # Replication tracking for balanced coverage
        target_r = math.ceil((self.n_items - 1) / (self.batch_size - 1))
        rep = [0] * self.n_items
        
        while uncovered > 0:
            # Count degrees (uncovered pairs per item)
            deg = [bin(row).count('1') for row in rows]
            
            # Pick anchor pair from top candidates
            u, v = self._pick_anchor_top_t(rows, deg, rng)
            if u is None:
                break
            
            # Build batch starting with anchor pair
            batch = [u, v]
            batch_set = {u, v}
            
            while len(batch) < self.batch_size:
                selmask = 0
                for x in batch:
                    selmask |= (1 << x)
                
                best_score = -1e18
                best_cands = []
                
                for c in range(self.n_items):
                    if c in batch_set:
                        continue
                    
                    # Count new pairs covered
                    gain = bin(rows[c] & selmask).count('1')
                    
                    if gain == 0 and len(batch) < self.batch_size - 1:
                        score = -1e9
                    else:
                        over = max(0, rep[c] - target_r)
                        score = gain - 0.1 * over
                    
                    if score > best_score:
                        best_score = score
                        best_cands = [c]
                    elif score == best_score:
                        best_cands.append(c)
                
                if not best_cands:
                    pool = [i for i in range(self.n_items) if i not in batch_set]
                    if not pool:
                        break
                    maxdeg = max(deg[i] for i in pool)
                    best_cands = [i for i in pool if deg[i] == maxdeg]
                
                c = rng.choice(best_cands)
                batch.append(c)
                batch_set.add(c)
            
            # Mark covered pairs
            newcov = 0
            for i in range(len(batch)):
                a = batch[i]
                for j in range(i + 1, len(batch)):
                    b = batch[j]
                    if (rows[a] >> b) & 1:
                        rows[a] &= ~(1 << b)
                        rows[b] &= ~(1 << a)
                        newcov += 1
            
            uncovered -= newcov
            batches.append(batch)
            
            for x in batch:
                rep[x] += 1
        
        return batches
    
    def _pick_anchor_top_t(self, rows: List[int], deg: List[int], 
                           rng: random.Random, top_t: int = 16) -> Tuple[Optional[int], Optional[int]]:
        """Pick anchor pair from top-T candidates by degree sum."""
        cands = []
        
        for u in range(self.n_items):
            ru = rows[u]
            vmask = ru >> (u + 1)
            while vmask:
                tz = (vmask & -vmask).bit_length() - 1
                v = (u + 1) + tz
                score = deg[u] + deg[v]
                
                if len(cands) < top_t:
                    cands.append((score, u, v))
                    if len(cands) == top_t:
                        cands.sort(key=lambda x: x[0])
                else:
                    if score > cands[0][0]:
                        cands[0] = (score, u, v)
                        cands.sort(key=lambda x: x[0])
                
                vmask &= vmask - 1
        
        if not cands:
            return None, None
        
        _, u, v = rng.choice(cands)
        return u, v
    
    def _remove_redundant(self, batches: List[List[int]]) -> List[List[int]]:
        """Remove redundant batches that don't contribute unique pairs."""
        if not batches:
            return batches
            
        cov = [[0] * self.n_items for _ in range(self.n_items)]
        for batch in batches:
            for i in range(len(batch)):
                a = batch[i]
                for j in range(i + 1, len(batch)):
                    b = batch[j]
                    cov[a][b] += 1
                    cov[b][a] += 1
        
        pruned = []
        for batch in batches:
            removable = True
            for i in range(len(batch)):
                a = batch[i]
                for j in range(i + 1, len(batch)):
                    b = batch[j]
                    if cov[a][b] < 2:
                        removable = False
                        break
                if not removable:
                    break
            
            if removable:
                for i in range(len(batch)):
                    a = batch[i]
                    for j in range(i + 1, len(batch)):
                        b = batch[j]
                        cov[a][b] -= 1
                        cov[b][a] -= 1
            else:
                pruned.append(batch)
        
        return pruned
    
    def _repair_missing_pairs(self, batches: List[List[int]], 
                              rng: random.Random) -> List[List[int]]:
        """Add minimal batches to cover any missing pairs."""
        rows = [(((1 << self.n_items) - 1) ^ (1 << i)) for i in range(self.n_items)]
        for batch in batches:
            for i in range(len(batch)):
                a = batch[i]
                for j in range(i + 1, len(batch)):
                    b = batch[j]
                    if (rows[a] >> b) & 1:
                        rows[a] &= ~(1 << b)
                        rows[b] &= ~(1 << a)
        
        result_batches = batches[:]
        while True:
            anchor = None
            for a in range(self.n_items):
                ru = rows[a] >> (a + 1)
                if ru:
                    b = (ru & -ru).bit_length() - 1
                    b = (a + 1) + b
                    anchor = (a, b)
                    break
            
            if anchor is None:
                break
            
            a, b = anchor
            batch = [a, b]
            batch_set = {a, b}
            
            while len(batch) < self.batch_size:
                selmask = 0
                for x in batch:
                    selmask |= (1 << x)
                
                best_gain, best_c = -1, None
                for c in range(self.n_items):
                    if c in batch_set:
                        continue
                    gain = bin(rows[c] & selmask).count('1')
                    if gain > best_gain:
                        best_gain, best_c = gain, c
                
                if best_c is None:
                    pool = [i for i in range(self.n_items) if i not in batch_set]
                    if not pool:
                        break
                    best_c = max(pool, key=lambda i: bin(rows[i]).count('1'))
                
                batch.append(best_c)
                batch_set.add(best_c)
            
            for i in range(len(batch)):
                x = batch[i]
                for j in range(i + 1, len(batch)):
                    y = batch[j]
                    if (rows[x] >> y) & 1:
                        rows[x] &= ~(1 << y)
                        rows[y] &= ~(1 << x)
            
            result_batches.append(batch)
        
        return result_batches
    
    def validate_batches(self, batches: List[List[int]]) -> Dict[str, any]:
        """
        Validate a batch configuration and return analysis.
        
        Returns:
            Dictionary with validation results and statistics
        """
        all_pairs = self.generate_all_pairs()
        covered_pairs = set()
        
        for batch in batches:
            covered_pairs.update(self.get_pairs_in_batch(batch))
            
        missing_pairs = all_pairs - covered_pairs
        
        duplicate_coverage = {}
        for batch in batches:
            for pair in self.get_pairs_in_batch(batch):
                duplicate_coverage[pair] = duplicate_coverage.get(pair, 0) + 1
                
        video_usage = {}
        for batch in batches:
            for item in batch:
                video_usage[item] = video_usage.get(item, 0) + 1
                
        return {
            'total_batches': len(batches),
            'total_pairs_needed': len(all_pairs),
            'pairs_covered': len(covered_pairs),
            'pairs_missing': len(missing_pairs),
            'missing_pairs_list': list(missing_pairs),
            'coverage_complete': len(missing_pairs) == 0,
            'max_pair_coverage': max(duplicate_coverage.values()) if duplicate_coverage else 0,
            'avg_pair_coverage': sum(duplicate_coverage.values()) / len(duplicate_coverage) if duplicate_coverage else 0,
            'item_usage': video_usage,
            'min_item_usage': min(video_usage.values()) if video_usage else 0,
            'max_item_usage': max(video_usage.values()) if video_usage else 0,
            'schonheim_lower_bound': self.calculate_schonheim_lower_bound(),
            'efficiency': self.calculate_schonheim_lower_bound() / len(batches) if batches else 0
        }


def _generate_optimal_batches(
    v: int,
    k: int,
    seed: int = 12345,
    time_limit: float = 10.0,
    passes: int = 12,
    greedy_trials: int = 2,
    forbid_above: int = 2,
    group_rounds: int = 12,
    group_time: float = 10.0,
    group_cands: int = 100,
) -> Optional[List[List[int]]]:
    """
    Generate near-optimal batches using LJCR covering designs + local search.
    
    Uses the same algorithm as the library's optimize_cover_pure.py, called
    directly as a module (no subprocess needed).
    
    Returns:
        List of batches (0-based), or None if LJCR data unavailable.
    """
    # Exact constructions (Steiner systems, projective/affine planes) are
    # provably optimal and perfectly balanced; use them when (v, k) admits one.
    try:
        from coverlib.constructions import exact_design

        design = exact_design(v, k)
        if design is not None:
            print(f"[optimal] Using exact 2-({v},{k},1) design ({len(design)} blocks, lambda=1)")
            return [list(block) for block in design]
    except Exception:
        pass

    try:
        from . import optimize_cover_pure as ocp
    except ImportError:
        return None

    cache_dir = _resolve_ljcr_cache_dir()

    # Try to load seed blocks from cache; fetch from LJCR if missing
    try:
        blocks = ocp.get_seed_blocks(
            v, k, cache_dir,
            offline_first=True,
            offline_only=False,   # allow live fetch if cache misses
        )
    except Exception as e:
        print(f"[optimal] Could not obtain seed blocks for v={v} k={k}: {e}")
        return None

    rng = random.Random(seed)
    random.seed(seed)

    # Repair under-coverage (rare for LJCR seeds)
    counts, _ = ocp.coverage_from_blocks(v, blocks)
    if min(counts) < 1:
        blocks = ocp.repair_to_coverage(v, k, blocks, rng=rng)

    # Prune redundant blocks
    counts, bpairs = ocp.coverage_from_blocks(v, blocks)
    order = list(range(len(blocks)))
    rng.shuffle(order)
    for idx in order:
        pp = bpairs[idx]
        if any(counts[p] == 1 for p in pp):
            continue
        for p in pp:
            counts[p] -= 1
        blocks[idx] = None
    blocks = [b for b in blocks if b is not None]

    # Local search + group DFS rebalancing
    opt = ocp.CoverOptimizer(v, blocks, seed=seed)
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

    result = [list(b) for b in opt.blocks]
    print(f"[optimal] Generated {len(result)} batches for v={v} k={k} "
          f"(lambda_max={opt.lambda_max()}, Schonheim>={ocp.schonheim_lb(v, k)})")
    return result


def _resolve_ljcr_cache_dir() -> Path:
    """Resolve the shared LJCR cache directory.

    Prefer the packaged cache so the Python package and server reuse the same
    covering-design data. Fall back to the legacy server-local cache path if
    the package cache is unavailable.
    """
    try:
        import multiarrangement as ma

        package_cache = Path(ma.__file__).resolve().parent / "ljcr_cache"
        if package_cache.exists():
            return package_cache
    except Exception as exc:
        _warn_once(
            "ljcr_cache_fallback",
            f"Packaged LJCR cache unavailable ({exc!r}); falling back to the server-local cache. "
            "Check the multiarrangement install if this is unexpected.",
        )

    return Path(__file__).resolve().parent / "ljcr_cache"


def _coverage_counts(n_items: int, batches: List[List[int]]) -> tuple[Counter[Tuple[int, int]], Counter[int]]:
    pair_counts: Counter[Tuple[int, int]] = Counter()
    item_counts: Counter[int] = Counter()
    for batch in batches:
        item_counts.update(int(idx) for idx in batch)
        for pair in itertools.combinations(sorted(int(idx) for idx in batch), 2):
            pair_counts[pair] += 1
    for idx in range(n_items):
        item_counts.setdefault(idx, 0)
    return pair_counts, item_counts


def _augment_cover_for_balance(
    n_items: int,
    batch_size: int,
    batches: List[List[int]],
    extra_blocks: int,
    seed: int,
) -> List[List[int]]:
    """Add a small number of targeted blocks around over-repeated pairs."""
    if extra_blocks <= 0:
        return [list(batch) for batch in batches]

    rng = random.Random(seed)
    augmented = [list(map(int, batch)) for batch in batches]
    pair_counts, item_counts = _coverage_counts(n_items, augmented)
    if not pair_counts:
        return augmented

    max_count = max(pair_counts.values())
    offender_pairs = {pair for pair, count in pair_counts.items() if count == max_count}
    critical_pairs: Set[Tuple[int, int]] = set()
    for batch in augmented:
        batch_pairs = set(itertools.combinations(sorted(batch), 2))
        if batch_pairs & offender_pairs:
            critical_pairs.update(pair for pair in batch_pairs if pair_counts[pair] == 1)

    all_pairs = list(itertools.combinations(range(n_items), 2))
    for _ in range(extra_blocks):
        if critical_pairs:
            anchor = rng.choice(sorted(critical_pairs))
        else:
            anchor = min(
                all_pairs,
                key=lambda pair: (
                    pair_counts[pair],
                    item_counts[pair[0]] + item_counts[pair[1]],
                    rng.random(),
                ),
            )

        block = [anchor[0], anchor[1]]
        block_set = set(block)
        while len(block) < batch_size:
            preferred: List[Tuple[float, int]] = []
            relaxed: List[Tuple[float, int]] = []
            for candidate in range(n_items):
                if candidate in block_set:
                    continue
                new_pairs = [tuple(sorted((candidate, existing))) for existing in block]
                critical_gain = sum(1 for pair in new_pairs if pair in critical_pairs)
                singleton_gain = sum(1 for pair in new_pairs if pair_counts[pair] == 1)
                duplicate_cost = sum(pair_counts[pair] for pair in new_pairs)
                score = (
                    critical_gain * 100.0
                    + singleton_gain * 15.0
                    - duplicate_cost * 2.0
                    - item_counts[candidate]
                    + rng.random()
                )
                option = (score, candidate)
                if not offender_pairs.intersection(new_pairs):
                    preferred.append(option)
                relaxed.append(option)

            options = preferred if preferred else relaxed
            if not options:
                break
            options.sort(reverse=True)
            top_options = options[:min(5, len(options))]
            selected = top_options[0] if rng.random() > 0.3 else rng.choice(top_options)
            block.append(selected[1])
            block_set.add(selected[1])

        if len(block) != batch_size:
            continue

        block = sorted(block)
        augmented.append(block)
        item_counts.update(block)
        for pair in itertools.combinations(block, 2):
            pair_counts[pair] += 1
            critical_pairs.discard(pair)

    return augmented


def _rebalance_fixed_cover(
    n_items: int,
    batches: List[List[int]],
    seed: int,
    *,
    passes: int = 40,
    greedy_trials: int = 20,
) -> List[List[int]]:
    """Use the local block-design optimizer without changing the trial budget."""
    try:
        from . import optimize_cover_pure as ocp
    except Exception:
        return batches

    try:
        blocks = [tuple(sorted(int(idx) for idx in batch)) for batch in batches]
        optimizer = ocp.CoverOptimizer(n_items, blocks, seed=seed)
        optimizer.local_search(passes=passes, forbid_above=None, greedy_trials=greedy_trials)
        return [list(block) for block in optimizer.blocks]
    except Exception as exc:
        print(f"Warning: fixed-budget balance optimization failed ({exc}); keeping candidate cover.")
        return batches


def _balanced_cover_score(n_items: int, batch_size: int, batches: List[List[int]]) -> tuple:
    """Lexicographic quality score for a complete covering design.

    The hard constraint is complete pair coverage. Among complete covers, prefer
    a flatter size-normalized concurrence matrix before considering trial count.
    """
    try:
        from coverlib.balanced import balance_sort_key

        return balance_sort_key(n_items, batch_size, batches)
    except Exception as exc:
        _warn_once(
            "balance_sort_key_fallback",
            f"coverlib.balanced unavailable ({exc!r}); using the simplified balance score. "
            "Schedule balance selection is degraded.",
        )

    pair_counts, item_counts = _coverage_counts(n_items, batches)
    expected_pairs = n_items * (n_items - 1) // 2
    if len(pair_counts) != expected_pairs or any(count < 1 for count in pair_counts.values()):
        missing = expected_pairs - len(pair_counts)
        return (1, missing, len(batches))

    values = list(pair_counts.values())
    lmax = max(values) if values else 0
    count_at_lmax = sum(1 for value in values if value == lmax)
    mean = sum(values) / len(values) if values else 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values) if values else 0.0
    item_values = list(item_counts.values())
    item_range = (max(item_values) - min(item_values)) if item_values else 0
    return (0, lmax, count_at_lmax, round(variance, 12), item_range, len(batches))


def _is_already_balanced_enough(n_items: int, batch_size: int, batches: List[List[int]]) -> bool:
    try:
        from coverlib.balanced import normalized_balance_metrics

        metrics = normalized_balance_metrics(n_items, batch_size, batches)
        return (
            metrics.complete
            and metrics.lambda_max_ratio <= 1.5
            and metrics.normalized_pair_sumsq_excess <= 0.05
        )
    except Exception:
        score = _balanced_cover_score(n_items, batch_size, batches)
        if score[0] != 0:
            return False
        _, lmax, count_at_lmax, *_ = score
        expected_pairs = n_items * (n_items - 1) // 2
        return lmax <= 3 and count_at_lmax <= max(1, int(math.ceil(expected_pairs * 0.02)))


def _generate_balanced_batches(
    n_items: int,
    batch_size: int,
    *,
    seed: int,
    restarts: int,
    max_extra_fraction: float = 0.0,
) -> List[List[int]]:
    """Generate complete pair coverage with a balanced concurrence matrix.

    The default is free balance only: keep the LJCR/minimal trial budget and
    replace it with a validated same-trial cache when available. A caller may
    explicitly pass a positive ``max_extra_fraction`` for offline experiments,
    but production study setup does not spend extra trials by default.
    """
    candidates: List[List[List[int]]] = []

    optimal = _generate_optimal_batches(n_items, batch_size, seed=seed)
    if optimal:
        # with a trial surplus allowed, always consult the cache: a certified
        # balanced cover may exist just above the minimum trial count
        if max_extra_fraction <= 0.0 and _is_already_balanced_enough(
                n_items, batch_size, optimal):
            pair_counts, _ = _coverage_counts(n_items, optimal)
            hist = Counter(pair_counts.values())
            print(
                f"[balanced] Using near-minimal cover for v={n_items} k={batch_size} "
                f"(lambda_max={max(pair_counts.values()) if pair_counts else 0}, hist={dict(sorted(hist.items()))})"
            )
            return optimal
        candidates.append(optimal)

    fallback_seed = seed if optimal else seed + 1009
    if not candidates:
        candidates.append(BatchGenerator(n_items, batch_size, fallback_seed).generate_batches(restarts=restarts))

    extra_budget = int(math.floor(len(candidates[0]) * max(0.0, float(max_extra_fraction))))
    trial_limit = len(candidates[0]) + extra_budget
    cached = _load_balanced_cache_candidate(n_items, batch_size, trial_limit)
    if cached and _balanced_cover_score(n_items, batch_size, cached) < _balanced_cover_score(n_items, batch_size, candidates[0]):
        pair_counts, _ = _coverage_counts(n_items, cached)
        hist = Counter(pair_counts.values())
        print(
            f"[balanced] Loaded cached balanced cover for v={n_items} k={batch_size} "
            f"({len(cached)} batches, lambda_max={max(pair_counts.values()) if pair_counts else 0}, "
            f"hist={dict(sorted(hist.items()))})"
        )
        return cached

    extra_blocks = max(0, trial_limit - len(candidates[0]))
    if extra_blocks:
        augmentation_attempts = 8 if n_items >= 32 else 12
        for offset in range(augmentation_attempts):
            augmented = _augment_cover_for_balance(
                n_items,
                batch_size,
                candidates[0],
                extra_blocks,
                seed + offset,
            )
            rebalanced = _rebalance_fixed_cover(n_items, augmented, seed + offset)
            if rebalanced and len(rebalanced) <= trial_limit:
                candidates.append(rebalanced)

    greedy_restarts = max(24, min(96, int(restarts)))
    seed_offsets = (0, 1, 2, 3, 4, 5)
    for offset in seed_offsets:
        candidate_seed = seed + offset
        greedy = BatchGenerator(n_items, batch_size, candidate_seed).generate_batches(restarts=greedy_restarts)
        if greedy and len(greedy) <= trial_limit:
            candidates.append(greedy)

    best = min(candidates, key=lambda batches: _balanced_cover_score(n_items, batch_size, batches))
    best = _improve_balanced_cover_if_needed(
        n_items,
        batch_size,
        best,
        seed=seed,
    )
    pair_counts, _ = _coverage_counts(n_items, best)
    hist = Counter(pair_counts.values())
    print(
        f"[balanced] Generated {len(best)} batches for v={n_items} k={batch_size} "
        f"(lambda_max={max(pair_counts.values()) if pair_counts else 0}, hist={dict(sorted(hist.items()))})"
    )
    return best


def _improve_balanced_cover_if_needed(
    n_items: int,
    batch_size: int,
    batches: List[List[int]],
    *,
    seed: int,
) -> List[List[int]]:
    """Run bounded temporary-violation local search for stubborn high-concurrence covers."""
    score = _balanced_cover_score(n_items, batch_size, batches)
    if os.getenv("MA_ENABLE_SLOW_BALANCE_SEARCH") != "1":
        return batches

    try:
        from coverlib.balanced import normalized_balance_metrics

        metrics = normalized_balance_metrics(n_items, batch_size, batches)
        if n_items < 24 or not metrics.complete or metrics.lambda_max_ratio <= 1.5:
            return batches
        target_lmax = metrics.ideal_lambda_max
    except Exception:
        if n_items < 24 or score[0] != 0 or score[1] <= 3:
            return batches
        target_lmax = max(2, score[1] - 1)

    try:
        from coverlib.balanced import improve_pair_balance
    except Exception:
        return batches

    attempts = 2
    iterations = min(6_000_000, max(600_000, n_items * 40_000))
    seconds_per_attempt = min(14.0, max(5.0, n_items * 0.35))
    improved = improve_pair_balance(
        n_items,
        batch_size,
        batches,
        seed=seed,
        target_lmax=target_lmax,
        attempts=attempts,
        iterations=iterations,
        seconds_per_attempt=seconds_per_attempt,
    )
    if _balanced_cover_score(n_items, batch_size, improved) < score:
        return improved
    return batches


def _load_balanced_cache_candidate(
    n_items: int,
    batch_size: int,
    trial_limit: int,
) -> Optional[List[List[int]]]:
    try:
        from coverlib.balanced import load_cached_balanced_cover
    except Exception as exc:
        _warn_once(
            "balanced_cache_loader_fallback",
            f"coverlib.balanced unavailable ({exc!r}); cached balanced covers are disabled.",
        )
        return None

    cache_dirs: List[Path] = []
    try:
        import multiarrangement as ma

        cache_dirs.append(Path(ma.__file__).resolve().parent / "balanced_cache")
    except Exception as exc:
        _warn_once(
            "balanced_cache_package_fallback",
            f"Packaged balanced cache unavailable ({exc!r}); balanced schedules may fall back "
            "to unoptimized covers. Check the multiarrangement install.",
        )
    cache_dirs.append(Path(__file__).resolve().parent / "balanced_cache")
    cache_dirs.append(Path.cwd() / "multiarrangement" / "balanced_cache")

    return load_cached_balanced_cover(
        n_items,
        batch_size,
        max_blocks=trial_limit,
        cache_dirs=cache_dirs,
    )


def generate_batches(
    n_items: int,
    batch_size: int,
    seed: Optional[int] = None,
    restarts: int = 64,
    flex: bool = False,
    algorithm: str = "balanced",
    max_extra_fraction: float = 0.0,
) -> List[List[int]]:
    """
    Convenience function to generate batches.
    
    Uses the same default as the desktop library: complete pair coverage with a
    same-trial balanced cache when available. Pass ``algorithm="hybrid"`` or
    ``algorithm="server"`` for the raw minimum-cover path.
    
    Args:
        n_items: Total number of stimuli
        batch_size: Number of stimuli per batch
        seed: Random seed for reproducibility
        restarts: Number of algorithm restarts
        flex: Use variable-size batches (library flex mode)
        algorithm: Algorithm hint ('balanced', 'hybrid', 'server', 'optimal', 'greedy')
        max_extra_fraction: Trial-budget tolerance. 0.0 (compact mode) keeps
            the minimum trial count; 0.20 (balanced mode) lets the cache
            supply a certified low-concurrence schedule with up to 20%
            more trials.

    Returns:
        List of batches
    """
    seed_value = 42 if seed is None else seed

    if algorithm == "balanced":
        return _generate_balanced_batches(
            n_items,
            batch_size,
            seed=seed_value,
            restarts=restarts,
            max_extra_fraction=max_extra_fraction,
        )

    # For flex mode, delegate to the library (flex requires optimize_cover_flex.py)
    if flex:
        try:
            import multiarrangement as ma
            algo = "hybrid" if algorithm == "server" else str(algorithm)
            batches = ma.create_batches(
                n_items, batch_size, seed=seed_value,
                algorithm=algo, flex=True,
            )
            if batches:
                return batches
        except Exception as e:
            print(f"Warning: library flex batch generation failed ({e}); falling back to server greedy.")

    # Try optimal covering design first (same algorithm as the library's hybrid path)
    if algorithm != "greedy":
        try:
            batches = _generate_optimal_batches(n_items, batch_size, seed=seed_value)
            if batches:
                return batches
        except Exception as e:
            print(f"Warning: optimal batch generation failed ({e}); falling back to greedy.")

    # Greedy fallback
    generator = BatchGenerator(n_items, batch_size, seed)
    return generator.generate_batches(restarts)
