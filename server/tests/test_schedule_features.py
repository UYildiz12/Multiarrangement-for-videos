"""Tests for schedule diagnostics and the per-study schedule cache."""

from app.routers.results import schedule_diagnostics
from app.routers import sessions as sessions_module


class TestScheduleDiagnostics:
    def test_perfect_round_robin_schedule(self):
        # All pairs of 4 items exactly once: lambda_max 1, complete.
        batches = [[0, 1], [2, 3], [0, 2], [1, 3], [0, 3], [1, 2]]
        diag = schedule_diagnostics(4, batches)
        assert diag is not None
        assert diag["complete_pair_coverage"] is True
        assert diag["lambda_max"] == 1
        assert diag["ideal_lambda_max"] == 1
        assert diag["pair_coverage_histogram"] == {"1": 6}
        assert diag["item_use_min"] == 3
        assert diag["item_use_max"] == 3
        assert diag["n_trials"] == 6
        assert diag["batch_sizes"] == [2]

    def test_unbalanced_schedule_reports_hot_pair(self):
        batches = [[0, 1, 2], [0, 1, 3], [0, 1, 2], [2, 3, 0]]
        diag = schedule_diagnostics(4, batches)
        assert diag["lambda_max"] == 3  # pair (0,1) appears three times
        assert diag["complete_pair_coverage"] is False or diag["lambda_max_ratio"] >= 1.0

    def test_empty_or_missing_schedule(self):
        assert schedule_diagnostics(4, None) is None
        assert schedule_diagnostics(4, []) is None


class TestScheduleCache:
    def test_schedule_generated_once_per_study(self, monkeypatch):
        calls = {"n": 0}

        def fake_generate(n_items, batch_size, seed=None, flex=False, algorithm="balanced"):
            calls["n"] += 1
            return [[0, 1, 2], [1, 2, 3]]

        monkeypatch.setattr(sessions_module, "generate_batches", fake_generate)
        sessions_module._SCHEDULE_CACHE.clear()

        first = sessions_module._get_or_create_schedule(
            "study-x", 4, 3, flex=False, algorithm="balanced"
        )
        second = sessions_module._get_or_create_schedule(
            "study-x", 4, 3, flex=False, algorithm="balanced"
        )
        assert calls["n"] == 1
        assert first == second
        # Returned schedules are defensive copies, not shared references.
        first[0][0] = 99
        third = sessions_module._get_or_create_schedule(
            "study-x", 4, 3, flex=False, algorithm="balanced"
        )
        assert third[0][0] == 0

    def test_different_config_misses_cache(self, monkeypatch):
        calls = {"n": 0}

        def fake_generate(n_items, batch_size, seed=None, flex=False, algorithm="balanced"):
            calls["n"] += 1
            return [[0, 1], [1, 2], [0, 2]]

        monkeypatch.setattr(sessions_module, "generate_batches", fake_generate)
        sessions_module._SCHEDULE_CACHE.clear()

        sessions_module._get_or_create_schedule("study-y", 3, 2, flex=False, algorithm="balanced")
        sessions_module._get_or_create_schedule("study-y", 3, 2, flex=False, algorithm="optimal")
        assert calls["n"] == 2


class TestAdaptiveInverseMdsDefault:
    def test_hosted_adaptive_does_not_refine_by_default(self, client, monkeypatch):
        """Hosted default must match the desktop library and the published
        recommendation: inverse-MDS refinement is opt-in."""
        calls = {"n": 0}

        def spy(D_init, trials, **kwargs):
            calls["n"] += 1
            return D_init

        monkeypatch.setattr(sessions_module, "refine_rdm_inverse_mds", spy)

        study = client.post(
            "/api/v1/studies",
            json={
                "name": "Adaptive Default",
                "paradigm": "adaptive",
                "config": {"min_subset_size": 2, "max_subset_size": 3},
            },
        ).json()
        client.post(
            f"/api/v1/studies/{study['id']}/stimuli",
            json={
                "stimuli": [
                    {
                        "ordinal": i,
                        "filename": f"clip_{i}.mp4",
                        "media_type": "video",
                        "media_url": f"https://example.com/{i}.mp4",
                    }
                    for i in range(4)
                ]
            },
        )
        session_id = client.post(
            f"/api/v1/studies/{study['id']}/sessions", json={"participant_id": "P1"}
        ).json()["session_id"]
        subset = client.get(f"/api/v1/sessions/{session_id}/next").json()["subset_indices"]
        response = client.post(
            f"/api/v1/sessions/{session_id}/trials",
            json={
                "trial_index": 0,
                "subset_indices": subset,
                "positions": {
                    str(idx): {"x": 100.0 + 40.0 * n, "y": 150.0 + 20.0 * n}
                    for n, idx in enumerate(subset)
                },
                "duration_seconds": 3.0,
                "arena_size": 600,
            },
        )
        assert response.status_code == 200
        assert calls["n"] == 0
