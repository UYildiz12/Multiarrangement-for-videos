"""
Admin endpoints protected by experimenter keys.

If the caller provides an ``x-experimenter-key`` header the derived owner_id
is used to filter results. For backwards-compatibility the legacy
``ADMIN_SECRET`` env-var still works as a *super-admin* passthrough.
In local development, ``LOCAL_DEV_BYPASS_AUTH=1`` allows keyless access.
"""

from typing import List, Optional
from uuid import UUID
import os

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.routers.studies import get_studies_db, get_stimuli_db
from app.routers.sessions import get_sessions_db, get_trials_db
from app.routers.experimenter import (
    get_optional_owner,
    owner_id_from_key,
    is_local_dev_bypass_auth_enabled,
    local_dev_owner_id,
    is_valid_signed_key,
)

router = APIRouter(tags=["admin"])


def _resolve_owner(
    x_admin_secret: Optional[str] = Header(default=None, alias="x-admin-secret"),
    x_experimenter_key: Optional[str] = Header(default=None, alias="x-experimenter-key"),
) -> Optional[UUID]:
    """Return an owner_id for filtering or None (super-admin = see all).

    Priority:
      1. x-experimenter-key → derive owner_id and filter
      2. x-admin-secret matching ADMIN_SECRET → super-admin (no filter)
      3. LOCAL_DEV_BYPASS_AUTH=1 → local-dev owner
      4. Either header present → 401
      5. Neither header → 401
    """
    # Experimenter key takes priority
    if x_experimenter_key and x_experimenter_key.strip():
        if not is_valid_signed_key(x_experimenter_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid experimenter key",
            )
        return owner_id_from_key(x_experimenter_key)

    # Legacy super-admin
    admin_secret = os.getenv("ADMIN_SECRET")
    if admin_secret and x_admin_secret == admin_secret:
        return None  # None = no filter = super-admin

    # Allow x-admin-secret to also be treated as experimenter key
    if x_admin_secret and x_admin_secret.strip():
        if not is_valid_signed_key(x_admin_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid experimenter key",
            )
        return owner_id_from_key(x_admin_secret)

    if is_local_dev_bypass_auth_enabled():
        return local_dev_owner_id()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Provide an x-experimenter-key header",
    )


@router.get("/admin/studies")
async def list_studies(owner_id: Optional[UUID] = Depends(_resolve_owner)):
    studies_db = get_studies_db()
    stimuli_db = get_stimuli_db()
    out = []
    for study in studies_db.values():
        if owner_id is not None and study.get("owner_id") != owner_id:
            continue
        out.append({
            "id": study["id"],
            "name": study["name"],
            "description": study.get("description"),
            "paradigm": study["paradigm"].value,
            "language": study["language"].value,
            "created_at": study["created_at"],
            "n_stimuli": len(stimuli_db.get(study["id"], [])),
        })
    return out


@router.get("/admin/studies/{study_id}/sessions")
async def list_sessions(study_id: UUID, owner_id: Optional[UUID] = Depends(_resolve_owner)):
    # Verify ownership
    studies_db = get_studies_db()
    if study_id in studies_db:
        study = studies_db[study_id]
        if owner_id is not None and study.get("owner_id") != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")
    sessions_db = get_sessions_db()
    trials_db = get_trials_db()
    out = []
    for s in sessions_db.values():
        if s["study_id"] != study_id:
            continue
        out.append({
            "id": s["id"],
            "participant_id": s["participant_id"],
            "status": s["status"].value,
            "current_trial_index": s["current_trial_index"],
            "started_at": s["started_at"],
            "completed_at": s.get("completed_at"),
            "n_trials": len(trials_db.get(s["id"], [])),
        })
    return out


@router.get("/admin/sessions/{session_id}/trials")
async def list_trials(session_id: UUID, owner_id: Optional[UUID] = Depends(_resolve_owner)):
    sessions_db = get_sessions_db()
    trials_db = get_trials_db()
    if session_id not in sessions_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    # Verify ownership (unless super-admin)
    if owner_id is not None:
        session = sessions_db[session_id]
        study = get_studies_db().get(session["study_id"])
        if study and study.get("owner_id") != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your session")
    return trials_db.get(session_id, [])


@router.delete("/admin/sessions/{session_id}")
async def delete_session(session_id: UUID, owner_id: Optional[UUID] = Depends(_resolve_owner)):
    """Delete a session and all its trials."""
    sessions_db = get_sessions_db()
    trials_db = get_trials_db()
    
    if session_id not in sessions_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    
    # Verify ownership (unless super-admin)
    if owner_id is not None:
        session = sessions_db[session_id]
        study = get_studies_db().get(session["study_id"])
        if study and study.get("owner_id") != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your session")
    
    del sessions_db[session_id]
    if session_id in trials_db:
        del trials_db[session_id]
    
    return {"status": "deleted", "session_id": str(session_id)}


@router.delete("/admin/studies/{study_id}")
async def delete_study(study_id: UUID, owner_id: Optional[UUID] = Depends(_resolve_owner)):
    """Delete a study, all its stimuli, and all related sessions."""
    studies_db = get_studies_db()
    stimuli_db = get_stimuli_db()
    sessions_db = get_sessions_db()
    trials_db = get_trials_db()
    
    if study_id not in studies_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    
    # Verify ownership (unless super-admin)
    if owner_id is not None:
        study = studies_db[study_id]
        if study.get("owner_id") != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")
    
    # Delete all sessions for this study
    sessions_to_delete = [sid for sid, s in sessions_db.items() if s["study_id"] == study_id]
    for sid in sessions_to_delete:
        del sessions_db[sid]
        if sid in trials_db:
            del trials_db[sid]
    
    # Delete stimuli
    if study_id in stimuli_db:
        del stimuli_db[study_id]
    
    # Delete study
    del studies_db[study_id]
    
    return {"status": "deleted", "study_id": str(study_id), "sessions_deleted": len(sessions_to_delete)}
