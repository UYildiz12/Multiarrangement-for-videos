"""
scripts/backup_db.py: clear errors, password kept out of argv, gzipped output.
"""

import gzip
import importlib.util
import io
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup_db.py"


@pytest.fixture
def backup():
    spec = importlib.util.spec_from_file_location("backup_db", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_requires_the_connection_string(backup, monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    assert backup.main([str(tmp_path)]) == 2
    assert "SUPABASE_DB_URL" in capsys.readouterr().err


def test_backup_explains_missing_pg_dump(backup, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(backup.shutil, "which", lambda name: None)
    with monkeypatch.context() as env:
        # Scoped: the API test fixtures also read SUPABASE_DB_URL on teardown.
        env.setenv("SUPABASE_DB_URL", "postgresql://user:secret@db.example.com:5432/postgres")
        assert backup.main([str(tmp_path / "out")]) == 2
    err = capsys.readouterr().err
    assert "pg_dump was not found" in err
    assert "secret" not in err
    assert not (tmp_path / "out").exists()


def test_password_is_moved_out_of_the_command_line(backup):
    url, password = backup.split_password(
        "postgresql+psycopg://user:p%40ss@db.example.com:5432/postgres?sslmode=require"
    )
    assert url == "postgresql://user@db.example.com:5432/postgres?sslmode=require"
    assert password == "p@ss"


def test_backup_writes_a_timestamped_gzip(backup, monkeypatch, tmp_path):
    monkeypatch.setattr(backup.shutil, "which", lambda name: "pg_dump")
    captured = {}

    class FakeProcess:
        def __init__(self, command, stdout, env):
            captured["command"] = command
            captured["password"] = env.get("PGPASSWORD")
            self.stdout = io.BytesIO(b"-- dump\nSELECT 1;\n")

        def wait(self):
            return 0

    monkeypatch.setattr(backup.subprocess, "Popen", FakeProcess)
    with monkeypatch.context() as env:
        env.setenv("SUPABASE_DB_URL", "postgresql://user:secret@db.example.com:5432/postgres")
        assert backup.main([str(tmp_path)]) == 0

    files = list(tmp_path.glob("multiarrangement-*.sql.gz"))
    assert len(files) == 1
    assert gzip.decompress(files[0].read_bytes()) == b"-- dump\nSELECT 1;\n"
    assert "secret" not in " ".join(captured["command"])
    assert captured["password"] == "secret"
