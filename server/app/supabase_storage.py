"""
Helpers for deleting study-scoped objects from Supabase Storage.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse


_LOCAL_SUPABASE_HOSTS = {"localhost", "127.0.0.1", "::1"}


def storage_bucket() -> str:
    return (
        os.getenv("SUPABASE_STORAGE_BUCKET")
        or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET")
        or "stimuli"
    )


def _supabase_url() -> str:
    url = (
        os.getenv("SUPABASE_URL")
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        or ""
    ).rstrip("/")
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if parsed.scheme == "http" and parsed.hostname in _LOCAL_SUPABASE_HOSTS:
        return url
    raise RuntimeError("SUPABASE_URL must be HTTPS, except for localhost development")


def _service_role_key() -> str:
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
        or ""
    ).strip()


def delete_storage_paths(paths: list[str]) -> dict[str, object]:
    unique_paths = sorted({path for path in paths if path})
    if not unique_paths:
        return {"status": "noop", "deleted": []}

    base_url = _supabase_url()
    service_key = _service_role_key()
    if not base_url or not service_key:
        return {
            "status": "skipped_unconfigured",
            "deleted": [],
            "paths": unique_paths,
        }

    request = urllib.request.Request(
        url=f"{base_url}/storage/v1/object/{storage_bucket()}",
        data=json.dumps({"prefixes": unique_paths}).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
            return {
                "status": "deleted",
                "deleted": payload if isinstance(payload, list) else unique_paths,
                "paths": unique_paths,
            }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {
            "status": "error",
            "deleted": [],
            "paths": unique_paths,
            "detail": detail,
            "http_status": exc.code,
        }
