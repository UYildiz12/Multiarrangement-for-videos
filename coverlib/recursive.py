"""Transversal inflation and reuse of certified Steiner ingredients.

These are standard design-theory constructions, with independently validated
ingredients and outputs. Unsupported field factors do not imply nonexistence.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

from .certificates import certify_schedule
from .constructions import ConstructedCover, GF, one_point_extension, one_point_truncation

Block = Tuple[int, ...]


@lru_cache(maxsize=None)
def transversal_factors(k: int, n: int) -> Optional[Tuple[int, ...]]:
    """Find supported finite-field factors of n admitting TD(k, factor)."""
    if not isinstance(k, int) or not isinstance(n, int) or k < 2 or n < 2:
        return None
    try:
        GF(n)
        if k <= n + 1:
            return (n,)
    except ValueError:
        pass
    for q in range(2, n):
        if n % q or k > q + 1:
            continue
        try:
            GF(q)
        except ValueError:
            continue
        rest = transversal_factors(k, n // q)
        if rest is not None:
            return (q,) + rest
    return None


@lru_cache(maxsize=None)
def transversal_design(k: int, n: int) -> Tuple[Block, ...]:
    """Return n^2 rows of TD(k,n), encoded by within-group item coordinates.

    Each row has k entries in range(n), one per group. Every ordered pair
    occurs exactly once in every two-column projection. Field rows are
    (x, y, y+x, y+2x, ...), with all arithmetic in the field; products use
    mixed-radix coordinates, not arithmetic modulo a composite integer.
    """
    factors = transversal_factors(k, n)
    if factors is None:
        raise ValueError(f"no supported transversal construction for TD({k},{n})")
    rows = [(0,) * k]
    for q in factors:
        field = GF(q)
        factor_rows = [
            tuple([x] + [field.add(y, field.mul(slope, x)) for slope in range(k - 1)])
            for x in range(q) for y in range(q)
        ]
        rows = [
            tuple(a * q + b for a, b in zip(old, new))
            for old in rows for new in factor_rows
        ]
    return tuple(rows)


def inflate_cover(
    g: int,
    n: int,
    k: int,
    outer_blocks: Sequence[Sequence[int]],
    inner_blocks: Sequence[Sequence[int]],
) -> List[Block]:
    """Cover g*n items using b_outer*n^2 + g*b_inner blocks of size k.

    The outer cover determines group combinations. Transversals cover pairs
    between groups; an inner cover in each group covers its internal pairs.
    Between-group concurrence equals the corresponding outer concurrence.
    Each item's frequency is n*r_outer[group] + r_inner[item].
    """
    outer = certify_schedule(g, k, outer_blocks, source="inflation_outer")
    inner = certify_schedule(n, k, inner_blocks, source="inflation_inner")
    if not outer.complete or not inner.complete:
        raise ValueError("inflation ingredients must have complete pair coverage")
    rows = transversal_design(k, n)
    blocks = [
        tuple(group * n + item for group, item in zip(sorted(block), row))
        for block in outer_blocks for row in rows
    ]
    blocks.extend(
        tuple(group * n + int(item) for item in sorted(block))
        for group in range(g) for block in inner_blocks
    )
    result = sorted(blocks)
    certificate = certify_schedule(g * n, k, result, source="transversal_inflation")
    if not certificate.complete or len(result) != outer.b * n * n + g * inner.b:
        raise AssertionError("transversal inflation failed independent validation")
    return result


def steiner_neighbor_candidates(
    v: int, k: int, blocks: Sequence[Sequence[int]]
) -> Tuple[Tuple[int, ConstructedCover], ...]:
    """Extend/truncate any verified Steiner 2-design, including cached designs."""
    certificate = certify_schedule(v, k, blocks, source="steiner_ingredient")
    if not certificate.complete or certificate.lambda_max != 1 or v <= k:
        return tuple()
    candidates = []
    for offset, name, constructor in (
        (1, "extension", one_point_extension),
        (-1, "truncation", one_point_truncation),
    ):
        try:
            result = constructor(v, k, blocks)
        except ValueError:
            continue
        source = f"cached_steiner_{name}_{v}_{certificate.schedule_hash[:12]}"
        verified = certify_schedule(v + offset, k, result, source=source)
        if not verified.complete:
            raise AssertionError("Steiner neighbor construction failed validation")
        candidates.append((v + offset, ConstructedCover(source, tuple(result))))
    return tuple(candidates)
