"""Optional general exact scheduling with validated constructive incumbents.

The default application scheduler remains cache-first. This module is an
explicit bounded refinement API. Solver optimality follows numerical MILP
conventions; analytic and solver evidence are reported separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from numbers import Integral, Real
import math
import time
import warnings
from typing import Any, Optional, Sequence

from .certificates import (certify_schedule, compact_sort_key, balanced_sort_key,
                           ideal_concurrence_profile)
from .dual_bounds import (trial_count_lower_bound, dual_incidence_bound,
                          cap_two_trial_bound_details)


class _Deadline(Exception):
    pass


class _Resource(Exception):
    pass


@dataclass
class GeneralSolveResult:
    v: int
    k: int
    mode: str
    blocks: tuple[tuple[int, ...], ...] = ()
    certificate: Any = None
    status: str = "FEASIBLE"
    backend: str = "none"
    proof_scope: str = "none"
    proof_kind: str = "none"
    minimum_count_proven: bool = False
    pair_profile_proven: bool = False
    item_profile_proven: bool = False
    full_objective_proven: bool = False
    stages: list[dict[str, Any]] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    deadline_exhausted: bool = False
    reference_count: Optional[int] = None
    budget_fraction: Optional[str] = None
    max_blocks: Optional[int] = None
    effective_max_blocks: Optional[int] = None
    cap_two_trial_lower_bound: Optional[int] = None
    cap_two_globally_excluded: bool = False
    message: str = ""

    @property
    def objective_key(self):
        if not self.blocks:
            return None
        key = compact_sort_key if self.mode == "compact" else balanced_sort_key
        return key(self.v, self.k, self.blocks)

    def to_dict(self) -> dict:
        data = dict(self.__dict__)
        data["blocks"] = [list(row) for row in self.blocks]
        data["certificate"] = self.certificate.to_dict(include_profiles=True) if self.certificate else None
        data["objective_key"] = self.objective_key
        data["has_valid_within_budget_cover"] = bool(self.blocks)
        return data


def _integer(value, name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer of at least {minimum}")
    return int(value)


def _fraction(value) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal, Fraction)):
        raise ValueError("max_extra_fraction must be a finite nonnegative number")
    try:
        answer = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, OverflowError, ZeroDivisionError):
        raise ValueError("max_extra_fraction must be a finite nonnegative number")
    if answer < 0:
        raise ValueError("max_extra_fraction must be a finite nonnegative number")
    return answer


def _independent_cover(v: int, k: int, max_output: int) -> list[tuple[int, ...]]:
    """A cache-free finite cover from unions of groups, including all boundaries."""
    if k == v:
        return [tuple(range(v))]
    if k == 2:
        if math.comb(v, 2) > max_output:
            raise _Resource("constructive output exceeds max_variables block limit")
        return list(combinations(range(v), 2))
    size = k // 2
    groups = [tuple(range(start, min(v, start + size))) for start in range(0, v, size)]
    if math.comb(len(groups), 2) > max_output:
        raise _Resource("constructive output exceeds max_variables block limit")
    blocks = set()
    for a, b in combinations(groups, 2):
        chosen = set(a + b)
        chosen.update(i for i in range(v) if i not in chosen and len(chosen) < k)
        blocks.add(tuple(sorted(chosen)))
    return sorted(blocks)


class _Model:
    def __init__(self, deadline, max_variables, max_constraints, max_nonzeros):
        self.deadline = deadline
        self.max_variables = max_variables
        self.max_constraints = max_constraints
        self.max_nonzeros = max_nonzeros
        self.lo = []
        self.hi = []
        self.integrality = []
        self.row_indices = []
        self.col_indices = []
        self.values = []
        self.lb = []
        self.ub = []

    def check(self):
        if time.perf_counter() >= self.deadline:
            raise _Deadline("absolute deadline reached during model assembly")

    def variable(self, lower=0, upper=1, integer=True):
        if len(self.lo) >= self.max_variables:
            raise _Resource("model variable limit reached")
        if len(self.lo) % 1024 == 0:
            self.check()
        index = len(self.lo)
        self.lo.append(lower)
        self.hi.append(upper)
        self.integrality.append(int(integer))
        return index

    def row(self, expression, lower=-math.inf, upper=math.inf):
        if len(self.lb) >= self.max_constraints:
            raise _Resource("model constraint limit reached")
        if len(self.lb) % 1024 == 0:
            self.check()
        index = len(self.lb)
        for column, value in expression:
            if value:
                if len(self.values) >= self.max_nonzeros:
                    raise _Resource("model nonzero storage limit reached")
                self.row_indices.append(index)
                self.col_indices.append(column)
                self.values.append(float(value))
        self.lb.append(lower)
        self.ub.append(upper)


def solve_schedule(
    v: int, k: int, *, mode: str = "compact", max_blocks: Optional[int] = None,
    max_extra_fraction=0.0, reference_count: Optional[int] = None,
    use_cache: bool = True, backend: str = "auto", time_limit: float = 10.0,
    max_columns: int = 50_000, max_variables: int = 300_000,
    max_constraints: int = 1_000_000, max_nonzeros: int = 5_000_000,
    seed: int = 42, threads: int = 1,
) -> GeneralSolveResult:
    """Optimize the full declared objective with one assembly/solver deadline.

    Compact order is count, full descending pair vector, full item-deviation
    vector. Balanced order is full pair vector, count, full item vector under an
    absolute budget or a fraction of the explicitly reported reference count.
    Decimal fractions use exact arithmetic (100 * .29 permits 29 extra trials).
    Zero time still constructs/verifies a fallback; that necessary setup/output
    overhead is measured and may exceed the solver deadline. Resource-limited
    cases return a valid within-budget incumbent or honestly return no cover.
    """
    # QueryPerformanceCounter on Windows: GetTickCount64-backed monotonic()
    # has ~15.6ms resolution and cannot enforce a small absolute budget.
    start = time.perf_counter()
    v = _integer(v, "v", 2)
    k = _integer(k, "k", 2)
    if k > v:
        raise ValueError("k must not exceed v")
    if not isinstance(mode, str) or mode not in {"compact", "balanced"}:
        raise ValueError("mode must be compact or balanced")
    if not isinstance(backend, str) or backend not in {"auto", "columns", "slots"}:
        raise ValueError("backend must be auto, columns or slots")
    if not isinstance(use_cache, bool):
        raise ValueError("use_cache must be a boolean")
    if isinstance(time_limit, bool) or not isinstance(time_limit, Real) or not math.isfinite(time_limit) or time_limit < 0:
        raise ValueError("time_limit must be a finite nonnegative number")
    for name in ("max_columns", "max_variables", "max_constraints", "max_nonzeros", "threads"):
        _integer(locals()[name], name)
    _integer(seed, "seed", -2**63)
    fraction = _fraction(max_extra_fraction)
    if max_blocks is not None:
        max_blocks = _integer(max_blocks, "max_blocks", 0)
    if reference_count is not None:
        reference_count = _integer(reference_count, "reference_count")
    if mode == "compact" and (fraction or reference_count is not None):
        raise ValueError("fractional budgets and reference_count require balanced mode")
    if max_blocks is not None and (fraction or reference_count is not None):
        raise ValueError("use either an absolute max_blocks or a fractional reference budget")

    deadline = start + float(time_limit)
    out = GeneralSolveResult(v, k, mode)
    pairs = math.comb(v, 2)
    pair_slots = math.comb(k, 2)
    key = compact_sort_key if mode == "compact" else balanced_sort_key
    incumbent = None
    incumbent_cert = None
    numerical_proofs = False

    def record_math(stage, objective, reason, scope="global_trial_count"):
        out.stages.append({"stage": stage, "status": "analytic_certificate", "objective": objective,
                           "proof_scope": scope, "proof_kind": "analytic", "reason": reason})

    def consider(blocks, bound=None):
        nonlocal incumbent, incumbent_cert
        cert = certify_schedule(v, k, blocks, source="general_solver_validated_witness")
        if not cert.complete or not cert.simple or (bound is not None and cert.b > bound):
            return None
        if incumbent is None or key(v, k, blocks) < key(v, k, incumbent):
            incumbent = tuple(tuple(sorted(map(int, row))) for row in blocks)
            incumbent_cert = cert
            if bound is not None:
                if mode == "balanced":
                    # The flag refers to the selected witness's count, not a
                    # different feasible minimum-count candidate in the pool.
                    out.minimum_count_proven = "MINIMUM_TRIALS_CERTIFIED" in cert.statuses
                elif "MINIMUM_TRIALS_CERTIFIED" in cert.statuses:
                    out.minimum_count_proven = True
        return cert

    def finish(status, message=""):
        out.status = status
        out.message = message
        out.blocks = incumbent or ()
        out.certificate = incumbent_cert
        out.elapsed_seconds = time.perf_counter() - start
        out.deadline_exhausted = time.perf_counter() >= deadline
        out.full_objective_proven = out.pair_profile_proven and out.item_profile_proven and (mode == "balanced" or out.minimum_count_proven)
        analytic_evidence = any(stage.get("proof_kind") == "analytic" for stage in out.stages)
        if out.full_objective_proven:
            out.proof_kind = "mixed_analytic_and_solver_numerical" if numerical_proofs else "analytic"
            out.status = "OPTIMAL_SOLVER" if numerical_proofs else "OPTIMAL_ANALYTIC"
        elif numerical_proofs:
            out.proof_kind = "mixed_analytic_and_solver_numerical_prefix" if analytic_evidence else "solver_numerical_prefix"
        elif analytic_evidence:
            out.proof_kind = "analytic_prefix"
            if out.proof_scope == "none":
                out.proof_scope = "analytic_bounds_or_partial_objective"
        return out

    # Mandatory fallback/output verification happens even with a zero deadline.
    if pairs > max_variables or v > max_variables:
        return finish("RESOURCE_LIMIT", "pair/item output verification exceeds max_variables storage limit")
    try:
        independent = _independent_cover(v, k, max_variables)
        consider(independent)
    except _Resource as exc:
        return finish("RESOURCE_LIMIT", str(exc))
    candidates = [independent]
    direct_triples_constructed = False
    if time.perf_counter() < deadline and k == 3:
        from .direct_triples import (direct_triple_candidates,
                                     DirectTripleDeadline, DirectTripleResource)
        try:
            direct = direct_triple_candidates(
                v, max_blocks=max_blocks, deadline=deadline,
                max_pair_entries=max_variables, max_output_cells=max_nonzeros)
            candidates.extend(candidate.blocks for candidate in direct)
            direct_triples_constructed = bool(direct)
            if direct:
                out.stages.append({"stage": "direct_triple_construction", "status": "generated",
                                   "candidates": [{"source": candidate.source, "b": len(candidate.blocks)}
                                                  for candidate in direct]})
        except (DirectTripleDeadline, DirectTripleResource) as exc:
            out.stages.append({"stage": "direct_triple_construction",
                               "status": "time_limit" if isinstance(exc, DirectTripleDeadline) else "resource_limit",
                               "message": str(exc)})
    if time.perf_counter() < deadline:
        from .repaired_transversal import (repaired_transversal_cover,
                                           locally_refined_transversal_cover)
        repaired = repaired_transversal_cover(v, k)
        if repaired is not None:
            candidates.append(repaired.blocks)
        if (v, k) == (100, 10) and 128 * k <= max_nonzeros and time.perf_counter() < deadline:
            refined = locally_refined_transversal_cover(v, k)
            if refined is not None:
                candidates.append(refined.blocks)
                out.stages.append({"stage": "local_transversal_construction", "status": "generated",
                                   "source": refined.source, "b": len(refined.blocks),
                                   "proof_scope": "validated_instance_incumbent"})
    if time.perf_counter() < deadline and v <= 100 and not direct_triples_constructed:
        from .constructions import structured_cover_candidates
        candidates.extend(candidate.blocks for candidate in structured_cover_candidates(v, k))
    elif time.perf_counter() < deadline and k == 3 and not direct_triples_constructed:
        # Polynomial Bose truncation/repair covers all large orders without
        # entering the unbounded Heffter backtracking branch.
        from .bose_repair import (bose_repaired_candidates,
                                  BoseRepairDeadline, BoseRepairResource)
        from .skolem import direct_skolem_cover
        try:
            constructed = direct_skolem_cover(
                v, k, deadline=deadline, max_pair_entries=max_variables,
                max_output_cells=max_nonzeros)
            if constructed is not None:
                candidates.append(constructed.blocks)
            else:
                candidates.extend(candidate.blocks for candidate in bose_repaired_candidates(
                    v, deadline=deadline, max_pair_entries=max_variables,
                    max_output_cells=max_nonzeros))
        except (BoseRepairDeadline, BoseRepairResource) as exc:
            out.stages.append({"stage": "triple_construction", "status": "time_limit" if isinstance(exc, BoseRepairDeadline) else "resource_limit", "message": str(exc)})
    if use_cache and time.perf_counter() < deadline:
        try:
            import multiarrangement as ma
            from .frontier import load_frontier_candidates
            package = Path(ma.__file__).resolve().parent
            candidates.extend(candidate.blocks for candidate in load_frontier_candidates(v, k, package_dir=package))
        except Exception as exc:
            out.stages.append({"stage": "cache", "status": "unavailable", "message": str(exc)})
    valid = []
    for blocks in candidates:
        if valid and time.perf_counter() >= deadline:
            break
        try:
            cert = certify_schedule(v, k, blocks, source="general_solver_candidate")
            if cert.complete and cert.simple:
                valid.append((blocks, cert))
        except (ValueError, TypeError):
            pass
    reference = min(cert.b for _, cert in valid)
    lower, excluded = trial_count_lower_bound(v, k)
    cap_two_detail = cap_two_trial_bound_details(v, k)
    out.cap_two_trial_lower_bound = cap_two_detail.lower_bound
    out.cap_two_globally_excluded = cap_two_detail.cap_two_globally_excluded
    if mode == "balanced":
        out.reference_count = reference_count if reference_count is not None else reference
        out.budget_fraction = str(fraction)
        budget = max_blocks if max_blocks is not None else out.reference_count + (out.reference_count * fraction.numerator // fraction.denominator)
    else:
        budget = max_blocks if max_blocks is not None else reference
    out.max_blocks = budget
    upper = min(budget, pairs)
    out.effective_max_blocks = upper
    incumbent = incumbent_cert = None
    for blocks, _ in valid:
        consider(blocks, upper)
    if mode == "compact" and incumbent_cert is not None and incumbent_cert.b < upper:
        upper = incumbent_cert.b
        out.effective_max_blocks = upper
        record_math("compact_incumbent_upper_bound", upper,
                    "a validated feasible incumbent bounds the global minimum trial count",
                    "global_count_optimum_preserving")
    if upper < lower:
        record_math("feasibility", lower, "global trial lower bound exceeds the supplied budget")
        return finish("INFEASIBLE_ANALYTIC")
    record_math("trial_lower_bound", lower, {"excluded_counts": list(excluded)})
    record_math("cap_two_trial_lower_bound", cap_two_detail.lower_bound,
                {"unrestricted_lower_bound": lower,
                 "conditional_exclusions": list(cap_two_detail.exclusions),
                 "cap_two_globally_excluded": cap_two_detail.cap_two_globally_excluded},
                "all_covers_with_pair_cap_at_most_two")
    if budget > pairs:
        record_math("budget_clamp", pairs, "every full optimum is irredundant and has distinct private pairs", "full_objective_optimum_preserving")
    fixed_b = None
    if k == v - 1 and incumbent_cert and incumbent_cert.b == 3:
        # Every simple cover consists of distinct complements. Three suffice;
        # adding complements strictly raises the entire sorted pair vector.
        # At a fixed count all choices are isomorphic, including item counts.
        out.minimum_count_proven = out.pair_profile_proven = out.item_profile_proven = True
        record_math("complement_boundary", incumbent_cert.b,
                    "three distinct complements attain the global count/pair/item objective",
                    "global_compact" if mode == "compact" else "within_declared_budget")
        out.proof_scope = "global_analytic" if mode == "compact" else "within_declared_budget_analytic"
        return finish("OPTIMAL_ANALYTIC")
    if mode == "compact" and incumbent_cert and "MINIMUM_TRIALS_CERTIFIED" in incumbent_cert.statuses:
        fixed_b = incumbent_cert.b
        out.minimum_count_proven = True
        record_math("min_trials", fixed_b, "validated witness attains the global arithmetic lower bound")
    elif upper == lower:
        fixed_b = lower
        if incumbent_cert:
            out.minimum_count_proven = True
            record_math("min_trials", lower, "global trial lower bound equals the feasible budget")

    # Ideal profiles increase lexicographically with their total pair-slot sum.
    if mode == "balanced" and incumbent_cert and incumbent_cert.b == lower and incumbent_cert.concurrence_profile == ideal_concurrence_profile(v, k, lower):
        fixed_b = lower
        out.minimum_count_proven = out.pair_profile_proven = True
        record_math("pair_profile", list(incumbent_cert.concurrence_profile), "ideal positive profile at the global minimum pair-slot total", "within_declared_budget")
    elif (mode == "balanced" and incumbent_cert
          and incumbent_cert.b == cap_two_detail.lower_bound
          and incumbent_cert.lambda_max == 2
          and incumbent_cert.global_lambda_lower_bound >= 2
          and incumbent_cert.concurrence_profile == ideal_concurrence_profile(
              v, k, cap_two_detail.lower_bound)):
        # Global cap>=2 excludes all cap-one covers; the conditioned count
        # bound excludes every smaller cap-two cover. Larger counts have a
        # lexicographically larger ideal pair vector, while cap>2 loses first.
        fixed_b = cap_two_detail.lower_bound
        out.minimum_count_proven = "MINIMUM_TRIALS_CERTIFIED" in incumbent_cert.statuses
        out.pair_profile_proven = True
        record_math("cap_conditioned_trial_lower_bound", fixed_b,
                    {"conditional_exclusions": list(cap_two_detail.exclusions),
                     "unrestricted_lower_bound": lower}, "all_cap_two_covers")
        record_math("pair_profile", list(incumbent_cert.concurrence_profile),
                    "ideal cap-two profile at its rigorously conditioned minimum count",
                    "within_declared_budget")
    elif fixed_b is not None and incumbent_cert and "PAIR_PROFILE_AT_B_CERTIFIED" in incumbent_cert.statuses:
        out.pair_profile_proven = True
        record_math("pair_profile", list(incumbent_cert.concurrence_profile), "validated fixed-count mathematical certificate", "at_proved_minimum_count" if mode == "compact" else "within_declared_budget")
    if out.pair_profile_proven and incumbent_cert and "ITEM_PROFILE_IDEAL" in incumbent_cert.statuses:
        out.item_profile_proven = True
        record_math("item_profile", list(incumbent_cert.item_deviation_profile), "attained sharp integer item-frequency bound", "at_proved_pair_profile_and_count")
        out.proof_scope = "global_analytic" if mode == "compact" else "within_declared_budget_analytic"
        return finish("OPTIMAL_ANALYTIC")
    global_cap = (lower * pair_slots + pairs - 1) // pairs
    global_cap_attained = incumbent_cert is not None and incumbent_cert.lambda_max == global_cap
    if mode == "balanced" and global_cap_attained:
        record_math("min_cap", global_cap,
                    "validated witness attains the global trial-count induced cap lower bound",
                    "within_declared_budget")
    if time.perf_counter() >= deadline:
        return finish("TIME_LIMIT", "no solver search was started; fallback construction/verification overhead is included")

    try:
        import numpy as np
        from scipy.optimize import milp, Bounds, LinearConstraint
        from scipy.sparse import csc_array
    except ImportError as exc:
        return finish("SOLVER_UNAVAILABLE", str(exc))
    columns = math.comb(v, k)
    if backend == "auto":
        backend = "columns" if columns <= max_columns and columns + pairs + 1 <= max_variables else "slots"
    out.backend = backend
    out.proof_scope = "full_universe_columns" if backend == "columns" else "equivalent_membership_slots"
    model = _Model(deadline, max_variables, max_constraints, max_nonzeros)
    pair_expressions = [[] for _ in range(pairs)]
    item_expressions = [[] for _ in range(v)]
    count_expression = []
    universe = None
    memberships = None
    activations = None

    try:
        pair_list = list(combinations(range(v), 2))
        pair_index = {pair: i for i, pair in enumerate(pair_list)}
        if backend == "columns":
            if columns > max_columns or columns > max_variables:
                raise _Resource("complete candidate universe exceeds the column/variable limit")
            if columns * (k + pair_slots + 1) > max_nonzeros:
                raise _Resource("complete candidate universe exceeds nonzero storage limit")
            universe = []
            for block in combinations(range(v), k):
                j = model.variable()
                universe.append(block)
                count_expression.append((j, 1))
                for i in block:
                    item_expressions[i].append((j, 1))
                for pair in combinations(block, 2):
                    pair_expressions[pair_index[pair]].append((j, 1))
            model.lo[0] = 1  # safe item relabeling: some selected block is canonical
        else:
            estimated_variables = upper * (1 + v + pairs) + (upper - 1) * (2 * v + 1)
            estimated_rows = upper * (3 * pairs + v + 2) + pairs + upper + (upper - 1) * (8 * v + 1)
            if estimated_variables > max_variables or estimated_rows > max_constraints:
                raise _Resource("equivalent slot model exceeds variable/constraint limits")
            activations = [model.variable() for _ in range(upper)]
            memberships = [[model.variable() for _ in range(v)] for _ in range(upper)]
            conjunctions = [[model.variable(integer=False) for _ in range(pairs)] for _ in range(upper)]
            model.lo[activations[0]] = 1
            for i in range(v):
                model.lo[memberships[0][i]] = model.hi[memberships[0][i]] = int(i < k)
            for t in range(upper):
                count_expression.append((activations[t], 1))
                model.row([(j, 1) for j in memberships[t]] + [(activations[t], -k)], 0, 0)
                if t + 1 < upper:
                    model.row([(activations[t], 1), (activations[t + 1], -1)], 0, math.inf)
                for i in range(v):
                    item_expressions[i].append((memberships[t][i], 1))
                degrees = [[] for _ in range(v)]
                for ip, (i, j) in enumerate(pair_list):
                    w = conjunctions[t][ip]
                    model.row([(w, 1), (memberships[t][i], -1)], -math.inf, 0)
                    model.row([(w, 1), (memberships[t][j], -1)], -math.inf, 0)
                    model.row([(w, 1), (memberships[t][i], -1), (memberships[t][j], -1)], -1, math.inf)
                    pair_expressions[ip].append((w, 1))
                    degrees[i].append((w, 1))
                    degrees[j].append((w, 1))
                for i in range(v):
                    model.row(degrees[i] + [(memberships[t][i], -(k - 1))], 0, 0)
                model.row([(w, 1) for w in conjunctions[t]] + [(activations[t], -pair_slots)], 0, 0)
            # Descending lexicographic memberships order active slots and make
            # them distinct, with coefficients at most two. XOR and prefix
            # auxiliaries are automatically integral at binary memberships.
            # The canonical first k-subset is lexicographically largest, so
            # this order and first-block relabeling preserve every simple cover.
            for t in range(upper - 1):
                prefix = model.variable(1, 1, integer=False)
                for i in range(v):
                    a, b = memberships[t][i], memberships[t + 1][i]
                    xor = model.variable(integer=False)
                    model.row([(xor, 1), (a, -1), (b, 1)], 0, math.inf)
                    model.row([(xor, 1), (b, -1), (a, 1)], 0, math.inf)
                    model.row([(xor, 1), (a, -1), (b, -1)], -math.inf, 0)
                    model.row([(xor, 1), (a, 1), (b, 1)], -math.inf, 2)
                    model.row([(a, 1), (b, -1), (prefix, -1)], -1, math.inf)
                    following = model.variable(integer=False)
                    model.row([(following, 1), (prefix, -1)], -math.inf, 0)
                    model.row([(following, 1), (xor, 1)], -math.inf, 1)
                    model.row([(following, 1), (prefix, -1), (xor, 1)], 0, math.inf)
                    prefix = following
                model.row([(prefix, 1), (activations[t + 1], 1)], -math.inf, 1)
        for expression in pair_expressions:
            model.row(expression, 1, math.inf)
        model.row(count_expression, fixed_b if fixed_b is not None else lower,
                  fixed_b if fixed_b is not None else upper)
    except (_Deadline, _Resource) as exc:
        out.stages.append({"stage": "assembly", "status": "time_limit" if isinstance(exc, _Deadline) else "resource_limit", "message": str(exc)})
        return finish("TIME_LIMIT" if isinstance(exc, _Deadline) else "RESOURCE_LIMIT", str(exc))

    def extract(values):
        if universe is not None:
            return [universe[j] for j in range(len(universe)) if values[j] > .5]
        return [tuple(i for i in range(v) if values[memberships[t][i]] > .5)
                for t in range(upper) if values[activations[t]] > .5]

    def solve_stage(name, expression, expected):
        nonlocal numerical_proofs
        model.check()
        c = np.zeros(len(model.lo))
        for index, coefficient in expression:
            c[index] += coefficient
        matrix = csc_array((model.values, (model.row_indices, model.col_indices)),
                           shape=(len(model.lb), len(model.lo)))
        model.check()
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise _Deadline("deadline reached before solver call")
        begun = time.perf_counter()
        with warnings.catch_warnings(record=True) as notices:
            answer = milp(c, integrality=np.asarray(model.integrality), bounds=Bounds(model.lo, model.hi),
                          constraints=LinearConstraint(matrix, model.lb, model.ub),
                          options={"time_limit": remaining, "threads": threads, "random_seed": seed % (2**31), "mip_rel_gap": 0.0})
        stage = {"stage": name, "status": "optimal" if answer.status == 0 else "time_limit" if answer.status == 1 else "infeasible" if answer.status == 2 else "solver_failure",
                 "raw_solver_status": int(answer.status), "message": answer.message,
                 "proof_scope": out.proof_scope, "proof_kind": "solver_numerical",
                 "objective": float(answer.fun) if answer.fun is not None else None,
                 "dual_bound": float(answer.mip_dual_bound) if getattr(answer, "mip_dual_bound", None) is not None else None,
                 "mip_gap": float(answer.mip_gap) if getattr(answer, "mip_gap", None) is not None else None,
                 "elapsed_seconds": time.perf_counter() - begun,
                 "variables": len(model.lo), "binary_variables": sum(model.integrality),
                 "constraints": len(model.lb), "warnings": [str(w.message) for w in notices]}
        valid = False
        if answer.x is not None:
            values = np.asarray(answer.x, dtype=float)
            integer_indices = np.asarray(model.integrality, dtype=bool)
            error = float(np.max(np.abs(values[integer_indices] - np.rint(values[integer_indices])))) if integer_indices.any() else 0.0
            rounded = values.copy()
            rounded[integer_indices] = np.rint(rounded[integer_indices])
            # Reconstruct continuous conjunctions/cap numerically; require all
            # solver constraints and an independently recounted complete cover.
            lhs = np.asarray(matrix @ rounded).ravel()
            violation = float(max(np.max(np.maximum(np.asarray(model.lb) - lhs, 0)),
                                  np.max(np.maximum(lhs - np.asarray(model.ub), 0)),
                                  np.max(np.maximum(np.asarray(model.lo) - rounded, 0)),
                                  np.max(np.maximum(rounded - np.asarray(model.hi), 0))))
            blocks = extract(rounded)
            try:
                cert = certify_schedule(v, k, blocks, source="general_solver_independently_recounted")
                objective = expected(cert)
                cover_valid = cert.complete and cert.simple and cert.b <= upper and error <= 1e-5 and violation <= 1e-5
                valid = cover_valid and answer.fun is not None and abs(objective - answer.fun) <= 1e-5
                stage.update({"integrality_max_error": error, "rounded_constraint_max_violation": violation,
                              "witness_valid": cover_valid, "objective_matches_witness": valid,
                              "witness_hash": cert.schedule_hash, "witness_objective_key": key(v, k, blocks),
                              "independently_recomputed_objective": objective})
                if cover_valid:
                    consider(blocks, upper)
            except (ValueError, TypeError):
                stage["witness_valid"] = False
        out.stages.append(stage)
        if answer.status == 0:
            if not valid:
                raise RuntimeError("solver optimal status has no valid matching independently checked witness")
            numerical_proofs = True
            return int(round(answer.fun))
        if answer.status == 2 and incumbent is None:
            return "infeasible"
        if answer.status == 2 and incumbent is not None:
            raise RuntimeError("solver infeasibility contradicts a validated feasible incumbent")
        if answer.status not in (1, 2):
            raise RuntimeError(f"solver failed with status {answer.status}: {answer.message}")
        return None

    tails = {}
    try:
        if mode == "compact" and fixed_b is None:
            value = solve_stage("min_trials", count_expression, lambda cert: cert.b)
            if value == "infeasible":
                return finish("INFEASIBLE_SOLVER")
            if value is None:
                return finish("TIME_LIMIT", "minimum-count stage unfinished; no later objective was frozen")
            fixed_b = value
            out.minimum_count_proven = True
            model.row(count_expression, value, value)

        if fixed_b is not None and incumbent_cert and incumbent_cert.b == fixed_b and "PAIR_PROFILE_AT_B_CERTIFIED" in incumbent_cert.statuses:
            out.pair_profile_proven = True
            record_math("pair_profile", list(incumbent_cert.concurrence_profile), "fixed-count sharp arithmetic certificate", "at_proved_minimum_count" if mode == "compact" else "within_declared_budget")
        if not out.pair_profile_proven:
            cap_low = ((fixed_b if fixed_b is not None else lower) * pair_slots + pairs - 1) // pairs
            if fixed_b is not None:
                cap_low = max(cap_low, dual_incidence_bound(v, k, fixed_b).lambda_lower_bound)
                if incumbent_cert is not None and incumbent_cert.b == fixed_b:
                    cap_low = max(cap_low, incumbent_cert.lambda_lower_bound)
            cap_high = incumbent_cert.lambda_max if incumbent_cert else upper
            L = None
            if mode == "balanced" and global_cap_attained:
                L = global_cap
            elif fixed_b is not None and incumbent_cert and "LAMBDA_CAP_CERTIFIED" in incumbent_cert.statuses:
                L = incumbent_cert.lambda_max
                record_math("min_cap", L, "attained fixed-count mathematical cap lower bound", "at_proved_minimum_count" if mode == "compact" else "within_declared_budget")
            else:
                cap_variable = model.variable(cap_low, cap_high, integer=False)
                for expression in pair_expressions:
                    model.row(expression + [(cap_variable, -1)], -math.inf, 0)
                L = solve_stage("min_cap", [(cap_variable, 1)], lambda cert: cert.lambda_max)
                if L == "infeasible":
                    return finish("INFEASIBLE_SOLVER")
                if L is None:
                    return finish("TIME_LIMIT", "cap stage unfinished")
                model.lo[cap_variable] = model.hi[cap_variable] = L
            for expression in pair_expressions:
                model.row(expression, 1, L)
            for ell in range(2, L + 1):
                tails[ell] = []
                for expression in pair_expressions:
                    indicator = model.variable()
                    tails[ell].append((indicator, 1))
                    model.row(expression + [(indicator, -ell)], 0, math.inf)
                    model.row(expression + [(indicator, -(L - ell + 1))], -math.inf, ell - 1)
            if L >= 2:
                # Scope: full compact / full budgeted balanced optimization.
                # This is NOT a valid cut for arbitrary fixed-b certificates.
                model.row(count_expression + tails[2], -math.inf, pairs)
            if fixed_b is not None and L >= 2:
                collision = dual_incidence_bound(v, k, fixed_b).collision_lower_bound
                model.row([(index, ell - 1) for ell in tails for index, _ in tails[ell]], collision, math.inf)
            for ell in range(L, 1, -1):
                if ell == 2 and fixed_b is not None:
                    value = fixed_b * pair_slots - pairs - sum(sum(x >= level for x in incumbent_cert.concurrence_profile) for level in range(3, L + 1))
                    record_math("pair_tail_2", value, "fixed pair-slot total and proved higher tails determine N2", "at_proved_higher_pair_tails_and_count")
                else:
                    value = solve_stage(f"pair_tail_{ell}", tails[ell], lambda cert, level=ell: sum(x >= level for x in cert.concurrence_profile))
                    if value is None:
                        return finish("TIME_LIMIT", "pair-tail prefix retained; unfinished tail was not frozen")
                    if value == "infeasible":
                        return finish("INFEASIBLE_SOLVER")
                model.row(tails[ell], value, value)
            out.pair_profile_proven = True

        if incumbent_cert is None:
            return finish("SOLVER_ERROR", "no validated incumbent after completed pair objective")
        fixed_b = incumbent_cert.b
        model.row(count_expression, fixed_b, fixed_b)
        if fixed_b == lower:
            out.minimum_count_proven = True
        if mode == "balanced":
            record_math("count_tie", fixed_b, "complete pair vector fixes count through its total pair slots", "at_proved_pair_profile")
            if fixed_b == lower:
                out.minimum_count_proven = True
        if "ITEM_PROFILE_IDEAL" in incumbent_cert.statuses:
            out.item_profile_proven = True
            record_math("item_profile", list(incumbent_cert.item_deviation_profile), "attained sharp integer item-frequency bound", "at_proved_pair_profile_and_count")
            return finish("OPTIMAL_SOLVER" if numerical_proofs else "OPTIMAL_ANALYTIC")

        # Arithmetic pair early exits still need exact histogram constraints for
        # item-only optimization. All pair tails fix the complete histogram.
        L = incumbent_cert.lambda_max
        if not tails:
            for expression in pair_expressions:
                model.row(expression, 1, L)
            for ell in range(2, L + 1):
                tails[ell] = []
                for expression in pair_expressions:
                    indicator = model.variable()
                    tails[ell].append((indicator, 1))
                    model.row(expression + [(indicator, -ell)], 0, math.inf)
                    model.row(expression + [(indicator, -(L - ell + 1))], -math.inf, ell - 1)
                count = sum(x >= ell for x in incumbent_cert.concurrence_profile)
                model.row(tails[ell], count, count)
        dmax = max(incumbent_cert.item_deviation_profile)
        replication_min = math.ceil((v - 1) / (k - 1))
        replication_values = [r for r in range(replication_min, fixed_b + 1) if abs(v * r - fixed_b * k) <= dmax]
        item_indicators = []
        for i in range(v):
            indicators = [(r, model.variable()) for r in replication_values]
            item_indicators.append(indicators)
            model.row([(j, 1) for _, j in indicators], 1, 1)
            model.row(item_expressions[i] + [(j, -r) for r, j in indicators], 0, 0)
        thresholds = sorted({abs(v * r - fixed_b * k) for r in replication_values if abs(v * r - fixed_b * k)}, reverse=True)
        for delta in thresholds:
            expression = [(j, 1) for indicators in item_indicators for r, j in indicators if abs(v * r - fixed_b * k) >= delta]
            value = solve_stage(f"item_tail_{delta}", expression, lambda cert, threshold=delta: sum(d >= threshold for d in cert.item_deviation_profile))
            if value is None:
                return finish("TIME_LIMIT", "item-tail prefix retained; full item objective unfinished")
            if value == "infeasible":
                return finish("INFEASIBLE_SOLVER")
            model.row(expression, value, value)
        out.item_profile_proven = True
        return finish("OPTIMAL_SOLVER" if numerical_proofs else "OPTIMAL_ANALYTIC")
    except (_Deadline, _Resource) as exc:
        out.stages.append({"stage": "remaining_objectives", "status": "time_limit" if isinstance(exc, _Deadline) else "resource_limit", "message": str(exc), "proof_scope": out.proof_scope})
        return finish("TIME_LIMIT" if isinstance(exc, _Deadline) else "RESOURCE_LIMIT", str(exc))
    except Exception as exc:
        out.stages.append({"stage": "solver_guard", "status": "error", "message": str(exc), "proof_scope": out.proof_scope})
        return finish("SOLVER_ERROR", str(exc))


def main():
    """JSON witness/ledger command line interface for bounded offline runs."""
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Bounded general multiarrangement schedule solver")
    parser.add_argument("--v", type=int, required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--mode", choices=("compact", "balanced"), default="compact")
    parser.add_argument("--max-blocks", type=int)
    parser.add_argument("--max-extra-fraction", type=Decimal, default=Decimal(0))
    parser.add_argument("--reference-count", type=int)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--backend", choices=("auto", "columns", "slots"), default="auto")
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--max-columns", type=int, default=50_000)
    parser.add_argument("--max-variables", type=int, default=300_000)
    parser.add_argument("--max-constraints", type=int, default=1_000_000)
    parser.add_argument("--max-nonzeros", type=int, default=5_000_000)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    options = vars(parser.parse_args())
    output = options.pop("output")
    options["use_cache"] = not options.pop("no_cache")
    try:
        result = solve_schedule(**options)
    except ValueError as exc:
        parser.error(str(exc))
    payload = json.dumps(result.to_dict(), indent=2)
    if output is not None:
        output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
