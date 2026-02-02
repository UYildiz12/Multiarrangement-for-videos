"""
Session and trial management endpoints.
"""

import itertools
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas import (
    SessionCreate,
    SessionResponse,
    SessionStartResponse,
    SessionStatus,
    NextTrialResponse,
    TrialSubmit,
    TrialResponse,
    StimulusResponse,
    Paradigm,
)
from app.routers.studies import get_studies_db, get_stimuli_db
from ma_core import (
    generate_batches,
    TrialArrangement,
    estimate_rdm_weighted_average,
    compute_evidence_matrix,
    select_next_subset_lift_weakest,
    check_stopping_criterion,
    fuse_setcover,
    refine_rdm_inverse_mds,
)
import numpy as np

router = APIRouter(tags=["sessions"])

# In-memory storage for development
_sessions_db: Dict[UUID, dict] = {}
_trials_db: Dict[UUID, List[dict]] = {}


def _time_limit_reached(session: dict, study: dict) -> bool:
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
    if not started_at:
        return False
    return datetime.utcnow() >= (started_at + timedelta(minutes=minutes))


@router.post(
    "/studies/{study_id}/sessions",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED
)
async def start_session(study_id: UUID, session: SessionCreate) -> SessionStartResponse:
    """Start a new experiment session."""
    return create_session(study_id, session.participant_id)


def create_session(study_id: UUID, participant_id: str) -> SessionStartResponse:
    """Internal helper to create a session for a study."""
    import uuid
    from datetime import datetime
    
    studies_db = get_studies_db()
    stimuli_db = get_stimuli_db()
    
    if study_id not in studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    study = studies_db[study_id]
    stimuli = stimuli_db.get(study_id, [])
    if stimuli:
        ordinals = sorted({int(s.get("ordinal", -1)) for s in stimuli})
        expected = list(range(len(ordinals)))
        if ordinals != expected:
            missing = sorted(set(expected) - set(ordinals))
            extra = sorted(set(ordinals) - set(expected))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stimulus ordinals must be contiguous 0..{len(ordinals)-1}. Missing={missing}, extra={extra}"
            )
        stimuli = sorted(stimuli, key=lambda s: s["ordinal"])
        stimuli_db[study_id] = stimuli
    n_stimuli = len(stimuli)
    
    session_id = uuid.uuid4()
    
    # Generate batches for set-cover paradigm
    batches = None
    if study["paradigm"] == Paradigm.SETCOVER:
        batch_size = study["config"].get("batch_size", 6)
        flex = bool(study["config"].get("flex", False))
        setcover_algorithm = study["config"].get("setcover_algorithm", "hybrid")
        if n_stimuli >= 2:
            effective_batch = min(batch_size, n_stimuli)
            batches = generate_batches(
                n_stimuli,
                effective_batch,
                seed=42,
                flex=flex,
                algorithm=str(setcover_algorithm),
            )

    # Initialize adaptive policy state
    seen = np.zeros((n_stimuli,), dtype=bool) if n_stimuli > 0 else None
    recent = np.zeros((n_stimuli,), dtype=float) if n_stimuli > 0 else None
    inclusion_counts = np.zeros((n_stimuli,), dtype=int) if n_stimuli > 0 else None
    last_subset = None
    last_anchor_pair = None

    # Optional duration tracking for time-aware costs
    durations = None
    if n_stimuli > 0:
        durations = np.zeros((n_stimuli,), dtype=float)
        for i, stim in enumerate(stimuli):
            dur = stim.get("duration_seconds")
            durations[i] = float(dur) if dur is not None else 0.0

    # Long-clip mask if configured
    long_clip_mask = None
    long_clip_threshold_seconds = study["config"].get("long_clip_threshold_seconds")
    if durations is not None and long_clip_threshold_seconds is not None:
        try:
            long_clip_mask = durations >= float(long_clip_threshold_seconds)
        except Exception:
            long_clip_mask = None

    # Generate pairs for pairwise paradigm (full coverage, no repeats)
    pairs = None
    if study["paradigm"] == Paradigm.PAIRWISE and n_stimuli >= 2:
        pairs = list(itertools.combinations(range(n_stimuli), 2))
        if study["config"].get("randomize_pairs", True):
            random.shuffle(pairs)

    session_data = {
        "id": session_id,
        "study_id": study_id,
        "participant_id": participant_id,
        "status": SessionStatus.IN_PROGRESS,
        "batches": batches or [],
        "pairs": pairs or [],
        "current_trial_index": 0,
        "started_at": datetime.utcnow(),
        "completed_at": None,
        # Adaptive state (for LTW paradigm)
        "D": np.ones((n_stimuli, n_stimuli)) - np.eye(n_stimuli) if n_stimuli > 0 else None,
        "W_raw": np.zeros((n_stimuli, n_stimuli)) if n_stimuli > 0 else None,
        "W_sched": np.zeros((n_stimuli, n_stimuli)) if n_stimuli > 0 else None,
        "trial_arrangements": [],
        "seen": seen,
        "recent": recent,
        "inclusion_counts": inclusion_counts,
        "durations": durations,
        "last_subset": last_subset,
        "last_anchor_pair": last_anchor_pair,
        "long_clip_mask": long_clip_mask,
    }
    
    _sessions_db[session_id] = session_data
    _trials_db[session_id] = []
    
    return SessionStartResponse(
        session_id=session_id,
        study_id=study_id,
        paradigm=study["paradigm"],
        n_stimuli=n_stimuli,
        stimuli=[StimulusResponse(**s) for s in stimuli],
        config=study["config"],
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: UUID) -> SessionResponse:
    """Get session status."""
    if session_id not in _sessions_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session = _sessions_db[session_id]
    studies_db = get_studies_db()
    study = studies_db.get(session["study_id"])
    if study is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
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
    """Get the next trial subset."""
    if session_id not in _sessions_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session = _sessions_db[session_id]
    studies_db = get_studies_db()
    study = studies_db[session["study_id"]]
    stimuli_db = get_stimuli_db()
    n_stimuli = len(stimuli_db.get(session["study_id"], []))
    
    trial_index = session["current_trial_index"]

    if _time_limit_reached(session, study):
        session["status"] = SessionStatus.COMPLETED
        session["completed_at"] = datetime.utcnow()
        return NextTrialResponse(
            trial_index=trial_index,
            subset_indices=[],
            is_final=True
        )
    
    if study["paradigm"] == Paradigm.SETCOVER:
        # Fixed batches
        batches = session.get("batches", [])
        if trial_index >= len(batches):
            return NextTrialResponse(
                trial_index=trial_index,
                subset_indices=[],
                is_final=True
            )
        
        return NextTrialResponse(
            trial_index=trial_index,
            subset_indices=batches[trial_index],
            is_final=False
        )
    elif study["paradigm"] == Paradigm.PAIRWISE:
        # Pairwise comparison
        pairs = session.get("pairs", [])
        if trial_index >= len(pairs):
            return NextTrialResponse(
                trial_index=trial_index,
                subset_indices=[],
                is_final=True
            )
        
        pair = pairs[trial_index]
        return NextTrialResponse(
            trial_index=trial_index,
            subset_indices=list(pair),
            is_final=False
        )
    else:
        # Adaptive LTW
        D = session.get("D")

        W = session.get("W_sched")
        
        if D is None or W is None or n_stimuli < 2:
            return NextTrialResponse(
                trial_index=trial_index,
                subset_indices=[],
                is_final=True
            )

        # Initial full-set trial (mirrors the Python library's trial 0)
        if trial_index == 0 and not session.get("trial_arrangements"):
            return NextTrialResponse(
                trial_index=trial_index,
                subset_indices=list(range(n_stimuli)),
                is_final=False
            )
        
        # Check stopping criterion
        threshold = study["config"].get("evidence_threshold", 0.35)
        stop_on_utility = bool(study["config"].get("stop_on_utility", False))
        if stop_on_utility:
            d = float(study["config"].get("utility_exponent", 10.0))
            iu = np.triu_indices(n_stimuli, 1)
            if iu[0].size > 0:
                u_vals = 1.0 - np.exp(-d * W[iu])
                if float(np.min(u_vals)) >= float(threshold):
                    return NextTrialResponse(
                        trial_index=trial_index,
                        subset_indices=[],
                        is_final=True
                    )
        elif check_stopping_criterion(W, threshold):
            return NextTrialResponse(
                trial_index=trial_index,
                subset_indices=[],
                is_final=True
            )
        
        # Select next subset
        min_size = study["config"].get("min_subset_size", 4)
        max_size = study["config"].get("max_subset_size", 6)
        cfg = study["config"]
        
        cold_start_trials = int(cfg.get("cold_start_require_unseen_trials", 0))
        require_unseen = cold_start_trials > 0 and int(session.get("current_trial_index", 0)) < cold_start_trials

        subset = select_next_subset_lift_weakest(
            D, W,
            utility_exponent=float(cfg.get("utility_exponent", 10.0)),
            time_cost_exponent=float(cfg.get("time_cost_exponent", 1.5)),
            arena_max=float(cfg.get("arena_max", 1.0)),
            min_size=int(min_size),
            max_size=int(max_size),
            seen=session.get("seen"),
            recent=session.get("recent"),
            last_subset=session.get("last_subset"),
            avoid_anchor_pair=session.get("last_anchor_pair") if bool(cfg.get("avoid_anchor_reuse", False)) else None,
            max_jaccard=cfg.get("max_jaccard"),
            overlap_penalty=float(cfg.get("overlap_penalty", 0.0)),
            recency_penalty=float(cfg.get("recency_penalty", 0.0)),
            unseen_boost=float(cfg.get("unseen_boost", 0.0)),
            stress_weight=float(cfg.get("stress_weight", 0.0)),
            durations=session.get("durations"),
            duration_cost_weight=float(cfg.get("duration_cost_weight", 0.0)),
            target_time_seconds=cfg.get("target_time_seconds"),
            target_time_tolerance=float(cfg.get("target_time_tolerance", 0.05)),
            duration_cost_cap_per_item=cfg.get("duration_cost_cap_per_item"),
            inclusion_counts=session.get("inclusion_counts"),
            long_clip_mask=session.get("long_clip_mask"),
            min_long_clip_inclusion_rate=float(cfg.get("min_long_clip_inclusion_rate", 0.0)),
            long_clip_boost=float(cfg.get("long_clip_boost", 0.0)),
            trials_so_far=int(session.get("current_trial_index", 0)),
            require_unseen=require_unseen,
        )
        
        return NextTrialResponse(
            trial_index=trial_index,
            subset_indices=subset,
            is_final=False
        )


@router.post("/sessions/{session_id}/trials", response_model=TrialResponse)
async def submit_trial(session_id: UUID, trial: TrialSubmit) -> TrialResponse:
    """Submit trial results."""
    import uuid
    from datetime import datetime
    
    if session_id not in _sessions_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session = _sessions_db[session_id]
    studies_db = get_studies_db()
    study = studies_db[session["study_id"]]
    
    trial_id = uuid.uuid4()
    now = datetime.utcnow()
    
    # Handle pairwise paradigm (rating-based)
    if study["paradigm"] == Paradigm.PAIRWISE:
        pairs = session.get("pairs", [])
        if trial.trial_index != session.get("current_trial_index", trial.trial_index):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trial index out of sequence"
            )
        if len(trial.subset_indices) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pairwise trials must include exactly two indices"
            )
        if trial.trial_index >= len(pairs):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trial index exceeds scheduled pairs"
            )
        expected_pair = list(pairs[trial.trial_index])
        if list(trial.subset_indices) != expected_pair:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Submitted pair does not match scheduled pair"
            )
        if trial.rating is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating is required for pairwise paradigm"
            )
        
        trial_data = {
            "id": trial_id,
            "trial_index": trial.trial_index,
            "subset_indices": trial.subset_indices,
            "rating": trial.rating,
            "duration_seconds": trial.duration_seconds,
            "started_at": now,
            "completed_at": now,
        }
        
        _trials_db[session_id].append(trial_data)
        session["current_trial_index"] = trial.trial_index + 1
        
        # Update pairwise RDM
        stimuli_db = get_stimuli_db()
        n_stimuli = len(stimuli_db.get(session["study_id"], []))
        
        if n_stimuli >= 2:
            # Initialize or get pairwise RDM storage
            if "pairwise_ratings" not in session:
                session["pairwise_ratings"] = {}
            
            # Store rating for this pair
            i, j = trial.subset_indices[0], trial.subset_indices[1]
            pair_key = (min(i, j), max(i, j))
            if pair_key not in session["pairwise_ratings"]:
                session["pairwise_ratings"][pair_key] = []
            session["pairwise_ratings"][pair_key].append(trial.rating)
            
            # Compute RDM from ratings (convert similarity 1-7 to dissimilarity 0-1)
            D = np.ones((n_stimuli, n_stimuli)) * 0.5  # default
            W = np.zeros((n_stimuli, n_stimuli))
            for (pi, pj), ratings in session["pairwise_ratings"].items():
                avg_rating = np.mean(ratings)
                # Rating scale: 1=different (dissimilarity 1), 7=similar (dissimilarity 0)
                # Invert: higher rating = more similar = lower dissimilarity
                dissimilarity = (7 - avg_rating) / 6  # 7 -> 0, 1 -> 1
                D[pi, pj] = dissimilarity
                D[pj, pi] = dissimilarity
                W[pi, pj] = len(ratings)
                W[pj, pi] = len(ratings)
            np.fill_diagonal(D, 0)
            session["D"] = D
            session["W_raw"] = W
        
        return TrialResponse(
            id=trial_id,
            trial_index=trial.trial_index,
            subset_indices=trial.subset_indices,
            duration_seconds=trial.duration_seconds,
            started_at=now,
            completed_at=now,
        )
    
    # Handle arrangement-based paradigms (setcover, adaptive)
    if trial.positions is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Positions are required for arrangement paradigms"
        )
    
    # Validate positions include all subset indices
    missing = [idx for idx in trial.subset_indices if str(idx) not in trial.positions]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing positions for indices: {missing}"
        )

    trial_data = {
        "id": trial_id,
        "trial_index": trial.trial_index,
        "subset_indices": trial.subset_indices,
        "positions": {k: (v.x, v.y) for k, v in trial.positions.items()},
        "duration_seconds": trial.duration_seconds,
        "started_at": now,
        "completed_at": now,
    }
    
    _trials_db[session_id].append(trial_data)
    
    # Update session state
    session["current_trial_index"] = trial.trial_index + 1
    
    # Convert positions to TrialArrangement format
    positions_dict = {int(k): (v.x, v.y) for k, v in trial.positions.items()}
    arrangement = TrialArrangement(
        subset=trial.subset_indices,
        positions=positions_dict
    )
    session["trial_arrangements"].append(arrangement)

    # Update adaptive policy state (seen/recency)
    if session.get("seen") is not None and session.get("recent") is not None:
        sel = list(positions_dict.keys())
        session["seen"][sel] = True
        recency_decay = float(study["config"].get("recency_decay", 0.85))
        session["recent"] *= recency_decay
        session["recent"][sel] += 1.0
        if session.get("inclusion_counts") is not None:
            for idx in sel:
                if 0 <= idx < len(session["inclusion_counts"]):
                    session["inclusion_counts"][idx] += 1
        session["last_subset"] = list(sel)
        if len(sel) >= 2:
            a, b = int(sel[0]), int(sel[1])
            session["last_anchor_pair"] = (min(a, b), max(a, b))

    # Re-estimate RDM/evidence
    stimuli_db = get_stimuli_db()
    n_stimuli = len(stimuli_db.get(session["study_id"], []))

    if n_stimuli >= 2:
        cfg = study["config"]
        robust_method = cfg.get("robust_method")
        robust_winsor_high = float(cfg.get("robust_winsor_high", 0.98))
        robust_huber_c = float(cfg.get("robust_huber_c", 0.9))

        if study["paradigm"] == Paradigm.SETCOVER:
            setcover_weight_mode = cfg.get("setcover_weight_mode", cfg.get("weight_mode", "max"))
            setcover_weight_alpha = float(cfg.get("setcover_weight_alpha", cfg.get("weight_alpha", 2.0)))
            use_inverse_mds = bool(cfg.get("use_inverse_mds", False))
            inverse_mds_max_iter = int(cfg.get("inverse_mds_max_iter", 15))
            inverse_mds_step_c = float(cfg.get("inverse_mds_step_c", 0.3))
            inverse_mds_tol = float(cfg.get("inverse_mds_tol", 1e-4))

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
            evidence_weight_mode = cfg.get("evidence_weight_mode", "k2012")
            evidence_alpha = float(cfg.get("evidence_alpha", 2.0))
            use_inverse_mds = bool(cfg.get("use_inverse_mds", False))
            inverse_mds_max_iter = int(cfg.get("inverse_mds_max_iter", 15))
            inverse_mds_step_c = float(cfg.get("inverse_mds_step_c", 0.3))
            inverse_mds_tol = float(cfg.get("inverse_mds_tol", 1e-4))

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

    return TrialResponse(
        id=trial_id,
        trial_index=trial.trial_index,
        subset_indices=trial.subset_indices,
        duration_seconds=trial.duration_seconds,
        started_at=now,
        completed_at=now,
    )


@router.post("/sessions/{session_id}/complete", response_model=SessionResponse)
async def complete_session(session_id: UUID) -> SessionResponse:
    """Mark session as completed."""
    from datetime import datetime
    
    if session_id not in _sessions_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session = _sessions_db[session_id]
    studies_db = get_studies_db()
    study = studies_db.get(session["study_id"])
    if study is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    session["status"] = SessionStatus.COMPLETED
    session["completed_at"] = datetime.utcnow()
    
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


# Export for results router
def get_sessions_db():
    return _sessions_db

def get_trials_db():
    return _trials_db
