# Security Best Practices Report

Audit date: 2026-06-11

Scope: FastAPI backend, SQLAlchemy/Supabase storage, experimenter-key auth, public study/session/invite routes, Next.js frontend, browser storage, Supabase media uploads, and dependency audit results.

## Executive Summary

The database access layer is mostly sound: the backend uses SQLAlchemy Core statements instead of string-built SQL, local SQLite enables foreign keys, and the Python dependency audit found no known vulnerabilities in the declared backend/package requirements.

The main risks are not SQL injection. They are authorization boundaries, hosted deployment configuration, direct browser-to-Supabase upload policy, long-lived experimenter bearer keys, and frontend package maintenance.

Two concrete backend bugs were fixed during this audit:

- Cross-owner chain composition is now rejected. A user can no longer add another owner's study to their chain.
- Arrangement trial submissions now must match the scheduled subset, closing a data-integrity tampering path.

The frontend dependency posture was also improved:

- `next` / `eslint-config-next` were updated to `16.2.9`.
- `ws` and `postcss` were overridden to patched versions.
- The vulnerable `xlsx` export dependency was removed; results export remains available as JSON and CSV.
- `npm audit --omit=dev` now reports zero vulnerabilities.

Production FastAPI defaults were tightened:

- Production CORS now requires explicit origins via `CORS_ALLOW_ORIGINS`.
- `/docs`, `/redoc`, and `/openapi.json` are hidden by default in production.
- The local experimenter-key signing secret fallback now fails closed in production.
- Supabase Storage cleanup now refuses to send the service-role key to non-HTTPS non-localhost URLs.

Supabase dashboard warnings for public table exposure are addressed by a new migration:

- `server/supabase/migrations/004_lock_down_public_api_exposure.sql`

## Findings

### HIGH-1: Public study/session routes rely on UUID secrecy instead of participant/session authorization

Location:

- `server/app/routers/studies.py:146` public `GET /studies/{study_id}`
- `server/app/routers/studies.py:208` public `GET /studies/{study_id}/stimuli`
- `server/app/routers/sessions.py:575` public `POST /studies/{study_id}/sessions`
- `server/app/routers/sessions.py:580` public `GET /sessions/{session_id}`
- `server/app/routers/sessions.py:600` public `GET /sessions/{session_id}/next`
- `server/app/routers/sessions.py:617` public `POST /sessions/{session_id}/trials`
- `server/app/routers/sessions.py:868` public `POST /sessions/{session_id}/complete`
- `server/app/routers/results.py:108` public session results when no experimenter key is supplied

Evidence:

The routes above do not require an experimenter key or participant/session secret. Some of this is intentional for participant access, but the current model treats `study_id` and `session_id` as bearer capabilities. `get_session_results` only blocks mismatched owners when an owner key is supplied; without one, it returns results by `session_id`.

Impact:

If a study UUID leaks, anyone can start arbitrary sessions for that study. If a session UUID leaks, anyone can view session state, advance/submit trials, complete the session, or fetch participant-facing results. This is acceptable only if all hosted studies are intentionally public-by-link and session UUIDs are treated as secrets.

Fix:

Add an explicit access model:

- For private/published studies, require invite tokens or participant session tokens to start/resume/submit.
- Store a random `participant_session_token_hash` per session and require `Authorization: Bearer <participant-token>` or a custom participant header for `/sessions/*`.
- Add `require_invite` or `visibility` to studies so local/demo workflows remain easy while hosted studies are protected.
- Consider returning participant tokens only through invite start flows.

Mitigation:

Until this is implemented, treat study/session UUIDs as sensitive, do not expose private studies by raw study ID, and avoid sensitive stimulus URLs in public studies.

### HIGH-2: Cross-owner chain route allowed attaching another owner's study

Location:

- Fixed in `server/app/routers/chains.py:269`
- New owner check at `server/app/routers/chains.py:279`
- Regression test in `server/tests/test_hosted_persistence.py`

Evidence:

Before the fix, `add_study_to_chain` verified ownership of the chain but not ownership of `payload.study_id`.

Impact:

Any experimenter who knew another study UUID could add it to their own chain, generate chain invites, and cause participant sessions to be created against the other owner's study.

Fix:

Implemented. The route now rejects cross-owner study additions with `403`.

Verification:

`python -m pytest server/tests/test_hosted_persistence.py::test_chain_rejects_study_owned_by_another_experimenter -q`

### HIGH-3: Arrangement trial submissions did not validate the submitted subset against the scheduled subset

Location:

- Helper added at `server/app/routers/sessions.py:410`
- Enforcement at `server/app/routers/sessions.py:736`
- Regression test in `server/tests/test_reliability_workflows.py`

Evidence:

Pairwise submissions validated the pair against the schedule, but arrangement submissions previously accepted any `subset_indices` for the current trial as long as positions were provided.

Impact:

A malicious or buggy client could submit an unscheduled subset and contaminate the fused RDM/evidence state.

Fix:

Implemented. Current-trial arrangement submissions now compare `subset_indices` with the scheduled set-cover/adaptive subset. Duplicate resubmissions remain idempotent.

Verification:

`python -m pytest server/tests/test_reliability_workflows.py::test_arrangement_submit_rejects_unscheduled_subset -q`

### HIGH-4: Supabase public table exposure must be locked down in the live project

Location:

- Browser Supabase anon client: `web/src/app/lib/supabaseClient.ts:3`
- Direct browser upload: `web/src/app/setup/page.tsx:1590`
- Public URL generation: `web/src/app/setup/page.tsx:1584`
- Owner/study path construction: `web/src/app/setup/page.tsx:1636`
- Supabase migrations define tables/indexes but no visible RLS or storage policies: `server/supabase/migrations/001_initial_schema.sql:4`
- Lockdown migration added: `server/supabase/migrations/004_lock_down_public_api_exposure.sql`

Evidence:

The frontend uploads files directly with `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The path includes owner/study IDs, but Supabase Storage cannot validate the custom experimenter key unless policies or signed upload URLs enforce it. The original migrations did not include `ENABLE ROW LEVEL SECURITY`, `CREATE POLICY`, or storage bucket policy SQL. A new migration now enables RLS on hosted tables and revokes direct table privileges from Supabase `anon` and `authenticated` API roles.

Impact:

Before the migration is applied, anyone with the public anon key can potentially access API-exposed table objects through PostgREST/GraphQL depending on grants. If the Supabase bucket allows anonymous insert/update broadly, any browser user could also upload objects into arbitrary paths or consume storage quota. If the bucket is public, uploaded media URLs are public-by-design.

Fix:

Apply `server/supabase/migrations/004_lock_down_public_api_exposure.sql` to the live Supabase project. This project uses FastAPI as the database access boundary, so `anon` and `authenticated` should not have direct table privileges.

Preferred:

- Move upload authorization to the backend.
- Backend verifies the experimenter key and mints short-lived signed upload URLs for exact study-scoped paths.
- Backend validates registered `media_storage_path` values belong to the authenticated owner/study.

Alternative:

- Use Supabase Auth for experimenters.
- Enable RLS/storage policies that bind paths to `auth.uid()`.
- Commit the policies/migrations to the repo.

Mitigation:

Review the actual Supabase Storage bucket policies before public deployment. Do not assume the path prefix alone is an authorization boundary. Confirm the FastAPI deployment uses a server-side Postgres role that can still access the tables after RLS is enabled.

### HIGH-5: `xlsx` production dependency had known advisories

Location:

- Former dependency: `web/package.json`
- Former usage: `web/src/app/experiment/page.tsx`, `web/src/app/results/page.tsx`

Evidence:

`npm audit --omit=dev` reported high-severity advisories for `xlsx@0.18.5` and no npm fix was available. The code used `xlsx` to write internally generated workbooks, not to parse uploaded spreadsheets.

Impact:

Exploitability was lower than the audit severity because the app was not parsing attacker-supplied XLSX files. However, keeping a flagged package in production prevented a clean dependency audit and created future maintenance risk.

Fix:

Implemented. Removed the `xlsx` dependency and the Excel export buttons. JSON and CSV downloads remain available on both result surfaces. `npm audit --omit=dev` reports zero vulnerabilities.

### MEDIUM-1: Experimenter keys are stateless, non-revocable bearer credentials stored in `localStorage`

Location:

- HMAC key generation/validation: `server/app/routers/experimenter.py:40`, `server/app/routers/experimenter.py:47`, `server/app/routers/experimenter.py:54`
- Owner derivation: `server/app/routers/experimenter.py:67`
- Public key generation: `server/app/routers/experimenter.py:126`
- Frontend persistence: `web/src/app/lib/KeyContext.tsx:57`, `web/src/app/lib/KeyContext.tsx:95`

Evidence:

Possession of the experimenter key equals account ownership. The server does not store issued keys, so individual revocation, rotation, audit metadata, and recovery are not possible. The key is persisted in browser `localStorage`, so any XSS can steal it.

Impact:

Leaked keys remain valid indefinitely. Lost keys lose access. Browser compromise exposes the owner identity.

Fix:

For lightweight accountless operation, move to DB-backed API keys:

- Store only key hashes.
- Use stable experimenter IDs independent of key strings.
- Support `revoked_at`, `last_used_at`, key labels, and rotation.

For public multi-user hosting, use accounts via Supabase Auth, Clerk, Auth.js, or equivalent. Then use revocable API keys only as optional automation tokens.

Mitigation:

At minimum, add a key-rotation story and avoid storing long-lived admin keys in persistent browser storage for production.

### MEDIUM-2: Production FastAPI defaults were too open

Location:

- Production environment detection and docs control: `server/app/main.py`
- Explicit CORS origin parsing: `server/app/main.py`

Evidence:

Before the fix, CORS was configured with `allow_origins=["*"]`, `allow_credentials=True`, and all methods/headers. FastAPI docs/OpenAPI routes were enabled by default.

Impact:

CORS is not an auth bypass for header-token APIs, but permissive CORS increases exposure and can combine badly with browser-stored bearer keys. Public docs expose route structure and schemas.

Fix:

Implemented:

- CORS is configured from explicit origin env vars and rejects `*` in production.
- Local development still defaults to localhost frontend origins.
- `/docs`, `/redoc`, and `/openapi.json` are disabled by default when `APP_ENV`, `ENVIRONMENT`, `RAILWAY_ENVIRONMENT`, or `VERCEL_ENV` indicates production.

Remaining mitigation:

- Set `CORS_ALLOW_ORIGINS` in Railway to the deployed Vercel origin.
- Enforce host validation and baseline security headers at the edge or in app code.

### MEDIUM-3: Rate limits and request-size limits are not visible in app code

Location:

- Public key generation: `server/app/routers/experimenter.py:126`
- Public demo/session starts: `server/app/routers/sessions.py:575`, `server/app/routers/invites.py:90`
- Trial submission: `server/app/routers/sessions.py:617`
- Movement trace cap only limits sample count: `server/app/routers/sessions.py:198`

Evidence:

There is a sample-count limit for movement traces, but no visible global request body limit, rate limit, per-IP throttle, or per-owner quota. These may exist in infrastructure, but they are not visible in the repo.

Impact:

Attackers can create keys, studies, sessions, demos, or large request bodies repeatedly, causing database/storage growth or CPU work.

Fix:

- Add edge request-size limits.
- Add API rate limiting for `/experimenter/generate-key`, public start routes, trial submissions, and uploads.
- Add quotas per experimenter/study/session.
- Validate movement trace sample shape and numeric ranges, not only list length.

### MEDIUM-4: Input schemas allow broad config/media fields without strict runtime validation

Location:

- Raw study config: `server/app/schemas.py:80`
- Media URLs and storage paths: `server/app/schemas.py:137`
- Trial movement trace: `server/app/schemas.py:208`

Evidence:

Study config is a generic `Dict[str, Any]` instead of a discriminated schema per paradigm. Stimulus URLs/storage paths are accepted as arbitrary strings. Movement trace is accepted as `Dict[str, Any]` and then only checked for a `samples` list and max sample count.

Impact:

This is mostly data quality and DoS hardening rather than direct injection, but stricter schemas would reduce unexpected state and make authorization rules easier to enforce.

Fix:

- Use per-paradigm Pydantic config models.
- Validate media URLs with allowed schemes/hosts or require backend-issued storage paths.
- Validate movement trace sample tuple length, finite numbers, ordinal range, phase values, and timestamp bounds.
- Consider `extra="forbid"` on request models where compatible.

### LOW-1: Local fallback signing secret should fail closed in production

Location:

- `server/app/routers/experimenter.py`

Evidence:

Before the fix, if `EXPERIMENTER_KEY_SECRET` was absent, the server used `"local-dev-signing-secret"`.

Impact:

Because `/experimenter/generate-key` is public, this does not immediately grant access to existing owner data. Still, fail-open secrets are unsafe production practice and can become dangerous if the key semantics expand.

Fix:

Implemented. `EXPERIMENTER_KEY_SECRET` is now required when `LOCAL_DEV_BYPASS_AUTH` is not enabled and a production environment variable is present.

### LOW-2: Bandit flagged `urllib.request.urlopen` in Supabase cleanup

Location:

- `server/app/supabase_storage.py`

Evidence:

Bandit flagged `urlopen`; the URL is built from environment configuration, not user input.

Impact:

Low direct risk if env vars are trusted. Still worth constraining to HTTPS Supabase URLs.

Fix:

Implemented. `SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_URL` must be HTTPS, except localhost HTTP for local Supabase development.

## Positive Findings

- SQLAlchemy Core is used for normal database operations; no string-built SQL injection pattern was found in `server/app`.
- SQLite local mode enables `PRAGMA foreign_keys=ON`.
- `.env.local` and `.env.vercel.production` exist locally under `web/`, but `git ls-files` showed they are not tracked; `web/.gitignore` ignores `.env*`.
- Backend/package `pip-audit` checks reported no known vulnerabilities for `server/requirements.txt` and the dependencies extracted from `pyproject.toml`.

## Verification Performed

- `python -m pytest server/tests -q`: 113 passed.
- `npm test -- --run`: 46 passed.
- `npm run lint`: passed.
- `npm run build`: passed.
- `npm audit --omit=dev`: 0 vulnerabilities.
- `python -m pytest server/tests/test_supabase_migrations.py -q`: validates the Supabase lockdown migration covers hosted tables.
- Temporary `pip-audit` for `server/requirements.txt`: no known vulnerabilities.
- Temporary `pip-audit` for dependencies extracted from `pyproject.toml`: no known vulnerabilities.
- `bandit -q -r server/app web/src`: two findings, documented above.

## Recommended Next Order

1. Decide the product auth model: DB-backed revocable keys or real accounts.
2. Add participant/session tokens and study visibility/invite enforcement.
3. Move Supabase uploads behind backend-issued signed upload URLs or commit Supabase Auth/RLS/storage policies.
4. Add host validation and baseline security headers.
5. Add rate limits, quotas, and request body limits.
