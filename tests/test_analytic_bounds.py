"""Exhaustive graph/cover checks and independent cache certificate validation."""
from collections import Counter
from itertools import combinations, combinations_with_replacement
from pathlib import Path
import json
import math
from fractions import Fraction

import pytest

from coverlib.analytic_bounds import (
    cap_two_degree_feasible, complement_boundary_profiles, horsley_trial_lower_bound,
    horsley_trial_bounds, is_graphical, plane_pair_obstruction, rational_sqrt_lower,
    row_degree_bound,
)
from coverlib.certificates import certify_schedule
from coverlib.dual_bounds import trial_count_bound_details, trial_count_lower_bound


def _graph_degree_profiles(v):
    edges = list(combinations(range(v), 2))
    profiles = set()
    for mask in range(1 << len(edges)):
        degree = [0] * v
        for index, (i, j) in enumerate(edges):
            if mask & (1 << index):
                degree[i] += 1
                degree[j] += 1
        profiles.add(tuple(sorted(degree)))
    return profiles


@pytest.mark.parametrize("v", range(2, 7))
def test_cap_two_balancing_against_every_simple_excess_graph(v):
    # Enumerating all simple graphs is independent of the degree decision
    # algorithm and checks every possible residue-compatible allocation.
    profiles = _graph_degree_profiles(v)
    for k in range(2, v + 1):
        rmin = (v + k - 3) // (k - 1)
        for b in range(1, math.comb(v, 2) + 1):
            possible = False
            for degrees in profiles:
                if any((d + v - 1) % (k - 1) for d in degrees):
                    continue
                r = tuple((d + v - 1) // (k - 1) for d in degrees)
                if min(r) >= rmin and max(r) <= b and sum(r) == b * k:
                    possible = True
                    break
            assert cap_two_degree_feasible(v, k, b) == possible
    if v <= 5:
        for degrees in combinations_with_replacement(range(v), v):
            assert is_graphical(degrees) == (degrees in profiles)


@pytest.mark.parametrize("v", range(2, 6))
def test_analytic_bounds_for_every_small_simple_complete_cover(v):
    for k in range(2, v + 1):
        universe = list(combinations(range(v), k))
        detail = trial_count_bound_details(v, k)
        for mask in range(1, 1 << len(universe)):
            blocks = [B for index, B in enumerate(universe) if mask & (1 << index)]
            pair = Counter(p for B in blocks for p in combinations(B, 2))
            if len(pair) != math.comb(v, 2):
                continue
            b = len(blocks)
            r = tuple(sum(i in B for B in blocks) for i in range(v))
            row = row_degree_bound(v, k, b)
            assert row.infeasible_reason is None
            assert b >= detail.lower_bound
            assert b >= detail.horsley_lower_bound
            assert b not in detail.excluded_counts
            assert max(pair.values()) >= row.lambda_lower_bound
            assert max(pair.values()) > 2 or not row.cap_two_excluded
            if row.forced_pair_profile is not None:
                assert tuple(sorted(pair.values(), reverse=True)) == row.forced_pair_profile
                assert tuple(sorted(r, reverse=True)) == row.forced_item_profile


@pytest.mark.parametrize("v,k,expected", [(9, 4, 8), (15, 5, 13), (16, 6, 10),
                                         (17, 9, 6), (19, 10, 6), (28, 10, 11)])
def test_published_trial_bound_and_its_attaining_witness(v, k, expected):
    assert horsley_trial_lower_bound(v, k) == expected
    detail = trial_count_bound_details(v, k)
    assert detail.lower_bound == expected
    assert "HORSLEY_THEOREM_1" in dict(detail.exclusions)[expected - 1]
    package = Path(__file__).parents[1] / "multiarrangement"
    manifest = json.loads((package / "frontier_cache/index.json").read_text())
    row = min(manifest["entries"][f"{v},{k}"], key=lambda r: r["b"])
    blocks = [tuple(map(int, line.split())) for line in
              (package / row["path"]).read_text().splitlines() if line.strip()]
    certificate = certify_schedule(v, k, blocks)
    assert certificate.b == expected
    assert "HORSLEY_MINIMUM_TRIALS" in certificate.statuses
    assert "MINIMUM_TRIALS_CERTIFIED" in certificate.statuses
    if (v, k) in [(9, 4), (17, 9), (19, 10)]:
        assert "LEXICOGRAPHIC_OPTIMUM_CERTIFIED" in certificate.statuses


def test_zero_residue_single_incidence_excludes_a_trial_count():
    row = row_degree_bound(33, 5, 53)
    assert row.infeasible_reason == "ROW_ZERO_RESIDUE_SINGLE_INCIDENCE"
    detail = trial_count_bound_details(33, 5)
    assert detail.lower_bound == 54
    assert "ROW_ZERO_RESIDUE_SINGLE_INCIDENCE" in dict(detail.exclusions)[53]


@pytest.mark.parametrize("v,k,b", [(5, 3, 4), (11, 3, 19), (22, 4, 39), (97, 5, 466)])
def test_two_extra_incidences_force_whole_profiles(v, k, b):
    row = row_degree_bound(v, k, b)
    rmin = (v - 1) // (k - 1)
    assert row.infeasible_reason is None
    assert row.lambda_lower_bound == k
    assert row.forced_pair_profile == (k,) + (1,) * (math.comb(v, 2) - 1)
    assert row.forced_item_profile == (rmin + 1,) * 2 + (rmin,) * (v - 2)
    package = Path(__file__).parents[1] / "multiarrangement"
    manifest = json.loads((package / "frontier_cache/index.json").read_text())
    record = min(manifest["entries"][f"{v},{k}"], key=lambda r: r["b"])
    blocks = [tuple(map(int, line.split())) for line in
              (package / record["path"]).read_text().splitlines() if line.strip()]
    certificate = certify_schedule(v, k, blocks)
    assert "ROW_DEGREE_PROFILE_OPTIMUM" in certificate.statuses
    assert "LEXICOGRAPHIC_OPTIMUM_CERTIFIED" in certificate.statuses


def test_forced_pair_exceeding_replication_excludes_the_count():
    row = row_degree_bound(7, 4, 4)
    assert row.infeasible_reason == "ROW_FORCED_PAIR_EXCEEDS_REPLICATION"
    assert row.forced_pair_profile is None


def test_irredundancy_is_not_imposed_on_an_arbitrary_fixed_count_cover():
    # All four triples are redundant but give a legitimate fixed-b witness.
    # The optimizer's private-pair cut must not leak into generic validation.
    blocks = list(combinations(range(4), 3))
    cert = certify_schedule(4, 3, blocks)
    assert cert.complete and cert.simple
    assert dict(cert.pair_histogram) == {2: 6}
    assert "PAIR_PROFILE_AT_B_CERTIFIED" in cert.statuses
    assert "MINIMUM_TRIALS_CERTIFIED" not in cert.statuses
    assert "LEXICOGRAPHIC_OPTIMUM_CERTIFIED" not in cert.statuses


@pytest.mark.parametrize("q", [6, 14, 21, 22, 30, 33])
def test_general_bruck_ryser_obstruction_requires_its_exact_hypotheses(q):
    assert plane_pair_obstruction(q * q, q) == "PROJECTIVE_PLANE_BRUCK_RYSER"
    assert plane_pair_obstruction(q * q + 1, q) is None
    detail = trial_count_bound_details(q * q, q)
    assert detail.lower_bound > q * (q + 1)
    assert "PROJECTIVE_PLANE_BRUCK_RYSER" in dict(detail.exclusions)[q * (q + 1)]


@pytest.mark.parametrize("q", [2, 3, 4, 5, 7, 8, 9, 12, 18, 20, 25])
def test_plane_guard_never_treats_unknown_orders_as_nonexistent(q):
    assert plane_pair_obstruction(q * q, q) is None


def test_lam_order_ten_guard_and_global_cap_certificate():
    assert plane_pair_obstruction(100, 10) == "PROJECTIVE_PLANE_LAM_ORDER_10"
    detail = trial_count_bound_details(100, 10)
    assert detail.lower_bound == 111
    assert dict(detail.exclusions)[110] == ("PROJECTIVE_PLANE_LAM_ORDER_10",)
    from coverlib.repaired_transversal import repaired_transversal
    cert = certify_schedule(100, 10, repaired_transversal(11).blocks)
    assert cert.global_lambda_lower_bound == 2
    assert "GLOBAL_LAMBDA_CAP_CERTIFIED" in cert.statuses
    assert "LEXICOGRAPHIC_OPTIMUM_CERTIFIED" not in cert.statuses


def test_rational_square_root_is_directed_and_never_overstates_theorem_14c():
    for numerator in range(100):
        for denominator in range(1, 20):
            value = Fraction(numerator, denominator)
            for scale in [1, 7, 100, 10**12]:
                lower = rational_sqrt_lower(value, scale)
                assert lower * lower <= value
                assert value < (lower + Fraction(1, scale))**2


@pytest.mark.parametrize("v,k,expected", [(12, 5, 9), (13, 5, 10), (12, 7, 5), (14, 8, 5)])
def test_extended_published_bounds_strengthen_dense_settings(v, k, expected):
    detail = trial_count_bound_details(v, k)
    assert detail.lower_bound == expected
    assert max(dict(horsley_trial_bounds(v, k)).values()) == expected
    assert any(reason.startswith("HORSLEY_THEOREM_1") for reason in dict(detail.exclusions)[expected - 1])


def test_published_hypotheses_and_integer_formula_match_an_independent_grid_screen():
    # Independently evaluate the rational branches, without production's
    # helper or any floating-point ceiling. Cover tests check their validity.
    for v in range(3, 101):
        for k in range(3, v + 1):
            r = (v - 2) // (k - 1) + 1
            d = r * (k - 1) - v + 1
            n = r - 1
            expected = {}
            if k < v and d < n:
                expected["HORSLEY_THEOREM_1"] = (v * (r + 1) + k) // (k + 1)
            if k < v and r < k:
                branches = []
                if d >= n:
                    branches.append(("HORSLEY_THEOREM_11", Fraction(r, 2 * (d + 1)), Fraction(r, 2 * (d + k))))
                else:
                    branches.append(("HORSLEY_THEOREM_14A", Fraction(1) - Fraction(d**2, 2 * n * r), Fraction(r + 1, 2 * (d + k))))
                    if d * 2 >= n and d * (d + k - 1) < n * r:
                        branches.append(("HORSLEY_THEOREM_14B", Fraction(1), Fraction(1) - Fraction(d * (d + k - 1), n * r)))
                for reason, alpha, beta in branches:
                    value = v * (r * (alpha - beta) + alpha) / (1 + k * (alpha - beta))
                    expected[reason] = (value.numerator + value.denominator - 1) // value.denominator
            actual = dict(horsley_trial_bounds(v, k))
            assert {reason: bound for reason, bound in actual.items() if not reason.endswith("RATIONAL_LOWER")} == expected


@pytest.mark.parametrize("v", [3, 4, 5, 6, 10, 21, 105])
def test_complement_boundary_profiles_and_full_compact_proof(v):
    universe = [tuple(i for i in range(v) if i != missing) for missing in range(v)]
    assert complement_boundary_profiles(v, v - 1, 2) is None
    previous = None
    for b in range(3, min(v, 8) + 1):
        cert = certify_schedule(v, v - 1, universe[:b])
        forced = complement_boundary_profiles(v, v - 1, b)
        assert cert.concurrence_profile == forced[0]
        assert tuple(sorted((sum(i in B for B in universe[:b]) for i in range(v)), reverse=True)) == forced[1]
        assert "COMPLEMENT_BOUNDARY_PROFILE_OPTIMUM" in cert.statuses
        assert "PAIR_PROFILE_AT_B_CERTIFIED" in cert.statuses
        assert ("LEXICOGRAPHIC_OPTIMUM_CERTIFIED" in cert.statuses) == (b == 3)
        if previous is not None:
            assert previous < cert.concurrence_profile
        previous = cert.concurrence_profile


@pytest.mark.parametrize("v", range(2, 21))
def test_trivial_domains_remain_exact_and_published_theorem_is_not_applied(v):
    assert horsley_trial_lower_bound(v, 2) == 0
    assert horsley_trial_lower_bound(v, v) == 0
    assert trial_count_lower_bound(v, 2) == (math.comb(v, 2), ())
    assert trial_count_lower_bound(v, v) == (1, ())
    pair_blocks = list(combinations(range(v), 2))
    for k, blocks in [(2, pair_blocks), (v, [tuple(range(v))])]:
        assert "LEXICOGRAPHIC_OPTIMUM_CERTIFIED" in certify_schedule(v, k, blocks).statuses


def test_every_indexed_witness_reproduces_dynamic_arithmetic_certificate():
    package = Path(__file__).parents[1] / "multiarrangement"
    manifest = json.loads((package / "frontier_cache/index.json").read_text())
    verified = 0
    for key, records in manifest["entries"].items():
        v, k = map(int, key.split(","))
        for record in records:
            blocks = [tuple(map(int, line.split())) for line in
                      (package / record["path"]).read_text().splitlines() if line.strip()]
            cert = certify_schedule(v, k, blocks, source=record["source"])
            assert cert.complete and cert.simple
            assert cert.schedule_hash == record["schedule_hash"]
            assert cert.b >= cert.trial_lower_bound
            assert cert.lambda_max >= cert.lambda_lower_bound
            actual = json.loads(json.dumps(cert.to_dict()))
            assert actual == {field: value for field, value in record.items() if field != "path"}
            # Independently check each exact row identity from blocks.
            pairs = Counter(p for B in blocks for p in combinations(B, 2))
            for i in range(v):
                assert sum(pairs[tuple(sorted((i, j)))] for j in range(v) if j != i) == (k - 1) * sum(i in B for B in blocks)
            verified += 1
    assert len(manifest["entries"]) == 756
    assert verified == manifest["frontier_points"]
