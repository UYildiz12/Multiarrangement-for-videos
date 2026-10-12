"""Regressions for optional full-objective scheduling and honest proof ledgers."""
from fractions import Fraction
from decimal import Decimal
import builtins
import math
import sys
from types import SimpleNamespace

import pytest

from coverlib.general import solve_schedule


@pytest.mark.parametrize("kwargs", [
    {"v": True}, {"v": 2.5}, {"v": 1}, {"k": 1}, {"k": 7},
    {"mode": "fixed"}, {"mode": []}, {"backend": "restricted"}, {"backend": []}, {"use_cache": 0},
    {"time_limit": math.nan}, {"time_limit": math.inf}, {"time_limit": True},
    {"time_limit": -1}, {"max_blocks": True}, {"max_blocks": 1.2},
    {"max_extra_fraction": math.nan}, {"max_extra_fraction": math.inf},
    {"max_extra_fraction": True}, {"max_extra_fraction": -.1},
    {"max_variables": False}, {"max_constraints": 0}, {"max_columns": 0},
    {"max_nonzeros": 0}, {"threads": 1.5}, {"seed": True},
    {"reference_count": 0}, {"max_blocks": 8, "reference_count": 6},
    {"mode": "compact", "max_extra_fraction": .25},
])
def test_strict_invalid_inputs(kwargs):
    options = {"v": 6, "k": 3, "mode": "balanced", "time_limit": 0}
    options.update(kwargs)
    with pytest.raises(ValueError):
        solve_schedule(**options)


@pytest.mark.parametrize("fraction", [.29, Decimal("0.29"), Fraction(29, 100)])
def test_exact_decimal_budget(fraction):
    result = solve_schedule(4, 3, mode="balanced", reference_count=100,
                            max_extra_fraction=fraction, use_cache=False, time_limit=0)
    assert result.max_blocks == 129
    assert result.effective_max_blocks == 6
    assert result.full_objective_proven


@pytest.mark.parametrize("v,k,b", [(2, 2, 1), (12, 2, 66), (20, 20, 1), (105, 104, 3)])
@pytest.mark.parametrize("mode", ["compact", "balanced"])
def test_generalized_analytic_boundaries(v, k, b, mode):
    result = solve_schedule(v, k, mode=mode, use_cache=False, time_limit=0)
    assert result.status == "OPTIMAL_ANALYTIC"
    assert result.certificate.b == b
    assert result.full_objective_proven
    assert result.minimum_count_proven and result.pair_profile_proven and result.item_profile_proven
    assert result.certificate.complete and result.certificate.simple


def test_impossible_budget_returns_no_oversized_witness():
    result = solve_schedule(12, 2, mode="balanced", max_blocks=65,
                            use_cache=False, time_limit=0)
    assert result.status == "INFEASIBLE_ANALYTIC"
    assert not result.blocks and result.certificate is None
    assert not result.full_objective_proven


def test_unsearched_tight_budget_is_unsolved_not_infeasible():
    result = solve_schedule(5, 3, mode="balanced", max_blocks=5,
                            use_cache=False, time_limit=0)
    assert result.status == "TIME_LIMIT"
    assert not result.blocks
    assert not result.full_objective_proven


def test_tiny_deadline_never_imports_optional_solver(monkeypatch):
    original = builtins.__import__
    def no_scipy(name, *args, **kwargs):
        assert not name.startswith("scipy"), "expired deadline started solver import"
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", no_scipy)
    result = solve_schedule(9, 5, use_cache=False, time_limit=1e-9)
    assert result.status == "TIME_LIMIT"
    assert result.deadline_exhausted
    assert result.blocks and result.certificate.complete
    assert result.elapsed_seconds > 0


def test_output_memory_preflight_even_all_items_boundary():
    result = solve_schedule(100_000, 100_000, max_variables=20, time_limit=0)
    assert result.status == "RESOURCE_LIMIT"
    assert not result.blocks
    assert "verification" in result.message


def test_cache_disabled_does_not_read_any_schedule_table(monkeypatch):
    original = builtins.open
    def audited_open(file, *args, **kwargs):
        assert not any(part in str(file) for part in ("frontier_cache", "balanced_cache", "ljcr_cache"))
        return original(file, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", audited_open)
    result = solve_schedule(103, 3, use_cache=False, time_limit=0)
    assert result.blocks and result.certificate.complete
    assert result.certificate.simple


def test_polynomial_bose_construction_above_index_range():
    result = solve_schedule(105, 3, use_cache=False, time_limit=2)
    assert result.status == "OPTIMAL_ANALYTIC"
    assert result.certificate.b == 1820
    assert result.certificate.lambda_max == 1


@pytest.mark.parametrize("backend", ["columns", "slots"])
def test_exact_balanced_improvement_needs_entire_budget(backend, monkeypatch):
    pytest.importorskip("scipy")
    # Exercise numerical stages even though the direct provider now solves5/3.
    monkeypatch.setattr("coverlib.direct_triples.direct_triple_candidates", lambda *a, **k: [])
    result = solve_schedule(5, 3, mode="balanced", max_blocks=5,
                            use_cache=False, backend=backend, time_limit=60)
    # Four trials cover pairs, but five trials improve the complete pair vector.
    assert result.status == "OPTIMAL_SOLVER"
    assert result.certificate.b == 5
    assert dict(result.certificate.pair_histogram) == {1: 5, 2: 5}
    assert result.certificate.item_deviation_profile == (0,) * 5
    assert result.full_objective_proven and not result.minimum_count_proven
    for stage in result.stages:
        if stage["status"] == "optimal":
            assert stage["witness_valid"] and stage["objective_matches_witness"]
            assert stage["proof_kind"] == "solver_numerical"


def test_slot_conjunctions_do_not_branch_but_memberships_do(monkeypatch):
    scipy = pytest.importorskip("scipy.optimize")
    monkeypatch.setattr("coverlib.direct_triples.direct_triple_candidates", lambda *a, **k: [])
    original = scipy.milp
    seen = []
    def inspect(c, **kwargs):
        seen.append(kwargs["integrality"].copy())
        return original(c, **kwargs)
    monkeypatch.setattr(scipy, "milp", inspect)
    result = solve_schedule(5, 3, mode="balanced", max_blocks=5,
                            use_cache=False, backend="slots", time_limit=60)
    assert result.full_objective_proven
    assert seen[0][:30].sum() == 30  # 5 activations + 5x5 memberships
    assert seen[0][30:].sum() == 0  # exact conjunctions / symmetry / cap
    assert seen[1].sum() == 40  # ten exact binary pair-tail indicators


def test_invalid_numerical_optimum_cannot_freeze_prefix(monkeypatch):
    scipy = pytest.importorskip("scipy.optimize")
    import numpy as np
    def invalid(c, **kwargs):
        return SimpleNamespace(status=0, message="fake optimal", fun=0.0,
                               x=np.zeros(len(c)), mip_dual_bound=0.0, mip_gap=0.0)
    monkeypatch.setattr(scipy, "milp", invalid)
    result = solve_schedule(8, 5, use_cache=False, backend="columns", time_limit=4)
    assert result.status == "SOLVER_ERROR"
    assert result.blocks and result.certificate.complete
    assert not result.minimum_count_proven
    assert not result.full_objective_proven
    assert not result.stages[-2]["witness_valid"]


@pytest.mark.parametrize("stop_status,expected_status", [(1, "TIME_LIMIT"), (4, "SOLVER_ERROR")])
def test_completed_numerical_count_prefix_survives_later_timeout_or_failure(monkeypatch, stop_status, expected_status):
    scipy = pytest.importorskip("scipy.optimize")
    original = scipy.milp
    calls = 0
    def stop_after_count(c, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original(c, **kwargs)
        return SimpleNamespace(status=stop_status, message="controlled later exit",
                               fun=None, x=None, mip_dual_bound=None, mip_gap=None)
    monkeypatch.setattr(scipy, "milp", stop_after_count)
    result = solve_schedule(8, 5, use_cache=False, backend="columns", time_limit=4)
    assert result.status == expected_status
    assert result.certificate.b == 4
    assert result.minimum_count_proven
    assert not result.pair_profile_proven and not result.full_objective_proven
    assert result.proof_kind == "mixed_analytic_and_solver_numerical_prefix"
    successful = [stage for stage in result.stages if stage["status"] == "optimal"]
    assert len(successful) == 1
    assert successful[0]["stage"] == "min_trials"
    assert successful[0]["objective"] == successful[0]["dual_bound"] == 4
    assert successful[0]["witness_valid"]


def test_first_feasible_fixed_budget_witness_certifies_minimum_count_before_tail_timeout(monkeypatch):
    scipy = pytest.importorskip("scipy.optimize")
    monkeypatch.setattr("coverlib.direct_triples.direct_triple_candidates", lambda *a, **k: [])
    original = scipy.milp
    calls = 0
    def stop_after_cap(c, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original(c, **kwargs)
        return SimpleNamespace(status=1, message="controlled tail timeout", fun=None,
                               x=None, mip_dual_bound=None, mip_gap=None)
    monkeypatch.setattr(scipy, "milp", stop_after_cap)
    result = solve_schedule(5, 3, mode="balanced", max_blocks=4,
                            use_cache=False, backend="columns", time_limit=4)
    assert result.status == "TIME_LIMIT"
    assert result.certificate.b == 4
    assert result.minimum_count_proven
    assert not result.pair_profile_proven and not result.full_objective_proven


def test_compact_large_budget_uses_incumbent_count_but_balanced_preserves_budget(monkeypatch):
    scipy = pytest.importorskip("scipy.optimize")
    sizes = []
    def interrupted(c, **kwargs):
        sizes.append(len(c))
        return SimpleNamespace(status=1, message="controlled count timeout", fun=None,
                               x=None, mip_dual_bound=None, mip_gap=None)
    monkeypatch.setattr(scipy, "milp", interrupted)
    common = dict(use_cache=False, backend="slots", time_limit=4, max_variables=400)
    large = solve_schedule(8, 5, max_blocks=999, **common)
    exact = solve_schedule(8, 5, max_blocks=6, **common)
    assert large.max_blocks == 999 and large.effective_max_blocks == 6
    assert exact.max_blocks == exact.effective_max_blocks == 6
    assert large.objective_key == exact.objective_key
    assert large.status == exact.status == "TIME_LIMIT"
    assert sizes == [307, 307]
    balanced = solve_schedule(8, 5, mode="balanced", max_blocks=10, **common)
    assert balanced.max_blocks == balanced.effective_max_blocks == 10
    assert balanced.status == "RESOURCE_LIMIT"
    assert len(sizes) == 2  # Full balanced budget preflight refuses the larger model.


def test_resource_exit_retains_valid_fallback():
    result = solve_schedule(8, 5, use_cache=False, backend="columns",
                            max_columns=1, time_limit=2)
    assert result.status in ("RESOURCE_LIMIT", "SOLVER_UNAVAILABLE")
    assert result.blocks and result.certificate.complete
    assert not result.full_objective_proven


@pytest.mark.parametrize("v,k,options", [
    (12, 2, {"time_limit": 0}),
    (5, 3, {"mode": "balanced", "max_blocks": 5, "backend": "columns", "time_limit": 4}),
])
def test_desktop_and_hosted_optional_api_parity(v, k, options):
    if options["time_limit"]:
        pytest.importorskip("scipy")
    import multiarrangement as ma
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "server"))
    try:
        from ma_core.batch_generator import solve_schedule as hosted
        desktop = ma.solve_schedule(v, k, use_cache=False, **options)
        server = hosted(v, k, use_cache=False, **options)
        assert desktop.objective_key == server.objective_key
        assert desktop.full_objective_proven == server.full_objective_proven
        assert desktop.full_objective_proven
        if not options["time_limit"]:
            assert desktop.blocks == server.blocks
            assert desktop.stages == server.stages
    finally:
        sys.path.pop(0)
