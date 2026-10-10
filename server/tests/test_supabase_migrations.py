from pathlib import Path


HOSTED_TABLES = [
    "studies",
    "stimuli",
    "sessions",
    "trials",
    "invites",
    "chains",
    "chain_studies",
    "chain_sessions",
    "chain_invites",
]


def test_lockdown_migration_enables_rls_and_revokes_api_role_access():
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "004_lock_down_public_api_exposure.sql"
    ).read_text(encoding="utf-8").lower()

    for table in HOSTED_TABLES:
        qualified = f"public.{table}"
        assert f"alter table {qualified} enable row level security;" in migration
        assert qualified in migration

    assert "from anon, authenticated;" in migration
    assert "alter default privileges in schema public" in migration


def test_upload_ledger_migration_is_locked_down_and_cascades():
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "005_upload_ledger.sql"
    ).read_text(encoding="utf-8").lower()

    assert "create table if not exists public.uploads" in migration
    assert "references public.studies(id) on delete cascade" in migration
    assert "alter table public.uploads enable row level security;" in migration
    assert "revoke all privileges on table public.uploads from anon, authenticated;" in migration
