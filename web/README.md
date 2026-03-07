# Web Frontend

This directory contains the Next.js frontend for browser-based Multiarrangement studies.

## What it includes

- study setup flow for local files or hosted media
- browser experiment pages for drag-based and pairwise tasks
- results and admin views backed by the FastAPI server
- bundled demo media under `public/` for smoke tests and screenshots

## Requirements

- Node.js 20 or newer
- npm

## Install

```bash
cd web
npm ci
```

## Environment variables

Create `web/.env.local` when running against a local or hosted backend:

```bash
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
NEXT_PUBLIC_LOCAL_DEV_BYPASS_AUTH=1
```

Optional Supabase media hosting:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_SUPABASE_BUCKET=stimuli
```

## Local development

```bash
cd web
npm run dev
```

Open `http://127.0.0.1:3000`.

Useful routes:

- `/demo` for bundled video demos from `public/videos`
- `/setup` to create a study and upload local or hosted stimuli
- `/participate` to run participant sessions
- `/admin`, `/dashboard`, and `/results` for experimenter workflows

## Verification

```bash
cd web
npm run build
npm run lint
```

Expected result for release `0.1.10.2`: the production build succeeds and lint exits with no errors.

## Deployment

- Vercel is the primary frontend deployment target
- Set `NEXT_PUBLIC_API_BASE` to the deployed FastAPI base URL
- Supabase credentials are optional and only needed for hosted media uploads from the setup flow
