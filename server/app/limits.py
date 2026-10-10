"""
Configurable limits for the hosted service.

Every limit is read from the environment when it is checked, so operators can
tune them on Railway without a code change (and tests can override them).
Setting a limit to 0 disables it; unparsable values fall back to the default.
"""

from __future__ import annotations

import os

MB = 1024 * 1024
GB = 1024 * MB


def env_int(name: str, default: int) -> int:
    """Return a non-negative integer from the environment, or *default*."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def format_bytes(n: int) -> str:
    """Human-readable size for error messages, e.g. ``5 MB``."""
    if n >= GB:
        return f"{round(n / GB, 1):g} GB"
    if n >= MB:
        return f"{round(n / MB, 1):g} MB"
    return f"{n} bytes"


def max_request_bytes() -> int:
    """Largest request body the API accepts (media never passes through the API)."""
    return env_int("MAX_REQUEST_BYTES", 5 * MB)


def max_studies_per_owner() -> int:
    return env_int("MAX_STUDIES_PER_OWNER", 100)


def max_stimuli_per_study() -> int:
    return env_int("MAX_STIMULI_PER_STUDY", 300)


def max_upload_bytes() -> int:
    """Largest single media file an experimenter may upload to Storage."""
    return env_int("MAX_UPLOAD_BYTES", 20 * MB)


def max_storage_bytes_per_owner() -> int:
    """Total upload volume allowed per experimenter key."""
    return env_int("MAX_STORAGE_BYTES_PER_OWNER", 150 * MB)


def max_storage_bytes_total() -> int:
    """Upload volume allowed across all experimenter keys (the free Supabase plan has 1 GB of storage)."""
    return env_int("MAX_STORAGE_BYTES_TOTAL", 800 * MB)
