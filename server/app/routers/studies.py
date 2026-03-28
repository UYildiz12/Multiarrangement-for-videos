"""
Study management endpoints backed by durable storage.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update

from app.routers.experimenter import get_optional_owner, get_required_owner
from app.supabase_storage import delete_storage_paths
from app.schemas import (
    Language,
    MediaType,
    Paradigm,
    StimulusBatchCreate,
    StimulusResponse,
    StudyCreate,
    StudyResponse,
    StudyUpdate,
)
from app.storage import (
    connect,
    fetch_all,
    fetch_one,
    ordered_select,
    stimuli_table,
    studies_table,
    utcnow_iso,
)

router = APIRouter(prefix="/studies", tags=["studies"])


def _parse_study(row: dict, n_stimuli: int | None = None) -> dict:
    return {
        "id": UUID(row["id"]),
        "owner_id": UUID(row["owner_id"]),
        "name": row["name"],
        "description": row.get("description"),
        "paradigm": Paradigm(row["paradigm"]),
        "config": row.get("config_json") or {},
        "language": Language(row.get("language") or "en"),
        "instructions": row.get("instructions_json"),
        "created_at": row["created_at"],
        "n_stimuli": n_stimuli if n_stimuli is not None else 0,
    }


def _parse_stimulus(row: dict) -> dict:
    return {
        "id": UUID(row["id"]),
        "ordinal": row["ordinal"],
        "filename": row["filename"],
        "media_type": MediaType(row["media_type"]),
        "media_url": row.get("media_url"),
        "thumbnail_url": row.get("thumbnail_url"),
        "media_storage_path": row.get("media_storage_path"),
        "thumbnail_storage_path": row.get("thumbnail_storage_path"),
        "duration_seconds": row.get("duration_seconds"),
    }


def get_study(study_id: UUID | str) -> dict | None:
    with connect(readonly=True) as conn:
        row = fetch_one(conn, select(studies_table).where(studies_table.c.id == str(study_id)))
        if row is None:
            return None
        n_stimuli = conn.execute(
            select(stimuli_table.c.id).where(stimuli_table.c.study_id == str(study_id))
        ).fetchall()
        return _parse_study(row, len(n_stimuli))


def list_stimuli_for_study(study_id: UUID | str) -> list[dict]:
    with connect(readonly=True) as conn:
        rows = fetch_all(
            conn,
            ordered_select(stimuli_table, stimuli_table.c.ordinal).where(
                stimuli_table.c.study_id == str(study_id)
            ),
        )
    return [_parse_stimulus(row) for row in rows]


def list_storage_paths_for_study(study_id: UUID | str) -> list[str]:
    paths: set[str] = set()
    for stimulus in list_stimuli_for_study(study_id):
        media_path = stimulus.get("media_storage_path")
        thumb_path = stimulus.get("thumbnail_storage_path")
        if media_path:
            paths.add(media_path)
        if thumb_path:
            paths.add(thumb_path)
    return sorted(paths)


@router.get("", response_model=List[StudyResponse])
async def list_studies(owner_id: Optional[UUID] = Depends(get_optional_owner)):
    if owner_id is None:
        return []
    with connect(readonly=True) as conn:
        study_rows = fetch_all(
            conn,
            ordered_select(studies_table, studies_table.c.created_at).where(
                studies_table.c.owner_id == str(owner_id)
            ),
        )
        out = []
        for row in study_rows:
            n_stimuli = len(
                conn.execute(
                    select(stimuli_table.c.id).where(stimuli_table.c.study_id == row["id"])
                ).fetchall()
            )
            out.append(StudyResponse(**_parse_study(row, n_stimuli)))
    return out


@router.post("", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
async def create_study(
    study: StudyCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> StudyResponse:
    study_id = str(uuid4())
    payload = {
        "id": study_id,
        "owner_id": str(owner_id),
        "name": study.name,
        "description": study.description,
        "paradigm": study.paradigm.value,
        "config_json": study.config,
        "language": study.language.value,
        "instructions_json": study.instructions,
        "created_at": utcnow_iso(),
    }
    with connect() as conn:
        conn.execute(studies_table.insert().values(**payload))
    return StudyResponse(**_parse_study(payload, 0))


@router.get("/{study_id}", response_model=StudyResponse)
async def get_study_endpoint(study_id: UUID) -> StudyResponse:
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    return StudyResponse(**study)


@router.patch("/{study_id}", response_model=StudyResponse)
async def update_study(
    study_id: UUID,
    update_payload: StudyUpdate,
    owner_id: UUID = Depends(get_required_owner),
) -> StudyResponse:
    existing = get_study(study_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if existing["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    changes = {}
    if update_payload.name is not None:
        changes["name"] = update_payload.name
    if update_payload.description is not None:
        changes["description"] = update_payload.description
    if update_payload.config is not None:
        changes["config_json"] = update_payload.config
    if update_payload.language is not None:
        changes["language"] = update_payload.language.value
    if update_payload.instructions is not None:
        changes["instructions_json"] = update_payload.instructions

    with connect() as conn:
        if changes:
            conn.execute(
                update(studies_table)
                .where(studies_table.c.id == str(study_id))
                .values(**changes)
            )

    refreshed = get_study(study_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    return StudyResponse(**refreshed)


@router.delete("/{study_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_study(
    study_id: UUID,
    owner_id: UUID = Depends(get_required_owner),
):
    existing = get_study(study_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if existing["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    delete_storage_paths(list_storage_paths_for_study(study_id))
    with connect() as conn:
        conn.execute(delete(studies_table).where(studies_table.c.id == str(study_id)))


@router.get("/{study_id}/stimuli", response_model=List[StimulusResponse])
async def list_stimuli(study_id: UUID) -> List[StimulusResponse]:
    if get_study(study_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    return [StimulusResponse(**row) for row in list_stimuli_for_study(study_id)]


@router.post("/{study_id}/stimuli", response_model=List[StimulusResponse])
async def register_stimuli(
    study_id: UUID,
    payload: StimulusBatchCreate,
    owner_id: UUID = Depends(get_required_owner),
) -> List[StimulusResponse]:
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if study["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    existing = list_stimuli_for_study(study_id)
    existing_ordinals = {stim["ordinal"] for stim in existing}
    new_rows = []
    for stim in payload.stimuli:
        if stim.ordinal in existing_ordinals:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate ordinal {stim.ordinal}",
            )
        new_rows.append(
            {
                "id": str(uuid4()),
                "study_id": str(study_id),
                "ordinal": stim.ordinal,
                "filename": stim.filename,
                "media_type": stim.media_type.value,
                "media_url": stim.media_url,
                "thumbnail_url": stim.thumbnail_url,
                "media_storage_path": stim.media_storage_path,
                "thumbnail_storage_path": stim.thumbnail_storage_path,
                "duration_seconds": stim.duration_seconds,
            }
        )
        existing_ordinals.add(stim.ordinal)

    with connect() as conn:
        if new_rows:
            conn.execute(stimuli_table.insert(), new_rows)

    all_rows = list_stimuli_for_study(study_id)
    return [StimulusResponse(**row) for row in all_rows]


def get_studies_db() -> dict:
    with connect(readonly=True) as conn:
        rows = fetch_all(conn, select(studies_table))
    return {UUID(row["id"]): _parse_study(row) for row in rows}


def get_stimuli_db() -> dict:
    with connect(readonly=True) as conn:
        rows = fetch_all(conn, ordered_select(stimuli_table, stimuli_table.c.study_id, stimuli_table.c.ordinal))
    grouped: dict[UUID, list[dict]] = {}
    for row in rows:
        grouped.setdefault(UUID(row["study_id"]), []).append(_parse_stimulus(row))
    return grouped
