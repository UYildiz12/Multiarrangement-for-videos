"""A table-free pair cover obtained by puncturing and repairing transversals.

For prime q == 3 (mod 4), q >= 7, this constructs (q-1)^2 items in blocks
of size q-1, using q^2+q-2 blocks. Pair concurrence is at most two and
item frequency is uniformly q+2. This is an incumbent construction, not a
claim of minimum trial count or global balanced optimality.
"""
from __future__ import annotations

import math
from numbers import Integral
from typing import Optional

from .constructions import ConstructedCover


def _prime(q: int) -> bool:
    return q >= 2 and all(q % d for d in range(2, math.isqrt(q)+1))


def repaired_transversal(q: int) -> ConstructedCover:
    """Construct the proven prime-field family with zero-based item IDs.

    Group g contains the nonzero field values y=1,...,q-1. Their item ID
    is g*(q-1)+(y-1). Lines y=m*g+c are punctured at y=0. A missing
    value in group g is replaced by m. Finally each group is a full block.
    """
    if isinstance(q, bool) or not isinstance(q, Integral):
        raise ValueError('q must be an integer')
    q = int(q)
    if q < 7 or q % 4 != 3 or not _prime(q):
        raise ValueError('this constructor requires a prime q >= 7 with q % 4 == 3')
    k = q-1
    blocks = []
    for m in range(q):
        for c in range(q):
            if m == 0 and c == 0:
                continue
            block = []
            for g in range(k):
                y = (m*g+c) % q
                if y == 0:
                    # A nonzero slope has at most one root; m != 0 here.
                    y = m
                block.append(g*k+y-1)
            blocks.append(tuple(sorted(block)))
    blocks.extend(tuple(range(g*k,(g+1)*k)) for g in range(k))
    return ConstructedCover(source=f'punctured_repaired_TD_prime_{q}',blocks=tuple(blocks))


def repaired_transversal_cover(v: int, k: int) -> Optional[ConstructedCover]:
    """Return the family when applicable; unsupported parameters return None."""
    if isinstance(v,bool) or isinstance(k,bool) or not isinstance(v,Integral) or not isinstance(k,Integral):
        return None
    if k < 6 or v != k*k:
        return None
    q = int(k)+1
    if q % 4 != 3 or not _prime(q):
        return None
    return repaired_transversal(q)


# Independently verified local refinement at q=11. Rows index slope m=1..10;
# columns index the retained root group g=0..9. Zero marks a deleted line.
# These are instance-specific incumbent data, not a formula for other orders.
_REFINED_11_FILLERS = (
    (0, 0, 3, 5, 2, 10, 3, 5, 9, 3),
    (1, 1, 2, 2, 3, 4, 5, 7, 4, 8),
    (2, 1, 1, 2, 4, 5, 5, 7, 8, 8),
    (10, 5, 1, 3, 3, 5, 6, 6, 7, 9),
    (9, 10, 2, 2, 4, 4, 6, 6, 1, 8),
    (10, 2, 2, 3, 4, 5, 5, 8, 7, 8),
    (8, 1, 1, 3, 4, 4, 6, 6, 7, 9),
    (10, 3, 2, 7, 3, 5, 8, 7, 7, 9),
    (10, 9, 5, 3, 1, 4, 5, 6, 8, 9),
    (3, 1, 1, 2, 3, 5, 6, 7, 8, 10),
)


def locally_refined_transversal_cover(v: int, k: int) -> Optional[ConstructedCover]:
    """Return the verified 128-trial (100,10) incumbent, when applicable.

    The affine fragments and ten full group blocks are retained, lines (1,0)
    and (1,10) are deleted, and each remaining missing point uses its recorded
    own-group filler. All4950 pairs are covered with concurrence at most two.
    An independently verified two-trial exchange improves the item profile
    to12:55,13:27,14:1,15:17. Neither minimum count nor the full balanced
    optimum is proved. No file reads or solver are needed.
    """
    if isinstance(v, bool) or isinstance(k, bool) or not isinstance(v, Integral) or not isinstance(k, Integral):
        return None
    if (v, k) != (100, 10):
        return None
    q=11
    blocks=[]
    for m in range(q):
        for c in range(q):
            if (m,c) in {(0,0),(1,0),(1,10)}:
                continue
            block=[]
            for g in range(k):
                y=(m*g+c)%q
                if y==0:
                    y=_REFINED_11_FILLERS[m-1][g]
                block.append(g*k+y-1)
            blocks.append(tuple(sorted(block)))
    blocks.extend(tuple(range(g*k,(g+1)*k)) for g in range(k))
    # Exact local two-trial exchange. The fragments above remain the seed;
    # these explicit replacements are independently recounted instance data.
    exchanges = (
        ((4,14,24,34,44,54,64,74,84,94), (4,5,14,24,34,44,64,74,84,94)),
        ((8,15,22,36,47,54,61,79,86,93), (8,15,22,47,54,61,79,84,86,93)),
    )
    for before, after in exchanges:
        blocks.remove(before)
        blocks.append(after)
    return ConstructedCover(source='locally_refined_affine_11_two_trial_exchange',blocks=tuple(sorted(blocks)))
