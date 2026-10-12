import itertools
import json
from collections import Counter
from pathlib import Path

import pytest

from coverlib.certificates import certify_schedule
from coverlib.constructions import structured_cover_candidates
from coverlib.expansion import shared_hole_cover, puncture_cover, neutral_item_walk


def exact(v,k):
    return next(c.blocks for c in structured_cover_candidates(v,k)
                if certify_schedule(v,k,c.blocks).lambda_max==1)


def test_single_common_point_preserves_exactness():
    # Four 12-point groups sharing one point yield a 2-(49,4,1) design.
    blocks=shared_hole_cover(4,12,1,4,[tuple(range(4))],exact(13,4))
    pairs=Counter(p for b in blocks for p in itertools.combinations(sorted(b),2))
    items=Counter(x for b in blocks for x in b)
    assert len(blocks)==196
    assert len(pairs)==1176 and set(pairs.values())=={1}
    assert set(items.values())=={16}


def test_shared_hole_pair_multiplicity_is_accumulated():
    inner=[(0,1,2,3),(0,1,2,4),(0,1,3,4)]
    blocks=shared_hole_cover(4,3,2,4,[tuple(range(4))],inner)
    counts=Counter(p for b in blocks for p in itertools.combinations(sorted(b),2))
    assert len(counts)==91 and min(counts.values())>=1
    assert counts[12,13]==4


@pytest.mark.parametrize('seed',range(3))
def test_multiple_point_deletion_keeps_every_surviving_pair(seed):
    blocks=puncture_cover(13,10,4,exact(13,4),seed)
    assert all(len(set(b))==4 for b in blocks)
    assert len(blocks)==len(set(blocks))
    assert set(p for b in blocks for p in itertools.combinations(b,2))==set(itertools.combinations(range(10),2))
    assert blocks==puncture_cover(13,10,4,exact(13,4),seed)


def test_neutral_walk_escapes_a_strict_item_balance_local_stop():
    data=json.loads((Path(__file__).parent/'fixtures/neutral_walk_51_6.json').read_text())
    before=certify_schedule(51,6,data['blocks'])
    from coverlib.refinement import improve_item_balance
    strict=certify_schedule(51,6,improve_item_balance(51,6,data['blocks']))
    after_blocks=neutral_item_walk(51,6,data['blocks'],seed=0,max_moves=50)
    after=certify_schedule(51,6,after_blocks)
    assert strict.item_deviation_profile==before.item_deviation_profile
    assert after.item_deviation_profile<before.item_deviation_profile
    assert after.b==before.b and after.pair_histogram==before.pair_histogram
    assert after_blocks==neutral_item_walk(51,6,data['blocks'],seed=0,max_moves=50)


def test_invalid_expansion_domains_rejected():
    with pytest.raises(ValueError):shared_hole_cover(4,3,4,4,[tuple(range(4))],[])
    with pytest.raises(ValueError):puncture_cover(13,3,4,exact(13,4),0)
    with pytest.raises(ValueError):neutral_item_walk(13,4,exact(13,4),0,max_moves=-1)
