"""Main FastAPI application for Table Rock Toolbox.

Consolidated backend for:
- Extract: OCC Exhibit A PDF extraction
- Title: Title document processing (Excel/CSV)
- Proration: Mineral holders + RRC queries
- Revenue: Revenue PDF extraction
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.extract import router as extract_router
from app.api.title import router as title_router
from app.api.proration import router as proration_router
from app.api.revenue import router as revenue_router
from app.api.admin import router as admin_router
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Consolidated backend for Table Rock Energy tools",
    version=settings.version,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/api/health")
async def health_check() -> dict:
    """Global health check endpoint."""
    return {
        "status": "healthy",
        "service": "table-rock-toolbox",
        "version": settings.version,
        "tools": ["extract", "title", "proration", "revenue"],
    }


# Include tool-specific routers
app.include_router(extract_router, prefix="/api/extract", tags=["extract"])
app.include_router(title_router, prefix="/api/title", tags=["title"])
app.include_router(proration_router, prefix="/api/proration", tags=["proration"])
app.include_router(revenue_router, prefix="/api/revenue", tags=["revenue"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 500 errors."""
    logger.exception(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.on_event("startup")
async def startup_event() -> None:
    """Application startup event."""
    logger.info(f"{settings.app_name} v{settings.version} starting up")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Application shutdown event."""
    logger.info(f"{settings.app_name} shutting down")


# Static file serving for production (React frontend)
# Check if static files exist (they're built during Docker build)
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    # Mount static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # Serve index.html for all non-API routes (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA for all non-API routes."""
        # Don't handle API routes here
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": "API route not found"},
            )

        # Serve index.html for all other routes (SPA handles routing)
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        return JSONResponse(
            status_code=404,
            content={"detail": "Frontend not built"},
        )
