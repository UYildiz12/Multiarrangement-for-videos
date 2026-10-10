"""
Signed upload URLs: ownership, size/type checks, caps and quota (Storage mocked).
"""

import json

import pytest
from sqlalchemy import func, select

from app import supabase_storage
from app.routers import studies as studies_router
from app.storage import connect, uploads_table
from app.supabase_storage import StorageRequestError


@pytest.fixture
def signed_paths(monkeypatch):
    """Replace the Supabase call and record the paths it was asked to sign."""
    paths = []

    def fake_create_signed_upload_url(path):
        paths.append(path)
        return {
            "path": path,
            "token": "upload-token",
            "signed_url": f"https://project.supabase.co/storage/v1/object/upload/sign/stimuli/{path}?token=upload-token",
        }

    monkeypatch.setattr(studies_router, "create_signed_upload_url", fake_create_signed_upload_url)
    return paths


def _create_study(client, sample_study_data, headers=None) -> dict:
    resp = client.post("/api/v1/studies", json=sample_study_data, headers=headers or {})
    assert resp.status_code == 201
    return resp.json()


def _request_upload(client, study_id, headers=None, **overrides):
    body = {
        "filename": "clip one.mp4",
        "content_type": "video/mp4",
        "size_bytes": 1000,
        "kind": "media",
        "index": 3,
    }
    body.update(overrides)
    return client.post(f"/api/v1/studies/{study_id}/uploads", json=body, headers=headers or {})


def _ledger_rows() -> int:
    with connect(readonly=True) as conn:
        return conn.execute(select(func.count()).select_from(uploads_table)).scalar_one()


def test_signed_upload_is_scoped_to_the_study_folder(client, signed_paths, sample_study_data):
    study = _create_study(client, sample_study_data)
    resp = _request_upload(client, study["id"])
    assert resp.status_code == 201

    data = resp.json()
    prefix = f"owners/{study['owner_id']}/studies/{study['id']}/"
    assert data["path"].startswith(f"{prefix}media/003_clip_one_")
    assert data["path"].endswith(".mp4")
    assert data["token"] == "upload-token"
    assert data["bucket"] == "stimuli"
    assert signed_paths == [data["path"]]

    # The issued path can be registered as a stimulus as before.
    registered = client.post(
        f"/api/v1/studies/{study['id']}/stimuli",
        json={"stimuli": [{
            "ordinal": 0,
            "filename": "clip one",
            "media_type": "video",
            "media_url": "https://project.supabase.co/storage/v1/object/public/stimuli/" + data["path"],
            "media_storage_path": data["path"],
        }]},
    )
    assert registered.status_code == 200


def test_upload_requires_a_key_and_study_ownership(client, monkeypatch, signed_paths, sample_study_data):
    key_a = client.post("/api/v1/experimenter/generate-key").json()["key"]
    key_b = client.post("/api/v1/experimenter/generate-key").json()["key"]
    study = _create_study(client, sample_study_data, headers={"x-experimenter-key": key_a})
    monkeypatch.delenv("LOCAL_DEV_BYPASS_AUTH")

    assert _request_upload(client, study["id"]).status_code == 401
    assert _request_upload(client, study["id"], headers={"x-experimenter-key": key_b}).status_code == 403
    assert _request_upload(client, study["id"], headers={"x-experimenter-key": key_a}).status_code == 201
    assert len(signed_paths) == 1


def test_upload_checks_declared_size_and_type(client, monkeypatch, signed_paths, sample_study_data):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "5000")
    study_id = _create_study(client, sample_study_data)["id"]

    too_big = _request_upload(client, study_id, size_bytes=5001)
    assert too_big.status_code == 413
    assert "5000 bytes" in too_big.json()["detail"]

    for content_type in ("application/pdf", "text/html", "application/octet-stream"):
        resp = _request_upload(client, study_id, filename="file.bin", content_type=content_type)
        assert resp.status_code == 415

    assert _request_upload(client, study_id, size_bytes=5000).status_code == 201
    assert _request_upload(client, study_id, filename="a.mp3", content_type="audio/mpeg").status_code == 201
    assert _request_upload(client, study_id, filename="a.PNG", content_type="Image/PNG").status_code == 201
    assert len(signed_paths) == 3
    assert signed_paths[-1].endswith(".png")


def test_upload_count_is_capped_per_study(client, monkeypatch, signed_paths, sample_study_data):
    monkeypatch.setenv("MAX_STIMULI_PER_STUDY", "2")
    study_id = _create_study(client, sample_study_data)["id"]

    for index in range(2):
        assert _request_upload(client, study_id, index=index).status_code == 201
    capped = _request_upload(client, study_id, index=2)
    assert capped.status_code == 409
    assert "at most 2 stimuli" in capped.json()["detail"]

    # Video thumbnails are counted separately from media files.
    thumb = _request_upload(client, study_id, kind="thumbnail", filename="clip_thumb.jpg", content_type="image/jpeg")
    assert thumb.status_code == 201
    assert "/thumbs/" in thumb.json()["path"]


def test_storage_quota_per_owner_is_released_by_study_deletion(client, monkeypatch, signed_paths, sample_study_data):
    monkeypatch.setenv("MAX_STORAGE_BYTES_PER_OWNER", "1500")
    deleted = {}

    def fake_delete(paths):
        deleted["paths"] = paths
        return {"status": "deleted", "deleted": paths}

    monkeypatch.setattr(studies_router, "delete_storage_paths", fake_delete)
    first_study = _create_study(client, sample_study_data)
    second_study = _create_study(client, sample_study_data)

    first = _request_upload(client, first_study["id"], size_bytes=1000)
    assert first.status_code == 201
    over = _request_upload(client, second_study["id"], size_bytes=600)
    assert over.status_code == 409
    assert "Storage quota exceeded" in over.json()["detail"]
    assert "1500 bytes" in over.json()["detail"]

    # Another experimenter key has its own quota.
    key = client.post("/api/v1/experimenter/generate-key").json()["key"]
    other_study = _create_study(client, sample_study_data, headers={"x-experimenter-key": key})
    other = _request_upload(client, other_study["id"], headers={"x-experimenter-key": key}, size_bytes=1000)
    assert other.status_code == 201

    # Deleting a study removes its uploads (even unregistered ones) and frees quota.
    assert client.delete(f"/api/v1/studies/{first_study['id']}").status_code == 204
    assert deleted["paths"] == [first.json()["path"]]
    assert _request_upload(client, second_study["id"], size_bytes=600).status_code == 201


def test_admin_study_deletion_also_clears_the_upload_ledger(client, monkeypatch, signed_paths, sample_study_data):
    from app.routers import admin as admin_router

    deleted = {}
    monkeypatch.setattr(admin_router, "delete_storage_paths", lambda paths: deleted.setdefault("paths", paths))
    study_id = _create_study(client, sample_study_data)["id"]
    path = _request_upload(client, study_id).json()["path"]
    assert _ledger_rows() == 1

    assert client.delete(f"/api/v1/admin/studies/{study_id}").status_code == 200
    assert deleted["paths"] == [path]
    assert _ledger_rows() == 0


def test_upload_reports_unconfigured_storage(client, monkeypatch, sample_study_data):
    for name in ("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    study_id = _create_study(client, sample_study_data)["id"]

    resp = _request_upload(client, study_id)
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"]
    assert _ledger_rows() == 0


def test_upload_reports_storage_errors(client, monkeypatch, sample_study_data):
    def failing(path):
        raise StorageRequestError("Supabase Storage returned HTTP 500")

    monkeypatch.setattr(studies_router, "create_signed_upload_url", failing)
    study_id = _create_study(client, sample_study_data)["id"]

    assert _request_upload(client, study_id).status_code == 502
    assert _ledger_rows() == 0


def test_upload_endpoint_is_rate_limited_as_upload(client, monkeypatch, signed_paths, sample_study_data):
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "1")
    study_id = _create_study(client, sample_study_data)["id"]
    assert _request_upload(client, study_id).status_code == 201
    assert _request_upload(client, study_id).status_code == 429


def test_create_signed_upload_url_calls_the_storage_api(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "stimuli")
    path = "owners/o/studies/s/media/000_clip_abc.mp4"
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"url": f"/object/upload/sign/stimuli/{path}?token=abc.def"}).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["authorization"] = request.get_header("Authorization")
        captured["apikey"] = request.get_header("Apikey")
        return FakeResponse()

    monkeypatch.setattr(supabase_storage.urllib.request, "urlopen", fake_urlopen)
    result = supabase_storage.create_signed_upload_url(path)

    assert captured == {
        "url": f"https://project.supabase.co/storage/v1/object/upload/sign/stimuli/{path}",
        "method": "POST",
        "authorization": "Bearer service-key",
        "apikey": "service-key",
    }
    assert result == {
        "path": path,
        "token": "abc.def",
        "signed_url": f"https://project.supabase.co/storage/v1/object/upload/sign/stimuli/{path}?token=abc.def",
    }


def test_create_signed_upload_url_requires_configuration(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
    with pytest.raises(supabase_storage.StorageNotConfiguredError):
        supabase_storage.create_signed_upload_url("owners/o/studies/s/media/a.mp4")
