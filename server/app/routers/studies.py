"""
Study management endpoints.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import (
    StudyCreate,
    StudyResponse,
    StudyUpdate,
    StimulusResponse,
    StimulusBatchCreate,
)
from app.routers.experimenter import get_optional_owner, get_required_owner

router = APIRouter(prefix="/studies", tags=["studies"])

# In-memory storage for development (replace with Supabase later)
_studies_db: dict = {}
_stimuli_db: dict = {}
_study_counter = 0


@router.get("", response_model=List[StudyResponse])
async def list_studies(owner_id: Optional[UUID] = Depends(get_optional_owner)):
    """List studies filtered by experimenter key. Returns empty if no key."""
    if owner_id is None:
        return []
    stimuli_db = _stimuli_db
    out = []
    for study in _studies_db.values():
        if study.get("owner_id") != owner_id:
            continue
        data = {**study, "n_stimuli": len(stimuli_db.get(study["id"], []))}
        out.append(StudyResponse(**data))
    return out


@router.post("", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
async def create_study(
    study: StudyCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> StudyResponse:
    """Create a new study. Requires experimenter key."""
    import uuid
    from datetime import datetime
    
    study_id = uuid.uuid4()
    
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
async def update_study(
    study_id: UUID,
    update: StudyUpdate,
    owner_id: UUID = Depends(get_required_owner),
) -> StudyResponse:
    """Update study configuration. Requires experimenter key."""
    if study_id not in _studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    study_data = _studies_db[study_id]
    if study_data.get("owner_id") != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your study"
        )
    
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
async def delete_study(
    study_id: UUID,
    owner_id: UUID = Depends(get_required_owner),
):
    """Delete a study and all associated data. Requires experimenter key."""
    if study_id not in _studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    study_data = _studies_db[study_id]
    if study_data.get("owner_id") != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your study"
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
async def register_stimuli(
    study_id: UUID,
    payload: StimulusBatchCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> List[StimulusResponse]:
    """Register stimuli for a study. Requires experimenter key."""
    if study_id not in _studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    study_data = _studies_db[study_id]
    if study_data.get("owner_id") != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your study"
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
