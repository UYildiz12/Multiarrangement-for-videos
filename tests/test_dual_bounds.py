"""Independent small-state checks and finite witness proofs for dual bounds."""
from collections import Counter
from itertools import combinations
from pathlib import Path
import json
import math

import pytest

from coverlib.certificates import certify_schedule
from coverlib.dual_bounds import (
    trial_count_bound_details,
    dual_incidence_bound, maximum_collisions_under_cap,
    relaxed_concurrence_profile, trial_count_lower_bound,
)


def _partitions(total, count, smallest=1):
    if not count:
        if total == 0:
            yield ()
        return
    for first in range(smallest, total // count + 1):
        for tail in _partitions(total - first, count - 1, first):
            yield (first,) + tail


@pytest.mark.parametrize("v", [2, 3, 4])
def test_collision_cap_and_lex_relaxation_against_every_small_integer_profile(v):
    pair_count = math.comb(v, 2)
    for total in range(pair_count, 4 * pair_count + 1):
        profiles = [tuple(reversed(p)) for p in _partitions(total, pair_count)]
        for cap in range(1, 5):
            eligible = [p for p in profiles if p[0] <= cap]
            expected_maximum = max(
                (sum(math.comb(x, 2) for x in p) for p in eligible), default=None,
            )
            assert maximum_collisions_under_cap(pair_count, total - pair_count, cap) == expected_maximum
            for threshold in range(2 * total + 1):
                feasible = [p for p in eligible if sum(math.comb(x, 2) for x in p) >= threshold]
                # k=2 makes b=total produce the requested abstract profile sum.
                actual = relaxed_concurrence_profile(v, 2, total, cap, threshold)
                assert actual == (min(feasible) if feasible else None)


@pytest.mark.parametrize("v,k", [(4, 3), (5, 3), (5, 4), (6, 4), (6, 5)])
def test_dual_identity_and_necessary_bounds_for_all_small_complete_simple_covers(v, k):
    universe = list(combinations(range(v), k))
    for b in range(1, min(5, len(universe)) + 1):
        for blocks in combinations(universe, b):
            counts = Counter(pair for block in blocks for pair in combinations(block, 2))
            if len(counts) != math.comb(v, 2):
                continue
            collisions = sum(math.comb(x, 2) for x in counts.values())
            intersections = sum(math.comb(len(set(a) & set(c)), 2) for a, c in combinations(blocks, 2))
            assert collisions == intersections
            bound = dual_incidence_bound(v, k, b)
            assert collisions >= bound.collision_lower_bound
            assert max(counts.values()) >= bound.lambda_lower_bound
            assert tuple(sorted(counts.values(), reverse=True)) >= bound.relaxed_profile
            lower, excluded = trial_count_lower_bound(v, k)
            assert b >= lower
            assert b not in excluded


@pytest.mark.parametrize("v,k,b,histogram", [
    (14, 6, 7, {1: 84, 3: 7}),
    (21, 9, 7, {1: 189, 3: 21}),
    (26, 8, 13, {1: 312, 4: 13}),
    (42, 10, 21, {1: 840, 5: 21}),
])
def test_stored_witnesses_attain_full_finite_objective(v, k, b, histogram):
    package = Path(__file__).parents[1] / "multiarrangement"
    manifest = json.loads((package / "frontier_cache/index.json").read_text())
    record = min(manifest["entries"][f"{v},{k}"], key=lambda row: row["b"])
    blocks = [tuple(map(int, line.split())) for line in (package / record["path"]).read_text().splitlines() if line.strip()]
    certificate = certify_schedule(v, k, blocks)
    assert certificate.b == b
    assert dict(certificate.pair_histogram) == histogram
    assert "DUAL_INCIDENCE_PROFILE_OPTIMUM" in certificate.statuses
    assert "LEXICOGRAPHIC_OPTIMUM_CERTIFIED" in certificate.statuses


def _compact_certificate(v, k):
    package = Path(__file__).parents[1] / "multiarrangement"
    manifest = json.loads((package / "frontier_cache/index.json").read_text())
    record = min(manifest["entries"][f"{v},{k}"], key=lambda row: row["b"])
    blocks = [tuple(map(int, line.split())) for line in (package / record["path"]).read_text().splitlines() if line.strip()]
    return certify_schedule(v, k, blocks)


def test_fixed_trial_certificate_does_not_claim_minimum_trials():
    """The fixed-count profile certificate does not prove the count minimal: at (11,6) the analytic bounds stop below
    six trials, and minimality comes only from the imported published bound C(11,6,2) >= 6."""
    certificate = _compact_certificate(11, 6)
    assert "DUAL_INCIDENCE_PROFILE_OPTIMUM" in certificate.statuses
    assert trial_count_bound_details(11, 6).lower_bound < certificate.b
    assert "MINIMUM_TRIALS_CERTIFIED" in certificate.statuses
    assert "PUBLISHED_BOUND_MINIMUM_TRIALS" in certificate.statuses
    assert certificate.published_bound_source == "LJCR_V1_2"


@pytest.mark.parametrize("v,k,b", [(56, 8, 57), (90, 10, 91)])
def test_bounds_proved_in_the_paper_certify_minimum_trials(v, k, b):
    certificate = _compact_certificate(v, k)
    assert certificate.b == certificate.trial_lower_bound == b
    assert certificate.published_bound_source == "MULTIARRANGEMENT_SI"
    assert {"MINIMUM_TRIALS_CERTIFIED", "PUBLISHED_BOUND_MINIMUM_TRIALS"} <= set(certificate.statuses)
    assert "BEST_FOUND_WITH_GAP" not in certificate.statuses


def test_imported_bound_raises_the_36_6_gap_without_claiming_minimality():
    certificate = _compact_certificate(36, 6)
    assert certificate.trial_lower_bound == 44 and certificate.b == 46
    assert "MINIMUM_TRIALS_CERTIFIED" not in certificate.statuses
    assert "BEST_FOUND_WITH_GAP" in certificate.statuses


def test_a_cover_below_a_proven_bound_is_rejected(monkeypatch):
    import coverlib.certificates as certificates

    blocks = [tuple(b) for b in combinations(range(7), 3)]  # 35 trials, a valid cover of 7 items
    monkeypatch.setattr(certificates, "published_lower_bound", lambda v, k: (36, "TEST"))
    with pytest.raises(AssertionError):
        certificates.certify_schedule(7, 3, blocks)


@pytest.mark.parametrize("v,k,arithmetic,stronger", [(10, 4, 8, 9), (7, 4, 4, 5), (9, 5, 4, 5)])
def test_dual_collision_bound_excludes_lower_trial_count(v, k, arithmetic, stronger):
    lower, excluded = trial_count_lower_bound(v, k)
    assert lower == stronger
    assert excluded == (arithmetic,)
    with pytest.raises(ValueError, match="exclude"):
        dual_incidence_bound(v, k, arithmetic)
    package = Path(__file__).parents[1] / "multiarrangement"
    manifest = json.loads((package / "frontier_cache/index.json").read_text())
    record = min(manifest["entries"][f"{v},{k}"], key=lambda row: row["b"])
    blocks = [tuple(map(int, line.split())) for line in (package / record["path"]).read_text().splitlines() if line.strip()]
    certificate = certify_schedule(v, k, blocks)
    assert "DUAL_INCIDENCE_MINIMUM_TRIALS" in certificate.statuses
    assert "MINIMUM_TRIALS_CERTIFIED" in certificate.statuses


def test_complete_single_block_and_incomplete_inputs():
    exact = certify_schedule(8, 8, [tuple(range(8))])
    assert exact.lambda_lower_bound == 1
    assert exact.dual_collision_lower_bound == 0
    assert "LEXICOGRAPHIC_OPTIMUM_CERTIFIED" in exact.statuses
    incomplete = certify_schedule(5, 3, [(0, 1, 2)])
    assert not incomplete.complete
    assert "DUAL_INCIDENCE_PROFILE_OPTIMUM" not in incomplete.statuses


def test_exact_balanced_upgrade_preserves_the_compact_selection_and_certificate_scope():
    from coverlib.frontier import select_frontier_cover
    package = Path(__file__).parents[1] / "multiarrangement"
    compact = select_frontier_cover(9, 5, package_dir=package, mode="compact")
    zero_surplus = select_frontier_cover(9, 5, package_dir=package, mode="balanced", max_blocks=5)
    balanced = select_frontier_cover(9, 5, package_dir=package, mode="balanced", max_blocks=6)
    assert compact.certificate.b == 5
    assert zero_surplus.certificate.schedule_hash == compact.certificate.schedule_hash
    assert balanced.certificate.b == 6
    assert balanced.source == "exact_full_universe_balanced_audit"
    assert dict(balanced.certificate.pair_histogram) == {1: 15, 2: 18, 3: 3}
    assert dict(balanced.certificate.item_histogram) == {3: 6, 4: 3}
    assert balanced.certificate.concurrence_profile < compact.certificate.concurrence_profile
    assert "DUAL_INCIDENCE_PROFILE_OPTIMUM" in balanced.certificate.statuses
    assert "ITEM_PROFILE_IDEAL" in balanced.certificate.statuses
    assert "MINIMUM_TRIALS_CERTIFIED" not in balanced.certificate.statuses
    assert "LEXICOGRAPHIC_OPTIMUM_CERTIFIED" not in balanced.certificate.statuses
