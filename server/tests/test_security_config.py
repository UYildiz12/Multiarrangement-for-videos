import pytest

from app.main import api_docs_enabled, cors_allow_origins, is_production_environment
from app.routers import experimenter


def test_local_cors_defaults_to_dev_frontend_origins(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    origins = cors_allow_origins()

    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3210" in origins


def test_production_cors_uses_explicit_origins(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://example.com, https://app.example.com/")

    assert cors_allow_origins() == ["https://example.com", "https://app.example.com"]


def test_production_cors_rejects_wildcard_origin(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")

    with pytest.raises(RuntimeError, match="explicit origins"):
        cors_allow_origins()


def test_api_docs_are_disabled_by_default_in_production(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("ENABLE_API_DOCS", raising=False)

    assert is_production_environment()
    assert not api_docs_enabled()


def test_experimenter_secret_is_required_in_production(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("LOCAL_DEV_BYPASS_AUTH", raising=False)
    monkeypatch.delenv("EXPERIMENTER_KEY_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="EXPERIMENTER_KEY_SECRET"):
        experimenter._get_signing_secret()
