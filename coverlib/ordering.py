"""Participant counterbalancing and anytime-balanced trial ordering."""

from __future__ import annotations

import hashlib
import itertools
import math
import random
from functools import lru_cache
from typing import Iterable, List, Optional, Sequence, Tuple


Block = Tuple[int, ...]
Permutation = Tuple[int, ...]


def relabel_schedule(
    blocks: Sequence[Sequence[int]],
    permutation: Sequence[int],
) -> List[List[int]]:
    """Apply an old-label -> new-label permutation to every block."""
    v = len(permutation)
    if sorted(int(item) for item in permutation) != list(range(v)):
        raise ValueError("permutation must contain every item exactly once")
    return [
        sorted(int(permutation[int(item)]) for item in block)
        for block in blocks
    ]


def _pair_vector(v: int, blocks: Sequence[Sequence[int]]) -> Tuple[int, ...]:
    counts = {(left, right): 0 for left in range(v) for right in range(left + 1, v)}
    for block in blocks:
        for left, right in itertools.combinations(sorted(int(item) for item in block), 2):
            counts[(left, right)] += 1
    return tuple(counts[(left, right)] for left in range(v) for right in range(left + 1, v))


def _permuted_pair_vector(
    v: int,
    pair_counts: Sequence[int],
    permutation: Sequence[int],
) -> Tuple[int, ...]:
    original_pairs = [
        (left, right)
        for left in range(v)
        for right in range(left + 1, v)
    ]
    remapped = {}
    for count, (left, right) in zip(pair_counts, original_pairs):
        new_left, new_right = permutation[left], permutation[right]
        if new_left > new_right:
            new_left, new_right = new_right, new_left
        remapped[(new_left, new_right)] = count
    return tuple(
        remapped[(left, right)]
        for left in range(v)
        for right in range(left + 1, v)
    )


def _candidate_permutations(v: int, count: int, seed: int) -> Tuple[Permutation, ...]:
    # Never ask the random completion loop for more distinct permutations than
    # the symmetric group contains (important for hosted studies with v <= 4).
    count = min(max(1, int(count)), math.factorial(v))
    permutations = {tuple(range(v))}
    if v > 1:
        coprime_multipliers = [
            multiplier
            for multiplier in range(1, v)
            if math.gcd(multiplier, v) == 1
        ]
        for multiplier in coprime_multipliers:
            for shift in range(v):
                permutations.add(
                    tuple((multiplier * item + shift) % v for item in range(v))
                )
                if len(permutations) >= count:
                    return tuple(sorted(permutations))
    rng = random.Random(f"counterbalance:{seed}:{v}")
    while len(permutations) < count:
        values = list(range(v))
        rng.shuffle(values)
        permutations.add(tuple(values))
    return tuple(sorted(permutations))


@lru_cache(maxsize=128)
def _counterbalanced_permutations_cached(
    v: int,
    blocks: Tuple[Block, ...],
    family_size: int,
    seed: int,
) -> Tuple[Permutation, ...]:
    pair_counts = _pair_vector(v, blocks)
    pool_size = max(32, min(512, family_size * 12))
    permutation_pool = _candidate_permutations(v, pool_size, seed)
    vectors = [
        _permuted_pair_vector(v, pair_counts, permutation)
        for permutation in permutation_pool
    ]
    aggregate = [0] * len(pair_counts)
    selected: List[Permutation] = []
    available = set(range(len(permutation_pool)))

    for _ in range(family_size):
        search_space: Iterable[int] = available if available else range(len(permutation_pool))
        best_index = min(
            search_space,
            key=lambda index: (
                tuple(
                    sorted(
                        (
                            aggregate[pair_index] + vectors[index][pair_index]
                            for pair_index in range(len(aggregate))
                        ),
                        reverse=True,
                    )
                ),
                permutation_pool[index],
            ),
        )
        selected.append(permutation_pool[best_index])
        for pair_index, count in enumerate(vectors[best_index]):
            aggregate[pair_index] += count
        available.discard(best_index)
    return tuple(selected)


def counterbalanced_schedule_family(
    v: int,
    blocks: Sequence[Sequence[int]],
    *,
    family_size: int = 16,
    seed: int = 12345,
) -> Tuple[Tuple[Block, ...], ...]:
    """Build isomorphic schedules with flattened aggregate concurrence."""
    if family_size < 1:
        raise ValueError("family_size must be positive")
    normalized = tuple(
        sorted(tuple(sorted(int(item) for item in block)) for block in blocks)
    )
    permutations = _counterbalanced_permutations_cached(
        v,
        normalized,
        int(family_size),
        int(seed),
    )
    return tuple(
        tuple(tuple(block) for block in relabel_schedule(normalized, permutation))
        for permutation in permutations
    )


def counterbalanced_schedule(
    v: int,
    blocks: Sequence[Sequence[int]],
    *,
    participant_index: int,
    family_size: int = 16,
    seed: int = 12345,
) -> List[List[int]]:
    family = counterbalanced_schedule_family(
        v,
        blocks,
        family_size=family_size,
        seed=seed,
    )
    selected = family[int(participant_index) % len(family)]
    return [list(block) for block in selected]


def participant_counterbalance_index(participant_id: str, family_size: int = 16) -> int:
    """Stable fallback slot when a sequential study-level index is unavailable."""
    if family_size < 1:
        raise ValueError("family_size must be positive")
    digest = hashlib.sha256(str(participant_id).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % family_size


def trial_order_cost(
    v: int,
    blocks: Sequence[Sequence[int]],
    *,
    durations: Optional[Sequence[float]] = None,
) -> Tuple[int, int, int, int, int, int, float]:
    """Evaluate anytime balance without changing the unordered certificate."""
    item_counts = [0] * v
    last_seen = [-1] * v
    maximum_gap = 0
    covered_pairs = set()
    total_pairs = math.comb(v, 2)
    missing_pair_area = 0
    max_prefix_range = 0
    prefix_deviation = 0
    maximum_overlap = 0
    total_overlap = 0
    duration_variation = 0.0
    previous = None
    previous_duration = None

    for trial_index, raw_block in enumerate(blocks):
        block = tuple(sorted(int(item) for item in raw_block))
        for item in block:
            item_counts[item] += 1
            if last_seen[item] >= 0:
                maximum_gap = max(maximum_gap, trial_index - last_seen[item])
            last_seen[item] = trial_index
        max_prefix_range = max(max_prefix_range, max(item_counts) - min(item_counts))
        total_uses = (trial_index + 1) * len(block)
        prefix_deviation += sum(abs(count * v - total_uses) for count in item_counts)
        covered_pairs.update(itertools.combinations(block, 2))
        missing_pair_area += total_pairs - len(covered_pairs)
        if previous is not None:
            overlap = len(set(previous).intersection(block))
            maximum_overlap = max(maximum_overlap, overlap)
            total_overlap += overlap
        if durations is not None:
            block_duration = sum(float(durations[item]) for item in block)
            if previous_duration is not None:
                duration_variation += abs(block_duration - previous_duration)
            previous_duration = block_duration
        previous = block

    final_index = len(blocks)
    for last in last_seen:
        if last >= 0:
            maximum_gap = max(maximum_gap, final_index - last)
    return (
        max_prefix_range,
        missing_pair_area,
        prefix_deviation,
        maximum_gap,
        maximum_overlap,
        total_overlap,
        round(duration_variation, 9),
    )


def optimize_trial_order(
    v: int,
    blocks: Sequence[Sequence[int]],
    *,
    durations: Optional[Sequence[float]] = None,
    seed: int = 12345,
    restarts: int = 4,
) -> List[List[int]]:
    """Greedily construct and multi-start an anytime-balanced block order."""
    normalized = [tuple(sorted(int(item) for item in block)) for block in blocks]
    if len(normalized) < 2:
        return [list(block) for block in normalized]
    effective_restarts = max(1, int(restarts))
    if len(normalized) > 400:
        effective_restarts = 1
    pair_sets = [set(itertools.combinations(block, 2)) for block in normalized]
    total_pairs = math.comb(v, 2)
    best_order = list(normalized)
    best_cost = trial_order_cost(v, best_order, durations=durations)

    for restart in range(effective_restarts):
        rng = random.Random(f"trial-order:{seed}:{restart}:{v}:{len(normalized)}")
        remaining = set(range(len(normalized)))
        order_indices: List[int] = []
        item_counts = [0] * v
        covered_pairs = set()
        last_seen = [-1] * v
        previous_index = None
        previous_duration = None

        while remaining:
            trial_index = len(order_indices)
            best_index = min(
                remaining,
                key=lambda index: _next_block_score(
                    v,
                    normalized[index],
                    pair_sets[index],
                    trial_index,
                    item_counts,
                    covered_pairs,
                    last_seen,
                    normalized[previous_index] if previous_index is not None else None,
                    previous_duration,
                    durations,
                    rng,
                    total_pairs,
                ),
            )
            block = normalized[best_index]
            for item in block:
                item_counts[item] += 1
                last_seen[item] = trial_index
            covered_pairs.update(pair_sets[best_index])
            if durations is not None:
                previous_duration = sum(float(durations[item]) for item in block)
            previous_index = best_index
            order_indices.append(best_index)
            remaining.remove(best_index)

        candidate = [normalized[index] for index in order_indices]
        candidate_cost = trial_order_cost(v, candidate, durations=durations)
        if candidate_cost < best_cost:
            best_order = candidate
            best_cost = candidate_cost
    return [list(block) for block in best_order]


def _next_block_score(
    v: int,
    block: Block,
    block_pairs: set,
    trial_index: int,
    item_counts: Sequence[int],
    covered_pairs: set,
    last_seen: Sequence[int],
    previous: Optional[Block],
    previous_duration: Optional[float],
    durations: Optional[Sequence[float]],
    rng: random.Random,
    total_pairs: int,
) -> Tuple[object, ...]:
    projected = list(item_counts)
    for item in block:
        projected[item] += 1
    total_uses = sum(projected)
    prefix_range = max(projected) - min(projected)
    prefix_deviation = sum(abs(count * v - total_uses) for count in projected)
    new_pairs = len(block_pairs.difference(covered_pairs))
    oldest_gap = max(
        (
            trial_index - last_seen[item]
            if last_seen[item] >= 0
            else trial_index + 1
        )
        for item in block
    )
    overlap = len(set(previous).intersection(block)) if previous is not None else 0
    duration_jump = 0.0
    if durations is not None and previous_duration is not None:
        duration_jump = abs(
            sum(float(durations[item]) for item in block) - previous_duration
        )
    return (
        prefix_range,
        prefix_deviation,
        total_pairs - len(covered_pairs) - new_pairs,
        -oldest_gap,
        overlap,
        round(duration_jump, 9),
        rng.random(),
        block,
    )


def prepare_schedule_for_participant(
    v: int,
    blocks: Sequence[Sequence[int]],
    *,
    participant_index: int = 0,
    counterbalance: bool = False,
    counterbalance_family_size: int = 16,
    optimize_order: bool = True,
    durations: Optional[Sequence[float]] = None,
    seed: int = 12345,
) -> List[List[int]]:
    prepared = [list(map(int, block)) for block in blocks]
    if counterbalance:
        prepared = counterbalanced_schedule(
            v,
            prepared,
            participant_index=participant_index,
            family_size=counterbalance_family_size,
            seed=seed,
        )
    if optimize_order:
        prepared = optimize_trial_order(
            v,
            prepared,
            durations=durations,
            seed=seed + int(participant_index),
        )
    return prepared
