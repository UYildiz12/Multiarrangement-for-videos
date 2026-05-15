"""
Tests for Pydantic schema validation.
"""

import pytest
from pydantic import ValidationError

from app.schemas import (
    StudyCreate,
    StudyUpdate,
    SessionCreate,
    TrialSubmit,
    Position,
    Paradigm,
    Language,
    MediaType,
    SetCoverConfig,
    AdaptiveConfig,
)


class TestStudySchemas:
    """Tests for study-related schemas."""

    def test_study_create_valid(self):
        """Test valid study creation."""
        study = StudyCreate(
            name="Test Study",
            paradigm=Paradigm.ADAPTIVE,
            language=Language.EN,
            config={"evidence_threshold": 0.35},
        )
        assert study.name == "Test Study"
        assert study.paradigm == Paradigm.ADAPTIVE
        assert study.language == Language.EN

    def test_study_create_minimal(self):
        """Test study creation with only required fields."""
        study = StudyCreate(name="Minimal", paradigm=Paradigm.SETCOVER)
        assert study.name == "Minimal"
        assert study.description is None
        assert study.config == {}

    def test_study_create_empty_name_fails(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            StudyCreate(name="", paradigm=Paradigm.ADAPTIVE)
        assert "string_too_short" in str(exc_info.value)

    def test_study_create_invalid_paradigm(self):
        """Test that invalid paradigm is rejected."""
        with pytest.raises(ValidationError):
            StudyCreate(name="Test", paradigm="invalid")

    def test_study_update_partial(self):
        """Test partial study update."""
        update = StudyUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.description is None
        assert update.config is None


class TestConfigSchemas:
    """Tests for configuration schemas."""

    def test_setcover_config_defaults(self):
        """Test set-cover config defaults."""
        config = SetCoverConfig()
        assert config.batch_size == 6
        assert config.flex is False
        assert config.setcover_algorithm == "balanced"
        assert config.weight_alpha == 2.0

    def test_setcover_config_batch_size_bounds(self):
        """Test batch size validation."""
        with pytest.raises(ValidationError):
            SetCoverConfig(batch_size=2)  # Too small
        with pytest.raises(ValidationError):
            SetCoverConfig(batch_size=15)  # Too large

    def test_adaptive_config_defaults(self):
        """Test adaptive config defaults."""
        config = AdaptiveConfig()
        assert config.evidence_threshold == 0.35
        assert config.min_subset_size == 4
        assert config.max_subset_size == 6
        assert config.use_inverse_mds is True

    def test_adaptive_config_threshold_bounds(self):
        """Test evidence threshold validation."""
        with pytest.raises(ValidationError):
            AdaptiveConfig(evidence_threshold=-0.1)
        with pytest.raises(ValidationError):
            AdaptiveConfig(evidence_threshold=1.5)


class TestSessionSchemas:
    """Tests for session-related schemas."""

    def test_session_create_valid(self):
        """Test valid session creation."""
        session = SessionCreate(participant_id="P001")
        assert session.participant_id == "P001"

    def test_session_create_empty_participant_fails(self):
        """Test that empty participant ID is rejected."""
        with pytest.raises(ValidationError):
            SessionCreate(participant_id="")


class TestTrialSchemas:
    """Tests for trial-related schemas."""

    def test_position_valid(self):
        """Test valid position."""
        pos = Position(x=150.5, y=200.3)
        assert pos.x == 150.5
        assert pos.y == 200.3

    def test_trial_submit_valid(self):
        """Test valid trial submission."""
        trial = TrialSubmit(
            trial_index=0,
            subset_indices=[0, 1, 2, 3],
            positions={
                "0": Position(x=100, y=100),
                "1": Position(x=200, y=200),
                "2": Position(x=300, y=300),
                "3": Position(x=400, y=400),
            },
            duration_seconds=45.2,
        )
        assert trial.trial_index == 0
        assert len(trial.subset_indices) == 4
        assert len(trial.positions) == 4

    def test_trial_submit_negative_duration_fails(self):
        """Test that negative duration is rejected."""
        with pytest.raises(ValidationError):
            TrialSubmit(
                trial_index=0,
                subset_indices=[0, 1],
                positions={"0": Position(x=0, y=0), "1": Position(x=1, y=1)},
                duration_seconds=-1.0,
            )


class TestEnums:
    """Tests for enum values."""

    def test_paradigm_values(self):
        """Test paradigm enum values."""
        assert Paradigm.SETCOVER.value == "setcover"
        assert Paradigm.ADAPTIVE.value == "adaptive"

    def test_language_values(self):
        """Test language enum values."""
        assert Language.EN.value == "en"
        assert Language.TR.value == "tr"

    def test_media_type_values(self):
        """Test media type enum values."""
        assert MediaType.VIDEO.value == "video"
        assert MediaType.AUDIO.value == "audio"
        assert MediaType.IMAGE.value == "image"
