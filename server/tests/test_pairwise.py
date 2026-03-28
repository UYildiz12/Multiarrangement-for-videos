import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import Paradigm

client = TestClient(app)

@pytest.fixture
def pairwise_study(client):
    """Create a pairwise study with 4 stimuli."""
    # 1. Create study
    study_resp = client.post("/api/v1/studies", json={
        "name": "Pairwise Test",
        "paradigm": "pairwise",
        "config": {
            "randomize_pairs": False,
            "repeat_pairs": 1
        }
    })
    assert study_resp.status_code == 201
    study_id = study_resp.json()["id"]

    # 2. Add 4 stimuli
    stimuli_payload = {"stimuli": [
        {"ordinal": i, "filename": f"clip_{i}.mp4", "media_type": "video"}
        for i in range(4)
    ]}
    client.post(f"/api/v1/studies/{study_id}/stimuli", json=stimuli_payload)
    return study_id

def test_pairwise_workflow(pairwise_study):
    """Test full pairwise workflow: create session, get pairs, submit ratings."""
    study_id = pairwise_study
    
    # 1. Start Session
    session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={
        "participant_id": "test_p1"
    })
    assert session_resp.status_code == 201
    session_id = session_resp.json()["session_id"]
    n_stimuli = session_resp.json()["n_stimuli"]
    assert n_stimuli == 4

    # Expected pairs for 4 stimuli: (0,1), (0,2), (0,3), (1,2), (1,3), (2,3) -> 6 pairs
    expected_pairs = 6
    
    for i in range(expected_pairs):
        # 2. Get Next Trial
        next_resp = client.get(f"/api/v1/sessions/{session_id}/next")
        assert next_resp.status_code == 200
        next_data = next_resp.json()
        
        assert next_data["trial_index"] == i
        assert len(next_data["subset_indices"]) == 2  # Always a pair
        # is_final is always False while there are still pairs to display;
        # the final signal comes from the NEXT call after the last submit
        assert next_data["is_final"] is False

        # 3. Submit Rating (1-7 scale)
        # Rating 7 = Very Similar => Dissimilarity 0
        # Rating 1 = Very Different => Dissimilarity 1
        rating = 7 if i % 2 == 0 else 1  # Alternating very similar / very different
        
        submit_resp = client.post(f"/api/v1/sessions/{session_id}/trials", json={
            "trial_index": i,
            "subset_indices": next_data["subset_indices"],
            "rating": rating,
            "duration_seconds": 2.0
        })
        assert submit_resp.status_code == 200
        submit_data = submit_resp.json()
        assert submit_data["trial_index"] == i
        if i < expected_pairs - 1:
            assert submit_data["next_trial"]["trial_index"] == i + 1
            assert submit_data["next_trial"]["is_final"] is False
            assert len(submit_data["next_trial"]["subset_indices"]) == 2
        else:
            assert submit_data["next_trial"]["trial_index"] == expected_pairs
            assert submit_data["next_trial"]["is_final"] is True
            assert submit_data["next_trial"]["subset_indices"] == []
    
    # 4. Verify completion
    next_resp = client.get(f"/api/v1/sessions/{session_id}/next")
    assert next_resp.json()["is_final"] is True
    assert next_resp.json()["subset_indices"] == []

    # 5. Check Results (RDM)
    results_resp = client.get(f"/api/v1/sessions/{session_id}/results")
    assert results_resp.status_code == 200
    results = results_resp.json()
    
    rdm = results["rdm"]
    assert len(rdm) == 4
    # Check diagonal is 0
    for k in range(4):
        assert rdm[k][k] == 0.0

def test_pairwise_invalid_submit(pairwise_study):
    """Test submitting invalid data to pairwise session."""
    study_id = pairwise_study
    session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={
        "participant_id": "test_p2"
    })
    session_id = session_resp.json()["session_id"]
    
    # Get first trial
    next_data = client.get(f"/api/v1/sessions/{session_id}/next").json()

    # Try submitting without rating
    bad_resp = client.post(f"/api/v1/sessions/{session_id}/trials", json={
        "trial_index": 0,
        "subset_indices": next_data["subset_indices"],
        # Missing rating
        "duration_seconds": 1.0
    })
    # Should fail because rating is required for PAIRWISE
    assert bad_resp.status_code == 400
