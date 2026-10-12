"""Bounded direct minimum triple covers, independent of caches and search.

Every integer order v>=3 is supported: direct STS for admissible orders;
adjoin-point covers for v=2 or4 mod6; explicit3-GDD6^n plus a five/six-point
hole for all remaining orders, including three finite seeds at v17/18.

For v=5mod6, minimum count requires cap3; one extra block permits the
globally minimal cap2 pair profile. Candidates carry construction provenance,
not proof labels; the general engine validates them and scopes their proofs.
The direct auxiliary STS formulas are Bose and half-idempotent Skolem; there
is no Heffter backtracking, table lookup or optional numerical dependency.

The adjoin-point and simple-padding distinction are documented in Demirkale,
Donovan and Grannell, Anti-Pasch optimal coverings with triples, Section3,
and Lindner, Rodger and Meszka, AJC68(2)(2017),276-284, pp277,281.
"""
from __future__ import annotations

import math
import time

from .constructions import ConstructedCover


class DirectTripleDeadline(TimeoutError):
    """Cooperative construction deadline was exhausted."""


class DirectTripleResource(ValueError):
    """Declared pair/output resource limit cannot support assembly."""


def direct_triple_supported(v):
    """Whether this module implements a direct cover for this integer order."""
    if isinstance(v, bool) or not isinstance(v, int) or v < 3:
        return False
    return True


def _direct_sts(order, check):
    """Direct admissible STS with periodic checks, using level-major labels."""
    check()
    rows = []

    def add(*row):
        if len(rows) % 128 == 0:
            check()
        rows.append(tuple(sorted(row)))

    if order % 6 == 3:
        m = order // 3
        point = lambda x, level: (level % 3) * m + x
        inverse_two = (m + 1) // 2
        for x in range(m):
            add(point(x, 0), point(x, 1), point(x, 2))
        for x in range(m):
            for y in range(x + 1, m):
                mean = (x + y) * inverse_two % m
                for level in range(3):
                    add(point(x, level), point(y, level), point(mean, level + 1))
    elif order >= 7 and order % 6 == 1:
        t = (order - 1) // 6
        m = 2 * t
        point = lambda x, level: (level % 3) * m + x
        infinity = 3 * m
        for x in range(t):
            add(point(x, 0), point(x, 1), point(x, 2))
        for x in range(m):
            for y in range(x + 1, m):
                s = (x + y) % m
                q = s // 2 if s % 2 == 0 else (s + m - 1) // 2
                for level in range(3):
                    add(point(x, level), point(y, level), point(q, level + 1))
        for x in range(t):
            for level in range(3):
                add(infinity, point(x + t, level), point(x, level + 1))
    else:
        raise ValueError("auxiliary STS order must be1 or3 mod6 and at least3")
    check()
    if len(rows) != order * (order - 1) // 6:
        raise AssertionError("direct STS count mismatch")
    return rows


def _factors():
    return tuple(((5, t), ((t + 1) % 5, (t - 1) % 5),
                  ((t + 2) % 5, (t - 2) % 5)) for t in range(5))


def _gdd_six(n, check):
    """Cross-group triples for every n>=0 except the finite seeded n=2."""
    from .gdd_six import gdd_six
    return gdd_six(n, check, _direct_sts)


def _canonical(source, rows, expected_count, check):
    check()
    blocks = tuple(sorted(rows))
    if len(blocks) != expected_count or len(set(blocks)) != expected_count:
        raise AssertionError("direct cover has repeated blocks or incorrect count")
    check()
    return ConstructedCover(source, blocks)


def direct_triple_candidates(v, *, max_blocks=None, deadline,
                             max_pair_entries, max_output_cells):
    """Return canonical complete candidates within a declared count limit.

    Unsupported valid orders return an empty list. Resource preflight uses
    P=choose(v,2) and a conservative peak triple-cell estimate including the
    auxiliary STS, common core and all returned covers. Limits must be finite
    nonnegative integers. Assembly checks perf_counter periodically; canonical
    sorting and mandatory caller verification are cooperative, not a hard
    process wall-clock guarantee. No partial candidate is returned on expiry.
    """
    if isinstance(v, bool) or not isinstance(v, int) or v < 3:
        raise ValueError("direct triple covers require integer v>=3")
    if max_blocks is not None and (isinstance(max_blocks, bool) or not isinstance(max_blocks, int) or max_blocks < 0):
        raise ValueError("max_blocks must be a nonnegative integer or None")
    for label, value in (("max_pair_entries", max_pair_entries), ("max_output_cells", max_output_cells)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{label} must be a finite nonnegative integer")
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not math.isfinite(deadline):
        raise ValueError("deadline must be a finite monotonic timestamp")
    if not direct_triple_supported(v):
        return []

    def check():
        if time.perf_counter() >= deadline:
            raise DirectTripleDeadline("deadline reached during direct triple construction")

    odd = v % 6 == 5
    b0 = (v * (v // 2) + 2) // 3
    # ceil((v-1)/2) equals v//2 for both odd and even orders.
    counts = [b0] + ([b0 + 1] if odd else [])
    eligible = [b for b in counts if max_blocks is None or b <= max_blocks]
    if not eligible:
        return []
    if v % 6 in (1, 3):
        base_count = b0
        core_count = b0
    elif v % 6 in (2, 4):
        base_count = (v - 1) * (v - 2) // 6
        core_count = b0
    else:
        n = (v - (5 if odd else 6)) // 6
        # All routes: STS auxiliaries <=1.5n^2 triples; affine cached
        # ingredients plus one live STS <2n^2+200n triples. This conservative
        # bound includes Jiang pairs and the finite PBD14/seed storage.
        # The fixed200-triangle allowance also covers tiny n=0/1 local
        # templates, all finite-seed constants, and the19-block PBD14.
        base_count = 2 * n * n + 200 * n + 200
        core_count = b0 - (4 if odd else 6)
    estimated_cells = 3 * (base_count + core_count + sum(eligible))
    if v * (v - 1) // 2 > max_pair_entries or estimated_cells > max_output_cells:
        raise DirectTripleResource("direct triple pair storage or conservative peak output cells exceed limits")
    check()

    if v % 6 in (1, 3):
        return [_canonical("triple_direct_sts", _direct_sts(v, check), b0, check)]
    if v in (17, 18):
        from .triple_seeds import V17_COMPACT, V17_BALANCED, V18
        if v == 18:
            return [_canonical("triple_gdd_six_hole", V18, b0, check)]
        return [_canonical("triple_gdd_five_hole_compact" if b == b0 else
                           "triple_gdd_five_hole_balanced",
                           V17_COMPACT if b == b0 else V17_BALANCED, b, check)
                for b in eligible]
    if v % 6 in (2, 4):
        rows = _direct_sts(v - 1, check)
        matching = [tuple(x for x in row if x != 0) for row in rows if 0 in row]
        a, b = matching[0]
        rows.extend(tuple(sorted((v - 1, x, y))) for x, y in matching[1:])
        rows.extend((tuple(sorted((v - 1, 0, a))), tuple(sorted((v - 1, 0, b)))))
        return [_canonical("triple_adjoin_sts", rows, b0, check)]

    rows, groups = _gdd_six(n, check)
    hole = tuple(range(6 * n, v))
    factors = _factors()
    for group_index, group in enumerate(groups):
        if group_index % 128 == 0:
            check()
        for point, factor in zip(hole[:5], factors):
            rows.extend(tuple(sorted((point, group[x], group[y]))) for x, y in factor)
        if not odd:
            rows.extend(tuple(sorted((hole[5], group[x], group[y]))) for x, y in factors[0])
    if odd:
        answer = []
        local = {b0: ((0, 1, 2), (0, 1, 3), (0, 1, 4), (2, 3, 4)),
                 b0 + 1: ((0, 1, 2), (0, 1, 3), (0, 3, 4), (1, 2, 4), (2, 3, 4))}
        for b in eligible:
            source = "triple_gdd_five_hole_compact" if b == b0 else "triple_gdd_five_hole_balanced"
            hole_rows = [tuple(hole[x] for x in block) for block in local[b]]
            answer.append(_canonical(source, rows + hole_rows, b, check))
        return answer
    local = ((0, 1, 2), (0, 1, 3), (0, 4, 5), (1, 4, 5), (2, 3, 4), (2, 3, 5))
    rows.extend(tuple(hole[x] for x in block) for block in local)
    return [_canonical("triple_gdd_six_hole", rows, b0, check)]
