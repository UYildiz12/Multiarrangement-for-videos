"""
Multiarrangement Web API.

FastAPI application for the web-based multiarrangement experiment platform.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import studies_router, sessions_router, results_router, invites_router, admin_router, chains_router, chains_public_router, experimenter_router
from app.schemas import HealthResponse
from app.storage import init_db

APP_VERSION = "0.1.12"
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
_PRODUCTION_ENV_VALUES = {"prod", "production"}
_LOCAL_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3210",
    "http://127.0.0.1:3210",
]
_PRODUCTION_CORS_ORIGINS = [
    "https://multiarrangement.vercel.app",
]


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in _TRUTHY_ENV_VALUES


def is_production_environment() -> bool:
    """Return True when the API is running in a hosted production environment."""
    candidates = (
        _env("APP_ENV"),
        _env("ENVIRONMENT"),
        _env("RAILWAY_ENVIRONMENT"),
        _env("VERCEL_ENV"),
    )
    return any(value.lower() in _PRODUCTION_ENV_VALUES for value in candidates)


def api_docs_enabled() -> bool:
    """Keep OpenAPI docs available locally and opt-in only in production."""
    override = _env("ENABLE_API_DOCS")
    if override:
        return _is_truthy(override)
    return not is_production_environment()


def cors_allow_origins() -> list[str]:
    """Return explicit browser origins allowed to call the API."""
    raw = (
        _env("CORS_ALLOW_ORIGINS")
        or _env("ALLOWED_ORIGINS")
        or _env("FRONTEND_ORIGIN")
        or _env("FRONTEND_URL")
    )
    configured = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]

    if not is_production_environment():
        return configured or _LOCAL_CORS_ORIGINS

    if "*" in configured:
        raise RuntimeError("CORS_ALLOW_ORIGINS must list explicit origins in production")
    return configured or _PRODUCTION_CORS_ORIGINS


_API_DOCS_ENABLED = api_docs_enabled()

app = FastAPI(
    title="Multiarrangement Web API",
    description="API for running similarity arrangement experiments in the browser",
    version=APP_VERSION,
    docs_url="/docs" if _API_DOCS_ENABLED else None,
    redoc_url="/redoc" if _API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _API_DOCS_ENABLED else None,
)

init_db()

# CORS for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(studies_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(results_router, prefix="/api/v1")
app.include_router(invites_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(chains_router, prefix="/api/v1")
app.include_router(chains_public_router, prefix="/api/v1")
app.include_router(experimenter_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return HealthResponse(status="ok", version=APP_VERSION)


@app.get("/")
def root():
    """Root endpoint with API info."""
    payload = {
        "name": "Multiarrangement Web API",
        "version": APP_VERSION,
    }
    if _API_DOCS_ENABLED:
        payload["docs"] = "/docs"
    return payload
