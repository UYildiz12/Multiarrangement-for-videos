from collections import Counter
from itertools import combinations, product

import pytest

from coverlib.campaign import CampaignCase, improve_case
from coverlib.certificates import certify_schedule, schonheim_lower_bound
from coverlib.constructions import GF, projective_plane, one_point_truncation
from coverlib.recursive import inflate_cover, steiner_neighbor_candidates, transversal_design
from coverlib.refinement import improve_item_balance


FANO = [(0, 1, 3), (0, 2, 6), (0, 4, 5), (1, 2, 4),
        (1, 5, 6), (2, 3, 5), (3, 4, 6)]
UNEVEN = FANO + [(0, 1, 2), (0, 3, 4)]


def recount(v, blocks):
    pairs = Counter(pair for block in blocks for pair in combinations(sorted(block), 2))
    items = Counter(x for block in blocks for x in block)
    assert len(pairs) == v * (v - 1) // 2
    assert len({tuple(sorted(b)) for b in blocks}) == len(blocks)
    return pairs, [items[x] for x in range(v)]


@pytest.mark.parametrize('k,n', [(3, 3), (5, 4), (5, 20), (4, 25), (6, 16)])
def test_transversal_every_two_columns_contain_every_ordered_pair_once(k, n):
    rows = transversal_design(k, n)
    assert len(rows) == n * n
    expected = set(product(range(n), repeat=2))
    for a, b in combinations(range(k), 2):
        assert {(row[a], row[b]) for row in rows} == expected


def test_gf16_distributivity_and_all_nonzero_elements_invertible():
    field = GF(16)
    assert all(field.mul(x, field.inv(x)) == 1 for x in range(1, 16))
    for x, y, z in product(range(16), repeat=3):
        assert field.mul(x, field.add(y, z)) == field.add(field.mul(x, y), field.mul(x, z))


def test_inflation_exact_design_has_proven_minimum_and_equal_item_exposure():
    result = inflate_cover(7, 3, 3, FANO, [(0, 1, 2)])
    pairs, items = recount(21, result)
    assert len(result) == 70
    assert set(pairs.values()) == {1}
    assert set(items) == {10}
    assert len(result) == schonheim_lower_bound(21, 3)


def test_composite_inflation_100_items_five_per_trial():
    inner = one_point_truncation(21, 5, projective_plane(4))
    result = inflate_cover(5, 20, 5, [tuple(range(5))], inner)
    pairs, items = recount(100, result)
    assert len(result) == 505
    assert Counter(pairs.values()) == {1: 4850, 2: 100}
    assert Counter(items) == {25: 75, 26: 25}
    # A five-trial gap remains. This must not acquire a minimum-size certificate.
    assert 'MINIMUM_TRIALS_CERTIFIED' not in certify_schedule(100, 5, result).statuses


def test_unsupported_transversal_and_incomplete_ingredient_rejected():
    with pytest.raises(ValueError, match='supported transversal'):
        transversal_design(7, 6)
    with pytest.raises(ValueError, match='complete pair coverage'):
        inflate_cover(7, 3, 3, FANO[:-1], [(0, 1, 2)])


def test_reuse_arbitrary_steiner_ingredient_for_neighbors():
    # This 21-item ingredient comes from inflation, not the built-in STS path.
    ingredient = inflate_cover(7, 3, 3, FANO, [(0, 1, 2)])
    candidates = dict(steiner_neighbor_candidates(21, 3, ingredient))
    assert set(candidates) == {20, 22}
    for v, candidate in candidates.items():
        certificate = certify_schedule(v, 3, candidate.blocks)
        assert certificate.complete and certificate.lambda_max == 2
        assert certificate.item_range <= 1
    assert steiner_neighbor_candidates(7, 3, UNEVEN) == ()


def test_item_refinement_continues_at_lambda_two_without_adding_trials():
    before_pairs, before_items = recount(7, UNEVEN)
    result = improve_item_balance(7, 3, UNEVEN)
    after_pairs, after_items = recount(7, result)
    assert len(result) == len(UNEVEN) == 9
    assert Counter(before_pairs.values()) == Counter(after_pairs.values())
    assert max(before_pairs.values()) == 2
    assert max(before_items) - min(before_items) == 2
    assert max(after_items) - min(after_items) == 1
    assert sum(x * x for x in after_items) < sum(x * x for x in before_items)
    assert improve_item_balance(7, 3, list(reversed(UNEVEN))) == result
    assert improve_item_balance(7, 3, result) == result
    for seed in range(4):
        seeded = improve_item_balance(7, 3, UNEVEN, seed=seed)
        assert seeded == improve_item_balance(7, 3, UNEVEN, seed=seed)
        pairs, items = recount(7, seeded)
        assert Counter(pairs.values()) == Counter(before_pairs.values())
        assert max(items) - min(items) == 1


def test_perfect_disconnected_cover_is_retained_and_invalid_inputs_rejected():
    assert improve_item_balance(7, 3, FANO) == [list(b) for b in sorted(FANO)]
    with pytest.raises(ValueError, match='complete pair coverage'):
        improve_item_balance(7, 3, FANO[:-1])
    with pytest.raises(ValueError):
        improve_item_balance(7, 3, FANO + [FANO[0]])
    with pytest.raises(ValueError):
        improve_item_balance(7, 3, FANO, max_moves=-1)


def test_campaign_runs_item_pass_on_pair_balanced_cover(tmp_path):
    certificate = certify_schedule(7, 3, UNEVEN)
    case = CampaignCase(7, 3, tuple(UNEVEN), 'fixture', certificate)
    result, wins = improve_case(case, methods=('items',), output_dir=tmp_path)
    assert len(wins) == 1
    assert result.certificate.pair_histogram == certificate.pair_histogram
    assert result.certificate.item_range == 1
    assert len(list(tmp_path.glob('v7_k3_b9_*.txt'))) == 1


@pytest.mark.parametrize('k', [3, 8, 10**9 + 7])
def test_lower_bound_uses_exact_integer_arithmetic(k):
    v = k * k - k + 1
    assert schonheim_lower_bound(v, k) == v
    assert schonheim_lower_bound(k * k, k) == k * (k + 1)


def test_98_item_lower_bound_does_not_round_up_to_491():
    from coverlib.combinatorics import schonheim_lb
    from multiarrangement.core.batch_generator import BatchGenerator
    from multiarrangement.optimize_cover_pure import schonheim_lb as script_bound
    assert schonheim_lower_bound(98, 5) == 490
    assert schonheim_lb(98, 5) == script_bound(98, 5) == 490
    assert BatchGenerator(98, 5).calculate_schonheim_lower_bound() == 490


def test_public_api_retains_better_input_if_optimizer_worsens_item_balance(tmp_path, monkeypatch):
    from coverlib import api
    good = improve_item_balance(7, 3, UNEVEN)
    path = tmp_path/'seed.txt'
    path.write_text(''.join(' '.join(map(str, block))+'\n' for block in good))
    class WorseOptimizer:
        def __init__(self, *args, **kwargs):
            self.blocks = UNEVEN
        def local_search(self, **kwargs):
            pass
    monkeypatch.setattr(api, 'CoverOptimizer', WorseOptimizer)
    monkeypatch.setattr(api, 'structured_cover_candidates', lambda *args: [])
    monkeypatch.setattr(api, 'improve_item_balance', lambda v, k, blocks: blocks)
    result = api.generate_cover(7, 3, seed_file=str(path), group_rounds=0)
    assert result.certificate['item_range'] == 1
    assert result.blocks == [tuple(b) for b in good]
