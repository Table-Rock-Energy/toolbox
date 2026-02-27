"""
GHL API Router

Provides endpoints for GHL connection management and contact operations:
- Connection CRUD (create, list, update, delete)
- Connection validation
- User listing for contact owner dropdown
- Single contact upsert
- Bulk contact send with async processing
- SSE progress streaming
- Job cancellation
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette import EventSourceResponse

from app.core.auth import require_auth
from app.models.ghl import (
    GHLConnectionCreate,
    GHLConnectionUpdate,
    GHLConnectionResponse,
    ContactUpsertRequest,
    ContactUpsertResponse,
    GHLValidationResult,
    GHLUserResponse,
    BulkSendRequest,
    BulkSendResponse,
    BulkSendValidationResponse,
    BulkSendStartResponse,
    ContactResult,
    ProgressEvent,
    JobStatusResponse,
    FailedContactDetail,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/connections")
async def list_connections(
    user: dict = Depends(require_auth),
) -> dict:
    """List all GHL connections."""
    from app.services.ghl.connection_service import list_connections

    connections = await list_connections()

    # Convert to response models
    connection_responses = [
        GHLConnectionResponse(**conn) for conn in connections
    ]

    return {"connections": connection_responses}


@router.post("/connections")
async def create_connection(
    data: GHLConnectionCreate,
    user: dict = Depends(require_auth),
) -> dict:
    """Create and validate a new GHL connection."""
    from app.services.ghl.connection_service import (
        create_connection,
        validate_connection,
    )

    try:
        # Create connection
        connection = await create_connection(
            name=data.name,
            token=data.token,
            location_id=data.location_id,
            notes=data.notes,
        )

        # Validate immediately
        validation = await validate_connection(connection["id"])

        # Parse validation result to model
        validation_result = GHLValidationResult(
            valid=validation["valid"],
            error=validation.get("error"),
            users=[GHLUserResponse(**u) for u in validation.get("users", [])],
        )

        return {
            "connection": GHLConnectionResponse(**connection),
            "validation": validation_result,
        }

    except Exception as e:
        logger.exception(f"Error creating connection: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/connections/{connection_id}")
async def update_connection(
    connection_id: str,
    data: GHLConnectionUpdate,
    user: dict = Depends(require_auth),
) -> dict:
    """Update an existing GHL connection."""
    from app.services.ghl.connection_service import (
        update_connection,
        validate_connection,
    )

    try:
        # Update connection
        connection = await update_connection(
            connection_id=connection_id,
            name=data.name,
            token=data.token,
            location_id=data.location_id,
            notes=data.notes,
        )

        if connection is None:
            raise HTTPException(status_code=404, detail="Connection not found")

        # Re-validate if token was changed
        validation = None
        if data.token is not None:
            validation_result = await validate_connection(connection_id)
            validation = GHLValidationResult(
                valid=validation_result["valid"],
                error=validation_result.get("error"),
                users=[GHLUserResponse(**u) for u in validation_result.get("users", [])],
            )

        response = {"connection": GHLConnectionResponse(**connection)}
        if validation:
            response["validation"] = validation

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating connection: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: str,
    user: dict = Depends(require_auth),
) -> dict:
    """Delete a GHL connection."""
    from app.services.ghl.connection_service import delete_connection

    deleted = await delete_connection(connection_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")

    return {"deleted": True}


@router.post("/connections/{connection_id}/validate")
async def validate_connection_endpoint(
    connection_id: str,
    user: dict = Depends(require_auth),
) -> GHLValidationResult:
    """Re-validate an existing GHL connection."""
    from app.services.ghl.connection_service import validate_connection

    try:
        validation = await validate_connection(connection_id)

        return GHLValidationResult(
            valid=validation["valid"],
            error=validation.get("error"),
            users=[GHLUserResponse(**u) for u in validation.get("users", [])],
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error validating connection: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections/{connection_id}/users")
async def get_connection_users(
    connection_id: str,
    user: dict = Depends(require_auth),
) -> dict:
    """Fetch GHL users for contact owner dropdown."""
    from app.services.ghl.connection_service import get_connection_users

    try:
        users = await get_connection_users(connection_id)

        return {
            "users": [GHLUserResponse(**u) for u in users]
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching users: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/contacts/upsert")
async def upsert_contact(
    data: ContactUpsertRequest,
    user: dict = Depends(require_auth),
) -> ContactUpsertResponse:
    """Upsert a single contact to GHL."""
    from app.services.ghl.connection_service import upsert_contact_via_connection
    from app.services.ghl.client import GHLAPIError, GHLAuthError, GHLRateLimitError

    # Build contact data dict from request
    contact_data = {}

    if data.first_name:
        contact_data["first_name"] = data.first_name
    if data.last_name:
        contact_data["last_name"] = data.last_name
    if data.email:
        contact_data["email"] = data.email
    if data.phone:
        contact_data["phone"] = data.phone
    if data.address1:
        contact_data["address1"] = data.address1
    if data.city:
        contact_data["city"] = data.city
    if data.state:
        contact_data["state"] = data.state
    if data.postal_code:
        contact_data["postal_code"] = data.postal_code
    if data.tags:
        contact_data["tags"] = data.tags
    if data.assigned_to:
        contact_data["assigned_to"] = data.assigned_to

    try:
        result = await upsert_contact_via_connection(
            connection_id=data.connection_id,
            contact_data=contact_data,
        )

        return ContactUpsertResponse(
            success=result.get("success", False),
            action=result.get("action", "failed"),
            ghl_contact_id=result.get("ghl_contact_id"),
            error=result.get("error"),
        )

    except ValueError as e:
        # Connection not found or missing required fields
        raise HTTPException(status_code=400, detail=str(e))

    except GHLAuthError as e:
        # Auth error - invalid token
        logger.warning(f"GHL auth error: {e}")
        raise HTTPException(status_code=401, detail=str(e))

    except GHLRateLimitError as e:
        # Rate limit error
        logger.warning(f"GHL rate limit error: {e}")
        raise HTTPException(status_code=429, detail=str(e))

    except GHLAPIError as e:
        # Other GHL API errors - pass through details per user decision
        logger.warning(f"GHL API error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    except Exception as e:
        logger.exception(f"Error upserting contact: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/contacts/validate-batch")
async def validate_batch_endpoint(
    data: BulkSendRequest,
    user: dict = Depends(require_auth),
) -> BulkSendValidationResponse:
    """Validate a batch of contacts before sending.

    Returns valid/invalid split without actually sending to GHL.
    Frontend uses this to show validation results and get user confirmation.
    """
    from app.services.ghl.bulk_send_service import validate_batch

    # Convert contacts to list of dicts
    contact_dicts = [contact.model_dump() for contact in data.contacts]

    # Validate batch
    valid_contacts, invalid_results = validate_batch(contact_dicts)

    # Convert invalid results to ContactResult models
    invalid_contact_models = [ContactResult(**result) for result in invalid_results]

    return BulkSendValidationResponse(
        valid_count=len(valid_contacts),
        invalid_count=len(invalid_results),
        invalid_contacts=invalid_contact_models,
    )


@router.post("/contacts/bulk-send")
async def bulk_send_endpoint(
    data: BulkSendRequest,
    user: dict = Depends(require_auth),
) -> BulkSendStartResponse:
    """Start an async bulk contact send job.

    Validates contacts, creates job in Firestore, and starts background processing.
    Returns immediately with job_id. Use /send/{job_id}/progress to stream progress.
    """
    from app.services.ghl.bulk_send_service import validate_batch, process_batch_async, create_send_job
    from app.utils.helpers import generate_uid

    try:
        # Generate job ID
        job_id = generate_uid()

        # Step 1: Validate batch
        contact_dicts = [contact.model_dump() for contact in data.contacts]
        valid_contacts, invalid_results = validate_batch(contact_dicts)

        # Step 2: Build tags list
        tags = [data.campaign_tag]
        if data.manual_sms:
            tags.append("manual sms")

        # Step 3: Calculate totals
        skipped_count = len(invalid_results)
        total_valid = len(valid_contacts)
        total_count = total_valid + skipped_count

        # Step 4: Create job in Firestore
        campaign_name = data.smart_list_name or data.campaign_tag
        await create_send_job(
            job_id=job_id,
            connection_id=data.connection_id,
            campaign_name=campaign_name,
            total_count=total_count,
            skipped_count=skipped_count,
            user_id=user.get("email"),
        )

        # Step 5: Start background processing (fire and forget)
        if valid_contacts:
            asyncio.create_task(
                process_batch_async(
                    job_id=job_id,
                    connection_id=data.connection_id,
                    contacts=valid_contacts,
                    tags=tags,
                    assigned_to_list=data.assigned_to_list,
                )
            )
        else:
            # No valid contacts - mark job as completed immediately
            from app.services.firestore_service import get_firestore_client
            db = get_firestore_client()
            doc_ref = db.collection("jobs").document(job_id)
            await doc_ref.update({
                "status": "completed",
                "completed_at": asyncio.get_event_loop().time(),
            })

        # Step 6: Return response immediately
        return BulkSendStartResponse(
            job_id=job_id,
            status="processing",
            total_count=total_count,
        )

    except ValueError as e:
        # Connection not found or validation error
        logger.warning(f"Validation error during bulk send: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception(f"Error starting bulk send: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/send/{job_id}/progress")
async def stream_send_progress(job_id: str, request: Request):
    """Stream SSE progress events for a bulk send job.

    Polls Firestore every 300ms for job status and yields progress events.
    When job completes, yields a final 'complete' event with full results.
    No auth required (job_id is UUID for security-through-obscurity).
    """
    from app.services.ghl.bulk_send_service import get_job_status
    import json

    async def event_generator():
        """Generate SSE events from Firestore polling."""
        previous_processed = -1

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info(f"Client disconnected from SSE stream for job {job_id}")
                break

            # Fetch job status from Firestore
            job_data = await get_job_status(job_id)

            if job_data is None:
                # Job not found - send error and close
                yield {
                    "event": "error",
                    "id": f"{job_id}-notfound",
                    "data": json.dumps({"error": "Job not found"}),
                }
                break

            # Extract progress data
            status = job_data.get("status", "processing")
            processed = job_data.get("processed_count", 0)
            total = job_data.get("total_count", 0)
            created = job_data.get("created_count", 0)
            updated = job_data.get("updated_count", 0)
            failed = job_data.get("failed_count", 0)

            # Only send progress event if processed count changed
            if processed != previous_processed:
                progress_event = ProgressEvent(
                    job_id=job_id,
                    processed=processed,
                    total=total,
                    created=created,
                    updated=updated,
                    failed=failed,
                    status=status,
                )

                yield {
                    "event": "progress",
                    "id": f"{job_id}-{processed}",
                    "data": progress_event.model_dump_json(),
                }

                previous_processed = processed

            # Check if job is complete
            if status in ("completed", "failed", "cancelled"):
                # Send final complete event with full results
                failed_contacts_data = job_data.get("failed_contacts", [])
                updated_contacts_data = job_data.get("updated_contacts", [])

                # Convert to Pydantic models
                failed_contacts = [FailedContactDetail(**fc) for fc in failed_contacts_data]
                updated_contacts = [ContactResult(**uc) for uc in updated_contacts_data]

                job_status = JobStatusResponse(
                    job_id=job_id,
                    status=status,
                    total_count=total,
                    processed_count=processed,
                    created_count=created,
                    updated_count=updated,
                    failed_count=failed,
                    skipped_count=job_data.get("skipped_count", 0),
                    failed_contacts=failed_contacts,
                    updated_contacts=updated_contacts,
                    created_at=job_data.get("created_at"),
                    completed_at=job_data.get("completed_at"),
                )

                yield {
                    "event": "complete",
                    "id": f"{job_id}-complete",
                    "data": job_status.model_dump_json(),
                }

                logger.info(f"Job {job_id} SSE stream complete with status: {status}")
                break

            # Poll every 300ms
            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


@router.post("/send/{job_id}/cancel")
async def cancel_send(job_id: str, user: dict = Depends(require_auth)):
    """Cancel a running bulk send job.

    Sets cancellation flag in Firestore. The background task will check this flag
    before processing each contact and stop gracefully.
    """
    from app.services.ghl.bulk_send_service import cancel_job

    cancelled = await cancel_job(job_id)

    if not cancelled:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"cancelled": True}


@router.get("/send/{job_id}/status")
async def get_send_status(job_id: str, user: dict = Depends(require_auth)):
    """Get full status of a bulk send job.

    Used by frontend to check if there's an active job on page load (reconnection).
    Returns full job status including failed contacts and updated contacts.
    """
    from app.services.ghl.bulk_send_service import get_job_status

    job_data = await get_job_status(job_id)

    if job_data is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Convert to JobStatusResponse
    failed_contacts_data = job_data.get("failed_contacts", [])
    updated_contacts_data = job_data.get("updated_contacts", [])

    # Convert to Pydantic models
    failed_contacts = [FailedContactDetail(**fc) for fc in failed_contacts_data]
    updated_contacts = [ContactResult(**uc) for uc in updated_contacts_data]

    return JobStatusResponse(
        job_id=job_data.get("job_id", job_id),
        status=job_data.get("status", "unknown"),
        total_count=job_data.get("total_count", 0),
        processed_count=job_data.get("processed_count", 0),
        created_count=job_data.get("created_count", 0),
        updated_count=job_data.get("updated_count", 0),
        failed_count=job_data.get("failed_count", 0),
        skipped_count=job_data.get("skipped_count", 0),
        failed_contacts=failed_contacts,
        updated_contacts=updated_contacts,
        created_at=job_data.get("created_at"),
        completed_at=job_data.get("completed_at"),
    )


@router.get("/daily-limit")
async def get_daily_limit():
    """Get current daily API rate limit status.

    Returns daily limit info including requests made today, remaining, and warning level.
    No auth required - lightweight status check for frontend display.
    """
    from app.services.ghl.client import daily_tracker

    return daily_tracker.get_info()


@router.post("/connections/{connection_id}/quick-check")
async def quick_check_connection(connection_id: str, user: dict = Depends(require_auth)):
    """Quick credential validation check for connection.

    Used by frontend modal to validate credentials on open without updating connection record.
    Returns pass/fail with error details if validation fails.
    """
    from app.services.ghl.connection_service import validate_connection

    try:
        result = await validate_connection(connection_id)
        is_valid = result.get("validation_status") == "valid"
        return {"valid": is_valid, "error": None if is_valid else result.get("validation_error")}
    except HTTPException as e:
        return {"valid": False, "error": e.detail}
    except Exception as e:
        logger.warning(f"Quick-check error for connection {connection_id}: {e}")
        return {"valid": False, "error": str(e)}
