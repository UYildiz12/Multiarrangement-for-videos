import math
from itertools import combinations

from coverlib.balanced import normalized_balance_metrics
from ma_core.batch_generator import generate_batches


def _create_study_with_stimuli(client, *, name: str, paradigm: str, n: int, config: dict):
    study_resp = client.post(
        "/api/v1/studies",
        json={
            "name": name,
            "paradigm": paradigm,
            "language": "en",
            "config": config,
        },
    )
    assert study_resp.status_code == 201
    study_id = study_resp.json()["id"]

    stimuli_resp = client.post(
        f"/api/v1/studies/{study_id}/stimuli",
        json={
            "stimuli": [
                {
                    "ordinal": idx,
                    "filename": f"{name}_{idx}.mp4",
                    "media_type": "video",
                    "media_url": f"https://example.com/{name}_{idx}.mp4",
                    "duration_seconds": 3.0 + (idx % 5),
                }
                for idx in range(n)
            ]
        },
    )
    assert stimuli_resp.status_code == 200
    return study_id


def _circle_positions(indices: list[int]) -> dict[str, dict[str, float]]:
    n = max(1, len(indices))
    return {
        str(idx): {
            "x": 360.0 + 240.0 * math.cos((2.0 * math.pi * offset) / n),
            "y": 360.0 + 240.0 * math.sin((2.0 * math.pi * offset) / n),
        }
        for offset, idx in enumerate(indices)
    }


def _assert_rdm_is_valid(rdm: list[list[float]], n: int) -> None:
    assert len(rdm) == n
    for i, row in enumerate(rdm):
        assert len(row) == n
        assert row[i] == 0
        for j, value in enumerate(row):
            assert math.isfinite(value)
            assert value >= 0
            assert value == rdm[j][i]


def _max_off_diagonal(rdm: list[list[float]]) -> float:
    return max(
        value
        for i, row in enumerate(rdm)
        for j, value in enumerate(row)
        if i != j
    )


def _pair_coverage_stats(batches: list[list[int]]) -> tuple[set[tuple[int, int]], dict[tuple[int, int], int]]:
    counts: dict[tuple[int, int], int] = {}
    for batch in batches:
        for pair in combinations(batch, 2):
            key = tuple(sorted(pair))
            counts[key] = counts.get(key, 0) + 1
    return set(counts), counts


def test_setcover_generates_complete_coverage_across_supported_batch_sizes():
    for batch_size in range(3, 13):
        n_items = batch_size + 5
        batches = generate_batches(n_items, batch_size, seed=123, algorithm="greedy")
        assert batches
        assert all(2 <= len(batch) <= batch_size for batch in batches)
        assert all(0 <= idx < n_items for batch in batches for idx in batch)

        covered = {
            tuple(sorted(pair))
            for batch in batches
            for pair in combinations(batch, 2)
        }
        expected = set(combinations(range(n_items), 2))
        assert covered == expected


def test_balanced_setcover_reduces_pathological_pair_repetition():
    n_items = 40
    batch_size = 6
    minimal_batches = generate_batches(n_items, batch_size, seed=123, algorithm="hybrid")
    balanced_batches = generate_batches(n_items, batch_size, seed=123, algorithm="balanced")

    expected_pairs = set(combinations(range(n_items), 2))
    minimal_covered, minimal_counts = _pair_coverage_stats(minimal_batches)
    balanced_covered, balanced_counts = _pair_coverage_stats(balanced_batches)

    assert minimal_covered == expected_pairs
    assert balanced_covered == expected_pairs
    assert len(balanced_batches) == len(minimal_batches)
    assert max(minimal_counts.values()) >= 8
    assert max(balanced_counts.values()) <= 6


def test_balanced_setcover_common_sizes_have_normalized_diagnostics():
    cases = [
        (16, 6, 10, 2.0, 0.18),
        (24, 6, 22, 2.5, 0.10),
        (40, 6, 55, 3.0, 0.04),
        (58, 6, 117, 1.5, 0.03),
        (15, 8, 6, 1.5, 0.07),
        (58, 8, 66, 1.0, 0.0),
    ]

    for n_items, batch_size, max_trials, max_ratio, max_sumsq_excess in cases:
        batches = generate_batches(n_items, batch_size, seed=123, algorithm="balanced")
        metrics = normalized_balance_metrics(n_items, batch_size, batches)

        assert metrics.complete is True
        assert len(batches) <= max_trials
        assert metrics.lambda_max_ratio <= max_ratio
        assert metrics.normalized_pair_sumsq_excess <= max_sumsq_excess


def test_balanced_setcover_is_reproducible_for_same_seed():
    first = generate_batches(40, 6, seed=123, algorithm="balanced")
    second = generate_batches(40, 6, seed=123, algorithm="balanced")

    assert second == first


def test_setcover_session_caps_batch_size_to_available_stimuli(client):
    study_id = _create_study_with_stimuli(
        client,
        name="small_setcover",
        paradigm="setcover",
        n=4,
        config={"batch_size": 12},
    )

    session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={"participant_id": "p1"})
    assert session_resp.status_code == 201
    next_resp = client.get(f"/api/v1/sessions/{session_resp.json()['session_id']}/next")
    assert next_resp.status_code == 200
    assert len(next_resp.json()["subset_indices"]) == 4


def test_duplicate_arrangement_submit_is_idempotent(client):
    study_id = _create_study_with_stimuli(
        client,
        name="duplicate_submit",
        paradigm="setcover",
        n=6,
        config={"batch_size": 4},
    )
    session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={"participant_id": "p1"})
    assert session_resp.status_code == 201
    session_id = session_resp.json()["session_id"]
    first_trial = client.get(f"/api/v1/sessions/{session_id}/next").json()
    payload = {
        "trial_index": first_trial["trial_index"],
        "subset_indices": first_trial["subset_indices"],
        "positions": _circle_positions(first_trial["subset_indices"]),
        "duration_seconds": 45.0,
        "arena_size": 600,
    }

    first_submit = client.post(f"/api/v1/sessions/{session_id}/trials", json=payload)
    assert first_submit.status_code == 200
    assert first_submit.json()["arena_size"] == 600
    duplicate_submit = client.post(f"/api/v1/sessions/{session_id}/trials", json=payload)

    assert duplicate_submit.status_code == 200
    assert duplicate_submit.json()["trial_index"] == first_submit.json()["trial_index"]
    assert duplicate_submit.json()["id"] == first_submit.json()["id"]
    assert duplicate_submit.json()["next_trial"] == first_submit.json()["next_trial"]
    assert duplicate_submit.json()["arena_size"] == 600

    trials_resp = client.get(f"/api/v1/admin/sessions/{session_id}/trials")
    assert trials_resp.status_code == 200
    assert trials_resp.json()[0]["arena_size"] == 600


def test_arrangement_results_return_scaled_rdm_with_raw_audit_matrix(client):
    n_stimuli = 8
    study_id = _create_study_with_stimuli(
        client,
        name="scaled_rdm",
        paradigm="adaptive",
        n=n_stimuli,
        config={
            "min_subset_size": 4,
            "max_subset_size": 6,
            "evidence_threshold": 999,
            "use_inverse_mds": False,
        },
    )
    session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={"participant_id": "p1"})
    assert session_resp.status_code == 201
    session_id = session_resp.json()["session_id"]
    first_trial = client.get(f"/api/v1/sessions/{session_id}/next").json()

    submit_resp = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": first_trial["trial_index"],
            "subset_indices": first_trial["subset_indices"],
            "positions": _circle_positions(first_trial["subset_indices"]),
            "duration_seconds": 90.0,
        },
    )
    assert submit_resp.status_code == 200

    results_resp = client.get(f"/api/v1/sessions/{session_id}/results")
    assert results_resp.status_code == 200
    results = results_resp.json()
    _assert_rdm_is_valid(results["rdm"], n_stimuli)
    _assert_rdm_is_valid(results["rdm_raw"], n_stimuli)
    assert results["rdm_scale"]["method"] == "max_offdiag_0_1"
    assert results["rdm_scale"]["divisor"] > 0
    assert _max_off_diagonal(results["rdm"]) == 1
    assert _max_off_diagonal(results["rdm_raw"]) == results["rdm_scale"]["divisor"]


def test_adaptive_first_trial_and_rdm_are_valid_for_large_video_sets(client):
    n_stimuli = 58
    study_id = _create_study_with_stimuli(
        client,
        name="adaptive_large",
        paradigm="adaptive",
        n=n_stimuli,
        config={
            "min_subset_size": 4,
            "max_subset_size": 8,
            "evidence_threshold": 999,
            "use_inverse_mds": False,
        },
    )
    session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={"participant_id": "p1"})
    assert session_resp.status_code == 201
    session_id = session_resp.json()["session_id"]

    first_trial = client.get(f"/api/v1/sessions/{session_id}/next").json()
    assert first_trial["trial_index"] == 0
    assert first_trial["subset_indices"] == list(range(n_stimuli))
    assert first_trial["is_final"] is False

    submit_resp = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": 0,
            "subset_indices": first_trial["subset_indices"],
            "positions": _circle_positions(first_trial["subset_indices"]),
            "duration_seconds": 120.0,
        },
    )
    assert submit_resp.status_code == 200
    next_trial = submit_resp.json()["next_trial"]
    assert next_trial["trial_index"] == 1
    assert 4 <= len(next_trial["subset_indices"]) <= 8

    results_resp = client.get(f"/api/v1/sessions/{session_id}/results")
    assert results_resp.status_code == 200
    results = results_resp.json()
    assert results["n_trials"] == 1
    _assert_rdm_is_valid(results["rdm"], n_stimuli)
