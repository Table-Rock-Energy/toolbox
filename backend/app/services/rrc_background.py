"""Background RRC download worker with PostgreSQL job tracking."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from app.services.proration.rrc_data_service import rrc_data_service

logger = logging.getLogger(__name__)

# Table name for RRC sync jobs stored via sync sessions
RRC_SYNC_JOBS_TABLE = "rrc_sync_jobs"


def _get_sync_session():
    """Get a synchronous database session for background thread usage."""
    from app.core.database import get_sync_session
    return get_sync_session()


def create_rrc_sync_job() -> str:
    """
    Create a new RRC sync job in PostgreSQL using sync session.

    Returns:
        Job ID
    """
    from app.core.database import get_sync_session
    from sqlalchemy import text

    session = get_sync_session()
    try:
        # Generate job ID with ISO timestamp
        job_id = f"rrc-sync-{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}"

        job_data = {
            "id": job_id,
            "status": "downloading_oil",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "oil_rows": 0,
            "gas_rows": 0,
            "error": None,
            "steps": [],
        }

        # Store as a config doc (app_config table, key = rrc_sync_job:{id})
        session.execute(
            text(
                "INSERT INTO app_config (key, data, created_at, updated_at) "
                "VALUES (:key, :data, NOW(), NOW()) "
                "ON CONFLICT (key) DO UPDATE SET data = :data, updated_at = NOW()"
            ),
            {"key": f"rrc_sync_job:{job_id}", "data": json.dumps(job_data)},
        )
        session.commit()
        logger.info(f"Created RRC sync job: {job_id}")
        return job_id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_rrc_sync_job(job_id: str, updates: dict) -> None:
    """
    Update an RRC sync job document using sync session.

    Args:
        job_id: Job document ID
        updates: Dictionary of fields to update
    """
    from app.core.database import get_sync_session
    from sqlalchemy import text

    session = get_sync_session()
    try:
        # Read current data
        result = session.execute(
            text("SELECT data FROM app_config WHERE key = :key"),
            {"key": f"rrc_sync_job:{job_id}"},
        )
        row = result.fetchone()
        if not row:
            logger.error(f"Job {job_id} not found for update")
            return

        data = row[0] if isinstance(row[0], dict) else json.loads(row[0])

        # Merge updates (convert datetimes to ISO strings for JSON)
        for k, v in updates.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
            else:
                data[k] = v

        session.execute(
            text("UPDATE app_config SET data = :data, updated_at = NOW() WHERE key = :key"),
            {"key": f"rrc_sync_job:{job_id}", "data": json.dumps(data)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def add_step(job_id: str, step_name: str, message: Optional[str] = None) -> None:
    """
    Add a step to the job's steps array using sync session.

    When message is None, the step is just starting (no completed_at).
    When message is provided, the step is completing (set completed_at and message).

    Args:
        job_id: Job document ID
        step_name: Step identifier (e.g., "downloading_oil")
        message: Optional completion message with results
    """
    from app.core.database import get_sync_session
    from sqlalchemy import text

    session = get_sync_session()
    try:
        result = session.execute(
            text("SELECT data FROM app_config WHERE key = :key"),
            {"key": f"rrc_sync_job:{job_id}"},
        )
        row = result.fetchone()
        if not row:
            logger.error(f"Job {job_id} not found when adding step")
            return

        data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        steps = data.get("steps", [])

        if message is None:
            # Step starting
            step_data = {
                "step": step_name,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "message": None,
            }
            steps.append(step_data)
        else:
            # Step completing - update the last step with this name
            for step in reversed(steps):
                if step["step"] == step_name and step["completed_at"] is None:
                    step["completed_at"] = datetime.utcnow().isoformat()
                    step["message"] = message
                    break

        data["steps"] = steps
        session.execute(
            text("UPDATE app_config SET data = :data, updated_at = NOW() WHERE key = :key"),
            {"key": f"rrc_sync_job:{job_id}", "data": json.dumps(data)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _run_rrc_download(job_id: str) -> None:
    """
    Background worker function that downloads RRC data and syncs to database.

    Runs in a separate thread. Uses synchronous SQLAlchemy sessions.
    Calls async sync_to_database using asyncio.run().

    Args:
        job_id: Job document ID
    """
    try:
        logger.info(f"Starting RRC download job: {job_id}")

        # Step 1: Download oil data
        update_rrc_sync_job(job_id, {"status": "downloading_oil"})
        add_step(job_id, "downloading_oil")

        oil_success, oil_message, oil_count = rrc_data_service.download_oil_data()

        if not oil_success:
            update_rrc_sync_job(job_id, {
                "status": "failed",
                "error": f"Oil download failed: {oil_message}",
                "completed_at": datetime.utcnow(),
            })
            add_step(job_id, "downloading_oil", f"Failed: {oil_message}")
            logger.error(f"Job {job_id} failed at oil download: {oil_message}")
            return

        update_rrc_sync_job(job_id, {"oil_rows": oil_count})
        add_step(job_id, "downloading_oil", f"Downloaded {oil_count:,} rows")
        logger.info(f"Job {job_id}: Downloaded {oil_count:,} oil rows")

        # Step 2: Download gas data
        update_rrc_sync_job(job_id, {"status": "downloading_gas"})
        add_step(job_id, "downloading_gas")

        gas_success, gas_message, gas_count = rrc_data_service.download_gas_data()

        if not gas_success:
            update_rrc_sync_job(job_id, {
                "status": "failed",
                "error": f"Gas download failed: {gas_message}",
                "completed_at": datetime.utcnow(),
            })
            add_step(job_id, "downloading_gas", f"Failed: {gas_message}")
            logger.error(f"Job {job_id} failed at gas download: {gas_message}")
            return

        update_rrc_sync_job(job_id, {"gas_rows": gas_count})
        add_step(job_id, "downloading_gas", f"Downloaded {gas_count:,} rows")
        logger.info(f"Job {job_id}: Downloaded {gas_count:,} gas rows")

        # Step 3: Sync oil to database
        update_rrc_sync_job(job_id, {"status": "syncing_oil"})
        add_step(job_id, "syncing_oil")

        try:
            oil_sync_result = asyncio.run(rrc_data_service.sync_to_database("oil"))

            if oil_sync_result.get("success"):
                oil_sync_msg = oil_sync_result.get("message", "Synced")
                add_step(job_id, "syncing_oil", oil_sync_msg)
                logger.info(f"Job {job_id}: {oil_sync_msg}")
            else:
                raise Exception(oil_sync_result.get("message", "Oil sync failed"))
        except Exception as e:
            update_rrc_sync_job(job_id, {
                "status": "failed",
                "error": f"Oil sync failed: {str(e)}",
                "completed_at": datetime.utcnow(),
            })
            add_step(job_id, "syncing_oil", f"Failed: {str(e)}")
            logger.error(f"Job {job_id} failed at oil sync: {e}")
            return

        # Step 4: Sync gas to database
        update_rrc_sync_job(job_id, {"status": "syncing_gas"})
        add_step(job_id, "syncing_gas")

        try:
            gas_sync_result = asyncio.run(rrc_data_service.sync_to_database("gas"))

            if gas_sync_result.get("success"):
                gas_sync_msg = gas_sync_result.get("message", "Synced")
                add_step(job_id, "syncing_gas", gas_sync_msg)
                logger.info(f"Job {job_id}: {gas_sync_msg}")
            else:
                raise Exception(gas_sync_result.get("message", "Gas sync failed"))
        except Exception as e:
            update_rrc_sync_job(job_id, {
                "status": "failed",
                "error": f"Gas sync failed: {str(e)}",
                "completed_at": datetime.utcnow(),
            })
            add_step(job_id, "syncing_gas", f"Failed: {str(e)}")
            logger.error(f"Job {job_id} failed at gas sync: {e}")
            return

        # Update RRC metadata cache with final counts
        try:
            from app.core.database import async_session_maker
            from app.services import db_service
            asyncio.run(_update_rrc_metadata(oil_count, gas_count))
            logger.info(f"Job {job_id}: Updated RRC metadata cache ({oil_count:,} oil, {gas_count:,} gas)")
        except Exception as e:
            logger.warning(f"Job {job_id}: Failed to update RRC metadata cache: {e}")

        # Clear in-memory caches so next request picks up fresh data (PERF-04)
        rrc_data_service._combined_lookup = None
        rrc_data_service._oil_df = None
        rrc_data_service._gas_df = None

        try:
            from app.services.proration.rrc_cache import invalidate_cache
            invalidate_cache()
            logger.info(f"Job {job_id}: In-memory RRC caches invalidated")
        except Exception as e:
            logger.warning(f"Job {job_id}: Cache invalidation failed: {e}")

        # All steps complete
        update_rrc_sync_job(job_id, {
            "status": "complete",
            "completed_at": datetime.utcnow(),
        })
        logger.info(f"Job {job_id} completed successfully: {oil_count:,} oil + {gas_count:,} gas rows")

    except Exception as e:
        logger.exception(f"Unexpected error in job {job_id}: {e}")
        try:
            update_rrc_sync_job(job_id, {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow(),
            })
        except Exception as update_error:
            logger.error(f"Failed to update job {job_id} with error status: {update_error}")


async def _update_rrc_metadata(oil_count: int, gas_count: int) -> None:
    """Update RRC metadata counts using async session (called via asyncio.run)."""
    from app.core.database import async_session_maker
    from app.services import db_service

    async with async_session_maker() as session:
        await db_service.update_rrc_metadata_counts(
            session,
            oil_rows=oil_count,
            gas_rows=gas_count,
            last_sync_at=datetime.utcnow(),
        )
        await session.commit()


def start_rrc_background_download() -> str:
    """
    Start an RRC download in a background thread.

    Returns:
        Job ID for polling status
    """
    # Create job document
    job_id = create_rrc_sync_job()

    # Spawn background thread (daemon=True so it doesn't block app shutdown)
    thread = threading.Thread(
        target=_run_rrc_download,
        args=(job_id,),
        daemon=True,
        name=f"rrc-download-{job_id}",
    )
    thread.start()

    logger.info(f"Started background RRC download thread for job {job_id}")
    return job_id


# Async functions for use in API endpoints

async def get_rrc_sync_job(job_id: str) -> Optional[dict]:
    """
    Get an RRC sync job by ID (async).

    Args:
        job_id: Job document ID

    Returns:
        Job document dict or None if not found
    """
    from app.core.database import async_session_maker
    from app.services import db_service

    async with async_session_maker() as session:
        data = await db_service.get_config_doc(session, f"rrc_sync_job:{job_id}")
    return data


async def get_active_rrc_sync_job() -> Optional[dict]:
    """
    Get the most recent active or recently completed RRC sync job (async).

    Returns active jobs (status != complete and != failed) or jobs that
    completed within the last 5 minutes.

    Returns:
        Most recent active/recent job or None
    """
    from sqlalchemy import select, text
    from app.core.database import async_session_maker
    from app.models.db_models import AppConfig

    async with async_session_maker() as session:
        # Query all rrc_sync_job: keys
        result = await session.execute(
            select(AppConfig).where(
                AppConfig.key.startswith("rrc_sync_job:")
            ).order_by(AppConfig.updated_at.desc()).limit(10)
        )
        rows = result.scalars().all()

    if not rows:
        return None

    five_min_ago = datetime.utcnow() - timedelta(minutes=5)

    # Check for active jobs first
    for row in rows:
        data = row.data
        if not data:
            continue
        status = data.get("status", "")
        if status in ("downloading_oil", "downloading_gas", "syncing_oil", "syncing_gas"):
            return data

    # Check for recently completed jobs
    for row in rows:
        data = row.data
        if not data:
            continue
        status = data.get("status", "")
        completed_at = data.get("completed_at")
        if status == "complete" and completed_at:
            if isinstance(completed_at, str):
                try:
                    completed_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                    if completed_dt.tzinfo:
                        completed_dt = completed_dt.replace(tzinfo=None)
                except (ValueError, TypeError):
                    continue
            else:
                completed_dt = completed_at
            if completed_dt >= five_min_ago:
                return data

    return None
