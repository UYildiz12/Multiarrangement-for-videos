"""
Cloudflare R2 storage: SigV4 signing (AWS test vectors), presigned uploads and
reads, the total-storage cap, link checks and deletion (network mocked).
"""

import datetime as dt
from urllib.parse import parse_qs, urlparse

import pytest

from app import r2_storage
from app.routers import studies as studies_router
from app.schemas import StimulusResponse

AK, SK = "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
MAY_24_2013 = dt.datetime(2013, 5, 24, tzinfo=dt.timezone.utc)


# ── signing: the worked examples of the Amazon S3 SigV4 documentation ────

def test_presigned_get_matches_the_aws_example():
    url = r2_storage.presign("GET", "examplebucket.s3.amazonaws.com", "/test.txt", AK, SK, 86400, MAY_24_2013,
                             region="us-east-1")
    assert url.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404")


def test_header_signatures_match_the_aws_examples():
    get = r2_storage.authorization_headers("GET", "examplebucket.s3.amazonaws.com", "/test.txt", "", b"", AK, SK,
                                           MAY_24_2013, region="us-east-1", extra_headers={"range": "bytes=0-9"})
    assert get["authorization"].endswith("f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")
    put = r2_storage.authorization_headers(
        "PUT", "examplebucket.s3.amazonaws.com", "/test%24file.text", "", b"Welcome to Amazon S3.", AK, SK,
        MAY_24_2013, region="us-east-1",
        extra_headers={"date": "Fri, 24 May 2013 00:00:00 GMT", "x-amz-storage-class": "REDUCED_REDUNDANCY"})
    assert put["authorization"].endswith("98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd")


# ── configured service ────────────────────────────────────────────────────

@pytest.fixture
def r2_env(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", AK)
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", SK)
    monkeypatch.setenv("R2_BUCKET", "stimuli")

    def no_supabase(path):
        pytest.fail("Supabase must not be used when R2 is configured")

    monkeypatch.setattr(studies_router, "create_signed_upload_url", no_supabase)


def _study(client, sample_study_data):
    resp = client.post("/api/v1/studies", json=sample_study_data)
    assert resp.status_code == 201
    return resp.json()


def _upload(client, study_id, **overrides):
    body = {"filename": "clip.mp4", "content_type": "video/mp4", "size_bytes": 1234, "kind": "media", "index": 0}
    body.update(overrides)
    return client.post(f"/api/v1/studies/{study_id}/uploads", json=body)


def test_upload_url_binds_type_and_size_and_registration_stores_a_reference(client, r2_env, sample_study_data):
    study = _study(client, sample_study_data)
    resp = _upload(client, study["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "r2"
    prefix = f"owners/{study['owner_id']}/studies/{study['id']}/"
    assert data["path"].startswith(prefix)
    put = urlparse(data["signed_url"])
    assert put.netloc == "acct123.r2.cloudflarestorage.com"
    assert put.path == "/stimuli/" + data["path"]
    assert parse_qs(put.query)["X-Amz-SignedHeaders"] == ["content-length;content-type;host"]
    assert data["media_url"] == "r2:" + data["path"]
    assert "X-Amz-Signature=" in data["read_url"]

    registered = client.post(f"/api/v1/studies/{study['id']}/stimuli", json={"stimuli": [{
        "ordinal": 0, "filename": "clip", "media_type": "video",
        "media_url": data["media_url"], "media_storage_path": data["path"]}]})
    assert registered.status_code == 200
    served = registered.json()[0]["media_url"]
    assert served.startswith("https://acct123.r2.cloudflarestorage.com/stimuli/" + prefix)
    assert parse_qs(urlparse(served).query)["X-Amz-Expires"] == ["86400"]
    listed = client.get(f"/api/v1/studies/{study['id']}/stimuli").json()[0]["media_url"]
    assert listed.startswith("https://acct123.r2.cloudflarestorage.com/")


def test_references_outside_the_study_folder_are_rejected(client, r2_env, sample_study_data):
    study = _study(client, sample_study_data)
    other = "r2:owners/someone-else/studies/x/media/000_secret.mp4"
    resp = client.post(f"/api/v1/studies/{study['id']}/stimuli", json={"stimuli": [{
        "ordinal": 0, "filename": "x", "media_type": "video", "media_url": other}]})
    assert resp.status_code == 400


def test_references_stay_unresolved_without_r2(monkeypatch):
    for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(name, raising=False)
    stim = StimulusResponse(id="00000000-0000-0000-0000-000000000001", ordinal=0, filename="a",
                            media_type="video", media_url="r2:owners/a/b.mp4", thumbnail_url="/audio.png")
    assert stim.media_url == "r2:owners/a/b.mp4"
    assert stim.thumbnail_url == "/audio.png"


# ── shared cap and links ──────────────────────────────────────────────────

def test_total_storage_cap_points_to_links(client, r2_env, monkeypatch, sample_study_data):
    monkeypatch.setenv("MAX_STORAGE_BYTES_TOTAL", "2000")
    study = _study(client, sample_study_data)
    assert _upload(client, study["id"], size_bytes=1500).status_code == 201
    full = _upload(client, study["id"], size_bytes=600, index=1)
    assert full.status_code == 507
    assert "Paste links" in full.json()["detail"]


@pytest.mark.parametrize("url,ok", [
    ("https://osf.io/abc/download", True),
    ("/videos/clip.mp4", True),
    ("blob:https://multiarrangement.com/1234", True),
    ("javascript:alert(1)", False),
    ("file:///C:/clip.mp4", False),
    ("//evil.example/clip.mp4", False),
    ("ftp://host/clip.mp4", False),
])
def test_linked_media_must_be_web_addresses(client, sample_study_data, url, ok):
    study = _study(client, sample_study_data)
    resp = client.post(f"/api/v1/studies/{study['id']}/stimuli", json={"stimuli": [{
        "ordinal": 0, "filename": "clip", "media_type": "video", "media_url": url}]})
    assert (resp.status_code == 200) == ok


# ── deletion ──────────────────────────────────────────────────────────────

def test_delete_keys_sends_one_signed_batch(monkeypatch, r2_env):
    sent = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        sent.append(request)
        return Response()

    monkeypatch.setattr(r2_storage.urllib.request, "urlopen", fake_urlopen)
    result = r2_storage.delete_keys(["owners/a/b<1>.mp4", "owners/a/c.png", "owners/a/c.png", ""])
    assert result["status"] == "deleted"
    assert result["deleted"] == ["owners/a/b<1>.mp4", "owners/a/c.png"]
    (request,) = sent
    assert request.full_url == "https://acct123.r2.cloudflarestorage.com/stimuli/?delete"
    assert request.get_method() == "POST"
    body = request.data.decode()
    assert "<Key>owners/a/b&lt;1&gt;.mp4</Key>" in body
    assert body.count("<Object>") == 2
    headers = {k.lower(): v for k, v in request.header_items()}
    assert headers["authorization"].startswith("AWS4-HMAC-SHA256 Credential=" + AK)
    assert "content-md5" in headers


def test_study_deletion_also_clears_r2(client, r2_env, monkeypatch, sample_study_data):
    deleted = []

    def fake_delete_keys(keys):
        deleted.extend(keys)
        return {"status": "deleted"}

    monkeypatch.setattr(r2_storage, "delete_keys", fake_delete_keys)
    study = _study(client, sample_study_data)
    path = _upload(client, study["id"]).json()["path"]
    assert client.delete(f"/api/v1/studies/{study['id']}").status_code == 204
    assert path in deleted
