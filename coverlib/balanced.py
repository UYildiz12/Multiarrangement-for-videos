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
    target = target_lmax if target_lmax is not None else max(2, min(current_lmax - 1, ideal_lmax + 2))

    if iterations is None:
        iterations = min(90_000, max(18_000, v * 1_500))
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
    rng = random.Random(seed)
    pairs = pair_list(v)
    all_items = list(range(v))
    blocks = [tuple(sorted(block)) for block in start_blocks]
    block_pairs = [block_pair_indices(block, v) for block in blocks]
    counts, item_counts = coverage_counts(v, blocks)

    best_blocks = list(blocks)
    best_score = _score_from_counts(counts, item_counts, len(blocks))
    current_scalar = _scalar_score(counts, item_counts, target_lmax, phase=0.0)
    started = time.time()

    for iteration in range(1, iterations + 1):
        if time.time() - started > seconds:
            break

        phase = iteration / iterations
        missing = [idx for idx, count in enumerate(counts) if count == 0]
        over_target = [idx for idx, count in enumerate(counts) if count > target_lmax]

        if over_target and (not missing or rng.random() < 0.75):
            pair_id = rng.choice(over_target)
            touching = [idx for idx, pair_ids in enumerate(block_pairs) if pair_id in pair_ids]
            block_idx = rng.choice(touching) if touching else rng.randrange(len(blocks))
            anchor_pair = None
            avoid_pair = pairs[pair_id]
        elif missing:
            pair_id = rng.choice(missing)
            anchor_pair = pairs[pair_id]
            avoid_pair = None
            sample = rng.sample(range(len(blocks)), min(16, len(blocks)))
            block_idx = min(sample, key=lambda idx: sum(counts[pair] == 1 for pair in block_pairs[idx]))
        else:
            block_idx = rng.randrange(len(blocks))
            anchor_pair = None
            avoid_pair = None

        old_block = blocks[block_idx]
        old_pairs = set(block_pairs[block_idx])
        base_counts = counts[:]
        base_item_counts = item_counts[:]
        for item in old_block:
            base_item_counts[item] -= 1
        for pair_id in old_pairs:
            base_counts[pair_id] -= 1

        required = _required_vertices(
            old_pairs,
            base_counts,
            pairs,
            k,
            rng,
            anchor_pair=anchor_pair,
            avoid_pair=avoid_pair,
        )
        new_block = _build_candidate_block(
            v,
            k,
            required,
            base_counts,
            base_item_counts,
            all_items,
            rng,
            target_lmax,
            avoid_pair=avoid_pair,
        )
        if len(new_block) != k or len(set(new_block)) != k or new_block == old_block:
            continue

        new_pair_ids = set(block_pair_indices(new_block, v))
        new_counts = base_counts
        new_item_counts = base_item_counts
        for item in new_block:
            new_item_counts[item] += 1
        for pair_id in new_pair_ids:
            new_counts[pair_id] += 1

        new_scalar = _scalar_score(new_counts, new_item_counts, target_lmax, phase=phase)
        delta = new_scalar - current_scalar
        temperature = max(1.0, 10_000.0 * (1.0 - phase))
        if delta <= 0 or rng.random() < math.exp(-delta / temperature):
            blocks[block_idx] = new_block
            block_pairs[block_idx] = tuple(new_pair_ids)
            counts = new_counts
            item_counts = new_item_counts
            current_scalar = new_scalar

            score = _score_from_counts(counts, item_counts, len(blocks))
            if score < best_score:
                best_score = score
                best_blocks = list(blocks)

    return best_blocks


def _required_vertices(
    old_pairs: Iterable[int],
    base_counts: Sequence[int],
    pairs: Sequence[Tuple[int, int]],
    k: int,
    rng: random.Random,
    *,
    anchor_pair: Tuple[int, int] | None,
    avoid_pair: Tuple[int, int] | None,
) -> List[int]:
    if anchor_pair is not None:
        return list(anchor_pair)

    required: List[int] = []
    critical_pairs = [pair_id for pair_id in old_pairs if base_counts[pair_id] == 0]
    rng.shuffle(critical_pairs)
    for pair_id in critical_pairs[:2]:
        for item in pairs[pair_id]:
            if item not in required:
                required.append(item)

    if (
        avoid_pair is not None
        and avoid_pair[0] in required
        and avoid_pair[1] in required
        and len(required) > 2
    ):
        required.remove(rng.choice(list(avoid_pair)))

    return required[:k]


def _build_candidate_block(
    v: int,
    k: int,
    required: Sequence[int],
    base_counts: Sequence[int],
    base_item_counts: Sequence[int],
    all_items: Sequence[int],
    rng: random.Random,
    target_lmax: int,
    *,
    avoid_pair: Tuple[int, int] | None,
) -> Block:
    selected = list(dict.fromkeys(int(item) for item in required if 0 <= int(item) < v))

    while len(selected) < k:
        options: List[Tuple[float, int]] = []
        for candidate in all_items:
            if candidate in selected:
                continue

            cost = base_item_counts[candidate] * 3.0 + rng.random() * 0.5
            for existing in selected:
                pair_id = pair_index(candidate, existing, v)
                new_count = base_counts[pair_id] + 1
                if base_counts[pair_id] == 0:
                    cost -= 1300.0
                if new_count > target_lmax:
                    cost += 2800.0 * (new_count - target_lmax) ** 2
                cost += 18.0 * new_count * new_count
                if avoid_pair is not None and {candidate, existing} == set(avoid_pair):
                    cost += 10_000.0
            options.append((cost, candidate))

        if not options:
            break
        options.sort(key=lambda item: item[0])
        top = options[: min(10, len(options))]
        selected.append(top[0][1] if rng.random() < 0.86 else rng.choice(top)[1])

    return tuple(sorted(selected))


def _score_from_counts(
    counts: Sequence[int],
    item_counts: Sequence[int],
    n_blocks: int,
) -> Tuple[int, int, int, int, int, int]:
    missing = sum(count == 0 for count in counts)
    if missing:
        return (
            1,
            missing,
            max(counts) if counts else 0,
            sum(count * count for count in counts),
            max(item_counts) - min(item_counts) if item_counts else 0,
            n_blocks,
        )
    lmax = max(counts) if counts else 0
    return (
        0,
        lmax,
        sum(count == lmax for count in counts),
        sum(count * count for count in counts),
        max(item_counts) - min(item_counts) if item_counts else 0,
        n_blocks,
    )


def _scalar_score(
    counts: Sequence[int],
    item_counts: Sequence[int],
    target_lmax: int,
    *,
    phase: float,
) -> float:
    missing = sum(count == 0 for count in counts)
    over_target = sum((count - target_lmax) ** 2 for count in counts if count > target_lmax)
    lmax = max(counts) if counts else 0
    item_range = max(item_counts) - min(item_counts) if item_counts else 0
    missing_penalty = 2000.0 + 250_000.0 * phase
    return (
        missing_penalty * missing
        + 30_000.0 * over_target
        + 3500.0 * lmax
        + 20.0 * sum(count * count for count in counts)
        + 50.0 * item_range
    )
