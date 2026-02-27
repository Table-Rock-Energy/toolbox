"""
GHL API Router

Provides endpoints for GHL connection management and contact operations:
- Connection CRUD (create, list, update, delete)
- Connection validation
- User listing for contact owner dropdown
- Single contact upsert
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

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
    ContactResult,
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
) -> BulkSendResponse:
    """Send a batch of contacts to GHL.

    Validates contacts, processes valid ones through GHL API, and persists job results.
    """
    from app.services.ghl.bulk_send_service import validate_batch, process_batch, persist_send_job
    from app.utils.helpers import generate_uid
    from app.services.ghl.client import GHLAPIError, GHLAuthError, GHLRateLimitError

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

        # Step 3: Process valid contacts (skip if all invalid)
        processing_results = {"created_count": 0, "updated_count": 0, "failed_count": 0, "results": []}

        if valid_contacts:
            processing_results = await process_batch(
                connection_id=data.connection_id,
                contacts=valid_contacts,
                tags=tags,
                assigned_to=data.assigned_to,
            )

        # Step 4: Combine results (invalid + processing)
        all_results = invalid_results + processing_results.get("results", [])

        # Calculate final counts
        created_count = processing_results.get("created_count", 0)
        updated_count = processing_results.get("updated_count", 0)
        failed_count = processing_results.get("failed_count", 0)
        skipped_count = len(invalid_results)
        total_count = created_count + updated_count + failed_count + skipped_count

        # Step 5: Persist job
        result_data = {
            "created_count": created_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "total_count": total_count,
            "results": all_results,
        }

        campaign_name = data.smart_list_name or data.campaign_tag
        await persist_send_job(
            job_id=job_id,
            connection_id=data.connection_id,
            campaign_name=campaign_name,
            result_data=result_data,
            user_id=user.get("email"),
        )

        # Step 6: Return response
        return BulkSendResponse(
            job_id=job_id,
            total_count=total_count,
            created_count=created_count,
            updated_count=updated_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            results=[ContactResult(**r) for r in all_results],
        )

    except GHLAuthError as e:
        logger.warning(f"GHL auth error during bulk send: {e}")
        raise HTTPException(status_code=401, detail=str(e))

    except GHLRateLimitError as e:
        logger.warning(f"GHL rate limit error during bulk send: {e}")
        raise HTTPException(status_code=429, detail=str(e))

    except ValueError as e:
        # Connection not found or validation error
        logger.warning(f"Validation error during bulk send: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception(f"Error during bulk send: {e}")
        raise HTTPException(status_code=500, detail=str(e))
