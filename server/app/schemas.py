"""
Pydantic schemas for the Multiarrangement API.

Defines request/response models for all endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Enums
class Paradigm(str, Enum):
    SETCOVER = "setcover"
    ADAPTIVE = "adaptive"
    PAIRWISE = "pairwise"


class Language(str, Enum):
    EN = "en"
    TR = "tr"


class MediaType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"


class SessionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class UserRole(str, Enum):
    ADMIN = "admin"
    RESEARCHER = "researcher"


# Config schemas for different paradigms
class SetCoverConfig(BaseModel):
    """Configuration for set-cover paradigm."""
    batch_size: int = Field(default=6, ge=3, le=12)
    flex: bool = False
    setcover_algorithm: str = "balanced"
    weight_alpha: float = 2.0
    weight_mode: str = "max"
    use_inverse_mds: bool = False


class AdaptiveConfig(BaseModel):
    """Configuration for adaptive LTW paradigm."""
    evidence_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    min_subset_size: int = Field(default=4, ge=3)
    max_subset_size: int = Field(default=6, le=12)
    utility_exponent: float = 10.0
    use_inverse_mds: bool = True
    inverse_mds_max_iter: int = 15
    inverse_mds_step_c: float = 0.3


class PairwiseConfig(BaseModel):
    """Configuration for pairwise comparison paradigm."""
    randomize_pairs: bool = True
    sample_fraction: float = Field(default=1.0, ge=0.1, le=1.0)
    repeat_pairs: int = Field(default=1, ge=1, le=5)


# Study schemas
class StudyCreate(BaseModel):
    """Request body for creating a study."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    paradigm: Paradigm
    language: Language = Language.EN
    config: Dict[str, Any] = Field(default_factory=dict)
    instructions: Optional[List[str]] = None


class StudyUpdate(BaseModel):
    """Request body for updating a study."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    language: Optional[Language] = None
    instructions: Optional[List[str]] = None


class StudyResponse(BaseModel):
    """Response for study endpoints."""
    id: UUID
    owner_id: UUID
    name: str
    description: Optional[str]
    paradigm: Paradigm
    config: Dict[str, Any]
    language: Language
    instructions: Optional[List[str]]
    created_at: datetime
    n_stimuli: int = 0

    model_config = ConfigDict(from_attributes=True)


# Stimulus schemas
class StimulusResponse(BaseModel):
    """Response for stimulus data."""
    id: UUID
    ordinal: int
    filename: str
    media_type: MediaType
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    media_storage_path: Optional[str] = None
    thumbnail_storage_path: Optional[str] = None
    duration_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class StimulusUploadResponse(BaseModel):
    """Response after initiating stimulus upload."""
    stimulus_id: UUID
    upload_url: str
    storage_path: str


class StimulusCreate(BaseModel):
    """Request body for registering a stimulus."""
    ordinal: int = Field(..., ge=0)
    filename: str = Field(..., min_length=1)
    media_type: MediaType
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    media_storage_path: Optional[str] = None
    thumbnail_storage_path: Optional[str] = None
    duration_seconds: Optional[float] = None


class StimulusBatchCreate(BaseModel):
    """Request body for registering multiple stimuli."""
    stimuli: List[StimulusCreate]


# Session schemas
class SessionCreate(BaseModel):
    """Request body for starting a session."""
    participant_id: str = Field(..., min_length=1, max_length=100)


class SessionResponse(BaseModel):
    """Response for session endpoints."""
    id: UUID
    study_id: UUID
    participant_id: str
    status: SessionStatus
    paradigm: Paradigm
    current_trial_index: int
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SessionStartResponse(BaseModel):
    """Extended response when starting a new session."""
    session_id: UUID
    study_id: UUID
    paradigm: Paradigm
    n_stimuli: int
    stimuli: List[StimulusResponse]
    config: Dict[str, Any]


# Invite schemas
class InviteCreate(BaseModel):
    """Request body for creating one or more invites."""
    participant_id: Optional[str] = Field(None, min_length=1, max_length=100)
    count: Optional[int] = Field(default=1, ge=1, le=100)


class InviteResponse(BaseModel):
    """Response for invite creation."""
    token: str
    study_id: UUID
    participant_id: Optional[str] = None
    used_session_id: Optional[UUID] = None


# Trial schemas
class Position(BaseModel):
    """A 2D position."""
    x: float
    y: float


class NextTrialResponse(BaseModel):
    """Response for getting the next trial."""
    trial_index: int
    subset_indices: List[int]
    is_final: bool = False


class TrialSubmit(BaseModel):
    """Request body for submitting a trial result."""
    trial_index: int
    subset_indices: List[int]
    positions: Optional[Dict[str, Position]] = None  # ordinal -> position (for arrangement)
    rating: Optional[int] = Field(default=None, ge=1, le=7)  # 1-7 scale (for pairwise)
    duration_seconds: float = Field(..., ge=0)
    arena_size: Optional[float] = Field(default=None, gt=0)
    # Optional token-movement recording: {"version": 1, "samples": [[t_ms, ordinal, x, y, phase], ...]}
    movement_trace: Optional[Dict[str, Any]] = None


class TrialResponse(BaseModel):
    """Response for trial data."""
    id: UUID
    trial_index: int
    subset_indices: List[int]
    duration_seconds: Optional[float]
    arena_size: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime]
    next_trial: Optional[NextTrialResponse] = None

    model_config = ConfigDict(from_attributes=True)


# Results schemas
class RdmScaleInfo(BaseModel):
    """How the primary RDM was scaled for display/export."""
    method: str
    divisor: float
    output_min: float = 0.0
    output_max: float = 1.0
    raw_units: str
    description: str


class ResultsResponse(BaseModel):
    """Response for computed results."""
    rdm: List[List[float]]
    rdm_raw: Optional[List[List[float]]] = None
    rdm_scale: RdmScaleInfo
    evidence: List[List[float]]
    evidence_raw: Optional[List[List[float]]] = None
    evidence_normalized: Optional[List[List[float]]] = None
    n_trials: int
    labels: List[str]
    schedule_diagnostics: Optional[Dict[str, Any]] = None


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    NPY = "npy"


# Health check
class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str

# Chain schemas
class ChainStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ChainCreate(BaseModel):
    """Request body for creating a chain."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class ChainResponse(BaseModel):
    """Response for chain endpoints."""
    id: UUID
    owner_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    studies: List["ChainStudyResponse"] = []

    model_config = ConfigDict(from_attributes=True)


class ChainStudyCreate(BaseModel):
    """Request body for adding a study to a chain."""
    study_id: UUID
    position: Optional[int] = None  # If None, append at end


class ChainStudyResponse(BaseModel):
    """Response for chain study entries."""
    id: UUID
    chain_id: UUID
    study_id: UUID
    study_name: str
    paradigm: Paradigm
    position: int

    model_config = ConfigDict(from_attributes=True)


class ChainInviteCreate(BaseModel):
    """Request body for creating chain invites."""
    participant_id: Optional[str] = Field(None, min_length=1, max_length=100)
    count: Optional[int] = Field(default=1, ge=1, le=100)


class ChainInviteResponse(BaseModel):
    """Response for chain invite creation."""
    token: str
    chain_id: UUID
    participant_id: Optional[str] = None


class ChainSessionResponse(BaseModel):
    """Response for chain session status."""
    id: UUID
    chain_id: UUID
    chain_name: str
    current_position: int
    total_studies: int
    current_session_id: Optional[UUID] = None
    status: ChainStatus
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ChainSessionStartResponse(BaseModel):
    """Extended response when starting a chain session."""
    chain_session_id: UUID
    chain_id: UUID
    chain_name: str
    total_studies: int
    current_position: int
    session_id: UUID
    study_id: UUID
    paradigm: Paradigm
    n_stimuli: int
    stimuli: List[StimulusResponse]
    config: Dict[str, Any]
