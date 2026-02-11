"""
Batch generation algorithms for the Multiarrangement web API.

This module provides algorithms to generate optimal batches of stimuli that ensure
all pairs appear together at least once while minimizing the total number of batches.

Extracted from the original multiarrangement.core.batch_generator module,
stripped of pygame/opencv dependencies for server-side use.
"""

import itertools
import math
import random
from typing import Dict, List, Optional, Set, Tuple


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
    from pathlib import Path
    try:
        from . import optimize_cover_pure as ocp
    except ImportError:
        return None

    # Locate the LJCR cache bundled with the server
    cache_dir = Path(__file__).parent / "ljcr_cache"

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


def generate_batches(
    n_items: int,
    batch_size: int,
    seed: Optional[int] = None,
    restarts: int = 64,
    flex: bool = False,
    algorithm: str = "server",
) -> List[List[int]]:
    """
    Convenience function to generate batches.
    
    Uses a hybrid strategy matching the desktop library:
    1. Try LJCR-optimal covering designs (via bundled optimize_cover_pure)
    2. Fall back to the library if installed (for flex mode)
    3. Fall back to local greedy algorithm
    
    Args:
        n_items: Total number of stimuli
        batch_size: Number of stimuli per batch
        seed: Random seed for reproducibility
        restarts: Number of algorithm restarts
        flex: Use variable-size batches (library flex mode)
        algorithm: Algorithm hint ('hybrid', 'server', 'optimal', 'greedy')
        
    Returns:
        List of batches
    """
    seed_value = 42 if seed is None else seed

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
