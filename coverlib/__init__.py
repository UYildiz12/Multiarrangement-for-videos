"""Covering-design utilities with a lightweight lazy public boundary."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "GeneralSolveResult": ("coverlib.general", "GeneralSolveResult"),
    "CoverResult": ("coverlib.api", "CoverResult"),
    "ExcessTarget": ("coverlib.excess", "ExcessTarget"),
    "ScheduleCertificate": ("coverlib.certificates", "ScheduleCertificate"),
    "analyze_excess_target": ("coverlib.excess", "analyze_excess_target"),
    "balanced_sort_key": ("coverlib.certificates", "balanced_sort_key"),
    "certify_schedule": ("coverlib.certificates", "certify_schedule"),
    "compact_sort_key": ("coverlib.certificates", "compact_sort_key"),
    "counterbalanced_schedule_family": (
        "coverlib.ordering",
        "counterbalanced_schedule_family",
    ),
    "exact_neighborhood_repair": (
        "coverlib.residual",
        "exact_neighborhood_repair",
    ),
    "generate_cover": ("coverlib.api", "generate_cover"),
    "optimize_trial_order": ("coverlib.ordering", "optimize_trial_order"),
    "pareto_frontier": ("coverlib.certificates", "pareto_frontier"),
    "prepare_schedule_for_participant": (
        "coverlib.ordering",
        "prepare_schedule_for_participant",
    ),
    "select_frontier_cover": ("coverlib.frontier", "select_frontier_cover"),
    "solve_residual_exact": ("coverlib.residual", "solve_residual_exact"),
    "solve_schedule": ("coverlib.general", "solve_schedule"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
