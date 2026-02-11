"""
Results export endpoints.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.schemas import ResultsResponse, ExportFormat
from app.routers.sessions import get_sessions_db, get_trials_db
from app.routers.studies import get_studies_db, get_stimuli_db
from app.routers.experimenter import get_required_owner, get_optional_owner

router = APIRouter(tags=["results"])


@router.get("/sessions/{session_id}/results", response_model=ResultsResponse)
async def get_session_results(session_id: UUID, owner_id: Optional[UUID] = Depends(get_optional_owner)) -> ResultsResponse:
    """Get computed RDM and evidence for a session.

    When an experimenter key is provided, ownership is enforced.
    Without a key, results are returned for the participant who just completed.
    """
    sessions_db = get_sessions_db()
    stimuli_db = get_stimuli_db()
    
    if session_id not in sessions_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session = sessions_db[session_id]
    
    # If an experimenter key was provided, verify ownership
    if owner_id is not None:
        studies_db = get_studies_db()
        study = studies_db.get(session["study_id"])
        if study is None or study.get("owner_id") != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your study"
            )
    
    stimuli = stimuli_db.get(session["study_id"], [])
    trials = get_trials_db().get(session_id, [])
    
    D = session.get("D")
    W_raw = session.get("W_raw")
    W_sched = session.get("W_sched")
    
    if D is None:
        D_list = []
        W_list = []
        W_raw_list = []
        W_sched_list = []
    else:
        D_list = D.tolist()
        W_raw_list = W_raw.tolist() if W_raw is not None else []
        W_sched_list = W_sched.tolist() if W_sched is not None else []
        # Prefer normalized evidence if available
        W_list = W_sched_list if W_sched_list else W_raw_list
    
    labels = [s.get("filename", f"stim_{i}") for i, s in enumerate(stimuli)]
    
    return ResultsResponse(
        rdm=D_list,
        evidence=W_list,
        evidence_raw=W_raw_list if W_raw_list else None,
        evidence_normalized=W_sched_list if W_sched_list else None,
        n_trials=len(trials),
        labels=labels,
    )


@router.get("/studies/{study_id}/export")
async def export_study_results(
    study_id: UUID,
    format: ExportFormat = Query(default=ExportFormat.JSON),
    owner_id: UUID = Depends(get_required_owner),
):
    """Export all results from a study. Requires experimenter key."""
    import json
    
    studies_db = get_studies_db()
    sessions_db = get_sessions_db()
    trials_db = get_trials_db()
    stimuli_db = get_stimuli_db()
    
    if study_id not in studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    study = studies_db[study_id]
    if study.get("owner_id") != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your study"
        )
    stimuli = stimuli_db.get(study_id, [])
    
    # Collect all sessions for this study
    study_sessions = [
        s for s in sessions_db.values() 
        if s["study_id"] == study_id
    ]
    
    if format == ExportFormat.JSON:
        export_data = {
            "study": {
                "id": str(study["id"]),
                "name": study["name"],
                "paradigm": study["paradigm"].value,
                "config": study["config"],
            },
            "stimuli": [
                {"ordinal": i, "filename": s.get("filename", f"stim_{i}")}
                for i, s in enumerate(stimuli)
            ],
            "sessions": []
        }
        
        for session in study_sessions:
            session_id = session["id"]
            trials = trials_db.get(session_id, [])
            
            D = session.get("D")
            
            session_export = {
                "id": str(session_id),
                "participant_id": session["participant_id"],
                "status": session["status"].value,
                "n_trials": len(trials),
                "rdm": D.tolist() if D is not None else None,
                "trials": [
                    {
                        "index": t["trial_index"],
                        "subset": t["subset_indices"],
                        "positions": t["positions"],
                        "duration": t["duration_seconds"],
                    }
                    for t in trials
                ]
            }
            export_data["sessions"].append(session_export)
        
        return JSONResponse(content=export_data)
    
    elif format == ExportFormat.CSV:
        # Return CSV of trial data
        import io
        import csv
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "session_id", "participant_id", "trial_index", 
            "subset", "duration_seconds"
        ])
        
        for session in study_sessions:
            session_id = session["id"]
            trials = trials_db.get(session_id, [])
            
            for trial in trials:
                writer.writerow([
                    str(session_id),
                    session["participant_id"],
                    trial["trial_index"],
                    str(trial["subset_indices"]),
                    trial["duration_seconds"],
                ])
        
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=study_{study_id}_results.csv"}
        )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format {format} not yet implemented"
        )
