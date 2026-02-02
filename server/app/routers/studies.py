"""
Study management endpoints.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas import (
    StudyCreate,
    StudyResponse,
    StudyUpdate,
    StimulusResponse,
    StimulusBatchCreate,
)

router = APIRouter(prefix="/studies", tags=["studies"])

# In-memory storage for development (replace with Supabase later)
_studies_db: dict = {}
_stimuli_db: dict = {}
_study_counter = 0


@router.post("", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
async def create_study(study: StudyCreate) -> StudyResponse:
    """Create a new study."""
    import uuid
    from datetime import datetime
    
    study_id = uuid.uuid4()
    owner_id = uuid.uuid4()  # TODO: Get from auth
    
    study_data = {
        "id": study_id,
        "owner_id": owner_id,
        "name": study.name,
        "description": study.description,
        "paradigm": study.paradigm,
        "config": study.config,
        "language": study.language,
        "instructions": study.instructions,
        "created_at": datetime.utcnow(),
        "n_stimuli": 0,
    }
    
    _studies_db[study_id] = study_data
    _stimuli_db[study_id] = []
    
    return StudyResponse(**study_data)


@router.get("/{study_id}", response_model=StudyResponse)
async def get_study(study_id: UUID) -> StudyResponse:
    """Get study details."""
    if study_id not in _studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    study_data = _studies_db[study_id]
    study_data["n_stimuli"] = len(_stimuli_db.get(study_id, []))
    return StudyResponse(**study_data)


@router.patch("/{study_id}", response_model=StudyResponse)
async def update_study(study_id: UUID, update: StudyUpdate) -> StudyResponse:
    """Update study configuration."""
    if study_id not in _studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    study_data = _studies_db[study_id]
    
    if update.name is not None:
        study_data["name"] = update.name
    if update.description is not None:
        study_data["description"] = update.description
    if update.config is not None:
        study_data["config"] = update.config
    if update.language is not None:
        study_data["language"] = update.language
    if update.instructions is not None:
        study_data["instructions"] = update.instructions
    
    study_data["n_stimuli"] = len(_stimuli_db.get(study_id, []))
    return StudyResponse(**study_data)


@router.delete("/{study_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_study(study_id: UUID):
    """Delete a study and all associated data."""
    if study_id not in _studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    del _studies_db[study_id]
    if study_id in _stimuli_db:
        del _stimuli_db[study_id]


@router.get("/{study_id}/stimuli", response_model=List[StimulusResponse])
async def list_stimuli(study_id: UUID) -> List[StimulusResponse]:
    """List all stimuli in a study."""
    if study_id not in _studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    return [StimulusResponse(**s) for s in _stimuli_db.get(study_id, [])]


@router.post("/{study_id}/stimuli", response_model=List[StimulusResponse])
async def register_stimuli(study_id: UUID, payload: StimulusBatchCreate) -> List[StimulusResponse]:
    """Register stimuli for a study (in-memory for now)."""
    if study_id not in _studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )

    import uuid

    existing = _stimuli_db.get(study_id, [])
    existing_ordinals = {s["ordinal"] for s in existing}

    for stim in payload.stimuli:
        if stim.ordinal in existing_ordinals:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate ordinal {stim.ordinal}"
            )
        stim_data = {
            "id": uuid.uuid4(),
            "ordinal": stim.ordinal,
            "filename": stim.filename,
            "media_type": stim.media_type,
            "media_url": stim.media_url,
            "thumbnail_url": stim.thumbnail_url,
            "duration_seconds": stim.duration_seconds,
        }
        existing.append(stim_data)

    # Keep stimuli ordered by ordinal for consistent indexing
    existing.sort(key=lambda s: s["ordinal"])
    _stimuli_db[study_id] = existing
    return [StimulusResponse(**s) for s in existing]


# Export storage for other routers
def get_studies_db():
    return _studies_db

def get_stimuli_db():
    return _stimuli_db
