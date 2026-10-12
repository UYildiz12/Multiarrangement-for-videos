"""Bounded exact residual completion and multi-block neighborhood repair.

The global covering problem is far too large to enumerate for most supported
``(v, k)`` pairs.  This module makes the exact part small: a structured or
existing core is fixed, candidate tail blocks are generated deterministically,
and a depth-first multicover solver fills the remaining lower demands without
violating a concurrence cap.

An exhaustive, untruncated candidate pool permits a fixed-core infeasibility
proof only if the search finishes without reaching its time or node limit.
The public solver returns ``None`` for both failure and interruption; callers
must not treat that return value as an infeasibility certificate.
"""

from __future__ import annotations

import itertools
import math
import random
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .certificates import balanced_sort_key, certify_schedule


Block = Tuple[int, ...]
Pair = Tuple[int, int]


def _pairs(v: int) -> Tuple[Pair, ...]:
    return tuple((left, right) for left in range(v) for right in range(left + 1, v))


def _pair_index_table(v: int) -> Tuple[Tuple[int, ...], ...]:
    table = [[-1] * v for _ in range(v)]
    index = 0
    for left in range(v):
        for right in range(left + 1, v):
            table[left][right] = index
            table[right][left] = index
            index += 1
    return tuple(tuple(row) for row in table)


def _normalize_blocks(blocks: Sequence[Sequence[int]]) -> List[Block]:
    return [tuple(sorted(int(item) for item in block)) for block in blocks]


def _block_pair_ids(block: Sequence[int], table: Sequence[Sequence[int]]) -> Tuple[int, ...]:
    return tuple(table[left][right] for left, right in itertools.combinations(block, 2))


def _coverage_counts(
    v: int,
    blocks: Sequence[Sequence[int]],
    table: Sequence[Sequence[int]],
) -> List[int]:
    counts = [0] * math.comb(v, 2)
    for block in blocks:
        for pair_id in _block_pair_ids(block, table):
            counts[pair_id] += 1
    return counts


@dataclass(frozen=True)
class ResidualSolveResult:
    blocks: Tuple[Block, ...]
    exhaustive_pool: bool
    candidate_count: int
    nodes: int
    timed_out: bool


@dataclass(frozen=True)
class RepairResult:
    blocks: Tuple[Block, ...]
    removed: Tuple[Block, ...]
    added: Tuple[Block, ...]
    target_lambda_max: int
    exhaustive_pool: bool
    nodes: int


def _feasible_block(
    block: Sequence[int],
    capacities: Sequence[int],
    table: Sequence[Sequence[int]],
) -> bool:
    return all(capacities[pair_id] > 0 for pair_id in _block_pair_ids(block, table))


def _beam_blocks_for_pair(
    v: int,
    k: int,
    anchor: Pair,
    deficits: Sequence[int],
    capacities: Sequence[int],
    table: Sequence[Sequence[int]],
    item_counts: Sequence[int],
    *,
    beam_width: int,
    per_pair: int,
    rng: random.Random,
) -> List[Block]:
    """Build promising feasible k-blocks containing one deficient pair."""
    states: List[Tuple[int, ...]] = [tuple(sorted(anchor))]
    while states and len(states[0]) < k:
        expanded: List[Tuple[Tuple[object, ...], Tuple[int, ...]]] = []
        for state in states:
            present = set(state)
            for item in range(v):
                if item in present:
                    continue
                candidate = tuple(sorted(state + (item,)))
                new_pair_ids = [table[item][other] for other in state]
                if any(capacities[pair_id] <= 0 for pair_id in new_pair_ids):
                    continue
                gain = sum(1 for pair_id in new_pair_ids if deficits[pair_id] > 0)
                capacity_slack = sum(capacities[pair_id] for pair_id in new_pair_ids)
                usage = item_counts[item]
                score = (-gain, usage, -capacity_slack, rng.random(), candidate)
                expanded.append((score, candidate))
        expanded.sort(key=lambda item: item[0])
        states = []
        seen: Set[Tuple[int, ...]] = set()
        for _, candidate in expanded:
            if candidate in seen:
                continue
            seen.add(candidate)
            states.append(candidate)
            if len(states) >= beam_width:
                break
    return states[:per_pair]


def generate_residual_candidates(
    v: int,
    k: int,
    base_blocks: Sequence[Sequence[int]],
    deficits: Sequence[int],
    capacities: Sequence[int],
    *,
    preferred_blocks: Iterable[Sequence[int]] = (),
    seed: int = 12345,
    max_enumerated_blocks: int = 200_000,
    candidate_limit: int = 20_000,
    beam_width: int = 96,
    per_pair: int = 24,
) -> Tuple[List[Block], bool]:
    """Return feasible tail candidates and whether the pool is exhaustive."""
    table = _pair_index_table(v)
    normalized_base = set(_normalize_blocks(base_blocks))
    item_counts = [0] * v
    for block in normalized_base:
        for item in block:
            item_counts[item] += 1

    combination_count = math.comb(v, k)
    exhaustive = combination_count <= max_enumerated_blocks
    candidates: Set[Block] = set()

    def consider(block: Sequence[int]) -> None:
        normalized = tuple(sorted(int(item) for item in block))
        if len(normalized) != k or len(set(normalized)) != k:
            return
        if normalized in normalized_base:
            return
        if _feasible_block(normalized, capacities, table):
            candidates.add(normalized)

    for block in preferred_blocks:
        consider(block)

    if exhaustive:
        for block in itertools.combinations(range(v), k):
            consider(block)
    else:
        rng = random.Random(f"{seed}:{v}:{k}:{sum(deficits)}")
        pair_list = _pairs(v)
        deficient_ids = [
            pair_id
            for pair_id, demand in enumerate(deficits)
            if demand > 0
        ]
        # Harder pairs first: low endpoint capacity and high demand.
        deficient_ids.sort(
            key=lambda pair_id: (
                capacities[pair_id],
                -deficits[pair_id],
                pair_id,
            )
        )
        for pair_id in deficient_ids:
            anchor = pair_list[pair_id]
            for block in _beam_blocks_for_pair(
                v,
                k,
                anchor,
                deficits,
                capacities,
                table,
                item_counts,
                beam_width=beam_width,
                per_pair=per_pair,
                rng=rng,
            ):
                consider(block)
            if len(candidates) >= candidate_limit:
                break

        # One-item variants of preferred blocks are valuable around
        # a removed neighborhood and remain deterministic.
        for raw in preferred_blocks:
            block = tuple(sorted(int(item) for item in raw))
            block_set = set(block)
            outside = [item for item in range(v) if item not in block_set]
            for position in range(k):
                for item in outside:
                    consider(block[:position] + block[position + 1 :] + (item,))
                    if len(candidates) >= candidate_limit:
                        break
                if len(candidates) >= candidate_limit:
                    break
            if len(candidates) >= candidate_limit:
                break

    ranked = sorted(
        candidates,
        key=lambda block: (
            -sum(deficits[pair_id] > 0 for pair_id in _block_pair_ids(block, table)),
            sum(item_counts[item] for item in block),
            block,
        ),
    )
    return ranked[:candidate_limit], exhaustive and len(ranked) <= candidate_limit


def solve_residual_exact(
    v: int,
    k: int,
    base_blocks: Sequence[Sequence[int]],
    *,
    blocks_to_add: int,
    lambda_cap: int,
    minimum_concurrence: int = 1,
    preferred_blocks: Iterable[Sequence[int]] = (),
    seed: int = 12345,
    time_limit_seconds: float = 5.0,
    node_limit: int = 500_000,
    max_enumerated_blocks: int = 200_000,
    candidate_limit: int = 20_000,
) -> Optional[ResidualSolveResult]:
    """Search a bounded tail over a deterministic candidate pool.

    A returned witness is exact. ``None`` can also mean timeout or node-limit
    exhaustion and never constitutes an infeasibility certificate.
    """
    if blocks_to_add < 0 or lambda_cap < minimum_concurrence:
        raise ValueError("invalid residual bounds")
    table = _pair_index_table(v)
    base = _normalize_blocks(base_blocks)
    counts = _coverage_counts(v, base, table)
    if any(count > lambda_cap for count in counts):
        return None

    deficits = [max(0, minimum_concurrence - count) for count in counts]
    capacities = [lambda_cap - count for count in counts]
    if sum(deficits) > blocks_to_add * math.comb(k, 2):
        return None
    if blocks_to_add == 0:
        if any(deficits):
            return None
        return ResidualSolveResult(tuple(), True, 0, 1, False)

    candidates, exhaustive = generate_residual_candidates(
        v,
        k,
        base,
        deficits,
        capacities,
        preferred_blocks=preferred_blocks,
        seed=seed,
        max_enumerated_blocks=max_enumerated_blocks,
        candidate_limit=candidate_limit,
    )
    if not candidates:
        return None

    pair_ids = [_block_pair_ids(block, table) for block in candidates]
    by_pair: List[List[int]] = [[] for _ in counts]
    for candidate_index, ids in enumerate(pair_ids):
        for pair_id in ids:
            by_pair[pair_id].append(candidate_index)

    deadline = time.perf_counter() + max(0.01, float(time_limit_seconds))
    selected: List[int] = []
    selected_set: Set[int] = set()
    nodes = 0
    timed_out = False
    solution: Optional[Tuple[int, ...]] = None

    def feasible(candidate_index: int) -> bool:
        return all(capacities[pair_id] > 0 for pair_id in pair_ids[candidate_index])

    def search(slots_left: int) -> bool:
        nonlocal nodes, timed_out, solution
        nodes += 1
        if nodes > node_limit or time.perf_counter() >= deadline:
            timed_out = True
            return False
        deficit_total = sum(deficits)
        if deficit_total > slots_left * math.comb(k, 2):
            return False
        if slots_left == 0:
            if deficit_total == 0:
                solution = tuple(selected)
                return True
            return False

        deficient = [pair_id for pair_id, demand in enumerate(deficits) if demand > 0]
        if deficient:
            option_rows: List[Tuple[int, int, List[int]]] = []
            for pair_id in deficient:
                options = [
                    candidate_index
                    for candidate_index in by_pair[pair_id]
                    if candidate_index not in selected_set and feasible(candidate_index)
                ]
                if not options:
                    return False
                option_rows.append((len(options), pair_id, options))
            _, _, options = min(option_rows, key=lambda row: (row[0], row[1]))
        else:
            options = [
                candidate_index
                for candidate_index in range(len(candidates))
                if candidate_index not in selected_set and feasible(candidate_index)
            ]
            if not options:
                return False

        options.sort(
            key=lambda candidate_index: (
                -sum(deficits[pair_id] > 0 for pair_id in pair_ids[candidate_index]),
                candidates[candidate_index],
            )
        )
        for candidate_index in options:
            changed_deficits: List[int] = []
            for pair_id in pair_ids[candidate_index]:
                capacities[pair_id] -= 1
                if deficits[pair_id] > 0:
                    deficits[pair_id] -= 1
                    changed_deficits.append(pair_id)
            selected.append(candidate_index)
            selected_set.add(candidate_index)
            if search(slots_left - 1):
                return True
            selected_set.remove(candidate_index)
            selected.pop()
            for pair_id in changed_deficits:
                deficits[pair_id] += 1
            for pair_id in pair_ids[candidate_index]:
                capacities[pair_id] += 1
            if timed_out:
                return False
        return False

    if not search(blocks_to_add) or solution is None:
        return None
    return ResidualSolveResult(
        blocks=tuple(candidates[index] for index in solution),
        exhaustive_pool=exhaustive,
        candidate_count=len(candidates),
        nodes=nodes,
        timed_out=timed_out,
    )


def _removal_sets_hitting_hot_pairs(
    v: int,
    blocks: Sequence[Block],
    counts: Sequence[int],
    *,
    cap: int,
    size: int,
    limit: int,
) -> List[Tuple[int, ...]]:
    table = _pair_index_table(v)
    block_pair_ids = [_block_pair_ids(block, table) for block in blocks]
    hot_pairs = {pair_id for pair_id, count in enumerate(counts) if count > cap}
    if not hot_pairs:
        return []
    pair_to_blocks: Dict[int, List[int]] = {
        pair_id: [
            block_index
            for block_index, ids in enumerate(block_pair_ids)
            if pair_id in ids
        ]
        for pair_id in hot_pairs
    }
    results: Set[Tuple[int, ...]] = set()

    def visit(chosen: Tuple[int, ...], uncovered: Set[int]) -> None:
        if len(results) >= limit:
            return
        if not uncovered:
            if len(chosen) == size:
                results.add(tuple(sorted(chosen)))
                return
            # Fill the remaining neighborhood positions with blocks carrying
            # the most high-concurrence pairs.
            available = [
                index for index in range(len(blocks)) if index not in chosen
            ]
            available.sort(
                key=lambda index: (
                    -sum(counts[pair_id] for pair_id in block_pair_ids[index]),
                    index,
                )
            )
            need = size - len(chosen)
            for extra in itertools.combinations(available[: max(need + 6, 12)], need):
                results.add(tuple(sorted(chosen + extra)))
                if len(results) >= limit:
                    break
            return
        if len(chosen) >= size:
            return
        pair_id = min(
            uncovered,
            key=lambda current: (
                len([index for index in pair_to_blocks[current] if index not in chosen]),
                current,
            ),
        )
        options = [index for index in pair_to_blocks[pair_id] if index not in chosen]
        options.sort(
            key=lambda index: (
                -len(uncovered.intersection(block_pair_ids[index])),
                index,
            )
        )
        for index in options:
            visit(
                chosen + (index,),
                uncovered.difference(block_pair_ids[index]),
            )

    visit(tuple(), hot_pairs)
    return sorted(results)[:limit]


def exact_neighborhood_repair(
    v: int,
    k: int,
    blocks: Sequence[Sequence[int]],
    *,
    max_removed_blocks: int = 4,
    removal_sets_per_size: int = 24,
    time_limit_seconds: float = 20.0,
    seed: int = 12345,
) -> Optional[RepairResult]:
    """Replace a small block neighborhood and strictly lower lambda_max.

    The returned schedule is independently certified and must improve the
    exact balanced key. ``None`` does not certify local or global nonexistence.
    """
    normalized = _normalize_blocks(blocks)
    certificate = certify_schedule(v, k, normalized, source="repair_input")
    if not certificate.complete or certificate.lambda_max <= 1:
        return None
    target_cap = certificate.lambda_max - 1
    table = _pair_index_table(v)
    counts = _coverage_counts(v, normalized, table)
    started = time.perf_counter()
    best: Optional[RepairResult] = None
    input_key = balanced_sort_key(v, k, normalized)

    for remove_count in range(1, max_removed_blocks + 1):
        removal_sets = _removal_sets_hitting_hot_pairs(
            v,
            normalized,
            counts,
            cap=target_cap,
            size=remove_count,
            limit=removal_sets_per_size,
        )
        for removal_index, removal_set in enumerate(removal_sets):
            elapsed = time.perf_counter() - started
            remaining_time = time_limit_seconds - elapsed
            if remaining_time <= 0:
                return best
            removal_lookup = set(removal_set)
            core = [
                block
                for index, block in enumerate(normalized)
                if index not in removal_lookup
            ]
            removed = [normalized[index] for index in removal_set]
            result = solve_residual_exact(
                v,
                k,
                core,
                blocks_to_add=remove_count,
                lambda_cap=target_cap,
                preferred_blocks=removed,
                seed=seed + remove_count * 1009 + removal_index,
                time_limit_seconds=min(remaining_time, 4.0),
            )
            if result is None:
                continue
            candidate = tuple(sorted(core + list(result.blocks)))
            candidate_certificate = certify_schedule(
                v,
                k,
                candidate,
                source=f"exact_residual_r{remove_count}",
            )
            if (
                candidate_certificate.lambda_max <= target_cap
                and balanced_sort_key(v, k, candidate) < input_key
            ):
                repair = RepairResult(
                    blocks=candidate,
                    removed=tuple(removed),
                    added=result.blocks,
                    target_lambda_max=target_cap,
                    exhaustive_pool=result.exhaustive_pool,
                    nodes=result.nodes,
                )
                if best is None or balanced_sort_key(v, k, repair.blocks) < balanced_sort_key(
                    v,
                    k,
                    best.blocks,
                ):
                    best = repair
                if candidate_certificate.lambda_max == target_cap:
                    return best
    return best
