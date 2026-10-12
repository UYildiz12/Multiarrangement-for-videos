"""Library boundary for cyclic and one-rotational schedule search.

The repository's historical orbit sweep remains useful, but it was written as
an offline driver.  This module exposes its prescribed-automorphism search as a
side-effect-free portfolio stage and optionally replaces its free tail with a
bounded exact residual completion.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .certificates import balanced_sort_key, certify_schedule
from .orbit_precompute import anneal_plan, enumerate_anneal_plans, ideal_lmax
from .residual import solve_residual_exact


Block = Tuple[int, ...]


@dataclass(frozen=True)
class SymmetryCandidate:
    blocks: Tuple[Block, ...]
    source: str
    model: str
    step: int
    orbit_size: int
    base_block_count: int
    tail_block_count: int
    lambda_cap: int
    exact_tail: bool


def search_symmetry_candidates(
    v: int,
    k: int,
    *,
    max_blocks: int,
    incumbent_blocks: Optional[List[List[int]]] = None,
    budget_seconds: float = 20.0,
    seed: int = 12345,
    max_plans: int = 8,
) -> Tuple[SymmetryCandidate, ...]:
    """Search cyclic/one-rotational cores and return strict incumbent wins.

    Failure is never a global nonexistence certificate: it applies only to the
    prescribed actions and bounded annealing effort tried here.
    """
    if max_blocks <= 0 or budget_seconds <= 0:
        return tuple()
    incumbent_key = (
        balanced_sort_key(v, k, incumbent_blocks)
        if incumbent_blocks
        else None
    )
    incumbent_lambda = (
        certify_schedule(v, k, incumbent_blocks).lambda_max
        if incumbent_blocks
        else math.inf
    )
    plans = enumerate_anneal_plans(v, k, max_blocks, {})
    if not plans:
        return tuple()

    started = time.process_time()
    results: List[SymmetryCandidate] = []
    seen_hashes = set()
    for plan_index, plan in enumerate(plans[:max_plans]):
        remaining = budget_seconds - (time.process_time() - started)
        if remaining <= 0:
            break
        plan_budget = max(0.25, remaining / max(1, min(max_plans, len(plans)) - plan_index))
        cap_floor = max(1, ideal_lmax(v, k, plan["bprime"]))
        cap_targets = [cap_floor]
        if cap_floor + 1 < incumbent_lambda:
            cap_targets.append(cap_floor + 1)
        for cap in cap_targets:
            remaining = budget_seconds - (time.process_time() - started)
            if remaining <= 0:
                break
            rng = random.Random(
                f"symmetry:{seed}:{v}:{k}:{plan['model']}:{plan['s']}:"
                f"{plan['m']}:{plan['r']}:{cap}"
            )
            solved = anneal_plan(
                v,
                k,
                cap,
                plan,
                min(plan_budget, remaining),
                rng,
            )
            if solved is None:
                continue
            base, tail, full, _, _, _ = solved
            chosen = tuple(sorted(tuple(sorted(block)) for block in full))
            source = f"orbit_{plan['model']}_anneal"
            exact_tail = False

            if tail:
                from .orbit_precompute import expand

                core = expand(
                    v,
                    plan["model"],
                    plan["s"],
                    [tuple(sorted(block)) for block in base],
                )
                exact = solve_residual_exact(
                    v,
                    k,
                    core,
                    blocks_to_add=len(tail),
                    lambda_cap=cap,
                    preferred_blocks=tail,
                    seed=seed + plan_index,
                    time_limit_seconds=min(3.0, max(0.1, remaining)),
                )
                if exact is not None:
                    chosen = tuple(sorted(tuple(core) + exact.blocks))
                    source = f"orbit_{plan['model']}_exact_tail"
                    exact_tail = True

            certificate = certify_schedule(v, k, chosen, source=source)
            if not certificate.complete:
                continue
            candidate_key = balanced_sort_key(v, k, chosen)
            if incumbent_key is not None and candidate_key >= incumbent_key:
                continue
            if certificate.schedule_hash in seen_hashes:
                continue
            seen_hashes.add(certificate.schedule_hash)
            results.append(
                SymmetryCandidate(
                    blocks=chosen,
                    source=source,
                    model=plan["model"],
                    step=int(plan["s"]),
                    orbit_size=int(plan["g"]),
                    base_block_count=int(plan["m"]),
                    tail_block_count=int(plan["r"]),
                    lambda_cap=cap,
                    exact_tail=exact_tail,
                )
            )
            incumbent_key = candidate_key
            incumbent_lambda = certificate.lambda_max
            break

    return tuple(
        sorted(
            results,
            key=lambda candidate: balanced_sort_key(v, k, candidate.blocks),
        )
    )

