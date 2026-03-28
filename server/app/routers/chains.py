"""
Chain management endpoints for linking multiple experiments.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select, update
from sqlalchemy.engine import Connection

from app.routers.experimenter import get_optional_owner, get_required_owner
from app.routers.sessions import (
    create_session,
    delete_session_record,
    get_session_record,
    get_session_start_payload,
    get_trials_for_session,
    list_sessions_for_study,
)
from app.routers.studies import get_studies_db, get_study
from app.schemas import (
    ChainCreate,
    ChainInviteCreate,
    ChainInviteResponse,
    ChainResponse,
    ChainSessionResponse,
    ChainSessionStartResponse,
    ChainStatus,
    ChainStudyCreate,
    ChainStudyResponse,
)
from app.storage import (
    chain_invites_table,
    chain_sessions_table,
    chain_studies_table,
    chains_table,
    connect,
    fetch_all,
    fetch_one,
    ordered_select,
    utcnow_iso,
)

router = APIRouter(prefix="/chains", tags=["chains"])
public_router = APIRouter(prefix="/public/chain-invites", tags=["chain-participation"])


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_chain(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": UUID(row["id"]),
        "owner_id": UUID(row["owner_id"]),
        "name": row["name"],
        "description": row.get("description"),
        "created_at": _parse_dt(row["created_at"]),
    }


def _parse_chain_session(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": UUID(row["id"]),
        "chain_id": UUID(row["chain_id"]),
        "invite_token": row["invite_token"],
        "participant_id": row["participant_id"],
        "current_position": int(row["current_position"]),
        "current_session_id": UUID(row["current_session_id"]) if row.get("current_session_id") else None,
        "status": ChainStatus(row["status"]),
        "started_at": _parse_dt(row["started_at"]),
        "completed_at": _parse_dt(row.get("completed_at")),
    }


def _parse_chain_invite(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "token": row["token"],
        "chain_id": UUID(row["chain_id"]),
        "participant_id": row.get("participant_id"),
        "created_at": _parse_dt(row["created_at"]),
        "chain_session_id": UUID(row["chain_session_id"]) if row.get("chain_session_id") else None,
    }


def _parse_chain_study(row: dict[str, Any], study: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": UUID(row["id"]),
        "chain_id": UUID(row["chain_id"]),
        "study_id": UUID(row["study_id"]),
        "study_name": study["name"],
        "paradigm": study["paradigm"],
        "position": int(row["position"]),
    }


def _get_chain(chain_id: UUID | str, conn: Connection | None = None) -> dict[str, Any] | None:
    statement = select(chains_table).where(chains_table.c.id == str(chain_id))
    if conn is not None:
        row = fetch_one(conn, statement)
    else:
        with connect(readonly=True) as managed:
            row = fetch_one(managed, statement)
    return _parse_chain(row) if row else None


def _list_chain_studies(chain_id: UUID | str, conn: Connection | None = None) -> list[dict[str, Any]]:
    statement = ordered_select(chain_studies_table, chain_studies_table.c.position).where(
        chain_studies_table.c.chain_id == str(chain_id)
    )
    if conn is not None:
        rows = fetch_all(conn, statement)
    else:
        with connect(readonly=True) as managed:
            rows = fetch_all(managed, statement)
    studies_db = get_studies_db()
    parsed = []
    for row in rows:
        study = studies_db.get(UUID(row["study_id"]))
        if study is not None:
            parsed.append(_parse_chain_study(row, study))
    return parsed


def _get_chain_invite(token: str, conn: Connection | None = None) -> dict[str, Any] | None:
    statement = select(chain_invites_table).where(chain_invites_table.c.token == token)
    if conn is not None:
        row = fetch_one(conn, statement)
    else:
        with connect(readonly=True) as managed:
            row = fetch_one(managed, statement)
    return _parse_chain_invite(row) if row else None


def _get_chain_session(chain_session_id: UUID | str, conn: Connection | None = None) -> dict[str, Any] | None:
    statement = select(chain_sessions_table).where(chain_sessions_table.c.id == str(chain_session_id))
    if conn is not None:
        row = fetch_one(conn, statement)
    else:
        with connect(readonly=True) as managed:
            row = fetch_one(managed, statement)
    return _parse_chain_session(row) if row else None


def _list_chain_sessions(chain_id: UUID | str) -> list[dict[str, Any]]:
    with connect(readonly=True) as conn:
        rows = fetch_all(
            conn,
            ordered_select(chain_sessions_table, chain_sessions_table.c.started_at).where(
                chain_sessions_table.c.chain_id == str(chain_id)
            ),
        )
    return [_parse_chain_session(row) for row in rows]


def _save_chain_session(chain_session: dict[str, Any], conn: Connection | None = None) -> None:
    values = {
        "current_position": int(chain_session["current_position"]),
        "current_session_id": str(chain_session["current_session_id"]) if chain_session.get("current_session_id") else None,
        "status": chain_session["status"].value if isinstance(chain_session["status"], ChainStatus) else str(chain_session["status"]),
        "started_at": chain_session["started_at"].astimezone(timezone.utc).isoformat() if chain_session.get("started_at") else utcnow_iso(),
        "completed_at": chain_session["completed_at"].astimezone(timezone.utc).isoformat() if chain_session.get("completed_at") else None,
    }
    statement = (
        update(chain_sessions_table)
        .where(chain_sessions_table.c.id == str(chain_session["id"]))
        .values(**values)
    )
    if conn is not None:
        conn.execute(statement)
    else:
        with connect() as managed:
            managed.execute(statement)


def _require_chain_owner(chain_id: UUID, owner_id: UUID) -> dict[str, Any]:
    chain = _get_chain(chain_id)
    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")
    if chain["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your chain")
    return chain


def _get_chain_with_studies(chain_id: UUID) -> dict[str, Any]:
    chain = _get_chain(chain_id)
    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")
    chain["studies"] = _list_chain_studies(chain_id)
    return chain


def _chain_start_response(chain_session: dict[str, Any], chain: dict[str, Any], session_payload) -> ChainSessionStartResponse:
    studies = _list_chain_studies(chain["id"])
    return ChainSessionStartResponse(
        chain_session_id=chain_session["id"],
        chain_id=chain["id"],
        chain_name=chain["name"],
        total_studies=len(studies),
        current_position=chain_session["current_position"],
        session_id=session_payload.session_id,
        study_id=session_payload.study_id,
        paradigm=session_payload.paradigm,
        n_stimuli=session_payload.n_stimuli,
        stimuli=session_payload.stimuli,
        config=session_payload.config,
    )


@router.post("", response_model=ChainResponse, status_code=status.HTTP_201_CREATED)
async def create_chain(
    chain: ChainCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> ChainResponse:
    chain_id = uuid4()
    chain_row = {
        "id": str(chain_id),
        "owner_id": str(owner_id),
        "name": chain.name,
        "description": chain.description,
        "created_at": utcnow_iso(),
    }
    with connect() as conn:
        conn.execute(chains_table.insert().values(**chain_row))
    created = _get_chain(chain_id)
    return ChainResponse(**{**created, "studies": []})


@router.get("", response_model=List[ChainResponse])
async def list_chains(owner_id: Optional[UUID] = Depends(get_optional_owner)) -> List[ChainResponse]:
    if owner_id is None:
        return []
    with connect(readonly=True) as conn:
        rows = fetch_all(
            conn,
            ordered_select(chains_table, chains_table.c.created_at).where(chains_table.c.owner_id == str(owner_id)),
        )
    return [ChainResponse(**{**_parse_chain(row), "studies": _list_chain_studies(row["id"])}) for row in rows]


@router.get("/{chain_id}", response_model=ChainResponse)
async def get_chain(chain_id: UUID, owner_id: Optional[UUID] = Depends(get_optional_owner)) -> ChainResponse:
    chain = _get_chain_with_studies(chain_id)
    if owner_id is not None and chain["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your chain")
    return ChainResponse(**chain)


@router.delete("/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chain(chain_id: UUID, owner_id: UUID = Depends(get_required_owner)):
    _require_chain_owner(chain_id, owner_id)
    with connect() as conn:
        conn.execute(delete(chains_table).where(chains_table.c.id == str(chain_id)))


@router.post("/{chain_id}/studies", response_model=ChainStudyResponse, status_code=status.HTTP_201_CREATED)
async def add_study_to_chain(
    chain_id: UUID,
    payload: ChainStudyCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> ChainStudyResponse:
    _require_chain_owner(chain_id, owner_id)
    study = get_study(payload.study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    with connect() as conn:
        rows = fetch_all(
            conn,
            ordered_select(chain_studies_table, chain_studies_table.c.position).where(
                chain_studies_table.c.chain_id == str(chain_id)
            ),
        )
        if any(row["study_id"] == str(payload.study_id) for row in rows):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Study is already in this chain")
        if payload.position is None:
            position = max([int(row["position"]) for row in rows], default=-1) + 1
        else:
            position = int(payload.position)
            for row in rows:
                if int(row["position"]) >= position:
                    conn.execute(
                        update(chain_studies_table)
                        .where(chain_studies_table.c.id == row["id"])
                        .values(position=int(row["position"]) + 1)
                    )
        chain_study_id = uuid4()
        conn.execute(
            chain_studies_table.insert().values(
                id=str(chain_study_id),
                chain_id=str(chain_id),
                study_id=str(payload.study_id),
                position=position,
            )
        )

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
    _require_chain_owner(chain_id, owner_id)
    with connect() as conn:
        rows = fetch_all(
            conn,
            ordered_select(chain_studies_table, chain_studies_table.c.position).where(
                chain_studies_table.c.chain_id == str(chain_id)
            ),
        )
        target = next((row for row in rows if row["study_id"] == str(study_id)), None)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found in chain")
        removed_position = int(target["position"])
        conn.execute(delete(chain_studies_table).where(chain_studies_table.c.id == target["id"]))
        for row in rows:
            if row["id"] == target["id"]:
                continue
            if int(row["position"]) > removed_position:
                conn.execute(
                    update(chain_studies_table)
                    .where(chain_studies_table.c.id == row["id"])
                    .values(position=int(row["position"]) - 1)
                )


@router.patch("/{chain_id}/studies/{study_id}", response_model=ChainStudyResponse)
async def reorder_study_in_chain(
    chain_id: UUID,
    study_id: UUID,
    new_position: int,
    owner_id: UUID = Depends(get_required_owner),
) -> ChainStudyResponse:
    _require_chain_owner(chain_id, owner_id)
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    with connect() as conn:
        rows = fetch_all(
            conn,
            ordered_select(chain_studies_table, chain_studies_table.c.position).where(
                chain_studies_table.c.chain_id == str(chain_id)
            ),
        )
        target = next((row for row in rows if row["study_id"] == str(study_id)), None)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found in chain")
        old_position = int(target["position"])
        for row in rows:
            row_position = int(row["position"])
            if row["id"] == target["id"]:
                continue
            if new_position > old_position and old_position < row_position <= new_position:
                conn.execute(update(chain_studies_table).where(chain_studies_table.c.id == row["id"]).values(position=row_position - 1))
            elif new_position < old_position and new_position <= row_position < old_position:
                conn.execute(update(chain_studies_table).where(chain_studies_table.c.id == row["id"]).values(position=row_position + 1))
        conn.execute(
            update(chain_studies_table)
            .where(chain_studies_table.c.id == target["id"])
            .values(position=int(new_position))
        )
    return ChainStudyResponse(
        id=UUID(target["id"]),
        chain_id=chain_id,
        study_id=study_id,
        study_name=study["name"],
        paradigm=study["paradigm"],
        position=int(new_position),
    )


@router.post("/{chain_id}/invites", response_model=List[ChainInviteResponse])
async def create_chain_invites(
    chain_id: UUID,
    payload: ChainInviteCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> List[ChainInviteResponse]:
    _require_chain_owner(chain_id, owner_id)
    chain_studies = _list_chain_studies(chain_id)
    if not chain_studies:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chain has no studies. Add at least one study before creating invites.")

    count = max(1, int(payload.count or 1))
    invite_rows = []
    responses = []
    for index in range(count):
        token = secrets.token_urlsafe(16)
        participant_id = payload.participant_id
        if participant_id and count > 1:
            participant_id = f"{payload.participant_id}_{index + 1}"
        invite_rows.append(
            {
                "token": token,
                "chain_id": str(chain_id),
                "participant_id": participant_id,
                "created_at": utcnow_iso(),
                "chain_session_id": None,
            }
        )
        responses.append(ChainInviteResponse(token=token, chain_id=chain_id, participant_id=participant_id))

    with connect() as conn:
        conn.execute(chain_invites_table.insert(), invite_rows)
    return responses


@public_router.post("/{token}/start", response_model=ChainSessionStartResponse)
async def start_chain_session(token: str) -> ChainSessionStartResponse:
    invite = _get_chain_invite(token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invite token")

    chain = _get_chain(invite["chain_id"])
    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")

    chain_studies = _list_chain_studies(chain["id"])
    if not chain_studies:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chain has no studies")

    if invite.get("chain_session_id"):
        chain_session = _get_chain_session(invite["chain_session_id"])
        if chain_session is None or chain_session.get("current_session_id") is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stored chain session is invalid")
        session_payload = get_session_start_payload(chain_session["current_session_id"])
        return _chain_start_response(chain_session, chain, session_payload)

    participant_id = invite.get("participant_id") or token
    first_study_id = chain_studies[0]["study_id"]
    session_payload = create_session(first_study_id, participant_id)
    chain_session_id = uuid4()
    chain_session_row = {
        "id": str(chain_session_id),
        "chain_id": str(chain["id"]),
        "invite_token": token,
        "participant_id": participant_id,
        "current_position": 0,
        "current_session_id": str(session_payload.session_id),
        "status": ChainStatus.IN_PROGRESS.value,
        "started_at": utcnow_iso(),
        "completed_at": None,
    }
    with connect() as conn:
        conn.execute(chain_sessions_table.insert().values(**chain_session_row))
        conn.execute(
            update(chain_invites_table)
            .where(chain_invites_table.c.token == token)
            .values(chain_session_id=str(chain_session_id))
        )
    chain_session = _get_chain_session(chain_session_id)
    return _chain_start_response(chain_session, chain, session_payload)


@public_router.post("/{token}/next", response_model=ChainSessionStartResponse)
async def advance_chain_session(token: str) -> ChainSessionStartResponse:
    invite = _get_chain_invite(token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invite token")
    if not invite.get("chain_session_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active chain session for this invite. Call /start first.")

    chain_session = _get_chain_session(invite["chain_session_id"])
    if chain_session is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active chain session for this invite. Call /start first.")

    chain = _get_chain(chain_session["chain_id"])
    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")
    chain_studies = _list_chain_studies(chain["id"])

    next_position = int(chain_session["current_position"]) + 1
    if next_position >= len(chain_studies):
        chain_session["status"] = ChainStatus.COMPLETED
        chain_session["completed_at"] = datetime.now(timezone.utc)
        _save_chain_session(chain_session)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chain is already complete. No more studies.")

    next_study_id = chain_studies[next_position]["study_id"]
    session_payload = create_session(next_study_id, chain_session["participant_id"])
    chain_session["current_position"] = next_position
    chain_session["current_session_id"] = session_payload.session_id
    if next_position == len(chain_studies) - 1:
        chain_session["status"] = ChainStatus.IN_PROGRESS
    _save_chain_session(chain_session)
    return _chain_start_response(chain_session, chain, session_payload)


@public_router.get("/{token}/status", response_model=ChainSessionResponse)
async def get_chain_session_status(token: str) -> ChainSessionResponse:
    invite = _get_chain_invite(token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invite token")
    if not invite.get("chain_session_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No chain session found for this invite")

    chain_session = _get_chain_session(invite["chain_session_id"])
    if chain_session is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No chain session found for this invite")
    chain = _get_chain(chain_session["chain_id"])
    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")

    return ChainSessionResponse(
        id=chain_session["id"],
        chain_id=chain["id"],
        chain_name=chain["name"],
        current_position=chain_session["current_position"],
        total_studies=len(_list_chain_studies(chain["id"])),
        current_session_id=chain_session.get("current_session_id"),
        status=chain_session["status"],
        started_at=chain_session["started_at"],
        completed_at=chain_session.get("completed_at"),
    )


@router.delete("/{chain_id}/sessions/{chain_session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chain_session(
    chain_id: UUID,
    chain_session_id: UUID,
    owner_id: UUID = Depends(get_required_owner),
):
    _require_chain_owner(chain_id, owner_id)
    chain_session = _get_chain_session(chain_session_id)
    if chain_session is None or chain_session["chain_id"] != chain_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain session not found")

    chain_study_ids = {chain_study["study_id"] for chain_study in _list_chain_studies(chain_id)}
    for study_id in chain_study_ids:
        for session in list_sessions_for_study(study_id):
            if session.get("participant_id") == chain_session.get("participant_id"):
                delete_session_record(session["id"])

    with connect() as conn:
        conn.execute(delete(chain_sessions_table).where(chain_sessions_table.c.id == str(chain_session_id)))


@router.get("/{chain_id}/sessions")
async def get_chain_sessions(chain_id: UUID, owner_id: UUID = Depends(get_required_owner)):
    chain = _require_chain_owner(chain_id, owner_id)
    chain_studies = _list_chain_studies(chain_id)
    chain_study_ids = {chain_study["study_id"] for chain_study in chain_studies}

    participants = []
    for chain_session in _list_chain_sessions(chain_id):
        participant_sessions = []
        for study_id in chain_study_ids:
            for session in list_sessions_for_study(study_id):
                if session.get("participant_id") != chain_session.get("participant_id"):
                    continue
                study = get_study(study_id)
                participant_sessions.append(
                    {
                        "session_id": str(session["id"]),
                        "study_id": str(study_id),
                        "study_name": study["name"] if study else "Unknown",
                        "paradigm": study["paradigm"].value if study else "",
                        "status": session["status"].value,
                        "n_trials": len(get_trials_for_session(session["id"])),
                        "started_at": session["started_at"].isoformat() if session.get("started_at") else None,
                    }
                )

        completed_count = sum(1 for session in participant_sessions if session["status"] == "completed")
        total_studies = len(chain_studies)
        computed_status = "completed" if total_studies and completed_count >= total_studies else "in_progress"
        if computed_status == "completed" and chain_session["status"] != ChainStatus.COMPLETED:
            chain_session["status"] = ChainStatus.COMPLETED
            chain_session["completed_at"] = datetime.now(timezone.utc)
            _save_chain_session(chain_session)

        participants.append(
            {
                "chain_session_id": str(chain_session["id"]),
                "participant_id": chain_session["participant_id"],
                "status": computed_status,
                "started_at": chain_session["started_at"].isoformat() if chain_session.get("started_at") else None,
                "completed_at": chain_session["completed_at"].isoformat() if chain_session.get("completed_at") else None,
                "current_position": len(participant_sessions),
                "sessions": participant_sessions,
            }
        )

    return jsonable_encoder(
        {
            "chain_id": str(chain_id),
            "chain_name": chain["name"],
            "total_studies": len(chain_studies),
            "participants": participants,
        }
    )


def get_chains_db():
    with connect(readonly=True) as conn:
        rows = fetch_all(conn, select(chains_table))
    return {UUID(row["id"]): _parse_chain(row) for row in rows}


def get_chain_studies_db():
    with connect(readonly=True) as conn:
        rows = fetch_all(conn, ordered_select(chain_studies_table, chain_studies_table.c.chain_id, chain_studies_table.c.position))
    grouped: dict[UUID, list[dict[str, Any]]] = {}
    studies_db = get_studies_db()
    for row in rows:
        study = studies_db.get(UUID(row["study_id"]))
        if study is None:
            continue
        grouped.setdefault(UUID(row["chain_id"]), []).append(_parse_chain_study(row, study))
    return grouped


def get_chain_invites_db():
    with connect(readonly=True) as conn:
        rows = fetch_all(conn, select(chain_invites_table))
    return {row["token"]: _parse_chain_invite(row) for row in rows}


def get_chain_sessions_db():
    with connect(readonly=True) as conn:
        rows = fetch_all(conn, select(chain_sessions_table))
    return {UUID(row["id"]): _parse_chain_session(row) for row in rows}
