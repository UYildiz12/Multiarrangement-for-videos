from __future__ import annotations
import random
from typing import List, Optional, Set, Tuple
from .combinatorics import block_pairs, invert_pair_index, pair_index

__all__ = ["repair_to_coverage", "greedy_sample_block"]

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
    return best_blk  # type: ignore

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
        blocks[idx] = None  # type: ignore
    return [b for b in blocks if b is not None]

# local helper to avoid circular import
from .combinatorics import block_pairs as _bp

def coverage_from_blocks(v: int, blocks: List[Tuple[int,...]]):
    P = v*(v-1)//2
    counts = [0]*P
    bpairs = [_bp(b, v) for b in blocks]
    for pp in bpairs:
        for p in pp: counts[p]+=1
    return counts, bpairs
