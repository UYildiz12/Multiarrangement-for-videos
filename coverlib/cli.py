from __future__ import annotations
import argparse
from pathlib import Path
from .api import generate_cover
from .combinatorics import schonheim_lb

def main():
    ap = argparse.ArgumentParser(description="covergen: cache-first LJCR (v,k,2) rebalancer (fixed-b)")
    ap.add_argument("--v", type=int, required=True)
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--passes", type=int, default=12)
    ap.add_argument("--greedy-trials", type=int, default=2)
    ap.add_argument("--forbid-above", type=int, default=2)
    ap.add_argument("--group-rounds", type=int, default=12)
    ap.add_argument("--group-time", type=float, default=10.0)
    ap.add_argument("--group-cands", type=int, default=100)
    from pathlib import Path
    # Prefer packaged cache under multiarrangement/ljcr_cache if available
    try:
        import multiarrangement
        default_cache = str((Path(multiarrangement.__file__).parent / "ljcr_cache").resolve())
    except Exception:
        default_cache = str((Path(__file__).parent.parent / "ljcr_cache").resolve())
    ap.add_argument("--cache-dir", type=str, default=default_cache)
    ap.add_argument("--offline-only", action="store_true")
    ap.add_argument("--seed-file", type=str, default=None)
    ap.add_argument("--outfile", type=str, default=None)
    args = ap.parse_args()

    res = generate_cover(
        args.v, args.k,
        passes=args.passes, greedy_trials=args.greedy_trials,
        forbid_above=args.forbid_above,
        group_rounds=args.group_rounds, group_time=args.group_time, group_cands=args.group_cands,
        cache_dir=args.cache_dir, offline_only=args.offline_only, seed_file=args.seed_file,
    )

    P = args.v*(args.v-1)//2
    avg_lambda = res.b * (args.k*(args.k-1)//2) / P
    print(f"Seed (after repair/prune): b={res.b}, Schönheim≥{schonheim_lb(args.v,args.k)}, avg λ={avg_lambda:.3f}")
    print("Final    λ_max:", res.lmax, "hist:", res.hist, "sumsq:", res.sumsq)

    out = Path(args.outfile or f"rebalance_v{args.v}_k{args.k}.txt")
    with out.open("w", encoding="utf-8") as f:
        for blk in res.blocks:
            f.write(" ".join(str(x) for x in blk) + "\n")  # 0-based output by default
    print("Saved improved cover to", out)

if __name__ == "__main__":
    main()
