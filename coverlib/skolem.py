"""Direct half-idempotent Skolem triple construction, without backtracking.

Th. Skolem (1958), Some Remarks on the Triple Systems of Steiner,
Mathematica Scandinavica 6,273-280, doi:10.7146/math.scand.a-10551.
"""
import time

from .constructions import ConstructedCover
from .bose_repair import BoseRepairDeadline, BoseRepairResource


def direct_skolem_cover(v, k, *, deadline, max_pair_entries, max_output_cells):
    """Return an exact STS(v) for k=3,v>=7,v=1mod6, else None.

    Resource and high-resolution deadline checks bound assembly. The general
    scheduler independently validates the resulting whole witness.
    """
    if k != 3 or v < 7 or v % 6 != 1:
        return None
    total = v * (v - 1) // 6
    if v * (v - 1) // 2 > max_pair_entries or 3 * total > max_output_cells:
        raise BoseRepairResource("Skolem output or pair storage exceeds resource limits")

    def check():
        if time.perf_counter() >= deadline:
            raise BoseRepairDeadline("deadline reached during direct Skolem construction")

    check()
    t = (v - 1) // 6
    m = 2 * t
    infinity = 6 * t
    rows = []

    def point(x, level):
        return level * m + x

    def add(row):
        if len(rows) % 128 == 0:
            check()
        rows.append(tuple(sorted(row)))

    for x in range(t):
        add((point(x, 0), point(x, 1), point(x, 2)))
    for x in range(m):
        for y in range(x + 1, m):
            s = (x + y) % m
            q = s // 2 if s % 2 == 0 else (s + m - 1) // 2
            for level in range(3):
                add((point(x, level), point(y, level), point(q, (level + 1) % 3)))
    for x in range(t):
        for level in range(3):
            add((infinity, point(x + t, level), point(x, (level + 1) % 3)))
    rows.sort()
    check()
    return ConstructedCover("skolem_direct", tuple(rows))
