# Server (FastAPI)

This directory contains the FastAPI backend that powers the browser-based Multiarrangement workflow.

## Responsibilities

- create and manage studies, stimuli, sessions, and trials
- generate set-cover batches and adaptive LTW subsets
- fuse trial data into RDM and evidence outputs
- expose experimenter and admin endpoints for the web UI

The local development path uses SQLite by default, so studies, invites, sessions, and results survive backend restarts even without Supabase.

## Requirements

- Python 3.10 or newer
- `pip`

## Install

From the repository root:

```bash
python -m pip install -r server/requirements-dev.txt
```

## Local development

The quickest local setup is keyless development mode:

```bash
cd server
LOCAL_DEV_BYPASS_AUTH=1 uvicorn app.main:app --reload --port 8000
```

Useful environment variables:

- `LOCAL_DEV_BYPASS_AUTH=1`: disables experimenter-key checks for localhost development
- `DATABASE_URL`: overrides the default local SQLite database or points the API at a hosted Postgres database
- `SUPABASE_DB_URL`: preferred Postgres connection string for the hosted deployment path
- `EXPERIMENTER_KEY_SECRET`: signing secret for issued experimenter keys
- `ADMIN_SECRET`: optional legacy super-admin override

Once the server is running:

- Open `http://127.0.0.1:8000/docs` for interactive API docs
- `GET /health` should return `{"status":"ok","version":"0.1.11"}`

## Test

```bash
pytest tests -q
```

The API tests run against isolated SQLite databases and cover resume/restart behavior for hosted studies, invites, chains, and results.

## Deployment notes

- `Procfile` and `railway.toml` support the Railway deployment used for the web API
- `supabase/migrations/` contains the schema files for the hosted storage/database path
- Supabase Storage remains optional for hosted media uploads; Postgres is used for durable hosted state
