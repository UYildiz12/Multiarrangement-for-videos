"""Tests for the single-item-swap balance search engine in coverlib.balanced."""

import random

import pytest

from coverlib.balanced import (
    _SwapState,
    _apply_swap,
    _init_state,
    _pair_cost,
    _propose_swap,
    _swap_delta,
    _total_cost,
    balance_score,
    coverage_counts,
    improve_pair_balance,
    pair_index,
)


def _random_complete_cover(v: int, k: int, seed: int) -> list[list[int]]:
    """Build a small complete cover by adding random blocks until all pairs covered."""
    rng = random.Random(seed)
    needed = {(i, j) for i in range(v) for j in range(i + 1, v)}
    blocks: list[list[int]] = []
    while needed:
        block = sorted(rng.sample(range(v), k))
        blocks.append(block)
        for a_idx in range(k):
            for b_idx in range(a_idx + 1, k):
                needed.discard((block[a_idx], block[b_idx]))
    return blocks


def _assert_state_consistent(st: _SwapState) -> None:
    """Incremental fields must match a from-scratch recount."""
    counts, item_counts = coverage_counts(st.v, st.blocks)
    assert st.counts == counts
    assert st.item_counts == item_counts
    assert st.missing == {pid for pid, c in enumerate(counts) if c == 0}
    assert st.over == {pid for pid, c in enumerate(counts) if c > st.target}
    assert st.sumsq == sum(c * c for c in counts)
    assert st.item_sumsq == sum(c * c for c in item_counts)
    assert st.lmax == max(counts)
    for c in range(len(st.count_hist)):
        assert st.count_hist[c] == sum(1 for x in counts if x == c)


def test_init_state_matches_recount():
    v, k = 10, 4
    blocks = _random_complete_cover(v, k, seed=1)
    st = _init_state(v, k, blocks, target=2)
    assert len(st.blocks) == len(blocks)
    _assert_state_consistent(st)


def test_apply_swap_keeps_state_consistent():
    v, k = 10, 4
    blocks = _random_complete_cover(v, k, seed=2)
    st = _init_state(v, k, blocks, target=2)
    rng = random.Random(3)
    applied = 0
    while applied < 60:
        bidx = rng.randrange(len(st.blocks))
        block = st.blocks[bidx]
        x = block[rng.randrange(len(block))]
        y = rng.randrange(v)
        if y in st.block_sets[bidx]:
            continue
        _apply_swap(st, bidx, x, y)
        applied += 1
        assert len(st.blocks[bidx]) == k
        assert len(set(st.blocks[bidx])) == k
        assert st.blocks[bidx] == tuple(sorted(st.blocks[bidx]))
    _assert_state_consistent(st)


def test_swap_delta_matches_total_cost_difference():
    v, k = 10, 4
    blocks = _random_complete_cover(v, k, seed=5)
    target = 2
    st = _init_state(v, k, blocks, target=target)
    rng = random.Random(6)
    missing_w, item_w = 40.0, 0.05
    checked = 0
    while checked < 40:
        bidx = rng.randrange(len(st.blocks))
        x = st.blocks[bidx][rng.randrange(k)]
        y = rng.randrange(v)
        if y in st.block_sets[bidx]:
            continue
        before = _total_cost(st.counts, st.item_counts, target, missing_w, item_w)
        delta = _swap_delta(st, bidx, x, y, missing_w, item_w)
        _apply_swap(st, bidx, x, y)
        after = _total_cost(st.counts, st.item_counts, target, missing_w, item_w)
        assert delta == pytest.approx(after - before)
        checked += 1


def test_propose_swap_returns_valid_moves():
    v, k = 12, 4
    blocks = _random_complete_cover(v, k, seed=7)
    blocks.append(list(blocks[0]))  # duplicate a block to create hot pairs
    st = _init_state(v, k, blocks, target=1)
    rng = random.Random(8)
    seen_any = False
    for _ in range(200):
        prop = _propose_swap(st, rng, missing_w=40.0, item_w=0.05)
        if prop is None:
            continue
        bidx, x, y, delta = prop
        seen_any = True
        assert x in st.block_sets[bidx]
        assert y not in st.block_sets[bidx]
        assert 0 <= y < v
        assert isinstance(delta, float)
    assert seen_any


def test_apply_swap_updates_item_blocks_index():
    v, k = 9, 3
    blocks = _random_complete_cover(v, k, seed=4)
    st = _init_state(v, k, blocks, target=2)
    bidx = 0
    x = st.blocks[0][0]
    y = next(i for i in range(v) if i not in st.block_sets[0])
    _apply_swap(st, bidx, x, y)
    for item in range(v):
        expected = {i for i, bs in enumerate(st.block_sets) if item in bs}
        assert st.item_blocks[item] == expected


def test_improve_pair_balance_contract_small():
    v, k = 12, 4
    blocks = _random_complete_cover(v, k, seed=9)
    blocks.append(list(blocks[0]))
    blocks.append(list(blocks[1]))
    before = balance_score(v, blocks)
    result = improve_pair_balance(
        v, k, blocks, seed=11, attempts=1, iterations=40_000, seconds_per_attempt=2.0
    )
    after = balance_score(v, result)
    assert len(result) == len(blocks)
    for block in result:
        assert len(block) == k
        assert len(set(block)) == k
    assert after[0] == 0  # complete
    assert after <= before  # never worse


def test_improve_pair_balance_flattens_duplicated_blocks():
    v, k = 12, 4
    blocks = _random_complete_cover(v, k, seed=12)
    blocks.extend([list(blocks[0]), list(blocks[0]), list(blocks[1])])
    before = balance_score(v, blocks)
    result = improve_pair_balance(
        v, k, blocks, seed=13, attempts=1, iterations=80_000, seconds_per_attempt=3.0
    )
    after = balance_score(v, result)
    assert after < before  # strictly better on an obviously unbalanced input
    assert after[0] == 0


def test_improve_pair_balance_deterministic_for_seed():
    v, k = 11, 4
    blocks = _random_complete_cover(v, k, seed=14)
    blocks.append(list(blocks[0]))
    kwargs = dict(attempts=1, iterations=30_000, seconds_per_attempt=30.0)
    first = improve_pair_balance(v, k, blocks, seed=21, **kwargs)
    second = improve_pair_balance(v, k, blocks, seed=21, **kwargs)
    assert first == second
