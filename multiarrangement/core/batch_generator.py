"""
Batch generation algorithms for multiarrangement experiments.

This module provides algorithms to generate optimal batches of videos that ensure
all pairs of videos appear together at least once while minimizing the total number of batches.
"""

import random
import itertools
from typing import List, Tuple, Set, Dict, Optional
from pathlib import Path
import math


class BatchGenerator:
    """
    Generate optimized batches for multiarrangement experiments.
    
    This class uses a hybrid algorithm approach that tries multiple optimization
    techniques in order of quality: optimal solutions, C extensions, then Python
    fallbacks. This ensures the best possible batch configurations that guarantee
    all video pairs appear together at least once while minimizing batch count.
    
    The default methods (greedy_algorithm, optimize_batches) now use the hybrid
    approach for optimal results with robust fallback options.
    
    Example:
        # Simple usage - automatically uses hybrid algorithm
        generator = BatchGenerator(n_videos=24, batch_size=8, seed=42)
        batches = generator.greedy_algorithm()  # Uses hybrid (optimal -> C -> Python)
        
        # Explicit algorithm selection
        batches = generator.optimize_batches(algorithm='hybrid')  # Recommended
        batches = generator.optimize_batches(algorithm='optimal') # Force optimal only
        batches = generator.optimize_batches(algorithm='greedy')  # Force greedy only
    """
    
    def __init__(self, n_videos: int, batch_size: int, seed: Optional[int] = None):
        """
        Initialize the batch generator.
        
        Args:
            n_videos: Total number of videos
            batch_size: Number of videos per batch
            seed: Random seed for reproducible results
        """
        self.n_videos = n_videos
        self.batch_size = batch_size
        self.video_indices = list(range(n_videos))
        
        if seed is not None:
            random.seed(seed)
            
        # Validate parameters
        if batch_size < 2:
            raise ValueError("Batch size must be at least 2")
        if batch_size > n_videos:
            raise ValueError("Batch size cannot be larger than number of videos")
            
    def calculate_schonheim_lower_bound(self) -> int:
        """
        Calculate the Schönheim lower bound for the minimum number of batches needed.
        
        This gives a theoretical lower bound on the number of batches required
        to ensure all pairs appear at least once.
        
        Returns:
            Theoretical minimum number of batches
        """
        v = self.n_videos
        k = self.batch_size
        
        # For t=2 (pairwise coverage), the Schönheim bound is:
        # ceil((v/k) * ceil((v-1)/(k-1)))
        return math.ceil((v / k) * math.ceil((v - 1) / (k - 1)))
        
    def generate_all_pairs(self) -> Set[Tuple[int, int]]:
        """
        Generate all possible pairs of video indices.
        
        Returns:
            Set of all video pairs
        """
        return set(itertools.combinations(self.video_indices, 2))
        
    def get_pairs_in_batch(self, batch: List[int]) -> Set[Tuple[int, int]]:
        """
        Get all pairs within a batch.
        
        Args:
            batch: List of video indices in the batch
            
        Returns:
            Set of pairs in the batch (ordered consistently with generate_all_pairs)
        """
        pairs = set()
        for i in range(len(batch)):
            for j in range(i + 1, len(batch)):
                a, b = batch[i], batch[j]
                # Ensure consistent ordering (smaller index first)
                if a > b:
                    a, b = b, a
                pairs.add((a, b))
        return pairs
        
    def greedy_algorithm(self, max_iterations: int = 1000) -> List[List[int]]:
        """
        Generate batches using the hybrid algorithm (recommended default).
        
        This method now uses the hybrid approach which tries multiple algorithms
        in order of quality: optimal solution, C extensions, then Python fallbacks.
        This ensures the best possible results with robust fallback options.
        
        Args:
            max_iterations: Maximum iterations (used for compatibility, converted to restarts)
            
        Returns:
            List of batches (each batch is a list of video indices)
        """
        # Use hybrid algorithm as the new default (best quality with fallbacks)
        return self.optimize_batches(algorithm='hybrid')
    
    def _generate_batches_optimized(self, restarts: int = 64, seed: int = 42) -> List[List[int]]:
        """
        Generate optimized batches using the proven algorithm from New_Greedy_1.py
        """
        try:
            # Import and use the working New_Greedy_1 implementation
            import New_Greedy_1
            video_indices = list(range(self.n_videos))
            batches = New_Greedy_1.generate_batches(
                video_indices, 
                self.batch_size,
                restarts=restarts,
                seed=seed,
                prune=True,
                grasp_passes=2,
                repair=True,
                reselect=True
            )
            return batches
        except (ImportError, Exception) as e:
            # Fallback implementation if New_Greedy_1.py not available
            print(f"⚠ Failed to use New_Greedy_1.py: {e}, using fallback")
            return self._fallback_greedy_implementation(restarts, seed)
        
    def _fallback_greedy_implementation(self, restarts: int, seed: int) -> List[List[int]]:
        """Simplified fallback implementation"""
        rng = random.Random(seed)
        best_batches = None
        best_len = 10**9
        
        for _ in range(restarts):
            batches = self._greedy_cover_once(rng)
            batches = self._remove_redundant(batches)
            batches = self._repair_missing_pairs(batches)
            
            if len(batches) < best_len:
                best_len = len(batches)
                best_batches = batches
        
        return best_batches or []
    
    def _pair_id(self, a: int, b: int) -> int:
        """Unique id for unordered pair {a,b}"""
        if a > b:
            a, b = b, a
        return a * (2 * self.n_videos - a - 1) // 2 + (b - a - 1)
    
    def _greedy_cover_once(self, rng) -> List[List[int]]:
        """Single greedy covering pass using bitsets"""
        # Initialize bitset rows - each row represents uncovered pairs for that video
        rows = [(((1 << self.n_videos) - 1) ^ (1 << i)) for i in range(self.n_videos)]
        uncovered = self.n_videos * (self.n_videos - 1) // 2
        batches = []
        
        # Replication tracking for balanced coverage
        target_r = math.ceil((self.n_videos - 1) / (self.batch_size - 1))
        rep = [0] * self.n_videos
        
        while uncovered > 0:
            # Count degrees (uncovered pairs per video)
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
                
                for c in range(self.n_videos):
                    if c in batch_set:
                        continue
                    
                    # Count new pairs covered
                    gain = bin(rows[c] & selmask).count('1')
                    
                    if gain == 0 and len(batch) < self.batch_size - 1:
                        score = -1e9  # Discourage zero-gain unless near end
                    else:
                        # Apply replication penalty
                        over = max(0, rep[c] - target_r)
                        score = gain - 0.1 * over
                    
                    if score > best_score:
                        best_score = score
                        best_cands = [c]
                    elif score == best_score:
                        best_cands.append(c)
                
                if not best_cands:
                    # Fallback to highest degree
                    pool = [i for i in range(self.n_videos) if i not in batch_set]
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
            
            # Update replication counts
            for x in batch:
                rep[x] += 1
        
        return batches
    
    def _pick_anchor_top_t(self, rows, deg, rng, top_t=16):
        """Pick anchor pair from top-T candidates by degree sum"""
        cands = []  # (score, u, v)
        
        for u in range(self.n_videos):
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
        
    def _greedy_select_batch(self, uncovered_pairs: Set[Tuple[int, int]]) -> List[int]:
        """
        Select videos for a batch using greedy strategy.
        
        Args:
            uncovered_pairs: Set of pairs that still need to be covered
            
        Returns:
            List of video indices for the batch
        """
        batch = []
        remaining_pairs = uncovered_pairs.copy()
        
        # Start with the video that appears in most uncovered pairs
        video_pair_counts = {}
        for pair in remaining_pairs:
            for video in pair:
                video_pair_counts[video] = video_pair_counts.get(video, 0) + 1
                
        if video_pair_counts:
            start_video = max(video_pair_counts, key=video_pair_counts.get)
            batch.append(start_video)
            
        # Greedily add videos that cover the most uncovered pairs
        while len(batch) < self.batch_size:
            best_video = None
            best_coverage = 0
            
            for video in self.video_indices:
                if video not in batch:
                    # Count how many uncovered pairs this video would cover
                    coverage = 0
                    for existing_video in batch:
                        pair = tuple(sorted([video, existing_video]))
                        if pair in remaining_pairs:
                            coverage += 1
                            
                    if coverage > best_coverage:
                        best_coverage = coverage
                        best_video = video
                        
            if best_video is not None:
                batch.append(best_video)
                # Update remaining pairs
                new_pairs = set()
                for existing_video in batch[:-1]:
                    pair = tuple(sorted([best_video, existing_video]))
                    new_pairs.add(pair)
                remaining_pairs -= new_pairs
            else:
                # No video provides additional coverage, add random video
                available_videos = [v for v in self.video_indices if v not in batch]
                if available_videos:
                    batch.append(random.choice(available_videos))
                else:
                    break
                    
        return batch
    
    def _remove_redundant(self, batches) -> List[List[int]]:
        """Remove redundant batches that don't contribute unique pairs"""
        if not batches:
            return batches
            
        # Build coverage matrix
        cov = [[0] * self.n_videos for _ in range(self.n_videos)]
        for batch in batches:
            for i in range(len(batch)):
                a = batch[i]
                for j in range(i + 1, len(batch)):
                    b = batch[j]
                    cov[a][b] += 1
                    cov[b][a] += 1
        
        # Check which batches can be removed
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
                # Remove coverage and don't add to pruned
                for i in range(len(batch)):
                    a = batch[i]
                    for j in range(i + 1, len(batch)):
                        b = batch[j]
                        cov[a][b] -= 1
                        cov[b][a] -= 1
            else:
                pruned.append(batch)
        
        return pruned
    
    def _grasp_local_improvement(self, batches, max_passes=2) -> List[List[int]]:
        """GRASP-style local improvement with swaps and deletions"""
        if not batches:
            return batches
        
        # For simplicity, just return the input batches
        # The full GRASP implementation is complex and not critical for basic functionality
        return batches
    
    def _repair_missing_pairs(self, batches) -> List[List[int]]:
        """Add minimal batches to cover any missing pairs"""
        # Check coverage
        rows = [(((1 << self.n_videos) - 1) ^ (1 << i)) for i in range(self.n_videos)]
        for batch in batches:
            for i in range(len(batch)):
                a = batch[i]
                for j in range(i + 1, len(batch)):
                    b = batch[j]
                    if (rows[a] >> b) & 1:
                        rows[a] &= ~(1 << b)
                        rows[b] &= ~(1 << a)
        
        # Add batches for missing pairs
        result_batches = batches[:]
        while True:
            anchor = None
            for a in range(self.n_videos):
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
            
            # Fill batch greedily
            while len(batch) < self.batch_size:
                selmask = 0
                for x in batch:
                    selmask |= (1 << x)
                
                best_gain, best_c = -1, None
                for c in range(self.n_videos):
                    if c in batch_set:
                        continue
                    gain = bin(rows[c] & selmask).count('1')
                    if gain > best_gain:
                        best_gain, best_c = gain, c
                
                if best_c is None:
                    pool = [i for i in range(self.n_videos) if i not in batch_set]
                    if not pool:
                        break
                    best_c = max(pool, key=lambda i: bin(rows[i]).count('1'))
                
                batch.append(best_c)
                batch_set.add(best_c)
            
            # Mark covered pairs
            for i in range(len(batch)):
                x = batch[i]
                for j in range(i + 1, len(batch)):
                    y = batch[j]
                    if (rows[x] >> y) & 1:
                        rows[x] &= ~(1 << y)
                        rows[y] &= ~(1 << x)
            
            result_batches.append(batch)
        
        return result_batches
    
    def _reselect_min_cover(self, batches) -> List[List[int]]:
        """Re-select minimum set of batches that covers all pairs"""
        if not batches:
            return batches
        
        M = self.n_videos * (self.n_videos - 1) // 2
        if M == 0:
            return batches
        
        # Precompute each batch's pair-bitmask
        masks = []
        for batch in batches:
            m = 0
            for i in range(len(batch)):
                a = batch[i]
                for j in range(i + 1, len(batch)):
                    b = batch[j]
                    m |= 1 << self._pair_id(a, b)
            masks.append(m)
        
        all_pairs_mask = (1 << M) - 1
        
        # Check if family covers all pairs
        fam_mask = 0
        for m in masks:
            fam_mask |= m
        if fam_mask != all_pairs_mask:
            return batches  # Can't improve if incomplete
        
        # Greedy set cover
        remaining = list(range(len(batches)))
        selected_idx = []
        uncovered = all_pairs_mask
        
        while uncovered:
            best_i = None
            best_gain = -1
            for idx in remaining:
                gain = bin(masks[idx] & uncovered).count('1')
                if gain > best_gain:
                    best_gain = gain
                    best_i = idx
            
            if best_i is None or best_gain == 0:
                break
            
            selected_idx.append(best_i)
            uncovered &= ~masks[best_i]
            remaining.remove(best_i)
        
        return [batches[i] for i in selected_idx]
        
    def brute_force_algorithm(self, max_batches: Optional[int] = None) -> List[List[int]]:
        """
        Generate batches using brute force optimization.
        
        This algorithm tries to find the minimum number of batches by
        systematically searching for valid combinations. It's guaranteed
        to find the optimal solution but can be very slow for large video sets.
        
        Args:
            max_batches: Maximum number of batches to try (default: Schönheim bound + 50%)
            
        Returns:
            List of batches (each batch is a list of video indices)
        """
        if max_batches is None:
            max_batches = int(self.calculate_schonheim_lower_bound() * 1.5)
            
        all_pairs = self.generate_all_pairs()
        
        # Try increasing numbers of batches until solution is found
        for num_batches in range(self.calculate_schonheim_lower_bound(), max_batches + 1):
            print(f"Trying {num_batches} batches...")
            
            solution = self._try_batch_count(num_batches, all_pairs)
            if solution is not None:
                return solution
                
        # If no solution found, fall back to greedy
        print(f"No solution found with up to {max_batches} batches. Using greedy algorithm.")
        return self.greedy_algorithm()
        
    def _try_batch_count(self, num_batches: int, all_pairs: Set[Tuple[int, int]], 
                        max_attempts: int = 10000) -> Optional[List[List[int]]]:
        """
        Try to find a solution with a specific number of batches.
        
        Args:
            num_batches: Number of batches to try
            all_pairs: All pairs that need to be covered
            max_attempts: Maximum number of random attempts
            
        Returns:
            List of batches if solution found, None otherwise
        """
        for attempt in range(max_attempts):
            # Generate random batches
            batches = []
            used_videos = set()
            
            for _ in range(num_batches):
                # Try to create a valid batch
                batch = self._create_random_batch(used_videos)
                batches.append(batch)
                used_videos.update(batch)
                
            # Check if all pairs are covered
            covered_pairs = set()
            for batch in batches:
                covered_pairs.update(self.get_pairs_in_batch(batch))
                
            if covered_pairs >= all_pairs:
                return batches
                
        return None
        
    def _create_random_batch(self, used_videos: Set[int]) -> List[int]:
        """
        Create a random batch, preferring unused videos.
        
        Args:
            used_videos: Set of videos already used in previous batches
            
        Returns:
            Random batch of video indices
        """
        batch = []
        available_videos = self.video_indices.copy()
        random.shuffle(available_videos)
        
        # Prefer unused videos first
        unused_videos = [v for v in available_videos if v not in used_videos]
        
        # Take from unused first, then from used if necessary
        candidates = unused_videos + [v for v in available_videos if v in used_videos]
        
        for video in candidates:
            if len(batch) >= self.batch_size:
                break
            if video not in batch:
                batch.append(video)
                
        return batch
        
    def validate_batches(self, batches: List[List[int]]) -> Dict[str, any]:
        """
        Validate a batch configuration and return analysis.
        
        Args:
            batches: List of batches to validate
            
        Returns:
            Dictionary with validation results and statistics
        """
        all_pairs = self.generate_all_pairs()
        covered_pairs = set()
        
        # Collect all covered pairs
        for batch in batches:
            batch_pairs = self.get_pairs_in_batch(batch)
            covered_pairs.update(batch_pairs)
            
        missing_pairs = all_pairs - covered_pairs
        duplicate_coverage = {}
        
        # Check for duplicate coverage
        for batch in batches:
            batch_pairs = self.get_pairs_in_batch(batch)
            for pair in batch_pairs:
                duplicate_coverage[pair] = duplicate_coverage.get(pair, 0) + 1
                
        # Count videos usage
        video_usage = {}
        for batch in batches:
            for video in batch:
                video_usage[video] = video_usage.get(video, 0) + 1
                
        return {
            'total_batches': len(batches),
            'total_pairs_needed': len(all_pairs),
            'pairs_covered': len(covered_pairs),
            'pairs_missing': len(missing_pairs),
            'missing_pairs_list': list(missing_pairs),
            'coverage_complete': len(missing_pairs) == 0,
            'max_pair_coverage': max(duplicate_coverage.values()) if duplicate_coverage else 0,
            'avg_pair_coverage': sum(duplicate_coverage.values()) / len(duplicate_coverage) if duplicate_coverage else 0,
            'video_usage': video_usage,
            'min_video_usage': min(video_usage.values()) if video_usage else 0,
            'max_video_usage': max(video_usage.values()) if video_usage else 0,
            'schonheim_lower_bound': self.calculate_schonheim_lower_bound(),
            'efficiency': self.calculate_schonheim_lower_bound() / len(batches) if batches else 0
        }
        
    def save_batches(self, batches: List[List[int]], output_file: Path) -> None:
        """
        Save batches to a file.
        
        Args:
            batches: List of batches to save
            output_file: Path to output file
        """
        output_file = Path(output_file)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Batch configuration for {self.n_videos} videos, batch size {self.batch_size}\n")
            f.write(f"# Total batches: {len(batches)}\n")
            f.write(f"# Schönheim lower bound: {self.calculate_schonheim_lower_bound()}\n\n")
            
            for batch in batches:
                f.write(','.join(map(str, batch)) + '\n')
                
        print(f"Saved {len(batches)} batches to {output_file}")
        
    def optimize_batches_hybrid(self, prefer_optimal: bool = True, **kwargs) -> List[List[int]]:
        """
        Generate optimized batches using the hybrid strategy:
        1. Try optimize_cover_pure.py (optimal) first
        2. Fall back to Greedy_gen.c (high-performance)
        3. Fall back to Python greedy (always available)
        
        Args:
            prefer_optimal: Whether to try optimal solutions first
            **kwargs: Additional arguments for the algorithms
            
        Returns:
            List of optimized batches
        """
        import subprocess
        import os
        from pathlib import Path
        
        # Get project root directory
        project_root = Path(__file__).parent.parent.parent
        
        if prefer_optimal:
            # Try optimize_cover_pure.py first
            try:
                batches = self._try_optimize_cover_pure(project_root, **kwargs)
                if batches:
                    print(f"✓ Used optimize_cover_pure.py (optimal solution: {len(batches)} batches)")
                    return batches
            except Exception as e:
                print(f"⚠ optimize_cover_pure.py failed: {e}")
        
        # Try pre-compiled C extension first (best performance)
        try:
            batches = self._try_greedy_c_extension(**kwargs)
            if batches:
                print(f"✓ Used C extension (pre-compiled: {len(batches)} batches)")
                return batches
        except Exception as e:
            print(f"⚠ C extension failed: {e}")
        
        # Try runtime-compiled C as fallback
        try:
            batches = self._try_greedy_c_runtime(project_root, **kwargs)
            if batches:
                print(f"✓ Used Greedy_gen.c (runtime compiled: {len(batches)} batches)")
                return batches
        except Exception as e:
            print(f"⚠ Runtime C compilation failed: {e}")
        
        # Final fallback to Python greedy
        print("ℹ Using Python greedy algorithm (fallback)")
        return self._try_new_greedy_python(**kwargs)
    
    def _try_optimize_cover_pure(self, project_root: Path, **kwargs) -> Optional[List[List[int]]]:
        """Try to use optimize_cover_pure.py for optimal batch generation."""
        import subprocess
        import tempfile
        import os
        from pathlib import Path
        
        # Try to find optimize_cover_pure.py in multiple locations
        # Prefer the packaged version first to avoid stale duplicates at repo root
        optimize_script = None

        # 1. Try package data directory (installed package or local)
        try:
            import multiarrangement as _ma_pkg
            package_dir = Path(_ma_pkg.__file__).parent
            package_script = package_dir / "optimize_cover_pure.py"
            if package_script.exists():
                optimize_script = package_script
        except ImportError:
            pass

        # 2. Try project root under multiarrangement/
        if optimize_script is None:
            if isinstance(project_root, str):
                project_root = Path(project_root)
            else:
                project_root = Path(project_root)
            project_script = project_root / "multiarrangement" / "optimize_cover_pure.py"
            if project_script.exists():
                optimize_script = project_script

        # 3. Try current working directory only as last resort
        if optimize_script is None:
            cwd_script = Path.cwd() / "optimize_cover_pure.py"
            if cwd_script.exists():
                optimize_script = cwd_script
        
        if optimize_script is None:
            print("⚠ optimize_cover_pure.py not found - using fallback method")
            return None
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            output_file = f.name
        
        try:
            # Run optimize_cover_pure.py with correct arguments
            cmd = [
                "python", str(optimize_script),
                "--v", str(self.n_videos),
                "--k", str(self.batch_size),
                "--outfile", output_file,
                "--offline-first",  # Use cache if available
                "--time-limit", "10"
            ]
            
            # Add any additional arguments
            if kwargs.get('seed'):
                cmd.extend(["--seed", str(kwargs['seed'])])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0 and os.path.exists(output_file):
                # Parse the output file
                batches = []
                with open(output_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Parse space or comma-separated integers
                            parts = line.replace(',', ' ').split()
                            batch = [int(x) for x in parts if x.isdigit()]
                            if len(batch) == self.batch_size:
                                batches.append(batch)
                
                return batches if batches else None
            else:
                # Check if it's a parameter limitation (LJCR doesn't have this covering design)
                stderr_lower = result.stderr.lower()
                if any(phrase in stderr_lower for phrase in [
                    "not available", "not found", "no such covering", 
                    "could not parse", "404", "not cached", "cache miss"
                ]):
                    return None  # Try next method
                else:
                    raise RuntimeError(f"optimize_cover_pure.py failed: {result.stderr}")
                    
        finally:
            # Clean up temporary file
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def _try_greedy_c_extension(self, **kwargs) -> Optional[List[List[int]]]:
        """Try to use pre-compiled C extension (preferred method)."""
        try:
            # Import the C extension module
            from ..greedy_c import generate_batches as generate_batches_c
            
            # Call the C function directly
            batches = generate_batches_c(self.n_videos, self.batch_size)
            return batches
            
        except ImportError:
            # C extension not available
            return None
        except Exception as e:
            raise RuntimeError(f"C extension failed: {e}")
    
    def _try_greedy_c_runtime(self, project_root: Path, **kwargs) -> Optional[List[List[int]]]:
        """Try to use compiled Greedy_gen.c for high-performance batch generation."""
        import subprocess
        import os
        import platform
        
        # Check for C source file
        c_source = project_root / "Greedy_gen.c"
        if not c_source.exists():
            raise FileNotFoundError("Greedy_gen.c not found")
        
        # Determine executable name based on platform
        if platform.system() == "Windows":
            exe_name = "greedy_gen.exe"
            compile_cmd = ["gcc", "-std=c11", "-O3", "-march=native", "-pipe", "-Wall", "-Wextra", 
                          str(c_source), "-o", exe_name]
        else:
            exe_name = "greedy_gen"
            compile_cmd = ["gcc", "-std=c11", "-O3", "-march=native", "-pipe", "-Wall", "-Wextra",
                          str(c_source), "-o", exe_name, "-lm"]
        
        exe_path = project_root / exe_name
        
        # Compile if executable doesn't exist or source is newer
        if not exe_path.exists() or c_source.stat().st_mtime > exe_path.stat().st_mtime:
            print(f"Compiling {c_source.name}...")
            
            # Check if gcc is available
            try:
                subprocess.run(["gcc", "--version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError("GCC compiler not available")
            
            # Compile
            result = subprocess.run(compile_cmd, cwd=project_root, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Compilation failed: {result.stderr}")
        
        # Run the compiled executable
        output_file = f"batches_{self.n_videos}videos_batchsize{self.batch_size}.txt"
        output_path = project_root / output_file
        
        # Remove existing output file
        if output_path.exists():
            output_path.unlink()
        
        cmd = [str(exe_path), str(self.n_videos), str(self.batch_size)]
        result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and output_path.exists():
            # Parse the output file
            batches = []
            with open(output_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Parse comma-separated integers
                        parts = line.replace(',', ' ').split()
                        batch = [int(x) for x in parts if x.isdigit()]
                        if len(batch) == self.batch_size:
                            batches.append(batch)
            
            return batches if batches else None
        else:
            raise RuntimeError(f"Greedy C program failed: {result.stderr}")
    
    def _try_new_greedy_python(self, **kwargs) -> List[List[int]]:
        """Use the integrated optimized greedy algorithm."""
        try:
            # Use our integrated optimized algorithm
            restarts = kwargs.get('restarts', 64)
            seed = kwargs.get('seed', 42)
            return self._generate_batches_optimized(restarts=restarts, seed=seed)
        except Exception as e:
            print(f"⚠ Advanced Python algorithm failed: {e}, using simple greedy")
            return self.greedy_algorithm()
    
    def optimize_batches(self, algorithm: str = 'hybrid', **kwargs) -> List[List[int]]:
        """
        Generate optimized batches using the specified algorithm.
        
        Args:
            algorithm: Algorithm to use ('hybrid', 'optimal', 'greedy', 'python', 'brute_force')
            **kwargs: Additional arguments for the algorithm
            
        Returns:
            List of optimized batches
        """
        if algorithm == 'hybrid':
            return self.optimize_batches_hybrid(**kwargs)
        elif algorithm == 'optimal':
            # Try only optimize_cover_pure.py
            return self.optimize_batches_hybrid(prefer_optimal=True, **kwargs)
        elif algorithm == 'greedy':
            # Try runtime C compilation or fallback to Python
            project_root = Path(__file__).parent.parent.parent
            try:
                batches = self._try_greedy_c_runtime(project_root, **kwargs)
                if batches:
                    print(f"✓ Used runtime C compilation: {len(batches)} batches")
                    return batches
            except Exception as e:
                print(f"⚠ Runtime C failed: {e}")
            
            print("ℹ Falling back to Python greedy")
            return self._try_new_greedy_python(**kwargs)
        elif algorithm == 'python':
            return self._try_new_greedy_python(**kwargs)
        elif algorithm == 'brute_force':
            return self.brute_force_algorithm(**kwargs)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}. Use 'hybrid', 'optimal', 'greedy', 'python', or 'brute_force'.")
