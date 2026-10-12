"""Necessary covering bounds from the dual block-intersection counts.

These bounds are deterministic and do not use a search outcome. They apply to
complete fixed-size covers at the stated trial count. Matching the relaxed
profile certifies its full lexicographic concurrence objective at that count;
it does not prove a smaller trial count impossible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Tuple

from .analytic_bounds import (horsley_trial_bounds, plane_pair_obstruction,
                              projective_failed_design_obstruction,
                              one_extra_cap_two_obstruction, row_degree_bound)


def integer_collision_minimum(total: int, buckets: int) -> int:
    """Minimum sum C(x_i,2) for nonnegative integer bins with given total."""
    if total < 0 or buckets < 0 or (buckets == 0 and total != 0):
        raise ValueError("need nonnegative total and bins, with no mass in zero bins")
    if buckets == 0:
        return 0
    quotient, remainder = divmod(total, buckets)
    return ((buckets - remainder) * quotient * (quotient - 1) // 2
            + remainder * quotient * (quotient + 1) // 2)


def maximum_collisions_under_cap(
    pairs: int, excess: int, cap: int,
) -> Optional[int]:
    """Exact maximum collisions for positive integer bins with a hard cap.

    ``excess`` is the total beyond one observation per pair. Convexity fills
    as many bins as possible to ``cap``, at most one partial bin, and leaves
    every other bin at one. ``None`` means these constraints are impossible.
    """
    if pairs < 0 or excess < 0 or cap < 1:
        return None
    if cap == 1:
        return 0 if excess == 0 else None
    full, remainder = divmod(excess, cap - 1)
    if full + bool(remainder) > pairs:
        return None
    return full * cap * (cap - 1) // 2 + remainder * (remainder + 1) // 2


def relaxed_concurrence_profile(
    v: int, k: int, b: int, cap: int, collision_lower_bound: int,
) -> Optional[Tuple[int, ...]]:
    """Lex-min positive profile with fixed sum and the collision lower bound.

    Choosing the smallest feasible multiplicity at each descending level is
    exact for this integer-histogram relaxation. Its feasibility oracle uses
    the attained maximum collision formula above, not a numeric approximation.
    """
    remaining_pairs = math.comb(v, 2)
    remaining_excess = b * math.comb(k, 2) - remaining_pairs
    required_collisions = collision_lower_bound
    profile = []
    if remaining_excess < 0:
        return None
    for level in range(cap, 1, -1):
        chosen = None
        for number in range(min(remaining_pairs, remaining_excess // (level - 1)) + 1):
            maximum = maximum_collisions_under_cap(
                remaining_pairs - number,
                remaining_excess - number * (level - 1),
                level - 1,
            )
            collisions_here = number * level * (level - 1) // 2
            if maximum is not None and maximum + collisions_here >= required_collisions:
                chosen = number
                break
        if chosen is None:
            return None
        profile.extend([level] * chosen)
        remaining_pairs -= chosen
        remaining_excess -= chosen * (level - 1)
        required_collisions -= chosen * level * (level - 1) // 2
    if remaining_excess or required_collisions > 0:
        return None
    return tuple(profile + [1] * remaining_pairs)


@dataclass(frozen=True)
class DualIncidenceBound:
    collision_lower_bound: int
    lambda_lower_bound: int
    uniform_replication_forced: bool
    relaxed_profile: Tuple[int, ...]


def _collision_and_cap_bounds(v: int, k: int, b: int) -> Tuple[int, int, bool]:
    intersection_sum_minimum = integer_collision_minimum(b * k, v)
    collision_lower_bound = integer_collision_minimum(
        intersection_sum_minimum, math.comb(b, 2),
    )
    replication_minimum = (v + k - 3) // (k - 1)
    excess_incidence = b * k - v * replication_minimum
    if excess_incidence < 0:
        raise ValueError("trial count cannot meet necessary item replication")
    uniform_forced = excess_incidence == 0
    if uniform_forced and b > 1:
        row_collision_minimum = integer_collision_minimum(
            k * (replication_minimum - 1), b - 1,
        )
        collision_lower_bound = max(
            collision_lower_bound, (b * row_collision_minimum + 1) // 2,
        )
    # lambda_ij <= min(r_i,r_j). Two items at concurrence L would consume
    # at least 2*(L-r_min) incidences beyond the required r_min per item.
    cap_upper_bound = min(b, replication_minimum + excess_incidence // 2)
    return collision_lower_bound, cap_upper_bound, uniform_forced


@dataclass(frozen=True)
class TrialCountBound:
    lower_bound: int
    schonheim_lower_bound: int
    horsley_lower_bound: int
    excluded_counts: Tuple[int, ...]
    # Every excluded count is accompanied by independently valid reasons.
    exclusions: Tuple[Tuple[int, Tuple[str, ...]], ...]
    horsley_bounds: Tuple[Tuple[str, int], ...] = ()


def trial_count_bound_details(v: int, k: int) -> TrialCountBound:
    """Combine published, item-row and dual-incidence necessary bounds.

    Consecutive counts starting at Schonheim are excluded by exact arithmetic.
    The first remaining count is a lower bound, not an existence claim.
    """
    if not (isinstance(v, int) and isinstance(k, int) and 2 <= k <= v):
        raise ValueError("need integer 2 <= k <= v")
    replication_minimum = (v + k - 3) // (k - 1)
    lower_bound = (v * replication_minimum + k - 1) // k
    schonheim = lower_bound
    published = horsley_trial_bounds(v, k)
    horsley = max((bound for _, bound in published), default=0)
    plane = plane_pair_obstruction(v, k)
    pairs = math.comb(v, 2)
    exclusions = []
    # Selecting one k-block for each pair supplies a universal finite upper
    # bound, so this loop cannot be unbounded for valid parameters.
    while lower_bound <= pairs:
        reasons = []
        reasons.extend(reason for reason, bound in published if lower_bound < bound)
        if plane and lower_bound * math.comb(k, 2) == pairs:
            reasons.append(plane)
        failed = projective_failed_design_obstruction(v, k)
        if failed and lower_bound == v + 1:
            reasons.append(failed)
        row = row_degree_bound(v, k, lower_bound)
        if row.infeasible_reason:
            reasons.append(row.infeasible_reason)
        collision_bound, cap_upper, _ = _collision_and_cap_bounds(v, k, lower_bound)
        if row.lambda_lower_bound > cap_upper:
            reasons.append("ROW_CAP_EXCEEDS_REPLICATION")
        excess = lower_bound * math.comb(k, 2) - pairs
        maximum = maximum_collisions_under_cap(pairs, excess, cap_upper)
        if maximum is None or maximum < collision_bound:
            reasons.append("DUAL_INCIDENCE_COLLISION")
        if not reasons:
            return TrialCountBound(lower_bound, schonheim, horsley,
                                   tuple(count for count, _ in exclusions),
                                   tuple(exclusions), published)
        exclusions.append((lower_bound, tuple(reasons)))
        lower_bound += 1
    raise AssertionError("necessary bound excluded a known universal covering bound")


def trial_count_lower_bound(v: int, k: int) -> Tuple[int, Tuple[int, ...]]:
    """Backward-compatible lower bound and consecutively excluded counts."""
    detail = trial_count_bound_details(v, k)
    return detail.lower_bound, detail.excluded_counts


@dataclass(frozen=True)
class CapTwoTrialBound:
    """Necessary count bound ONLY among complete covers with pair cap <=2."""
    lower_bound: int
    unrestricted_lower_bound: int
    excluded_counts: Tuple[int, ...]
    exclusions: Tuple[Tuple[int, Tuple[str, ...]], ...]
    cap_two_globally_excluded: bool = False


@lru_cache(maxsize=4096)
def cap_two_trial_bound_details(v: int, k: int) -> CapTwoTrialBound:
    """Separate cap-two count bound; never feed it to compact min-count.

    Row-degree and dual-collision exclusions apply only at cap <=2. A verified
    near-plane exclusion additionally handles one-extra affine/projective
    counts. Exhausting the pair-slot upper bound excludes cap two globally,
    but says nothing about existence of covers with a larger pair cap.
    """
    if not (isinstance(v, int) and isinstance(k, int) and 2 <= k <= v):
        raise ValueError("need integer 2 <= k <= v")
    unrestricted_lower_bound = trial_count_bound_details(v, k).lower_bound
    b = unrestricted_lower_bound
    pairs, slots = math.comb(v, 2), math.comb(k, 2)
    maximum_count = 2 * pairs // slots
    one_extra = one_extra_cap_two_obstruction(v, k)
    exclusions = []
    while b <= maximum_count:
        reasons = []
        if row_degree_bound(v, k, b).cap_two_excluded:
            reasons.append("CAP_TWO_ROW_DEGREE")
        collision, _, _ = _collision_and_cap_bounds(v, k, b)
        maximum = maximum_collisions_under_cap(pairs, b * slots - pairs, 2)
        if maximum is None or maximum < collision:
            reasons.append("CAP_TWO_DUAL_INCIDENCE_COLLISION")
        base = k * (k + 1) if v == k * k else v
        if one_extra and b == base + 1:
            reasons.append(one_extra)
        if not reasons:
            break
        exclusions.append((b, tuple(reasons)))
        b += 1
    return CapTwoTrialBound(b, unrestricted_lower_bound,
                           tuple(n for n, _ in exclusions), tuple(exclusions),
                           b > maximum_count)


def dual_incidence_bound(v: int, k: int, b: int) -> DualIncidenceBound:
    """Return universally necessary bounds for a complete (v,k,b) covering.

    Double counting gives sum C(lambda_ij,2) = sum C(|B_a intersect B_b|,2).
    The intersection sum equals sum C(r_i,2), at least the balanced-bin
    minimum for ``bk`` item appearances. Integer convexity then bounds the
    right-hand collision sum. When coverage forces every r_i=r_min, each
    trial's intersection sum is exactly k*(r_min-1), giving a row refinement.
    """
    if not (isinstance(v, int) and isinstance(k, int) and isinstance(b, int)
            and 2 <= k <= v and b >= 1):
        raise ValueError("need integer 2 <= k <= v and positive b")
    pairs = math.comb(v, 2)
    slots = b * math.comb(k, 2)
    if slots < pairs:
        raise ValueError("trial count cannot provide complete pair coverage")
    collision_lower_bound, cap_upper_bound, uniform_forced = _collision_and_cap_bounds(v, k, b)
    excess = slots - pairs
    lambda_lower_bound = (slots + pairs - 1) // pairs
    for cap in range(lambda_lower_bound, cap_upper_bound + 1):
        maximum = maximum_collisions_under_cap(pairs, excess, cap)
        if maximum is not None and maximum >= collision_lower_bound:
            lambda_lower_bound = cap
            break
    else:
        raise ValueError("dual incidence constraints exclude this covering count")
    profile = relaxed_concurrence_profile(v, k, b, lambda_lower_bound, collision_lower_bound)
    if profile is None:
        raise AssertionError("collision feasibility oracle and profile disagree")
    return DualIncidenceBound(collision_lower_bound, lambda_lower_bound, uniform_forced, profile)
