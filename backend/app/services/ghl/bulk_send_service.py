"""Bulk contact send service for GoHighLevel integration.

Provides batch validation, sequential processing with rate limiting,
and job persistence for bulk contact operations.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def categorize_error(error: Exception, status_code: int = None) -> tuple[str, str]:
    """Categorize GHL API error for user-actionable feedback.
    Returns (ErrorCategory value, error message)."""
    if status_code == 429:
        return "rate_limit", "Rate limit exceeded. Retry after delay."
    if status_code == 400:
        return "validation", str(error)
    if status_code == 401:
        return "api_error", "Authentication failed. Check token."
    if status_code == 403:
        return "api_error", "Permission denied. Check token scopes and location ID."
    if status_code and status_code >= 500:
        return "api_error", "GHL server error. Retry later."
    if "timeout" in str(error).lower() or "connection" in str(error).lower():
        return "network", "Network error. Check connection."
    return "unknown", str(error)


def validate_batch(contacts: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate a batch of contacts and separate valid from invalid.

    Args:
        contacts: List of contact dicts with mineral_contact_system_id + contact fields

    Returns:
        Tuple of (valid_contacts_list, invalid_contact_results_list)
        Valid contacts include normalized data + mineral_contact_system_id preserved
        Invalid contacts are ContactResult dicts with status="skipped" and error message
    """
    from app.services.ghl.normalization import normalize_contact, validate_contact

    valid_contacts = []
    invalid_results = []

    for contact in contacts:
        # Check for required system ID
        system_id = contact.get("mineral_contact_system_id")
        if not system_id:
            invalid_results.append({
                "mineral_contact_system_id": "unknown",
                "status": "skipped",
                "ghl_contact_id": None,
                "error": "Missing mineral_contact_system_id",
            })
            continue

        # Normalize contact data
        try:
            normalized = normalize_contact(contact)

            # Validate contact (requires email OR phone)
            is_valid, error_msg = validate_contact(normalized)

            if is_valid:
                # Preserve system ID in normalized data
                normalized["mineral_contact_system_id"] = system_id
                valid_contacts.append(normalized)
            else:
                # Add to invalid results
                invalid_results.append({
                    "mineral_contact_system_id": system_id,
                    "status": "skipped",
                    "ghl_contact_id": None,
                    "error": error_msg or "Validation failed",
                })

        except Exception as e:
            logger.warning(f"Error normalizing contact {system_id}: {e}")
            invalid_results.append({
                "mineral_contact_system_id": system_id,
                "status": "skipped",
                "ghl_contact_id": None,
                "error": f"Normalization error: {str(e)}",
            })

    logger.info(f"Validated batch: {len(valid_contacts)} valid, {len(invalid_results)} invalid")

    return valid_contacts, invalid_results


async def process_batch(
    connection_id: str,
    contacts: list[dict],
    tags: list[str],
    assigned_to: Optional[str] = None,
) -> dict:
    """Process a batch of validated contacts through GHL API.

    Creates a single GHLClient instance for the entire batch to share the rate limiter.
    Processes contacts sequentially with proper error handling (skip-and-continue).

    Args:
        connection_id: GHL connection ID
        contacts: List of normalized contact dicts (must include mineral_contact_system_id)
        tags: List of tags to apply to all contacts
        assigned_to: Optional GHL user ID for contact owner

    Returns:
        Dict with created_count, updated_count, failed_count, total_count, results
    """
    from app.services.ghl.connection_service import get_connection
    from app.services.ghl.client import GHLClient, GHLAPIError

    # Fetch connection with decrypted token
    connection = await get_connection(connection_id, decrypt_token=True)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    token = connection.get("token")
    location_id = connection.get("location_id")

    if not token or not location_id:
        raise ValueError("Connection missing token or location_id")

    # Counters
    created_count = 0
    updated_count = 0
    failed_count = 0
    results = []

    # Create ONE GHLClient instance for the entire batch (shared rate limiter)
    async with GHLClient(token=token, location_id=location_id) as client:
        # Process contacts sequentially
        for contact in contacts:
            system_id = contact.get("mineral_contact_system_id", "unknown")

            try:
                # Build contact data for upsert
                contact_data = {}

                # Copy contact fields (excluding system_id)
                for key, value in contact.items():
                    if key != "mineral_contact_system_id" and value is not None:
                        contact_data[key] = value

                # Always add tags
                contact_data["tags"] = tags

                # Add assigned_to if provided
                if assigned_to:
                    contact_data["assigned_to"] = assigned_to

                # Upsert contact
                result = await client.upsert_contact(contact_data)

                # Track result
                action = result.get("action", "unknown")
                ghl_contact_id = result.get("ghl_contact_id")

                results.append({
                    "mineral_contact_system_id": system_id,
                    "status": action,
                    "ghl_contact_id": ghl_contact_id,
                    "error": None,
                })

                # Increment counter
                if action == "created":
                    created_count += 1
                elif action == "updated":
                    updated_count += 1

                logger.info(f"Contact {system_id}: {action} (GHL ID: {ghl_contact_id})")

            except GHLAPIError as e:
                # GHL API error - log and continue
                logger.warning(f"GHL API error for contact {system_id}: {e}")
                failed_count += 1
                results.append({
                    "mineral_contact_system_id": system_id,
                    "status": "failed",
                    "ghl_contact_id": None,
                    "error": str(e),
                })

            except Exception as e:
                # Unexpected error - log and continue
                logger.exception(f"Unexpected error for contact {system_id}: {e}")
                failed_count += 1
                results.append({
                    "mineral_contact_system_id": system_id,
                    "status": "failed",
                    "ghl_contact_id": None,
                    "error": f"Unexpected error: {str(e)}",
                })

    total_count = created_count + updated_count + failed_count

    logger.info(
        f"Batch complete: {total_count} processed "
        f"({created_count} created, {updated_count} updated, {failed_count} failed)"
    )

    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "total_count": total_count,
        "results": results,
    }


async def persist_send_job(
    job_id: str,
    connection_id: str,
    campaign_name: str,
    result_data: dict,
    user_id: Optional[str] = None,
) -> None:
    """Persist send job results to Firestore.

    Args:
        job_id: Unique job identifier
        connection_id: GHL connection ID used
        campaign_name: Campaign or smart list name
        result_data: Result dict with counts and results list
        user_id: Optional user email who initiated the job
    """
    try:
        from app.services.firestore_service import get_firestore_client

        db = get_firestore_client()

        # Build job document
        job_doc = {
            "job_id": job_id,
            "tool": "ghl_send",
            "connection_id": connection_id,
            "campaign_name": campaign_name,
            "created_count": result_data.get("created_count", 0),
            "updated_count": result_data.get("updated_count", 0),
            "failed_count": result_data.get("failed_count", 0),
            "skipped_count": result_data.get("skipped_count", 0),
            "total_count": result_data.get("total_count", 0),
            "results": result_data.get("results", []),
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
            "status": "completed",
        }

        # Write to Firestore
        doc_ref = db.collection("jobs").document(job_id)
        await doc_ref.set(job_doc)

        logger.info(f"Persisted job {job_id} to Firestore")

    except Exception as e:
        # Non-critical - log warning but don't raise
        logger.warning(f"Failed to persist job {job_id} to Firestore: {e}")


async def create_send_job(
    job_id: str,
    connection_id: str,
    campaign_name: str,
    total_count: int,
    skipped_count: int,
    user_id: Optional[str] = None,
) -> None:
    """Create initial job document in Firestore with processing status."""
    try:
        from app.services.firestore_service import get_firestore_client

        db = get_firestore_client()

        # Build job document
        job_doc = {
            "job_id": job_id,
            "tool": "ghl_send",
            "connection_id": connection_id,
            "campaign_name": campaign_name,
            "status": "processing",
            "total_count": total_count,
            "skipped_count": skipped_count,
            "processed_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "failed_count": 0,
            "failed_contacts": [],
            "updated_contacts": [],
            "cancelled_by_user": False,
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
            "user_id": user_id,
        }

        # Write to Firestore
        doc_ref = db.collection("jobs").document(job_id)
        await doc_ref.set(job_doc)

        logger.info(f"Created send job {job_id} in Firestore")

    except Exception as e:
        # Non-critical - log warning but don't raise
        logger.warning(f"Failed to create job {job_id} in Firestore: {e}")


async def get_job_status(job_id: str) -> Optional[dict]:
    """Fetch job status from Firestore."""
    try:
        from app.services.firestore_service import get_firestore_client

        db = get_firestore_client()
        doc_ref = db.collection("jobs").document(job_id)
        doc = await doc_ref.get()

        if doc.exists:
            return doc.to_dict()
        return None

    except Exception as e:
        logger.warning(f"Failed to fetch job {job_id} from Firestore: {e}")
        return None


async def cancel_job(job_id: str) -> bool:
    """Set cancellation flag on job. Returns True if job was found and updated."""
    try:
        from app.services.firestore_service import get_firestore_client

        db = get_firestore_client()
        doc_ref = db.collection("jobs").document(job_id)

        # Check if job exists
        doc = await doc_ref.get()
        if not doc.exists:
            return False

        # Update cancellation flag
        await doc_ref.update({
            "cancelled_by_user": True,
            "cancellation_requested_at": datetime.now(timezone.utc),
        })

        logger.info(f"Cancelled job {job_id}")
        return True

    except Exception as e:
        logger.warning(f"Failed to cancel job {job_id}: {e}")
        return False


async def process_batch_async(
    job_id: str,
    connection_id: str,
    contacts: list[dict],
    tags: list[str],
    assigned_to_list: Optional[list[str]] = None,
) -> None:
    """Process a batch of validated contacts asynchronously with progress updates.

    This function runs as a background task. It:
    - Checks for cancellation before each contact
    - Checks daily rate limit before each contact
    - Updates Firestore after each contact (for real-time progress)
    - Categorizes errors for actionable feedback
    - Stores failed contacts with full data for retry
    - Stores updated contacts for spot-checking
    - Distributes contacts evenly across 1-2 owners (even split)

    Args:
        job_id: Job identifier for progress tracking
        connection_id: GHL connection ID
        contacts: List of normalized contact dicts (must include mineral_contact_system_id)
        tags: List of tags to apply to all contacts
        assigned_to_list: Optional list of 1-2 GHL user IDs for contact owner assignment (even split)
    """
    from app.services.ghl.connection_service import get_connection
    from app.services.ghl.client import GHLClient, GHLAPIError, daily_tracker
    from app.services.firestore_service import get_firestore_client

    db = get_firestore_client()
    doc_ref = db.collection("jobs").document(job_id)

    # Counters
    processed_count = 0
    created_count = 0
    updated_count = 0
    failed_count = 0
    failed_contacts = []
    updated_contacts = []

    try:
        # Fetch connection with decrypted token
        connection = await get_connection(connection_id, decrypt_token=True)
        if not connection:
            raise ValueError(f"Connection {connection_id} not found")

        token = connection.get("token")
        location_id = connection.get("location_id")

        if not token or not location_id:
            raise ValueError("Connection missing token or location_id")

        # Create ONE GHLClient instance for the entire batch (shared rate limiter)
        async with GHLClient(token=token, location_id=location_id) as client:
            # Process contacts sequentially
            for i, contact in enumerate(contacts):
                # Check for cancellation
                job_doc = await doc_ref.get()
                if job_doc.exists and job_doc.to_dict().get("cancelled_by_user", False):
                    logger.info(f"Job {job_id} cancelled by user at {processed_count}/{len(contacts)} contacts")
                    await doc_ref.update({
                        "status": "cancelled",
                        "completed_at": datetime.now(timezone.utc),
                    })
                    return

                # Check daily limit before each contact
                if daily_tracker.remaining <= 0:
                    logger.warning(f"Job {job_id}: Daily rate limit hit at {processed_count}/{len(contacts)} contacts")
                    # Store remaining contacts as "skipped" with rate_limit category
                    for remaining_contact in contacts[i:]:
                        failed_contacts.append({
                            "mineral_contact_system_id": remaining_contact.get("mineral_contact_system_id", "unknown"),
                            "error_category": "rate_limit",
                            "error_message": "Daily rate limit reached (200,000 requests/day). Remaining contacts can be sent after midnight UTC.",
                            "contact_data": remaining_contact,
                        })
                        failed_count += 1
                    # Update job with daily_limit_hit flag
                    await doc_ref.update({
                        "status": "daily_limit_hit",
                        "processed": processed_count,
                        "failed": failed_count,
                        "daily_limit_hit": True,
                        "daily_limit_hit_at": processed_count,
                        "completed_at": datetime.now(timezone.utc),
                        "failed_contacts": failed_contacts,
                    })
                    return

                system_id = contact.get("mineral_contact_system_id", "unknown")

                try:
                    # Build contact data for upsert
                    contact_data = {}

                    # Copy contact fields (excluding system_id)
                    for key, value in contact.items():
                        if key != "mineral_contact_system_id" and value is not None:
                            contact_data[key] = value

                    # Always add tags
                    contact_data["tags"] = tags

                    # Determine owner for this contact (even split if 2 owners)
                    contact_owner = None
                    if assigned_to_list and len(assigned_to_list) > 0:
                        if len(assigned_to_list) == 1:
                            contact_owner = assigned_to_list[0]
                        else:
                            # Even split: first half to owner A, second half to owner B
                            midpoint = (len(contacts) + 1) // 2
                            contact_owner = assigned_to_list[0] if i < midpoint else assigned_to_list[1]

                    # Add assigned_to if we have a contact owner
                    if contact_owner:
                        contact_data["assigned_to"] = contact_owner

                    # Upsert contact
                    result = await client.upsert_contact(contact_data)

                    # Track result
                    action = result.get("action", "unknown")
                    ghl_contact_id = result.get("ghl_contact_id")

                    contact_result = {
                        "mineral_contact_system_id": system_id,
                        "status": action,
                        "ghl_contact_id": ghl_contact_id,
                        "error": None,
                    }

                    # Increment counter
                    if action == "created":
                        created_count += 1
                    elif action == "updated":
                        updated_count += 1
                        # Store updated contacts for spot-checking (limit to 50)
                        if len(updated_contacts) < 50:
                            updated_contacts.append(contact_result)

                    processed_count += 1

                    # Update Firestore after each contact (for real-time progress)
                    await doc_ref.update({
                        "processed_count": processed_count,
                        "created_count": created_count,
                        "updated_count": updated_count,
                        "failed_count": failed_count,
                    })

                    logger.info(f"Contact {system_id}: {action} (GHL ID: {ghl_contact_id}) [{processed_count}/{len(contacts)}]")

                except GHLAPIError as e:
                    # GHL API error - categorize and continue
                    status_code = getattr(e, "status_code", None)
                    error_category, error_message = categorize_error(e, status_code)

                    logger.warning(f"GHL API error for contact {system_id}: {error_message} (category: {error_category})")
                    failed_count += 1
                    processed_count += 1

                    # Store failed contact with full data for retry
                    failed_contacts.append({
                        "mineral_contact_system_id": system_id,
                        "error_category": error_category,
                        "error_message": error_message,
                        "contact_data": contact,  # Full contact data for retry
                    })

                    # Update Firestore
                    await doc_ref.update({
                        "processed_count": processed_count,
                        "failed_count": failed_count,
                    })

                except Exception as e:
                    # Unexpected error - categorize and continue
                    error_category, error_message = categorize_error(e)

                    logger.exception(f"Unexpected error for contact {system_id}: {error_message}")
                    failed_count += 1
                    processed_count += 1

                    # Store failed contact
                    failed_contacts.append({
                        "mineral_contact_system_id": system_id,
                        "error_category": error_category,
                        "error_message": error_message,
                        "contact_data": contact,
                    })

                    # Update Firestore
                    await doc_ref.update({
                        "processed_count": processed_count,
                        "failed_count": failed_count,
                    })

        # Job complete - write final status
        await doc_ref.update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc),
            "failed_contacts": failed_contacts,
            "updated_contacts": updated_contacts,
        })

        logger.info(
            f"Job {job_id} complete: {processed_count} processed "
            f"({created_count} created, {updated_count} updated, {failed_count} failed)"
        )

    except Exception as e:
        # Top-level error - mark job as failed
        logger.exception(f"Job {job_id} failed with error: {e}")
        try:
            await doc_ref.update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now(timezone.utc),
            })
        except Exception as update_error:
            logger.error(f"Failed to update job {job_id} with error status: {update_error}")
