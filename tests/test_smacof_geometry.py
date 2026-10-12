"""Geometric regression tests shared by desktop and hosted numerical cores."""
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest


@pytest.fixture(params=['multiarrangement/adaptive/lift_weakest.py','server/ma_core/lift_weakest.py'])
def core(request):
    path=Path(__file__).resolve().parents[1]/request.param
    name='_geometry_test_'+request.param.replace('/','_').replace('.','_')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def distances(X):
    return np.linalg.norm(X[:,None,:]-X[None,:,:],axis=-1)


@pytest.mark.parametrize('n',[2,3,5,8])
def test_exact_planar_distances_are_fixed_points(core,n):
    points=np.random.default_rng(n).normal(size=(n,2))
    D=distances(points)
    X=core._smacof_mds_2d(D,max_iter=20)
    np.testing.assert_allclose(distances(X),D,rtol=1e-8,atol=1e-8)


@pytest.mark.parametrize('seed',[17,91,103])
def test_metric_stress_does_not_increase_with_iterations(core,seed):
    D=distances(np.random.default_rng(seed).normal(size=(8,5)))
    ix=np.triu_indices(8,1)
    stress=[]
    for iterations in [0,1,2,3,5,10,20,40]:
        X=core._smacof_mds_2d(D,max_iter=iterations,eps=0)
        stress.append(np.sum((distances(X)[ix]-D[ix])**2))
    assert np.all(np.diff(stress)<=1e-9),stress
