"""Fixed schedules with a chosen number of trials beyond the compact cover.

``budget_schedule(n_items, batch_size, n_trials, seed)`` returns exactly ``n_trials`` trials of ``batch_size``
items that together show every pair. The extra trials go to the least-observed pairs:

* two starting covers are tried: the flattest portfolio cover with at most ``n_trials`` trials (the selection rule
  of the balanced mode, with the budget as its limit) and the compact cover;
* each is extended by randomly relabelled copies of itself while whole copies fit, so that every pair appears in
  each copy, then by greedy trials on the least-observed pairs;
* the result with the smaller sum of 1/lambda over pairs (the average variance under the equal-variance model of
  the paper) is returned.

A local search then flattens the added trials only, swapping points while the sum of squared pair concurrences does
not increase, so the starting cover and its coverage are kept. This is the balanced arm of the paper's third
simulation study (sim_surplus.py), with the same code.
"""
from typing import List
from collections import Counter
from itertools import combinations
from math import comb

import numpy as np

from .schedule_cache import load_indexed_schedule


def budget_schedule(n_items: int, batch_size: int, n_trials: int, seed: int = 42) -> List[List[int]]:
    """Schedule of exactly ``n_trials`` trials that shows every pair, spending the trials beyond the compact cover on
    the least-observed pairs."""
    v, k, target = int(n_items), int(batch_size), int(n_trials)
    comp = load_indexed_schedule(v, k, mode="compact")
    if comp is None:
        raise ValueError(f"no indexed schedule for {v} items in trials of {k}")
    if target < len(comp):
        raise ValueError(f"n_trials must be at least {len(comp)}, the length of the indexed compact schedule for "
                         f"{v} items in trials of {k}")
    if target > comb(v, k):
        raise ValueError(f"only {comb(v, k)} distinct trials of {k} of {v} items exist")
    return balanced_design(v, k, flattest_within(v, k, target), target, np.random.default_rng(seed),
                           compact=comp)


def flattest_within(v: int, k: int, max_blocks: int) -> List[List[int]]:
    """The flattest portfolio cover with at most ``max_blocks`` trials."""
    from pathlib import Path

    import multiarrangement as ma
    from coverlib.frontier import select_frontier_cover

    package = Path(ma.__file__).resolve().parent
    sel = select_frontier_cover(v, k, package_dir=package, mode="balanced", max_blocks=int(max_blocks))
    if sel is None or not sel.certificate.complete or not sel.certificate.simple:
        raise ValueError(f"no complete portfolio cover with at most {max_blocks} trials for ({v},{k})")
    return [list(b) for b in sel.blocks]


def balanced_design(v, k, base, target, rng, compact=None):
    """Extra trials for a fixed budget. Two candidates are built: the flattest portfolio cover that fits (base) and,
    when it differs, the compact cover, each extended by relabelled copies of itself while whole copies fit and then
    by greedy trials on the least-observed pairs. The candidate with the smaller sum of 1/lambda over pairs (the
    average variance under the equal-variance model) is kept; the flatter descending concurrence vector breaks ties.
    No trial is repeated."""
    cands = [extend_cover(v, k, base, target, rng)]
    if compact is not None and sorted(sorted(B) for B in compact) != sorted(sorted(B) for B in base):
        cands.append(extend_cover(v, k, compact, target, rng))
    return min(cands, key=lambda bl: (inverse_load(v, bl), descending_profile(v, bl)))


def concurrence(v, blocks):
    lam = np.zeros((v, v), dtype=int)
    for B in blocks:
        for a in B:
            for b in B:
                if a != b:
                    lam[a, b] += 1
    return lam


def inverse_load(v, blocks):
    """Sum of 1/lambda over all pairs (every pair is covered)."""
    lam = concurrence(v, blocks)[np.triu_indices(v, 1)]
    return float(np.sum(1.0 / lam))


def descending_profile(v, blocks):
    return tuple(sorted(concurrence(v, blocks)[np.triu_indices(v, 1)].tolist(), reverse=True))


def extend_cover(v, k, base, target, rng):
    """base plus randomly relabelled copies of it while whole copies fit, each copy flattened by local search with
    the earlier trials kept, then greedy trials on the least-observed pairs."""
    blocks = [list(B) for B in base]
    copies = 1
    while len(blocks) + len(base) <= target:
        copies += 1
        seen = {tuple(sorted(B)) for B in blocks}
        perm = rng.permutation(v)
        fixed = len(blocks)
        for B in base:
            t = tuple(sorted(int(perm[x]) for x in B))
            if t in seen:  # the relabelled trial repeats one already present (small settings only)
                t = fresh_trial(v, k, seen, rng)
            seen.add(t)
            blocks.append(list(t))
        flat = flatten(v, blocks, fixed, concurrence(v, blocks), rng, iters=400000, floor=copies)
        if inverse_load(v, flat) <= inverse_load(v, blocks):  # flattening must not cost average precision
            blocks = flat
    return balanced_padding(v, k, blocks, target, rng) if len(blocks) < target else blocks

def fresh_trial(v, k, seen, rng):
    """A random trial of k items that is not in ``seen``."""
    for _ in range(1000):
        t = tuple(sorted(rng.choice(v, k, replace=False).tolist()))
        if t not in seen:
            return t
    for t in combinations(range(v), k):
        if t not in seen:
            return t
    raise ValueError(f"all {comb(v, k)} trials of {k} of {v} items are already used")


def balanced_padding(v, k, blocks, target, rng):
    """Add greedy trials, each started from a least-observed pair and grown by the item that joins the most
    least-observed pairs, until there are ``target`` trials; then flatten the added trials."""
    lam = np.zeros((v, v), dtype=int)
    for B in blocks:
        for a in B:
            for b in B:
                if a != b:
                    lam[a, b] += 1
    out = [list(B) for B in blocks]
    seen = {tuple(sorted(B)) for B in blocks}
    iu = np.triu_indices(v, 1)
    while len(out) < target:
        vals = lam[iu]
        m = vals.min()
        cand = np.flatnonzero(vals == m)
        p = cand[rng.integers(len(cand))]
        trial = [int(iu[0][p]), int(iu[1][p])]
        while len(trial) < k:
            rest = np.setdiff1d(np.arange(v), trial)
            gain = np.array([sum(lam[x, y] == m for y in trial) for x in rest], dtype=float)
            gain += 1e-3 * rng.random(len(rest))
            trial.append(int(rest[np.argmax(gain)]))
        t = tuple(sorted(trial))
        if t in seen:
            t = fresh_trial(v, k, seen, rng)
        seen.add(t)
        for a in t:
            for b in t:
                if a != b:
                    lam[a, b] += 1
        out.append(list(t))
    return flatten(v, out, len(blocks), lam, rng)


def flatten(v, blocks, fixed, lam, rng, iters=60000, floor=1):
    """Local search on the added trials only (the starting cover keeps coverage): swap a point of an added trial
    for an outside point whenever the sum of squared concurrences does not increase, no pair drops below ``floor``
    and no trial is repeated."""
    blocks = [list(B) for B in blocks]
    if len(blocks) <= fixed:
        return blocks
    seen = Counter(tuple(sorted(B)) for B in blocks)
    for _ in range(iters):
        t = int(rng.integers(fixed, len(blocks)))
        B = blocks[t]
        i = int(rng.integers(len(B)))
        p = B[i]
        q = int(rng.integers(v))
        if q in B:
            continue
        others = [x for x in B if x != p]
        # change in sum over ordered pairs of lam^2 when p is replaced by q in this trial
        delta = sum((lam[q, y] + 1) ** 2 - lam[q, y] ** 2 + (lam[p, y] - 1) ** 2 - lam[p, y] ** 2 for y in others)
        if delta <= 0 and all(lam[p, y] > floor for y in others):
            new = tuple(sorted(others + [q]))
            if seen[new] > 0:
                continue
            seen[tuple(sorted(B))] -= 1
            seen[new] += 1
            for y in others:
                lam[p, y] -= 1
                lam[y, p] -= 1
                lam[q, y] += 1
                lam[y, q] += 1
            B[i] = q
    return [sorted(B) for B in blocks]


def load_repeat_design(v: int, k: int, r: int, mode: str = "compact"):
    """A searched design from ``repeat_cache/`` in which every pair is shown at least r times, verified on load; None
    when there is none or it fails the check. The index maps "v,k,r" to one entry per mode, each naming a file (plain
    or .gz) of one trial per line: ``compact`` is the fewest trials found, evened out, and ``balanced`` the most even
    schedule found with at most 25% more trials than that."""
    import json
    from pathlib import Path

    import multiarrangement as ma

    folder = Path(ma.__file__).resolve().parent / "repeat_cache"
    try:
        entry = json.loads((folder / "index.json").read_text(encoding="utf-8")).get(f"{v},{k},{r}")
        if entry and "path" not in entry:
            entry = entry.get(mode)
        if not entry:
            return None
        path = folder / entry["path"]
        if path.suffix == ".gz":
            import gzip

            text = gzip.decompress(path.read_bytes()).decode("ascii")
        else:
            text = path.read_text()
        blocks = [[int(x) for x in line.split()] for line in text.splitlines() if line.strip()]
    except (OSError, ValueError, KeyError):
        return None
    if not blocks or any(len(B) != k or len(set(B)) != k or min(B) < 0 or max(B) >= v for B in blocks):
        return None
    if len({tuple(sorted(B)) for B in blocks}) != len(blocks):
        return None
    lam = concurrence(v, blocks)
    if lam[np.triu_indices(v, 1)].min() < r:
        return None
    return blocks


def repeat_schedule(n_items: int, batch_size: int, repeats: int, seed: int = 42,
                    mode: str = "compact") -> List[List[int]]:
    """Schedule in which every pair is shown at least ``repeats`` times.

    The searched designs of ``repeat_cache/`` are used when available: in ``compact`` mode the fewest trials found,
    evened out, and in ``balanced`` mode the most even schedule found with at most 25% more trials than that, perfectly
    balanced where such a design was found. Otherwise ``repeats`` randomly relabelled copies of the compact cover are
    used, each chosen so that no trial repeats an earlier one, evened out by the local search without letting any pair
    fall below the number of copies. Raises ValueError when the setting has too few distinct trials for that many
    copies."""
    v, k, r = int(n_items), int(batch_size), int(repeats)
    if r < 1:
        raise ValueError("repeats must be at least 1")
    if mode not in ("compact", "balanced"):
        raise ValueError("mode must be 'compact' or 'balanced'")
    comp = load_indexed_schedule(v, k, mode="compact")
    if comp is None:
        raise ValueError(f"no indexed schedule for {v} items in trials of {k}")
    if r == 1:
        return [list(B) for B in comp]
    searched = load_repeat_design(v, k, r, mode)
    if searched is not None and (mode == "balanced" or len(searched) <= r * len(comp)):
        return searched
    if r * len(comp) > comb(v, k):
        raise ValueError(f"only {comb(v, k)} distinct trials of {k} of {v} items exist, fewer than {r} copies of the "
                         f"{len(comp)}-trial compact schedule")
    rng = np.random.default_rng(seed)
    blocks = [list(B) for B in comp]
    for copies in range(2, r + 1):
        seen = {tuple(sorted(B)) for B in blocks}
        for _ in range(20000):
            perm = rng.permutation(v)
            new = [tuple(sorted(int(perm[x]) for x in B)) for B in comp]
            if not seen.intersection(new):
                break
        else:
            raise ValueError(f"could not relabel copy {copies} of the compact schedule for ({v},{k}) without repeating "
                             f"a trial")
        fixed = len(blocks)
        blocks.extend(list(t) for t in new)
        flat = flatten(v, blocks, fixed, concurrence(v, blocks), rng, iters=400000, floor=copies)
        if inverse_load(v, flat) <= inverse_load(v, blocks):
            blocks = flat
    # final pass over all trials (the first copy included), never letting a pair fall below r
    flat = flatten(v, blocks, 0, concurrence(v, blocks), rng, iters=400000, floor=r)
    if inverse_load(v, flat) <= inverse_load(v, blocks) and len({tuple(sorted(B)) for B in flat}) == len(flat):
        blocks = flat
    lam = concurrence(v, blocks)
    iu = np.triu_indices(v, 1)
    if lam[iu].min() < r or len({tuple(sorted(B)) for B in blocks}) != len(blocks):
        raise ValueError(f"internal check failed for ({v},{k}) with {r} repeats")
    return blocks
