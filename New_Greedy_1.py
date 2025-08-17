import math, random
from typing import List, Tuple

# ---------- utils ----------
def _pair_id(a: int, b: int, n: int) -> int:
    """Unique id in [0, C(n,2)) for unordered pair {a,b} with a != b."""
    if a > b:
        a, b = b, a
    # triangular mapping
    return a * (2*n - a - 1) // 2 + (b - a - 1)

# ---------- helpers ----------
def _remove_redundant(batches, n):
    cov = [[0]*n for _ in range(n)]
    for S in batches:
        for i in range(len(S)):
            a = S[i]
            for j in range(i+1, len(S)):
                b = S[j]
                cov[a][b] += 1
                cov[b][a] += 1
    pruned = []
    for S in batches:
        removable = True
        for i in range(len(S)):
            a = S[i]
            for j in range(i+1, len(S)):
                b = S[j]
                if cov[a][b] < 2:
                    removable = False
                    break
            if not removable:
                break
        if removable:
            for i in range(len(S)):
                a = S[i]
                for j in range(i+1, len(S)):
                    b = S[j]
                    cov[a][b] -= 1
                    cov[b][a] -= 1
        else:
            pruned.append(S)
    return pruned

def _pick_anchor_top_t(rows, deg, T, rng):
    """Pick an uncovered pair (u,v) uniformly at random among the top-T by score=deg[u]+deg[v]."""
    n = len(rows)
    cands = []  # (score, u, v), kept sorted ascending by score, size <= T
    for u in range(n):
        ru = rows[u]
        vmask = ru >> (u+1)
        while vmask:
            tz = (vmask & -vmask).bit_length() - 1
            v = (u + 1) + tz
            score = deg[u] + deg[v]
            if len(cands) < T:
                cands.append((score, u, v))
                if len(cands) == T:
                    cands.sort(key=lambda x: x[0])
            else:
                if score > cands[0][0]:
                    cands[0] = (score, u, v)
                    cands.sort(key=lambda x: x[0])
            vmask &= vmask - 1
    if not cands:
        return None, None
    _, u, v = rng.choice(cands)
    return u, v

def _greedy_cover_once(n, k, rng, top_t=16, lambda_rep=0.1):
    """
    Greedy construction using bitsets + Top-T anchor randomization + replication penalty.
    lambda_rep: penalty weight for over-replicated vertices (0 = off).
    """
    rows = [(((1 << n) - 1) ^ (1 << i)) for i in range(n)]
    uncovered = n*(n-1)//2
    batches = []
    # replication target (how many batches each vertex would appear in under perfect balance)
    target_r = math.ceil((n - 1) / (k - 1))
    rep = [0]*n  # replication counts across batches built so far

    while uncovered > 0:
        deg = [row.bit_count() for row in rows]
        u, v = _pick_anchor_top_t(rows, deg, top_t, rng)
        if u is None:
            break  # safety

        S = [u, v]
        Sset = {u, v}
        while len(S) < k:
            selmask = 0
            for x in S:
                selmask |= (1 << x)

            best_score = -1e18
            best_cands = []
            for c in range(n):
                if c in Sset:
                    continue
                gain = (rows[c] & selmask).bit_count()  # how many still-missing pairs added with S
                if gain == 0 and len(S) < k - 1:
                    # allow zero-gain late, but prefer positive gains strongly
                    score = -1e9
                else:
                    # replication penalty only if rep exceeds target
                    over = max(0, rep[c] - target_r)
                    score = gain - lambda_rep * over
                if score > best_score:
                    best_score = score
                    best_cands = [c]
                elif score == best_score:
                    best_cands.append(c)

            if not best_cands:
                # fallback: pick highest-degree vertex
                pool = [i for i in range(n) if i not in Sset]
                if not pool:
                    break
                maxdeg = max(deg[i] for i in pool)
                best_cands = [i for i in pool if deg[i] == maxdeg]

            c = rng.choice(best_cands)
            S.append(c); Sset.add(c)

        # Mark covered pairs within S
        newcov = 0
        for i in range(len(S)):
            a = S[i]
            for j in range(i+1, len(S)):
                b = S[j]
                if (rows[a] >> b) & 1:
                    rows[a] &= ~(1 << b)
                    rows[b] &= ~(1 << a)
                    newcov += 1
        uncovered -= newcov
        batches.append(S)
        # update replication counts after finalizing the batch
        for x in S:
            rep[x] += 1

    return batches

def _build_cov(batches, n):
    cov = [[0]*n for _ in range(n)]
    for S in batches:
        for i in range(len(S)):
            a = S[i]
            for j in range(i+1, len(S)):
                b = S[j]
                cov[a][b] += 1
                cov[b][a] += 1
    return cov

def _unique_pairs_in_batch(S, cov):
    U = []
    for i in range(len(S)):
        a = S[i]
        for j in range(i+1, len(S)):
            b = S[j]
            if cov[a][b] == 1:
                U.append((a, b))
    return U

def _safe_to_remove_one(S, x, cov):
    for y in S:
        if y == x: continue
        if cov[x][y] < 2:
            return False
    return True

def _safe_to_remove_two(S, x1, x2, cov):
    if x1 == x2: return False
    for y in S:
        if y == x1 or y == x2: continue
        if cov[x1][y] < 2 or cov[x2][y] < 2:
            return False
    if cov[x1][x2] < 2:
        return False
    return True

def _update_cov_for_batch_change(oldS, newS, cov):
    old_set = set(oldS); new_set = set(newS)
    olds = list(old_set)
    news = list(new_set)
    for i in range(len(olds)):
        a = olds[i]
        for j in range(i+1, len(olds)):
            b = olds[j]
            if not (a in new_set and b in new_set):
                cov[a][b] -= 1
                cov[b][a] -= 1
    for i in range(len(news)):
        a = news[i]
        for j in range(i+1, len(news)):
            b = news[j]
            if not (a in old_set and b in old_set):
                cov[a][b] += 1
                cov[b][a] += 1

# ---------- GRASP-style local improvement ----------
def _grasp_local_swap_delete(batches, n, k, max_passes=3):
    if not batches: return batches
    cov = _build_cov(batches, n)

    for _ in range(max_passes):
        removed_any = False
        unique_lists = [_unique_pairs_in_batch(S, cov) for S in batches]
        order = sorted(range(len(batches)), key=lambda i: len(unique_lists[i]))
        to_remove = set()

        for ti in order:
            if ti in to_remove: 
                continue
            T = batches[ti]
            U = [tuple(sorted(p)) for p in unique_lists[ti]]
            if not U:
                for i in range(k):
                    a = T[i]
                    for j in range(i+1, k):
                        b = T[j]
                        cov[a][b] -= 1; cov[b][a] -= 1
                to_remove.add(ti)
                removed_any = True
                continue

            success_all = True
            for (a,b) in U:
                if cov[a][b] != 1:
                    continue
                success = False

                # 1-swap attempts
                for si, S in enumerate(batches):
                    if si == ti or si in to_remove: 
                        continue
                    Sset = set(S)
                    if (a in Sset) ^ (b in Sset):
                        have = a if (a in Sset) else b
                        need = b if have == a else a

                        best_x = None
                        best_margin = -1
                        for x in S:
                            if x == have: 
                                continue
                            if _safe_to_remove_one(S, x, cov):
                                margin = min(cov[x][y] for y in S if y != x)
                                if margin > best_margin:
                                    best_margin = margin
                                    best_x = x
                        if best_x is None:
                            continue

                        oldS = S[:]
                        newS = [y for y in S if y != best_x]
                        if need not in newS:
                            newS.append(need)
                        else:
                            continue

                        _update_cov_for_batch_change(oldS, newS, cov)
                        batches[si] = newS
                        success = True
                        break

                # 2-swap if 1-swap failed
                if not success:
                    for si, S in enumerate(batches):
                        if si == ti or si in to_remove:
                            continue
                        Sset = set(S)
                        if (a in Sset) or (b in Sset):
                            continue
                        found = False
                        for i in range(k):
                            x1 = S[i]
                            for j in range(i+1, k):
                                x2 = S[j]
                                if not _safe_to_remove_two(S, x1, x2, cov):
                                    continue
                                oldS = S[:]
                                newS = [y for y in S if y != x1 and y != x2] + [a, b]
                                _update_cov_for_batch_change(oldS, newS, cov)
                                batches[si] = newS
                                found = True
                                break
                            if found:
                                break
                        if found:
                            success = True
                            break

                if not success:
                    success_all = False
                    break

            if success_all:
                for i in range(k):
                    x = T[i]
                    for j in range(i+1, k):
                        y = T[j]
                        cov[x][y] -= 1; cov[y][x] -= 1
                to_remove.add(ti)
                removed_any = True

        if not removed_any:
            break

        batches = [batches[i] for i in range(len(batches)) if i not in to_remove]

    return batches

# ---------- coverage repair ----------
def _repair_missing_pairs(batches, n, k):
    rows = [(((1 << n) - 1) ^ (1 << i)) for i in range(n)]
    for S in batches:
        for i in range(len(S)):
            a = S[i]
            for j in range(i+1, len(S)):
                b = S[j]
                if (rows[a] >> b) & 1:
                    rows[a] &= ~(1 << b)
                    rows[b] &= ~(1 << a)

    def build_batch_for_anchor(a,b):
        S = [a,b]
        Sset = {a,b}
        while len(S) < k:
            selmask = 0
            for x in S: selmask |= (1 << x)
            best_gain, best_c = -1, None
            for c in range(n):
                if c in Sset: continue
                gain = (rows[c] & selmask).bit_count()
                if gain > best_gain:
                    best_gain, best_c = gain, c
            if best_c is None:
                pool = [i for i in range(n) if i not in Sset]
                if not pool: break
                best_c = max(pool, key=lambda i: rows[i].bit_count())
            S.append(best_c); Sset.add(best_c)
        return S

    while True:
        anchor = None
        for a in range(n):
            ru = rows[a] >> (a+1)
            if ru:
                b = (ru & -ru).bit_length() - 1
                b = (a + 1) + b
                anchor = (a,b); break
        if anchor is None:
            break
        a,b = anchor
        S = build_batch_for_anchor(a,b)
        for i in range(len(S)):
            x = S[i]
            for j in range(i+1, len(S)):
                y = S[j]
                if (rows[x] >> y) & 1:
                    rows[x] &= ~(1 << y)
                    rows[y] &= ~(1 << x)
        batches.append(S)

    return batches

# ---------- reselect (cheap set-cover over existing batches) ----------
def _reselect_min_cover_over_existing(batches, n, k):
    """
    Given a covering family (list of batches) that already covers all pairs,
    greedily re-select a smaller subset of those batches to cover all pairs.
    This is often strictly better than 'remove redundant' alone.
    """
    if not batches:
        return batches
    M = n*(n-1)//2
    # Precompute each batch's pair-bitmask
    masks = []
    for S in batches:
        m = 0
        for i in range(len(S)):
            a = S[i]
            for j in range(i+1, len(S)):
                b = S[j]
                m |= 1 << _pair_id(a, b, n)
        masks.append(m)

    all_pairs_mask = (1 << M) - 1
    uncovered = all_pairs_mask
    # quick sanity: if family doesn't cover all pairs (shouldn't happen), just return original
    fam_mask = 0
    for m in masks:
        fam_mask |= m
    if fam_mask != all_pairs_mask:
        return batches

    remaining = list(range(len(batches)))
    selected_idx = []
    # Standard greedy set cover on the restricted family
    while uncovered:
        best_i = None
        best_gain = -1
        for idx in remaining:
            gain = (masks[idx] & uncovered).bit_count()
            if gain > best_gain:
                best_gain = gain
                best_i = idx
        if best_i is None or best_gain == 0:
            # should not happen if fam_mask==all_pairs_mask
            break
        selected_idx.append(best_i)
        uncovered &= ~masks[best_i]
        remaining.remove(best_i)

    # Build new batch list
    return [batches[i] for i in selected_idx]

# ---------- bounds ----------
def lower_bounds(n, k):
    total_pairs = n*(n-1)//2
    pairs_per_batch = k*(k-1)//2
    lb_naive = math.ceil(total_pairs / pairs_per_batch)
    lb_schoenheim = math.ceil((n / k) * math.ceil((n-1) / (k-1)))
    return lb_naive, lb_schoenheim

# ---------- public API ----------
def generate_batches(Arr: List[int], batch_size: int, *,
                     restarts: int = 64,
                     seed: int = 0,
                     prune: bool = True,
                     grasp_passes: int = 2,
                     top_t: int = 16,
                     repair: bool = True,
                     lambda_rep: float = 0.1,
                     reselect: bool = True):
    """
    Greedy+bitset covering with Top-T anchor selection, replication balancing,
    GRASP local swaps, coverage repair, re-selection over existing batches,
    and early exit at the Schönheim bound.

    Args:
      Arr: sorted unique labels
      batch_size: k
      restarts: number of randomized greedy runs; best kept solution is used
      seed: RNG seed
      prune: remove redundant batches after construction / local search
      grasp_passes: number of local-search passes (0 to disable)
      top_t: size of the Top-T pool for anchor selection (diversifies choices)
      repair: ensure coverage by adding minimal greedy batches if anything is missing
      lambda_rep: replication penalty (>=0). 0.1–0.3 is a sensible range.
      reselect: run restricted set-cover over existing batches to shrink the set

    Returns:
      List[List[int]] of labels from Arr
    """
    n = len(Arr)
    rng = random.Random(seed)
    best_batches = None
    best_len = 10**9

    lb_naive, lb_sch = lower_bounds(n, batch_size)

    for _ in range(restarts):
        batches = _greedy_cover_once(n, batch_size, rng, top_t=top_t, lambda_rep=lambda_rep)
        if prune:
            batches = _remove_redundant(batches, n)
        if grasp_passes > 0:
            batches = _grasp_local_swap_delete(batches, n, batch_size, max_passes=grasp_passes)
            if prune:
                batches = _remove_redundant(batches, n)

        if repair:
            batches = _repair_missing_pairs(batches, n, batch_size)
            if prune:
                batches = _remove_redundant(batches, n)

        if reselect:
            batches = _reselect_min_cover_over_existing(batches, n, batch_size)
            if prune:
                batches = _remove_redundant(batches, n)

        if len(batches) < best_len:
            best_len = len(batches)
            best_batches = batches

        if best_len <= lb_sch:
            break

        rng.seed(rng.getrandbits(64))

    # Map back to labels
    label_map = {i: Arr[i] for i in range(n)}
    return [[label_map[i] for i in batch] for batch in best_batches]

# ---- sanity helpers ----
def verify_coverage(batches, Arr):
    idx = {v:i for i,v in enumerate(Arr)}
    n = len(Arr)
    seen = [[0]*n for _ in range(n)]
    for B in batches:
        for i in range(len(B)):
            a = idx[B[i]]
            for j in range(i+1, len(B)):
                b = idx[B[j]]
                seen[a][b] += 1
                seen[b][a] += 1
    missing = []
    for a in range(n):
        for b in range(a+1, n):
            if seen[a][b] == 0:
                missing.append((Arr[a], Arr[b]))
    return missing

if __name__ == "__main__":
    import time
    items = list(range(25))
    k = 8

    lb_naive, lb_sch = lower_bounds(len(items), k)

    t0 = time.time()
    batches = generate_batches(items, k,
                               restarts=128,
                               seed=0,
                               prune=True,
                               grasp_passes=3,
                               top_t=16,
                               repair=True,
                               lambda_rep=0.2,      
                               reselect=True)
    elapsed = time.time() - t0

    print(f"Solved in {elapsed:.2f}s – {len(batches)} batches")
    print(f"Schoenheim Lower bound: {lb_sch}")
    print("Coverage missing pairs:", verify_coverage(batches, items))

