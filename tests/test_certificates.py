from __future__ import annotations

import pytest

from coverlib.certificates import (
    balanced_sort_key,
    certify_schedule,
    pareto_frontier,
)
from coverlib.constructions import one_point_extension_design, projective_plane


def test_exact_design_receives_formal_certificates():
    blocks = projective_plane(3)
    certificate = certify_schedule(13, 4, blocks, source="projective_plane")

    assert certificate.complete
    assert certificate.b == 13
    assert certificate.lambda_max == 1
    assert "MINIMUM_TRIALS_CERTIFIED" in certificate.statuses
    assert "IDEAL_HISTOGRAM_AT_B" in certificate.statuses
    assert "ITEM_PROFILE_IDEAL" in certificate.statuses
    assert "PARETO_CERTIFIED" in certificate.statuses


def test_one_point_extension_receives_compact_pareto_certificate():
    blocks = one_point_extension_design(58, 8)
    assert blocks is not None

    certificate = certify_schedule(58, 8, blocks, source="one_point_extension")

    assert certificate.b == certificate.schonheim_lower_bound == 66
    assert certificate.pair_histogram == ((1, 1458), (2, 195))
    assert certificate.item_range == 1
    assert "PARETO_CERTIFIED" in certificate.statuses


def test_balanced_key_uses_full_concurrence_profile():
    all_pairs = [[i, j] for i in range(6) for j in range(i + 1, 6)]
    ideal = all_pairs + [[0, 1], [0, 2], [0, 3]]
    concentrated = all_pairs + [[0, 1], [0, 1], [0, 1]]

    assert balanced_sort_key(6, 2, ideal) < balanced_sort_key(6, 2, concentrated)


def test_frontier_preserves_nondominated_existing_candidates():
    compact = certify_schedule(
        13,
        4,
        projective_plane(3),
        source="existing_exact",
    )
    duplicate_provenance = certify_schedule(
        13,
        4,
        projective_plane(3),
        source="new_verification",
    )

    frontier = pareto_frontier([compact, duplicate_provenance])

    assert {certificate.source for certificate in frontier} == {
        "existing_exact",
        "new_verification",
    }


def test_frontier_rejects_mixed_parameter_sets():
    first = certify_schedule(13, 4, projective_plane(3))
    second_blocks = one_point_extension_design(58, 8)
    assert second_blocks is not None
    second = certify_schedule(58, 8, second_blocks)

    with pytest.raises(ValueError, match=r"same \(v, k\)"):
        pareto_frontier([first, second])
