"""
Tests for API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check."""

    def test_health_check(self, client):
        """Test health endpoint returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestStudyEndpoints:
    """Tests for study CRUD operations."""

    def test_create_study(self, client):
        """Test creating a study."""
        response = client.post("/api/v1/studies", json={
            "name": "Test Study",
            "paradigm": "adaptive",
            "language": "en",
            "config": {"evidence_threshold": 0.35}
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Study"
        assert data["paradigm"] == "adaptive"
        assert "id" in data

    def test_get_study(self, client):
        """Test getting a study."""
        # Create first
        create_resp = client.post("/api/v1/studies", json={
            "name": "Get Test",
            "paradigm": "setcover"
        })
        study_id = create_resp.json()["id"]
        
        # Get it
        response = client.get(f"/api/v1/studies/{study_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test"

    def test_get_nonexistent_study(self, client):
        """Test 404 for nonexistent study."""
        import uuid
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/studies/{fake_id}")
        assert response.status_code == 404

    def test_update_study(self, client):
        """Test updating a study."""
        create_resp = client.post("/api/v1/studies", json={
            "name": "Original",
            "paradigm": "adaptive"
        })
        study_id = create_resp.json()["id"]
        
        response = client.patch(f"/api/v1/studies/{study_id}", json={
            "name": "Updated Name"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_delete_study(self, client):
        """Test deleting a study."""
        create_resp = client.post("/api/v1/studies", json={
            "name": "To Delete",
            "paradigm": "setcover"
        })
        study_id = create_resp.json()["id"]
        
        # Delete
        response = client.delete(f"/api/v1/studies/{study_id}")
        assert response.status_code == 204
        
        # Verify gone
        get_resp = client.get(f"/api/v1/studies/{study_id}")
        assert get_resp.status_code == 404


class TestSessionEndpoints:
    """Tests for session management."""

    def test_start_session(self, client):
        """Test starting a session."""
        # Create study first
        study_resp = client.post("/api/v1/studies", json={
            "name": "Session Test",
            "paradigm": "adaptive",
            "config": {"min_subset_size": 3, "max_subset_size": 4}
        })
        study_id = study_resp.json()["id"]
        
        # Start session
        response = client.post(f"/api/v1/studies/{study_id}/sessions", json={
            "participant_id": "P001"
        })
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["paradigm"] == "adaptive"

    def test_get_session(self, client):
        """Test getting session status."""
        # Setup
        study_resp = client.post("/api/v1/studies", json={
            "name": "Get Session Test",
            "paradigm": "setcover"
        })
        study_id = study_resp.json()["id"]
        
        session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={
            "participant_id": "P002"
        })
        session_id = session_resp.json()["session_id"]
        
        # Get
        response = client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["participant_id"] == "P002"
        assert response.json()["status"] == "in_progress"

    def test_complete_session(self, client):
        """Test completing a session."""
        # Setup
        study_resp = client.post("/api/v1/studies", json={
            "name": "Complete Test",
            "paradigm": "adaptive"
        })
        study_id = study_resp.json()["id"]
        
        session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={
            "participant_id": "P003"
        })
        session_id = session_resp.json()["session_id"]
        
        # Complete
        response = client.post(f"/api/v1/sessions/{session_id}/complete")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"


class TestResultsEndpoints:
    """Tests for results retrieval."""

    def test_get_session_results(self, client):
        """Test getting session results."""
        # Setup
        study_resp = client.post("/api/v1/studies", json={
            "name": "Results Test",
            "paradigm": "adaptive"
        })
        study_id = study_resp.json()["id"]
        
        session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={
            "participant_id": "P004"
        })
        session_id = session_resp.json()["session_id"]
        
        # Get results
        response = client.get(f"/api/v1/sessions/{session_id}/results")
        assert response.status_code == 200
        data = response.json()
        assert "rdm" in data
        assert "evidence" in data
        assert "n_trials" in data

    def test_export_study_json(self, client):
        """Test JSON export."""
        study_resp = client.post("/api/v1/studies", json={
            "name": "Export Test",
            "paradigm": "setcover"
        })
        study_id = study_resp.json()["id"]
        
        response = client.get(f"/api/v1/studies/{study_id}/export?format=json")
        assert response.status_code == 200
        data = response.json()
        assert "study" in data
        assert "sessions" in data


class TestTrialFlow:
    """Integration test for full trial flow."""

    def test_adaptive_trial_flow(self, client):
        """Test submitting trials in adaptive mode."""
        # Create study
        study_resp = client.post("/api/v1/studies", json={
            "name": "Flow Test",
            "paradigm": "adaptive",
            "config": {"min_subset_size": 2, "max_subset_size": 3}
        })
        study_id = study_resp.json()["id"]
        
        # Start session
        session_resp = client.post(f"/api/v1/studies/{study_id}/sessions", json={
            "participant_id": "FlowTest"
        })
        session_id = session_resp.json()["session_id"]
        
        # Get next trial (may be empty with no stimuli)
        next_resp = client.get(f"/api/v1/sessions/{session_id}/next")
        assert next_resp.status_code == 200
