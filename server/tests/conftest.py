"""
Test configuration and fixtures for the Multiarrangement server.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_study_data():
    """Sample data for creating a study."""
    return {
        "name": "Test Video Study",
        "description": "A test study for unit testing",
        "paradigm": "adaptive",
        "language": "en",
        "config": {
            "evidence_threshold": 0.35,
            "min_subset_size": 4,
            "max_subset_size": 6,
        },
    }


@pytest.fixture
def sample_setcover_study_data():
    """Sample data for a set-cover study."""
    return {
        "name": "Set-Cover Study",
        "paradigm": "setcover",
        "language": "en",
        "config": {
            "batch_size": 6,
            "flex": False,
        },
    }


@pytest.fixture
def sample_trial_positions():
    """Sample trial positions for 4 stimuli."""
    return {
        "0": {"x": 150.5, "y": 200.3},
        "1": {"x": 320.1, "y": 180.7},
        "2": {"x": 400.0, "y": 350.2},
        "3": {"x": 250.0, "y": 400.0},
    }
