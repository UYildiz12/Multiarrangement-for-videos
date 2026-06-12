"""General prescribed-automorphism (orbit) sweep for balanced pair covers.

For every open case (v, k, b) from the LJCR balance sweep, enumerate symmetric
plans: full orbits of m base blocks under a cyclic action <+s> on either
  - plain model:  points Z_v
  - rot1 model:   points Z_{v-1} plus a fixed point (the "infinity" item)
and search base blocks by DFS with exact orbit-weighted class accounting.

Budgets are measured in process CPU time, so machine sleep merely pauses the
run instead of burning the budget. Every found schedule is expanded and
independently re-verified before being written to the staging directory as a
cache file in repo format (v{v}_k{k}_b{b'}.txt, zero-based, space-separated).

Usage:
  python orbit_sweep.py test             # quick engine self-test
  python orbit_sweep.py known            # emit pre-verified known solutions
  python orbit_sweep.py case V K         # attack one case with a long budget
  python orbit_sweep.py all              # full sweep, worst-ratio-first
  python orbit_sweep.py all I N          # shard I of N (I = 0..N-1)
"""

import json
import math
import os
import random
import sys
import time
import traceback
from itertools import combinations
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
SWEEP_JSONL = Path(os.environ.get(
    "MA_SWEEP_JSONL",
    _REPO_ROOT / "docs" / "ljcr_balance_sweep_results_v2.jsonl"))
OUT_DIR = Path(os.environ.get("MA_OUT_DIR", _REPO_ROOT / "orbit_out"))

CASE_BUDGET_S = 75.0       # CPU-seconds per case in 'all' mode
FLAG_BUDGET_S = 240.0      # CPU-seconds for 'case' mode and worst offenders
SLICE_S = 3.0              # one randomized restart slice (CPU-seconds)
MAX_BASE_BLOCKS = 12

clock = time.process_time

# Pre-verified known solutions (model, s, base blocks). 86x6 from the
# difference-method construction, hand- and machine-verified.
KNOWN = {
    (86, 6): ("plain", 1, [(0, 11, 24, 38, 50, 66),
                           (0, 2, 5, 35, 45, 54),
                           (0, 1, 8, 65, 69, 71)]),
}


# ---------------------------------------------------------------- structures

def build_points(v, model):
    """Return (n_finite, points, inf_point). Items are 0..v-1; in the rot1
    model item v-1 plays the fixed point."""
    if model == "plain":
        return v, list(range(v)), None
    return v - 1, list(range(v)), v - 1


def pair_classes(v, model, s):
    """Class id, class size, and inc (concurrence added to every pair of the
    class per base-block occurrence) for all pairs under x -> x+s."""
    n, _, infp = build_points(v, model)
    g = n // s

    def shift(x):
        return x if x == infp else (x + s) % n

    cid = {}
    sizes = []
    for x in range(v):
        for y in range(x + 1, v):
            if (x, y) in cid:
                continue
            members = set()
            a, c = x, y
            while True:
                members.add((a, c) if a < c else (c, a))
                a, c = shift(a), shift(c)
                key = (a, c) if a < c else (c, a)
                if key == (x, y):
                    break
            oid = len(sizes)
            for mkey in members:
                cid[mkey] = oid
            sizes.append(len(members))
    incs = []
    for sz in sizes:
        if g % sz:
            return None  # non-uniform action; reject structure
        incs.append(g // sz)
    return cid, sizes, incs


def enumerate_plans(v, k, b, cap, pc_cache):
    """All structurally feasible (model, s, g, m, slack) plans."""
    kp = k * (k - 1) // 2
    r_min = math.ceil((v - 1) / (k - 1))     # Schonheim item degree floor
    plans = []
    for model in ("plain", "rot1"):
        n = v if model == "plain" else v - 1
        if n < 2:
            continue
        for s in range(1, n + 1):
            if n % s:
                continue
            g = n // s
            if g < 4:
                continue
            m = b // g
            if m == 0 or m > MAX_BASE_BLOCKS:
                continue
            if m * g * k < v * r_min:        # below covering item-degree floor
                continue
            key = (model, s)
            if key not in pc_cache:
                pc_cache[key] = pair_classes(v, model, s)
            pc = pc_cache[key]
            if pc is None:
                continue
            cid, sizes, incs = pc
            n_classes = len(sizes)
            slots = m * kp
            slack = slots - n_classes
            if slack < 0:
                continue
            if any(cap // inc < 1 for inc in incs):
                continue
            if slots > sum(cap // inc for inc in incs):
                continue
            plans.append({"model": model, "s": s, "g": g, "m": m,
                          "slack": slack, "classes": n_classes,
                          "cid": cid, "incs": incs})
    # prefer high symmetry (large g) and breathing room (slack), few blocks
    plans.sort(key=lambda p: (-p["g"], -min(p["slack"], 8), p["m"]))
    return plans


# -------------------------------------------------------------------- search

class _Timeout(Exception):
    pass


def search_plan(v, k, cap, plan, deadline, rng):
    """Randomized-restart DFS for the plan's base blocks. Returns base blocks
    or None. Deadline is in process CPU seconds."""
    model, s, m = plan["model"], plan["s"], plan["m"]
    n, _, infp = build_points(v, model)
    g = n // s
    cid, incs = plan["cid"], plan["incs"]
    n_classes = plan["classes"]
    slack = plan["slack"]
    cap_c = [cap // inc for inc in incs]

    # flat pair->class table
    table = [[0] * v for _ in range(v)]
    for (x, y), c in cid.items():
        table[x][y] = c
        table[y][x] = c

    anchors = list(range(s)) + ([infp] if infp is not None else [])

    def one_restart(slice_deadline):
        occ = [0] * n_classes
        covered = 0
        extra = 0
        blocks = []
        block = []
        node = 0

        def grow(bi):
            nonlocal covered, extra, node
            node += 1
            if not node % 2048 and clock() > slice_deadline:
                raise _Timeout
            if len(block) == k:
                bb = tuple(sorted(block))
                # reject blocks with nontrivial stabilizer (short orbits)
                for j in range(1, g):
                    if bb == tuple(sorted(
                            x if x == infp else (x + j * s) % n for x in bb)):
                        return None
                blocks.append(bb)
                if bi + 1 == m:
                    if covered == n_classes:
                        return list(blocks)
                    blocks.pop()
                    return None
                saved = block[:]
                res = grow_block(bi + 1)
                if res is None:
                    blocks.pop()
                    block[:] = saved
                return res
            cands = []
            for e in (anchors if not block else range(v)):
                if e in block:
                    continue
                new = 0
                ok = True
                add = 0
                for x in block:
                    c = table[x][e]
                    if occ[c] + 1 > cap_c[c]:
                        ok = False
                        break
                    if occ[c] == 0:
                        new += 1
                    else:
                        add += 1
                if not ok or extra + add > slack:
                    continue
                cands.append((new, rng.random(), e))
            cands.sort(reverse=True)
            for _, _, e in cands:
                bumped = []
                for x in block:
                    c = table[x][e]
                    occ[c] += 1
                    if occ[c] == 1:
                        covered += 1
                    else:
                        extra += 1
                    bumped.append(c)
                block.append(e)
                res = grow(bi)
                if res is not None:
                    return res
                block.pop()
                for c in bumped:
                    if occ[c] == 1:
                        covered -= 1
                    else:
                        extra -= 1
                    occ[c] -= 1
            return None

        def grow_block(bi):
            block.clear()
            return grow(bi)

        return grow_block(0)

    while clock() < deadline:
        try:
            res = one_restart(min(deadline, clock() + SLICE_S))
        except _Timeout:
            continue
        if res is not None:
            return res
    return None


# ------------------------------------------------------------------ annealer

MISS_W = 1000        # cost per uncovered pair
OVER_W = 120         # cost per squared unit of concurrence above cap
R_TAIL_MAX = 60      # largest free tail worth annealing
RESTART_S = 20.0     # CPU-seconds per annealing restart


def enumerate_anneal_plans(v, k, b_allowed, pc_cache):
    """Orbit-core (+ optional free-tail) plans with actual trial count
    b' <= b_allowed. Pure-orbit plans (no tail) are preferred: they give
    uniform concurrence and near-uniform item usage by construction."""
    kp = k * (k - 1) // 2
    r_min = math.ceil((v - 1) / (k - 1))     # Schonheim item degree floor
    # small k covers few classes per block, so allow more base blocks
    max_m = {3: 28, 4: 20, 5: 16}.get(k, MAX_BASE_BLOCKS)
    plans = []
    for model in ("plain", "rot1"):
        n = v if model == "plain" else v - 1
        if n < 4:
            continue
        for s in range(1, n + 1):
            if n % s:
                continue
            g = n // s
            if g < 4:
                continue
            m_hi = min(b_allowed // g, max_m)
            if m_hi == 0:
                continue
            key = (model, s)
            if key not in pc_cache:
                pc_cache[key] = pair_classes(v, model, s)
            pc = pc_cache[key]
            if pc is None:
                continue
            cid, sizes, incs = pc
            n_classes = len(sizes)
            m_lo = None
            for m in range(1, m_hi + 1):
                if m * kp >= n_classes and m * g * k >= v * r_min:
                    m_lo = m
                    break
            if m_lo is not None:
                # pure orbits: smallest covering m, plus one extra for slack
                for m in (m_lo, m_lo + 1):
                    if m > m_hi:
                        continue
                    plans.append({"model": model, "s": s, "g": g, "m": m,
                                  "r": 0, "bprime": m * g,
                                  "classes": n_classes, "cid": cid,
                                  "sizes": sizes, "incs": incs,
                                  "slack": m * kp - n_classes})
            else:
                # orbits cannot cover alone: max orbits plus a free tail
                m = m_hi
                r = b_allowed - m * g
                uncov = n_classes - m * kp
                if (0 < r <= min(R_TAIL_MAX, int(0.45 * b_allowed))
                        and uncov * g <= r * kp):
                    plans.append({"model": model, "s": s, "g": g, "m": m,
                                  "r": r, "bprime": m * g + r,
                                  "classes": n_classes, "cid": cid,
                                  "sizes": sizes, "incs": incs,
                                  "slack": r * kp - uncov * g})
    # easiest first (slack), then fewer trials, then more symmetry
    plans.sort(key=lambda p: (p["r"] > 0, -min(p["slack"], 12),
                              p["bprime"], -p["g"]))
    return plans[:8]


def anneal_plan(v, k, cap, plan, budget_s, rng):
    """Simulated annealing over m base blocks (orbit core) plus r free tail
    blocks. Integer-exact incremental cost; returns a fully verified schedule
    or None."""
    model, s, m, r = plan["model"], plan["s"], plan["m"], plan["r"]
    n, _, infp = build_points(v, model)
    g = n // s
    cid, sizes, incs = plan["cid"], plan["sizes"], plan["incs"]
    n_classes = plan["classes"]

    table = [[0] * v for _ in range(v)]
    for (x, y), c in cid.items():
        table[x][y] = c
        table[y][x] = c
    # partner lookup: partners[x][c] = elements e with class(x, e) == c
    partners = [dict() for _ in range(v)]
    for (x, y), c in cid.items():
        partners[x].setdefault(c, []).append(y)
        partners[y].setdefault(c, []).append(x)

    deadline = clock() + budget_s
    p_tail = 0.8 * r / (m + r) if r else 0.0

    state_fresh = True
    while clock() < deadline:
        if not state_fresh:
            # reheat: keep the near-feasible state, just raise temperature
            solved = run_slice(min(deadline, clock() + RESTART_S),
                               max(500.0, cost() * 0.5))
            if solved is not None:
                return solved
            state_fresh = not (len(miss_classes) <= 2 and tot[1] <= 6)
            continue
        base = [rng.sample(range(v), k) for _ in range(m)]
        tail = [rng.sample(range(v), k) for _ in range(r)]
        occ = [0] * n_classes
        for blk in base:
            for a, c2 in combinations(blk, 2):
                occ[table[a][c2]] += 1
        tpair = {}
        tcls = {}
        for blk in tail:
            for a, c2 in combinations(blk, 2):
                p = (a, c2) if a < c2 else (c2, a)
                tpair[p] = tpair.get(p, 0) + 1
                tcls.setdefault(table[a][c2], {})[p] = tpair[p]
        missA = [0] * n_classes
        overA = [0] * n_classes
        ssA = [0] * n_classes
        tot = [0, 0, 0]  # miss, over, ss (exact integers)
        miss_classes = set()

        def recompute(c):
            lam = occ[c] * incs[c]
            d = tcls.get(c)
            n0 = sizes[c] - (len(d) if d else 0)
            mi = n0 if lam == 0 else 0
            e = lam - cap
            ov = n0 * e * e if e > 0 else 0
            ss = n0 * lam * lam
            if d:
                for p, tp in d.items():
                    l2 = lam + tp
                    if l2 == 0:
                        mi += 1
                    e2 = l2 - cap
                    if e2 > 0:
                        ov += e2 * e2
                    ss += l2 * l2
            tot[0] += mi - missA[c]
            missA[c] = mi
            tot[1] += ov - overA[c]
            overA[c] = ov
            tot[2] += ss - ssA[c]
            ssA[c] = ss
            if mi:
                miss_classes.add(c)
            else:
                miss_classes.discard(c)

        for c in range(n_classes):
            recompute(c)

        def cost():
            return MISS_W * tot[0] + OVER_W * tot[1] + tot[2]

        def apply_core(i, pos, e):
            blk = base[i]
            old = blk[pos]
            touched = set()
            for q, x in enumerate(blk):
                if q == pos:
                    continue
                c_out = table[x][old]
                c_in = table[x][e]
                occ[c_out] -= 1
                occ[c_in] += 1
                touched.add(c_out)
                touched.add(c_in)
            blk[pos] = e
            for c in touched:
                recompute(c)
            return old

        def apply_tail(j, pos, e):
            blk = tail[j]
            old = blk[pos]
            touched = set()
            for q, x in enumerate(blk):
                if q == pos:
                    continue
                p_out = (x, old) if x < old else (old, x)
                c_out = table[x][old]
                cnt = tpair.get(p_out, 0) - 1
                if cnt > 0:
                    tpair[p_out] = cnt
                    tcls[c_out][p_out] = cnt
                else:
                    tpair.pop(p_out, None)
                    d = tcls.get(c_out)
                    if d is not None:
                        d.pop(p_out, None)
                        if not d:
                            tcls.pop(c_out, None)
                p_in = (x, e) if x < e else (e, x)
                c_in = table[x][e]
                tpair[p_in] = tpair.get(p_in, 0) + 1
                tcls.setdefault(c_in, {})[p_in] = tpair[p_in]
                touched.add(c_out)
                touched.add(c_in)
            blk[pos] = e
            for c in touched:
                recompute(c)
            return old

        def run_slice(slice_end, T0):
            T = T0
            it = 0
            start = clock()
            span = max(0.5, slice_end - start)
            while True:
                it += 1
                if not it % 512:
                    now = clock()
                    if now > slice_end:
                        return None
                    frac = (now - start) / span
                    T = T0 * (2.0 / T0) ** max(0.0, min(1.0, frac))
                before = cost()
                if miss_classes and rng.random() < 0.6:
                    # guided repair: cover a missing class with the exact
                    # partner element that produces it
                    c_tgt = next(iter(miss_classes))
                    i = rng.randrange(m)
                    blk = base[i]
                    x = blk[rng.randrange(k)]
                    opts = partners[x].get(c_tgt)
                    if not opts:
                        continue
                    e = opts[rng.randrange(len(opts))]
                    if e in blk:
                        continue
                    pos = rng.randrange(k)
                    if blk[pos] == x:
                        pos = (pos + 1) % k
                        if blk[pos] == x:
                            continue
                    old = apply_core(i, pos, e)
                    delta = cost() - before
                    if delta > 0 and rng.random() >= math.exp(-delta / T):
                        apply_core(i, pos, old)
                elif r and rng.random() < p_tail:
                    j = rng.randrange(r)
                    pos = rng.randrange(k)
                    e = rng.randrange(v)
                    if e in tail[j]:
                        continue
                    old = apply_tail(j, pos, e)
                    delta = cost() - before
                    if delta > 0 and rng.random() >= math.exp(-delta / T):
                        apply_tail(j, pos, old)
                else:
                    i = rng.randrange(m)
                    pos = rng.randrange(k)
                    e = rng.randrange(v)
                    if e in base[i]:
                        continue
                    old = apply_core(i, pos, e)
                    delta = cost() - before
                    if delta > 0 and rng.random() >= math.exp(-delta / T):
                        apply_core(i, pos, old)
                if tot[0] == 0 and tot[1] == 0:
                    try:
                        core = expand(v, model, s,
                                      [tuple(sorted(b_)) for b_ in base])
                        full = core + [tuple(sorted(t_)) for t_ in tail]
                        if len(set(full)) != len(full):
                            raise ValueError("duplicate blocks")
                        lmax, hist, use = verify(v, k, full, cap)
                        return base, tail, full, lmax, hist, use
                    except Exception:
                        # stabilized orbit or duplicate: force perturbation
                        i = rng.randrange(m)
                        pos = rng.randrange(k)
                        choices = [e for e in range(v)
                                   if e not in base[i]]
                        apply_core(i, pos, rng.choice(choices))

        solved = run_slice(min(deadline, clock() + RESTART_S),
                           max(500.0, cost() * 0.02))
        if solved is not None:
            return solved
        if os.environ.get("MA_DEBUG"):
            print(f"    slice end: miss={tot[0]} ({len(miss_classes)} cls) "
                  f"over={tot[1]} ss={tot[2]} t={clock():.1f}", flush=True)
        state_fresh = not (len(miss_classes) <= 2 and tot[1] <= 6)
    return None


def expand(v, model, s, base_blocks):
    n, _, infp = build_points(v, model)
    g = n // s
    seen = set()
    out = []
    for bb in base_blocks:
        for j in range(g):
            blk = tuple(sorted(
                x if x == infp else (x + j * s) % n for x in bb))
            if blk in seen:
                raise ValueError("duplicate block on expansion")
            seen.add(blk)
            out.append(blk)
    return out


def verify(v, k, blocks, cap):
    counts = {}
    for blk in blocks:
        assert len(blk) == k and len(set(blk)) == k
        for p in combinations(blk, 2):
            counts[p] = counts.get(p, 0) + 1
    n_pairs = v * (v - 1) // 2
    if len(counts) != n_pairs:
        raise ValueError(f"{n_pairs - len(counts)} pairs missing")
    lmax = max(counts.values())
    if lmax > cap:
        raise ValueError(f"lambda_max {lmax} above cap {cap}")
    hist = {}
    for c in counts.values():
        hist[c] = hist.get(c, 0) + 1
    use = {}
    for blk in blocks:
        for x in blk:
            use[x] = use.get(x, 0) + 1
    if len(use) != v:
        raise ValueError("some item never used")
    return lmax, hist, (min(use.values()), max(use.values()))


def ideal_lmax(v, k, b):
    return math.ceil(b * k * (k - 1) / 2 / (v * (v - 1) / 2))


def write_cache_file(v, k, blocks):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"v{v}_k{k}_b{len(blocks)}.txt"
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for blk in blocks:
            f.write(" ".join(str(x) for x in blk) + "\n")
    return path


def results_path(shard, tag=""):
    if shard is None:
        return OUT_DIR / f"orbit_sweep_results{tag}.jsonl"
    return OUT_DIR / (f"orbit_sweep_results{tag}"
                      f"_s{shard[0]}of{shard[1]}.jsonl")


def load_done():
    done = set()
    if OUT_DIR.exists():
        for path in OUT_DIR.glob("orbit_sweep_results*.jsonl"):
            for ln in path.open():
                try:
                    r = json.loads(ln)
                    done.add((r["v"], r["k"]))
                except Exception:
                    pass
    return done


def log_result(rec, shard, tag=""):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with results_path(shard, tag).open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


# -------------------------------------------------------------------- driver

def attack_case(v, k, b, cur_lmax, budget_s, seed=12345, skip_known=False):
    """Anneal orbit-core+tail plans at cap ideal (and ideal+1 as fallback);
    return result record."""
    t_cpu = clock()
    t_wall = time.time()
    ideal = ideal_lmax(v, k, b)
    known = None if skip_known else KNOWN.get((v, k))
    if known:
        model, s, base = known
        blocks = expand(v, model, s, base)
        lmax, hist, use = verify(v, k, blocks, cap=cur_lmax)
        path = write_cache_file(v, k, blocks)
        return {"v": v, "k": k, "b": b, "found": True, "source": "known",
                "model": model, "s": s, "base": [list(x) for x in base],
                "blocks": len(blocks), "lambda_max": lmax,
                "hist": hist, "item_use": use, "file": str(path),
                "secs": round(clock() - t_cpu, 1)}
    pc_cache = {}
    tried = set()
    tiers = [(0.0, 0), (0.05, 0), (0.10, 0), (0.20, 0)]
    fracs = [0.40, 0.15, 0.15, 0.15]
    if cur_lmax > ideal + 1:
        tiers.append((0.0, 1))      # strict-budget cap fallback
        fracs.append(0.15)
    for (rho, cap_bump), frac in zip(tiers, fracs):
        b_allowed = int(math.ceil(b * (1.0 + rho)))
        plans = [p for p in enumerate_anneal_plans(v, k, b_allowed, pc_cache)
                 if (p["model"], p["s"], p["m"], p["r"]) not in tried]
        if not plans:
            continue
        top = plans[:4]
        per_plan = budget_s * frac / len(top)
        for plan in top:
            tried.add((plan["model"], plan["s"], plan["m"], plan["r"]))
            cap = max(2, ideal_lmax(v, k, plan["bprime"])) + cap_bump
            if cap >= cur_lmax and plan["bprime"] >= b:
                continue
            rng = random.Random(f"{seed}:{v}:{k}:{cap}:{rho}:"
                                f"{plan['s']}:{plan['model']}:{plan['m']}")
            res = anneal_plan(v, k, cap, plan, per_plan, rng)
            if res is None:
                continue
            base, tail, full, lmax, hist, use = res
            path = write_cache_file(v, k, full)
            return {"v": v, "k": k, "b": b, "found": True,
                    "source": "anneal", "model": plan["model"],
                    "s": plan["s"], "m": plan["m"], "r": plan["r"],
                    "rho": rho, "cap": cap,
                    "base": [sorted(x) for x in base],
                    "tail": [sorted(x) for x in tail],
                    "blocks": len(full), "lambda_max": lmax,
                    "hist": hist, "item_use": use, "file": str(path),
                    "secs": round(clock() - t_cpu, 1)}
    return {"v": v, "k": k, "b": b, "found": False,
            "secs": round(clock() - t_cpu, 1),
            "wall": round(time.time() - t_wall, 1)}


# open cases known from the production report but absent from the sweep file
EXTRA_CASES = [(58, 6, 117, 3)]


def schonheim(v, k):
    return math.ceil(v / k * math.ceil((v - 1) / (k - 1)))


def load_gap_cases():
    """(v, k) combos in the supported grid (k=3..10, v<=100) that the LJCR
    sweep never touched. Baseline trial count is the Schonheim bound, so
    slack tiers stay conservative whatever base cover the runtime uses.
    Combos with a constructible exact design are skipped: the runtime
    builds those directly."""
    rows = [json.loads(l) for l in SWEEP_JSONL.open()]
    have = {(r["v"], r["k"]) for r in rows}
    have.update((v, k) for (v, k, _, _) in EXTRA_CASES)
    try:
        sys.path.insert(0, str(SWEEP_JSONL.parents[1]))
        from coverlib.constructions import exact_design
    except Exception:
        exact_design = None
    cases = []
    for k in range(3, 11):
        for v in range(max(8, k + 2), 101):
            if (v, k) in have:
                continue
            if exact_design is not None:
                try:
                    if exact_design(v, k) is not None:
                        continue
                except Exception:
                    pass
            cases.append((v, k, schonheim(v, k), 99))
    return cases


def load_open_cases():
    rows = [json.loads(l) for l in SWEEP_JSONL.open()]
    bad = [r for r in rows if r["candidate_lambda_max_ratio"] > 1.0]
    bad.sort(key=lambda r: -r["candidate_lambda_max_ratio"])
    cases = [(r["v"], r["k"], r["candidate_blocks"],
              r["candidate_lambda_max"]) for r in bad]
    have = {(v, k) for (v, k, _, _) in cases}
    for extra in EXTRA_CASES:
        if (extra[0], extra[1]) not in have:
            cases.append(extra)
    return cases


def run_cases(cases, shard, tag=""):
    done = load_done()
    wins = 0
    for i, (v, k, b, lmax) in enumerate(cases):
        if (v, k) in done:
            continue
        budget = FLAG_BUDGET_S if lmax >= 8 else CASE_BUDGET_S
        try:
            rec = attack_case(v, k, b, lmax, budget_s=budget)
            if tag:
                rec["baseline"] = "schonheim"
        except Exception:
            rec = {"v": v, "k": k, "b": b, "found": False,
                   "error": traceback.format_exc(limit=3)}
        log_result(rec, shard, tag)
        if rec.get("found"):
            wins += 1
            print(f"[{i+1}/{len(cases)}] WIN  {v}x{k}: lambda "
                  f"{lmax} -> {rec['lambda_max']} "
                  f"({rec['blocks']} trials, {rec['secs']}s cpu)", flush=True)
        else:
            print(f"[{i+1}/{len(cases)}] ---  {v}x{k}: no orbit win "
                  f"({rec.get('secs', '?')}s cpu)", flush=True)
    print(f"shard {shard} complete: {wins} wins", flush=True)


def main():
    mode = sys.argv[1] if sys.argv[1:] else "test"

    if mode == "test":
        rec = attack_case(86, 6, 259, 19, budget_s=5)
        print(json.dumps({kk: rec[kk] for kk in
                          ("found", "source", "blocks", "lambda_max",
                           "item_use")}))
        pc_cache = {}
        for (v, k, b) in ((99, 6, 336), (58, 6, 117), (40, 6, 55)):
            plans = enumerate_plans(v, k, b, 2, pc_cache)
            brief = [(p["model"], p["s"], p["g"], p["m"], p["slack"])
                     for p in plans]
            print(f"{v}x{k} b={b} cap=2 plans: {brief}")
        return

    if mode == "known":
        for (v, k), _ in KNOWN.items():
            for case in load_open_cases():
                if case[0] == v and case[1] == k:
                    rec = attack_case(v, k, case[2], case[3], budget_s=5)
                    log_result(rec, None)
                    print(json.dumps(rec))
        return

    if mode == "case":
        v, k = int(sys.argv[2]), int(sys.argv[3])
        for (cv, ck, b, lmax) in load_open_cases():
            if (cv, ck) == (v, k):
                rec = attack_case(v, k, b, lmax, budget_s=FLAG_BUDGET_S)
                log_result(rec, None)
                print(json.dumps(rec))
                return
        print("case not in open list")
        return

    if mode == "anneal":
        # benchmark mode: attack one case, ignoring known solutions and
        # without touching the results log
        v, k = int(sys.argv[2]), int(sys.argv[3])
        budget = float(sys.argv[4]) if len(sys.argv) > 4 else FLAG_BUDGET_S
        for (cv, ck, b, lmax) in load_open_cases():
            if (cv, ck) == (v, k):
                rec = attack_case(v, k, b, lmax, budget_s=budget,
                                  skip_known=True)
                rec.pop("base", None)
                rec.pop("tail", None)
                print(json.dumps(rec))
                return
        print("case not in open list")
        return

    if mode == "all":
        cases = load_open_cases()
        shard = None
        if len(sys.argv) > 3:
            i, nshard = int(sys.argv[2]), int(sys.argv[3])
            shard = (i, nshard)
            cases = [c for j, c in enumerate(cases) if j % nshard == i]
        run_cases(cases, shard)
        return

    if mode == "gaps":
        cases = load_gap_cases()
        shard = None
        if len(sys.argv) > 3:
            i, nshard = int(sys.argv[2]), int(sys.argv[3])
            shard = (i, nshard)
            cases = [c for j, c in enumerate(cases) if j % nshard == i]
        run_cases(cases, shard, tag="_gaps")
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        with (OUT_DIR / "crash.log").open("a", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "\n")
        raise
