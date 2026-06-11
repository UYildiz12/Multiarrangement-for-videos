"""
Results export endpoints backed by durable storage.
"""

from __future__ import annotations

import csv
import io
import json
from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from app.routers.experimenter import get_optional_owner, get_required_owner
from app.routers.sessions import get_session_record, get_trials_for_session, list_sessions_for_study
from app.routers.studies import get_study, list_stimuli_for_study
from app.schemas import ExportFormat, ResultsResponse

router = APIRouter(tags=["results"])


def schedule_diagnostics(n_items: int, batches: list[list[int]] | None) -> dict[str, object] | None:
    """Summarize the evidence structure of a fixed schedule for experimenters.

    Reports pair-concurrence balance (lambda) and item-use spread so the
    experimenter can see how evenly the schedule samples stimulus pairs.
    """
    if not batches or n_items < 2:
        return None
    try:
        from coverlib.balanced import coverage_histogram, normalized_balance_metrics
    except Exception:
        return None
    batch_sizes = sorted({len(batch) for batch in batches})
    k = max(batch_sizes)
    metrics = normalized_balance_metrics(n_items, k, batches)
    histogram = coverage_histogram(n_items, batches)
    item_counts: dict[int, int] = {}
    for batch in batches:
        for item in batch:
            item_counts[int(item)] = item_counts.get(int(item), 0) + 1
    uses = [item_counts.get(i, 0) for i in range(n_items)]
    return {
        "n_trials": len(batches),
        "batch_sizes": batch_sizes,
        "complete_pair_coverage": metrics.complete,
        "lambda_max": metrics.lambda_max,
        "ideal_lambda_max": metrics.ideal_lambda_max,
        "lambda_max_ratio": round(metrics.lambda_max_ratio, 4),
        "normalized_pair_sumsq_excess": round(metrics.normalized_pair_sumsq_excess, 6),
        "pair_coverage_histogram": {str(count): freq for count, freq in sorted(histogram.items())},
        "item_use_min": min(uses),
        "item_use_max": max(uses),
    }


def _scale_rdm_for_output(D: np.ndarray, paradigm: str) -> tuple[list[list[float]], list[list[float]], dict[str, object]]:
    raw = np.asarray(D, dtype=float)
    raw = np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0)
    raw = (raw + raw.T) / 2.0
    np.fill_diagonal(raw, 0.0)

    if raw.size == 0:
        return [], [], {
            "method": "none",
            "divisor": 1.0,
            "raw_units": "none",
            "description": "No RDM was available.",
        }

    if str(paradigm) == "pairwise":
        scaled = np.clip(raw, 0.0, 1.0)
        np.fill_diagonal(scaled, 0.0)
        return scaled.tolist(), raw.tolist(), {
            "method": "absolute_0_1",
            "divisor": 1.0,
            "raw_units": "rating-derived dissimilarity",
            "description": "Pairwise ratings are already encoded as 0..1 dissimilarities.",
        }

    iu = np.triu_indices_from(raw, k=1)
    finite = raw[iu][np.isfinite(raw[iu])] if iu[0].size else np.array([], dtype=float)
    divisor = float(np.max(finite)) if finite.size else 0.0
    if divisor > 1e-12:
        scaled = raw / divisor
    else:
        divisor = 1.0
        scaled = np.zeros_like(raw)
    scaled = np.clip(scaled, 0.0, 1.0)
    np.fill_diagonal(scaled, 0.0)
    return scaled.tolist(), raw.tolist(), {
        "method": "max_offdiag_0_1",
        "divisor": divisor,
        "raw_units": "reconstructed center-to-center Euclidean dissimilarity",
        "description": "Arrangement RDM divided by its maximum finite off-diagonal value; ratios and rank order are preserved.",
    }


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
        rdm_raw = None
        rdm_scale = {
            "method": "none",
            "divisor": 1.0,
            "raw_units": "none",
            "description": "No RDM was available.",
        }
        evidence = []
        evidence_raw = None
        evidence_normalized = None
    else:
        rdm, rdm_raw, rdm_scale = _scale_rdm_for_output(D, study["paradigm"].value)
        evidence_raw = W_raw.tolist() if W_raw is not None else None
        evidence_normalized = W_sched.tolist() if W_sched is not None else None
        evidence = evidence_normalized or evidence_raw or []

    labels = _labels_for_study(session["study_id"])
    return ResultsResponse(
        rdm=rdm,
        rdm_raw=rdm_raw,
        rdm_scale=rdm_scale,
        evidence=evidence,
        evidence_raw=evidence_raw,
        evidence_normalized=evidence_normalized,
        n_trials=len(trials),
        labels=labels,
        schedule_diagnostics=schedule_diagnostics(len(labels), session.get("batches")),
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
        if D is None:
            rdm = None
            rdm_raw = None
            rdm_scale = None
        else:
            rdm, rdm_raw, rdm_scale = _scale_rdm_for_output(D, study["paradigm"].value)
        export_data["sessions"].append(
            {
                "id": str(session["id"]),
                "participant_id": session["participant_id"],
                "status": session["status"].value,
                "started_at": session["started_at"].isoformat() if session.get("started_at") else None,
                "completed_at": session["completed_at"].isoformat() if session.get("completed_at") else None,
                "n_trials": len(trials),
                "rdm": rdm,
                "rdm_raw": rdm_raw,
                "rdm_scale": rdm_scale,
                "evidence_raw": W_raw.tolist() if W_raw is not None else None,
                "evidence_normalized": W_sched.tolist() if W_sched is not None else None,
                "schedule_diagnostics": schedule_diagnostics(len(stimuli), session.get("batches")),
                "trials": [
                    {
                        "id": str(trial["id"]),
                        "trial_index": trial["trial_index"],
                        "subset_indices": trial["subset_indices"],
                        "positions": trial["positions"],
                        "rating": trial.get("rating"),
                        "duration_seconds": trial["duration_seconds"],
                        "arena_size": trial.get("arena_size"),
                        "movement_trace": trial.get("movement_trace"),
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
                "arena_size",
                "started_at",
                "completed_at",
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
                        trial.get("arena_size"),
                        trial["started_at"],
                        trial["completed_at"],
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
