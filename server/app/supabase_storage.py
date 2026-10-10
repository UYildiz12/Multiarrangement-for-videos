"""
Helpers for study-scoped objects in Supabase Storage: signed upload URLs and
deletion. Both use the service-role key, which never leaves the server.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import parse_qs, quote, urlparse


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


class StorageNotConfiguredError(RuntimeError):
    """SUPABASE_URL or the service-role key is missing on this server."""


class StorageRequestError(RuntimeError):
    """Supabase Storage rejected or did not answer a request."""


def study_storage_prefix(owner_id: object, study_id: object) -> str:
    """Folder that holds every object of a study (deleted with the study)."""
    return f"owners/{owner_id}/studies/{study_id}/"


def create_signed_upload_url(path: str) -> dict[str, str]:
    """Ask Supabase Storage for a one-time signed upload URL for *path*.

    Mirrors supabase-js ``createSignedUploadUrl``. The browser can upload this
    single object with the returned token, so the public anon key needs no
    write access to the bucket. Returns ``path``, ``token`` and ``signed_url``.
    """
    base_url = _supabase_url()
    service_key = _service_role_key()
    if not base_url or not service_key:
        raise StorageNotConfiguredError("Supabase Storage is not configured on this server")

    request = urllib.request.Request(
        url=f"{base_url}/storage/v1/object/upload/sign/{storage_bucket()}/{quote(path)}",
        data=b"{}",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raise StorageRequestError(f"Supabase Storage returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise StorageRequestError("Could not get a signed upload URL from Supabase Storage") from exc

    relative_url = str(payload.get("url") or "")
    token = parse_qs(urlparse(relative_url).query).get("token", [""])[0]
    if not token:
        raise StorageRequestError("Supabase Storage did not return an upload token")
    return {
        "path": path,
        "token": token,
        "signed_url": f"{base_url}/storage/v1{relative_url}",
    }


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
