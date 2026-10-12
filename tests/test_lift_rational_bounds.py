"""Scope and exact-arithmetic regressions for the isolated second patch layer."""
from itertools import combinations, product
import pytest

from coverlib.analytic_bounds import (affine_one_extra_lift_hasse_primes,
    one_extra_cap_two_obstruction, plane_pair_obstruction, is_graphical)
from coverlib.dual_bounds import trial_count_bound_details, cap_two_trial_bound_details


@pytest.mark.parametrize('k,primes',[
    (3,()), (6,(2,3)), (10,()), (15,(2,3)), (55,()), (66,(3,11)), (105,(3,7)), (190,(2,19)),
])
def test_exact_local_places_match_independent_full_gram(k,primes):
    # Recorded by independent Schur LDL / a different integer orthogonal basis,
    # with finite primitive-conic oracles. Not a solver or floating-point test.
    assert affine_one_extra_lift_hasse_primes(k)==primes


@pytest.mark.parametrize('k',[0,1,2,4,7,True,3.0,float('nan'),float('inf')])
def test_helper_rejects_invalid_or_nontriangular_inputs(k):
    with pytest.raises(ValueError):
        affine_one_extra_lift_hasse_primes(k)


@pytest.mark.parametrize('k',[66,105,190])
def test_new_general_lift_bound_is_only_cap_conditioned(k):
    v=k*k;baseline=k*(k+1)
    assert plane_pair_obstruction(v,k)
    assert one_extra_cap_two_obstruction(v,k)=='AFFINE_CAP_TWO_PERMUTATION_LIFT_RATIONAL_HASSE'
    ordinary=trial_count_bound_details(v,k)
    conditioned=cap_two_trial_bound_details(v,k)
    assert ordinary.lower_bound==baseline+1
    assert conditioned.lower_bound==baseline+2
    assert conditioned.unrestricted_lower_bound==ordinary.lower_bound
    assert dict(conditioned.exclusions)[baseline+1]==('AFFINE_CAP_TWO_PERMUTATION_LIFT_RATIONAL_HASSE',)
    assert not conditioned.cap_two_globally_excluded
    assert all('LIFT' not in reason for _,reasons in ordinary.exclusions for reason in reasons)


def test_unknown_plane_branch_cannot_be_excluded_by_a_negative_lift():
    # A failed lift cannot exclude the alternative all-high / affine-plane branch.
    assert affine_one_extra_lift_hasse_primes(15)==(2,3)
    assert plane_pair_obstruction(15*15,15) is None
    assert one_extra_cap_two_obstruction(15*15,15) is None


def test_order_six_provenance_and_open_order_ten_stay_exactly_unchanged():
    assert one_extra_cap_two_obstruction(36,6)=='AFFINE_CAP_TWO_ORDER_6_PERMUTATION_LIFT_EISENSTEIN'
    assert trial_count_bound_details(36,6).lower_bound==43
    assert cap_two_trial_bound_details(36,6).lower_bound==44
    assert one_extra_cap_two_obstruction(100,10) is None
    assert trial_count_bound_details(100,10).lower_bound==111
    assert cap_two_trial_bound_details(100,10).lower_bound==111


@pytest.mark.parametrize('k',[3,6,10,66,105,190])
def test_conditional_lift_helper_does_not_touch_other_arena_sizes(k):
    assert one_extra_cap_two_obstruction(k*k+1,k) is None


def test_graphical_early_exit_agrees_with_complete_small_graph_oracle():
    for vertices in range(1,6):
        edges=list(combinations(range(vertices),2));valid=set()
        for bits in product((0,1),repeat=len(edges)):
            degrees=[0]*vertices
            for present,(a,b) in zip(bits,edges):
                if present:degrees[a]+=1;degrees[b]+=1
            valid.add(tuple(sorted(degrees)))
        for degrees in product(range(vertices),repeat=vertices):
            assert is_graphical(degrees)==(tuple(sorted(degrees)) in valid)
    assert is_graphical((0,)*36100)
    assert is_graphical((2,2,2)+(0,)*36097)
