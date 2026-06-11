"""Tests for exact combinatorial design constructions in coverlib.constructions."""

import pytest

from coverlib.balanced import normalized_balance_metrics
from coverlib.constructions import (
    GF,
    affine_plane,
    constructible_designs,
    projective_plane,
    steiner_triple_system,
)


def _assert_perfect(v: int, k: int, blocks, expected_b: int) -> None:
    assert len(blocks) == expected_b
    for block in blocks:
        assert len(block) == k
        assert len(set(block)) == k
        assert all(0 <= item < v for item in block)
    metrics = normalized_balance_metrics(v, k, blocks)
    assert metrics.complete
    assert metrics.lambda_max == 1
    assert metrics.item_range == 0  # every item in exactly r blocks


class TestGF:
    def test_prime_field_arithmetic(self):
        f = GF(5)
        assert f.add(3, 4) == 2
        assert f.mul(3, 4) == 2
        assert f.mul(2, f.inv(2)) == 1

    @pytest.mark.parametrize("q", [4, 8, 9])
    def test_prime_power_fields_are_fields(self, q):
        f = GF(q)
        # Every nonzero element has a multiplicative inverse.
        for a in range(1, q):
            assert f.mul(a, f.inv(a)) == 1
        # No zero divisors.
        for a in range(1, q):
            for b in range(1, q):
                assert f.mul(a, b) != 0

    def test_unsupported_order_raises(self):
        with pytest.raises(ValueError):
            GF(6)


class TestSteinerTripleSystems:
    @pytest.mark.parametrize("v", [7, 9, 13, 15, 19, 21, 25, 27, 31, 33, 37, 43, 49, 57, 63, 73, 91, 99])
    def test_sts_is_perfect(self, v):
        blocks = steiner_triple_system(v)
        _assert_perfect(v, 3, blocks, v * (v - 1) // 6)

    def test_inadmissible_v_raises(self):
        with pytest.raises(ValueError):
            steiner_triple_system(8)


class TestProjectivePlanes:
    @pytest.mark.parametrize("q", [2, 3, 4, 5, 7, 8, 9])
    def test_projective_plane_is_perfect(self, q):
        v = q * q + q + 1
        blocks = projective_plane(q)
        _assert_perfect(v, q + 1, blocks, v)


class TestAffinePlanes:
    @pytest.mark.parametrize("q", [3, 4, 5, 7, 8, 9])
    def test_affine_plane_is_perfect(self, q):
        blocks = affine_plane(q)
        _assert_perfect(q * q, q, blocks, q * q + q)


def test_constructible_designs_enumeration():
    designs = dict(constructible_designs(max_v=100, min_k=3))
    # Spot checks: the 57x8 projective plane and 49x7 affine plane are present.
    assert (57, 8) in designs
    assert (49, 7) in designs
    assert (13, 4) in designs
    # STS sizes present.
    assert (99, 3) in designs
    for (v, k), blocks in designs.items():
        assert v <= 100
        assert k >= 3
        metrics = normalized_balance_metrics(v, k, blocks)
        assert metrics.complete
        assert metrics.lambda_max == 1
