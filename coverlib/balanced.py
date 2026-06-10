from __future__ import annotations

import itertools
import math
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


Block = Tuple[int, ...]


@dataclass(frozen=True)
class NormalizedBalanceMetrics:
    """Size-comparable diagnostics for a pair-cover schedule."""

    v: int
    k: int
    n_blocks: int
    total_pairs: int
    total_pair_slots: int
    complete: bool
    missing_pairs: int
    missing_pair_fraction: float
    lambda_mean: float
    lambda_max: int
    ideal_lambda_max: int
    lambda_max_ratio: float
    pairs_at_lambda_max: int
    pairs_at_lambda_max_fraction: float
    pair_sumsq: int
    ideal_pair_sumsq: int
    pair_sumsq_excess: int
    normalized_pair_sumsq_excess: float
    item_sumsq: int
    ideal_item_sumsq: int
    item_sumsq_excess: int
    normalized_item_sumsq_excess: float
    item_range: int
    pair_slot_trial_lower_bound: int
    trial_efficiency: float


def pair_index(i: int, j: int, v: int) -> int:
    if i > j:
        i, j = j, i
    return i * (2 * v - i - 1) // 2 + (j - i - 1)


def pair_list(v: int) -> List[Tuple[int, int]]:
    return [(i, j) for i in range(v) for j in range(i + 1, v)]


def block_pair_indices(block: Sequence[int], v: int) -> Tuple[int, ...]:
    ordered = tuple(sorted(int(x) for x in block))
    return tuple(pair_index(a, b, v) for a, b in itertools.combinations(ordered, 2))


def coverage_counts(v: int, blocks: Sequence[Sequence[int]]) -> Tuple[List[int], List[int]]:
    counts = [0] * (v * (v - 1) // 2)
    item_counts = [0] * v
    for block in blocks:
        ordered = tuple(sorted(int(x) for x in block))
        for item in ordered:
            item_counts[item] += 1
        for pair in block_pair_indices(ordered, v):
            counts[pair] += 1
    return counts, item_counts


def _ideal_sumsq(total: int, buckets: int) -> int:
    if buckets <= 0:
        return 0
    quotient, remainder = divmod(total, buckets)
    return remainder * (quotient + 1) ** 2 + (buckets - remainder) * quotient**2


def normalized_balance_metrics(
    v: int,
    k: int,
    blocks: Sequence[Sequence[int]],
) -> NormalizedBalanceMetrics:
    """Return balance diagnostics that can be compared across ``v`` values.

    Raw ``lambda_max`` is not directly comparable across stimulus set sizes
    because the unavoidable mean pair concurrence changes with the number of
    pairs and the trial budget. This metric normalizes against the best possible
    integer distribution for the actual number of pair observations.
    """
    counts, item_counts = coverage_counts(v, blocks)
    total_pairs = len(counts)
    total_pair_slots = sum(counts)
    missing_pairs = sum(count == 0 for count in counts)
    lambda_max = max(counts) if counts else 0
    ideal_lambda_max = math.ceil(total_pair_slots / total_pairs) if total_pairs else 0
    pairs_at_lambda_max = sum(count == lambda_max for count in counts) if counts else 0
    pair_sumsq = sum(count * count for count in counts)
    ideal_pair_sumsq = _ideal_sumsq(total_pair_slots, total_pairs)
    pair_sumsq_excess = pair_sumsq - ideal_pair_sumsq

    item_total_slots = sum(item_counts)
    item_sumsq = sum(count * count for count in item_counts)
    ideal_item_sumsq = _ideal_sumsq(item_total_slots, v)
    item_sumsq_excess = item_sumsq - ideal_item_sumsq

    pair_slots_per_trial = math.comb(k, 2) if k >= 2 else 0
    pair_slot_trial_lower_bound = (
        math.ceil(total_pairs / pair_slots_per_trial)
        if pair_slots_per_trial and total_pairs
        else 0
    )

    return NormalizedBalanceMetrics(
        v=v,
        k=k,
        n_blocks=len(blocks),
        total_pairs=total_pairs,
        total_pair_slots=total_pair_slots,
        complete=missing_pairs == 0,
        missing_pairs=missing_pairs,
        missing_pair_fraction=(missing_pairs / total_pairs) if total_pairs else 0.0,
        lambda_mean=(total_pair_slots / total_pairs) if total_pairs else 0.0,
        lambda_max=lambda_max,
        ideal_lambda_max=ideal_lambda_max,
        lambda_max_ratio=(lambda_max / ideal_lambda_max) if ideal_lambda_max else 0.0,
        pairs_at_lambda_max=pairs_at_lambda_max,
        pairs_at_lambda_max_fraction=(pairs_at_lambda_max / total_pairs) if total_pairs else 0.0,
        pair_sumsq=pair_sumsq,
        ideal_pair_sumsq=ideal_pair_sumsq,
        pair_sumsq_excess=pair_sumsq_excess,
        normalized_pair_sumsq_excess=(
            pair_sumsq_excess / ideal_pair_sumsq if ideal_pair_sumsq else 0.0
        ),
        item_sumsq=item_sumsq,
        ideal_item_sumsq=ideal_item_sumsq,
        item_sumsq_excess=item_sumsq_excess,
        normalized_item_sumsq_excess=(
            item_sumsq_excess / ideal_item_sumsq if ideal_item_sumsq else 0.0
        ),
        item_range=max(item_counts) - min(item_counts) if item_counts else 0,
        pair_slot_trial_lower_bound=pair_slot_trial_lower_bound,
        trial_efficiency=(
            len(blocks) / pair_slot_trial_lower_bound if pair_slot_trial_lower_bound else 0.0
        ),
    )


def balance_sort_key(v: int, k: int, blocks: Sequence[Sequence[int]]) -> Tuple[object, ...]:
    """Lexicographic score for selecting scientifically balanced covers."""
    metrics = normalized_balance_metrics(v, k, blocks)
    if not metrics.complete:
        return (
            1,
            metrics.missing_pairs,
            round(metrics.missing_pair_fraction, 12),
            metrics.n_blocks,
        )
    return (
        0,
        round(metrics.lambda_max_ratio, 12),
        metrics.lambda_max,
        round(metrics.normalized_pair_sumsq_excess, 12),
        round(metrics.pairs_at_lambda_max_fraction, 12),
        round(metrics.normalized_item_sumsq_excess, 12),
        metrics.item_range,
        metrics.n_blocks,
    )


def balance_score(v: int, blocks: Sequence[Sequence[int]]) -> Tuple[int, int, int, int, int, int]:
    counts, item_counts = coverage_counts(v, blocks)
    missing = sum(count == 0 for count in counts)
    if missing:
        return (
            1,
            missing,
            max(counts) if counts else 0,
            sum(count * count for count in counts),
            max(item_counts) - min(item_counts) if item_counts else 0,
            len(blocks),
        )
    lmax = max(counts) if counts else 0
    return (
        0,
        lmax,
        sum(count == lmax for count in counts),
        sum(count * count for count in counts),
        max(item_counts) - min(item_counts) if item_counts else 0,
        len(blocks),
    )


def coverage_histogram(v: int, blocks: Sequence[Sequence[int]]) -> Counter[int]:
    counts, _ = coverage_counts(v, blocks)
    return Counter(counts)


@dataclass
class _SwapState:
    """Incrementally-maintained covering state for single-item-swap search."""

    v: int
    k: int
    target: int
    blocks: List[Tuple[int, ...]]
    block_sets: List[set]
    pairs: List[Tuple[int, int]]
    counts: List[int]
    item_counts: List[int]
    item_blocks: List[set]
    count_hist: List[int]
    missing: set = field(default_factory=set)
    over: set = field(default_factory=set)
    sumsq: int = 0
    item_sumsq: int = 0
    lmax: int = 0


def _init_state(v: int, k: int, blocks: Sequence[Sequence[int]], *, target: int) -> _SwapState:
    normalized = [tuple(sorted(int(x) for x in block)) for block in blocks]
    counts, item_counts = coverage_counts(v, normalized)
    count_hist = [0] * (len(normalized) + 2)
    for count in counts:
        count_hist[count] += 1
    item_blocks: List[set] = [set() for _ in range(v)]
    for bidx, block in enumerate(normalized):
        for item in block:
            item_blocks[item].add(bidx)
    return _SwapState(
        v=v,
        k=k,
        target=target,
        blocks=normalized,
        block_sets=[set(block) for block in normalized],
        pairs=pair_list(v),
        counts=counts,
        item_counts=item_counts,
        item_blocks=item_blocks,
        count_hist=count_hist,
        missing={pid for pid, count in enumerate(counts) if count == 0},
        over={pid for pid, count in enumerate(counts) if count > target},
        sumsq=sum(count * count for count in counts),
        item_sumsq=sum(count * count for count in item_counts),
        lmax=max(counts) if counts else 0,
    )


def _apply_swap(st: _SwapState, bidx: int, x: int, y: int) -> None:
    """Replace item x with item y in block bidx, updating all state in O(k)."""
    others = [u for u in st.blocks[bidx] if u != x]
    for u in others:
        pid = pair_index(x, u, st.v)
        c = st.counts[pid]
        st.counts[pid] = c - 1
        st.sumsq += (c - 1) * (c - 1) - c * c
        st.count_hist[c] -= 1
        st.count_hist[c - 1] += 1
        if c == 1:
            st.missing.add(pid)
        if c > st.target and c - 1 <= st.target:
            st.over.discard(pid)
        if c == st.lmax and st.count_hist[c] == 0:
            while st.lmax > 0 and st.count_hist[st.lmax] == 0:
                st.lmax -= 1
    for u in others:
        pid = pair_index(y, u, st.v)
        c = st.counts[pid]
        st.counts[pid] = c + 1
        st.sumsq += (c + 1) * (c + 1) - c * c
        st.count_hist[c] -= 1
        st.count_hist[c + 1] += 1
        if c == 0:
            st.missing.discard(pid)
        if c + 1 > st.target:
            st.over.add(pid)
        if c + 1 > st.lmax:
            st.lmax = c + 1
    cx = st.item_counts[x]
    st.item_sumsq += (cx - 1) * (cx - 1) - cx * cx
    st.item_counts[x] = cx - 1
    cy = st.item_counts[y]
    st.item_sumsq += (cy + 1) * (cy + 1) - cy * cy
    st.item_counts[y] = cy + 1
    st.item_blocks[x].discard(bidx)
    st.item_blocks[y].add(bidx)
    new_block = tuple(sorted(others + [y]))
    st.blocks[bidx] = new_block
    st.block_sets[bidx] = set(new_block)


_OVER_WEIGHT = 64.0


def _pair_cost(count: int, target: int, missing_w: float) -> float:
    cost = float(count * count)
    if count == 0:
        cost += missing_w
    elif count > target:
        excess = count - target
        cost += _OVER_WEIGHT * excess * excess
    return cost


def _total_cost(
    counts: Sequence[int],
    item_counts: Sequence[int],
    target: int,
    missing_w: float,
    item_w: float,
) -> float:
    """Reference objective; only used by tests and debugging."""
    total = sum(_pair_cost(count, target, missing_w) for count in counts)
    total += item_w * sum(count * count for count in item_counts)
    return total


def _swap_delta(st: _SwapState, bidx: int, x: int, y: int, missing_w: float, item_w: float) -> float:
    delta = 0.0
    target = st.target
    for u in st.blocks[bidx]:
        if u == x:
            continue
        pid = pair_index(x, u, st.v)
        c = st.counts[pid]
        delta += _pair_cost(c - 1, target, missing_w) - _pair_cost(c, target, missing_w)
        pid = pair_index(y, u, st.v)
        c = st.counts[pid]
        delta += _pair_cost(c + 1, target, missing_w) - _pair_cost(c, target, missing_w)
    cx = st.item_counts[x]
    cy = st.item_counts[y]
    delta += item_w * float((cx - 1) * (cx - 1) - cx * cx + (cy + 1) * (cy + 1) - cy * cy)
    return delta


def _random_hot_pair(st: _SwapState, rng: random.Random) -> int | None:
    """Sample a pair id with count > target; rejection-sample via blocks, then exact."""
    if not st.over:
        return None
    for _ in range(8):
        block = st.blocks[rng.randrange(len(st.blocks))]
        a = block[rng.randrange(len(block))]
        b = block[rng.randrange(len(block))]
        if a == b:
            continue
        pid = pair_index(a, b, st.v)
        if st.counts[pid] > st.target:
            return pid
    return rng.choice(tuple(st.over))


def _best_replacement(
    st: _SwapState,
    bidx: int,
    x: int,
    rng: random.Random,
    missing_w: float,
    item_w: float,
    samples: int = 14,
) -> Tuple[int, float] | None:
    best_y = None
    best_delta = 0.0
    block_set = st.block_sets[bidx]
    for _ in range(samples):
        y = rng.randrange(st.v)
        if y in block_set or y == x:
            continue
        delta = _swap_delta(st, bidx, x, y, missing_w, item_w)
        if best_y is None or delta < best_delta:
            best_y = y
            best_delta = delta
    if best_y is None:
        return None
    return best_y, best_delta


def _propose_swap(
    st: _SwapState,
    rng: random.Random,
    *,
    missing_w: float,
    item_w: float,
) -> Tuple[int, int, int, float] | None:
    """Return (block_idx, item_out, item_in, delta) or None."""
    # Repair move: bring a missing pair's partner into a block holding one endpoint.
    if st.missing and rng.random() < 0.9:
        pid = rng.choice(tuple(st.missing))
        a, b = st.pairs[pid]
        if rng.random() < 0.5:
            a, b = b, a
        candidate_blocks = [i for i in st.item_blocks[a] if b not in st.block_sets[i]]
        if candidate_blocks:
            bidx = rng.choice(candidate_blocks)
            best = None
            for x in st.blocks[bidx]:
                if x == a:
                    continue
                delta = _swap_delta(st, bidx, x, b, missing_w, item_w)
                if best is None or delta < best[1]:
                    best = (x, delta)
            if best is not None:
                return bidx, best[0], b, best[1]
    # Flatten move: evict one endpoint of an over-target pair.
    if st.over and rng.random() < 0.7:
        pid = _random_hot_pair(st, rng)
        if pid is not None:
            a, b = st.pairs[pid]
            shared = st.item_blocks[a] & st.item_blocks[b]
            if shared:
                bidx = rng.choice(tuple(shared))
                x = a if rng.random() < 0.5 else b
                found = _best_replacement(st, bidx, x, rng, missing_w, item_w)
                if found is not None:
                    return bidx, x, found[0], found[1]
    # Generic move: random block/item with greedy-sampled replacement.
    bidx = rng.randrange(len(st.blocks))
    block = st.blocks[bidx]
    x = block[rng.randrange(len(block))]
    found = _best_replacement(st, bidx, x, rng, missing_w, item_w)
    if found is None:
        return None
    return bidx, x, found[0], found[1]


def read_blocks_file(path: str | Path, v: int, k: int) -> List[List[int]]:
    blocks: List[List[int]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            block = [int(part) for part in text.replace(",", " ").split()]
            if len(block) != k:
                raise ValueError(f"Expected block size {k}, got {len(block)} in {path}")
            if len(set(block)) != k:
                raise ValueError(f"Duplicate item in block {block} in {path}")
            if any(item < 0 or item >= v for item in block):
                raise ValueError(f"Item out of range in block {block} in {path}")
            blocks.append(sorted(block))
    return blocks


def write_blocks_file(path: str | Path, blocks: Sequence[Sequence[int]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for block in blocks:
            handle.write(" ".join(str(int(item)) for item in sorted(block)))
            handle.write("\n")


def load_cached_balanced_cover(
    v: int,
    k: int,
    *,
    max_blocks: int,
    cache_dirs: Sequence[str | Path],
) -> List[List[int]] | None:
    """Load the best precomputed balanced cover within a trial budget."""
    candidates: List[List[List[int]]] = []
    pattern = f"v{v}_k{k}_b*.txt"
    for cache_dir in cache_dirs:
        root = Path(cache_dir)
        if not root.exists():
            continue
        for path in sorted(root.glob(pattern)):
            try:
                blocks = read_blocks_file(path, v, k)
            except Exception:
                continue
            if len(blocks) > max_blocks:
                continue
            score = balance_score(v, blocks)
            if score[0] == 0:
                candidates.append(blocks)

    if not candidates:
        return None
    return min(candidates, key=lambda blocks: balance_sort_key(v, k, blocks))


def improve_pair_balance(
    v: int,
    k: int,
    blocks: Sequence[Sequence[int]],
    *,
    seed: int = 12345,
    target_lmax: int | None = None,
    attempts: int = 3,
    iterations: int | None = None,
    seconds_per_attempt: float | None = None,
) -> List[List[int]]:
    """Flatten pair concurrence with fixed trial count.

    This is a bounded stochastic local search inspired by covering-array
    generators: moves may temporarily under-cover pairs, but the returned cover is
    never worse than the input under ``balance_score``.
    """
    normalized = [tuple(sorted(int(x) for x in block)) for block in blocks]
    if not normalized or k < 2:
        return [list(block) for block in normalized]

    start_score = balance_score(v, normalized)
    if start_score[0] != 0:
        return [list(block) for block in normalized]

    current_lmax = start_score[1]
    if current_lmax <= 2:
        return [list(block) for block in normalized]

    pair_budget = len(normalized) * math.comb(k, 2)
    ideal_lmax = max(1, math.ceil(pair_budget / max(1, v * (v - 1) // 2)))
    target = target_lmax if target_lmax is not None else max(2, ideal_lmax)

    if iterations is None:
        iterations = min(8_000_000, max(500_000, v * 60_000))
    if seconds_per_attempt is None:
        seconds_per_attempt = min(18.0, max(4.0, v * 0.35))

    best_blocks = normalized
    best_score = start_score
    attempt_seeds = (seed, 22, 11, 33, 44, seed + 11, seed + 22, seed + 33)
    for attempt in range(max(1, attempts)):
        attempt_seed = attempt_seeds[attempt % len(attempt_seeds)]
        candidate = _anneal_once(
            v,
            k,
            best_blocks,
            target_lmax=target,
            seed=attempt_seed,
            iterations=iterations,
            seconds=seconds_per_attempt,
        )
        candidate_score = balance_score(v, candidate)
        if candidate_score < best_score:
            best_blocks = candidate
            best_score = candidate_score
            if best_score[0] == 0 and best_score[1] <= ideal_lmax:
                break
            if best_score[0] == 0 and best_score[1] <= target:
                target = max(2, best_score[1] - 1)

    return [list(block) for block in best_blocks]


def _anneal_once(
    v: int,
    k: int,
    start_blocks: Sequence[Block],
    *,
    target_lmax: int,
    seed: int,
    iterations: int,
    seconds: float,
) -> List[Block]:
    """Single-item-swap annealing with a zero-temperature polish tail.

    Temporary coverage violations are allowed mid-search (phase-ramped missing
    penalty); only complete states are ever recorded as best.
    """
    rng = random.Random(seed)
    if k >= v or not start_blocks:
        return [tuple(sorted(block)) for block in start_blocks]
    st = _init_state(v, k, start_blocks, target=target_lmax)
    item_w = 0.05

    best_blocks = list(st.blocks)
    best_key = (st.lmax, st.sumsq, st.item_sumsq) if not st.missing else None

    # Calibrate the starting temperature from sampled move deltas.
    calibration: List[float] = []
    for _ in range(64):
        prop = _propose_swap(st, rng, missing_w=40.0, item_w=item_w)
        if prop is not None and prop[3] > 0:
            calibration.append(prop[3])
    calibration.sort()
    t_start = max(4.0, calibration[len(calibration) // 2] if calibration else 32.0)
    t_end = max(0.05, t_start / 400.0)

    polish_at = 0.8
    started = time.time()
    phase = 0.0
    iteration = 0
    while iteration < iterations:
        if (iteration & 127) == 0:
            elapsed = time.time() - started
            if elapsed >= seconds:
                break
            phase = max(elapsed / seconds, iteration / iterations)
        iteration += 1

        polish = phase >= polish_at
        if polish and not st.missing:
            missing_w = 1e18
        else:
            missing_w = 16.0 + 600.0 * phase * phase

        prop = _propose_swap(st, rng, missing_w=missing_w, item_w=item_w)
        if prop is None:
            continue
        bidx, x, y, delta = prop
        if delta > 0.0:
            if polish:
                continue
            temperature = t_start * (t_end / t_start) ** min(1.0, phase / polish_at)
            if rng.random() >= math.exp(-delta / temperature):
                continue
        _apply_swap(st, bidx, x, y)
        if not st.missing:
            key = (st.lmax, st.sumsq, st.item_sumsq)
            if best_key is None or key < best_key:
                best_key = key
                best_blocks = list(st.blocks)

    return best_blocks
