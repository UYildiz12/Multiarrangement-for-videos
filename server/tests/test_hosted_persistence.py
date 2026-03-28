"""
Hosted persistence and resume tests.
"""

import importlib

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _create_study(name: str, paradigm: str = "setcover") -> str:
    study_resp = client.post(
        "/api/v1/studies",
        json={
            "name": name,
            "paradigm": paradigm,
            "language": "en",
            "config": {"batch_size": 3, "min_subset_size": 3, "max_subset_size": 4},
        },
    )
    assert study_resp.status_code == 201
    study_id = study_resp.json()["id"]
    stimuli_resp = client.post(
        f"/api/v1/studies/{study_id}/stimuli",
        json={
            "stimuli": [
                {"ordinal": idx, "filename": f"{name}_{idx}.mp4", "media_type": "video", "media_url": f"https://example.com/{name}_{idx}.mp4"}
                for idx in range(4)
            ]
        },
    )
    assert stimuli_resp.status_code == 200
    return study_id


def _reload_client() -> TestClient:
    import app.main as main_module
    import app.routers as routers_module
    import app.routers.admin as admin_module
    import app.routers.chains as chains_module
    import app.routers.invites as invites_module
    import app.routers.results as results_module
    import app.routers.sessions as sessions_module
    import app.routers.studies as studies_module
    import app.state as state_module
    import app.storage as storage_module

    for module in (
        storage_module,
        state_module,
        studies_module,
        sessions_module,
        results_module,
        invites_module,
        admin_module,
        chains_module,
        routers_module,
        main_module,
    ):
        importlib.reload(module)
    return TestClient(main_module.app)


def _positions_for(subset_indices: list[int]) -> dict[str, dict[str, float]]:
    return {
        str(idx): {"x": 100.0 + offset * 75.0, "y": 180.0 + offset * 35.0}
        for offset, idx in enumerate(subset_indices)
    }


def test_regular_invite_reopens_same_session():
    study_id = _create_study("Invite Resume")
    invite_resp = client.post(f"/api/v1/admin/studies/{study_id}/invites", json={"count": 1})
    assert invite_resp.status_code == 201
    token = invite_resp.json()[0]["token"]

    first_start = client.post(f"/api/v1/public/invites/{token}/start")
    assert first_start.status_code == 201
    first_session_id = first_start.json()["session_id"]

    second_start = client.post(f"/api/v1/public/invites/{token}/start")
    assert second_start.status_code == 201
    assert second_start.json()["session_id"] == first_session_id

    complete_resp = client.post(f"/api/v1/sessions/{first_session_id}/complete")
    assert complete_resp.status_code == 200

    third_start = client.post(f"/api/v1/public/invites/{token}/start")
    assert third_start.status_code == 201
    assert third_start.json()["session_id"] == first_session_id


def test_chain_invite_start_resume_and_next():
    study_a = _create_study("Chain A")
    study_b = _create_study("Chain B")

    chain_resp = client.post("/api/v1/chains", json={"name": "My chain"})
    assert chain_resp.status_code == 201
    chain_id = chain_resp.json()["id"]

    add_a = client.post(f"/api/v1/chains/{chain_id}/studies", json={"study_id": study_a, "position": 0})
    add_b = client.post(f"/api/v1/chains/{chain_id}/studies", json={"study_id": study_b, "position": 1})
    assert add_a.status_code == 201
    assert add_b.status_code == 201

    invite_resp = client.post(f"/api/v1/chains/{chain_id}/invites", json={"count": 1})
    assert invite_resp.status_code == 200
    token = invite_resp.json()[0]["token"]

    first_start = client.post(f"/api/v1/public/chain-invites/{token}/start")
    assert first_start.status_code == 200
    first_payload = first_start.json()

    resumed_start = client.post(f"/api/v1/public/chain-invites/{token}/start")
    assert resumed_start.status_code == 200
    resumed_payload = resumed_start.json()
    assert resumed_payload["chain_session_id"] == first_payload["chain_session_id"]
    assert resumed_payload["session_id"] == first_payload["session_id"]
    assert resumed_payload["current_position"] == 0

    complete_first = client.post(f"/api/v1/sessions/{first_payload['session_id']}/complete")
    assert complete_first.status_code == 200

    next_resp = client.post(f"/api/v1/public/chain-invites/{token}/next")
    assert next_resp.status_code == 200
    next_payload = next_resp.json()
    assert next_payload["chain_session_id"] == first_payload["chain_session_id"]
    assert next_payload["session_id"] != first_payload["session_id"]
    assert next_payload["current_position"] == 1

    resumed_after_next = client.post(f"/api/v1/public/chain-invites/{token}/start")
    assert resumed_after_next.status_code == 200
    assert resumed_after_next.json()["session_id"] == next_payload["session_id"]

    status_resp = client.get(f"/api/v1/public/chain-invites/{token}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["current_position"] == 1


def test_regular_invite_resumes_same_session_after_module_reload():
    study_id = _create_study("Invite Reload")
    invite_resp = client.post(f"/api/v1/admin/studies/{study_id}/invites", json={"count": 1})
    token = invite_resp.json()[0]["token"]

    first_start = client.post(f"/api/v1/public/invites/{token}/start")
    assert first_start.status_code == 201
    session_id = first_start.json()["session_id"]

    reloaded_client = _reload_client()
    resumed_start = reloaded_client.post(f"/api/v1/public/invites/{token}/start")
    assert resumed_start.status_code == 201
    assert resumed_start.json()["session_id"] == session_id


def test_setcover_session_continues_after_reload_and_exports_results():
    study_id = _create_study("Setcover Resume", paradigm="setcover")
    session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={"participant_id": "setcover_p1"})
    session_id = session_resp.json()["session_id"]

    next_resp = client.get(f"/api/v1/sessions/{session_id}/next")
    assert next_resp.status_code == 200
    first_trial = next_resp.json()
    assert first_trial["is_final"] is False

    submit_resp = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": first_trial["trial_index"],
            "subset_indices": first_trial["subset_indices"],
            "positions": _positions_for(first_trial["subset_indices"]),
            "duration_seconds": 12.5,
        },
    )
    assert submit_resp.status_code == 200

    reloaded_client = _reload_client()

    session_status = reloaded_client.get(f"/api/v1/sessions/{session_id}")
    assert session_status.status_code == 200
    assert session_status.json()["current_trial_index"] == 1

    next_after_reload = reloaded_client.get(f"/api/v1/sessions/{session_id}/next")
    assert next_after_reload.status_code == 200
    assert next_after_reload.json()["trial_index"] == 1

    results_resp = reloaded_client.get(f"/api/v1/sessions/{session_id}/results")
    assert results_resp.status_code == 200
    results = results_resp.json()
    assert results["n_trials"] == 1
    assert len(results["rdm"]) == 4
    assert len(results["labels"]) == 4

    export_json = reloaded_client.get(f"/api/v1/studies/{study_id}/export?format=json")
    assert export_json.status_code == 200
    export_payload = export_json.json()
    assert export_payload["study"]["id"] == study_id
    assert len(export_payload["sessions"]) == 1
    assert export_payload["sessions"][0]["n_trials"] == 1
    assert export_payload["sessions"][0]["trials"][0]["positions"] is not None

    export_csv = reloaded_client.get(f"/api/v1/studies/{study_id}/export?format=csv")
    assert export_csv.status_code == 200
    assert "session_id,participant_id,status,trial_index" in export_csv.text

    admin_sessions = reloaded_client.get(f"/api/v1/admin/studies/{study_id}/sessions")
    assert admin_sessions.status_code == 200
    assert admin_sessions.json()[0]["n_trials"] == 1

    delete_session = reloaded_client.delete(f"/api/v1/admin/sessions/{session_id}")
    assert delete_session.status_code == 200
    deleted_results = reloaded_client.get(f"/api/v1/sessions/{session_id}/results")
    assert deleted_results.status_code == 404

    delete_study = reloaded_client.delete(f"/api/v1/admin/studies/{study_id}")
    assert delete_study.status_code == 200
    missing_study = reloaded_client.get(f"/api/v1/studies/{study_id}")
    assert missing_study.status_code == 404


def test_pairwise_session_continues_after_reload():
    study_id = _create_study("Pairwise Resume", paradigm="pairwise")
    session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={"participant_id": "pairwise_p1"})
    session_id = session_resp.json()["session_id"]

    first_trial = client.get(f"/api/v1/sessions/{session_id}/next").json()
    submit_resp = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": first_trial["trial_index"],
            "subset_indices": first_trial["subset_indices"],
            "rating": 6,
            "duration_seconds": 3.0,
        },
    )
    assert submit_resp.status_code == 200

    reloaded_client = _reload_client()
    session_status = reloaded_client.get(f"/api/v1/sessions/{session_id}")
    assert session_status.status_code == 200
    assert session_status.json()["current_trial_index"] == 1

    next_after_reload = reloaded_client.get(f"/api/v1/sessions/{session_id}/next")
    assert next_after_reload.status_code == 200
    assert next_after_reload.json()["trial_index"] == 1
    assert len(next_after_reload.json()["subset_indices"]) == 2

    results_resp = reloaded_client.get(f"/api/v1/sessions/{session_id}/results")
    assert results_resp.status_code == 200
    assert results_resp.json()["n_trials"] == 1


def test_adaptive_session_continues_after_reload():
    study_resp = client.post(
        "/api/v1/studies",
        json={
            "name": "Adaptive Resume",
            "paradigm": "adaptive",
            "language": "en",
            "config": {"min_subset_size": 3, "max_subset_size": 4, "evidence_threshold": 999},
        },
    )
    assert study_resp.status_code == 201
    study_id = study_resp.json()["id"]
    stimuli_resp = client.post(
        f"/api/v1/studies/{study_id}/stimuli",
        json={
            "stimuli": [
                {"ordinal": idx, "filename": f"adaptive_{idx}.mp4", "media_type": "video", "media_url": f"https://example.com/adaptive_{idx}.mp4"}
                for idx in range(5)
            ]
        },
    )
    assert stimuli_resp.status_code == 200

    session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={"participant_id": "adaptive_p1"})
    session_id = session_resp.json()["session_id"]

    first_trial = client.get(f"/api/v1/sessions/{session_id}/next").json()
    assert first_trial["trial_index"] == 0
    assert len(first_trial["subset_indices"]) == 5

    submit_resp = client.post(
        f"/api/v1/sessions/{session_id}/trials",
        json={
            "trial_index": first_trial["trial_index"],
            "subset_indices": first_trial["subset_indices"],
            "positions": _positions_for(first_trial["subset_indices"]),
            "duration_seconds": 14.0,
        },
    )
    assert submit_resp.status_code == 200

    reloaded_client = _reload_client()
    session_status = reloaded_client.get(f"/api/v1/sessions/{session_id}")
    assert session_status.status_code == 200
    assert session_status.json()["current_trial_index"] == 1

    next_after_reload = reloaded_client.get(f"/api/v1/sessions/{session_id}/next")
    assert next_after_reload.status_code == 200
    assert next_after_reload.json()["trial_index"] == 1
    assert next_after_reload.json()["is_final"] is False
    assert len(next_after_reload.json()["subset_indices"]) >= 3

    results_resp = reloaded_client.get(f"/api/v1/sessions/{session_id}/results")
    assert results_resp.status_code == 200
    assert results_resp.json()["n_trials"] == 1


def test_chain_admin_listing_and_delete_survive_reload():
    study_a = _create_study("Chain Admin A")
    study_b = _create_study("Chain Admin B")

    chain_resp = client.post("/api/v1/chains", json={"name": "Admin Chain"})
    assert chain_resp.status_code == 201
    chain_id = chain_resp.json()["id"]

    assert client.post(f"/api/v1/chains/{chain_id}/studies", json={"study_id": study_a, "position": 0}).status_code == 201
    assert client.post(f"/api/v1/chains/{chain_id}/studies", json={"study_id": study_b, "position": 1}).status_code == 201

    invite_resp = client.post(f"/api/v1/chains/{chain_id}/invites", json={"participant_id": "chain_admin", "count": 1})
    token = invite_resp.json()[0]["token"]

    start_resp = client.post(f"/api/v1/public/chain-invites/{token}/start")
    assert start_resp.status_code == 200
    chain_session_id = start_resp.json()["chain_session_id"]
    first_session_id = start_resp.json()["session_id"]
    assert client.post(f"/api/v1/sessions/{first_session_id}/complete").status_code == 200
    next_resp = client.post(f"/api/v1/public/chain-invites/{token}/next")
    assert next_resp.status_code == 200

    reloaded_client = _reload_client()
    chain_sessions_resp = reloaded_client.get(f"/api/v1/chains/{chain_id}/sessions")
    assert chain_sessions_resp.status_code == 200
    participants = chain_sessions_resp.json()["participants"]
    assert len(participants) == 1
    assert participants[0]["chain_session_id"] == chain_session_id
    assert len(participants[0]["sessions"]) >= 2

    delete_resp = reloaded_client.delete(f"/api/v1/chains/{chain_id}/sessions/{chain_session_id}")
    assert delete_resp.status_code == 204

    chain_sessions_after_delete = reloaded_client.get(f"/api/v1/chains/{chain_id}/sessions")
    assert chain_sessions_after_delete.status_code == 200
    assert chain_sessions_after_delete.json()["participants"] == []


def test_demo_start_returns_hosted_session_payload():
    demo_resp = client.post("/api/v1/public/demo/start", json={"paradigm": "adaptive", "n_stimuli": 16})
    assert demo_resp.status_code == 201
    payload = demo_resp.json()
    assert payload["paradigm"] == "adaptive"
    assert payload["n_stimuli"] == 16
    assert len(payload["stimuli"]) == 16
    assert all(stimulus["media_type"] == "video" for stimulus in payload["stimuli"])
