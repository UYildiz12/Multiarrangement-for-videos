"""
Deletion of a study's stored objects in every configured backend.

Uploads go to Cloudflare R2 when it is configured and to Supabase Storage
otherwise, and a study may hold objects from before a switch, so deletion
asks both; deleting a key that does not exist is not an error in either.
"""

from __future__ import annotations

from app import r2_storage, supabase_storage


def delete_storage_paths(paths: list[str]) -> dict[str, object]:
    result = supabase_storage.delete_storage_paths(paths)
    if r2_storage.r2_configured():
        result = {**result, "r2": r2_storage.delete_keys(paths)}
    return result
