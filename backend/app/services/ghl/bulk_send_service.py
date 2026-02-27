"""Bulk contact send service for GoHighLevel integration.

Provides batch validation, sequential processing with rate limiting,
and job persistence for bulk contact operations.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


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
