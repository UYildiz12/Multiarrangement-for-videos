import json

from app.storage import _normalize_database_url
from app.supabase_storage import delete_storage_paths, storage_bucket


def test_normalize_database_url_uses_psycopg_driver_for_postgresql_urls():
    assert _normalize_database_url(
        "postgresql://user:pass@example.com:5432/postgres"
    ) == "postgresql+psycopg://user:pass@example.com:5432/postgres"


def test_normalize_database_url_uses_psycopg_driver_for_postgres_urls():
    assert _normalize_database_url(
        "postgres://user:pass@example.com:5432/postgres"
    ) == "postgresql+psycopg://user:pass@example.com:5432/postgres"


def test_normalize_database_url_keeps_explicit_driver_and_sqlite_urls():
    assert _normalize_database_url(
        "postgresql+psycopg://user:pass@example.com:5432/postgres"
    ) == "postgresql+psycopg://user:pass@example.com:5432/postgres"
    assert _normalize_database_url("sqlite:///tmp/test.sqlite3") == "sqlite:///tmp/test.sqlite3"


def test_storage_bucket_prefers_explicit_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "hosted-media")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_BUCKET", "public-bucket")
    assert storage_bucket() == "hosted-media"


def test_delete_storage_paths_skips_when_supabase_not_configured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)

    result = delete_storage_paths(["owners/a/studies/s1/media/file.png"])

    assert result["status"] == "skipped_unconfigured"
    assert result["paths"] == ["owners/a/studies/s1/media/file.png"]


def test_delete_storage_paths_calls_supabase_storage_api(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"[]"

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "stimuli")
    monkeypatch.setattr("app.supabase_storage.urllib.request.urlopen", fake_urlopen)

    result = delete_storage_paths(
        [
            "owners/a/studies/s1/media/file.png",
            "owners/a/studies/s1/media/file.png",
            "owners/a/studies/s1/thumbs/file.jpg",
        ]
    )

    assert captured["url"] == "https://example.supabase.co/storage/v1/object/stimuli"
    assert captured["method"] == "DELETE"
    assert captured["timeout"] == 30
    assert json.loads(str(captured["body"])) == {
        "prefixes": [
            "owners/a/studies/s1/media/file.png",
            "owners/a/studies/s1/thumbs/file.jpg",
        ]
    }
    assert result["status"] == "deleted"
    assert result["paths"] == [
        "owners/a/studies/s1/media/file.png",
        "owners/a/studies/s1/thumbs/file.jpg",
    ]
