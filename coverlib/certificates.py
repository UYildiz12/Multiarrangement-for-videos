"""Formal schedule verification and Pareto-frontier helpers.

The search code is intentionally allowed to remain heuristic.  This module is
the deterministic boundary around it: every returned candidate can be checked
independently, compared under the exact compact/balanced objectives, and tagged
only with certificates justified by arithmetic lower bounds.
"""

from __future__ import annotations

import hashlib
import itertools
import math
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable, List, Sequence, Tuple

from .incidence_bounds import six_trial_optimal_profile
from .dual_bounds import (dual_incidence_bound, trial_count_bound_details,
                          cap_two_trial_bound_details)
from .analytic_bounds import complement_boundary_profiles, row_degree_bound
from .published_bounds import published_lower_bound


Block = Tuple[int, ...]


def schonheim_lower_bound(v: int, k: int) -> int:
    """Return the Schonheim lower bound C(v, k, 2)."""
    if not 2 <= k <= v:
        raise ValueError("need 2 <= k <= v")
    replication_minimum = (v + k - 3) // (k - 1)
    return (v * replication_minimum + k - 1) // k


def ideal_concurrence_profile(v: int, k: int, b: int) -> Tuple[int, ...]:
    """Most balanced integer pair-concurrence vector possible at fixed ``b``."""
    if v < 2 or not 2 <= k <= v or b < 0:
        raise ValueError("invalid schedule parameters")
    total_pairs = math.comb(v, 2)
    total_pair_slots = b * math.comb(k, 2)
    low, high_count = divmod(total_pair_slots, total_pairs)
    return (low + 1,) * high_count + (low,) * (total_pairs - high_count)


def ideal_concurrence_histogram(v: int, k: int, b: int) -> Counter[int]:
    return Counter(ideal_concurrence_profile(v, k, b))


def _normalize_blocks(v: int, k: int, blocks: Sequence[Sequence[int]]) -> Tuple[Block, ...]:
    normalized: List[Block] = []
    for index, block in enumerate(blocks):
        values = tuple(sorted(int(item) for item in block))
        if len(values) != k:
            raise ValueError(f"block {index} has size {len(values)}; expected {k}")
        if len(set(values)) != k:
            raise ValueError(f"block {index} contains duplicate items")
        if any(item < 0 or item >= v for item in values):
            raise ValueError(f"block {index} contains an item outside 0..{v - 1}")
        normalized.append(values)
    if len(set(normalized)) != len(normalized):
        raise ValueError("schedule contains repeated identical blocks")
    return tuple(normalized)


def _counts(
    v: int,
    blocks: Sequence[Block],
) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    pair_counts = Counter()
    item_counts = [0] * v
    for block in blocks:
        for item in block:
            item_counts[item] += 1
        pair_counts.update(itertools.combinations(block, 2))
    concurrence = tuple(
        pair_counts[(a, b)]
        for a in range(v)
        for b in range(a + 1, v)
    )
    return concurrence, tuple(item_counts)


def concurrence_profile(v: int, blocks: Sequence[Sequence[int]]) -> Tuple[int, ...]:
    """Return pair concurrences sorted from largest to smallest."""
    counts = Counter()
    for block in blocks:
        ordered = tuple(sorted(int(item) for item in block))
        counts.update(itertools.combinations(ordered, 2))
    return tuple(
        sorted(
            (
                counts[(a, b)]
                for a in range(v)
                for b in range(a + 1, v)
            ),
            reverse=True,
        )
    )


def item_deviation_profile(v: int, blocks: Sequence[Sequence[int]]) -> Tuple[int, ...]:
    """Return exact, integer-scaled deviations from perfectly even item use."""
    counts = [0] * v
    total = 0
    for block in blocks:
        for item in block:
            counts[int(item)] += 1
            total += 1
    # Scaling by v avoids floating-point comparisons:
    # abs(count - total/v) * v == abs(count*v - total).
    return tuple(sorted((abs(count * v - total) for count in counts), reverse=True))


def schedule_hash(blocks: Sequence[Sequence[int]]) -> str:
    """Stable hash invariant to block and within-block ordering.

    This is a labeled-schedule hash, not an isomorphism canonicalization across
    arbitrary stimulus relabelings.
    """
    normalized = sorted(tuple(sorted(int(item) for item in block)) for block in blocks)
    payload = "\n".join(" ".join(str(item) for item in block) for block in normalized)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ScheduleCertificate:
    v: int
    k: int
    b: int
    source: str
    schedule_hash: str
    schonheim_lower_bound: int
    complete: bool
    simple: bool
    lambda_max: int
    pair_histogram: Tuple[Tuple[int, int], ...]
    item_histogram: Tuple[Tuple[int, int], ...]
    item_range: int
    concurrence_profile: Tuple[int, ...]
    item_deviation_profile: Tuple[int, ...]
    statuses: Tuple[str, ...]
    dual_collision_lower_bound: int = 0
    lambda_lower_bound: int = 0
    trial_lower_bound: int = 0
    excluded_trial_counts: Tuple[int, ...] = ()
    horsley_lower_bound: int = 0
    row_degree_lambda_lower_bound: int = 0
    row_degree_profile_forced: bool = False
    trial_count_exclusion_proofs: Tuple[Tuple[int, Tuple[str, ...]], ...] = ()
    global_lambda_lower_bound: int = 0
    horsley_bound_proofs: Tuple[Tuple[str, int], ...] = ()
    cap_two_trial_lower_bound: int = 0
    cap_two_trial_exclusion_proofs: Tuple[Tuple[int, Tuple[str, ...]], ...] = ()
    cap_two_globally_excluded: bool = False
    published_lower_bound: int = 0
    published_bound_source: str = ""

    def to_dict(self, *, include_profiles: bool = False) -> dict:
        data = asdict(self)
        data["pair_histogram"] = dict(self.pair_histogram)
        data["item_histogram"] = dict(self.item_histogram)
        if not include_profiles:
            data.pop("concurrence_profile", None)
            data.pop("item_deviation_profile", None)
        return data


def certify_schedule(
    v: int,
    k: int,
    blocks: Sequence[Sequence[int]],
    *,
    source: str = "unknown",
) -> ScheduleCertificate:
    """Validate a simple schedule and attach only mechanically proven statuses."""
    normalized = _normalize_blocks(v, k, blocks)
    concurrence, item_counts = _counts(v, normalized)
    profile = tuple(sorted(concurrence, reverse=True))
    item_profile = item_deviation_profile(v, normalized)
    b = len(normalized)
    complete = bool(concurrence) and min(concurrence) >= 1
    actual_histogram = Counter(concurrence)
    ideal_histogram = ideal_concurrence_histogram(v, k, b)
    item_histogram = Counter(item_counts)
    item_low, item_high_count = divmod(b * k, v)
    ideal_item_histogram = Counter(
        {item_low: v - item_high_count, item_low + 1: item_high_count}
        if item_high_count
        else {item_low: v}
    )
    lower_bound = schonheim_lower_bound(v, k)
    trial_detail = trial_count_bound_details(v, k)
    certified_trial_lower_bound = trial_detail.lower_bound
    own_trial_lower_bound = certified_trial_lower_bound
    # Proven bounds imported from the covering tables and from the paper (coverlib.published_bounds).
    published = published_lower_bound(v, k)
    published_bound, published_source = published if published is not None else (0, "")
    certified_trial_lower_bound = max(certified_trial_lower_bound, published_bound)
    excluded_counts = trial_detail.excluded_counts
    cap_two_detail = cap_two_trial_bound_details(v, k)
    global_cap_lower_bound = (certified_trial_lower_bound * math.comb(k, 2)
                              + math.comb(v, 2) - 1) // math.comb(v, 2)

    statuses: List[str] = ["VALIDATED"]
    if complete and max(concurrence) <= 2 and b < cap_two_detail.lower_bound:
        raise AssertionError("valid cap-two cover contradicts its conditioned count bound")
    if complete:
        statuses.append("COMPLETE_PAIR_COVERAGE")
    if complete and b < certified_trial_lower_bound:
        raise AssertionError("valid covering contradicts a proven trial-count lower bound")
    if complete and b == certified_trial_lower_bound:
        statuses.append("MINIMUM_TRIALS_CERTIFIED")
        if b == own_trial_lower_bound:
            last_reasons = trial_detail.exclusions[-1][1] if excluded_counts else ()
            if "DUAL_INCIDENCE_COLLISION" in last_reasons:
                statuses.append("DUAL_INCIDENCE_MINIMUM_TRIALS")
            if trial_detail.horsley_lower_bound == b and b > lower_bound:
                statuses.append("HORSLEY_MINIMUM_TRIALS")
            if any(reason.startswith("ROW_") for reason in last_reasons):
                statuses.append("ROW_DEGREE_MINIMUM_TRIALS")
        else:
            statuses.append("PUBLISHED_BOUND_MINIMUM_TRIALS")
    if complete and actual_histogram == ideal_histogram:
        statuses.extend(("IDEAL_HISTOGRAM_AT_B", "LAMBDA_CAP_CERTIFIED"))
    structural_profile = six_trial_optimal_profile(v, k, b)
    if complete and structural_profile is not None and profile == structural_profile:
        statuses.append("SIX_TRIAL_INCIDENCE_OPTIMUM")
        if "LAMBDA_CAP_CERTIFIED" not in statuses:
            statuses.append("LAMBDA_CAP_CERTIFIED")
    complement = complement_boundary_profiles(v, k, b) if complete else None
    if complement is not None:
        if profile != complement[0] or tuple(sorted(item_counts, reverse=True)) != complement[1]:
            raise AssertionError("valid covering contradicts its complement boundary profile")
        statuses.append("COMPLEMENT_BOUNDARY_PROFILE_OPTIMUM")
    dual_bound = dual_incidence_bound(v, k, b) if complete else None
    row_bound = row_degree_bound(v, k, b) if complete else None
    if row_bound is not None and row_bound.infeasible_reason:
        raise AssertionError("valid covering contradicts a necessary row-degree bound")
    if (dual_bound is not None and max(concurrence) == dual_bound.lambda_lower_bound
            and "LAMBDA_CAP_CERTIFIED" not in statuses):
        statuses.extend(("DUAL_INCIDENCE_CAP_OPTIMUM", "LAMBDA_CAP_CERTIFIED"))
    if (row_bound is not None and max(concurrence) == row_bound.lambda_lower_bound
            and "LAMBDA_CAP_CERTIFIED" not in statuses):
        statuses.extend(("ROW_DEGREE_CAP_OPTIMUM", "LAMBDA_CAP_CERTIFIED"))
    if (dual_bound is not None and profile == dual_bound.relaxed_profile
            and "IDEAL_HISTOGRAM_AT_B" not in statuses
            and "SIX_TRIAL_INCIDENCE_OPTIMUM" not in statuses):
        statuses.append("DUAL_INCIDENCE_PROFILE_OPTIMUM")
    if row_bound is not None and profile == row_bound.forced_pair_profile:
        if tuple(sorted(item_counts, reverse=True)) != row_bound.forced_item_profile:
            raise AssertionError("valid covering contradicts its forced item profile")
        statuses.append("ROW_DEGREE_PROFILE_OPTIMUM")
    if complete and max(concurrence) == global_cap_lower_bound:
        statuses.append("GLOBAL_LAMBDA_CAP_CERTIFIED")
        if "LAMBDA_CAP_CERTIFIED" not in statuses:
            statuses.append("LAMBDA_CAP_CERTIFIED")
    if complement is not None and "LAMBDA_CAP_CERTIFIED" not in statuses:
        statuses.append("LAMBDA_CAP_CERTIFIED")
    if ("IDEAL_HISTOGRAM_AT_B" in statuses
            or "SIX_TRIAL_INCIDENCE_OPTIMUM" in statuses
            or "DUAL_INCIDENCE_PROFILE_OPTIMUM" in statuses
            or "ROW_DEGREE_PROFILE_OPTIMUM" in statuses
            or "COMPLEMENT_BOUNDARY_PROFILE_OPTIMUM" in statuses):
        statuses.append("PAIR_PROFILE_AT_B_CERTIFIED")
    if item_histogram == ideal_item_histogram:
        statuses.append("ITEM_PROFILE_IDEAL")
    if (
        "MINIMUM_TRIALS_CERTIFIED" in statuses
        and "PAIR_PROFILE_AT_B_CERTIFIED" in statuses
    ):
        statuses.append("PARETO_CERTIFIED")
    elif complete:
        statuses.append("BEST_FOUND_WITH_GAP")
    if "PARETO_CERTIFIED" in statuses and "ITEM_PROFILE_IDEAL" in statuses:
        statuses.append("LEXICOGRAPHIC_OPTIMUM_CERTIFIED")

    return ScheduleCertificate(
        v=v,
        k=k,
        b=b,
        source=source,
        schedule_hash=schedule_hash(normalized),
        schonheim_lower_bound=lower_bound,
        complete=complete,
        simple=True,
        lambda_max=max(concurrence) if concurrence else 0,
        pair_histogram=tuple(sorted(actual_histogram.items())),
        item_histogram=tuple(sorted(item_histogram.items())),
        item_range=(max(item_counts) - min(item_counts)) if item_counts else 0,
        concurrence_profile=profile,
        item_deviation_profile=item_profile,
        statuses=tuple(statuses),
        dual_collision_lower_bound=dual_bound.collision_lower_bound if dual_bound else 0,
        lambda_lower_bound=max(dual_bound.lambda_lower_bound, row_bound.lambda_lower_bound) if dual_bound else 0,
        trial_lower_bound=certified_trial_lower_bound,
        published_lower_bound=published_bound,
        published_bound_source=published_source if published_bound else "",
        excluded_trial_counts=excluded_counts,
        horsley_lower_bound=trial_detail.horsley_lower_bound,
        row_degree_lambda_lower_bound=row_bound.lambda_lower_bound if row_bound else 0,
        row_degree_profile_forced=row_bound is not None and row_bound.forced_pair_profile is not None,
        trial_count_exclusion_proofs=trial_detail.exclusions,
        global_lambda_lower_bound=global_cap_lower_bound,
        horsley_bound_proofs=trial_detail.horsley_bounds,
        cap_two_trial_lower_bound=cap_two_detail.lower_bound,
        cap_two_trial_exclusion_proofs=cap_two_detail.exclusions,
        cap_two_globally_excluded=cap_two_detail.cap_two_globally_excluded,
    )


def compact_sort_key(
    v: int,
    k: int,
    blocks: Sequence[Sequence[int]],
) -> Tuple[object, ...]:
    """Exact compact-mode objective: b, concurrence, then item balance."""
    profile = concurrence_profile(v, blocks)
    missing = sum(count == 0 for count in profile)
    if missing:
        return (1, missing, len(blocks))
    return (0, len(blocks), profile, item_deviation_profile(v, blocks))


def balanced_sort_key(
    v: int,
    k: int,
    blocks: Sequence[Sequence[int]],
) -> Tuple[object, ...]:
    """Exact budgeted-balance objective: concurrence, b, then item balance."""
    profile = concurrence_profile(v, blocks)
    missing = sum(count == 0 for count in profile)
    if missing:
        return (1, missing, len(blocks))
    return (0, profile, len(blocks), item_deviation_profile(v, blocks))


def pareto_frontier(
    certificates: Iterable[ScheduleCertificate],
) -> Tuple[ScheduleCertificate, ...]:
    """Return nondominated schedules under (trial count, concurrence profile)."""
    candidates = list(certificates)
    parameter_sets = {(candidate.v, candidate.k) for candidate in candidates}
    if len(parameter_sets) > 1:
        raise ValueError("Pareto candidates must share the same (v, k)")

    frontier: List[ScheduleCertificate] = []
    for candidate in candidates:
        if not candidate.complete:
            continue
        dominated = False
        for other in candidates:
            if other is candidate or not other.complete:
                continue
            no_more_trials = other.b <= candidate.b
            no_worse_balance = other.concurrence_profile <= candidate.concurrence_profile
            strictly_better = (
                other.b < candidate.b
                or other.concurrence_profile < candidate.concurrence_profile
            )
            if no_more_trials and no_worse_balance and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return tuple(
        sorted(
            frontier,
            key=lambda cert: (
                cert.b,
                cert.concurrence_profile,
                cert.item_deviation_profile,
                cert.schedule_hash,
            ),
        )
    )
