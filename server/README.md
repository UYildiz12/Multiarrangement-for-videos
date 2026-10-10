# Server (FastAPI)

This directory contains the FastAPI backend that powers the browser-based Multiarrangement workflow.

## Responsibilities

- create and manage studies, stimuli, sessions, and trials
- generate set-cover batches and adaptive LTW subsets
- fuse token-center distances into RDM and evidence outputs
- expose experimenter and admin endpoints for the web UI

For arrangement paradigms, submitted positions are token centers. When the web client provides arena size, the backend attaches the arena center and radius to each trial before RDM estimation so distances are computed in arena-radius units rather than raw pixels.

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
- `CORS_ALLOW_ORIGINS`: comma-separated browser origins allowed to call the API in production, for example `https://your-vercel-app.vercel.app`
- `ENABLE_API_DOCS=1`: optional production override for `/docs`, `/redoc`, and `/openapi.json`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_SECRET_KEY`) and `SUPABASE_STORAGE_BUCKET` (default `stimuli`): server-side Storage access, used to issue signed upload URLs and to delete a study's files. Required for hosted media uploads; never give the service-role key to the web app.
- `EXPERIMENTER_INVITE_CODE`: optional; when set, new experimenter keys can only be generated with this code (see below)
- Rate limits, size limits and caps: see [Limits and abuse protection](#limits-and-abuse-protection)

Once the server is running:

- Open `http://127.0.0.1:8000/docs` for interactive API docs
- `GET /health` should return `{"status":"ok","version":"0.1.12"}`
- `GET /health/db` runs `SELECT 1` and returns `{"status":"ok","database":"ok"}`, or HTTP 503 if the database cannot be reached

## Test

```bash
pytest tests -q
```

The API tests run against isolated SQLite databases and cover resume/restart behavior for hosted studies, invites, chains, and results.

## Deployment notes

- `/railway.toml` is the canonical Railway deployment config; it runs the API with `PYTHONPATH=server:.` so the backend can use the shared set-cover utilities and cached covering designs.
- `/nixpacks.toml` installs the backend Python dependencies, and `/.railwayignore` keeps the Railway artifact focused on the API plus the shared cover-generation code and caches.
- `supabase/migrations/` contains the schema files for the hosted storage/database path.
- Supabase Storage remains optional for hosted media uploads; Postgres is used for durable hosted state. Hosted uploads need the server-side Storage variables listed above.
- Railway sets `RAILWAY_ENVIRONMENT=production` for production deployments. In that mode the API hides OpenAPI docs by default, rejects wildcard CORS, and requires `EXPERIMENTER_KEY_SECRET`.
- Set `CORS_ALLOW_ORIGINS` to the deployed Vercel origin before promoting a production frontend, otherwise browsers will correctly block cross-origin API calls.

## Limits and abuse protection

All limits are environment variables read on each request, so they can be changed on Railway without a code change. Set a value to `0` to disable that limit. Sizes are in bytes.

| Variable | Default | Applies to |
| --- | --- | --- |
| `RATE_LIMIT_KEYGEN_PER_HOUR` | `5` | `POST /api/v1/experimenter/generate-key`, per client IP |
| `RATE_LIMIT_STUDIES_PER_HOUR` | `30` | `POST /api/v1/studies` and `POST /api/v1/public/demo/start` (the demo also creates a study), per client IP |
| `RATE_LIMIT_UPLOADS_PER_HOUR` | `300` | `POST /api/v1/studies/{id}/uploads` and `POST /api/v1/studies/{id}/stimuli`, per client IP |
| `RATE_LIMIT_DEFAULT_PER_MINUTE` | `600` | every other request, per client IP (participants submit many trials) |
| `MAX_REQUEST_BYTES` | `5242880` (5 MB) | request body size; larger bodies get HTTP 413 |
| `MAX_STUDIES_PER_OWNER` | `100` | studies per experimenter key (HTTP 409) |
| `MAX_STIMULI_PER_STUDY` | `300` | stimuli per study, and media uploads issued per study (HTTP 409); also caps `n_stimuli` of the public demo |
| `MAX_UPLOAD_BYTES` | `52428800` (50 MB) | declared size of one uploaded file (HTTP 413) |
| `MAX_STORAGE_BYTES_PER_OWNER` | `1073741824` (1 GB) | total size of the uploads issued to one experimenter key (HTTP 409) |

- Rate limiting is an in-memory sliding window (`app/ratelimit.py`). Exceeding a limit returns HTTP 429 with a `Retry-After` header. Counters live in the API process, reset on restart and are per instance, which matches the single Railway instance.
- The client IP is taken from `X-Forwarded-For`, counting `TRUSTED_PROXY_HOPS` entries from the right (default `1`: the rightmost entry, which Railway's proxy appends and a client cannot forge; entries further left are client-supplied). Set it to the number of proxies you control in front of the API, or to `0` to ignore the header and use the TCP peer address. The TCP peer is also used when the header is missing or has fewer entries than `TRUSTED_PROXY_HOPS`. Users behind one university NAT share a budget; raise the limits if that becomes a problem.
- The 5 MB request limit is enough because media files never pass through the API (see below). The largest API bodies are trial submissions with movement traces (at most 50,000 samples) and stimulus lists.
- "Start experiment" on the setup page also creates a study, so local test runs count towards `MAX_STUDIES_PER_OWNER`; experimenters can delete old studies on the Experimenter page.

### Invite code for new experimenter keys

`POST /api/v1/experimenter/generate-key` is public. To restrict who can create keys, set `EXPERIMENTER_INVITE_CODE` on Railway and share the code with experimenters. The endpoint then requires `{"invite_code": "..."}` in the JSON body (compared in constant time) and returns HTTP 403 otherwise. The Experimenter page has an optional invite-code field for this. Leaving the variable unset keeps key generation open. Keys issued earlier keep working, and participants never need a code.

## Hosted media uploads

Media goes from the browser straight to Supabase Storage; the API only sees small JSON requests.

1. The web app asks `POST /api/v1/studies/{study_id}/uploads` (experimenter key required, caller must own the study) for one file, sending `filename`, `content_type`, `size_bytes`, `kind` (`media` or `thumbnail`) and `index`.
2. The API checks the declared size against `MAX_UPLOAD_BYTES`, the type against `video/*`, `audio/*` and `image/*`, the number of uploads in the study against `MAX_STIMULI_PER_STUDY` (thumbnails are counted separately) and the owner's total against `MAX_STORAGE_BYTES_PER_OWNER`. It then asks Supabase Storage for a signed upload URL with the service-role key, for a path it chooses under `owners/{owner_id}/studies/{study_id}/`.
3. The browser uploads the file with supabase-js `uploadToSignedUrl` and registers the stimulus with `POST /api/v1/studies/{study_id}/stimuli` as before. Storage paths outside the study's folder are rejected, because study deletion removes them with the service-role key. Playback still uses public URLs.

Every issued upload is recorded in the `uploads` table (`supabase/migrations/005_upload_ledger.sql`; the API also creates the table on startup when it is missing). The quota is computed from this ledger rather than from the stimuli table because files are uploaded before they are registered: counting only registered stimuli would let a client request upload URLs without ever registering them. The ledger also lets study deletion remove files that were uploaded but never registered. Deleting a study deletes its ledger rows and frees the quota. Sizes are those declared by the client; the bucket's own size limit enforces the real maximum per file.

### Supabase dashboard steps after deploying

Do these once the API (with `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` set on Railway) and the web app are deployed, so that uploads only work through signed URLs issued by the API:

1. **Storage > Buckets > `stimuli` > Edit bucket**: keep it public (playback uses public URLs), turn on "Restrict file upload size" and set it to 50 MB, and set "Allowed MIME types" to `video/*, audio/*, image/*`. (List exact image types instead of `image/*` if you also want to block SVG files.)
2. **Storage > Policies** (policies on `storage.objects`): delete, or restrict to the service role, every policy that lets the `anon` (or `public`/`authenticated`) role INSERT, UPDATE or DELETE objects in the `stimuli` bucket. Signed upload URLs and the service-role key do not need these policies. Public URLs do not need an `anon` SELECT policy either, and such a policy lets anyone list every file in the bucket, so remove it unless something else relies on it.
3. Check: an upload from the browser console with only the anon key (`supabase.storage.from("stimuli").upload("test.txt", new Blob(["x"]))`) should now fail, while publishing a study with uploaded media from the setup page still works.

## Health checks and keep-alive

- `GET /health` reports that the API process is up and is unchanged.
- `GET /health/db` runs `SELECT 1` through the API's database connection and returns HTTP 503 with `{"status":"error","database":"unavailable"}` on failure.
- `.github/workflows/keepalive.yml` calls `/health/db` with `curl -fsS` every two days (and on manual dispatch). This keeps the Supabase free-tier project from being paused for inactivity. A failed run makes GitHub e-mail the repository owner, which doubles as a basic uptime alert.
- GitHub disables scheduled workflows in public repositories after 60 days without repository activity; re-enable the workflow on the Actions tab if that happens. If the Supabase project has already been paused, restore it from the Supabase dashboard; the keep-alive cannot wake it.

## Backups

`scripts/backup_db.py` (at the repository root) runs `pg_dump` and writes `multiarrangement-<UTC timestamp>.sql.gz` into the folder given on the command line:

```bash
export SUPABASE_DB_URL='postgresql://postgres.<project-ref>:<password>@<host>:5432/postgres'
python scripts/backup_db.py ~/multiarrangement-backups
```

- The connection string is read only from `SUPABASE_DB_URL` (copy it from Supabase > Project Settings > Database); never store it in the repository. The script hands the password to `pg_dump` through `PGPASSWORD` rather than the command line.
- It needs the PostgreSQL client tools (`pg_dump`) at least as new as the Supabase Postgres version, and prints installation hints if `pg_dump` is missing.
- It dumps the `public` schema (all app tables). Uploaded media files in Supabase Storage are not included.
- Restore into an empty database with `gunzip -c <file>.sql.gz | psql "$TARGET_DB_URL"`.
- Run it on a schedule you control (for example weekly with cron or Windows Task Scheduler) and keep copies off the machine.
