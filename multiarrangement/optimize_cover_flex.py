# optimize_cover_pure_varsize.py
# LJCR fetch -> local cache -> repair/prune -> size-aware local search
# -> targeted multi-block DFS over *components* (size-aware, shrink-only).
# Supports shrinking blocks down to --min-k-size (default 2), never increasing sizes.
# Output lines are variable-length (each block on its own line), 0-based by default.

from __future__ import annotations
import argparse, html, math, random, re, sys, time, urllib.request
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

# ---------------- floors for variable block sizes ----------------
def total_pair_budget(blocks: List[Tuple[int,...]]) -> int:
    return sum(len(b)*(len(b)-1)//2 for b in blocks)

def lambda_floor(blocks: List[Tuple[int,...]], v: int) -> int:
    P = v*(v-1)//2
    S = total_pair_budget(blocks)
    floor_avg = math.ceil(S / P) if P>0 else 0
    inc = [0]*v
    for b in blocks:
        kb = len(b)
        for x in b:
            inc[x] += (kb-1)
    floor_vertex = max(math.ceil(inc[x]/(v-1)) for x in range(v)) if v>1 else 0
    return max(floor_avg, floor_vertex)

# Schonheim LB (for fixed k, informational)
def schonheim_lb(v: int, k: int) -> int:
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
    # Strategy 3: after first k-tuple, chunk
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

def read_blocks_file_fixed(path: Path, v: int, k: int) -> List[Tuple[int,...]]:
    """Strict reader expecting exactly k entries per line (for LJCR cache)."""
    blocks: List[Tuple[int,...]] = []
    if not path.exists(): return blocks
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip().replace(",", " ")
            if not ln or ln.startswith("#"): continue
            nums = [int(x) for x in ln.split()]
            if len(nums) != k: 
                continue
            blocks.append(tuple(sorted(nums)))
    if not blocks: return []
    zero_based = any(0 in b for b in blocks)
    if not zero_based:
        blocks = [tuple(x-1 for x in b) for b in blocks]
    for b in blocks:
        if any(x < 0 or x >= v for x in b):
            raise ValueError(f"{path}: item out of range for v={v}.")
    return blocks

def read_blocks_file_var(path: Path, v: int) -> List[Tuple[int,...]]:
    """Lenient reader: accepts variable-length lines (>=2, <=v)."""
    blocks: List[Tuple[int,...]] = []
    if not path.exists(): return blocks
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip().replace(",", " ")
            if not ln or ln.startswith("#"): continue
            nums = [int(x) for x in ln.split()]
            if len(nums) < 2 or len(nums) > v: 
                continue
            blocks.append(tuple(sorted(nums)))
    if not blocks: return []
    zero_based = any(0 in b for b in blocks)
    if not zero_based:
        blocks = [tuple(x-1 for x in b) for b in blocks]
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
        blocks = read_blocks_file_fixed(p, v, k)
        if blocks:
            print(f"Loaded seed from cache: {p} (blocks={len(blocks)})")
            return blocks
        if offline_only:
            raise RuntimeError(f"Cache miss and offline-only enabled. Expected file: {p}")
    print(f"Cache miss for (v={v},k={k}). Fetching from LJCR…")
    blocks = fetch_ljcr_cover(v, k)
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

# ---------------- optimizer (size-aware, shrink-only) ----------------
class CoverOptimizer:
    def __init__(self, v: int, blocks: List[Tuple[int,...]], seed: int = 12345):
        self.v = v
        self.blocks = [tuple(sorted(b)) for b in blocks]
        random.seed(seed)
        self.P = v*(v-1)//2
        self.block_pairs = [block_pairs(b, v) for b in self.blocks]
        self.pair_count = [0]*self.P
        for pp in self.block_pairs:
            for p in pp: self.pair_count[p]+=1
        if min(self.pair_count) < 1: raise ValueError("Seed cover does not cover all pairs.")

    # ----- stats -----
    def lambda_max(self)->int: return max(self.pair_count)
    def sumsq(self)->int: return sum(c*c for c in self.pair_count)
    def histogram(self)->Dict[int,int]: return histogram(self.pair_count)

    # ----- local greedy candidate add cost -----
    def _add_cost(self, x:int, cur:Tuple[int,...], T:Optional[int])->int:
        v = self.v; cost=0
        for y in cur:
            if x==y: continue
            c=self.pair_count[pair_index(x,y,v)]
            if T is not None and c>=T:
                d = c - (T-1)
                cost += d*d
            else:
                cost += 1 + 2*c
        return cost

    # ----- variable-size 1-opt (shrink allowed, never grow) -----
    def try_replace_block(self, idx:int, *, forbid_above:Optional[int]=2, greedy_trials:int=1,
                          allow_noncritical:bool=True, avoid_pairs:Optional[Set[int]]=None,
                          k_min_size:int=2) -> bool:
        v = self.v
        old_block = self.blocks[idx]
        old_pairs = set(self.block_pairs[idx])
        k0 = len(old_block)

        critical = [p for p in old_pairs if self.pair_count[p]==1]
        required: Set[int] = set()
        for p in critical:
            i,j = invert_pair_index(p, v); required.add(i); required.add(j)
        if not critical and not allow_noncritical: return False
        if len(required)>k0: return False  # cannot grow

        kmin = max(k_min_size, len(required))
        sizes = list(range(k0, kmin-1, -1))  # same size first, then smaller

        best_eval = (self.lambda_max(), self.sumsq())
        best_cand: Optional[Tuple[int,...]] = None

        T = forbid_above
        trials=max(1,greedy_trials)
        for m in sizes:
            for _ in range(trials):
                S=sorted(required)
                while len(S)<m:
                    best_x=None; best_c=None
                    # candidate pool: endpoints of required + low-pressure vertices wrt current S
                    for x in range(v):
                        if x in S: continue
                        c=self._add_cost(x, tuple(S), T)
                        if best_c is None or c<best_c or (c==best_c and random.random()<0.2):
                            best_c=c; best_x=x
                    if best_x is None: break
                    S.append(best_x)
                if len(S)!=m: continue
                cand=tuple(sorted(S))
                if cand==old_block: continue
                cand_pairs=set(block_pairs(cand, v))
                removed_only = old_pairs - cand_pairs
                added_only   = cand_pairs - old_pairs
                if any(self.pair_count[p]==1 for p in removed_only): continue
                if avoid_pairs and (cand_pairs & avoid_pairs): continue
                if T is not None and any(self.pair_count[p]+1 > T for p in added_only): continue

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

                if (new_lmax, new_sumsq) < best_eval:
                    best_eval=(new_lmax,new_sumsq); best_cand=cand
            if best_cand is not None:
                break

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

    def local_search(self, passes:int=8, forbid_above:Optional[int]=2, greedy_trials:int=2, k_min_size:int=2)->None:
        for _ in range(passes):
            improved=False
            lmax=self.lambda_max()
            idxs=list(range(len(self.blocks)))
            idxs.sort(key=lambda i: sum(1 for p in self.block_pairs[i] if self.pair_count[p]==lmax), reverse=True)
            for i in idxs:
                if self.try_replace_block(i, forbid_above=forbid_above, greedy_trials=greedy_trials,
                                          allow_noncritical=True, avoid_pairs=None, k_min_size=k_min_size):
                    improved=True
            if not improved: break

    # ----- shrink passes -----
    def shrink_one_vertex_pass(self, k_min_size:int, cap:int, max_sweeps:int=2, rng=random) -> bool:
        v = self.v
        changed_any = False
        for _ in range(max_sweeps):
            lmax = self.lambda_max()
            offender = {p for p,c in enumerate(self.pair_count) if c == lmax}
            order = list(range(len(self.blocks)))
            order.sort(key=lambda i: sum(1 for p in self.block_pairs[i] if p in offender), reverse=True)
            sweep_changed = False
            lmax_count_total = sum(1 for c in self.pair_count if c == lmax)
            for i in order:
                B = list(self.blocks[i]); m = len(B)
                if m <= k_min_size: 
                    continue
                # removable vertices (no unique pairs)
                removable: List[Tuple[int, List[int]]] = []
                for u in B:
                    rem_pairs = []
                    ok = True
                    for y in B:
                        if y == u: continue
                        p = pair_index(u, y, v)
                        if self.pair_count[p] == 1:
                            ok = False; break
                        rem_pairs.append(p)
                    if ok:
                        removable.append((u, rem_pairs))
                if not removable:
                    continue
                best = None
                for (u, rem_pairs) in removable:
                    rm_lmax_cnt = sum(1 for p in rem_pairs if self.pair_count[p] == lmax)
                    new_lmax_est = lmax if lmax_count_total > rm_lmax_cnt else lmax - 1
                    tpair_delta = -sum(1 for p in rem_pairs if self.pair_count[p] == lmax)
                    delta_sumsq = 0
                    for p in rem_pairs:
                        c = self.pair_count[p]
                        delta_sumsq += (c-1)*(c-1) - c*c
                    key = (new_lmax_est, -tpair_delta, delta_sumsq)
                    if (best is None) or (key < best[0]):
                        best = (key, u, rem_pairs)
                if best is None:
                    continue
                _, u, rem_pairs = best
                for p in rem_pairs:
                    self.pair_count[p] -= 1
                B.remove(u)
                self.blocks[i] = tuple(sorted(B))
                self.block_pairs[i] = tuple(sorted(block_pairs(self.blocks[i], v)))
                sweep_changed = True
                changed_any = True
                lmax = self.lambda_max()
                lmax_count_total = sum(1 for c in self.pair_count if c == lmax)
            if not sweep_changed:
                break
        return changed_any

    def shrink_to_min_pass(self, k_min_size:int=2, max_sweeps:int=2) -> bool:
        """Aggressively shrink blocks down to the minimum, preserving critical pairs."""
        v = self.v
        changed_any = False
        for _ in range(max_sweeps):
            changed = False
            lmax = self.lambda_max()
            offender = {p for p,c in enumerate(self.pair_count) if c == lmax}
            order = list(range(len(self.blocks)))
            order.sort(key=lambda i: sum(1 for p in self.block_pairs[i] if p in offender), reverse=True)
            for i in order:
                B = list(self.blocks[i])
                if len(B) <= k_min_size: 
                    continue
                # required vertices to maintain all currently 1-covered pairs in this block
                required = set()
                for p in self.block_pairs[i]:
                    if self.pair_count[p] == 1:
                        a,b = invert_pair_index(p, v)
                        if a in B and b in B:
                            required.add(a); required.add(b)
                k_target = max(k_min_size, len(required))
                if k_target >= len(B): 
                    continue
                opt = [u for u in B if u not in required]
                # remove high-pressure vertices first
                def pressure(u):
                    return sum(1 for y in B if y!=u and self.pair_count[pair_index(u,y,v)] >= lmax)
                opt.sort(key=pressure, reverse=True)
                removed = False
                for u in opt:
                    if len(B) <= k_target: break
                    # only remove if it won't break coverage
                    ok=True; rem=[]
                    for y in B:
                        if y==u: continue
                        p = pair_index(u,y,v)
                        if self.pair_count[p] == 1:
                            ok=False; break
                        rem.append(p)
                    if not ok: continue
                    for p in rem: self.pair_count[p]-=1
                    B.remove(u)
                    removed = True
                if removed:
                    self.blocks[i] = tuple(sorted(B))
                    self.block_pairs[i] = tuple(sorted(block_pairs(self.blocks[i], v)))
                    changed = True; changed_any = True
            if not changed: break
        return changed_any

    # ----- offender components -----
    def offender_components(self) -> List[Tuple[List[int], List[int]]]:
        """Return components as (block_indices, offender_pairs) sorted by size."""
        lmax = self.lambda_max()
        offenders = [p for p,c in enumerate(self.pair_count) if c==lmax]
        if not offenders: return []
        pair_to_blocks: Dict[int,List[int]] = {p: [] for p in offenders}
        for i,pp in enumerate(self.block_pairs):
            for p in pp:
                if p in pair_to_blocks: pair_to_blocks[p].append(i)
        seen_pairs:set[int]=set(); seen_blocks:set[int]=set(); comps=[]
        for p in offenders:
            if p in seen_pairs: continue
            q = [("p",p)]; P=[]; B=[]
            seen_pairs.add(p)
            while q:
                t,x = q.pop()
                if t=="p":
                    P.append(x)
                    for i in pair_to_blocks.get(x,[]):
                        if i in seen_blocks: continue
                        seen_blocks.add(i)
                        q.append(("b", i))
                else:
                    B.append(x)
                    for p2 in self.block_pairs[x]:
                        if p2 not in pair_to_blocks or p2 in seen_pairs: continue
                        seen_pairs.add(p2)
                        q.append(("p", p2))
            comps.append((B,P))
        comps.sort(key=lambda bp: (len(bp[0])+len(bp[1]), len(bp[0])))
        return comps

    # ----- restricted candidate pool -----
    def candidate_pool(self, idx:int, critical_vertices:Set[int], target:int, pool_cap:int=24) -> List[int]:
        v = self.v
        base = set(self.blocks[idx])
        pool = set(base) | set(critical_vertices)
        scores = []
        for x in range(v):
            if x in pool: continue
            c = 0
            for y in base:
                if x==y: continue
                if self.pair_count[pair_index(x,y,v)] >= target: c += 1
            scores.append((c,x))
        scores.sort(key=lambda t:t[0])
        for _,x in scores[:max(0, pool_cap-len(pool))]:
            pool.add(x)
        return list(pool)

    # ----- tiny 2-block "kick" to free an offender quickly -----
    def two_block_kick(self, p0:int, target:int, k_min_size:int=2, rng=random) -> bool:
        v = self.v
        a,b = invert_pair_index(p0, v)
        idxs = [i for i,pp in enumerate(self.block_pairs) if p0 in pp]
        rng.shuffle(idxs)
        changed=False
        for i in idxs[:6]:
            B = list(self.blocks[i])
            if len(B) <= k_min_size: continue
            for u in (a,b):
                if u not in B: continue
                # safe removal?
                rem = []
                ok=True
                for y in B:
                    if y==u: continue
                    p = pair_index(u,y,v)
                    if self.pair_count[p]==1: ok=False; break
                    rem.append(p)
                if not ok: continue
                for p in rem: self.pair_count[p]-=1
                B.remove(u)
                self.blocks[i] = tuple(sorted(B))
                self.block_pairs[i] = tuple(sorted(block_pairs(self.blocks[i], v)))
                changed=True
                break
            if changed: break
        return changed

    # ----- component-level DFS swap (size-aware, shrink-only) -----
    def reduce_component(self, idxs: List[int], target:int, time_limit:float=2.0,
                         candidates_per_block:int=60, k_min_size:int=2, rng=random) -> bool:
        start = time.time()
        v = self.v
        lmax = self.lambda_max()
        if lmax <= target or not idxs: return False

        # remove component blocks virtually
        count_out = self.pair_count[:]
        for i in idxs:
            for q in self.block_pairs[i]: count_out[q]-=1
        if any(c > target for c in count_out):
            return False

        critical = {q for q in range(self.P) if count_out[q]==0}
        crit_vertices:set[int] = set()
        for q in critical:
            a,b = invert_pair_index(q, v); crit_vertices.add(a); crit_vertices.add(b)

        avoid_hi = {p for p,c in enumerate(self.pair_count) if c>=target}

        cand_lists: List[List[Tuple[int,...]]] = []
        cand_pairs: List[List[Set[int]]] = []
        for i in idxs:
            s: Set[Tuple[int,...]] = set()
            tries = 0
            k0 = len(self.blocks[i])
            kmin = max(k_min_size, 2)
            sizes = list(range(k0, kmin-1, -1))
            pool = self.candidate_pool(i, crit_vertices, target, pool_cap=24)
            while len(s) < candidates_per_block and tries < candidates_per_block*30:
                tries += 1
                m = sizes[min(len(sizes)-1, tries % max(1,len(sizes)))] if sizes else k0
                S: List[int] = []
                # greedy fill from pool
                while len(S) < m:
                    best_x=None; best_sc=None
                    for x in pool:
                        if x in S: continue
                        sc = 0.0
                        for y in S:
                            q = pair_index(x,y,v)
                            if q in critical: sc += 5.0
                            if q in avoid_hi: sc -= 2.0
                            if self.pair_count[q] >= target: sc -= 3.0
                        sc += rng.random()*0.1
                        if best_sc is None or sc>best_sc:
                            best_sc, best_x = sc, x
                    if best_x is None: break
                    S.append(best_x)
                if len(S)!=m: continue
                blk = tuple(sorted(S))
                pp = set(block_pairs(blk, v))
                if any(self.pair_count[q]+1 > target for q in pp):
                    continue
                s.add(blk)
                # time slice check
                if time.time() - start > time_limit:
                    break
            lst = list(s)
            if not lst:
                # fallback minimal candidates: current block shrunk by one, respecting kmin
                orig = set(self.blocks[i])
                if len(orig) > kmin:
                    S = set(orig)
                    # try to remove a high-pressure vertex
                    def press(u):
                        return sum(1 for y in S if y!=u and self.pair_count[pair_index(u,y,v)]>=target)
                    u = max(S, key=press)
                    S.remove(u)
                    blk = tuple(sorted(S))
                    pp = set(block_pairs(blk, v))
                    if not any(self.pair_count[q]+1 > target for q in pp):
                        lst = [blk]
            cand_lists.append(lst)
            cand_pairs.append([set(block_pairs(blk,v)) for blk in lst])
            # fail-fast
            if time.time() - start > time_limit:
                break

        if any(len(lst) < 1 for lst in cand_lists):
            return False

            temp = count_out[:]
            critical_list = sorted(list(critical))
            need = {q:1 for q in critical_list}

            solution = [None]*len(idxs)
            deadline = start + time_limit

            def dfs(pos:int)->bool:
                if time.time() > deadline: return False
                if pos == len(idxs):
                    return True
                order = list(range(len(cand_lists[pos])))
                order.sort(key=lambda m: (
                    sum(temp[q] for q in cand_pairs[pos][m] if temp[q] >= target-1),
                    -sum(1 for q in cand_pairs[pos][m] if q in need and need[q]>0)
                ))
                for m in order:
                    pp = cand_pairs[pos][m]
                    if any(temp[q]+1 > target for q in pp): 
                        continue
                # look-ahead on critical
                    ok=True
                    for q in critical_list:
                        if need[q]<=0: continue
                    possible = False
                    for p2 in range(pos, len(idxs)):
                        for mm in range(len(cand_lists[p2])):
                            if q in cand_pairs[p2][mm]:
                                possible = True; break
                        if possible: break
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
            # commit
                for pos, i in enumerate(idxs):
                    m = solution[pos]
                    new_blk = cand_lists[pos][m]
                    old_pp = self.block_pairs[i]
                    for q in old_pp: self.pair_count[q]-=1
                    self.blocks[i] = new_blk
                    new_pp = tuple(sorted(block_pairs(new_blk, v)))
                    self.block_pairs[i] = new_pp
                    for q in new_pp: self.pair_count[q]+=1
                assert min(self.pair_count) >= 1
                return True
        return False

# ---------------- CLI ----------------
def main():
    ap = argparse.ArgumentParser(description="Cache-first LJCR (v,k,2) -> repair -> size-aware local search -> component DFS (shrink-only).")
    ap.add_argument("--v", type=int, help="number of items (points)")
    ap.add_argument("--k", type=int, help="initial uniform block size (from LJCR seed)")
    ap.add_argument("--passes", type=int, default=15)
    ap.add_argument("--greedy_trials", type=int, default=4)
    ap.add_argument("--forbid_above", type=int, default=2, help="cap during local search / DFS; -1 to disable (floors still apply)")
    ap.add_argument("--group_rounds", type=int, default=12, help="how many DFS rounds")
    ap.add_argument("--group_time", type=float, default=6.0, help="seconds per DFS round (split across components)")
    ap.add_argument("--group_cands", type=int, default=100, help="candidate blocks per position (upper bound)")
    ap.add_argument("--outfile", type=str, default=None)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--out-indexing", choices=["zero","one"], default="zero")

    # shrink-only size control (default to 2 per your request)
    ap.add_argument("--min-k-size", type=int, default=2, help="minimum allowed block size after shrink (>=2). Default 2.")

    # cache + offline
    # Default to the packaged cache inside the installed module
    default_cache = str((Path(__file__).parent / "ljcr_cache").resolve())
    ap.add_argument("--cache-dir", type=str, default=default_cache)
    ap.add_argument("--offline-first", action="store_true", default=True, help="load from cache if available (default)")
    ap.add_argument("--offline-only", action="store_true", help="do not fetch; error on cache miss")
    ap.add_argument("--seed-file", type=str, default=None, help="explicit seed file (auto 0/1-base detection; variable sizes allowed)")

    # bulk download
    ap.add_argument("--bulk-download", action="store_true", help="download covers into cache and exit")
    ap.add_argument("--v-min", type=int, default=4)
    ap.add_argument("--v-max", type=int, default=100)
    ap.add_argument("--k-min", type=int, default=2)
    ap.add_argument("--k-max", type=int, default=10)
    ap.add_argument("--rate-ms", type=int, default=250, help="delay between LJCR requests (ms)")

    args = ap.parse_args()
    cache_dir = Path(args.cache_dir)

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
    min_k_size = max(2, args.min_k_size or 2)

    # Seed blocks: seed-file (variable) > cache (fixed) > LJCR fetch
    if args.seed_file:
        path = Path(args.seed_file)
        blocks = read_blocks_file_var(path, v)
        if not blocks:
            print(f"Failed to read seed from {path}", file=sys.stderr)
            sys.exit(1)
        print(f"Loaded local seed (variable sizes allowed): {path} (blocks={len(blocks)})")
    else:
        # Honor --offline-first only if set; default is to fetch on miss
        blocks = get_seed_blocks(v, k, cache_dir, offline_first=args.offline_first, offline_only=args.offline_only)

    # If under-covered (rare for LJCR), repair then prune (keep uniform k during repair)
    counts, _ = coverage_from_blocks(v, blocks)
    if min(counts) < 1:
        print("Seed under-covers; repairing…")
        def greedy_sample_block(v,k,rng=random):
            deg=[0]*v
            uncovered=[p for p,c in enumerate(counts) if c==0]
            if not uncovered:
                return tuple(sorted(rng.sample(range(v), k)))
            for p in uncovered:
                i,j = invert_pair_index(p,v); deg[i]+=1; deg[j]+=1
            S=sorted(range(v), key=lambda x:-deg[x])[:k]
            return tuple(sorted(S))
        while min(counts) < 1:
            blk = greedy_sample_block(v, k, rng)
            blocks.append(blk)
            pp = block_pairs(blk, v)
            for p in pp: counts[p]+=1
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
    S = total_pair_budget(blocks)
    avg_lambda = S / P if P>0 else 0.0
    print(f"Seed (after repair/prune): b={b}, initial k={k}, Schonheim>={schonheim_lb(v,k)}, avg lambda={avg_lambda:.3f}")
    global_floor = lambda_floor(blocks, v)
    print(f"Lambda floor (variable sizes): >= {global_floor}")

    # Build optimizer
    opt = CoverOptimizer(v, blocks, seed=args.seed)
    print("Initial  lambda_max:", opt.lambda_max(), "hist:", opt.histogram(), "sumsq:", opt.sumsq())

    # Aggressive shrink-to-min first (mink=2 default)
    if opt.shrink_to_min_pass(k_min_size=min_k_size, max_sweeps=2):
        S = total_pair_budget(opt.blocks)
        print(f"After shrink_to_min: lambda_max={opt.lambda_max()} avg_lambda={S/P:.3f}")
        global_floor = max(global_floor, lambda_floor(opt.blocks, v))

    # One loose 1-opt pass (slightly relaxed) to open the landscape
    loose_cap = None if args.forbid_above < 0 else max(3, global_floor)
    print("Loose local search pass...")
    opt.local_search(passes=max(1, args.passes//3), forbid_above=loose_cap, greedy_trials=args.greedy_trials, k_min_size=min_k_size)

    # Clamp and finish local search strictly
    explicit_cap = None if args.forbid_above < 0 else args.forbid_above
    forbid = None if explicit_cap is None else max(explicit_cap, global_floor)
    print("Strict local search pass...")
    opt.local_search(passes=max(1, args.passes - max(1, args.passes//3)), forbid_above=forbid, greedy_trials=args.greedy_trials, k_min_size=min_k_size)

    # DFS rounds over components
    improved = True
    rounds_left = args.group_rounds
    while rounds_left>0 and improved:
        rounds_left -= 1
        lnow = opt.lambda_max()
        global_floor = max(global_floor, lambda_floor(opt.blocks, v))
        if lnow <= global_floor:
            print(f"Reached proven lower bound on lambda_max: {global_floor}.")
            break
        target = max(lnow - 1, global_floor)
        print(f"[round] target lambda_max={target} (floor={global_floor}) ...")

        # quick kicks on a few offenders
        offenders = [p for p,c in enumerate(opt.pair_count) if c==lnow]
        random.shuffle(offenders)
        kicked=False
        for p0 in offenders[:8]:
            if opt.two_block_kick(p0, target=target, k_min_size=min_k_size, rng=rng):
                kicked=True
                break
        if kicked:
            print("  [kick] applied quick offender shrink.")
            continue

        # component-wise DFS with time slicing
        comps = opt.offender_components()
        if not comps:
            improved = False
            break
        per_round_deadline = time.time() + args.group_time
        improved_this_round=False
        for (B_idxs, Pairs) in comps:
            if time.time() > per_round_deadline: break
            ok = opt.reduce_component(B_idxs, target=target, time_limit=max(0.5, args.group_time/len(comps)),
                                      candidates_per_block=min(args.group_cands, 60),
                                      k_min_size=min_k_size, rng=rng)
            if ok:
                print(f"  [component] improved over {len(B_idxs)} blocks.")
                improved_this_round=True
                break
        if not improved_this_round:
            # prep board: quick shrink + tiny strict 1-opt
            if opt.shrink_one_vertex_pass(k_min_size=min_k_size, cap=target, max_sweeps=1):
                print("  [shrink] applied single-vertex shrink.")
                opt.local_search(passes=2, forbid_above=target, greedy_trials=1, k_min_size=min_k_size)
                improved=True
            else:
                improved=False

    print("Final    lambda_max:", opt.lambda_max(), "hist:", opt.histogram(), "sumsq:", opt.sumsq())
    outpath = Path(args.outfile or f"rebalance_v{v}_k{k}_min{min_k_size}.txt")
    one_based = (args.out_indexing == "one")
    with outpath.open("w", encoding="utf-8") as f:
        for blk in opt.blocks:
            if one_based: f.write(" ".join(str(x+1) for x in blk) + "\n")
            else:         f.write(" ".join(str(x)   for x in blk) + "\n")
    print("Saved improved cover to", outpath)

if __name__ == "__main__":
    main()
