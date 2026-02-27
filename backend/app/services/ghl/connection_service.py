"""
GHL Connection CRUD Service

Provides Firestore CRUD operations for GHL connections with encrypted token storage.
Handles connection validation, user listing, and contact upsert delegation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

GHL_CONNECTIONS_COLLECTION = "ghl_connections"


async def create_connection(
    name: str,
    token: str,
    location_id: str,
    notes: Optional[str] = None,
) -> dict:
    """
    Create a new GHL connection with encrypted token storage.

    Args:
        name: User-friendly connection name
        token: GHL Private Integration Token (will be encrypted)
        location_id: GHL Location ID
        notes: Optional notes

    Returns:
        Connection dict with id, name, token_last4, location_id, notes,
        validation_status, created_at, updated_at
    """
    from app.services.firestore_service import get_firestore_client
    from app.services.shared.encryption import encrypt_value

    # Encrypt token
    encrypted_token = encrypt_value(token)
    token_last4 = token[-4:] if len(token) >= 4 else ""

    # Create document data
    now = datetime.now(timezone.utc)
    doc_data = {
        "name": name,
        "encrypted_token": encrypted_token,
        "token_last4": token_last4,
        "location_id": location_id,
        "notes": notes or "",
        "validation_status": "pending",
        "created_at": now,
        "updated_at": now,
    }

    # Save to Firestore
    db = get_firestore_client()
    doc_ref = db.collection(GHL_CONNECTIONS_COLLECTION).document()
    await doc_ref.set(doc_data)

    connection_id = doc_ref.id
    logger.info(f"Created connection {connection_id}")

    # Return connection (without encrypted_token)
    result = {
        "id": connection_id,
        "name": name,
        "token_last4": token_last4,
        "location_id": location_id,
        "notes": notes or "",
        "validation_status": "pending",
        "created_at": now,
        "updated_at": now,
    }

    return result


async def get_connection(
    connection_id: str,
    decrypt_token: bool = False,
) -> Optional[dict]:
    """
    Fetch a connection by ID.

    Args:
        connection_id: Connection document ID
        decrypt_token: If True, decrypt and include token in result

    Returns:
        Connection dict (without encrypted_token) or None if not found
    """
    from app.services.firestore_service import get_firestore_client
    from app.services.shared.encryption import decrypt_value

    db = get_firestore_client()
    doc_ref = db.collection(GHL_CONNECTIONS_COLLECTION).document(connection_id)
    doc = await doc_ref.get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    data["id"] = doc.id

    # Decrypt token if requested
    if decrypt_token and "encrypted_token" in data:
        encrypted_token = data.pop("encrypted_token")
        data["token"] = decrypt_value(encrypted_token)
    else:
        # Always remove encrypted_token from returned dict
        data.pop("encrypted_token", None)

    return data


async def list_connections() -> list[dict]:
    """
    List all GHL connections.

    Returns:
        List of connection dicts sorted by name (no encrypted_token fields)
    """
    from app.services.firestore_service import get_firestore_client

    db = get_firestore_client()
    docs = db.collection(GHL_CONNECTIONS_COLLECTION).stream()

    connections = []
    async for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        # Remove encrypted_token
        data.pop("encrypted_token", None)
        connections.append(data)

    # Sort by name
    connections.sort(key=lambda c: c.get("name", "").lower())

    return connections


async def update_connection(
    connection_id: str,
    name: Optional[str] = None,
    token: Optional[str] = None,
    location_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[dict]:
    """
    Update an existing connection.

    Args:
        connection_id: Connection document ID
        name: New name (if provided)
        token: New token (if provided, will be encrypted)
        location_id: New location ID (if provided)
        notes: New notes (if provided)

    Returns:
        Updated connection dict or None if not found
    """
    from app.services.firestore_service import get_firestore_client
    from app.services.shared.encryption import encrypt_value

    # Check if connection exists
    existing = await get_connection(connection_id)
    if not existing:
        return None

    # Build update data with only non-None fields
    update_data = {}

    if name is not None:
        update_data["name"] = name

    if token is not None:
        # Encrypt new token
        update_data["encrypted_token"] = encrypt_value(token)
        update_data["token_last4"] = token[-4:] if len(token) >= 4 else ""
        # Reset validation status when token changes
        update_data["validation_status"] = "pending"

    if location_id is not None:
        update_data["location_id"] = location_id

    if notes is not None:
        update_data["notes"] = notes

    # Always update timestamp
    update_data["updated_at"] = datetime.now(timezone.utc)

    # Update Firestore
    db = get_firestore_client()
    doc_ref = db.collection(GHL_CONNECTIONS_COLLECTION).document(connection_id)
    await doc_ref.update(update_data)

    logger.info(f"Updated connection {connection_id}")

    # Return updated connection
    return await get_connection(connection_id)


async def delete_connection(connection_id: str) -> bool:
    """
    Delete a connection.

    Args:
        connection_id: Connection document ID

    Returns:
        True if deleted, False if not found
    """
    from app.services.firestore_service import get_firestore_client

    # Check if exists first
    existing = await get_connection(connection_id)
    if not existing:
        return False

    # Delete
    db = get_firestore_client()
    doc_ref = db.collection(GHL_CONNECTIONS_COLLECTION).document(connection_id)
    await doc_ref.delete()

    logger.info(f"Deleted connection {connection_id}")

    return True


async def validate_connection(connection_id: str) -> dict:
    """
    Validate a connection by testing the token via GHL API.

    Args:
        connection_id: Connection document ID

    Returns:
        Dict with: valid (bool), error (str or None), users (list)

    Raises:
        ValueError: If connection not found
    """
    from app.services.firestore_service import get_firestore_client
    from app.services.ghl.client import GHLClient, GHLAPIError, GHLAuthError

    # Fetch connection with decrypted token
    connection = await get_connection(connection_id, decrypt_token=True)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    token = connection.get("token")
    location_id = connection.get("location_id")

    if not token or not location_id:
        raise ValueError("Connection missing token or location_id")

    # Try to validate via get_users
    validation_result = {
        "valid": False,
        "error": None,
        "users": [],
    }

    try:
        async with GHLClient(token=token, location_id=location_id) as client:
            response = await client.get_users()

            # Success - parse users
            users_data = response.get("users", [])
            validation_result["valid"] = True
            validation_result["users"] = users_data

            # Update validation status in Firestore
            db = get_firestore_client()
            doc_ref = db.collection(GHL_CONNECTIONS_COLLECTION).document(connection_id)
            await doc_ref.update({
                "validation_status": "valid",
                "updated_at": datetime.now(timezone.utc),
            })

            logger.info(f"Connection {connection_id} validated successfully")

    except GHLAuthError as e:
        # Auth error - invalid token
        validation_result["error"] = str(e)

        # Update validation status
        db = get_firestore_client()
        doc_ref = db.collection(GHL_CONNECTIONS_COLLECTION).document(connection_id)
        await doc_ref.update({
            "validation_status": "invalid",
            "updated_at": datetime.now(timezone.utc),
        })

        logger.warning(f"Connection {connection_id} validation failed: auth error")

    except GHLAPIError as e:
        # Other API error
        validation_result["error"] = str(e)

        # Update validation status
        db = get_firestore_client()
        doc_ref = db.collection(GHL_CONNECTIONS_COLLECTION).document(connection_id)
        await doc_ref.update({
            "validation_status": "invalid",
            "updated_at": datetime.now(timezone.utc),
        })

        logger.warning(f"Connection {connection_id} validation failed: {e}")

    return validation_result


async def get_connection_users(connection_id: str) -> list[dict]:
    """
    Fetch GHL users for a connection (for contact owner dropdown).

    Args:
        connection_id: Connection document ID

    Returns:
        List of user dicts (id, name, email, role)

    Raises:
        ValueError: If connection not found
    """
    from app.services.ghl.client import GHLClient

    # Fetch connection with decrypted token
    connection = await get_connection(connection_id, decrypt_token=True)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    token = connection.get("token")
    location_id = connection.get("location_id")

    if not token or not location_id:
        raise ValueError("Connection missing token or location_id")

    # Fetch users
    async with GHLClient(token=token, location_id=location_id) as client:
        response = await client.get_users()
        users = response.get("users", [])

    return users


async def upsert_contact_via_connection(
    connection_id: str,
    contact_data: dict,
) -> dict:
    """
    Upsert a contact via a GHL connection.

    Args:
        connection_id: Connection document ID
        contact_data: Contact data dict

    Returns:
        Dict with: success (bool), action (str), ghl_contact_id (str), error (str)

    Raises:
        ValueError: If connection not found
    """
    from app.services.ghl.client import GHLClient

    # Fetch connection with decrypted token
    connection = await get_connection(connection_id, decrypt_token=True)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    token = connection.get("token")
    location_id = connection.get("location_id")

    if not token or not location_id:
        raise ValueError("Connection missing token or location_id")

    # Upsert contact
    async with GHLClient(token=token, location_id=location_id) as client:
        result = await client.upsert_contact(contact_data)

    return result
