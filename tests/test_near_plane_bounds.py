"""Scope regressions for isolated new near-plane count bounds."""
from collections import Counter
from itertools import combinations
import math
import pytest

from coverlib.analytic_bounds import (plane_pair_obstruction,
    projective_failed_design_obstruction, one_extra_cap_two_obstruction)
from coverlib.dual_bounds import trial_count_bound_details, cap_two_trial_bound_details
from coverlib.certificates import certify_schedule
from coverlib.constructions import affine_plane, projective_plane
from coverlib.general import solve_schedule


@pytest.mark.parametrize('v,k,unrestricted,conditioned',[
    (36,6,43,44),(100,10,111,111),(43,7,45,45),(111,11,113,113),
    (196,14,211,212),(441,21,463,464),(484,22,507,508),
    (900,30,931,932),(1089,33,1123,1124),(1444,38,1483,1484),
])
def test_new_bounds_keep_cap_condition_separate(v,k,unrestricted,conditioned):
    ordinary=trial_count_bound_details(v,k);cap=cap_two_trial_bound_details(v,k)
    assert ordinary.lower_bound==unrestricted
    assert cap.unrestricted_lower_bound==unrestricted and cap.lower_bound==conditioned
    assert not cap.cap_two_globally_excluded
    if conditioned>unrestricted:
        assert cap.excluded_counts==tuple(range(unrestricted,conditioned))
        assert all(reason.startswith('AFFINE_CAP_TWO') for _,reasons in cap.exclusions for reason in reasons)
        assert all(not reason.startswith('AFFINE_CAP_TWO') for _,reasons in ordinary.exclusions for reason in reasons)


@pytest.mark.parametrize('v,k',[(43,7),(111,11)])
def test_projective_sane_exclusion_is_unconditional(v,k):
    detail=trial_count_bound_details(v,k)
    assert plane_pair_obstruction(v,k)
    assert projective_failed_design_obstruction(v,k)=='SANE_PROJECTIVE_FAILED_DESIGN'
    assert detail.lower_bound==v+2
    assert 'SANE_PROJECTIVE_FAILED_DESIGN' in dict(detail.exclusions)[v+1]


@pytest.mark.parametrize('q',[2,3,4,5,7,8,9])
@pytest.mark.parametrize('kind',['affine','projective'])
def test_actual_planes_and_plane_plus_block_are_never_rejected(q,kind):
    if kind=='affine':v,k,blocks=q*q,q,affine_plane(q)
    else:v,k,blocks=q*q+q+1,q+1,projective_plane(q)
    assert not plane_pair_obstruction(v,k)
    assert not projective_failed_design_obstruction(v,k)
    assert not one_extra_cap_two_obstruction(v,k)
    pc=Counter(p for row in blocks for p in combinations(row,2))
    assert len(pc)==math.comb(v,2) and set(pc.values())=={1}
    if k==2:
        # Every two-set is already a plane block, so a distinct extra row
        # does not exist. The exact boundary itself must remain accepted.
        cert=certify_schedule(v,k,blocks)
        assert cert.complete and cert.trial_lower_bound==cert.b
        assert cert.cap_two_trial_lower_bound==cert.b
        return
    extra=next(row for row in combinations(range(v),k) if row not in blocks)
    cert=certify_schedule(v,k,blocks+[extra])
    assert cert.complete and cert.simple and cert.lambda_max==2
    assert cert.trial_lower_bound==len(blocks)
    assert cert.cap_two_trial_lower_bound<=len(blocks)
    assert 'MINIMUM_TRIALS_CERTIFIED' not in cert.statuses


@pytest.mark.parametrize('order',[12,18,20,25])
def test_unknown_or_unobstructed_orders_stay_unexcluded(order):
    assert plane_pair_obstruction(order*order,order) is None
    k=order+1;v=order*order+order+1
    assert plane_pair_obstruction(v,k) is None
    assert projective_failed_design_obstruction(v,k) is None


@pytest.mark.parametrize('mode',['compact','balanced'])
def test_order_six_budget43_not_unrestricted_infeasible(mode):
    result=solve_schedule(36,6,mode=mode,max_blocks=43,use_cache=False,time_limit=0)
    assert result.status=='TIME_LIMIT' and not result.blocks
    assert result.cap_two_trial_lower_bound==44
    count=next(s for s in result.stages if s['stage']=='trial_lower_bound')
    conditioned=next(s for s in result.stages if s['stage']=='cap_two_trial_lower_bound')
    assert count['objective']==43 and count['proof_scope']=='global_trial_count'
    assert conditioned['objective']==44 and conditioned['proof_scope']=='all_covers_with_pair_cap_at_most_two'
    assert not result.minimum_count_proven and not result.full_objective_proven


@pytest.mark.parametrize('mode',['compact','balanced'])
def test_projective_budget44_unconditionally_infeasible(mode):
    result=solve_schedule(43,7,mode=mode,max_blocks=44,use_cache=False,time_limit=0)
    assert result.status=='INFEASIBLE_ANALYTIC' and not result.blocks
    assert result.cap_two_trial_lower_bound==45
    assert not result.full_objective_proven


def test_general_balanced_conditioned_early_exit_does_not_claim_minimum_count():
    result=solve_schedule(5,3,mode='balanced',max_blocks=5,use_cache=False,time_limit=1)
    assert result.status=='OPTIMAL_ANALYTIC' and result.full_objective_proven
    assert result.certificate.b==5 and result.certificate.lambda_max==2
    assert result.cap_two_trial_lower_bound==5
    assert not result.minimum_count_proven
    assert result.pair_profile_proven and result.item_profile_proven
    assert result.proof_scope=='within_declared_budget_analytic'
    assert any(s['stage']=='cap_conditioned_trial_lower_bound' and s['proof_scope']=='all_cap_two_covers' for s in result.stages)


def test_tight_balanced_budget_retains_cap_three_compact_optimum():
    result=solve_schedule(5,3,mode='balanced',max_blocks=4,use_cache=False,time_limit=1)
    assert result.status=='OPTIMAL_ANALYTIC' and result.full_objective_proven
    assert result.certificate.b==4 and result.certificate.lambda_max==3
    assert result.minimum_count_proven
    assert result.cap_two_trial_lower_bound==5


def test_no_cap_two_cover_boundary_is_metadata_only():
    cap=cap_two_trial_bound_details(5,4)
    assert cap.cap_two_globally_excluded and cap.lower_bound>=cap.unrestricted_lower_bound==3
    result=solve_schedule(5,4,mode='compact',use_cache=False,time_limit=0)
    assert result.full_objective_proven and result.certificate.b==3
    assert result.certificate.lambda_max==3 and result.minimum_count_proven
    assert result.cap_two_globally_excluded
