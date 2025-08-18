# optimize_cover_pure.py
# LJCR fetch -> (now) local cache -> repair/prune -> 1-opt local search
# -> targeted multi-block DFS swaps (pure stdlib) to reduce lambda_max.
# Output is 0-based by default (use --out-indexing one for 1-based).

from __future__ import annotations
import argparse, html, math, random, re, sys, time, urllib.request, os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------- combinatorial helpers ----------------
def pair_index(i: int, j: int, v: int) -> int:
    if i > j: i, j = j, i
    prior = i * (v - 1) - (i * (i - 1)) // 2
    return prior + (j - i - 1)

def invert_pair_index(p: int, v: int) -> Tuple[int,int]:
    acc = 0
    for i in range(v - 1):
        row = v - 1 - i
        if p < acc + row:
            j = i + 1 + (p - acc)
            return i, j
        acc += row
    raise ValueError("pair index out of range")

def block_pairs(block: Tuple[int,...], v: int) -> Tuple[int,...]:
    k = len(block)
    out: List[int] = []
    for a in range(k):
        ia = block[a]
        for b in range(a+1, k):
            ib = block[b]
            out.append(pair_index(ia, ib, v))
    return tuple(out)

def histogram(counts: List[int]) -> Dict[int,int]:
    h: Dict[int,int] = {}
    for c in counts: h[c] = h.get(c,0) + 1
    return dict(sorted(h.items()))

def schonheim_lb(v: int, k: int) -> int:
    # ceil(v/k * ceil((v-1)/(k-1)))
    return math.ceil((v / k) * math.ceil((v - 1) / (k - 1)))

# ---------------- LJCR fetch (robust parser) ----------------
LJCR_URL = "https://ljcr.dmgordon.org/cover/show_cover.php?v={v}&k={k}&t=2"
_INT_RE = re.compile(r"-?\d+")

def parse_blocks_from_html(html_text: str, v: int, k: int) -> List[Tuple[int,...]]:
    text = html.unescape(html_text)
    blocks: List[Tuple[int,...]] = []

    # Strategy 1: <pre>/<code>
    for tag in ("pre","code"):
        for m in re.finditer(fr"(?is)<{tag}[^>]*>(.*?)</{tag}>", text):
            for line in m.group(1).splitlines():
                nums = [int(x) for x in _INT_RE.findall(line)]
                if len(nums) == k:
                    blk = tuple(sorted(x-1 for x in nums))
                    if all(0 <= x < v for x in blk): blocks.append(blk)
        if blocks: return blocks

    # Strategy 2: per-line
    for line in text.splitlines():
        nums = [int(x) for x in _INT_RE.findall(line)]
        if len(nums) == k:
            blk = tuple(sorted(x-1 for x in nums))
            if all(0 <= x < v for x in blk): blocks.append(blk)
    if blocks: return blocks

    # Strategy 3: collect long run after first k-tuple, chunk
    allints: List[int] = []; seen_first = False
    for line in text.splitlines():
        nums = [int(x) for x in _INT_RE.findall(line)]
        if not nums: continue
        if not seen_first and len(nums) == k:
            seen_first = True; allints.extend(nums)
        elif seen_first:
            allints.extend(nums)
    if allints:
        for i in range(0, len(allints), k):
            chunk = allints[i:i+k]
            if len(chunk) != k: continue
            blk = tuple(sorted(x-1 for x in chunk))
            if all(0 <= x < v for x in blk): blocks.append(blk)
    return blocks

def fetch_ljcr_cover(v: int, k: int) -> List[Tuple[int,...]]:
    url = LJCR_URL.format(v=v, k=k)
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = resp.read().decode("utf-8", errors="replace")
    blocks = parse_blocks_from_html(data, v, k)
    if not blocks: raise RuntimeError(f"Could not parse blocks from LJCR (v={v},k={k}).")
    ks = {len(b) for b in blocks}
    if len(ks) != 1 or list(ks)[0] != k:
        raise RuntimeError(f"Parsed blocks have inconsistent k: {ks}")
    return blocks

# ---------------- cache utils ----------------
def cache_path(cache_dir: Path, v: int, k: int) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"v{v}_k{k}_t2.txt"  # stored as 0-based, one block per line

def read_blocks_file(path: Path, v: int, k: int) -> List[Tuple[int,...]]:
    blocks: List[Tuple[int,...]] = []
    if not path.exists(): return blocks
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip().replace(",", " ")
            if not ln or ln.startswith("#"): continue
            nums = [int(x) for x in ln.split()]
            if len(nums) != k: 
                # tolerate ragged lines (skip)
                continue
            blocks.append(tuple(sorted(nums)))
    if not blocks: return []
    # detect indexing: if any 0 present, assume 0-based; else assume 1-based
    zero_based = any(0 in b for b in blocks)
    if not zero_based:
        blocks = [tuple(x-1 for x in b) for b in blocks]
    # range check
    for b in blocks:
        if any(x < 0 or x >= v for x in b):
            raise ValueError(f"{path}: item out of range for v={v}.")
    return blocks

def save_blocks_file(path: Path, blocks: List[Tuple[int,...]], indexing: str = "zero") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for b in blocks:
            if indexing == "one":
                f.write(" ".join(str(x+1) for x in b) + "\n")
            else:
                f.write(" ".join(str(x) for x in b) + "\n")

def get_seed_blocks(v: int, k: int, cache_dir: Path, offline_first: bool, offline_only: bool) -> List[Tuple[int,...]]:
    p = cache_path(cache_dir, v, k)
    if offline_first or offline_only:
        blocks = read_blocks_file(p, v, k)
        if blocks:
            print(f"Loaded seed from cache: {p} (blocks={len(blocks)})")
            return blocks
        if offline_only:
            raise RuntimeError(f"Cache miss and offline-only enabled. Expected file: {p}")
    print(f"Cache miss for (v={v},k={k}). Fetching from LJCR…")
    blocks = fetch_ljcr_cover(v, k)
    # Save to cache as 0-based
    save_blocks_file(p, blocks, indexing="zero")
    print(f"Saved LJCR seed to cache: {p}")
    return blocks

# ---------------- bulk download ----------------
def bulk_download(cache_dir: Path, v_min: int, v_max: int, k_min: int, k_max: int, rate_ms: int, skip_existing: bool=True) -> None:
    total = 0; ok = 0; miss = 0; saved = 0
    for v in range(v_min, v_max+1):
        for k in range(k_min, min(k_max, v-1)+1):
            total += 1
            p = cache_path(cache_dir, v, k)
            if skip_existing and p.exists():
                print(f"[skip] v={v} k={k} -> {p.name}")
                ok += 1
                continue
            try:
                blocks = fetch_ljcr_cover(v, k)
                save_blocks_file(p, blocks, indexing="zero")
                print(f"[save] v={v} k={k} -> {p.name} (blocks={len(blocks)})")
                ok += 1; saved += 1
            except Exception as e:
                print(f"[MISS] v={v} k={k}: {e}")
                miss += 1
            # polite rate limit
            time.sleep(max(0.0, rate_ms/1000.0))
    print(f"Bulk done. tried={total}, ok={ok}, saved={saved}, miss={miss}")

# ---------------- coverage bookkeeping ----------------
def coverage_from_blocks(v: int, blocks: List[Tuple[int,...]]):
    P = v*(v-1)//2
    counts = [0]*P
    bpairs = [block_pairs(b, v) for b in blocks]
    for pp in bpairs:
        for p in pp: counts[p]+=1
    return counts, bpairs

def vertex_frequencies(v: int, blocks: List[Tuple[int,...]]) -> List[int]:
    freq = [0]*v
    for b in blocks:
        for x in b: freq[x]+=1
    return freq

# ---------------- repair + prune (if under-covered) ----------------
def greedy_sample_block(v: int, k: int, uncovered_pairs: Set[int], trials: int = 512, rng=random) -> Tuple[int,...]:
    if not uncovered_pairs:
        return tuple(sorted(rng.sample(range(v), k)))
    deg = [0]*v
    for p in uncovered_pairs:
        i,j = invert_pair_index(p, v); deg[i]+=1; deg[j]+=1
    weights = [d+1 for d in deg]
    best_blk, best_score = None, -1
    for _ in range(trials):
        cand = set(); w = weights[:]; total = sum(w)
        while len(cand) < k and total>0:
            r = rng.uniform(0,total); acc=0
            for u,wu in enumerate(w):
                acc += wu
                if acc >= r:
                    cand.add(u); total-=w[u]; w[u]=0; break
        if len(cand) < k:
            remain = [u for u in range(v) if u not in cand]
            rng.shuffle(remain)
            for u in remain[:k-len(cand)]: cand.add(u)
        blk = tuple(sorted(cand))
        c=0
        for a in range(k):
            ia = blk[a]
            for b in range(a+1,k):
                ib = blk[b]
                if pair_index(ia,ib,v) in uncovered_pairs: c+=1
        if c>best_score: best_score, best_blk = c, blk
    return best_blk

def repair_to_coverage(v: int, k: int, blocks: List[Tuple[int,...]], rng=random) -> List[Tuple[int,...]]:
    counts, bpairs = coverage_from_blocks(v, blocks)
    P = v*(v-1)//2
    uncovered = {p for p in range(P) if counts[p]==0}
    if not uncovered: return blocks
    while uncovered:
        blk = greedy_sample_block(v,k,uncovered, trials=512, rng=rng)
        blocks.append(blk)
        pp = block_pairs(blk,v); bpairs.append(pp)
        for p in pp:
            if counts[p]==0: uncovered.discard(p)
            counts[p]+=1
    # prune (safe deletions)
    order = list(range(len(blocks))); rng.shuffle(order)
    for idx in order:
        pp = bpairs[idx]
        if any(counts[p]==1 for p in pp): continue
        for p in pp: counts[p]-=1
        blocks[idx] = None
    return [b for b in blocks if b is not None]

# ---------------- optimizer (same as your version) ----------------
class CoverOptimizer:
    def __init__(self, v: int, blocks: List[Tuple[int,...]], seed: int = 12345):
        self.v=v; self.blocks=[tuple(sorted(b)) for b in blocks]; self.k=len(self.blocks[0])
        random.seed(seed)
        self.P = v*(v-1)//2
        self.block_pairs = [block_pairs(b, v) for b in self.blocks]
        self.pair_count = [0]*self.P
        for pp in self.block_pairs:
            for p in pp: self.pair_count[p]+=1
        if min(self.pair_count) < 1: raise ValueError("Seed cover does not cover all pairs.")

    def lambda_max(self)->int: return max(self.pair_count)
    def sumsq(self)->int: return sum(c*c for c in self.pair_count)
    def histogram(self)->Dict[int,int]: return histogram(self.pair_count)
    
    def count_at_level(self, level: int) -> int:
        """Count pairs at exactly the given level."""
        return sum(1 for c in self.pair_count if c == level)

    def try_replace_block(self, idx:int, *, forbid_above:Optional[int]=2, greedy_trials:int=1,
                          allow_noncritical:bool=True, avoid_pairs:Optional[Set[int]]=None) -> bool:
        v,k = self.v,self.k
        old_block = self.blocks[idx]
        old_pairs = set(self.block_pairs[idx])

        critical = [p for p in old_pairs if self.pair_count[p]==1]
        required: Set[int] = set()
        for p in critical:
            i,j = invert_pair_index(p, v); required.add(i); required.add(j)
        if not critical and not allow_noncritical: return False
        if len(required)>k: return False

        best_eval = (self.lambda_max(), self.count_at_level(self.lambda_max()), self.sumsq())
        best_cand: Optional[Tuple[int,...]] = None

        def add_cost(x:int, cur:Tuple[int,...])->int:
            cost=0
            for y in cur:
                if x==y: continue
                c=self.pair_count[pair_index(x,y,v)]
                cost += 1 + 2*c
            return cost

        trials=max(1,greedy_trials)
        for _ in range(trials):
            S=sorted(required)
            while len(S)<k:
                best_x=None; best_c=None
                for x in range(v):
                    if x in S: continue
                    c=add_cost(x, tuple(S))
                    if best_c is None or c<best_c or (c==best_c and random.random()<0.2):
                        best_c=c; best_x=x
                if best_x is None: break
                S.append(best_x)
            if len(S)!=k: continue
            cand=tuple(sorted(S))
            if cand==old_block: continue
            cand_pairs=set(block_pairs(cand, v))
            removed_only = old_pairs - cand_pairs
            added_only   = cand_pairs - old_pairs
            if any(self.pair_count[p]==1 for p in removed_only): continue
            if avoid_pairs and (cand_pairs & avoid_pairs): continue
            if forbid_above is not None and any(self.pair_count[p]+1 > forbid_above for p in added_only): continue

            cur_lmax=self.lambda_max(); cur_sumsq=self.sumsq()
            delta=0
            for p in removed_only: delta += 1 - 2*self.pair_count[p]
            for p in added_only:   delta += 1 + 2*self.pair_count[p]
            new_sumsq = cur_sumsq + delta

            maybe_inc = any(self.pair_count[p]+1 > cur_lmax for p in added_only)
            maybe_dec = any(self.pair_count[p]==cur_lmax for p in removed_only)
            if maybe_inc or maybe_dec:
                changed={}
                for p in removed_only: changed[p]=self.pair_count[p]-1
                for p in added_only:   changed[p]=changed.get(p,self.pair_count[p])+1
                new_lmax=0
                for p in range(self.P):
                    c = changed[p] if p in changed else self.pair_count[p]
                    if c>new_lmax: new_lmax=c
            else:
                new_lmax=cur_lmax

            # Count pairs at the new lambda_max level
            new_count_at_lmax = 0
            if maybe_inc or maybe_dec:
                for p in range(self.P):
                    c = changed[p] if p in changed else self.pair_count[p]
                    if c == new_lmax: new_count_at_lmax += 1
            else:
                new_count_at_lmax = self.count_at_level(new_lmax)
            
            new_eval = (new_lmax, new_count_at_lmax, new_sumsq)
            if new_eval < best_eval:
                best_eval = new_eval; best_cand = cand

        if best_cand is None: return False
        cand_pairs = set(block_pairs(best_cand, v))
        removed_only = set(self.block_pairs[idx]) - cand_pairs
        added_only   = cand_pairs - set(self.block_pairs[idx])
        for p in removed_only: self.pair_count[p]-=1
        for p in added_only:   self.pair_count[p]+=1
        self.blocks[idx]=best_cand
        self.block_pairs[idx]=tuple(sorted(cand_pairs))
        assert min(self.pair_count)>=1
        return True

    def local_search(self, passes:int=8, forbid_above:Optional[int]=2, greedy_trials:int=2)->None:
        for _ in range(passes):
            improved=False
            lmax=self.lambda_max()
            idxs=list(range(len(self.blocks)))
            idxs.sort(key=lambda i: sum(1 for p in self.block_pairs[i] if self.pair_count[p]==lmax), reverse=True)
            for i in idxs:
                if self.try_replace_block(i, forbid_above=forbid_above, greedy_trials=greedy_trials,
                                          allow_noncritical=True, avoid_pairs=None):
                    improved=True
            if not improved: break

    def offender_components(self, lmax: int) -> List[Tuple[Set[int], Set[int]]]:
        """Build connected components of the bipartite graph between offender pairs and blocks containing them."""
        # Build incidence lists once
        pair_to_blocks = {}
        for i, pp in enumerate(self.block_pairs):
            for p in pp:
                if self.pair_count[p] == lmax:
                    pair_to_blocks.setdefault(p, set()).add(i)

        seen_pairs, seen_blocks = set(), set()
        comps = []  # each: (pairs_set, blocks_set)
        for p in pair_to_blocks.keys():
            if p in seen_pairs: continue
            P, B = set(), set()
            stack = [("p", p)]
            while stack:
                typ, x = stack.pop()
                if typ == "p":
                    if x in seen_pairs: continue
                    seen_pairs.add(x); P.add(x)
                    for i in pair_to_blocks[x]:
                        if i not in seen_blocks:
                            stack.append(("b", i))
                else:  # block
                    if x in seen_blocks: continue
                    seen_blocks.add(x); B.add(x)
                    for q in self.block_pairs[x]:
                        if self.pair_count[q] == lmax and q not in seen_pairs:
                            stack.append(("p", q))
            if P: comps.append((P, B))
        # smallest first tends to be easiest
        comps.sort(key=lambda c: (len(c[0]) + len(c[1]), len(c[0])))
        return comps

    def add_cost_phi(self, x: int, cur: Tuple[int, ...], T: int, critical: Set[int], v: int) -> float:
        """Compute cost using convex penalty above T-1 and bonus for covering critical pairs."""
        cost = 0.0
        for y in cur:
            if x == y: continue
            q = pair_index(x, y, v)
            c = self.pair_count[q]
            if q in critical: cost -= 10  # reward covering critical
            # convex penalty above T-1
            if c >= T:
                d = c - (T-1)
                cost += d*d
        return cost

    def one_vertex_swap(self, T: int, iters: int = 1000, rng=random) -> bool:
        """Try replacing single vertices in blocks that touch offender pairs."""
        v, k = self.v, self.k
        improved = False
        offender = {p for p, c in enumerate(self.pair_count) if c >= T+1}
        blocks = list(range(len(self.blocks)))
        blocks.sort(key=lambda i: sum(1 for p in self.block_pairs[i] if p in offender), reverse=True)
        
        for i in blocks:
            B = list(self.blocks[i])
            base_pairs = set(self.block_pairs[i])
            # try each position
            for pos in range(k):
                u = B[pos]
                best = None
                for x in range(v):
                    if x in B: continue
                    cand = B[:]; cand[pos] = x; cand.sort()
                    pp = set(block_pairs(tuple(cand), v))
                    added = pp - base_pairs
                    removed = base_pairs - pp
                    # never break coverage
                    if any(self.pair_count[p]==1 for p in removed): continue
                    # respect the cap
                    if any(self.pair_count[p] + 1 > T for p in added): continue
                    # measure improvement: fewer offender pairs / fewer T pairs
                    cur_bad = sum(1 for p in base_pairs if self.pair_count[p] >= T+1)
                    new_bad = sum(1 for p in pp if self.pair_count[p] + (1 if p in added else 0) >= T+1)
                    if best is None or new_bad < best[0]:
                        best = (new_bad, tuple(cand), pp, added, removed)
                if best and best[0] < cur_bad:
                    _, cand, pp, added, removed = best
                    for p in removed: self.pair_count[p] -= 1
                    for p in added: self.pair_count[p] += 1
                    self.blocks[i] = cand
                    self.block_pairs[i] = tuple(sorted(pp))
                    improved = True
        return improved

    # ----- targeted multi-block DFS swap (pure stdlib) -----
    def reduce_lmax_group(self, target:int, time_limit:float=15.0, max_pairs_considered:int=20,
                          candidates_per_block:int=100, rng=random) -> bool:
        start = time.time()
        deadline = start + max(0.0, time_limit)
        v,k = self.v,self.k
        lmax = self.lambda_max()
        if lmax <= target: return False

        # Get offender components (smallest first)
        comps = self.offender_components(lmax)
        if not comps: return False
        
        # Prioritize easy offenders: fewest covering blocks, low vertex degree
        def offender_difficulty(p: int) -> Tuple[int, int, int]:
            i, j = invert_pair_index(p, v)
            covering_blocks = sum(1 for bp in self.block_pairs if p in bp)
            # Vertex degrees
            deg_i = sum(1 for bp in self.block_pairs for q in bp if i in invert_pair_index(q, v))
            deg_j = sum(1 for bp in self.block_pairs for q in bp if j in invert_pair_index(q, v))
            # Union neighborhood size
            blocks_touching_i_or_j = set()
            for idx, bp in enumerate(self.block_pairs):
                for q in bp:
                    ii, jj = invert_pair_index(q, v)
                    if ii == i or jj == i or ii == j or jj == j:
                        blocks_touching_i_or_j.add(idx)
            return (covering_blocks, deg_i + deg_j, len(blocks_touching_i_or_j))
        
        # Sort components by difficulty of their offender pairs
        for comp_idx, (pairs, blocks) in enumerate(comps):
            if pairs:
                min_difficulty = min(offender_difficulty(p) for p in pairs)
                comps[comp_idx] = (pairs, blocks, min_difficulty)
        
        comps.sort(key=lambda c: c[2] if len(c) > 2 else (0, 0, 0))

        for pairs, blocks, _ in comps:
            if time_limit > 0 and time.time() > deadline:
                break
            
            # Remove all blocks in this component when computing critical
            count_out = self.pair_count[:]
            for i in blocks:
                for q in self.block_pairs[i]: count_out[q]-=1
            if any(c > target for c in count_out):
                continue

            critical = {q for q in range(self.P) if count_out[q]==0}
            avoid_hi = {p for p,c in enumerate(self.pair_count) if c>=lmax-1}

            cand_lists: List[List[Tuple[int,...]]] = []
            cand_pairs: List[List[Set[int]]] = []
            for i in blocks:
                s: Set[Tuple[int,...]] = set()
                tries = 0
                while len(s) < candidates_per_block and tries < candidates_per_block*20:
                    if time_limit > 0 and time.time() > deadline:
                        # Out of time for this round
                        return False
                    tries += 1
                    S: List[int] = []
                    while len(S) < k:
                        best_x=None; best_sc=None
                        for x in range(v):
                            if x in S: continue
                            # Use phi-based cost for better scoring
                            sc = -self.add_cost_phi(x, tuple(S), target+1, critical, v)
                            sc += rng.random()*0.1  # Small random tie-breaker
                            if best_sc is None or sc>best_sc:
                                best_sc, best_x = sc, x
                        if best_x is None: break
                        S.append(best_x)
                    if len(S)!=k: continue
                    blk = tuple(sorted(S))
                    pp = set(block_pairs(blk, v))
                    if any(p in pairs for p in pp):  # avoid any offender pair in this component
                        continue
                    s.add(blk)
                lst = list(s)
                if not lst:
                    orig = set(self.blocks[i])
                    # Fallback sampling with caps and time checks
                    min_target = min(20, candidates_per_block)
                    attempts = 0
                    max_attempts = min_target * 100
                    while len(s) < min_target and attempts < max_attempts:
                        if time_limit > 0 and time.time() > deadline:
                            return False
                        attempts += 1
                        S = set(orig)
                        if len(S)>=2:
                            S = set(random.sample(list(S), k-2))
                        while len(S) < k:
                            S.add(rng.randrange(v))
                        blk = tuple(sorted(S))
                        pp = set(block_pairs(blk,v))
                        if any(p in pairs for p in pp): continue
                        s.add(blk)
                    lst = list(s)
                cand_lists.append(lst)
                cand_pairs.append([set(block_pairs(blk,v)) for blk in lst])

            temp = count_out[:]
            critical_list = sorted(list(critical))
            need = {q:1 for q in critical_list}
            cover_pos = {q:set() for q in critical_list}
            for pos in range(len(blocks)):
                for m,pp in enumerate(cand_pairs[pos]):
                    for q in critical_list:
                        if q in pp: cover_pos[q].add(pos)
            if any(len(cover_pos[q])==0 for q in critical_list):
                continue

            solution = [None]*len(blocks)
            deadline = start + time_limit

            def dfs(pos:int)->bool:
                if time.time() > deadline: return False
                if pos == len(blocks):
                    return True
                order = list(range(len(cand_lists[pos])))
                order.sort(key=lambda m: (
                    sum(temp[q] for q in cand_pairs[pos][m] if temp[q] >= target-1),
                    -sum(1 for q in cand_pairs[pos][m] if q in need and need[q]>0),
                    sum(1 for q in cand_pairs[pos][m] if temp[q] == target)  # Minimize pairs at target level
                ))
                for m in order:
                    pp = cand_pairs[pos][m]
                    if any(temp[q]+1 > target for q in pp): 
                        continue
                    # look-ahead on critical
                    ok=True
                    for q in critical_list:
                        if need[q]<=0: continue
                        possible = any( (q in cand_pairs[p2][mm]) for p2 in range(pos, len(blocks)) for mm in range(len(cand_lists[p2])) )
                        if not possible: ok=False; break
                    if not ok: continue

                    for q in pp: temp[q]+=1
                    changed=[]
                    for q in pp:
                        if q in need and need[q]>0:
                            need[q]-=1; changed.append(q)

                    solution[pos]=m
                    if dfs(pos+1): return True

                    solution[pos]=None
                    for q in pp: temp[q]-=1
                    for q in changed: need[q]+=1
                return False

            if dfs(0):
                block_list = list(blocks)
                for pos, i in enumerate(block_list):
                    m = solution[pos]
                    new_blk = cand_lists[pos][m]
                    old_pp = self.block_pairs[i]
                    for q in old_pp: self.pair_count[q]-=1
                    self.blocks[i] = new_blk
                    new_pp = tuple(sorted(block_pairs(new_blk, v)))
                    self.block_pairs[i] = new_pp
                    for q in new_pp: self.pair_count[q]+=1
                assert min(self.pair_count) >= 1
                print(f"[group] reduced component with {len(pairs)} offender pairs from lambda={lmax} to <={target} across {len(blocks)} blocks.")
                return True
        return False

# ---------------- CLI ----------------
def main():
    ap = argparse.ArgumentParser(description="Cache-first LJCR (v,k,2) -> repair -> local search -> pure-stdlib group DFS swaps.")
    ap.add_argument("--v", type=int, help="number of items (points)")
    ap.add_argument("--k", type=int, help="block size")
    ap.add_argument("--passes", type=int, default=12)
    ap.add_argument("--greedy_trials", type=int, default=2)
    ap.add_argument("--forbid_above", type=int, default=2, help="-1 to disable cap during local search")
    ap.add_argument("--group_rounds", type=int, default=12, help="how many group DFS attempts")
    ap.add_argument("--group_time", type=float, default=10.0, help="seconds per group attempt")
    ap.add_argument("--group_cands", type=int, default=100, help="candidate blocks per position")
    ap.add_argument("--outfile", type=str, default=None)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--out-indexing", choices=["zero","one"], default="zero")
    ap.add_argument("--time-limit", type=float, default=10.0, help="overall time limit in seconds (<=0 to disable)")

    # cache + offline
    # Default to the packaged cache inside the installed module
    default_cache = str((Path(__file__).parent / "ljcr_cache").resolve())
    ap.add_argument("--cache-dir", type=str, default=default_cache)
    ap.add_argument("--offline-first", action="store_true", help="load from cache if available (default)")
    ap.add_argument("--offline-only", action="store_true", help="do not fetch; error on cache miss")
    ap.add_argument("--seed-file", type=str, default=None, help="explicit seed file (auto 0/1-base detection)")

    # bulk download mode
    ap.add_argument("--bulk-download", action="store_true", help="download covers into cache and exit")
    ap.add_argument("--v-min", type=int, default=4)
    ap.add_argument("--v-max", type=int, default=100)
    ap.add_argument("--k-min", type=int, default=2)
    ap.add_argument("--k-max", type=int, default=10)
    ap.add_argument("--rate-ms", type=int, default=250, help="delay between LJCR requests (ms)")

    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    start_time = time.time()
    deadline = (start_time + args.time_limit) if args.time_limit and args.time_limit > 0 else None

    # Bulk mode
    if args.bulk_download:
        bulk_download(cache_dir, args.v_min, args.v_max, args.k_min, args.k_max, args.rate_ms, skip_existing=True)
        return

    if args.v is None or args.k is None:
        print("Error: --v and --k are required unless --bulk-download is set.", file=sys.stderr)
        sys.exit(2)

    v,k = args.v, args.k
    rng = random.Random(args.seed)
    random.seed(args.seed)

    # Seed blocks: seed-file > cache (offline-first) > LJCR fetch
    if args.seed_file:
        path = Path(args.seed_file)
        blocks = read_blocks_file(path, v, k)
        if not blocks:
            print(f"Failed to read seed from {path}", file=sys.stderr)
            sys.exit(1)
        print(f"Loaded local seed: {path} (blocks={len(blocks)})")
    else:
        blocks = get_seed_blocks(v, k, cache_dir, offline_first=True or args.offline_first, offline_only=args.offline_only)

    # If under-covered (rare for LJCR), repair then prune
    counts, _ = coverage_from_blocks(v, blocks)
    if min(counts) < 1:
        print("Seed under-covers; repairing…")
        blocks = repair_to_coverage(v,k,blocks, rng=rng)
        print(f"Repaired to {len(blocks)} blocks with full coverage.")

    # prune deletions (safe)
    counts, bpairs = coverage_from_blocks(v, blocks)
    order=list(range(len(blocks))); rng.shuffle(order)
    removed=0
    for idx in order:
        pp = bpairs[idx]
        if any(counts[p]==1 for p in pp): continue
        for p in pp: counts[p]-=1
        blocks[idx]=None; removed+=1
    if removed:
        blocks=[b for b in blocks if b is not None]
        print(f"Pruned {removed} redundant blocks; now {len(blocks)}.")

    # Stats
    P=v*(v-1)//2; b=len(blocks)
    avg_lambda = b * (k*(k-1)//2) / P
    print(f"Seed (after repair/prune): b={b}, Schonheim>={schonheim_lb(v,k)}, avg lambda={avg_lambda:.3f}")
    freq = vertex_frequencies(v, blocks)
    lmax_vertex_lb = max((7*f + (v-2)) // (v-1) for f in freq)  # ceil(7f/(v-1))
    print(f"Vertex-frequency lower bound on lambda_max: >= {lmax_vertex_lb} (max f_i={max(freq)})")
    # Prepare output path early so we can save on timeout
    outpath = Path(args.outfile or f"rebalance_v{v}_k{k}.txt")
    one_based = (args.out_indexing == "one")

    # 1-opt local search
    opt = CoverOptimizer(v, blocks, seed=args.seed)

    def time_left():
        if deadline is None:
            return None
        return max(0.0, deadline - time.time())

    def maybe_timeout():
        if deadline is not None and time.time() >= deadline:
            print("Time limit reached; saving current cover…")
            save_blocks_file(outpath, opt.blocks, indexing=("one" if one_based else "zero"))
            print("Saved improved cover to", outpath)
            sys.exit(0)
    print("Initial  lambda_max:", opt.lambda_max(), "hist:", opt.histogram(), "sumsq:", opt.sumsq())
    forbid = None if args.forbid_above < 0 else args.forbid_above
    opt.local_search(passes=args.passes, forbid_above=forbid, greedy_trials=args.greedy_trials)
    maybe_timeout()

    # 1-vertex swap pass to clear stubborn offenders
    print("Running 1-vertex swap pass...")
    opt.one_vertex_swap(T=opt.lambda_max()-1, iters=1000, rng=rng)
    maybe_timeout()

    # Phase: minimize count of pairs at current lambda_max
    print("Phase: minimizing count of pairs at current lambda_max...")
    lmax = opt.lambda_max()
    while lmax > 2:
        maybe_timeout()
        count_at_lmax = opt.count_at_level(lmax)
        print(f"Current lambda_max={lmax}, count={count_at_lmax}")
        
        # Try to reduce the count at this level
        improved_count = False
        for _ in range(3):  # Up to 3 attempts
            old_count = opt.count_at_level(lmax)
            opt.local_search(passes=2, forbid_above=lmax, greedy_trials=3)
            new_count = opt.count_at_level(lmax)
            if new_count < old_count:
                improved_count = True
                print(f"Reduced count at lambda_max={lmax} from {old_count} to {new_count}")
                break
            maybe_timeout()
        
        if not improved_count:
            break
        
        # Check if lambda_max dropped
        new_lmax = opt.lambda_max()
        if new_lmax < lmax:
            lmax = new_lmax
            print(f"lambda_max dropped to {lmax}")
        else:
            break

    # group DFS rounds with early stopping
    improved = True
    rounds_left = args.group_rounds
    while rounds_left>0 and improved:
        rounds_left -= 1
        lnow = opt.lambda_max()
        if lnow <= 2: break
        target = lnow - 1
        print(f"[group] trying target lambda_max={target} ... (round {args.group_rounds - rounds_left}/{args.group_rounds})")
        remaining = time_left()
        round_time = args.group_time if (remaining is None) else max(0.0, min(args.group_time, remaining))
        if remaining is not None and remaining <= 0:
            maybe_timeout()
        improved = opt.reduce_lmax_group(target=target, time_limit=round_time,
                                         max_pairs_considered=20, candidates_per_block=args.group_cands, rng=rng)
        maybe_timeout()
        
        # Early stop: if we succeeded, try another round immediately
        if improved:
            print(f"[group] success! lambda_max reduced to {opt.lambda_max()}")
            rounds_left += 1  # Give another round

    # Final 1-vertex swap pass
    print("Final 1-vertex swap pass...")
    opt.one_vertex_swap(T=opt.lambda_max()-1, iters=1000, rng=rng)
    maybe_timeout()

    print("Final    lambda_max:", opt.lambda_max(), "hist:", opt.histogram(), "sumsq:", opt.sumsq())

    with outpath.open("w", encoding="utf-8") as f:
        for blk in opt.blocks:
            if one_based: f.write(" ".join(str(x+1) for x in blk) + "\n")
            else:         f.write(" ".join(str(x)   for x in blk) + "\n")
    print("Saved improved cover to", outpath)

if __name__ == "__main__":
    main()
