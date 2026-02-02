"""
Invite and public participation endpoints.
"""

from typing import Dict, List, Optional
from uuid import UUID
import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.schemas import (
    InviteCreate,
    InviteResponse,
    SessionStartResponse,
)
from app.routers.studies import get_studies_db, get_stimuli_db
from app.routers.sessions import create_session

router = APIRouter(tags=["invites"])

_invites_db: Dict[str, dict] = {}


def _require_admin(x_admin_secret: Optional[str] = Header(default=None, alias="x-admin-secret")):
    secret = os.getenv("ADMIN_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_SECRET not configured"
        )
    if x_admin_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin secret"
        )
    return True


@router.post(
    "/admin/studies/{study_id}/invites",
    response_model=List[InviteResponse],
    dependencies=[Depends(_require_admin)],
    status_code=status.HTTP_201_CREATED,
)
async def create_invites(study_id: UUID, payload: InviteCreate) -> List[InviteResponse]:
    """Create one or more participant invites for a study."""
    studies_db = get_studies_db()
    if study_id not in studies_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

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


def get_invites_db():
    return _invites_db
