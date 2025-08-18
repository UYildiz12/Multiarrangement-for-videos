import numpy as np
from multiarrangement.adaptive.lift_weakest import (
    TrialArrangement,
    estimate_rdm_weighted_average,
    refine_rdm_inverse_mds,
    select_next_subset_lift_weakest,
)


def _simulate_positions_from_rdm(D_sub: np.ndarray, noise=0.01, seed=0):
    rng = np.random.default_rng(seed)
    # Simple classical MDS to 2D
    from multiarrangement.adaptive.lift_weakest import _classical_mds_2d

    X = _classical_mds_2d(D_sub)
    # Scale to RMS ~ 1 for distances
    m = D_sub.shape[0]
    Ds = np.zeros_like(D_sub)
    for i in range(m):
        for j in range(i+1, m):
            Ds[i, j] = Ds[j, i] = np.linalg.norm(X[i]-X[j])
    iu = np.triu_indices(m, 1)
    rms = float(np.sqrt(np.mean(Ds[iu]**2))) if iu[0].size else 1.0
    if rms > 0:
        X = X / rms
    # Add small isotropic noise
    X = X + noise * rng.standard_normal(size=X.shape)
    return X


def test_weighted_average_and_inverse_mds_small():
    n = 6
    # Ground truth distances from random 3D points
    rng = np.random.default_rng(42)
    Xtrue = rng.standard_normal((n, 3))
    Dtrue = np.zeros((n, n))
    for i in range(n):
        for j in range(i+1, n):
            Dtrue[i, j] = Dtrue[j, i] = np.linalg.norm(Xtrue[i]-Xtrue[j])
    # Normalize
    iu = np.triu_indices(n, 1)
    Dtrue = Dtrue / float(np.sqrt(np.mean(Dtrue[iu]**2)))

    # Simulate trials: full + 2 subsets
    trials = []
    # Trial 1: full
    Xfull = _simulate_positions_from_rdm(Dtrue, noise=0.02, seed=1)
    pos_full = {i: (float(Xfull[i,0]), float(Xfull[i,1])) for i in range(n)}
    trials.append(TrialArrangement(subset=list(range(n)), positions=pos_full))
    # Trial 2: subset of 4
    subset2 = [0, 1, 2, 3]
    D2 = Dtrue[np.ix_(subset2, subset2)]
    X2 = _simulate_positions_from_rdm(D2, noise=0.02, seed=2)
    pos2 = {subset2[i]: (float(X2[i,0]), float(X2[i,1])) for i in range(len(subset2))}
    trials.append(TrialArrangement(subset=subset2, positions=pos2))
    # Trial 3: subset of 4
    subset3 = [2, 3, 4, 5]
    D3 = Dtrue[np.ix_(subset3, subset3)]
    X3 = _simulate_positions_from_rdm(D3, noise=0.02, seed=3)
    pos3 = {subset3[i]: (float(X3[i,0]), float(X3[i,1])) for i in range(len(subset3))}
    trials.append(TrialArrangement(subset=subset3, positions=pos3))

    Dest, W = estimate_rdm_weighted_average(n, trials)
    # Correlate upper triangles
    iu = np.triu_indices(n, 1)
    r_before = np.corrcoef(Dtrue[iu], Dest[iu])[0,1]
    # Inverse MDS refinement should not degrade correlation notably
    Dref = refine_rdm_inverse_mds(Dest, trials, max_iter=10, step_c=0.3, tol=1e-4)
    r_after = np.corrcoef(Dtrue[iu], Dref[iu])[0,1]
    assert r_after >= r_before - 0.05


def test_lift_the_weakest_basic():
    # Small synthetic D and W
    n = 5
    D = np.ones((n, n)) - np.eye(n)
    W = np.zeros((n, n))
    # Make pair (0,1) the weakest (tie with others), should pick it as start
    subset = select_next_subset_lift_weakest(D, W, min_size=3)
    assert len(subset) >= 3
    assert 0 in subset and 1 in subset

