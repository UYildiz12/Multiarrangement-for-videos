from __future__ import annotations

import itertools

from coverlib.certificates import certify_schedule
from coverlib.ordering import (
    counterbalanced_schedule_family,
    optimize_trial_order,
    trial_order_cost,
)


SCHEDULE = (
    (0, 2, 5),
    (1, 3, 4),
    (0, 1, 3),
    (1, 2, 3),
    (2, 4, 5),
    (1, 3, 5),
    (0, 3, 4),
)


def _aggregate_profile(v, schedules):
    counts = {(a, b): 0 for a in range(v) for b in range(a + 1, v)}
    for schedule in schedules:
        for block in schedule:
            for pair in itertools.combinations(block, 2):
                counts[tuple(sorted(pair))] += 1
    return tuple(sorted(counts.values(), reverse=True))


def test_counterbalanced_family_preserves_each_certificate_and_flattens_group():
    family = counterbalanced_schedule_family(6, SCHEDULE, family_size=6, seed=9)
    original = certify_schedule(6, 3, SCHEDULE)

    assert len(family) == 6
    for schedule in family:
        certificate = certify_schedule(6, 3, schedule)
        assert certificate.b == original.b
        assert certificate.concurrence_profile == original.concurrence_profile
        assert certificate.complete
    assert _aggregate_profile(6, family) < _aggregate_profile(6, [SCHEDULE] * 6)


def test_trial_order_improves_anytime_cost_without_changing_schedule():
    durations = [1.0, 3.0, 2.0, 8.0, 5.0, 4.0]
    ordered = optimize_trial_order(6, SCHEDULE, durations=durations, seed=7)

    assert trial_order_cost(6, ordered, durations=durations) <= trial_order_cost(
        6,
        SCHEDULE,
        durations=durations,
    )
    assert sorted(map(tuple, ordered)) == sorted(SCHEDULE)


def test_counterbalance_family_can_repeat_pool_for_small_item_sets():
    schedule = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))

    family = counterbalanced_schedule_family(
        4,
        schedule,
        family_size=32,
        seed=4,
    )

    assert len(family) == 32
    assert all(sorted(map(tuple, member)) == sorted(schedule) for member in family)
