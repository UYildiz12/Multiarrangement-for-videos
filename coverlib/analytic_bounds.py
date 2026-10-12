"""Exact necessary bounds from published theory and item-degree identities.

These bounds exclude covers or lower-bound their pair objective. Feasibility
of a degree graph alone never certifies that it decomposes into k-blocks.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Tuple


def _parameters(v: int, k: int) -> None:
    if not (isinstance(v, int) and isinstance(k, int) and 2 <= k <= v):
        raise ValueError("need integer 2 <= k <= v")


def horsley_trial_lower_bound(v: int, k: int) -> int:
    """Horsley (2016), Theorem 1, for pair coverage demand one.

    Return zero when the theorem's strict hypothesis does not apply. Source:
    https://arxiv.org/html/1409.0485v3 . Its lambda denotes coverage demand,
    not the maximum observed pair concurrence.
    """
    _parameters(v, k)
    r = (v + k - 3) // (k - 1)
    d = r * (k - 1) - (v - 1)
    if 3 <= k < v and d < r - 1:
        return (v * (r + 1) + k) // (k + 1)
    return 0


def rational_sqrt_lower(value: Fraction, scale: int = 10**12) -> Fraction:
    """Guaranteed downward square-root bound using integer arithmetic only."""
    if value < 0 or not isinstance(scale, int) or scale < 1:
        raise ValueError("need nonnegative value and positive integer scale")
    return Fraction(math.isqrt(value.numerator * scale**2 // value.denominator), scale)


def horsley_trial_bounds(v: int, k: int) -> Tuple[Tuple[str, int], ...]:
    """All implemented Horsley covering bounds, with checked hypotheses.

    Theorems 1, 11, 14(a,b) use exact rationals. Theorem 14(c) uses a directed
    rational square-root lower bound; this can weaken but cannot overstate the
    published bound because CB is increasing in beta when alpha=1 and r<k.
    """
    _parameters(v, k)
    first = horsley_trial_lower_bound(v, k)
    result = [("HORSLEY_THEOREM_1", first)] if first else []
    r = (v + k - 3) // (k - 1)
    d = r * (k - 1) - (v - 1)
    n = r - 1
    if not (3 <= k < v and r < k):
        return tuple(result)

    def append(reason: str, alpha: Fraction, beta: Fraction) -> None:
        if not alpha >= 2 * beta >= 0:
            raise AssertionError("published parameter hypotheses failed")
        value = (r * v * (alpha - beta) + alpha * v) / (k * (alpha - beta) + 1)
        result.append((reason, -(-value.numerator // value.denominator)))

    if d >= n:
        append("HORSLEY_THEOREM_11", Fraction(n + 1, 2 * d + 2),
               Fraction(n + 1, 2 * (d + k)))
    else:
        append("HORSLEY_THEOREM_14A", 1 - Fraction(d * d, 2 * n * (n + 1)),
               Fraction(n + 2, 2 * (d + k)))
        if 2 * d >= n and d * (d + k - 1) < n * (n + 1):
            append("HORSLEY_THEOREM_14B", Fraction(1),
                   1 - Fraction(d * (d + k - 1), n * (n + 1)))
        if 2 * d < n and 4 * (n + 1) * (n + 2) * (n - d) > d * (d + k)**2:
            root = rational_sqrt_lower(Fraction(d * (n + 2), (n + 1) * (n - d)))
            beta = root - Fraction(d * (d + k), 2 * (n + 1) * (n - d))
            if beta >= 0:
                append("HORSLEY_THEOREM_14C_RATIONAL_LOWER", Fraction(1), beta)
    return tuple(result)


def plane_pair_obstruction(v: int, k: int) -> Optional[str]:
    """Published nonexistence excluding affine/projective cap-one covers.

    At v=k squared such a cover is an affine plane of order k, completing
    to a projective plane. At v=k*k-k+1 it is a projective plane of order k-1.
    Bruck--Ryser (1949), Theorem 1, supplies the general
    square-free prime obstruction; Lam--Thiel--Swiercz (1989) excludes k=10,
    independently confirmed by Bright et al. (AAAI 2021, SAT certificates).
    This package relies on those published results; it does not rerun their
    large external certificate verification.
    No absence of a prime-power construction is treated as nonexistence.
    """
    _parameters(v, k)
    if v == k * k:
        order = k
    elif v == k * k - k + 1:
        order = k - 1
    else:
        return None
    if order == 10:
        return "PROJECTIVE_PLANE_LAM_ORDER_10"
    if order % 4 not in (1, 2):
        return None
    remaining = order
    divisor = 2
    while divisor * divisor <= remaining:
        exponent = 0
        while remaining % divisor == 0:
            remaining //= divisor
            exponent += 1
        if exponent % 2 and divisor % 4 == 3:
            return "PROJECTIVE_PLANE_BRUCK_RYSER"
        divisor += 1
    if remaining % 4 == 3:
        return "PROJECTIVE_PLANE_BRUCK_RYSER"
    return None


def projective_failed_design_obstruction(v: int, k: int) -> Optional[str]:
    """Sane (1991), Theorem 3.1: unrestricted one-extra projective cover.

    A cover on v=k*k-k+1 with v+1 k-blocks either has a block whose deletion
    leaves a projective plane, or is a projective failed design. The cited
    theorem excludes the latter WITHOUT a pair-cap assumption. A published
    plane obstruction therefore excludes this count for every complete cover.
    https://combinatorialpress.com/jcmcc-articles/volume-009/
        on-affine-and-projective-failed-designs/
    """
    _parameters(v, k)
    if v == k * k - k + 1 and plane_pair_obstruction(v, k):
        return "SANE_PROJECTIVE_FAILED_DESIGN"
    return None


def affine_one_extra_lift_hasse_primes(k: int) -> Tuple[int, ...]:
    """Exact rational obstruction to the forced triangular permutation lift.

    This helper is conditional on the one-extra affine cap-two structure:
    k=C(n,2), quotient size V=C(n+1,2)+1, group size g=C(n-1,2).
    A hypothetical square quotient T makes A=(k-g)I+gJ=T*T^T congruent to I.
    The lifted Gram splits as k*W plus g*A, while I splits as W plus g*I,
    with W=(I_(g-1)+J_(g-1)) repeated V times and det(W)=g**V.
    N=V*(g-1) is even in this family, so the determinant gain k**N is a
    square and the full-sum cross term disappears. The remaining Hasse ratio
    is (k,k)_p**C(N,2) * (k,g**V)_p**(N-1). A negative place excludes the
    lift; an empty result does NOT construct a lift or covering.

    This is a specialized exact replay of the classical rational Gram / Bose-
    Connor obstruction, using epsilon(D)=product_(i<j)(d_i,d_j), including p=2.
    It is NEVER an unrestricted covering bound or a generic SGDD criterion.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 3:
        raise ValueError("need triangular integer k >= 3")
    root = math.isqrt(8 * k + 1)
    n = (root + 1) // 2
    if root * root != 8 * k + 1 or n * (n - 1) // 2 != k:
        raise ValueError("need triangular integer k >= 3")
    groups = n * (n + 1) // 2 + 1
    group_size = (n - 1) * (n - 2) // 2
    dimension = groups * (group_size - 1)
    if dimension % 2:
        raise AssertionError("triangular-family determinant gain must be square")

    def factors(value: int) -> set[int]:
        result = set()
        divisor = 2
        while divisor * divisor <= value:
            if value % divisor == 0:
                result.add(divisor)
                while value % divisor == 0:
                    value //= divisor
            divisor = 3 if divisor == 2 else divisor + 2
        if value > 1:
            result.add(value)
        return result

    def symbol(a: int, b: int, prime: int) -> int:
        alpha = beta = 0
        while a % prime == 0:
            a //= prime
            alpha += 1
        while b % prime == 0:
            b //= prime
            beta += 1
        if prime == 2:
            u, z = a % 8, b % 8
            exponent = ((u - 1) // 2) * ((z - 1) // 2)
            exponent += alpha * ((z * z - 1) // 8) + beta * ((u * u - 1) // 8)
        else:
            exponent = alpha * beta * ((prime - 1) // 2)
            exponent += beta * (pow(a % prime, (prime - 1) // 2, prime) == prime - 1)
            exponent += alpha * (pow(b % prime, (prime - 1) // 2, prime) == prime - 1)
        return -1 if exponent % 2 else 1

    negative = []
    for prime in sorted({2} | factors(k) | factors(group_size)):
        ratio = 1
        if (dimension * (dimension - 1) // 2) % 2:
            ratio *= symbol(k, k, prime)
        if (dimension - 1) % 2 and groups % 2:
            ratio *= symbol(k, group_size, prime)
        if ratio < 0:
            negative.append(prime)
    # At every other odd prime both arguments are units, and at infinity
    # they are positive, so all omitted local ratios are exactly +1.
    return tuple(negative)


def one_extra_cap_two_obstruction(v: int, k: int) -> Optional[str]:
    """Verified cap-conditioned affine/projective one-extra exclusions.

    This is NEVER an unrestricted count bound. Evidence: independently checked
    near-plane structure theorem SHA256 a588b093fc839feb87f519baa011106d11dcad
    4499d9186bc5d61405236a27a8. The affine no-all-high branch requires
    k=C(n,2) and a 2-(C(n+1,2)+1,n+1,2) biplane permutation lift.
    """
    _parameters(v, k)
    if not plane_pair_obstruction(v, k):
        return None  # A plane plus an extra block remains a valid counterexample.
    if v == k * k - k + 1:
        return "PROJECTIVE_CAP_TWO_ONE_EXTRA_FORCES_PLANE"
    if v != k * k:
        return None
    root = math.isqrt(8 * k + 1)
    if root * root != 8 * k + 1 or root % 2 != 1:
        return "AFFINE_CAP_TWO_ONE_EXTRA_NONTRIANGULAR"
    n = (root + 1) // 2
    if n < 3 or n * (n - 1) // 2 != k:
        return "AFFINE_CAP_TWO_ONE_EXTRA_NONTRIANGULAR"
    if k == 6:
        # Complete rooted 11/5 biplane catalogue, parity-to-C3 reduction, and
        # Eisenstein norm 6**11 obstruction. Independent replay SHA256:
        # f8b8d48a9292bd5eb09e7fe27d86729da8cc29ff3cbf74f9807d7b70012e6007.
        # This excludes the lift, not the existing 2-(11,5,2) biplane itself.
        return "AFFINE_CAP_TWO_ORDER_6_PERMUTATION_LIFT_EISENSTEIN"
    points, order = n * (n + 1) // 2 + 1, n - 1
    if points % 2 == 0:
        if math.isqrt(order) ** 2 != order:
            return "AFFINE_CAP_TWO_BIPLANE_DETERMINANT"
    else:
        target = 2 if points % 4 == 1 else -2
        remaining, divisor = order, 2
        while divisor * divisor <= remaining:
            exponent = 0
            while remaining % divisor == 0:
                remaining //= divisor
                exponent += 1
            if (exponent % 2 and divisor != 2
                    and pow(target % divisor, (divisor - 1) // 2, divisor) == divisor - 1):
                return "AFFINE_CAP_TWO_BIPLANE_CHOWLA_RYSER"
            divisor += 1
        if (remaining > 2
                and pow(target % remaining, (remaining - 1) // 2, remaining) == remaining - 1):
            return "AFFINE_CAP_TWO_BIPLANE_CHOWLA_RYSER"
    if affine_one_extra_lift_hasse_primes(k):
        return "AFFINE_CAP_TWO_PERMUTATION_LIFT_RATIONAL_HASSE"
    return None


def complement_boundary_profiles(
    v: int, k: int, b: int,
) -> Optional[Tuple[Tuple[int, ...], Tuple[int, ...]]]:
    """Forced pair and item profiles for a simple k=v-1 cover at fixed b.

    Three distinct complements give the full compact and any-budget balanced
    optimum. Larger fixed counts remain valid covers and are not rejected.
    """
    _parameters(v, k)
    if not isinstance(b, int) or b < 1:
        raise ValueError("need positive integer b")
    if k != v - 1 or not 3 <= b <= v:
        return None
    pairs = ((b,) * math.comb(v - b, 2)
             + (b - 1,) * (b * (v - b))
             + (b - 2,) * math.comb(b, 2))
    items = (b,) * (v - b) + (b - 1,) * b
    return pairs, items


def is_graphical(degrees: Tuple[int, ...]) -> bool:
    """Exact Havel--Hakimi decision for a loopless simple degree sequence."""
    n = len(degrees)
    if any(d < 0 or d >= n for d in degrees) or sum(degrees) % 2:
        return False
    remaining = list(degrees)
    while remaining:
        remaining.sort(reverse=True)
        first = remaining.pop(0)
        if first == 0:
            return True  # All remaining degrees are zero; no further work.
        if first > len(remaining):
            return False
        for i in range(first):
            remaining[i] -= 1
            if remaining[i] < 0:
                return False
    return True


def cap_two_degree_feasible(v: int, k: int, b: int) -> bool:
    """Necessary cap-two row feasibility, not a covering existence test.

    Excess degrees are (k-1)*r_i-(v-1). If any permissible degree allocation
    is graphical, so is the allocation whose r_i differ by at most one:
    moving k-1 units from a higher degree to a lower degree uses successive
    simple-graph edge switches. Thus testing the balanced sequence is exact
    for this degree relaxation. See docs/scheduling-analytic-bounds.md.
    """
    _parameters(v, k)
    if not isinstance(b, int) or b < 1:
        raise ValueError("need positive integer b")
    rmin = (v + k - 3) // (k - 1)
    q, high = divmod(b * k, v)
    replication = (q + 1,) * high + (q,) * (v - high)
    if min(replication) < rmin or max(replication) > b:
        return False
    return is_graphical(tuple((k - 1) * r - (v - 1) for r in replication))


@dataclass(frozen=True)
class RowDegreeBound:
    replication_minimum: int
    residual_degree: int
    excess_incidence: int
    lambda_lower_bound: int
    cap_two_excluded: bool
    infeasible_reason: Optional[str]
    forced_pair_profile: Optional[Tuple[int, ...]]
    forced_item_profile: Optional[Tuple[int, ...]]


def row_degree_bound(v: int, k: int, b: int) -> RowDegreeBound:
    """Necessary arithmetic consequences of sum_j lambda_ij=(k-1)*r_i.

    When the minimum row degree has no excess and just two extra item
    incidences remain, the excess multigraph must be a single edge of weight
    k-1. This forces the entire pair and item-frequency profiles.
    """
    _parameters(v, k)
    if not isinstance(b, int) or b < 1:
        raise ValueError("need positive integer b")
    rmin = (v + k - 3) // (k - 1)
    d = rmin * (k - 1) - (v - 1)
    residual = b * k - v * rmin
    reason = None
    forced_pairs = forced_items = None
    cap_two_excluded = not cap_two_degree_feasible(v, k, b)
    cap_lower = 3 if cap_two_excluded else 1
    if residual < 0:
        reason = "INSUFFICIENT_ITEM_INCIDENCES"
    elif d == 0 and residual == 1:
        # One positive-degree vertex is impossible in a loopless graph.
        reason = "ROW_ZERO_RESIDUE_SINGLE_INCIDENCE"
    elif d == 0 and residual == 2:
        # A single vertex with two extra incidences is impossible; the only
        # alternative is two vertices joined by the whole excess weight.
        if k > min(b, rmin + 1):
            reason = "ROW_FORCED_PAIR_EXCEEDS_REPLICATION"
        else:
            forced_pairs = (k,) + (1,) * (math.comb(v, 2) - 1)
            forced_items = (rmin + 1,) * 2 + (rmin,) * (v - 2)
            cap_lower = k
    return RowDegreeBound(rmin, d, residual, cap_lower, cap_two_excluded,
                          reason, forced_pairs, forced_items)
