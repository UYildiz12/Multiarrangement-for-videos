#!/usr/bin/env python3
"""
Back up the hosted Multiarrangement database with pg_dump.

Usage (the connection string comes from the environment, never from a file):

    SUPABASE_DB_URL='postgresql://...' python scripts/backup_db.py backups/

Writes ``multiarrangement-<UTC timestamp>.sql.gz`` into the given folder. It
dumps the ``public`` schema (studies, stimuli, sessions, trials, invites,
chains, upload ledger); media files in Supabase Storage are not included.
Requires the PostgreSQL client tools (pg_dump) at least as new as the server.
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit


def split_password(db_url: str) -> tuple[str, str | None]:
    """Return (URL without password, password) so the password stays out of argv.

    Also drops a SQLAlchemy driver suffix such as ``postgresql+psycopg://``.
    """
    parts = urlsplit(db_url)
    scheme = parts.scheme.split("+", 1)[0]
    netloc = parts.netloc
    password = None
    if "@" in netloc:
        userinfo, host = netloc.rsplit("@", 1)
        user, sep, raw_password = userinfo.partition(":")
        if sep:
            password = unquote(raw_password)
        netloc = f"{user}@{host}"
    return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment)), password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump the hosted database to a timestamped .sql.gz file.")
    parser.add_argument("output_dir", type=Path, help="folder for the backup file (created if missing)")
    args = parser.parse_args(argv)

    db_url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not db_url:
        print("error: set SUPABASE_DB_URL to the database connection string first.", file=sys.stderr)
        return 2

    pg_dump = shutil.which("pg_dump")
    if pg_dump is None:
        print(
            "error: pg_dump was not found on PATH. Install the PostgreSQL client tools "
            "(same major version as the Supabase server or newer), e.g. "
            "'brew install libpq', 'apt install postgresql-client', or the PostgreSQL "
            "installer for Windows, then run this script again.",
            file=sys.stderr,
        )
        return 2

    url, password = split_password(db_url)
    env = dict(os.environ)
    env.pop("SUPABASE_DB_URL", None)
    if password is not None:
        env["PGPASSWORD"] = password

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = args.output_dir / f"multiarrangement-{stamp}.sql.gz"
    partial = target.with_name(target.name + ".partial")

    command = [pg_dump, "--no-owner", "--no-privileges", "--schema=public", f"--dbname={url}"]
    with gzip.open(partial, "wb") as out:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, env=env)
        shutil.copyfileobj(process.stdout, out)
        process.stdout.close()
        exit_code = process.wait()

    if exit_code != 0:
        partial.unlink(missing_ok=True)
        print(f"error: pg_dump failed with exit code {exit_code}; no backup written.", file=sys.stderr)
        return exit_code

    partial.replace(target)
    print(f"Backup written to {target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
