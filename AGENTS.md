# Codex Environment Instructions

Bugs: add regression test when it fits.

## Python + Pytest (Always Use This)
- Default behavior:
  - Use shared venv at `/mnt/d/codex-venvs/shared` across repos.
  - Only use repo `.venv` when explicitly needed for isolation.
- Command preference:
  - `/mnt/d/codex-venvs/shared/bin/python`, `/mnt/d/codex-venvs/shared/bin/pip`, `/mnt/d/codex-venvs/shared/bin/pytest` by default
  - `.venv/bin/python`, `.venv/bin/pip`, `.venv/bin/pytest` only for project-specific isolation
- Do **not** use system `python3`/`pip` for project tasks unless explicitly requested.

## Quick Health Check
- Run:
  - `python -V`
  - `pytest --version`
  - `echo $VIRTUAL_ENV`

## If `.venv` Is Missing
- Use shared venv by default (`/mnt/d/codex-venvs/shared`).
- Only create `.venv` if project isolation is explicitly needed:
  - `python3 -m pip install --target .codex_pytools virtualenv`
  - `PYTHONPATH=.codex_pytools python3 -m virtualenv .venv`
  - `.venv/bin/python -m pip install -r server/requirements.txt -r MA_data/requirements.txt`

## Runtime Notes
- Use writable runtime caches:
  - `MPLCONFIGDIR=/tmp/matplotlib`
  - `JOBLIB_TEMP_FOLDER=/tmp/joblib`
  - `JOBLIB_MULTIPROCESSING=0` (prevents sandbox semaphore warnings)
- npm/pip caches are configured to use `D:` for reuse across projects:
  - pip: `/mnt/d/codex-cache/pip`
  - npm: `/mnt/d/codex-cache/npm`
