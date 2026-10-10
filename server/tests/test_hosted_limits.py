"""
Request-size limit, security headers, /health/db, invite codes and caps.
"""

import json
import os

from app import limits


def _stimulus(ordinal: int, **extra) -> dict:
    return {"ordinal": ordinal, "filename": f"clip{ordinal}.mp4", "media_type": "video", **extra}


# ── request size ─────────────────────────────────────────────────────────

def test_default_limits(monkeypatch):
    for name in (
        "MAX_REQUEST_BYTES",
        "MAX_STUDIES_PER_OWNER",
        "MAX_STIMULI_PER_STUDY",
        "MAX_UPLOAD_BYTES",
        "MAX_STORAGE_BYTES_PER_OWNER",
        "MAX_STORAGE_BYTES_TOTAL",
    ):
        monkeypatch.delenv(name, raising=False)
    assert limits.max_request_bytes() == 5 * 1024 * 1024
    assert limits.max_studies_per_owner() == 100
    assert limits.max_stimuli_per_study() == 300
    assert limits.max_upload_bytes() == 20 * 1024 * 1024
    assert limits.max_storage_bytes_per_owner() == 150 * 1024 * 1024
    assert limits.max_storage_bytes_total() == 800 * 1024 * 1024

    monkeypatch.setenv("MAX_STUDIES_PER_OWNER", "not-a-number")
    assert limits.max_studies_per_owner() == 100


def test_oversized_request_is_rejected_with_413(client, monkeypatch, sample_study_data):
    monkeypatch.setenv("MAX_REQUEST_BYTES", "2000")
    oversized = dict(sample_study_data, description="x" * 5000)

    resp = client.post("/api/v1/studies", json=oversized)
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"]

    assert client.post("/api/v1/studies", json=sample_study_data).status_code == 201


def test_body_without_content_length_is_also_limited(client, monkeypatch, sample_study_data):
    monkeypatch.setenv("MAX_REQUEST_BYTES", "2000")
    body = json.dumps(dict(sample_study_data, description="x" * 5000)).encode()

    def chunks():
        for start in range(0, len(body), 500):
            yield body[start:start + 500]

    resp = client.post(
        "/api/v1/studies",
        content=chunks(),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413


# ── security headers and health ──────────────────────────────────────────

def test_security_headers_on_api_responses(client):
    for resp in (client.get("/health"), client.get("/api/v1/studies/not-a-uuid")):
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_health_db_reports_ok(client):
    resp = client.get("/health/db")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


def test_health_db_returns_503_when_database_is_unreachable(client, monkeypatch, tmp_path):
    good_url = os.environ["DATABASE_URL"]
    missing = tmp_path / "missing-dir" / "db.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{missing.as_posix()}")
    try:
        resp = client.get("/health/db")
        plain = client.get("/health")
    finally:
        monkeypatch.setenv("DATABASE_URL", good_url)

    assert resp.status_code == 503
    assert resp.json() == {"status": "error", "database": "unavailable"}
    assert plain.status_code == 200
    assert plain.json()["status"] == "ok"


# ── invite code for key generation ───────────────────────────────────────

def test_generate_key_needs_no_code_when_unset(client, monkeypatch):
    monkeypatch.delenv("EXPERIMENTER_INVITE_CODE", raising=False)
    assert client.post("/api/v1/experimenter/generate-key").json()["key"]
    resp = client.post("/api/v1/experimenter/generate-key", json={"invite_code": "anything"})
    assert resp.status_code == 200


def test_generate_key_requires_matching_invite_code(client, monkeypatch, sample_study_data):
    monkeypatch.setenv("EXPERIMENTER_INVITE_CODE", "lab-2026")

    missing = client.post("/api/v1/experimenter/generate-key")
    assert missing.status_code == 403
    assert "invite code is required" in missing.json()["detail"]

    empty = client.post("/api/v1/experimenter/generate-key", json={})
    assert empty.status_code == 403

    wrong = client.post("/api/v1/experimenter/generate-key", json={"invite_code": "lab-2025"})
    assert wrong.status_code == 403
    assert "invite code is required" in wrong.json()["detail"]

    ok = client.post("/api/v1/experimenter/generate-key", json={"invite_code": " lab-2026 "})
    assert ok.status_code == 200
    headers = {"x-experimenter-key": ok.json()["key"]}

    # The issued key works, and participants never need a code.
    study = client.post("/api/v1/studies", json=sample_study_data, headers=headers).json()
    client.post(
        f"/api/v1/studies/{study['id']}/stimuli",
        json={"stimuli": [_stimulus(i) for i in range(4)]},
        headers=headers,
    )
    invite = client.post(
        f"/api/v1/admin/studies/{study['id']}/invites",
        json={"participant_id": "P01"},
        headers=headers,
    ).json()[0]
    assert client.post(f"/api/v1/public/invites/{invite['token']}/start").status_code == 201


# ── caps ─────────────────────────────────────────────────────────────────

def test_study_cap_per_owner(client, monkeypatch, sample_study_data):
    monkeypatch.setenv("MAX_STUDIES_PER_OWNER", "2")
    first = client.post("/api/v1/studies", json=sample_study_data).json()
    assert client.post("/api/v1/studies", json=sample_study_data).status_code == 201

    capped = client.post("/api/v1/studies", json=sample_study_data)
    assert capped.status_code == 409
    assert "at most 2 studies" in capped.json()["detail"]

    # Other owners are unaffected, and deleting a study frees a slot.
    key = client.post("/api/v1/experimenter/generate-key").json()["key"]
    other = client.post("/api/v1/studies", json=sample_study_data, headers={"x-experimenter-key": key})
    assert other.status_code == 201
    assert client.delete(f"/api/v1/studies/{first['id']}").status_code == 204
    assert client.post("/api/v1/studies", json=sample_study_data).status_code == 201


def test_stimulus_cap_per_study(client, monkeypatch, sample_study_data):
    monkeypatch.setenv("MAX_STIMULI_PER_STUDY", "3")
    study_id = client.post("/api/v1/studies", json=sample_study_data).json()["id"]
    url = f"/api/v1/studies/{study_id}/stimuli"

    assert client.post(url, json={"stimuli": [_stimulus(0), _stimulus(1)]}).status_code == 200
    capped = client.post(url, json={"stimuli": [_stimulus(2), _stimulus(3)]})
    assert capped.status_code == 409
    assert "at most 3 stimuli" in capped.json()["detail"]
    assert client.post(url, json={"stimuli": [_stimulus(2)]}).status_code == 200

    demo = client.post("/api/v1/public/demo/start", json={"paradigm": "adaptive", "n_stimuli": 4})
    assert demo.status_code == 400


def test_stimulus_storage_paths_must_stay_in_the_study_folder(client, sample_study_data):
    study = client.post("/api/v1/studies", json=sample_study_data).json()
    url = f"/api/v1/studies/{study['id']}/stimuli"
    prefix = f"owners/{study['owner_id']}/studies/{study['id']}/"

    for bad in (
        "owners/someone-else/studies/other-study/media/clip.mp4",
        f"{prefix}../../other-study/media/clip.mp4",
    ):
        resp = client.post(url, json={"stimuli": [_stimulus(0, media_storage_path=bad)]})
        assert resp.status_code == 400

    resp = client.post(url, json={"stimuli": [_stimulus(0, media_storage_path=f"{prefix}media/clip.mp4")]})
    assert resp.status_code == 200
