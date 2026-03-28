"""
Admin endpoints protected by experimenter keys.
"""

from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete

from app.routers.experimenter import (
    is_local_dev_bypass_auth_enabled,
    is_valid_signed_key,
    local_dev_owner_id,
    owner_id_from_key,
)
from app.routers.sessions import delete_session_record, get_session_record, get_trials_for_session, list_sessions_for_study
from app.routers.studies import get_study, get_studies_db, list_stimuli_for_study
from app.storage import connect, studies_table

router = APIRouter(tags=["admin"])


def _resolve_owner(
    x_admin_secret: str | None = Header(default=None, alias="x-admin-secret"),
    x_experimenter_key: str | None = Header(default=None, alias="x-experimenter-key"),
) -> UUID | None:
    if x_experimenter_key and x_experimenter_key.strip():
        if not is_valid_signed_key(x_experimenter_key):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid experimenter key")
        return owner_id_from_key(x_experimenter_key)

    admin_secret = os.getenv("ADMIN_SECRET")
    if admin_secret and x_admin_secret == admin_secret:
        return None

    if x_admin_secret and x_admin_secret.strip():
        if not is_valid_signed_key(x_admin_secret):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid experimenter key")
        return owner_id_from_key(x_admin_secret)

    if is_local_dev_bypass_auth_enabled():
        return local_dev_owner_id()

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Provide an x-experimenter-key header")


@router.get("/admin/studies")
async def list_studies(owner_id: UUID | None = Depends(_resolve_owner)):
    studies = []
    for study in get_studies_db().values():
        if owner_id is not None and study["owner_id"] != owner_id:
            continue
        studies.append(
            {
                "id": study["id"],
                "name": study["name"],
                "description": study.get("description"),
                "paradigm": study["paradigm"].value,
                "language": study["language"].value,
                "created_at": study["created_at"],
                "n_stimuli": len(list_stimuli_for_study(study["id"])),
            }
        )
    return jsonable_encoder(studies)


@router.get("/admin/studies/{study_id}/sessions")
async def list_sessions(study_id: UUID, owner_id: UUID | None = Depends(_resolve_owner)):
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if owner_id is not None and study["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    sessions = []
    for session in list_sessions_for_study(study_id):
        sessions.append(
            {
                "id": session["id"],
                "participant_id": session["participant_id"],
                "status": session["status"].value,
                "current_trial_index": session["current_trial_index"],
                "started_at": session["started_at"],
                "completed_at": session.get("completed_at"),
                "n_trials": len(get_trials_for_session(session["id"])),
            }
        )
    return jsonable_encoder(sessions)


@router.get("/admin/sessions/{session_id}/trials")
async def list_trials(session_id: UUID, owner_id: UUID | None = Depends(_resolve_owner)):
    session = get_session_record(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if owner_id is not None:
        study = get_study(session["study_id"])
        if study is None or study["owner_id"] != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your session")
    return jsonable_encoder(get_trials_for_session(session_id))


@router.delete("/admin/sessions/{session_id}")
async def delete_session(session_id: UUID, owner_id: UUID | None = Depends(_resolve_owner)):
    session = get_session_record(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if owner_id is not None:
        study = get_study(session["study_id"])
        if study is None or study["owner_id"] != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your session")
    delete_session_record(session_id)
    return {"status": "deleted", "session_id": str(session_id)}


@router.delete("/admin/studies/{study_id}")
async def delete_study(study_id: UUID, owner_id: UUID | None = Depends(_resolve_owner)):
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if owner_id is not None and study["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    session_count = len(list_sessions_for_study(study_id))
    with connect() as conn:
        conn.execute(delete(studies_table).where(studies_table.c.id == str(study_id)))
    return {"status": "deleted", "study_id": str(study_id), "sessions_deleted": session_count}
