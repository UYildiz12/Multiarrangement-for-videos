"""Bounded, table-free triple covers from the polynomial Bose construction."""
from itertools import combinations
import time

from .combinatorics import pair_index
from .constructions import ConstructedCover, steiner_triple_system


class BoseRepairDeadline(TimeoutError):
    pass


class BoseRepairResource(ValueError):
    pass


def bose_repaired_candidates(v, *, deadline, max_pair_entries, max_output_cells):
    """Return complete triple candidates without Heffter search or table reads.

    Truncate the smallest Bose order w>=v, w=3 mod6. Retained triples
    cover all surviving pairs except the retained two-point fragments. Padding
    each uncovered fragment completes coverage; rows are deduplicated. For two
    deleted points, their fragment graph is a union of even cycles. When none
    is a four-cycle, consecutive two-edge paths give a shorter cap-two cover.
    The generic padded cover remains available for all deletion counts.
    """
    def check():
        if time.perf_counter() >= deadline:
            raise BoseRepairDeadline("deadline reached during Bose truncation/repair")

    if isinstance(v, bool) or not isinstance(v, int) or v < 3:
        raise ValueError("Bose truncation requires integer v>=3")
    w = v + (3 - v) % 6
    total = w * (w - 1) // 6
    # Bound both original and retained output cells, plus dense pair recounts.
    if v * (v - 1) // 2 > max_pair_entries or 6 * total > max_output_cells:
        raise BoseRepairResource("Bose base/output or pair storage exceeds resource limits")
    check()
    base = [(0, 1, 2)] if w == 3 else steiner_triple_system(w)
    check()
    retained, fragments = [], []
    for index, row in enumerate(base):
        if index % 128 == 0:
            check()
        surviving = tuple(i for i in row if i < v)
        if len(surviving) == 3:
            retained.append(surviving)
        elif len(surviving) == 2:
            fragments.append(surviving)
    del base
    if w == v:
        return [ConstructedCover("bose_exact", tuple(retained))]

    answers = []
    if w - v == 2:
        neighbors = [[] for _ in range(v)]
        for a, b in fragments:
            neighbors[a].append(b)
            neighbors[b].append(a)
        # Independent structural check before applying the two-hole theorem.
        if all(len(adjacent) in (0, 2) for adjacent in neighbors):
            seen, cycles = set(), []
            for start in range(v):
                check()
                if start in seen or not neighbors[start]:
                    continue
                cycle, previous, current = [], None, start
                while current not in seen:
                    if len(cycle) % 128 == 0:
                        check()
                    seen.add(current)
                    cycle.append(current)
                    choices = sorted(neighbors[current])
                    following = choices[0] if choices[0] != previous else choices[1]
                    previous, current = current, following
                if current != start or len(cycle) % 2 or len(cycle) < 4:
                    cycles = []
                    break
                cycles.append(cycle)
            if cycles and all(len(cycle) >= 6 for cycle in cycles):
                repaired = list(retained)
                for cycle in cycles:
                    check()
                    for i in range(0, len(cycle), 2):
                        repaired.append(tuple(sorted((cycle[i], cycle[i + 1], cycle[(i + 2) % len(cycle)]))))
                answers.append(ConstructedCover("bose_two_hole_paths", tuple(sorted(set(repaired)))))
                # This repairs two missing pairs per added triple and attains
                # cap two with ideal items. It dominates generic padding while
                # retaining these Bose triples; no extra padding work is needed.
                check()
                return answers

    counts = [0] * (v * (v - 1) // 2)
    replications = [0] * v
    padded = set(retained)

    def add(row):
        for a, b in combinations(row, 2):
            counts[pair_index(a, b, v)] += 1
        for item in row:
            replications[item] += 1

    for index, row in enumerate(retained):
        if index % 128 == 0:
            check()
        add(row)
    for a, b in sorted(fragments):
        check()
        if counts[pair_index(a, b, v)]:
            continue
        # Minimize the two changed concurrence levels, then third-item exposure.
        best, best_key = None, None
        for c in range(v):
            if c % 128 == 0:
                check()
            if c in (a, b):
                continue
            first, second = counts[pair_index(a, c, v)], counts[pair_index(b, c, v)]
            score = (max(first, second), first + second, replications[c], c)
            if best_key is None or score < best_key:
                best, best_key = c, score
        row = tuple(sorted((a, b, best)))
        if row not in padded:
            padded.add(row)
            add(row)
    check()
    answers.append(ConstructedCover("bose_truncated_padded", tuple(sorted(padded))))
    return answers
