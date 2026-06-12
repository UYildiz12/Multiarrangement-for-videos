"""
Session and trial management endpoints backed by durable storage.
"""

from __future__ import annotations

import itertools
import random
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import numpy as np
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.engine import Connection

from app.routers.studies import get_study, list_stimuli_for_study
from app.schemas import (
    NextTrialResponse,
    Paradigm,
    SessionCreate,
    SessionResponse,
    SessionStartResponse,
    SessionStatus,
    StimulusResponse,
    TrialResponse,
    TrialSubmit,
)
from app.state import load_session_state, serialize_session_state
from app.storage import (
    connect,
    fetch_all,
    fetch_one,
    ordered_select,
    sessions_table,
    trials_table,
    utcnow_iso,
)
from ma_core import (
    TrialArrangement,
    check_stopping_criterion,
    compute_evidence_matrix,
    estimate_rdm_weighted_average,
    fuse_setcover,
    generate_batches,
    refine_rdm_inverse_mds,
    select_next_subset_lift_weakest,
)

router = APIRouter(tags=["sessions"])

WEB_ARENA_PADDING = 20.0


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _session_base_from_row(row: dict[str, Any]) -> dict[str, Any]:
    base = {
        "id": UUID(row["id"]),
        "study_id": UUID(row["study_id"]),
        "participant_id": row["participant_id"],
        "status": SessionStatus(row["status"]),
        "current_trial_index": int(row["current_trial_index"]),
        "started_at": _parse_dt(row["started_at"]),
        "completed_at": _parse_dt(row.get("completed_at")),
    }
    loaded = load_session_state(base, row.get("state_json") or {})
    loaded.setdefault("batches", [])
    loaded.setdefault("pairs", [])
    loaded.setdefault("trial_arrangements", [])
    loaded.setdefault("pairwise_ratings", {})
    return loaded


def _trial_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": UUID(row["id"]),
        "session_id": UUID(row["session_id"]),
        "trial_index": int(row["trial_index"]),
        "subset_indices": [int(idx) for idx in (row.get("subset_indices_json") or [])],
        "positions": row.get("positions_json"),
        "rating": row.get("rating"),
        "duration_seconds": float(row["duration_seconds"]),
        "arena_size": float(row["arena_size"]) if row.get("arena_size") is not None else None,
        "movement_trace": row.get("movement_trace_json"),
        "started_at": _parse_dt(row["started_at"]),
        "completed_at": _parse_dt(row.get("completed_at")),
    }


def _session_started_at_iso(session: dict[str, Any]) -> str:
    started_at = session.get("started_at")
    if isinstance(started_at, datetime):
        return started_at.astimezone(timezone.utc).isoformat()
    return str(started_at or utcnow_iso())


def _session_completed_at_iso(session: dict[str, Any]) -> str | None:
    completed_at = session.get("completed_at")
    if completed_at is None:
        return None
    if isinstance(completed_at, datetime):
        return completed_at.astimezone(timezone.utc).isoformat()
    return str(completed_at)


def _save_session(session: dict[str, Any], conn: Connection | None = None) -> None:
    values = {
        "status": session["status"].value if isinstance(session["status"], SessionStatus) else str(session["status"]),
        "current_trial_index": int(session.get("current_trial_index", 0)),
        "started_at": _session_started_at_iso(session),
        "completed_at": _session_completed_at_iso(session),
        "state_json": serialize_session_state(session),
    }
    statement = (
        update(sessions_table)
        .where(sessions_table.c.id == str(session["id"]))
        .values(**values)
    )
    if conn is not None:
        conn.execute(statement)
    else:
        with connect() as managed:
            managed.execute(statement)


def _insert_trial(trial_row: dict[str, Any], conn: Connection | None = None) -> None:
    if conn is not None:
        conn.execute(trials_table.insert().values(**trial_row))
    else:
        with connect() as managed:
            managed.execute(trials_table.insert().values(**trial_row))


def _get_session_row(session_id: UUID | str, conn: Connection | None = None) -> dict[str, Any] | None:
    statement = select(sessions_table).where(sessions_table.c.id == str(session_id))
    if conn is not None:
        return fetch_one(conn, statement)
    with connect(readonly=True) as managed:
        return fetch_one(managed, statement)


def get_session_record(session_id: UUID | str) -> dict[str, Any] | None:
    row = _get_session_row(session_id)
    if row is None:
        return None
    return _session_base_from_row(row)


def get_trials_for_session(session_id: UUID | str) -> list[dict[str, Any]]:
    with connect(readonly=True) as conn:
        rows = fetch_all(
            conn,
            ordered_select(trials_table, trials_table.c.trial_index).where(
                trials_table.c.session_id == str(session_id)
            ),
        )
    return [_trial_from_row(row) for row in rows]


def _get_trial_for_index(session_id: UUID | str, trial_index: int) -> dict[str, Any] | None:
    with connect(readonly=True) as conn:
        row = fetch_one(
            conn,
            select(trials_table).where(
                trials_table.c.session_id == str(session_id),
                trials_table.c.trial_index == int(trial_index),
            ),
        )
    return _trial_from_row(row) if row else None


def _normalize_positions_payload(positions: dict[str, Any] | None) -> dict[str, list[float]] | None:
    if positions is None:
        return None
    normalized: dict[str, list[float]] = {}
    for key, value in positions.items():
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            x, y = value[0], value[1]
        else:
            x, y = value.x, value.y
        normalized[str(key)] = [float(x), float(y)]
    return normalized


_MAX_TRACE_SAMPLES = 50_000


def _validated_movement_trace(trace: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate an optional token-movement recording before persisting it."""
    if trace is None:
        return None
    samples = trace.get("samples") if isinstance(trace, dict) else None
    if not isinstance(samples, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="movement_trace must be an object with a 'samples' list",
        )
    if len(samples) > _MAX_TRACE_SAMPLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"movement_trace exceeds the {_MAX_TRACE_SAMPLES}-sample limit",
        )
    return trace


def _arena_geometry_from_size(arena_size: float | None) -> tuple[tuple[float, float] | None, float | None]:
    """Return the web arena center/radius used for scale-invariant RDM distances."""
    if arena_size is None:
        return None, None
    size = float(arena_size)
    if not np.isfinite(size) or size <= 0:
        return None, None
    center = (size / 2.0, size / 2.0)
    radius = max(1.0, size / 2.0 - WEB_ARENA_PADDING)
    return center, radius


def _duplicate_trial_response(
    session_id: UUID,
    trial: TrialSubmit,
    session: dict[str, Any],
    study: dict[str, Any],
    n_stimuli: int,
    positions_json: dict[str, list[float]] | None,
) -> TrialResponse | None:
    existing = _get_trial_for_index(session_id, trial.trial_index)
    if existing is None:
        return None
    if [int(idx) for idx in trial.subset_indices] != existing["subset_indices"]:
        return None
    rating = int(trial.rating) if trial.rating is not None else None
    if rating != existing["rating"]:
        return None
    if _normalize_positions_payload(existing["positions"]) != positions_json:
        return None

    next_trial, session_changed = _build_next_trial_response(session, study, n_stimuli)
    if session_changed:
        _save_session(session)
    return TrialResponse(
        id=existing["id"],
        trial_index=existing["trial_index"],
        subset_indices=existing["subset_indices"],
        duration_seconds=existing["duration_seconds"],
        arena_size=existing.get("arena_size"),
        started_at=existing["started_at"],
        completed_at=existing["completed_at"],
        next_trial=next_trial,
    )


def list_sessions_for_study(study_id: UUID | str) -> list[dict[str, Any]]:
    with connect(readonly=True) as conn:
        rows = fetch_all(
            conn,
            ordered_select(sessions_table, sessions_table.c.started_at).where(
                sessions_table.c.study_id == str(study_id)
            ),
        )
    return [_session_base_from_row(row) for row in rows]


def delete_session_record(session_id: UUID | str, conn: Connection | None = None) -> bool:
    statement = delete(sessions_table).where(sessions_table.c.id == str(session_id))
    if conn is not None:
        result = conn.execute(statement)
        return result.rowcount > 0
    with connect() as managed:
        result = managed.execute(statement)
        return result.rowcount > 0


def _time_limit_reached(session: dict[str, Any], study: dict[str, Any]) -> bool:
    minutes = study.get("config", {}).get("time_limit_minutes")
    if minutes is None:
        return False
    try:
        minutes = float(minutes)
    except Exception:
        return False
    if minutes <= 0:
        return False
    started_at = session.get("started_at")
    if not isinstance(started_at, datetime):
        return False
    return datetime.now(timezone.utc) >= (started_at + timedelta(minutes=minutes))


def _build_next_trial_response(
    session: dict[str, Any],
    study: dict[str, Any],
    n_stimuli: int,
) -> tuple[NextTrialResponse, bool]:
    trial_index = int(session["current_trial_index"])
    session_changed = False

    if _time_limit_reached(session, study):
        session["status"] = SessionStatus.COMPLETED
        session["completed_at"] = datetime.now(timezone.utc)
        session_changed = True
        return NextTrialResponse(trial_index=trial_index, subset_indices=[], is_final=True), session_changed

    if study["paradigm"] == Paradigm.SETCOVER:
        batches = session.get("batches", [])
        if trial_index >= len(batches):
            return NextTrialResponse(trial_index=trial_index, subset_indices=[], is_final=True), session_changed
        return NextTrialResponse(
            trial_index=trial_index,
            subset_indices=[int(idx) for idx in batches[trial_index]],
            is_final=False,
        ), session_changed

    if study["paradigm"] == Paradigm.PAIRWISE:
        pairs = session.get("pairs", [])
        if trial_index >= len(pairs):
            return NextTrialResponse(trial_index=trial_index, subset_indices=[], is_final=True), session_changed
        return NextTrialResponse(
            trial_index=trial_index,
            subset_indices=[int(idx) for idx in pairs[trial_index]],
            is_final=False,
        ), session_changed

    D = session.get("D")
    W = session.get("W_sched")
    if D is None or W is None or n_stimuli < 2:
        return NextTrialResponse(trial_index=trial_index, subset_indices=[], is_final=True), session_changed

    if trial_index == 0 and not session.get("trial_arrangements"):
        return NextTrialResponse(
            trial_index=trial_index,
            subset_indices=list(range(n_stimuli)),
            is_final=False,
        ), session_changed

    threshold = study["config"].get("evidence_threshold", 0.5)
    stop_on_utility = bool(study["config"].get("stop_on_utility", False))
    if stop_on_utility:
        utility_exponent = float(study["config"].get("utility_exponent", 10.0))
        upper = np.triu_indices(n_stimuli, 1)
        if upper[0].size > 0:
            utility_values = 1.0 - np.exp(-utility_exponent * W[upper])
            if float(np.min(utility_values)) >= float(threshold):
                return NextTrialResponse(trial_index=trial_index, subset_indices=[], is_final=True), session_changed
    elif check_stopping_criterion(W, threshold):
        return NextTrialResponse(trial_index=trial_index, subset_indices=[], is_final=True), session_changed

    config = study["config"]
    cold_start_trials = int(config.get("cold_start_require_unseen_trials", 0))
    require_unseen = cold_start_trials > 0 and trial_index < cold_start_trials
    subset = select_next_subset_lift_weakest(
        D,
        W,
        min_size=int(config.get("min_subset_size", 3)),
        max_size=config.get("max_subset_size"),
        utility_exponent=float(config.get("utility_exponent", 10.0)),
        time_cost_exponent=float(config.get("time_cost_exponent", 1.5)),
        durations=session.get("durations"),
        long_clip_mask=session.get("long_clip_mask"),
        recent=session.get("recent"),
        seen=session.get("seen"),
        last_subset=session.get("last_subset"),
        avoid_anchor_pair=session.get("last_anchor_pair"),
        inclusion_counts=session.get("inclusion_counts"),
        require_unseen=require_unseen,
        max_jaccard=config.get("max_jaccard"),
        overlap_penalty=float(config.get("overlap_penalty", 0.0)),
        recency_penalty=float(config.get("recency_penalty", 0.0)),
        unseen_boost=float(config.get("unseen_boost", 0.0)),
        stress_weight=float(config.get("stress_weight", 0.0)),
        duration_cost_weight=float(config.get("duration_cost_weight", 0.0)),
        target_time_seconds=config.get("target_time_seconds"),
        target_time_tolerance=float(config.get("target_time_tolerance", 0.05)),
        duration_cost_cap_per_item=config.get("duration_cost_cap_per_item"),
        min_long_clip_inclusion_rate=float(config.get("min_long_clip_inclusion_rate", 0.0)),
        long_clip_boost=float(config.get("long_clip_boost", 0.0)),
        trials_so_far=trial_index,
    )
    return NextTrialResponse(
        trial_index=trial_index,
        subset_indices=[int(idx) for idx in subset],
        is_final=False,
    ), session_changed


def _build_session_start_response(
    session: dict[str, Any],
    study: dict[str, Any],
    stimuli: list[dict[str, Any]],
) -> SessionStartResponse:
    return SessionStartResponse(
        session_id=session["id"],
        study_id=session["study_id"],
        paradigm=study["paradigm"],
        n_stimuli=len(stimuli),
        stimuli=[StimulusResponse(**stimulus) for stimulus in stimuli],
        config=study["config"],
    )


def _expected_arrangement_subset(
    session: dict[str, Any],
    study: dict[str, Any],
    n_stimuli: int,
) -> list[int]:
    trial_index = int(session["current_trial_index"])
    if study["paradigm"] == Paradigm.SETCOVER:
        batches = session.get("batches", [])
        if trial_index >= len(batches):
            return []
        return [int(idx) for idx in batches[trial_index]]

    next_trial, session_changed = _build_next_trial_response(session, study, n_stimuli)
    if session_changed:
        _save_session(session)
    return [int(idx) for idx in next_trial.subset_indices]


def get_session_start_payload(session_id: UUID | str) -> SessionStartResponse:
    session = get_session_record(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    study = get_study(session["study_id"])
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    stimuli = list_stimuli_for_study(session["study_id"])
    return _build_session_start_response(session, study, stimuli)


def _validate_and_sort_stimuli(study_id: UUID | str) -> list[dict[str, Any]]:
    stimuli = list_stimuli_for_study(study_id)
    if stimuli:
        ordinals = sorted({int(stimulus.get("ordinal", -1)) for stimulus in stimuli})
        expected = list(range(len(ordinals)))
        if ordinals != expected:
            missing = sorted(set(expected) - set(ordinals))
            extra = sorted(set(ordinals) - set(expected))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stimulus ordinals must be contiguous 0..{len(ordinals) - 1}. Missing={missing}, extra={extra}",
            )
        stimuli = sorted(stimuli, key=lambda stimulus: stimulus["ordinal"])
    return stimuli


# Set-cover schedules are deterministic per (study, size, config), so cache
# them: regenerating on every session start costs up to seconds per participant.
_SCHEDULE_CACHE: dict[tuple, list[list[int]]] = {}


def _get_or_create_schedule(
    study_id: UUID | str,
    n_stimuli: int,
    batch_size: int,
    *,
    flex: bool,
    algorithm: str,
    max_extra_fraction: float = 0.0,
) -> list[list[int]]:
    key = (str(study_id), n_stimuli, batch_size, flex, algorithm,
           round(max_extra_fraction, 3))
    cached = _SCHEDULE_CACHE.get(key)
    if cached is None:
        cached = generate_batches(
            n_stimuli,
            batch_size,
            seed=42,
            flex=flex,
            algorithm=algorithm,
            max_extra_fraction=max_extra_fraction,
        )
        _SCHEDULE_CACHE[key] = cached
    return [list(batch) for batch in cached]


def create_session(study_id: UUID, participant_id: str) -> SessionStartResponse:
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    stimuli = _validate_and_sort_stimuli(study_id)
    n_stimuli = len(stimuli)
    session_id = uuid4()

    batches = None
    if study["paradigm"] == Paradigm.SETCOVER and n_stimuli >= 2:
        batch_size = study["config"].get("batch_size", 6)
        flex = bool(study["config"].get("flex", False))
        setcover_algorithm = study["config"].get("setcover_algorithm", "balanced")
        # schedule_mode: "compact" keeps the minimum trial count;
        # "balanced" allows up to 20% more trials so a certified
        # low-concurrence schedule can be served from the cache
        schedule_mode = str(study["config"].get("schedule_mode", "compact"))
        extra_fraction = 0.20 if schedule_mode == "balanced" else 0.0
        effective_batch = min(batch_size, n_stimuli)
        batches = _get_or_create_schedule(
            study_id,
            n_stimuli,
            effective_batch,
            flex=flex,
            algorithm=str(setcover_algorithm),
            max_extra_fraction=extra_fraction,
        )

    seen = np.zeros((n_stimuli,), dtype=bool) if n_stimuli > 0 else None
    recent = np.zeros((n_stimuli,), dtype=float) if n_stimuli > 0 else None
    inclusion_counts = np.zeros((n_stimuli,), dtype=int) if n_stimuli > 0 else None
    durations = None
    if n_stimuli > 0:
        durations = np.zeros((n_stimuli,), dtype=float)
        for index, stimulus in enumerate(stimuli):
            duration = stimulus.get("duration_seconds")
            durations[index] = float(duration) if duration is not None else 0.0

    long_clip_mask = None
    long_clip_threshold_seconds = study["config"].get("long_clip_threshold_seconds")
    if durations is not None and long_clip_threshold_seconds is not None:
        try:
            long_clip_mask = durations >= float(long_clip_threshold_seconds)
        except Exception:
            long_clip_mask = None

    pairs = None
    if study["paradigm"] == Paradigm.PAIRWISE and n_stimuli >= 2:
        pairs = list(itertools.combinations(range(n_stimuli), 2))
        if study["config"].get("randomize_pairs", True):
            random.shuffle(pairs)

    started_at_iso = utcnow_iso()
    session = {
        "id": session_id,
        "study_id": study_id,
        "participant_id": participant_id,
        "status": SessionStatus.IN_PROGRESS,
        "current_trial_index": 0,
        "started_at": _parse_dt(started_at_iso),
        "completed_at": None,
        "batches": batches or [],
        "pairs": pairs or [],
        "D": np.zeros((n_stimuli, n_stimuli)) if n_stimuli > 0 else None,
        "W_raw": np.zeros((n_stimuli, n_stimuli)) if n_stimuli > 0 else None,
        "W_sched": np.zeros((n_stimuli, n_stimuli)) if study["paradigm"] == Paradigm.ADAPTIVE and n_stimuli > 0 else None,
        "trial_arrangements": [],
        "seen": seen,
        "recent": recent,
        "inclusion_counts": inclusion_counts,
        "durations": durations,
        "last_subset": None,
        "last_anchor_pair": None,
        "long_clip_mask": long_clip_mask,
        "pairwise_ratings": {},
    }

    payload = {
        "id": str(session_id),
        "study_id": str(study_id),
        "participant_id": participant_id,
        "status": SessionStatus.IN_PROGRESS.value,
        "current_trial_index": 0,
        "started_at": started_at_iso,
        "completed_at": None,
        "state_json": serialize_session_state(session),
    }
    with connect() as conn:
        conn.execute(sessions_table.insert().values(**payload))

    return _build_session_start_response(session, study, stimuli)


@router.post(
    "/studies/{study_id}/sessions",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_session(study_id: UUID, session: SessionCreate) -> SessionStartResponse:
    return create_session(study_id, session.participant_id)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: UUID) -> SessionResponse:
    session = get_session_record(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    study = get_study(session["study_id"])
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    return SessionResponse(
        id=session["id"],
        study_id=session["study_id"],
        participant_id=session["participant_id"],
        status=session["status"],
        paradigm=study["paradigm"],
        current_trial_index=session["current_trial_index"],
        started_at=session["started_at"],
        completed_at=session["completed_at"],
    )


@router.get("/sessions/{session_id}/next", response_model=NextTrialResponse)
async def get_next_trial(session_id: UUID) -> NextTrialResponse:
    session = get_session_record(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    study = get_study(session["study_id"])
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    n_stimuli = len(list_stimuli_for_study(session["study_id"]))
    next_trial, session_changed = _build_next_trial_response(session, study, n_stimuli)
    if session_changed:
        _save_session(session)
    return next_trial


@router.post("/sessions/{session_id}/trials", response_model=TrialResponse)
async def submit_trial(session_id: UUID, trial: TrialSubmit) -> TrialResponse:
    session = get_session_record(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session["status"] != SessionStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not active")

    study = get_study(session["study_id"])
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    stimuli = list_stimuli_for_study(session["study_id"])
    n_stimuli = len(stimuli)
    now = datetime.now(timezone.utc)
    trial_id = uuid4()

    if study["paradigm"] == Paradigm.PAIRWISE:
        pairs = session.get("pairs", [])
        if trial.trial_index != session["current_trial_index"]:
            duplicate = _duplicate_trial_response(
                session_id,
                trial,
                session,
                study,
                n_stimuli,
                positions_json=None,
            )
            if duplicate is not None:
                return duplicate
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trial index out of sequence")
        if len(trial.subset_indices) != 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pairwise trials must include exactly two indices")
        if trial.trial_index >= len(pairs):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trial index exceeds scheduled pairs")
        expected_pair = list(pairs[trial.trial_index])
        if list(trial.subset_indices) != expected_pair:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Submitted pair does not match scheduled pair")
        if trial.rating is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating is required for pairwise paradigm")

        trial_row = {
            "id": str(trial_id),
            "session_id": str(session_id),
            "trial_index": trial.trial_index,
            "subset_indices_json": [int(idx) for idx in trial.subset_indices],
            "positions_json": None,
            "rating": trial.rating,
            "duration_seconds": float(trial.duration_seconds),
            "arena_size": None,
            "movement_trace_json": None,
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
        }

        if n_stimuli >= 2:
            pairwise_ratings = dict(session.get("pairwise_ratings") or {})
            left, right = trial.subset_indices[0], trial.subset_indices[1]
            pair_key = (min(left, right), max(left, right))
            ratings = list(pairwise_ratings.get(pair_key, []))
            ratings.append(trial.rating)
            pairwise_ratings[pair_key] = ratings
            session["pairwise_ratings"] = pairwise_ratings

            D = np.ones((n_stimuli, n_stimuli)) * 0.5
            W = np.zeros((n_stimuli, n_stimuli))
            for (pi, pj), pair_ratings in pairwise_ratings.items():
                avg_rating = np.mean(pair_ratings)
                dissimilarity = (7 - avg_rating) / 6
                D[pi, pj] = dissimilarity
                D[pj, pi] = dissimilarity
                W[pi, pj] = len(pair_ratings)
                W[pj, pi] = len(pair_ratings)
            np.fill_diagonal(D, 0)
            session["D"] = D
            session["W_raw"] = W
            session["W_sched"] = None

        session["current_trial_index"] = trial.trial_index + 1
        next_trial, _ = _build_next_trial_response(session, study, n_stimuli)
        with connect() as conn:
            _insert_trial(trial_row, conn)
            _save_session(session, conn)
        return TrialResponse(
            id=trial_id,
            trial_index=trial.trial_index,
            subset_indices=[int(idx) for idx in trial.subset_indices],
            duration_seconds=trial.duration_seconds,
            arena_size=None,
            started_at=now,
            completed_at=now,
            next_trial=next_trial,
        )

    if trial.positions is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Positions are required for arrangement paradigms")

    movement_trace = _validated_movement_trace(trial.movement_trace)

    missing = [idx for idx in trial.subset_indices if str(idx) not in trial.positions]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing positions for indices: {missing}")

    positions_json = _normalize_positions_payload(trial.positions)
    if trial.trial_index != session["current_trial_index"]:
        duplicate = _duplicate_trial_response(
            session_id,
            trial,
            session,
            study,
            n_stimuli,
            positions_json=positions_json,
        )
        if duplicate is not None:
            return duplicate
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trial index out of sequence")

    expected_subset = _expected_arrangement_subset(session, study, n_stimuli)
    submitted_subset = [int(idx) for idx in trial.subset_indices]
    if submitted_subset != expected_subset:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Submitted subset does not match scheduled subset")

    trial_row = {
        "id": str(trial_id),
        "session_id": str(session_id),
        "trial_index": trial.trial_index,
        "subset_indices_json": [int(idx) for idx in trial.subset_indices],
        "positions_json": positions_json,
        "rating": None,
        "duration_seconds": float(trial.duration_seconds),
        "arena_size": float(trial.arena_size) if trial.arena_size is not None else None,
        "movement_trace_json": movement_trace,
        "started_at": now.isoformat(),
        "completed_at": now.isoformat(),
    }

    session["current_trial_index"] = trial.trial_index + 1
    positions_dict = {int(key): (value.x, value.y) for key, value in trial.positions.items()}
    arena_center, arena_radius = _arena_geometry_from_size(trial.arena_size)
    arrangement = TrialArrangement(
        subset=trial.subset_indices,
        positions=positions_dict,
        arena_center=arena_center,
        arena_radius=arena_radius,
    )
    session["trial_arrangements"] = list(session.get("trial_arrangements") or [])
    session["trial_arrangements"].append(arrangement)

    if session.get("seen") is not None and session.get("recent") is not None:
        selected = list(positions_dict.keys())
        session["seen"][selected] = True
        recency_decay = float(study["config"].get("recency_decay", 0.85))
        session["recent"] *= recency_decay
        session["recent"][selected] += 1.0
        if session.get("inclusion_counts") is not None:
            for idx in selected:
                if 0 <= idx < len(session["inclusion_counts"]):
                    session["inclusion_counts"][idx] += 1
        subset_for_tracking = [int(idx) for idx in trial.subset_indices]
        session["last_subset"] = subset_for_tracking
        if len(subset_for_tracking) >= 2:
            anchor_a, anchor_b = subset_for_tracking[0], subset_for_tracking[1]
            session["last_anchor_pair"] = (min(anchor_a, anchor_b), max(anchor_a, anchor_b))

    if n_stimuli >= 2:
        config = study["config"]
        robust_method = config.get("robust_method")
        robust_winsor_high = float(config.get("robust_winsor_high", 0.98))
        robust_huber_c = float(config.get("robust_huber_c", 0.9))

        if study["paradigm"] == Paradigm.SETCOVER:
            setcover_weight_mode = config.get("setcover_weight_mode", config.get("weight_mode", "max"))
            setcover_weight_alpha = float(config.get("setcover_weight_alpha", config.get("weight_alpha", 2.0)))
            use_inverse_mds = bool(config.get("use_inverse_mds", False))
            inverse_mds_max_iter = int(config.get("inverse_mds_max_iter", 15))
            inverse_mds_step_c = float(config.get("inverse_mds_step_c", 0.3))
            inverse_mds_tol = float(config.get("inverse_mds_tol", 1e-4))
            D, W_raw = fuse_setcover(
                n_stimuli,
                session["trial_arrangements"],
                weight_mode=str(setcover_weight_mode),
                alpha=setcover_weight_alpha,
                robust_method=robust_method,
                robust_winsor_high=robust_winsor_high,
                robust_huber_c=robust_huber_c,
                use_inverse_mds=use_inverse_mds,
                inverse_mds_max_iter=inverse_mds_max_iter,
                inverse_mds_step_c=inverse_mds_step_c,
                inverse_mds_tol=inverse_mds_tol,
            )
            session["D"] = D
            session["W_raw"] = W_raw
            session["W_sched"] = None
        else:
            evidence_weight_mode = config.get("evidence_weight_mode", "k2012")
            evidence_alpha = float(config.get("evidence_alpha", 2.0))
            # Off by default to match the desktop library and the published
            # recommendation: use the direct fused RDM as the primary output.
            use_inverse_mds = bool(config.get("use_inverse_mds", False))
            inverse_mds_max_iter = int(config.get("inverse_mds_max_iter", 15))
            inverse_mds_step_c = float(config.get("inverse_mds_step_c", 0.3))
            inverse_mds_tol = float(config.get("inverse_mds_tol", 1e-4))

            D, W_raw = estimate_rdm_weighted_average(
                n_stimuli,
                session["trial_arrangements"],
                alpha=evidence_alpha,
                robust_method=robust_method,
                robust_winsor_high=robust_winsor_high,
                robust_huber_c=robust_huber_c,
                weight_mode=str(evidence_weight_mode),
            )
            W_sched = compute_evidence_matrix(
                n_stimuli,
                session["trial_arrangements"],
                D_reference=D,
                weight_mode="max",
                alpha=evidence_alpha,
                robust_method=robust_method,
                robust_winsor_high=robust_winsor_high,
                robust_huber_c=robust_huber_c,
            )
            if use_inverse_mds:
                D = refine_rdm_inverse_mds(
                    D,
                    session["trial_arrangements"],
                    max_iter=inverse_mds_max_iter,
                    tol=inverse_mds_tol,
                    step_c=inverse_mds_step_c,
                )
            session["D"] = D
            session["W_raw"] = W_raw
            session["W_sched"] = W_sched

    next_trial, _ = _build_next_trial_response(session, study, n_stimuli)
    with connect() as conn:
        _insert_trial(trial_row, conn)
        _save_session(session, conn)

    return TrialResponse(
        id=trial_id,
        trial_index=trial.trial_index,
        subset_indices=[int(idx) for idx in trial.subset_indices],
        duration_seconds=trial.duration_seconds,
        arena_size=trial.arena_size,
        started_at=now,
        completed_at=now,
        next_trial=next_trial,
    )


@router.post("/sessions/{session_id}/complete", response_model=SessionResponse)
async def complete_session(session_id: UUID) -> SessionResponse:
    session = get_session_record(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    study = get_study(session["study_id"])
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    session["status"] = SessionStatus.COMPLETED
    session["completed_at"] = datetime.now(timezone.utc)
    _save_session(session)
    return SessionResponse(
        id=session["id"],
        study_id=session["study_id"],
        participant_id=session["participant_id"],
        status=session["status"],
        paradigm=study["paradigm"],
        current_trial_index=session["current_trial_index"],
        started_at=session["started_at"],
        completed_at=session["completed_at"],
    )


def get_sessions_db() -> dict[UUID, dict[str, Any]]:
    with connect(readonly=True) as conn:
        rows = fetch_all(conn, select(sessions_table))
    return {UUID(row["id"]): _session_base_from_row(row) for row in rows}


def get_trials_db() -> dict[UUID, list[dict[str, Any]]]:
    with connect(readonly=True) as conn:
        rows = fetch_all(conn, ordered_select(trials_table, trials_table.c.session_id, trials_table.c.trial_index))
    grouped: dict[UUID, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(UUID(row["session_id"]), []).append(_trial_from_row(row))
    return grouped
