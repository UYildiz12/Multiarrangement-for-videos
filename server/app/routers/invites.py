"""
Invite and public participation endpoints backed by durable storage.
"""

from __future__ import annotations

import secrets
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update

from app.routers.experimenter import get_required_owner
from app.routers.sessions import create_session, get_session_start_payload
from app.routers.studies import get_study, list_stimuli_for_study
from app.schemas import (
    InviteCreate,
    InviteResponse,
    Language,
    MediaType,
    Paradigm,
    SessionStartResponse,
)
from app.storage import (
    connect,
    fetch_all,
    fetch_one,
    invites_table,
    stimuli_table,
    studies_table,
    utcnow_iso,
)

router = APIRouter(tags=["invites"])

_DEMO_OWNER_ID = UUID("00000000-0000-0000-0000-000000000042")


def get_invite(token: str) -> dict | None:
    with connect(readonly=True) as conn:
        return fetch_one(conn, select(invites_table).where(invites_table.c.token == token))


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
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if study["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    count = max(1, int(payload.count or 1))
    invite_rows = []
    responses = []
    for _ in range(count):
        token = secrets.token_urlsafe(16)
        invite_row = {
            "token": token,
            "study_id": str(study_id),
            "participant_id": payload.participant_id,
            "used_session_id": None,
        }
        invite_rows.append(invite_row)
        responses.append(
            InviteResponse(
                token=token,
                study_id=study_id,
                participant_id=payload.participant_id,
                used_session_id=None,
            )
        )

    with connect() as conn:
        conn.execute(invites_table.insert(), invite_rows)

    return responses


@router.post(
    "/public/invites/{token}/start",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_from_invite(token: str) -> SessionStartResponse:
    invite = get_invite(token)
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    existing_session_id = invite.get("used_session_id")
    if existing_session_id:
        return get_session_start_payload(existing_session_id)

    study_id = UUID(invite["study_id"])
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    stimuli = list_stimuli_for_study(study_id)
    if len(stimuli) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Study has no stimuli")

    participant_id = invite.get("participant_id") or token
    response = create_session(study_id, participant_id)
    with connect() as conn:
        conn.execute(
            update(invites_table)
            .where(invites_table.c.token == token)
            .values(used_session_id=str(response.session_id))
        )
    return response


class DemoStartRequest(BaseModel):
    paradigm: str = "adaptive"
    n_stimuli: int = 16


def _create_demo_study(paradigm: str, n_stimuli: int) -> UUID:
    study_id = uuid4()
    paradigm_value = Paradigm.ADAPTIVE if paradigm == "adaptive" else Paradigm.SETCOVER
    study_row = {
        "id": str(study_id),
        "owner_id": str(_DEMO_OWNER_ID),
        "name": f"Demo {paradigm_value.value} {n_stimuli}",
        "description": "Bundled hosted demo study",
        "paradigm": paradigm_value.value,
        "config_json": {
            "evidence_threshold": 0.35,
            "utility_exponent": 10.0,
            "min_subset_size": 4,
            "max_subset_size": 6,
            "use_inverse_mds": True,
            "batch_size": 6,
            "setcover_weight_mode": "max",
            "setcover_weight_alpha": 2.0,
        },
        "language": Language.EN.value,
        "instructions_json": [
            "Arrange the stimuli based on their perceived similarity.",
            "Use each token's center as its location; center-to-center distances become dissimilarities.",
            "Place similar token centers close together and different token centers far apart.",
            "Double-click a stimulus to play it.",
            "All stimuli must be inside the circle before you submit.",
        ],
        "created_at": utcnow_iso(),
    }
    stimulus_rows = [
        {
            "id": str(uuid4()),
            "study_id": str(study_id),
            "ordinal": ordinal,
            "filename": f"Stimulus {ordinal + 1}",
            "media_type": MediaType.VIDEO.value,
            "media_url": None,
            "thumbnail_url": None,
            "duration_seconds": 3.0,
        }
        for ordinal in range(n_stimuli)
    ]
    with connect() as conn:
        conn.execute(studies_table.insert().values(**study_row))
        if stimulus_rows:
            conn.execute(stimuli_table.insert(), stimulus_rows)
    return study_id


@router.post(
    "/public/demo/start",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_demo_session(req: DemoStartRequest) -> SessionStartResponse:
    if req.paradigm not in {"adaptive", "setcover"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported demo paradigm")
    if req.n_stimuli < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Demo requires at least two stimuli")
    study_id = _create_demo_study(req.paradigm, req.n_stimuli)
    participant_id = f"demo_user_{uuid4().hex[:8]}"
    return create_session(study_id, participant_id)


def get_invites_db():
    with connect(readonly=True) as conn:
        rows = fetch_all(conn, select(invites_table))
    return {row["token"]: row for row in rows}
