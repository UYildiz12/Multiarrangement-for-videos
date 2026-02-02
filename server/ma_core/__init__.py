"""
Multiarrangement Core Algorithms.

Server-side implementations of the core algorithms for batch generation,
RDM estimation, and adaptive subset selection.
"""

from .batch_generator import BatchGenerator, generate_batches
from .lift_weakest import (
    TrialArrangement,
    compute_evidence_matrix,
    estimate_rdm_weighted_average,
    refine_rdm_inverse_mds,
    select_next_subset_lift_weakest,
    get_min_evidence,
    check_stopping_criterion,
)
from .setcover_fusion import fuse_setcover

__all__ = [
    "BatchGenerator",
    "generate_batches",
    "TrialArrangement",
    "compute_evidence_matrix",
    "estimate_rdm_weighted_average",
    "refine_rdm_inverse_mds",
    "select_next_subset_lift_weakest",
    "get_min_evidence",
    "check_stopping_criterion",
    "fuse_setcover",
]
