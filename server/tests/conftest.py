"""
Test configuration and fixtures for the Multiarrangement server.
"""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_BOOTSTRAP_DB = Path(tempfile.gettempdir()) / "multiarrangement_server_bootstrap.sqlite3"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_BOOTSTRAP_DB.as_posix()}")

from app.main import app
from app.storage import reset_db


@pytest.fixture(autouse=True)
def local_dev_bypass_auth(monkeypatch, tmp_path):
    """Run API tests in local keyless mode with an isolated SQLite database."""
    monkeypatch.setenv("LOCAL_DEV_BYPASS_AUTH", "1")
    db_path = tmp_path / "test_hosted.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    reset_db()
    yield
    reset_db()


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
