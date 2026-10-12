"""
Study management endpoints backed by durable storage.
"""

from __future__ import annotations

import re
import secrets
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select, update

from app.limits import (
    format_bytes,
    max_stimuli_per_study,
    max_storage_bytes_per_owner,
    max_storage_bytes_total,
    max_studies_per_owner,
    max_upload_bytes,
)
from app.routers.experimenter import get_optional_owner, get_required_owner
from app import r2_storage
from app.object_storage import delete_storage_paths
from app.supabase_storage import (
    StorageNotConfiguredError,
    StorageRequestError,
    create_signed_upload_url,
    storage_bucket,
    study_storage_prefix,
)
from app.schemas import (
    Language,
    MediaType,
    Paradigm,
    SignedUploadRequest,
    SignedUploadResponse,
    StimulusBatchCreate,
    StimulusResponse,
    StudyCreate,
    StudyResponse,
    StudyUpdate,
    UploadKind,
)
from app.storage import (
    connect,
    fetch_all,
    fetch_one,
    ordered_select,
    stimuli_table,
    studies_table,
    uploads_table,
    utcnow_iso,
)

router = APIRouter(prefix="/studies", tags=["studies"])

_ALLOWED_UPLOAD_TYPES = ("video/", "audio/", "image/")


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
    # Also uploads that were never registered as stimuli (e.g. a failed publish).
    with connect(readonly=True) as conn:
        paths.update(
            conn.execute(
                select(uploads_table.c.storage_path).where(uploads_table.c.study_id == str(study_id))
            ).scalars()
        )
    return sorted(paths)


def delete_study_rows(study_id: UUID | str) -> None:
    """Delete a study (its stimuli, sessions and trials cascade) and its upload ledger."""
    with connect() as conn:
        conn.execute(delete(uploads_table).where(uploads_table.c.study_id == str(study_id)))
        conn.execute(delete(studies_table).where(studies_table.c.id == str(study_id)))


def _upload_object_name(payload: SignedUploadRequest) -> str:
    """``media/003_clip_name_<random>.mp4``, the layout the web client used before."""
    stem, dot, ext = payload.filename.rpartition(".")
    if not dot:
        stem, ext = payload.filename, ""
    ext = re.sub(r"[^a-z0-9]", "", ext.lower())[:10] or "bin"
    label = re.sub(r"[^A-Za-z0-9_-]+", "_", stem)[:80].strip("_") or "file"
    section = "media" if payload.kind == UploadKind.MEDIA else "thumbs"
    return f"{section}/{payload.index:03d}_{label}_{secrets.token_hex(8)}.{ext}"


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
    repeats = (study.config or {}).get("pair_repeats", 1)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or not 1 <= repeats <= 4:
        raise HTTPException(
            status_code=422,  # Unprocessable Content
            detail="pair_repeats must be a whole number from 1 to 4.",
        )
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
    limit = max_studies_per_owner()
    with connect() as conn:
        if limit:
            owned = conn.execute(
                select(func.count())
                .select_from(studies_table)
                .where(studies_table.c.owner_id == str(owner_id))
            ).scalar_one()
            if owned >= limit:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Study limit reached: an experimenter key can own at most {limit} studies. "
                        "Delete studies you no longer need and try again."
                    ),
                )
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
    delete_study_rows(study_id)


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
    limit = max_stimuli_per_study()
    if limit and len(existing) + len(payload.stimuli) > limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stimulus limit reached: a study can have at most {limit} stimuli.",
        )

    # Study deletion removes these paths with the service-role key, so they must
    # stay inside this study's folder.
    prefix = study_storage_prefix(study["owner_id"], study_id)
    for stim in payload.stimuli:
        refs = [u[len(r2_storage.REF_PREFIX):] for u in (stim.media_url, stim.thumbnail_url)
                if u and u.startswith(r2_storage.REF_PREFIX)]
        for path in (stim.media_storage_path, stim.thumbnail_storage_path, *refs):
            if path and (not path.startswith(prefix) or ".." in path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Storage paths must be inside this study's folder ({prefix})",
                )

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


@router.post(
    "/{study_id}/uploads",
    response_model=SignedUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_signed_upload(
    study_id: UUID,
    payload: SignedUploadRequest,
    owner_id: UUID = Depends(get_required_owner),
) -> SignedUploadResponse:
    """Issue a signed upload URL for one file of this study.

    The file goes to Cloudflare R2 when it is configured (the presigned PUT
    binds the declared type and size) and to Supabase Storage otherwise (the
    bucket's own size limit and MIME allow-list enforce them). A plain ``def``
    so the blocking Storage request runs in the threadpool.
    """
    study = get_study(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if study["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your study")

    content_type = payload.content_type.split(";")[0].strip().lower()
    if not content_type.startswith(_ALLOWED_UPLOAD_TYPES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only video, audio and image files can be uploaded.",
        )
    max_bytes = max_upload_bytes()
    if max_bytes and payload.size_bytes > max_bytes:
        raise HTTPException(
            status_code=413,  # Content Too Large (constant name differs across Starlette versions)
            detail=f"File too large: the limit is {format_bytes(max_bytes)} per file.",
        )

    with connect(readonly=True) as conn:
        same_kind = conn.execute(
            select(func.count())
            .select_from(uploads_table)
            .where(uploads_table.c.study_id == str(study_id))
            .where(uploads_table.c.kind == payload.kind.value)
        ).scalar_one()
        used_bytes = int(
            conn.execute(
                select(func.coalesce(func.sum(uploads_table.c.size_bytes), 0)).where(
                    uploads_table.c.owner_id == str(owner_id)
                )
            ).scalar_one()
        )
        total_bytes = int(
            conn.execute(select(func.coalesce(func.sum(uploads_table.c.size_bytes), 0))).scalar_one()
        )

    max_files = max_stimuli_per_study()
    if max_files and same_kind >= max_files:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stimulus limit reached: a study can have at most {max_files} stimuli.",
        )
    quota = max_storage_bytes_per_owner()
    if quota and used_bytes + payload.size_bytes > quota:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Storage quota exceeded: this experimenter key has used {format_bytes(used_bytes)} "
                f"of {format_bytes(quota)}. Delete studies you no longer need to free space."
            ),
        )

    total_cap = max_storage_bytes_total()
    if total_cap and total_bytes + payload.size_bytes > total_cap:
        raise HTTPException(
            status_code=507,  # Insufficient Storage
            detail=(
                "The service's shared upload storage is full. Paste links to files you host yourself "
                "(for example on OSF or a university web server) instead of uploading them."
            ),
        )

    path = study_storage_prefix(owner_id, study_id) + _upload_object_name(payload)
    if r2_storage.r2_configured():
        response = SignedUploadResponse(
            provider="r2",
            path=path,
            signed_url=r2_storage.create_upload_url(path, content_type, payload.size_bytes),
            bucket=r2_storage._env("R2_BUCKET"),
            media_url=r2_storage.ref_for(path),
            read_url=r2_storage.read_url(path),
        )
        _record_upload(path, owner_id, study_id, payload, content_type)
        return response
    try:
        signed = create_signed_upload_url(path)
    except StorageNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hosted media uploads are not configured on this server.",
        ) from None
    except StorageRequestError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not prepare the upload. Please try again.",
        ) from None

    _record_upload(path, owner_id, study_id, payload, content_type)
    return SignedUploadResponse(provider="supabase", bucket=storage_bucket(), **signed)


def _record_upload(path: str, owner_id: UUID, study_id: UUID, payload: SignedUploadRequest, content_type: str) -> None:
    with connect() as conn:
        conn.execute(
            uploads_table.insert().values(
                storage_path=path,
                owner_id=str(owner_id),
                study_id=str(study_id),
                kind=payload.kind.value,
                content_type=content_type,
                size_bytes=payload.size_bytes,
                created_at=utcnow_iso(),
            )
        )


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
