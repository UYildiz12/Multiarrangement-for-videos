"""
Durable storage for the hosted Multiarrangement service.

The app keeps experimenter-key auth, but stores hosted state in a relational
database so studies, invites, sessions, and results survive backend restarts.
The same code supports Supabase Postgres in deployment and SQLite in tests /
local development.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import (
    JSON,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    delete,
    event,
    select,
)
from sqlalchemy.engine import Connection, Engine, RowMapping


metadata = MetaData()

studies_table = Table(
    "studies",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("owner_id", String(36), nullable=False, index=True),
    Column("name", String(200), nullable=False),
    Column("description", String, nullable=True),
    Column("paradigm", String(32), nullable=False),
    Column("config_json", JSON, nullable=False, default=dict),
    Column("language", String(8), nullable=False, default="en"),
    Column("instructions_json", JSON, nullable=True),
    Column("created_at", String(64), nullable=False),
)

stimuli_table = Table(
    "stimuli",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("study_id", String(36), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("filename", String, nullable=False),
    Column("media_type", String(16), nullable=False),
    Column("media_url", String, nullable=True),
    Column("thumbnail_url", String, nullable=True),
    Column("duration_seconds", Float, nullable=True),
    UniqueConstraint("study_id", "ordinal", name="uq_stimuli_study_ordinal"),
)

sessions_table = Table(
    "sessions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("study_id", String(36), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("participant_id", String(100), nullable=False),
    Column("status", String(32), nullable=False),
    Column("current_trial_index", Integer, nullable=False, default=0),
    Column("started_at", String(64), nullable=False),
    Column("completed_at", String(64), nullable=True),
    Column("state_json", JSON, nullable=False, default=dict),
)

trials_table = Table(
    "trials",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("session_id", String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("trial_index", Integer, nullable=False),
    Column("subset_indices_json", JSON, nullable=False),
    Column("positions_json", JSON, nullable=True),
    Column("rating", Integer, nullable=True),
    Column("duration_seconds", Float, nullable=False),
    Column("started_at", String(64), nullable=False),
    Column("completed_at", String(64), nullable=True),
    UniqueConstraint("session_id", "trial_index", name="uq_trials_session_index"),
)

invites_table = Table(
    "invites",
    metadata,
    Column("token", String(255), primary_key=True),
    Column("study_id", String(36), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("participant_id", String(100), nullable=True),
    Column("used_session_id", String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
)

chains_table = Table(
    "chains",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("owner_id", String(36), nullable=False, index=True),
    Column("name", String(200), nullable=False),
    Column("description", String, nullable=True),
    Column("created_at", String(64), nullable=False),
)

chain_studies_table = Table(
    "chain_studies",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("chain_id", String(36), ForeignKey("chains.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("study_id", String(36), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    UniqueConstraint("chain_id", "position", name="uq_chain_studies_position"),
    UniqueConstraint("chain_id", "study_id", name="uq_chain_studies_study"),
)

chain_sessions_table = Table(
    "chain_sessions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("chain_id", String(36), ForeignKey("chains.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("invite_token", String(255), nullable=False, index=True),
    Column("participant_id", String(100), nullable=False),
    Column("current_position", Integer, nullable=False, default=0),
    Column("current_session_id", String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
    Column("status", String(32), nullable=False),
    Column("started_at", String(64), nullable=False),
    Column("completed_at", String(64), nullable=True),
)

chain_invites_table = Table(
    "chain_invites",
    metadata,
    Column("token", String(255), primary_key=True),
    Column("chain_id", String(36), ForeignKey("chains.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("participant_id", String(100), nullable=True),
    Column("created_at", String(64), nullable=False),
    Column("chain_session_id", String(36), ForeignKey("chain_sessions.id", ondelete="SET NULL"), nullable=True),
)

Index("ix_sessions_study_participant", sessions_table.c.study_id, sessions_table.c.participant_id)
Index("ix_chain_sessions_chain_participant", chain_sessions_table.c.chain_id, chain_sessions_table.c.participant_id)

_engine: Engine | None = None
_engine_url: str | None = None


def _default_sqlite_url() -> str:
    db_path = Path(__file__).resolve().parents[1] / "multiarrangement_hosted.sqlite3"
    return f"sqlite:///{db_path.as_posix()}"


def get_database_url() -> str:
    return (
        os.getenv("SUPABASE_DB_URL")
        or os.getenv("DATABASE_URL")
        or _default_sqlite_url()
    )


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:")


def _create_engine(url: str) -> Engine:
    kwargs: dict[str, Any] = {"future": True}
    if _is_sqlite(url):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)

    if _is_sqlite(url):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore[no-redef]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_engine() -> Engine:
    global _engine, _engine_url
    url = get_database_url()
    if _engine is None or _engine_url != url:
        _engine = _create_engine(url)
        _engine_url = url
    return _engine


def init_db() -> None:
    metadata.create_all(get_engine())


def reset_db() -> None:
    engine = get_engine()
    metadata.drop_all(engine)
    metadata.create_all(engine)


@contextmanager
def connect(readonly: bool = False) -> Iterator[Connection]:
    engine = get_engine()
    if readonly:
        with engine.connect() as conn:
            yield conn
    else:
        with engine.begin() as conn:
            yield conn


def row_to_dict(row: RowMapping | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def fetch_one(conn: Connection, statement) -> dict[str, Any] | None:
    row = conn.execute(statement).mappings().first()
    return row_to_dict(row)


def fetch_all(conn: Connection, statement) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(statement).mappings().all()]


def clear_all_tables() -> None:
    with connect() as conn:
        for table in (
            chain_invites_table,
            chain_sessions_table,
            chain_studies_table,
            chains_table,
            invites_table,
            trials_table,
            sessions_table,
            stimuli_table,
            studies_table,
        ):
            conn.execute(delete(table))


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ordered_select(table: Table, *order_cols):
    return select(table).order_by(*order_cols)

