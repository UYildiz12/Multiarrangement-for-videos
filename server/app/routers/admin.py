"""
Admin endpoints protected by a shared secret.
"""

from typing import List, Optional
from uuid import UUID
import os

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.routers.studies import get_studies_db, get_stimuli_db
from app.routers.sessions import get_sessions_db, get_trials_db

router = APIRouter(tags=["admin"])


def _require_admin(x_admin_secret: Optional[str] = Header(default=None, alias="x-admin-secret")):
    secret = os.getenv("ADMIN_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_SECRET not configured",
        )
    if x_admin_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin secret",
        )
    return True


@router.get("/admin/studies", dependencies=[Depends(_require_admin)])
async def list_studies():
    studies_db = get_studies_db()
    stimuli_db = get_stimuli_db()
    out = []
    for study in studies_db.values():
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


@router.get("/admin/studies/{study_id}/sessions", dependencies=[Depends(_require_admin)])
async def list_sessions(study_id: UUID):
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


@router.get("/admin/sessions/{session_id}/trials", dependencies=[Depends(_require_admin)])
async def list_trials(session_id: UUID):
    trials_db = get_trials_db()
    if session_id not in trials_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return trials_db.get(session_id, [])


@router.delete("/admin/sessions/{session_id}", dependencies=[Depends(_require_admin)])
async def delete_session(session_id: UUID):
    """Delete a session and all its trials."""
    sessions_db = get_sessions_db()
    trials_db = get_trials_db()
    
    if session_id not in sessions_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    
    del sessions_db[session_id]
    if session_id in trials_db:
        del trials_db[session_id]
    
    return {"status": "deleted", "session_id": str(session_id)}


@router.delete("/admin/studies/{study_id}", dependencies=[Depends(_require_admin)])
async def delete_study(study_id: UUID):
    """Delete a study, all its stimuli, and all related sessions."""
    studies_db = get_studies_db()
    stimuli_db = get_stimuli_db()
    sessions_db = get_sessions_db()
    trials_db = get_trials_db()
    
    if study_id not in studies_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    
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

