"""API routes for job history and data retrieval."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import is_user_admin, require_auth
from app.core.database import get_db
from app.services import db_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize_value(val):
    """Convert database types to JSON-safe values."""
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
    """Ensure all values in a document are JSON-serializable."""
    return {k: _serialize_value(v) for k, v in doc.items()}


def _job_to_dict(job) -> dict:
    """Convert a Job ORM instance to a dict for API responses."""
    return {
        "id": job.id,
        "user_id": job.user_id,
        "tool": job.tool.value if job.tool else None,
        "status": job.status.value if job.status else None,
        "source_filename": job.source_filename,
        "source_file_size": job.source_file_size,
        "total_count": job.total_count,
        "success_count": job.success_count,
        "error_count": job.error_count,
        "error_message": job.error_message,
        "options": job.options,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/jobs")
async def get_jobs(
    tool: Optional[str] = Query(None, description="Filter by tool (extract, title, proration, revenue)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of jobs to return"),
    user: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get recent job history. Non-admin sees own jobs only."""
    try:
        from app.models.db_models import ToolType

        try:
            tool_enum = ToolType(tool.replace("-", "_")) if tool else None
        except ValueError:
            return {"jobs": [], "count": 0}

        email = user.get("email", "")
        if is_user_admin(email):
            jobs = await db_service.get_recent_jobs(session, tool=tool_enum, limit=limit)
        else:
            jobs = await db_service.get_user_jobs(session, user_id=email, tool=tool_enum, limit=limit)

        jobs_dicts = [_job_to_dict(j) for j in jobs]

        # Resolve emails to names for jobs missing user_name
        try:
            from app.core.auth import get_full_allowlist

            allowlist = get_full_allowlist()
            name_map: dict[str, str] = {}
            for u in allowlist:
                uemail = u.get("email", "").lower()
                first = u.get("first_name", "")
                last = u.get("last_name", "")
                full = f"{first} {last}".strip()
                if uemail and full:
                    name_map[uemail] = full

            for job in jobs_dicts:
                if not job.get("user_name") and job.get("user_id"):
                    resolved = name_map.get(job["user_id"].lower())
                    if resolved:
                        job["user_name"] = resolved
        except Exception:
            pass  # Non-critical enrichment

        return {
            "jobs": jobs_dicts,
            "count": len(jobs_dicts),
        }
    except Exception as e:
        logger.exception(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    user: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Delete a job. Restricted to job owner or admin."""
    try:
        job = await db_service.get_job(session, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        email = user.get("email", "")
        job_owner = job.user_id or ""

        if job_owner != email and not is_user_admin(email):
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own jobs",
            )

        deleted = await db_service.delete_job(session, job_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Job not found")

        return {"success": True, "message": f"Job {job_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get a specific job by ID."""
    try:
        job = await db_service.get_job(session, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return _job_to_dict(job)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching job: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/jobs/{job_id}/entries")
async def get_job_entries(
    job_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get entries for a specific job."""
    try:
        job = await db_service.get_job(session, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        tool = job.tool.value if job.tool else None
        entries = []

        if tool == "extract":
            rows = await db_service.get_extract_entries(session, job_id)
            entries = [_serialize_doc({"entry_number": r.entry_number, "primary_name": r.primary_name, "entity_type": r.entity_type, "mailing_address": r.mailing_address, "city": r.city, "state": r.state, "zip_code": r.zip_code, "notes": r.notes}) for r in rows]
        elif tool == "title":
            rows = await db_service.get_title_entries(session, job_id)
            entries = [_serialize_doc({"full_name": r.full_name, "entity_type": r.entity_type, "address": r.address, "city": r.city, "state": r.state, "zip_code": r.zip_code, "notes": r.notes}) for r in rows]
        elif tool == "proration":
            rows = await db_service.get_proration_rows(session, job_id)
            entries = [_serialize_doc({"owner": r.owner, "county": r.county, "interest": r.interest, "rrc_lease": r.rrc_lease, "rrc_acres": r.rrc_acres, "notes": r.notes}) for r in rows]
        elif tool == "revenue":
            stmts = await db_service.get_revenue_statements(session, job_id)
            entries = [_serialize_doc({"filename": s.filename, "format": s.format, "payor": s.payor, "check_number": s.check_number, "total_rows": s.total_rows, "total_net": s.total_net}) for s in stmts]

        return {
            "job_id": job_id,
            "tool": tool,
            "entries": entries,
            "count": len(entries),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching job entries: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/rrc/status")
async def get_rrc_status(session: AsyncSession = Depends(get_db)):
    """Get RRC data status from database."""
    try:
        status = await db_service.get_rrc_data_status(session)
        return status
    except Exception as e:
        logger.exception(f"Error fetching RRC status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
