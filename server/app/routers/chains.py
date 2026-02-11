"""
Chain management endpoints for linking multiple experiments.
"""

import secrets
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import (
    ChainCreate,
    ChainResponse,
    ChainStudyCreate,
    ChainStudyResponse,
    ChainInviteCreate,
    ChainInviteResponse,
    ChainSessionResponse,
    ChainSessionStartResponse,
    ChainStatus,
    SessionStatus,
    StimulusResponse,
)
from app.routers.studies import get_studies_db, get_stimuli_db
from app.routers.sessions import create_session
from app.routers.experimenter import get_optional_owner, get_required_owner

router = APIRouter(prefix="/chains", tags=["chains"])

# In-memory storage for development (replace with Supabase later)
_chains_db: Dict[UUID, dict] = {}
_chain_studies_db: Dict[UUID, List[dict]] = {}
_chain_invites_db: Dict[str, dict] = {}  # token -> invite data
_chain_sessions_db: Dict[UUID, dict] = {}


def _require_chain_owner(chain_id: UUID, owner_id: UUID) -> dict:
    """Ensure the caller owns the chain and return chain data."""
    if chain_id not in _chains_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found"
        )
    chain = _chains_db[chain_id]
    if chain.get("owner_id") != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your chain"
        )
    return chain


def _get_chain_with_studies(chain_id: UUID) -> dict:
    """Get chain data with populated studies list."""
    if chain_id not in _chains_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found"
        )
    
    chain = _chains_db[chain_id].copy()
    studies_db = get_studies_db()
    
    chain_studies = sorted(
        _chain_studies_db.get(chain_id, []),
        key=lambda x: x["position"]
    )
    
    studies = []
    for cs in chain_studies:
        study = studies_db.get(cs["study_id"])
        if study:
            studies.append({
                "id": cs["id"],
                "chain_id": chain_id,
                "study_id": cs["study_id"],
                "study_name": study["name"],
                "paradigm": study["paradigm"],
                "position": cs["position"],
            })
    
    chain["studies"] = studies
    return chain


@router.post("", response_model=ChainResponse, status_code=status.HTTP_201_CREATED)
async def create_chain(
    chain: ChainCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> ChainResponse:
    """Create a new experiment chain. Requires experimenter key."""
    import uuid
    
    chain_id = uuid.uuid4()
    
    chain_data = {
        "id": chain_id,
        "owner_id": owner_id,
        "name": chain.name,
        "description": chain.description,
        "created_at": datetime.utcnow(),
    }
    
    _chains_db[chain_id] = chain_data
    _chain_studies_db[chain_id] = []
    
    return ChainResponse(**{**chain_data, "studies": []})


@router.get("", response_model=List[ChainResponse])
async def list_chains(
    owner_id: Optional[UUID] = Depends(get_optional_owner),
) -> List[ChainResponse]:
    """List chains filtered by experimenter key. Returns empty if no key."""
    if owner_id is None:
        return []
    return [
        ChainResponse(**_get_chain_with_studies(chain_id))
        for chain_id, chain_data in _chains_db.items()
        if chain_data.get("owner_id") == owner_id
    ]


@router.get("/{chain_id}", response_model=ChainResponse)
async def get_chain(
    chain_id: UUID,
    owner_id: Optional[UUID] = Depends(get_optional_owner),
) -> ChainResponse:
    """Get chain details with studies."""
    if owner_id is not None:
        _require_chain_owner(chain_id, owner_id)
    return ChainResponse(**_get_chain_with_studies(chain_id))


@router.delete("/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chain(
    chain_id: UUID,
    owner_id: UUID = Depends(get_required_owner),
):
    """Delete a chain and all associated data."""
    _require_chain_owner(chain_id, owner_id)
    
    del _chains_db[chain_id]
    if chain_id in _chain_studies_db:
        del _chain_studies_db[chain_id]
    
    # Clean up invites for this chain
    tokens_to_remove = [
        token for token, invite in _chain_invites_db.items()
        if invite["chain_id"] == chain_id
    ]
    for token in tokens_to_remove:
        del _chain_invites_db[token]


@router.post("/{chain_id}/studies", response_model=ChainStudyResponse, status_code=status.HTTP_201_CREATED)
async def add_study_to_chain(
    chain_id: UUID,
    payload: ChainStudyCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> ChainStudyResponse:
    """Add a study to a chain."""
    import uuid
    
    _require_chain_owner(chain_id, owner_id)
    
    studies_db = get_studies_db()
    if payload.study_id not in studies_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found"
        )
    
    chain_studies = _chain_studies_db.get(chain_id, [])
    
    # Check if study is already in chain
    existing = [cs for cs in chain_studies if cs["study_id"] == payload.study_id]
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Study is already in this chain"
        )
    
    # Determine position
    if payload.position is not None:
        position = payload.position
        # Shift existing studies if needed
        for cs in chain_studies:
            if cs["position"] >= position:
                cs["position"] += 1
    else:
        # Append at end
        position = max([cs["position"] for cs in chain_studies], default=-1) + 1
    
    study = studies_db[payload.study_id]
    chain_study_id = uuid.uuid4()
    
    chain_study = {
        "id": chain_study_id,
        "chain_id": chain_id,
        "study_id": payload.study_id,
        "position": position,
    }
    chain_studies.append(chain_study)
    _chain_studies_db[chain_id] = chain_studies
    
    return ChainStudyResponse(
        id=chain_study_id,
        chain_id=chain_id,
        study_id=payload.study_id,
        study_name=study["name"],
        paradigm=study["paradigm"],
        position=position,
    )


@router.delete("/{chain_id}/studies/{study_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_study_from_chain(
    chain_id: UUID,
    study_id: UUID,
    owner_id: UUID = Depends(get_required_owner),
):
    """Remove a study from a chain."""
    _require_chain_owner(chain_id, owner_id)
    
    chain_studies = _chain_studies_db.get(chain_id, [])
    removed_position = None
    
    for i, cs in enumerate(chain_studies):
        if cs["study_id"] == study_id:
            removed_position = cs["position"]
            chain_studies.pop(i)
            break
    
    if removed_position is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found in chain"
        )
    
    # Reorder remaining studies
    for cs in chain_studies:
        if cs["position"] > removed_position:
            cs["position"] -= 1
    
    _chain_studies_db[chain_id] = chain_studies


@router.patch("/{chain_id}/studies/{study_id}", response_model=ChainStudyResponse)
async def reorder_study_in_chain(
    chain_id: UUID,
    study_id: UUID,
    new_position: int,
    owner_id: UUID = Depends(get_required_owner),
) -> ChainStudyResponse:
    """Change the position of a study in the chain."""
    _require_chain_owner(chain_id, owner_id)
    
    chain_studies = _chain_studies_db.get(chain_id, [])
    target_study = None
    old_position = None
    
    for cs in chain_studies:
        if cs["study_id"] == study_id:
            target_study = cs
            old_position = cs["position"]
            break
    
    if target_study is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study not found in chain"
        )
    
    # Reorder studies
    if new_position > old_position:
        # Moving down
        for cs in chain_studies:
            if old_position < cs["position"] <= new_position:
                cs["position"] -= 1
    else:
        # Moving up
        for cs in chain_studies:
            if new_position <= cs["position"] < old_position:
                cs["position"] += 1
    
    target_study["position"] = new_position
    _chain_studies_db[chain_id] = chain_studies
    
    studies_db = get_studies_db()
    study = studies_db[study_id]
    
    return ChainStudyResponse(
        id=target_study["id"],
        chain_id=chain_id,
        study_id=study_id,
        study_name=study["name"],
        paradigm=study["paradigm"],
        position=new_position,
    )


@router.post("/{chain_id}/invites", response_model=List[ChainInviteResponse])
async def create_chain_invites(
    chain_id: UUID,
    payload: ChainInviteCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> List[ChainInviteResponse]:
    """Generate invite links for a chain."""
    _require_chain_owner(chain_id, owner_id)
    
    chain_studies = _chain_studies_db.get(chain_id, [])
    if not chain_studies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chain has no studies. Add at least one study before creating invites."
        )
    
    invites = []
    count = payload.count or 1
    
    for i in range(count):
        token = secrets.token_urlsafe(16)
        participant_id = payload.participant_id
        if participant_id and count > 1:
            participant_id = f"{payload.participant_id}_{i+1}"
        
        invite = {
            "token": token,
            "chain_id": chain_id,
            "participant_id": participant_id,
            "created_at": datetime.utcnow(),
        }
        _chain_invites_db[token] = invite
        invites.append(ChainInviteResponse(
            token=token,
            chain_id=chain_id,
            participant_id=participant_id,
        ))
    
    return invites


# Public endpoints for chain participation
public_router = APIRouter(prefix="/public/chain-invites", tags=["chain-participation"])


@public_router.post("/{token}/start", response_model=ChainSessionStartResponse)
async def start_chain_session(token: str) -> ChainSessionStartResponse:
    """Start or resume a chain session from an invite token."""
    import uuid
    from app.routers.sessions import get_sessions_db, get_stimuli_db
    
    invite = _chain_invites_db.get(token)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite token"
        )
    
    chain_id = invite["chain_id"]
    if chain_id not in _chains_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found"
        )
    
    chain = _chains_db[chain_id]
    chain_studies = sorted(
        _chain_studies_db.get(chain_id, []),
        key=lambda x: x["position"]
    )
    
    if not chain_studies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chain has no studies"
        )
    
    # Check if there's an existing chain session for this invite
    existing_chain_session_id = invite.get("chain_session_id")
    if existing_chain_session_id and existing_chain_session_id in _chain_sessions_db:
        # Resume existing session
        chain_session = _chain_sessions_db[existing_chain_session_id]
        
        # Check if already completed
        if chain_session["status"] == ChainStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This chain has already been completed"
            )
        
        # Get current session info
        current_position = chain_session["current_position"]
        current_session_id = chain_session["current_session_id"]
        
        sessions_db = get_sessions_db()
        stimuli_db = get_stimuli_db()
        studies_db = get_studies_db()
        
        if current_session_id in sessions_db:
            session = sessions_db[current_session_id]
            
            # Check if current study session is completed - if so, advance to next study
            if session.get("status") == SessionStatus.COMPLETED:
                # Calculate next position
                next_position = current_position + 1
                
                # Check if chain is complete
                if next_position >= len(chain_studies):
                    chain_session["status"] = ChainStatus.COMPLETED
                    chain_session["completed_at"] = datetime.utcnow()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This chain has already been completed"
                    )
                
                # Get the next study
                next_chain_study = chain_studies[next_position]
                next_study_id = next_chain_study["study_id"]
                participant_id = chain_session["participant_id"]
                
                # Create session for next study
                session_response = create_session(next_study_id, participant_id)
                
                # Update chain session
                chain_session["current_position"] = next_position
                chain_session["current_session_id"] = session_response.session_id
                
                return ChainSessionStartResponse(
                    chain_session_id=existing_chain_session_id,
                    chain_id=chain_id,
                    chain_name=chain["name"],
                    total_studies=len(chain_studies),
                    current_position=next_position,
                    session_id=session_response.session_id,
                    study_id=next_study_id,
                    paradigm=session_response.paradigm,
                    n_stimuli=session_response.n_stimuli,
                    stimuli=session_response.stimuli,
                    config=session_response.config,
                )
            
            # Session is still in progress, return it
            study = studies_db.get(session["study_id"], {})
            stimuli = stimuli_db.get(session["study_id"], [])
            
            return ChainSessionStartResponse(
                chain_session_id=existing_chain_session_id,
                chain_id=chain_id,
                chain_name=chain["name"],
                total_studies=len(chain_studies),
                current_position=current_position,
                session_id=current_session_id,
                study_id=session["study_id"],
                paradigm=study.get("paradigm"),
                n_stimuli=len(stimuli),
                stimuli=[
                    StimulusResponse(
                        id=s["id"],
                        ordinal=s["ordinal"],
                        filename=s["filename"],
                        media_type=s.get("media_type", "video"),
                        url=s.get("url"),
                    )
                    for s in stimuli
                ],
                config=study.get("config", {}),
            )
        else:
            # Session data was lost (e.g., server restart) - recreate at current position
            if current_position < len(chain_studies):
                chain_study = chain_studies[current_position]
                study_id = chain_study["study_id"]
                participant_id = chain_session.get("participant_id", f"chain_{uuid.uuid4().hex[:8]}")
                
                # Create session for current study
                session_response = create_session(study_id, participant_id)
                
                # Update chain session with new session ID
                chain_session["current_session_id"] = session_response.session_id
                
                return ChainSessionStartResponse(
                    chain_session_id=existing_chain_session_id,
                    chain_id=chain_id,
                    chain_name=chain["name"],
                    total_studies=len(chain_studies),
                    current_position=current_position,
                    session_id=session_response.session_id,
                    study_id=study_id,
                    paradigm=session_response.paradigm,
                    n_stimuli=session_response.n_stimuli,
                    stimuli=session_response.stimuli,
                    config=session_response.config,
                )
    
    # Create new chain session
    first_chain_study = chain_studies[0]
    study_id = first_chain_study["study_id"]
    
    # Generate participant ID
    participant_id = invite.get("participant_id") or f"chain_{uuid.uuid4().hex[:8]}"
    
    # Create the first study session
    session_response = create_session(study_id, participant_id)
    
    # Create chain session to track progress
    chain_session_id = uuid.uuid4()
    chain_session = {
        "id": chain_session_id,
        "chain_invite_token": token,
        "chain_id": chain_id,
        "current_position": 0,
        "current_session_id": session_response.session_id,
        "status": ChainStatus.IN_PROGRESS,
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "participant_id": participant_id,
    }
    _chain_sessions_db[chain_session_id] = chain_session
    
    # Mark invite as used (store chain session ID)
    invite["chain_session_id"] = chain_session_id
    
    return ChainSessionStartResponse(
        chain_session_id=chain_session_id,
        chain_id=chain_id,
        chain_name=chain["name"],
        total_studies=len(chain_studies),
        current_position=0,
        session_id=session_response.session_id,
        study_id=study_id,
        paradigm=session_response.paradigm,
        n_stimuli=session_response.n_stimuli,
        stimuli=session_response.stimuli,
        config=session_response.config,
    )


@public_router.post("/{token}/next", response_model=ChainSessionStartResponse)
async def advance_chain_session(token: str) -> ChainSessionStartResponse:
    """Advance to the next study in the chain."""
    import uuid
    
    invite = _chain_invites_db.get(token)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite token"
        )
    
    chain_session_id = invite.get("chain_session_id")
    if not chain_session_id or chain_session_id not in _chain_sessions_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active chain session for this invite. Call /start first."
        )
    
    chain_session = _chain_sessions_db[chain_session_id]
    chain_id = chain_session["chain_id"]
    chain = _chains_db[chain_id]
    
    chain_studies = sorted(
        _chain_studies_db.get(chain_id, []),
        key=lambda x: x["position"]
    )
    
    next_position = chain_session["current_position"] + 1
    
    if next_position >= len(chain_studies):
        # Chain is complete
        chain_session["status"] = ChainStatus.COMPLETED
        chain_session["completed_at"] = datetime.utcnow()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chain is already complete. No more studies."
        )
    
    # Get the next study
    next_chain_study = chain_studies[next_position]
    study_id = next_chain_study["study_id"]
    participant_id = chain_session["participant_id"]
    
    # Create session for next study
    session_response = create_session(study_id, participant_id)
    
    # Update chain session
    chain_session["current_position"] = next_position
    chain_session["current_session_id"] = session_response.session_id
    
    return ChainSessionStartResponse(
        chain_session_id=chain_session_id,
        chain_id=chain_id,
        chain_name=chain["name"],
        total_studies=len(chain_studies),
        current_position=next_position,
        session_id=session_response.session_id,
        study_id=study_id,
        paradigm=session_response.paradigm,
        n_stimuli=session_response.n_stimuli,
        stimuli=session_response.stimuli,
        config=session_response.config,
    )


@public_router.get("/{token}/status", response_model=ChainSessionResponse)
async def get_chain_session_status(token: str) -> ChainSessionResponse:
    """Get the current status of a chain session."""
    invite = _chain_invites_db.get(token)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite token"
        )
    
    chain_session_id = invite.get("chain_session_id")
    if not chain_session_id or chain_session_id not in _chain_sessions_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No chain session found for this invite"
        )
    
    chain_session = _chain_sessions_db[chain_session_id]
    chain_id = chain_session["chain_id"]
    chain = _chains_db[chain_id]
    chain_studies = _chain_studies_db.get(chain_id, [])
    
    return ChainSessionResponse(
        id=chain_session_id,
        chain_id=chain_id,
        chain_name=chain["name"],
        current_position=chain_session["current_position"],
        total_studies=len(chain_studies),
        current_session_id=chain_session["current_session_id"],
        status=chain_session["status"],
        started_at=chain_session["started_at"],
        completed_at=chain_session.get("completed_at"),
    )


# Export storage for testing
def get_chains_db():
    return _chains_db

def get_chain_studies_db():
    return _chain_studies_db

def get_chain_invites_db():
    return _chain_invites_db

def get_chain_sessions_db():
    return _chain_sessions_db


# Admin endpoint to delete chain participant session
@router.delete("/{chain_id}/sessions/{chain_session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chain_session(
    chain_id: UUID,
    chain_session_id: UUID,
    owner_id: UUID = Depends(get_required_owner),
):
    """Delete a chain participant session and associated data."""
    from app.routers.sessions import get_sessions_db, get_trials_db
    
    _require_chain_owner(chain_id, owner_id)
    
    if chain_session_id not in _chain_sessions_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain session not found"
        )
    
    chain_session = _chain_sessions_db[chain_session_id]
    if chain_session["chain_id"] != chain_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chain session does not belong to this chain"
        )
    
    participant_id = chain_session.get("participant_id")
    
    # Delete associated study sessions for this participant (scoped to chain's studies)
    sessions_db = get_sessions_db()
    trials_db = get_trials_db()
    
    chain_study_ids = {cs["study_id"] for cs in _chain_studies_db.get(chain_id, [])}
    sessions_to_delete = [
        sid for sid, session in sessions_db.items()
        if session.get("participant_id") == participant_id
        and session.get("study_id") in chain_study_ids
    ]
    
    for sid in sessions_to_delete:
        if sid in trials_db:
            del trials_db[sid]
        del sessions_db[sid]
    
    # Delete the chain session
    del _chain_sessions_db[chain_session_id]


# Admin endpoint to get chain participant sessions
@router.get("/{chain_id}/sessions")
async def get_chain_sessions(
    chain_id: UUID,
    owner_id: UUID = Depends(get_required_owner),
):
    """Get all sessions for a chain (for admin results viewing)."""
    from app.routers.sessions import get_sessions_db, get_trials_db
    
    chain = _require_chain_owner(chain_id, owner_id)
    chain_studies = sorted(
        _chain_studies_db.get(chain_id, []),
        key=lambda x: x["position"]
    )
    
    # Find all chain sessions for this chain
    chain_sessions = [
        cs for cs in _chain_sessions_db.values()
        if cs["chain_id"] == chain_id
    ]
    
    sessions_db = get_sessions_db()
    trials_db = get_trials_db()
    studies_db = get_studies_db()
    
    result = {
        "chain_id": str(chain_id),
        "chain_name": chain["name"],
        "total_studies": len(chain_studies),
        "participants": []
    }
    
    for cs in chain_sessions:
        participant_sessions = []
        
        # Find all study sessions for this participant
        for session in sessions_db.values():
            if session.get("participant_id") == cs.get("participant_id"):
                study_id = session["study_id"]
                study = studies_db.get(study_id, {})
                trials = trials_db.get(session["id"], [])
                
                participant_sessions.append({
                    "session_id": str(session["id"]),
                    "study_id": str(study_id),
                    "study_name": study.get("name", "Unknown"),
                    "paradigm": study.get("paradigm", {}).value if hasattr(study.get("paradigm", {}), "value") else str(study.get("paradigm", "")),
                    "status": session.get("status", {}).value if hasattr(session.get("status", {}), "value") else str(session.get("status", "")),
                    "n_trials": len(trials),
                    "started_at": session.get("started_at", datetime.utcnow()).isoformat() if session.get("started_at") else None,
                })
        
        # Compute actual status: check if we have sessions for all studies in the chain
        # and all of them are completed
        completed_count = sum(
            1 for s in participant_sessions 
            if s["status"] == "completed"
        )
        total_studies = len(chain_studies)
        
        # Update current_position based on actual sessions
        actual_position = len(participant_sessions)
        
        # Determine actual status
        if completed_count >= total_studies:
            computed_status = "completed"
            # Also update the stored status if needed
            if cs["status"] != ChainStatus.COMPLETED:
                cs["status"] = ChainStatus.COMPLETED
                cs["completed_at"] = datetime.utcnow()
        else:
            computed_status = "in_progress"
        
        participant_data = {
            "chain_session_id": str(cs["id"]),
            "participant_id": cs.get("participant_id", "unknown"),
            "status": computed_status,
            "started_at": cs["started_at"].isoformat() if cs.get("started_at") else None,
            "completed_at": cs.get("completed_at").isoformat() if cs.get("completed_at") else None,
            "current_position": actual_position,
            "sessions": participant_sessions
        }
        
        result["participants"].append(participant_data)
    
    return result
