from __future__ import annotations
import random, time
from typing import Dict, List, Optional, Set, Tuple
from .combinatorics import block_pairs, invert_pair_index, pair_index, histogram

__all__ = ["CoverOptimizer"]

class CoverOptimizer:
    """Fixed-b cover rebalancer (pure stdlib).
    - Keeps coverage (pair_count >= 1 for all pairs).
    - Improves lexicographically: lambda_max then sumsq.
    - Has 1-opt (coverage-preserving) and a multi-block DFS swap to lower lambda_max.
    """
    def __init__(self, v: int, blocks: List[Tuple[int,...]], seed: int = 12345):
        self.v=v; self.blocks=[tuple(sorted(b)) for b in blocks]; self.k=len(self.blocks[0])
        random.seed(seed)
        self.P = v*(v-1)//2
        self.block_pairs = [block_pairs(b, v) for b in self.blocks]
        self.pair_count = [0]*self.P
        for pp in self.block_pairs:
            for p in pp: self.pair_count[p]+=1
        if min(self.pair_count) < 1:
            raise ValueError("Seed cover does not cover all pairs.")

    def lambda_max(self)->int: return max(self.pair_count)
    def sumsq(self)->int: return sum(c*c for c in self.pair_count)
    def histogram(self)->Dict[int,int]: return histogram(self.pair_count)

    def try_replace_block(self, idx:int, *, forbid_above:Optional[int]=2, greedy_trials:int=1) -> bool:
        v,k = self.v,self.k
        old_block = self.blocks[idx]
        old_pairs = set(self.block_pairs[idx])
        critical = [p for p in old_pairs if self.pair_count[p]==1]
        if not critical: return False
        required: Set[int] = set()
        for p in critical:
            i,j = invert_pair_index(p, v); required.add(i); required.add(j)
        if len(required)>k: return False

        best_eval = (self.lambda_max(), self.sumsq())
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
            if forbid_above is not None and any(self.pair_count[p]+1 > forbid_above for p in added_only): continue

            cur_lmax=self.lambda_max(); cur_sumsq=self.sumsq()
            delta=0
            for p in removed_only: delta += 1 - 2*self.pair_count[p]
            for p in added_only:   delta += 1 + 2*self.pair_count[p]
            new_sumsq = cur_sumsq + delta

            maybe_inc = any(self.pair_count[p]+1 > cur_lmax for p in added_only)
            maybe_dec = any(self.pair_count[p] == cur_lmax for p in removed_only)
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
                if self.try_replace_block(i, forbid_above=forbid_above, greedy_trials=greedy_trials):
                    improved=True
            if not improved: break

    # group DFS (same approach you used)
    def reduce_lmax_group(self, target:int, time_limit:float=15.0, max_pairs_considered:int=20,
                          candidates_per_block:int=100, rng=random) -> bool:
        start = time.time()
        v,k = self.v,self.k
        lmax = self.lambda_max()
        if lmax <= target: return False
        offenders = [p for p,c in enumerate(self.pair_count) if c==lmax]
        rng.shuffle(offenders); offenders = offenders[:max_pairs_considered]
        avoid_hi = {p for p,c in enumerate(self.pair_count) if c>=lmax-1}
        from .combinatorics import block_pairs as bp

        for p0 in offenders:
            if time.time()-start > time_limit: break
            idxs = [i for i,bp_ in enumerate(self.block_pairs) if p0 in bp_]
            if not idxs: continue
            count_out = self.pair_count[:]
            for i in idxs:
                for q in self.block_pairs[i]: count_out[q]-=1
            if any(c > target for c in count_out):
                continue
            critical = {q for q in range(self.P) if count_out[q]==0}

            cand_lists: List[List[Tuple[int,...]]] = []
            cand_pairs: List[List[Set[int]]] = []
            for i in idxs:
                s: Set[Tuple[int,...]] = set(); tries = 0
                while len(s) < candidates_per_block and tries < candidates_per_block*20:
                    tries += 1; S: List[int] = []
                    while len(S) < k:
                        best_x=None; best_sc=None
                        for x in range(v):
                            if x in S: continue
                            sc = 0.0
                            for y in S:
                                q = pair_index(x,y,v)
                                if q in critical: sc += 5.0
                                if q in avoid_hi: sc -= 2.0
                            sc += rng.random()*0.1
                            if best_sc is None or sc>best_sc:
                                best_sc, best_x = sc, x
                        if best_x is None: break
                        S.append(best_x)
                    if len(S)!=k: continue
                    blk = tuple(sorted(S)); pp = set(bp(blk, v))
                    if p0 in pp: continue
                    s.add(blk)
                lst = list(s)
                if not lst:
                    orig = set(self.blocks[i])
                    while len(s) < min(20, candidates_per_block):
                        S = set(orig)
                        if len(S)>=2:
                            S = set(random.sample(list(S), k-2))
                        while len(S) < k:
                            S.add(rng.randrange(v))
                        blk = tuple(sorted(S)); pp = set(bp(blk,v))
                        if p0 in pp: continue
                        s.add(blk)
                    lst = list(s)
                cand_lists.append(lst)
                cand_pairs.append([set(bp(blk,v)) for blk in lst])

            temp = count_out[:]
            critical_list = sorted(list(critical))
            need = {q:1 for q in critical_list}
            cover_pos = {q:set() for q in critical_list}
            for pos in range(len(idxs)):
                for m,pp in enumerate(cand_pairs[pos]):
                    for q in critical_list:
                        if q in pp: cover_pos[q].add(pos)
            if any(len(cover_pos[q])==0 for q in critical_list):
                continue

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
                    ok=True
                    for q in critical_list:
                        if need[q]<=0: continue
                        possible = any( (q in cand_pairs[p2][mm]) for p2 in range(pos, len(idxs)) for mm in range(len(cand_lists[p2])) )
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
