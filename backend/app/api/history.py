"""API routes for job history and data retrieval."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize_value(val):
    """Convert Firestore-specific types to JSON-safe values."""
    if val is None:
        return val
    if isinstance(val, datetime):
        return val.isoformat()
    if hasattr(val, "isoformat"):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_serialize_value(v) for v in val]
    return val


def _serialize_doc(doc: dict) -> dict:
    """Ensure all values in a Firestore document are JSON-serializable."""
    return {k: _serialize_value(v) for k, v in doc.items()}


@router.get("/jobs")
async def get_jobs(
    tool: Optional[str] = Query(None, description="Filter by tool (extract, title, proration, revenue)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of jobs to return"),
):
    """Get recent job history."""
    if not settings.firestore_enabled:
        raise HTTPException(status_code=503, detail="Database not enabled")

    try:
        from app.services import firestore_service as db

        jobs = await db.get_recent_jobs(tool=tool, limit=limit)
        jobs = [_serialize_doc(j) for j in jobs]

        # Resolve emails to names for jobs missing user_name
        try:
            from app.core.auth import get_full_allowlist

            allowlist = get_full_allowlist()
            name_map: dict[str, str] = {}
            for u in allowlist:
                email = u.get("email", "").lower()
                first = u.get("first_name", "")
                last = u.get("last_name", "")
                full = f"{first} {last}".strip()
                if email and full:
                    name_map[email] = full

            for job in jobs:
                if not job.get("user_name") and job.get("user_id"):
                    resolved = name_map.get(job["user_id"].lower())
                    if resolved:
                        job["user_name"] = resolved
        except Exception:
            pass  # Non-critical enrichment

        return {
            "jobs": jobs,
            "count": len(jobs),
        }
    except Exception as e:
        logger.exception(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and all its associated entries."""
    if not settings.firestore_enabled:
        raise HTTPException(status_code=503, detail="Database not enabled")

    try:
        from app.services import firestore_service as db

        deleted = await db.delete_job(job_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Job not found")

        return {"success": True, "message": f"Job {job_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a specific job by ID."""
    if not settings.firestore_enabled:
        raise HTTPException(status_code=503, detail="Database not enabled")

    try:
        from app.services import firestore_service as db

        job = await db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching job: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/jobs/{job_id}/entries")
async def get_job_entries(job_id: str):
    """Get entries for a specific job."""
    if not settings.firestore_enabled:
        raise HTTPException(status_code=503, detail="Database not enabled")

    try:
        from app.services import firestore_service as db

        job = await db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        tool = job.get("tool")
        entries = []

        if tool == "extract":
            entries = await db.get_extract_entries(job_id)
        elif tool == "title":
            entries = await db.get_title_entries(job_id)
        elif tool == "proration":
            entries = await db.get_proration_rows(job_id)
        elif tool == "revenue":
            entries = await db.get_revenue_statements(job_id)

        return {
            "job_id": job_id,
            "tool": tool,
            "entries": [_serialize_doc(e) for e in entries],
            "count": len(entries),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching job entries: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/rrc/status")
async def get_rrc_status():
    """Get RRC data status from Firestore."""
    if not settings.firestore_enabled:
        raise HTTPException(status_code=503, detail="Database not enabled")

    try:
        from app.services import firestore_service as db

        status = await db.get_rrc_data_status()
        return status
    except Exception as e:
        logger.exception(f"Error fetching RRC status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
