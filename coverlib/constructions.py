"""Deterministic combinatorial constructions for certified schedules.

The base constructors return 2-(v, k, 1) designs.  One-point extension and
truncation turn those exact designs into ideal pair covers on the neighbouring
orders v+1 and v-1 without stochastic search.

Provided constructions:
- Steiner triple systems (k=3) for every admissible v (v = 1 or 3 mod 6):
  Bose construction for v = 6t+3, Heffter difference triples (found by a tiny
  backtracking search) for v = 6t+1.
- Projective planes PG(2, q): v = q^2+q+1, k = q+1, b = v.
- Affine planes AG(2, q): v = q^2, k = q, b = q^2+q.
- Minimum-length one-point extensions with concurrence in {1, 2}.
- Ideal-concurrence one-point truncations for budgeted balanced mode.

Finite fields GF(q) are supported for prime q and for q in {4, 8, 9, 16} via
hardcoded irreducible polynomials, including fields used by transversal inflation.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterator, List, Sequence, Tuple

Block = Tuple[int, ...]


@dataclass(frozen=True)
class ConstructedCover:
    """A deterministic schedule candidate with explicit provenance."""

    source: str
    blocks: Tuple[Block, ...]

# Irreducible polynomials for small prime-power fields, coefficients low->high.
_IRREDUCIBLE: Dict[int, Tuple[int, Tuple[int, ...]]] = {
    4: (2, (1, 1, 1)),       # x^2 + x + 1 over GF(2)
    8: (2, (1, 1, 0, 1)),    # x^3 + x + 1 over GF(2)
    9: (3, (1, 0, 1)),       # x^2 + 1 over GF(3)
    16: (2, (1, 1, 0, 0, 1)),  # x^4 + x + 1 over GF(2)
}


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for d in range(2, int(n ** 0.5) + 1):
        if n % d == 0:
            return False
    return True


class GF:
    """Finite field GF(q) for prime q or q in {4, 8, 9, 16}.

    Elements are integers 0..q-1. For prime powers, the integer encodes the
    polynomial's coefficients in base p (low degree first).
    """

    def __init__(self, q: int):
        if _is_prime(q):
            self.q = q
            self._p = q
            self._deg = 1
        elif q in _IRREDUCIBLE:
            self.q = q
            self._p, self._poly = _IRREDUCIBLE[q]
            self._deg = len(self._poly) - 1
        else:
            raise ValueError(f"GF({q}) is not supported (prime or one of {sorted(_IRREDUCIBLE)})")
        self._inv: Dict[int, int] = {}

    def _coeffs(self, a: int) -> List[int]:
        out = []
        for _ in range(self._deg):
            out.append(a % self._p)
            a //= self._p
        return out

    def _encode(self, coeffs: List[int]) -> int:
        value = 0
        for c in reversed(coeffs):
            value = value * self._p + (c % self._p)
        return value

    def add(self, a: int, b: int) -> int:
        if self._deg == 1:
            return (a + b) % self._p
        ca, cb = self._coeffs(a), self._coeffs(b)
        return self._encode([(x + y) % self._p for x, y in zip(ca, cb)])

    def neg(self, a: int) -> int:
        if self._deg == 1:
            return (-a) % self._p
        return self._encode([(-c) % self._p for c in self._coeffs(a)])

    def mul(self, a: int, b: int) -> int:
        if self._deg == 1:
            return (a * b) % self._p
        ca, cb = self._coeffs(a), self._coeffs(b)
        prod = [0] * (2 * self._deg - 1)
        for i, x in enumerate(ca):
            if not x:
                continue
            for j, y in enumerate(cb):
                prod[i + j] = (prod[i + j] + x * y) % self._p
        # Reduce modulo the irreducible polynomial (monic by construction).
        for top in range(len(prod) - 1, self._deg - 1, -1):
            coef = prod[top]
            if not coef:
                continue
            prod[top] = 0
            shift = top - self._deg
            for i in range(self._deg):
                prod[shift + i] = (prod[shift + i] - coef * self._poly[i]) % self._p
        return self._encode(prod[: self._deg])

    def inv(self, a: int) -> int:
        if a == 0:
            raise ZeroDivisionError("0 has no inverse")
        if self._deg == 1:
            return pow(a, self._p - 2, self._p)
        cached = self._inv.get(a)
        if cached is None:
            for b in range(1, self.q):
                if self.mul(a, b) == 1:
                    cached = b
                    break
            self._inv[a] = cached
        return cached


@lru_cache(maxsize=None)
def _heffter_triples(t: int, v: int) -> Tuple[Tuple[int, int, int], ...]:
    """Partition {1..3t} into triples (a, b, c) with a+b = c or a+b+c = v.

    Solves Heffter's first difference problem by backtracking; instances with
    t <= 16 (v <= 97) are found near-instantly. A solution exists for every
    admissible t.
    """
    available = set(range(1, 3 * t + 1))
    triples: List[Tuple[int, int, int]] = []

    def candidate_pairs(largest: int) -> Iterator[Tuple[int, int]]:
        # Case 1: largest = a + b (direct difference triple).
        for a in range(1, (largest + 1) // 2):
            b = largest - a
            if a in available and b in available:
                yield a, b
        # Case 2: a + b + largest = v (wraparound triple).
        s = v - largest
        for a in range(max(1, s - largest + 1), (s + 1) // 2):
            b = s - a
            if b < largest and a in available and b in available:
                yield a, b

    def extend() -> bool:
        if not available:
            return True
        # Branch on the largest unused difference: it has the fewest
        # completion pairs, which keeps the search tree tiny.
        largest = max(available)
        available.discard(largest)
        for a, b in candidate_pairs(largest):
            available.discard(a)
            available.discard(b)
            triples.append((a, b, largest))
            if extend():
                return True
            triples.pop()
            available.add(a)
            available.add(b)
        available.add(largest)
        return False

    if not extend():
        raise ValueError(f"No Heffter partition found for t={t}")
    return tuple(triples)


def steiner_triple_system(v: int) -> List[Block]:
    """Construct an STS(v): a perfect k=3 schedule with every pair exactly once."""
    if v < 7 or v % 6 not in (1, 3):
        raise ValueError(f"STS({v}) does not exist (need v = 1 or 3 mod 6, v >= 7)")

    blocks: List[Block] = []
    if v % 6 == 3:
        # Bose construction over Z_n x {0,1,2}, n = v/3 odd.
        n = v // 3
        inv2 = (n + 1) // 2

        def point(i: int, j: int) -> int:
            return i + j * n

        for i in range(n):
            blocks.append(tuple(sorted((point(i, 0), point(i, 1), point(i, 2)))))
        for i in range(n):
            for j in range(i + 1, n):
                half = ((i + j) * inv2) % n
                for a in range(3):
                    blocks.append(
                        tuple(sorted((point(i, a), point(j, a), point(half, (a + 1) % 3))))
                    )
    else:
        # v = 6t+1: develop base blocks {0, a, a+b} from Heffter triples mod v.
        t = v // 6
        for a, b, _c in _heffter_triples(t, v):
            for x in range(v):
                blocks.append(tuple(sorted((x, (x + a) % v, (x + a + b) % v))))

    return [tuple(block) for block in sorted(blocks)]


def projective_plane(q: int) -> List[Block]:
    """Construct PG(2, q): v = q^2+q+1 points, lines of size q+1, lambda 1."""
    f = GF(q)

    # Canonical projective points: first nonzero coordinate normalized to 1.
    points: List[Tuple[int, int, int]] = []
    points.extend((1, a, b) for a in range(q) for b in range(q))
    points.extend((0, 1, a) for a in range(q))
    points.append((0, 0, 1))
    index = {p: i for i, p in enumerate(points)}

    blocks: List[Block] = []
    for line in points:  # self-dual: lines use the same canonical triples
        members = [
            index[p]
            for p in points
            if f.add(f.add(f.mul(line[0], p[0]), f.mul(line[1], p[1])), f.mul(line[2], p[2])) == 0
        ]
        blocks.append(tuple(sorted(members)))
    return sorted(blocks)


def affine_plane(q: int) -> List[Block]:
    """Construct AG(2, q): v = q^2 points, lines of size q, lambda 1."""
    f = GF(q)

    def point(x: int, y: int) -> int:
        return x * q + y

    blocks: List[Block] = []
    for a in range(q):
        for b in range(q):
            blocks.append(tuple(sorted(point(x, f.add(f.mul(a, x), b)) for x in range(q))))
    for c in range(q):
        blocks.append(tuple(sorted(point(c, y) for y in range(q))))
    return sorted(blocks)


def exact_design(v: int, k: int) -> List[Block] | None:
    """Return a perfect 2-(v, k, 1) design for (v, k) if one is constructible.

    Returns None when no supported construction matches; never raises for
    out-of-family parameters.
    """
    try:
        if k == 3 and v >= 7 and v % 6 in (1, 3):
            return steiner_triple_system(v)
        q = k - 1
        if q >= 2 and v == q * q + q + 1 and (_is_prime(q) or q in _IRREDUCIBLE):
            return projective_plane(q)
        q = k
        if q >= 3 and v == q * q and (_is_prime(q) or q in _IRREDUCIBLE):
            return affine_plane(q)
    except Exception:
        return None
    return None


def _verify_steiner_design(u: int, k: int, blocks: Sequence[Sequence[int]]) -> List[Block]:
    normalized = [tuple(sorted(int(item) for item in block)) for block in blocks]
    if any(len(block) != k or len(set(block)) != k for block in normalized):
        raise ValueError("base design contains an invalid block")
    if any(item < 0 or item >= u for block in normalized for item in block):
        raise ValueError("base design contains an out-of-range point")
    if len(set(normalized)) != len(normalized):
        raise ValueError("base design contains repeated blocks")
    counts: Dict[Tuple[int, int], int] = {}
    for block in normalized:
        for pair in itertools.combinations(block, 2):
            counts[pair] = counts.get(pair, 0) + 1
    if len(counts) != math.comb(u, 2) or set(counts.values()) != {1}:
        raise ValueError("base blocks are not a Steiner 2-design")
    return normalized


def one_point_extension(
    u: int,
    k: int,
    base_blocks: Sequence[Sequence[int]],
) -> List[Block]:
    """Extend a 2-(u, k, 1) design to an ideal minimum cover on u+1 points.

    The new point is ``u``.  The distinguished old point is ``u-1``; the
    remaining points are partitioned deterministically into groups of size
    ``k-1``.  The construction is valid when the replication number
    ``r=(u-1)/(k-1)`` is at least ``k-2``.
    """
    design = _verify_steiner_design(u, k, base_blocks)
    if (u - 1) % (k - 1):
        raise ValueError("base design has a nonintegral replication number")
    replication = (u - 1) // (k - 1)
    if replication < k - 2:
        raise ValueError("one-point extension needs r >= k-2")

    distinguished = u - 1
    new_point = u
    remaining = list(range(u - 1))
    groups = [
        remaining[index * (k - 1) : (index + 1) * (k - 1)]
        for index in range(replication)
    ]
    if any(len(group) != k - 1 for group in groups):
        raise ValueError("failed to partition the old points")

    added = [tuple(sorted(group + [new_point])) for group in groups]
    representatives = [groups[index][0] for index in range(k - 2)]
    added.append(tuple(sorted([distinguished, new_point] + representatives)))
    return sorted(design + added)


def one_point_truncation(
    u: int,
    k: int,
    base_blocks: Sequence[Sequence[int]],
) -> List[Block]:
    """Remove one point from a 2-(u, k, 1) design and cyclically pad its groups.

    The result is a cover on ``u-1`` points with the original number of trials,
    ideal pair concurrence at that trial count, and ideal item replication.
    """
    design = _verify_steiner_design(u, k, base_blocks)
    removed_point = u - 1
    groups = [
        tuple(item for item in block if item != removed_point)
        for block in design
        if removed_point in block
    ]
    groups = sorted(groups)
    replication = len(groups)
    if replication < 3:
        raise ValueError("truncation needs at least three groups to avoid a two-cycle")
    if any(len(group) != k - 1 for group in groups):
        raise ValueError("invalid truncated group")
    flattened = [item for group in groups for item in group]
    if sorted(flattened) != list(range(u - 1)):
        raise ValueError("blocks through the removed point do not partition the remainder")

    kept = [block for block in design if removed_point not in block]
    representatives = [group[0] for group in groups]
    padded = [
        tuple(sorted(group + (representatives[(index + 1) % replication],)))
        for index, group in enumerate(groups)
    ]
    return sorted(kept + padded)


def one_point_extension_design(v: int, k: int) -> List[Block] | None:
    """Return a certified extension candidate for target parameters ``(v, k)``."""
    if v <= k:
        return None
    base = exact_design(v - 1, k)
    if base is None:
        return None
    try:
        return one_point_extension(v - 1, k, base)
    except ValueError:
        return None


def one_point_truncation_design(v: int, k: int) -> List[Block] | None:
    """Return an ideal-concurrence truncation candidate for ``(v, k)``."""
    base = exact_design(v + 1, k)
    if base is None:
        return None
    try:
        return one_point_truncation(v + 1, k, base)
    except ValueError:
        return None


def structured_cover_candidates(v: int, k: int) -> List[ConstructedCover]:
    """Return all supported deterministic candidates, without discarding ties."""
    candidates: List[ConstructedCover] = []
    exact = exact_design(v, k)
    if exact is not None:
        candidates.append(ConstructedCover("exact_design", tuple(exact)))
    extension = one_point_extension_design(v, k)
    if extension is not None:
        candidates.append(ConstructedCover("one_point_extension", tuple(extension)))
    truncation = one_point_truncation_design(v, k)
    if truncation is not None:
        candidates.append(ConstructedCover("one_point_truncation", tuple(truncation)))

    unique: List[ConstructedCover] = []
    seen = set()
    for candidate in candidates:
        identity = tuple(sorted(candidate.blocks))
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(candidate)
    return unique


def certified_compact_cover(v: int, k: int) -> ConstructedCover | None:
    """Return a deterministic candidate that attains the Schönheim bound."""
    replication_minimum = (v + k - 3) // (k - 1)
    lower_bound = (v * replication_minimum + k - 1) // k
    for candidate in structured_cover_candidates(v, k):
        if candidate.source == "one_point_truncation":
            continue
        if len(candidate.blocks) == lower_bound:
            return candidate
    return None


def constructible_designs(
    max_v: int = 100,
    min_k: int = 3,
) -> Iterator[Tuple[Tuple[int, int], List[Block]]]:
    """Yield ((v, k), blocks) for every supported perfect design with v <= max_v."""
    supported_q = [q for q in range(2, 10) if _is_prime(q) or q in _IRREDUCIBLE]

    for v in range(7, max_v + 1):
        if v % 6 in (1, 3) and 3 >= min_k:
            yield (v, 3), steiner_triple_system(v)
    for q in supported_q:
        v = q * q + q + 1
        if v <= max_v and q + 1 >= min_k:
            yield (v, q + 1), projective_plane(q)
    for q in supported_q:
        v = q * q
        if v <= max_v and q >= min_k:
            yield (v, q), affine_plane(q)
