"""
Adaptive multiarrangement components, including the Lift-the-Weakest algorithm.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .lift_weakest import (
    estimate_rdm_weighted_average,
    select_next_subset_lift_weakest,
    refine_rdm_inverse_mds,
)

if TYPE_CHECKING:
    from .adaptive_experiment import AdaptiveConfig, AdaptiveMultiarrangementExperiment


def __getattr__(name: str) -> Any:
    if name in {"AdaptiveMultiarrangementExperiment", "AdaptiveConfig"}:
        module = import_module("multiarrangement.adaptive.adaptive_experiment")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "estimate_rdm_weighted_average",
    "select_next_subset_lift_weakest",
    "refine_rdm_inverse_mds",
    "AdaptiveMultiarrangementExperiment",
    "AdaptiveConfig",
]
