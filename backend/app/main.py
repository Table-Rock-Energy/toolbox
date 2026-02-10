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
from app.api.history import router as history_router
from app.api.ai_validation import router as ai_router
from app.api.enrichment import router as enrichment_router
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
app.include_router(history_router, prefix="/api/history", tags=["history"])
app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
app.include_router(enrichment_router, prefix="/api/enrichment", tags=["enrichment"])


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


_scheduler = None


@app.on_event("startup")
async def startup_event() -> None:
    """Application startup event."""
    global _scheduler
    logger.info(f"{settings.app_name} v{settings.version} starting up")

    # Load enrichment config from Firestore
    try:
        from app.api.enrichment import load_enrichment_config_from_firestore
        await load_enrichment_config_from_firestore()
    except Exception as e:
        logger.warning(f"Could not load enrichment config: {e}")

    # Initialize database if enabled
    if settings.use_database:
        try:
            from app.core.database import init_db
            await init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
            logger.warning("Continuing without database persistence")

    # Start monthly RRC data scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from app.services.proration.rrc_data_service import rrc_data_service

        async def scheduled_rrc_download():
            """Monthly job to download and sync RRC data."""
            logger.info("Scheduled RRC data download starting...")
            try:
                success, message, stats = rrc_data_service.download_all_data()
                if success:
                    sync_result = await rrc_data_service.sync_to_database("both")
                    logger.info(f"Scheduled RRC download complete: {message} | Sync: {sync_result.get('message', 'N/A')}")
                else:
                    logger.warning(f"Scheduled RRC download failed: {message}")
            except Exception as e:
                logger.exception(f"Scheduled RRC download error: {e}")

        _scheduler = AsyncIOScheduler()
        # Run on the 1st of every month at 2:00 AM
        _scheduler.add_job(
            scheduled_rrc_download,
            "cron",
            day=1,
            hour=2,
            minute=0,
            id="rrc_monthly_download",
            name="Monthly RRC Data Download",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("RRC monthly download scheduler started (1st of each month at 2:00 AM)")
    except ImportError:
        logger.info("APScheduler not installed, skipping RRC cron scheduler")
    except Exception as e:
        logger.warning(f"Failed to start RRC scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Application shutdown event."""
    global _scheduler
    logger.info(f"{settings.app_name} shutting down")

    # Stop scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

    # Close database connections
    if settings.use_database:
        try:
            from app.core.database import close_db
            await close_db()
        except Exception as e:
            logger.warning(f"Error closing database: {e}")


# Static file serving for production (React frontend)
# Check if static files exist (they're built during Docker build)
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    # Mount static assets (JS, CSS, images)
    if (STATIC_DIR / "assets").exists():
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

        # Check if the requested path is a static file (logo, favicon, etc.)
        static_file = STATIC_DIR / full_path
        if static_file.exists() and static_file.is_file():
            return FileResponse(static_file)

        # Serve index.html for all other routes (SPA handles routing)
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        return JSONResponse(
            status_code=404,
            content={"detail": "Frontend not built"},
        )
