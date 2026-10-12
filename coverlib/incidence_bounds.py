"""Finite incidence bounds that strengthen unconstrained histogram targets.

The six-trial table follows the complement-pair argument and exhaustive equality
check documented in docs/compact-balanced-design.md. It applies only to the
stated parameters; it is not extrapolated to other trial counts or sizes.
"""
from typing import Optional, Tuple


def six_trial_optimal_profile(v: int, k: int, b: int) -> Optional[Tuple[int, ...]]:
    """Best pair-concurrence profile for complete (2k,k) covers with six trials.

    Coverage and incidence counting force every item to occur three times.
    At most ten distinct three-trial supports can coexist, because complementary
    supports are disjoint. The balanced-pigeonhole bound is tight except for
    k=4,6,9 in this finite range; exhaustive enumeration rules out equality
    in those cases, and explicit six-trial witnesses attain the next integer.
    """
    if b != 6 or v != 2 * k or not 3 <= k <= 10:
        return None
    triplicates = {3: 0, 4: 1, 5: 0, 6: 3, 7: 4, 8: 6, 9: 9, 10: 10}[k]
    pair_count = v * (v - 1) // 2
    pair_slots = b * k * (k - 1) // 2
    duplicates = pair_slots - pair_count - 2 * triplicates
    singles = pair_count - duplicates - triplicates
    return (3,) * triplicates + (2,) * duplicates + (1,) * singles
