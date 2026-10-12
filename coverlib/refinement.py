"""Deterministic item balancing that preserves the entire pair histogram.

These moves keep trial count and complete pair coverage fixed. Connectivity
is deliberately absent from the objective. See docs/compact-balanced-design.md.
"""
from __future__ import annotations

import itertools
import random
from typing import List, Optional, Sequence, Tuple

from .certificates import certify_schedule

Block = Tuple[int, ...]


def improve_item_balance(
    v: int,
    k: int,
    blocks: Sequence[Sequence[int]],
    *,
    max_moves: int = 1000,
    seed: Optional[int] = None,
) -> List[List[int]]:
    """Transfer appearances from frequent to infrequent items without pair loss.

    A replacement x -> y in block {x} union S is admissible when the multiset
    of counts lambda[x,z], z in S, equals that of lambda[y,z]+1. This is exactly
    the condition for preserving the full pair-count histogram. Requiring
    r[x] >= r[y]+2 strictly improves item balance. This bounded local method
    does not claim that no better schedule exists when it stops.

    Inputs must be simple complete covers. Output order is canonical; apply
    participant-specific trial ordering after this schedule optimization.
    An optional seed changes the internal traversal order for reproducible
    restarts; it does not change the acceptance criterion or preservation rules.
    """
    if isinstance(max_moves, bool) or not isinstance(max_moves, int) or max_moves < 0:
        raise ValueError("max_moves must be a nonnegative integer")
    before = certify_schedule(v, k, blocks, source="item_refinement_input")
    if not before.complete:
        raise ValueError("item refinement requires complete pair coverage")
    work = sorted(tuple(sorted(int(x) for x in block)) for block in blocks)
    if before.item_range <= 1 or max_moves == 0:
        return [list(block) for block in work]
    if seed is not None:
        random.Random(seed).shuffle(work)
    present = set(work)
    counts = [[0] * v for _ in range(v)]
    frequency = [0] * v
    for block in work:
        for x in block:
            frequency[x] += 1
        for x, y in itertools.combinations(block, 2):
            counts[x][y] += 1
            counts[y][x] += 1

    for _ in range(max_moves):
        low_items = sorted(range(v), key=lambda x: (frequency[x], x))
        move = None
        for index, block in enumerate(work):
            for x in sorted(block, key=lambda x: (-frequency[x], x)):
                rest = [z for z in block if z != x]
                removed_counts = sorted(counts[x][z] for z in rest)
                if removed_counts[0] < 2:
                    continue
                for y in low_items:
                    if frequency[y] >= frequency[x] - 1:
                        break
                    if y in block:
                        continue
                    replacement = tuple(sorted(rest + [y]))
                    if replacement in present:
                        continue
                    if sorted(counts[y][z] + 1 for z in rest) == removed_counts:
                        move = (index, x, y, rest, replacement)
                        break
                if move is not None:
                    break
            if move is not None:
                break
        if move is None:
            break
        index, x, y, rest, replacement = move
        present.remove(work[index])
        present.add(replacement)
        work[index] = replacement
        for z in rest:
            counts[x][z] -= 1
            counts[z][x] -= 1
            counts[y][z] += 1
            counts[z][y] += 1
        frequency[x] -= 1
        frequency[y] += 1

    result = [list(block) for block in sorted(work)]
    after = certify_schedule(v, k, result, source="item_refinement_output")
    if (not after.complete or after.pair_histogram != before.pair_histogram
            or after.b != before.b or after.item_deviation_profile > before.item_deviation_profile):
        raise AssertionError("item refinement violated its preservation contract")
    return result
