# Web Migration Plan (Full Parity)

## Goal
Build a browser-based version of Multiarrangement with **full feature parity** while keeping the existing MA Python library unchanged. New code lives under `web/` and `server/`.

## Chosen Stack (free/easiest)
- Frontend: **React/Next.js** (Vercel)
- Backend: **FastAPI** (Render)
- DB/Auth/Storage: **Supabase** (Postgres + Auth + Storage)

## What We Did So Far
- Added separate **web/** and **server/** scaffolds (no edits to MA library).
- Created **FastAPI** stub at `server/app/main.py` with `/health`.
- Added backend deps at `server/requirements.txt`.
- Extracted core algorithms into `server/ma_core/`:
  - Adaptive LTW (`lift_weakest.py`) with evidence + stopping logic.
  - Set-cover fusion (`setcover_fusion.py`) including robust weights + inverse-MDS.
- Implemented backend endpoints for:
  - `POST /studies` and `POST /studies/{id}/stimuli`
  - `POST /studies/{id}/sessions`, `GET /sessions/{id}/next`
  - `POST /sessions/{id}/trials`, `POST /sessions/{id}/complete`
  - `GET /sessions/{id}/results`
- Added evidence raw/normalized output in results schema.
- Wired the Next.js app to the backend:
  - Preset media list from `web/src/app/api/videos/route.ts`
  - Setup flow creates study + registers stimuli + starts session
  - Experiment flow pulls next subset + submits trial positions
  - Media playback supports video/audio/image via `MediaModal`

## Plan (Phase-by-Phase)
### Phase 1 — Core Extraction (server/ma_core)
- Copy/port algorithm-only code (no pygame/opencv):
  - batch generation (set-cover + flex)
  - LTW selection + evidence
  - fusion modes + inverse-MDS
- Add tests for deterministic behavior.

### Phase 2 — Backend API (server/)
- Define DB schema (Supabase):
  - users, studies, stimuli, sessions, trials, results
- Implement endpoints:
  - create study, upload stimuli
  - start session, get next subset
  - submit trial positions, compute next
  - export results (CSV/XLSX/NPY/JSON)
- Store trial logs + metadata per session.

### Phase 3 — Frontend UI (web/)
- Implement full-parity UI:
  - circular drag arena, inside-check gating
  - media playback (video/audio/image)
  - instructions (EN/TR + custom)
  - magnifier (Z/X + wheel)
  - mixed-media confirmation
  - fullscreen mode
- Wire to backend API.

### Phase 4 — Admin + Auth
- Admin login via Supabase Auth.
- Admin dashboard:
  - create/configure studies
  - upload media
  - export results

### Phase 5 — Deploy
- Vercel (web), Render (server), Supabase (DB/Auth/Storage).

## Immediate Next Step
Lock down persistence and auth (Supabase schema + RLS), then replace in-memory storage.
