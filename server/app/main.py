"""
Multiarrangement Web API.

FastAPI application for the web-based multiarrangement experiment platform.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import studies_router, sessions_router, results_router, invites_router, admin_router, chains_router, chains_public_router, experimenter_router
from app.schemas import HealthResponse

app = FastAPI(
    title="Multiarrangement Web API",
    description="API for running similarity arrangement experiments in the browser",
    version="0.1.0",
)

# CORS for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
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
    return HealthResponse(status="ok", version="0.1.0")


@app.get("/")
def root():
    """Root endpoint with API info."""
    return {
        "name": "Multiarrangement Web API",
        "version": "0.1.0",
        "docs": "/docs",
    }
