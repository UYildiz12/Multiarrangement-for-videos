"""
Invite and public participation endpoints.
"""

from typing import Dict, List
from uuid import UUID
import secrets

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import (
    InviteCreate,
    InviteResponse,
    SessionStartResponse,
    StudyCreate,
    Paradigm,
    Language,
    StimulusCreate,
    MediaType,
    StimulusBatchCreate,
)
import uuid
import datetime
from app.routers.studies import get_studies_db, get_stimuli_db
from app.routers.sessions import create_session
from app.routers.experimenter import get_required_owner

router = APIRouter(tags=["invites"])

_invites_db: Dict[str, dict] = {}


@router.post(
    "/admin/studies/{study_id}/invites",
    response_model=List[InviteResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_invites(
    study_id: UUID,
    payload: InviteCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> List[InviteResponse]:
    """Create one or more participant invites for a study. Requires ownership."""
    studies_db = get_studies_db()
    if study_id not in studies_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    study = studies_db[study_id]
    if study.get("owner_id") != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    count = max(1, int(payload.count or 1))
    invites = []
    for _ in range(count):
        token = secrets.token_urlsafe(16)
        invite = {
            "token": token,
            "study_id": study_id,
            "participant_id": payload.participant_id,
            "used_session_id": None,
        }
        _invites_db[token] = invite
        invites.append(InviteResponse(**invite))
    return invites


@router.post(
    "/public/invites/{token}/start",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_from_invite(token: str) -> SessionStartResponse:
    """Start a participant session from a one-time invite token."""
    invite = _invites_db.get(token)
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    if invite.get("used_session_id") is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite already used")

    study_id = invite["study_id"]
    studies_db = get_studies_db()
    stimuli_db = get_stimuli_db()

    if study_id not in studies_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if len(stimuli_db.get(study_id, [])) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Study has no stimuli")

    participant_id = invite.get("participant_id") or token
    response = create_session(study_id, participant_id)
    invite["used_session_id"] = response.session_id
    _invites_db[token] = invite
    return response


from pydantic import BaseModel

class DemoStartRequest(BaseModel):
    paradigm: str = "adaptive"  # "adaptive" (LtW) or "setcover"
    n_stimuli: int = 16

@router.post(
    "/public/demo/start",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_demo_session(req: DemoStartRequest) -> SessionStartResponse:
    """Start a fresh throwaway session for a demo."""
    from app.routers.studies import _studies_db, _stimuli_db
    from app.routers.sessions import create_session

    study_id = uuid.uuid4()
    
    # We use a dummy owner UUID
    dummy_owner_id = uuid.uuid4()
    
    study_data = {
        "id": study_id,
        "owner_id": dummy_owner_id,
        "name": f"Demo {req.paradigm.title()} {req.n_stimuli}",
        "description": "Ephemeral demo study",
        "paradigm": Paradigm.ADAPTIVE if req.paradigm == "adaptive" else Paradigm.SETCOVER,
        "config": {
            "evidence_threshold": 0.35,
            "utility_exponent": 10.0,
            "min_subset_size": 4,
            "max_subset_size": 6,
            "use_inverse_mds": True,
            "batch_size": 6,
            "setcover_weight_mode": "max",
            "setcover_weight_alpha": 2.0,
        },
        "language": Language.EN,
        "instructions": [
            "Please arrange the stimuli on the screen based on their perceived similarity.",
            "Place similar stimuli closer together — token center distances reflect similarity.",
            "You can play the videos by clicking on them.",
            "When you are finished with an arrangement, click the 'Next' button."
        ],
        "created_at": datetime.datetime.utcnow(),
        "n_stimuli": req.n_stimuli,
        "is_demo": True, # Custom flag just in case
    }
    _studies_db[study_id] = study_data
    
    # Create mock stimuli
    stims = []
    for i in range(req.n_stimuli):
        stims.append({
            "id": uuid.uuid4(),
            "ordinal": i,
            "filename": f"Stimulus {i+1}",
            "media_type": MediaType.VIDEO,
            "media_url": "", # We'll just let the frontend provide the videos or handle empty URLs (wait, frontend demo page will provide the preset videos). Just give it preset video names.
            "thumbnail_url": None,
            "duration_seconds": 3.0,
        })
        
    # Since frontend will also manage videos, we'll try to sync filenames with the preset videos if possible.
    # Actually, the presets are in `classicVideos` in frontend (e.g. from `/api/videos`). We'll just create generic stimuli here.
    _stimuli_db[study_id] = stims

    participant_id = f"demo_user_{uuid.uuid4().hex[:8]}"
    response = create_session(study_id, participant_id)
    return response


def get_invites_db():
    return _invites_db
