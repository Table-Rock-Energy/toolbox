"""Background RRC download worker with Firestore job tracking."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from google.cloud import firestore

from app.core.config import settings
from app.services.proration.rrc_data_service import rrc_data_service

logger = logging.getLogger(__name__)

# Collection name for RRC sync jobs
RRC_SYNC_JOBS_COLLECTION = "rrc_sync_jobs"

# Synchronous Firestore client for use in background thread (separate from async client)
_sync_firestore_client: Optional[firestore.Client] = None


def _get_sync_firestore_client() -> firestore.Client:
    """
    Get or create synchronous Firestore client for background thread.

    This is separate from the async client used in API endpoints.
    The background thread runs outside the asyncio event loop and needs
    a synchronous client.
    """
    global _sync_firestore_client
    if _sync_firestore_client is None:
        _sync_firestore_client = firestore.Client(
            project=settings.gcs_project_id,
            database="tablerocktools",
        )
    return _sync_firestore_client


def create_rrc_sync_job() -> str:
    """
    Create a new RRC sync job document in Firestore.

    Returns:
        Job ID
    """
    db = _get_sync_firestore_client()

    # Generate job ID with ISO timestamp
    job_id = f"rrc-sync-{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}"

    job_data = {
        "id": job_id,
        "status": "downloading_oil",
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "oil_rows": 0,
        "gas_rows": 0,
        "error": None,
        "steps": [],
    }

    db.collection(RRC_SYNC_JOBS_COLLECTION).document(job_id).set(job_data)
    logger.info(f"Created RRC sync job: {job_id}")
    return job_id


def update_rrc_sync_job(job_id: str, updates: dict) -> None:
    """
    Update an RRC sync job document.

    Args:
        job_id: Job document ID
        updates: Dictionary of fields to update
    """
    db = _get_sync_firestore_client()
    db.collection(RRC_SYNC_JOBS_COLLECTION).document(job_id).update(updates)


def add_step(job_id: str, step_name: str, message: Optional[str] = None) -> None:
    """
    Add a step to the job's steps array.

    When message is None, the step is just starting (no completed_at).
    When message is provided, the step is completing (set completed_at and message).

    Args:
        job_id: Job document ID
        step_name: Step identifier (e.g., "downloading_oil")
        message: Optional completion message with results
    """
    db = _get_sync_firestore_client()
    job_ref = db.collection(RRC_SYNC_JOBS_COLLECTION).document(job_id)
    job_doc = job_ref.get()

    if not job_doc.exists:
        logger.error(f"Job {job_id} not found when adding step")
        return

    steps = job_doc.to_dict().get("steps", [])

    if message is None:
        # Step starting
        step_data = {
            "step": step_name,
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "message": None,
        }
        steps.append(step_data)
    else:
        # Step completing - update the last step with this name
        for step in reversed(steps):
            if step["step"] == step_name and step["completed_at"] is None:
                step["completed_at"] = datetime.utcnow()
                step["message"] = message
                break

    job_ref.update({"steps": steps})


def _run_rrc_download(job_id: str) -> None:
    """
    Background worker function that downloads RRC data and syncs to Firestore.

    Runs in a separate thread. Uses synchronous Firestore client.
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
            # Oil failed - stop here
            update_rrc_sync_job(job_id, {
                "status": "failed",
                "error": f"Oil download failed: {oil_message}",
                "completed_at": datetime.utcnow(),
            })
            add_step(job_id, "downloading_oil", f"Failed: {oil_message}")
            logger.error(f"Job {job_id} failed at oil download: {oil_message}")
            return

        # Oil succeeded
        update_rrc_sync_job(job_id, {"oil_rows": oil_count})
        add_step(job_id, "downloading_oil", f"Downloaded {oil_count:,} rows")
        logger.info(f"Job {job_id}: Downloaded {oil_count:,} oil rows")

        # Step 2: Download gas data
        update_rrc_sync_job(job_id, {"status": "downloading_gas"})
        add_step(job_id, "downloading_gas")

        gas_success, gas_message, gas_count = rrc_data_service.download_gas_data()

        if not gas_success:
            # Gas failed - stop here
            update_rrc_sync_job(job_id, {
                "status": "failed",
                "error": f"Gas download failed: {gas_message}",
                "completed_at": datetime.utcnow(),
            })
            add_step(job_id, "downloading_gas", f"Failed: {gas_message}")
            logger.error(f"Job {job_id} failed at gas download: {gas_message}")
            return

        # Gas succeeded
        update_rrc_sync_job(job_id, {"gas_rows": gas_count})
        add_step(job_id, "downloading_gas", f"Downloaded {gas_count:,} rows")
        logger.info(f"Job {job_id}: Downloaded {gas_count:,} gas rows")

        # Step 3: Sync oil to database
        update_rrc_sync_job(job_id, {"status": "syncing_oil"})
        add_step(job_id, "syncing_oil")

        try:
            # sync_to_database is async - run it with asyncio.run()
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

        # All steps complete
        update_rrc_sync_job(job_id, {
            "status": "complete",
            "completed_at": datetime.utcnow(),
        })
        logger.info(f"Job {job_id} completed successfully: {oil_count:,} oil + {gas_count:,} gas rows")

    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error in job {job_id}: {e}")
        try:
            update_rrc_sync_job(job_id, {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow(),
            })
        except Exception as update_error:
            logger.error(f"Failed to update job {job_id} with error status: {update_error}")


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


# Async functions for use in API endpoints (use async Firestore client)

async def get_rrc_sync_job(job_id: str) -> Optional[dict]:
    """
    Get an RRC sync job by ID (async).

    Args:
        job_id: Job document ID

    Returns:
        Job document dict or None if not found
    """
    from app.services.firestore_service import get_firestore_client

    db = get_firestore_client()
    doc = await db.collection(RRC_SYNC_JOBS_COLLECTION).document(job_id).get()

    if not doc.exists:
        return None

    return doc.to_dict()


async def get_active_rrc_sync_job() -> Optional[dict]:
    """
    Get the most recent active or recently completed RRC sync job (async).

    Returns active jobs (status != complete and != failed) or jobs that
    completed within the last 5 minutes.

    Returns:
        Most recent active/recent job or None
    """
    from app.services.firestore_service import get_firestore_client

    db = get_firestore_client()

    # Query for non-terminal jobs (downloading, syncing)
    active_query = db.collection(RRC_SYNC_JOBS_COLLECTION).where(
        "status", "in", ["downloading_oil", "downloading_gas", "syncing_oil", "syncing_gas"]
    ).order_by("started_at", direction=firestore.Query.DESCENDING).limit(1)

    active_docs = await active_query.get()
    if active_docs:
        return active_docs[0].to_dict()

    # Also check for recently completed jobs (within last 5 minutes)
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
    recent_query = db.collection(RRC_SYNC_JOBS_COLLECTION).where(
        "status", "==", "complete"
    ).where(
        "completed_at", ">=", five_min_ago
    ).order_by("completed_at", direction=firestore.Query.DESCENDING).limit(1)

    try:
        recent_docs = await recent_query.get()
        if recent_docs:
            return recent_docs[0].to_dict()
    except Exception:
        # Composite index may not exist - try without the completed_at filter
        pass

    return None
