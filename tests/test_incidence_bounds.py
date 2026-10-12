from collections import Counter
from itertools import combinations
from pathlib import Path
import json
import math

import numpy as np
import pytest

from coverlib.certificates import certify_schedule
from coverlib.incidence_bounds import six_trial_optimal_profile


WITNESSES = json.loads((Path(__file__).parent/'fixtures/six_trial_witnesses.json').read_text())


@pytest.mark.parametrize('row', WITNESSES, ids=lambda row: f"v{row['v']}_k{row['k']}")
def test_incidence_optimum_against_exhaustive_equality_check_and_witness(row):
    v, k, blocks = row['v'], row['k'], row['blocks']
    # Enumerate all equality cases of the independent ten-support lower bound.
    supports = [(0,) + p for p in combinations(range(1, 6), 2)]
    signs = np.array([[1 if i in s else -1 for i in range(6)] for s in supports])
    orientations = np.array([[1 if mask & (1 << i) else -1 for i in range(10)]
                             for mask in range(1024)])
    q, r = divmod(v, 10)
    equality_possible = False
    for high in combinations(range(10), r):
        weights = np.full(10, q)
        weights[list(high)] += 1
        if np.any(np.all(orientations @ (weights[:, None] * signs) == 0, axis=1)):
            equality_possible = True
            break
    lower_bound = 10 * math.comb(q, 2) + r * q + int(not equality_possible)
    actual = Counter(p for b in blocks for p in combinations(sorted(b), 2))
    assert len(actual) == math.comb(v, 2)
    assert sum(count == 3 for count in actual.values()) == lower_bound
    assert tuple(sorted(actual.values(), reverse=True)) == six_trial_optimal_profile(v, k, 6)
    cert = certify_schedule(v, k, blocks)
    assert 'SIX_TRIAL_INCIDENCE_OPTIMUM' in cert.statuses
    assert 'LEXICOGRAPHIC_OPTIMUM_CERTIFIED' in cert.statuses
    assert 'BEST_FOUND_WITH_GAP' not in cert.statuses


def test_structural_certificate_rejects_a_complete_but_less_balanced_cover():
    base = next(row['blocks'] for row in WITNESSES if row['k'] == 4)
    # Duplicate each item's incidence pattern, giving 16 items, eight per trial.
    blocks = [[2*x+j for x in b for j in (0,1)] for b in base]
    cert = certify_schedule(16, 8, blocks)
    assert cert.complete and cert.b == 6
    assert 'MINIMUM_TRIALS_CERTIFIED' in cert.statuses
    assert 'SIX_TRIAL_INCIDENCE_OPTIMUM' not in cert.statuses
    assert 'LEXICOGRAPHIC_OPTIMUM_CERTIFIED' not in cert.statuses


@pytest.mark.parametrize('parameters', [(16,8,7), (15,8,6), (22,11,6), (4,2,6)])
def test_finite_bound_is_not_extrapolated(parameters):
    assert six_trial_optimal_profile(*parameters) is None
