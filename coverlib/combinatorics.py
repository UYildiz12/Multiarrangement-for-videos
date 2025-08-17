from __future__ import annotations
import math
from typing import Dict, List, Tuple

__all__ = [
    "pair_index", "invert_pair_index", "block_pairs", "schonheim_lb", "histogram"
]

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

def schonheim_lb(v: int, k: int) -> int:
    return math.ceil((v / k) * math.ceil((v - 1) / (k - 1)))

def histogram(counts: List[int]) -> Dict[int,int]:
    h: Dict[int,int] = {}
    for c in counts: h[c] = h.get(c,0) + 1
    return dict(sorted(h.items()))
