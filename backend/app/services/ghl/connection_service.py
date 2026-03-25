"""
GHL Connection CRUD Service

Provides PostgreSQL CRUD operations for GHL connections with encrypted token storage.
Handles connection validation, user listing, and contact upsert delegation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _conn_to_dict(conn, include_token: bool = False) -> dict:
    """Convert a GHLConnection ORM instance to a dict for API responses."""
    result = {
        "id": conn.id,
        "name": conn.name,
        "token_last4": conn.token_last4,
        "location_id": conn.location_id,
        "notes": conn.notes or "",
        "validation_status": conn.validation_status or "pending",
        "created_at": conn.created_at,
        "updated_at": conn.updated_at,
    }
    if include_token:
        from app.services.shared.encryption import decrypt_value
        result["token"] = decrypt_value(conn.encrypted_token)
    return result


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
    from app.core.database import async_session_maker
    from app.services import db_service
    from app.services.shared.encryption import encrypt_value

    # Encrypt token
    encrypted_token = encrypt_value(token)
    token_last4 = token[-4:] if len(token) >= 4 else ""

    async with async_session_maker() as session:
        conn = await db_service.save_ghl_connection(session, {
            "name": name,
            "encrypted_token": encrypted_token,
            "token_last4": token_last4,
            "location_id": location_id,
            "notes": notes or "",
            "validation_status": "pending",
        })
        await session.commit()

        result = _conn_to_dict(conn)

    logger.info(f"Created connection {result['id']}")
    return result


async def get_connection(
    connection_id: str,
    decrypt_token: bool = False,
) -> Optional[dict]:
    """
    Fetch a connection by ID.

    Args:
        connection_id: Connection ID
        decrypt_token: If True, decrypt and include token in result

    Returns:
        Connection dict or None if not found
    """
    from app.core.database import async_session_maker
    from app.services import db_service

    async with async_session_maker() as session:
        conn = await db_service.get_ghl_connection(session, connection_id)
        if not conn:
            return None
        return _conn_to_dict(conn, include_token=decrypt_token)


async def list_connections() -> list[dict]:
    """
    List all GHL connections.

    Returns:
        List of connection dicts sorted by name (no encrypted tokens)
    """
    from app.core.database import async_session_maker
    from app.services import db_service

    async with async_session_maker() as session:
        connections = await db_service.get_ghl_connections(session)
        result = [_conn_to_dict(c) for c in connections]

    # Sort by name
    result.sort(key=lambda c: c.get("name", "").lower())
    return result


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
        connection_id: Connection ID
        name: New name (if provided)
        token: New token (if provided, will be encrypted)
        location_id: New location ID (if provided)
        notes: New notes (if provided)

    Returns:
        Updated connection dict or None if not found
    """
    from app.core.database import async_session_maker
    from app.services import db_service
    from app.services.shared.encryption import encrypt_value

    # Build update data
    update_data = {"id": connection_id}

    if name is not None:
        update_data["name"] = name
    if token is not None:
        update_data["encrypted_token"] = encrypt_value(token)
        update_data["token_last4"] = token[-4:] if len(token) >= 4 else ""
        update_data["validation_status"] = "pending"
    if location_id is not None:
        update_data["location_id"] = location_id
    if notes is not None:
        update_data["notes"] = notes

    async with async_session_maker() as session:
        conn = await db_service.save_ghl_connection(session, update_data)
        await session.commit()
        result = _conn_to_dict(conn)

    logger.info(f"Updated connection {connection_id}")
    return result


async def delete_connection(connection_id: str) -> bool:
    """
    Delete a connection.

    Args:
        connection_id: Connection ID

    Returns:
        True if deleted, False if not found
    """
    from app.core.database import async_session_maker
    from app.services import db_service

    async with async_session_maker() as session:
        deleted = await db_service.delete_ghl_connection(session, connection_id)
        await session.commit()

    if deleted:
        logger.info(f"Deleted connection {connection_id}")
    return deleted


async def validate_connection(connection_id: str) -> dict:
    """
    Validate a connection by testing the token via GHL API.

    Args:
        connection_id: Connection ID

    Returns:
        Dict with: valid (bool), error (str or None), users (list)

    Raises:
        ValueError: If connection not found
    """
    from app.core.database import async_session_maker
    from app.services import db_service
    from app.services.ghl.client import GHLClient, GHLAPIError, GHLAuthError

    # Fetch connection with decrypted token
    connection = await get_connection(connection_id, decrypt_token=True)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    token = connection.get("token")
    location_id = connection.get("location_id")

    if not token or not location_id:
        raise ValueError("Connection missing token or location_id")

    validation_result = {
        "valid": False,
        "error": None,
        "users": [],
    }

    new_status = "invalid"

    try:
        async with GHLClient(token=token, location_id=location_id) as client:
            response = await client.get_users()
            users_data = response.get("users", [])
            validation_result["valid"] = True
            validation_result["users"] = users_data
            new_status = "valid"
            logger.info(f"Connection {connection_id} validated successfully")

    except GHLAuthError as e:
        validation_result["error"] = str(e)
        logger.warning(f"Connection {connection_id} validation failed: auth error")

    except GHLAPIError as e:
        validation_result["error"] = str(e)
        logger.warning(f"Connection {connection_id} validation failed: {e}")

    # Update validation status in database
    async with async_session_maker() as session:
        await db_service.save_ghl_connection(session, {
            "id": connection_id,
            "validation_status": new_status,
        })
        await session.commit()

    return validation_result


async def get_connection_users(connection_id: str) -> list[dict]:
    """
    Fetch GHL users for a connection (for contact owner dropdown).

    Args:
        connection_id: Connection ID

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
        connection_id: Connection ID
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
