"""
Results export endpoints backed by durable storage.
"""

from __future__ import annotations

import csv
import io
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from app.routers.experimenter import get_optional_owner, get_required_owner
from app.routers.sessions import get_session_record, get_trials_for_session, list_sessions_for_study
from app.routers.studies import get_study, list_stimuli_for_study
from app.schemas import ExportFormat, ResultsResponse

router = APIRouter(tags=["results"])


def _labels_for_study(study_id: UUID | str) -> list[str]:
    stimuli = list_stimuli_for_study(study_id)
    return [stimulus.get("filename", f"stim_{index}") for index, stimulus in enumerate(stimuli)]


@router.get("/sessions/{session_id}/results", response_model=ResultsResponse)
async def get_session_results(session_id: UUID, owner_id: UUID | None = Depends(get_optional_owner)) -> ResultsResponse:
    session = get_session_record(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    study = get_study(session["study_id"])
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if owner_id is not None and study["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    trials = get_trials_for_session(session_id)
    D = session.get("D")
    W_raw = session.get("W_raw")
    W_sched = session.get("W_sched")

    if D is None:
        rdm = []
        evidence = []
        evidence_raw = None
        evidence_normalized = None
    else:
        rdm = D.tolist()
        evidence_raw = W_raw.tolist() if W_raw is not None else None
        evidence_normalized = W_sched.tolist() if W_sched is not None else None
        evidence = evidence_normalized or evidence_raw or []

    return ResultsResponse(
        rdm=rdm,
        evidence=evidence,
        evidence_raw=evidence_raw,
        evidence_normalized=evidence_normalized,
        n_trials=len(trials),
        labels=_labels_for_study(session["study_id"]),
    )


@router.get("/studies/{study_id}/export")
async def export_study_results(
    study_id: UUID,
    format: ExportFormat = Query(default=ExportFormat.JSON),
    owner_id: UUID = Depends(get_required_owner),
):
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if study["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    stimuli = list_stimuli_for_study(study_id)
    study_sessions = list_sessions_for_study(study_id)

    export_data = {
        "study": {
            "id": str(study["id"]),
            "name": study["name"],
            "paradigm": study["paradigm"].value,
            "config": study["config"],
        },
        "stimuli": [
            {
                "ordinal": stimulus["ordinal"],
                "filename": stimulus["filename"],
                "media_type": stimulus["media_type"].value,
                "media_url": stimulus.get("media_url"),
                "thumbnail_url": stimulus.get("thumbnail_url"),
                "media_storage_path": stimulus.get("media_storage_path"),
                "thumbnail_storage_path": stimulus.get("thumbnail_storage_path"),
                "duration_seconds": stimulus.get("duration_seconds"),
            }
            for stimulus in stimuli
        ],
        "sessions": [],
    }

    for session in study_sessions:
        trials = get_trials_for_session(session["id"])
        D = session.get("D")
        W_raw = session.get("W_raw")
        W_sched = session.get("W_sched")
        export_data["sessions"].append(
            {
                "id": str(session["id"]),
                "participant_id": session["participant_id"],
                "status": session["status"].value,
                "started_at": session["started_at"].isoformat() if session.get("started_at") else None,
                "completed_at": session["completed_at"].isoformat() if session.get("completed_at") else None,
                "n_trials": len(trials),
                "rdm": D.tolist() if D is not None else None,
                "evidence_raw": W_raw.tolist() if W_raw is not None else None,
                "evidence_normalized": W_sched.tolist() if W_sched is not None else None,
                "trials": [
                    {
                        "id": str(trial["id"]),
                        "trial_index": trial["trial_index"],
                        "subset_indices": trial["subset_indices"],
                        "positions": trial["positions"],
                        "rating": trial.get("rating"),
                        "duration_seconds": trial["duration_seconds"],
                        "started_at": trial["started_at"].isoformat() if trial.get("started_at") else None,
                        "completed_at": trial["completed_at"].isoformat() if trial.get("completed_at") else None,
                    }
                    for trial in trials
                ],
            }
        )

    if format == ExportFormat.JSON:
        return JSONResponse(content=jsonable_encoder(export_data))

    if format == ExportFormat.CSV:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "session_id",
                "participant_id",
                "status",
                "trial_index",
                "subset_indices",
                "rating",
                "duration_seconds",
                "positions",
            ]
        )
        for session_data in export_data["sessions"]:
            for trial in session_data["trials"]:
                writer.writerow(
                    [
                        session_data["id"],
                        session_data["participant_id"],
                        session_data["status"],
                        trial["trial_index"],
                        json.dumps(trial["subset_indices"]),
                        trial["rating"],
                        trial["duration_seconds"],
                        json.dumps(trial["positions"]),
                    ]
                )
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=study_{study_id}_results.csv"},
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Format {format} is not implemented for hosted export",
    )
