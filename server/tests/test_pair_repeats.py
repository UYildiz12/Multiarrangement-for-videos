"""
Balanced schedules with repeats: every pair at least r times, validation, and the error for settings that cannot
hold r copies.
"""

from itertools import combinations

import pytest
from fastapi import HTTPException

from app.routers import sessions as sessions_router


def _study(client, repeats, batch_size=3, schedule_mode="balanced"):
    body = {"name": "Repeats", "paradigm": "setcover", "language": "en",
            "config": {"batch_size": batch_size, "schedule_mode": schedule_mode, "pair_repeats": repeats}}
    return client.post("/api/v1/studies", json=body)


def _pair_counts(n, batches):
    counts = {p: 0 for p in combinations(range(n), 2)}
    for batch in batches:
        for p in combinations(sorted(batch), 2):
            counts[p] += 1
    return counts


@pytest.mark.parametrize("bad", [0, 5, 2.5, "2", True])
def test_pair_repeats_must_be_a_whole_number_from_1_to_4(client, bad):
    assert _study(client, bad).status_code == 422


def test_repeat_schedule_shows_every_pair_at_least_r_times():
    batches = sessions_router._get_or_create_repeat_schedule("study-a", 9, 3, 2)
    counts = _pair_counts(9, batches)
    assert min(counts.values()) >= 2
    assert len({tuple(sorted(b)) for b in batches}) == len(batches)  # no trial repeated


def test_repeats_that_cannot_be_built_give_a_clear_error():
    with pytest.raises(HTTPException) as err:
        # each pair of 5 stimuli lies in only C(3,2) = 3 distinct trials of 4, so 4 repeats are impossible
        sessions_router._get_or_create_repeat_schedule("study-b", 5, 4, 4)
    assert err.value.status_code == 422
    assert "repeats per pair are not available" in err.value.detail


def test_a_session_of_a_repeat_study_uses_the_repeat_schedule(client):
    study = _study(client, 2).json()
    stimuli = [{"ordinal": i, "filename": f"clip{i}", "media_type": "video", "media_url": f"/videos/clip{i}.mp4"}
               for i in range(9)]
    assert client.post(f"/api/v1/studies/{study['id']}/stimuli", json={"stimuli": stimuli}).status_code == 200
    resp = client.post(f"/api/v1/studies/{study['id']}/sessions", json={"participant_id": "p1"})
    assert resp.status_code in (200, 201), resp.text
    session = sessions_router.get_session_record(resp.json()["session_id"])
    counts = _pair_counts(9, session["batches"])
    assert min(counts.values()) >= 2


def test_a_compact_study_with_repeats_also_uses_the_repeat_schedule(client):
    study = _study(client, 3, schedule_mode="compact").json()
    stimuli = [{"ordinal": i, "filename": f"clip{i}", "media_type": "video", "media_url": f"/videos/clip{i}.mp4"}
               for i in range(9)]
    assert client.post(f"/api/v1/studies/{study['id']}/stimuli", json={"stimuli": stimuli}).status_code == 200
    resp = client.post(f"/api/v1/studies/{study['id']}/sessions", json={"participant_id": "p1"})
    assert resp.status_code in (200, 201), resp.text
    session = sessions_router.get_session_record(resp.json()["session_id"])
    assert min(_pair_counts(9, session["batches"]).values()) >= 3


@pytest.mark.parametrize("mode", ["compact", "balanced"])
def test_both_modes_show_every_pair_at_least_r_times(mode):
    batches = sessions_router._get_or_create_repeat_schedule(f"study-{mode}", 13, 4, 2, mode=mode)
    assert min(_pair_counts(13, batches).values()) >= 2
    assert len({tuple(sorted(b)) for b in batches}) == len(batches)


def test_repeat_cache_entries_per_mode_are_read_and_checked(tmp_path, monkeypatch):
    import json

    import multiarrangement as ma
    from multiarrangement.core import budget

    pkg = tmp_path / "pkg"
    (pkg / "repeat_cache").mkdir(parents=True)
    compact = [list(t) for t in combinations(range(6), 3)]  # every triple: each pair 4 times
    (pkg / "repeat_cache" / "c.txt").write_text("\n".join(" ".join(map(str, b)) for b in compact))
    (pkg / "repeat_cache" / "bad.txt").write_text("0 1 2\n0 1 2")  # repeated trial: refused on load
    (pkg / "repeat_cache" / "index.json").write_text(json.dumps(
        {"6,3,2": {"compact": {"path": "c.txt"}, "balanced": {"path": "bad.txt"}}}))
    monkeypatch.setattr(ma, "__file__", str(pkg / "__init__.py"))
    got = budget.load_repeat_design(6, 3, 2, "compact")
    assert got is not None and min(_pair_counts(6, got).values()) >= 2
    assert budget.load_repeat_design(6, 3, 2, "balanced") is None
    with pytest.raises(ValueError):
        budget.repeat_schedule(6, 3, 2, mode="fastest")
