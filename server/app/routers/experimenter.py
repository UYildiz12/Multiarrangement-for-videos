"""
Experimenter key management.

Keys are self-generated random tokens.  The server never stores them — it
derives a deterministic ``owner_id`` (UUID-5) from each key so that studies
and chains can be associated with whoever holds the same key.
"""

import os
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status

router = APIRouter(prefix="/experimenter", tags=["experimenter"])

# Namespace for UUID-5 derivation (arbitrary but fixed)
_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_LOCAL_DEV_OWNER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


def owner_id_from_key(key: str) -> uuid.UUID:
    """Deterministic owner_id from an experimenter key."""
    return uuid.uuid5(_NAMESPACE, key.strip())


def is_local_dev_bypass_auth_enabled() -> bool:
    """Return True when key auth is disabled for local development."""
    value = os.getenv("LOCAL_DEV_BYPASS_AUTH", "")
    return value.strip().lower() in _TRUTHY_ENV_VALUES


def local_dev_owner_id() -> uuid.UUID:
    """Stable owner_id used when LOCAL_DEV_BYPASS_AUTH is enabled."""
    return _LOCAL_DEV_OWNER_ID


def get_optional_owner(
    x_experimenter_key: Optional[str] = Header(default=None, alias="x-experimenter-key"),
) -> Optional[uuid.UUID]:
    """FastAPI dependency — returns owner_id when a key header is present."""
    if x_experimenter_key and x_experimenter_key.strip():
        return owner_id_from_key(x_experimenter_key)
    if is_local_dev_bypass_auth_enabled():
        return local_dev_owner_id()
    return None


def get_required_owner(
    x_experimenter_key: Optional[str] = Header(default=None, alias="x-experimenter-key"),
) -> uuid.UUID:
    """FastAPI dependency — requires an experimenter key and returns owner_id."""
    if x_experimenter_key and x_experimenter_key.strip():
        return owner_id_from_key(x_experimenter_key)
    if is_local_dev_bypass_auth_enabled():
        return local_dev_owner_id()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Provide an x-experimenter-key header",
    )


@router.post("/generate-key")
async def generate_key():
    """Generate a new random experimenter key.

    The key is **not** stored on the server.  The caller must save it.
    """
    key = secrets.token_urlsafe(24)  # 32-char URL-safe string
    return {"key": key}
