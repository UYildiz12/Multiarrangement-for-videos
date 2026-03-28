from app.storage import _normalize_database_url


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
