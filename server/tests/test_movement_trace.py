"""Tests for movement-trace capture: submit, persist, fetch, export, caps."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_study_with_stimuli(name: str, n: int = 4) -> str:
    study_resp = client.post(
        "/api/v1/studies",
        json={
            "name": name,
            "paradigm": "setcover",
            "language": "en",
            "config": {"batch_size": 3},
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
                }
                for idx in range(n)
            ]
        },
    )
    assert stimuli_resp.status_code == 200
    return study_id


def _start_session(study_id: str, participant: str) -> tuple[str, list[int]]:
    session_resp = client.post(
        f"/api/v1/studies/{study_id}/sessions", json={"participant_id": participant}
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["session_id"]
    next_resp = client.get(f"/api/v1/sessions/{session_id}/next")
    assert next_resp.status_code == 200
    return session_id, next_resp.json()["subset_indices"]


def _positions_for(subset: list[int]) -> dict[str, dict[str, float]]:
    return {
        str(idx): {"x": 120.0 + offset * 60.0, "y": 200.0 + offset * 25.0}
        for offset, idx in enumerate(subset)
    }


def _trace_for(subset: list[int]) -> dict:
    ordinal = subset[0]
    return {
        "version": 1,
        "samples": [
            [0, ordinal, 500.0, 80.0, 0],
            [120, ordinal, 400.0, 150.0, 1],
            [240, ordinal, 300.0, 210.0, 1],
            [360, ordinal, 120.0, 200.0, 2],
        ],
    }


def test_trace_round_trip_submit_fetch_export():
    study_id = _create_study_with_stimuli("TraceRT")
    session_id, subset = _start_session(study_id, "P-trace")
    trace = _trace_for(subset)

    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": 0,
            "subset_indices": subset,
            "positions": _positions_for(subset),
            "duration_seconds": 9.5,
            "arena_size": 600,
            "movement_trace": trace,
        },
    )
    assert submit.status_code == 200

    trials = client.get(f"/api/v1/admin/sessions/{session_id}/trials")
    assert trials.status_code == 200
    rows = trials.json()
    assert len(rows) == 1
    assert rows[0]["movement_trace"] == trace

    export = client.get(f"/api/v1/studies/{study_id}/export?format=json")
    assert export.status_code == 200
    exported_sessions = export.json()["sessions"]
    assert exported_sessions[0]["trials"][0]["movement_trace"] == trace


def test_trace_is_optional_and_defaults_to_none():
    study_id = _create_study_with_stimuli("TraceOpt")
    session_id, subset = _start_session(study_id, "P-no-trace")

    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": 0,
            "subset_indices": subset,
            "positions": _positions_for(subset),
            "duration_seconds": 4.0,
            "arena_size": 600,
        },
    )
    assert submit.status_code == 200
    rows = client.get(f"/api/v1/admin/sessions/{session_id}/trials").json()
    assert rows[0]["movement_trace"] is None


def test_oversized_trace_rejected():
    study_id = _create_study_with_stimuli("TraceCap")
    session_id, subset = _start_session(study_id, "P-cap")
    huge = {
        "version": 1,
        "samples": [[i, subset[0], 1.0, 2.0, 1] for i in range(50_001)],
    }
    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": 0,
            "subset_indices": subset,
            "positions": _positions_for(subset),
            "duration_seconds": 4.0,
            "arena_size": 600,
            "movement_trace": huge,
        },
    )
    assert submit.status_code == 400
    assert "movement_trace" in submit.json()["detail"]


def test_duplicate_submit_ignores_trace_differences():
    study_id = _create_study_with_stimuli("TraceDup")
    session_id, subset = _start_session(study_id, "P-dup")
    positions = _positions_for(subset)

    first = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": 0,
            "subset_indices": subset,
            "positions": positions,
            "duration_seconds": 5.0,
            "arena_size": 600,
            "movement_trace": _trace_for(subset),
        },
    )
    assert first.status_code == 200

    # Idempotent resubmission of the same trial without a trace must succeed.
    duplicate = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": 0,
            "subset_indices": subset,
            "positions": positions,
            "duration_seconds": 5.0,
            "arena_size": 600,
        },
    )
    assert duplicate.status_code == 200
    rows = client.get(f"/api/v1/admin/sessions/{session_id}/trials").json()
    assert len(rows) == 1
    # The original trace is preserved.
    assert rows[0]["movement_trace"] == _trace_for(subset)


def test_legacy_trials_table_gains_trace_column():
    """The startup self-migration must add movement_trace_json to old tables."""
    import sqlalchemy as sa

    from app.storage import _ensure_trials_movement_trace_column

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE trials ("
                "id TEXT PRIMARY KEY, session_id TEXT, trial_index INTEGER, "
                "subset_indices_json TEXT, positions_json TEXT, rating INTEGER, "
                "duration_seconds FLOAT, arena_size FLOAT, "
                "started_at TEXT, completed_at TEXT)"
            )
        )
    _ensure_trials_movement_trace_column(engine)
    columns = {column["name"] for column in sa.inspect(engine).get_columns("trials")}
    assert "movement_trace_json" in columns
