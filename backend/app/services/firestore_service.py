"""Firestore service for persistent data storage."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

from app.core.config import settings

logger = logging.getLogger(__name__)

# Firestore client (lazy initialization)
_db: Optional[AsyncClient] = None


def get_firestore_client() -> AsyncClient:
    """Get or create Firestore async client."""
    global _db
    if _db is None:
        _db = firestore.AsyncClient(
            project=settings.gcs_project_id,
            database="tablerocktools",
        )
    return _db


# =============================================================================
# Collection Names
# =============================================================================

USERS_COLLECTION = "users"
JOBS_COLLECTION = "jobs"
EXTRACT_ENTRIES_COLLECTION = "extract_entries"
TITLE_ENTRIES_COLLECTION = "title_entries"
PRORATION_ROWS_COLLECTION = "proration_rows"
REVENUE_STATEMENTS_COLLECTION = "revenue_statements"
RRC_OIL_COLLECTION = "rrc_oil_proration"
RRC_GAS_COLLECTION = "rrc_gas_proration"
RRC_SYNC_COLLECTION = "rrc_data_syncs"
AUDIT_LOGS_COLLECTION = "audit_logs"
APP_CONFIG_COLLECTION = "app_config"
USER_PREFERENCES_COLLECTION = "user_preferences"


# =============================================================================
# User Operations
# =============================================================================


async def get_or_create_user(
    firebase_uid: str,
    email: str,
    display_name: Optional[str] = None,
    photo_url: Optional[str] = None,
) -> dict:
    """Get existing user or create new one from Firebase auth."""
    db = get_firestore_client()
    user_ref = db.collection(USERS_COLLECTION).document(firebase_uid)
    user_doc = await user_ref.get()

    if user_doc.exists:
        # Update last login
        await user_ref.update({
            "last_login_at": datetime.utcnow(),
            "display_name": display_name or user_doc.to_dict().get("display_name"),
            "photo_url": photo_url or user_doc.to_dict().get("photo_url"),
        })
        return user_doc.to_dict()

    # Create new user
    user_data = {
        "id": firebase_uid,
        "email": email,
        "display_name": display_name,
        "photo_url": photo_url,
        "is_admin": False,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "last_login_at": datetime.utcnow(),
    }
    await user_ref.set(user_data)
    logger.info(f"Created new user: {email}")
    return user_data


# =============================================================================
# Job Operations
# =============================================================================


async def create_job(
    tool: str,
    source_filename: str,
    user_id: Optional[str] = None,
    source_file_size: Optional[int] = None,
    options: Optional[dict] = None,
) -> dict:
    """Create a new processing job."""
    db = get_firestore_client()
    job_id = str(uuid4())

    job_data = {
        "id": job_id,
        "user_id": user_id,
        "tool": tool,
        "status": "pending",
        "source_filename": source_filename,
        "source_file_size": source_file_size,
        "options": options or {},
        "total_count": 0,
        "success_count": 0,
        "error_count": 0,
        "error_message": None,
        "created_at": datetime.utcnow(),
        "completed_at": None,
    }

    await db.collection(JOBS_COLLECTION).document(job_id).set(job_data)
    logger.info(f"Created job {job_id} for {tool}")
    return job_data


async def update_job_status(
    job_id: str,
    status: str,
    total_count: int = 0,
    success_count: int = 0,
    error_count: int = 0,
    error_message: Optional[str] = None,
) -> Optional[dict]:
    """Update job status and counts."""
    db = get_firestore_client()
    job_ref = db.collection(JOBS_COLLECTION).document(job_id)

    update_data = {
        "status": status,
        "total_count": total_count,
        "success_count": success_count,
        "error_count": error_count,
        "error_message": error_message,
        "updated_at": datetime.utcnow(),
    }

    if status in ("completed", "failed"):
        update_data["completed_at"] = datetime.utcnow()

    await job_ref.update(update_data)
    logger.info(f"Updated job {job_id} status to {status}")

    job_doc = await job_ref.get()
    return job_doc.to_dict() if job_doc.exists else None


async def get_job(job_id: str) -> Optional[dict]:
    """Get job by ID."""
    db = get_firestore_client()
    job_doc = await db.collection(JOBS_COLLECTION).document(job_id).get()
    return job_doc.to_dict() if job_doc.exists else None


async def delete_job(job_id: str) -> bool:
    """Delete a job and all its associated entries."""
    db = get_firestore_client()
    job_doc = await db.collection(JOBS_COLLECTION).document(job_id).get()
    if not job_doc.exists:
        return False

    tool = job_doc.to_dict().get("tool")

    # Map tool to its entries collection
    entries_collection = {
        "extract": EXTRACT_ENTRIES_COLLECTION,
        "title": TITLE_ENTRIES_COLLECTION,
        "proration": PRORATION_ROWS_COLLECTION,
        "revenue": REVENUE_STATEMENTS_COLLECTION,
    }.get(tool)

    # Delete related entries
    if entries_collection:
        docs = await db.collection(entries_collection).where("job_id", "==", job_id).get()
        batch = db.batch()
        count = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            if count % 500 == 0:
                await batch.commit()
                batch = db.batch()
        if count % 500 != 0:
            await batch.commit()
        logger.info(f"Deleted {count} entries from {entries_collection} for job {job_id}")

    # Delete the job document
    await db.collection(JOBS_COLLECTION).document(job_id).delete()
    logger.info(f"Deleted job {job_id} ({tool})")
    return True


async def get_user_jobs(
    user_id: str,
    tool: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Get jobs for a user, optionally filtered by tool."""
    db = get_firestore_client()
    query = db.collection(JOBS_COLLECTION).where("user_id", "==", user_id)

    if tool:
        query = query.where("tool", "==", tool)

    try:
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        docs = await query.get()
    except Exception:
        # Composite index may not exist; query without ordering and sort in Python
        logger.warning("Firestore composite index missing for get_user_jobs, falling back to client-side sort")
        base_query = db.collection(JOBS_COLLECTION).where("user_id", "==", user_id)
        if tool:
            base_query = base_query.where("tool", "==", tool)
        docs = await base_query.limit(limit).get()
        docs = sorted(docs, key=lambda d: d.to_dict().get("created_at", ""), reverse=True)
    return [doc.to_dict() for doc in docs]


async def get_recent_jobs(
    tool: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Get recent jobs across all users."""
    db = get_firestore_client()
    query = db.collection(JOBS_COLLECTION)

    if tool:
        query = query.where("tool", "==", tool)

    try:
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        docs = await query.get()
    except Exception:
        # Composite index may not exist; query without ordering and sort in Python
        logger.warning("Firestore composite index missing for get_recent_jobs, falling back to client-side sort")
        base_query = db.collection(JOBS_COLLECTION)
        if tool:
            base_query = base_query.where("tool", "==", tool)
        docs = await base_query.limit(limit).get()
        docs = sorted(docs, key=lambda d: d.to_dict().get("created_at", ""), reverse=True)
    return [doc.to_dict() for doc in docs]


# =============================================================================
# Extract Entry Operations
# =============================================================================


async def save_extract_entries(job_id: str, entries: list[dict]) -> int:
    """Save extract entries for a job."""
    db = get_firestore_client()
    batch = db.batch()
    count = 0

    for entry_data in entries:
        doc_ref = db.collection(EXTRACT_ENTRIES_COLLECTION).document()
        entry_data["job_id"] = job_id
        entry_data["created_at"] = datetime.utcnow()
        batch.set(doc_ref, entry_data)
        count += 1

        # Firestore batch limit is 500
        if count % 500 == 0:
            await batch.commit()
            batch = db.batch()

    if count % 500 != 0:
        await batch.commit()

    logger.info(f"Saved {count} extract entries for job {job_id}")
    return count


async def get_extract_entries(job_id: str) -> list[dict]:
    """Get extract entries for a job."""
    db = get_firestore_client()
    docs = await db.collection(EXTRACT_ENTRIES_COLLECTION).where("job_id", "==", job_id).get()
    return [doc.to_dict() for doc in docs]


# =============================================================================
# Title Entry Operations
# =============================================================================


async def save_title_entries(job_id: str, entries: list[dict]) -> int:
    """Save title entries for a job."""
    db = get_firestore_client()
    batch = db.batch()
    count = 0

    for entry_data in entries:
        doc_ref = db.collection(TITLE_ENTRIES_COLLECTION).document()
        entry_data["job_id"] = job_id
        entry_data["created_at"] = datetime.utcnow()
        batch.set(doc_ref, entry_data)
        count += 1

        if count % 500 == 0:
            await batch.commit()
            batch = db.batch()

    if count % 500 != 0:
        await batch.commit()

    logger.info(f"Saved {count} title entries for job {job_id}")
    return count


async def get_title_entries(job_id: str) -> list[dict]:
    """Get title entries for a job."""
    db = get_firestore_client()
    docs = await db.collection(TITLE_ENTRIES_COLLECTION).where("job_id", "==", job_id).get()
    return [doc.to_dict() for doc in docs]


# =============================================================================
# Proration Row Operations
# =============================================================================


async def save_proration_rows(job_id: str, rows: list[dict]) -> int:
    """Save proration rows for a job."""
    db = get_firestore_client()
    batch = db.batch()
    count = 0

    for row_data in rows:
        doc_ref = db.collection(PRORATION_ROWS_COLLECTION).document()
        row_data["job_id"] = job_id
        row_data["created_at"] = datetime.utcnow()
        batch.set(doc_ref, row_data)
        count += 1

        if count % 500 == 0:
            await batch.commit()
            batch = db.batch()

    if count % 500 != 0:
        await batch.commit()

    logger.info(f"Saved {count} proration rows for job {job_id}")
    return count


async def get_proration_rows(job_id: str) -> list[dict]:
    """Get proration rows for a job."""
    db = get_firestore_client()
    docs = await db.collection(PRORATION_ROWS_COLLECTION).where("job_id", "==", job_id).get()
    return [doc.to_dict() for doc in docs]


# =============================================================================
# Revenue Statement Operations
# =============================================================================


async def save_revenue_statement(job_id: str, statement_data: dict) -> dict:
    """Save a revenue statement with its rows."""
    db = get_firestore_client()

    # Calculate totals from rows
    rows = statement_data.get("rows", [])
    total_gross = sum(r.get("owner_value", 0) or 0 for r in rows)
    total_tax = sum(r.get("owner_tax_amount", 0) or 0 for r in rows)
    total_deductions = sum(r.get("owner_deduct_amount", 0) or 0 for r in rows)
    total_net = sum(r.get("owner_net_revenue", 0) or 0 for r in rows)

    statement_id = str(uuid4())
    statement_doc = {
        "id": statement_id,
        "job_id": job_id,
        "filename": statement_data.get("filename", ""),
        "format": statement_data.get("format", "unknown"),
        "payor": statement_data.get("payor"),
        "operator_name": statement_data.get("operator_name"),
        "check_number": statement_data.get("check_number"),
        "check_amount": statement_data.get("check_amount"),
        "check_date": statement_data.get("check_date"),
        "owner_number": statement_data.get("owner_number"),
        "owner_name": statement_data.get("owner_name"),
        "total_rows": len(rows),
        "total_gross": total_gross,
        "total_tax": total_tax,
        "total_deductions": total_deductions,
        "total_net": total_net,
        "errors": statement_data.get("errors", []),
        "rows": rows,  # Store rows as subcollection or embedded
        "created_at": datetime.utcnow(),
    }

    await db.collection(REVENUE_STATEMENTS_COLLECTION).document(statement_id).set(statement_doc)
    logger.info(f"Saved revenue statement with {len(rows)} rows for job {job_id}")
    return statement_doc


async def get_revenue_statements(job_id: str) -> list[dict]:
    """Get revenue statements for a job."""
    db = get_firestore_client()
    docs = await db.collection(REVENUE_STATEMENTS_COLLECTION).where("job_id", "==", job_id).get()
    return [doc.to_dict() for doc in docs]


# =============================================================================
# RRC Data Operations
# =============================================================================


async def upsert_rrc_oil_record(
    district: str,
    lease_number: str,
    operator_name: Optional[str] = None,
    lease_name: Optional[str] = None,
    field_name: Optional[str] = None,
    county: Optional[str] = None,
    unit_acres: Optional[float] = None,
    allowable: Optional[float] = None,
    raw_data: Optional[dict] = None,
) -> tuple[dict, bool, bool]:
    """
    Insert or update an RRC oil proration record.
    Returns: (record, is_new, is_updated)
    """
    db = get_firestore_client()
    doc_id = f"{district}-{lease_number}"
    doc_ref = db.collection(RRC_OIL_COLLECTION).document(doc_id)
    doc = await doc_ref.get()

    record_data = {
        "district": district,
        "lease_number": lease_number,
        "operator_name": operator_name,
        "lease_name": lease_name,
        "field_name": field_name,
        "county": county,
        "unit_acres": unit_acres,
        "allowable": allowable,
        "raw_data": raw_data,
        "updated_at": datetime.utcnow(),
    }

    if doc.exists:
        existing = doc.to_dict()
        # Check if data changed
        changed = (
            existing.get("unit_acres") != unit_acres or
            existing.get("operator_name") != operator_name or
            existing.get("lease_name") != lease_name
        )
        if changed:
            await doc_ref.update(record_data)
            return record_data, False, True
        return existing, False, False
    else:
        record_data["created_at"] = datetime.utcnow()
        await doc_ref.set(record_data)
        return record_data, True, False


async def upsert_rrc_gas_record(
    district: str,
    lease_number: str,
    operator_name: Optional[str] = None,
    lease_name: Optional[str] = None,
    field_name: Optional[str] = None,
    county: Optional[str] = None,
    unit_acres: Optional[float] = None,
    allowable: Optional[float] = None,
    raw_data: Optional[dict] = None,
) -> tuple[dict, bool, bool]:
    """
    Insert or update an RRC gas proration record.
    Returns: (record, is_new, is_updated)
    """
    db = get_firestore_client()
    doc_id = f"{district}-{lease_number}"
    doc_ref = db.collection(RRC_GAS_COLLECTION).document(doc_id)
    doc = await doc_ref.get()

    record_data = {
        "district": district,
        "lease_number": lease_number,
        "operator_name": operator_name,
        "lease_name": lease_name,
        "field_name": field_name,
        "county": county,
        "unit_acres": unit_acres,
        "allowable": allowable,
        "raw_data": raw_data,
        "updated_at": datetime.utcnow(),
    }

    if doc.exists:
        existing = doc.to_dict()
        changed = (
            existing.get("unit_acres") != unit_acres or
            existing.get("operator_name") != operator_name or
            existing.get("lease_name") != lease_name
        )
        if changed:
            await doc_ref.update(record_data)
            return record_data, False, True
        return existing, False, False
    else:
        record_data["created_at"] = datetime.utcnow()
        await doc_ref.set(record_data)
        return record_data, True, False


async def lookup_rrc_acres(
    district: str,
    lease_number: str,
) -> Optional[dict]:
    """
    Look up RRC lease data from Firestore master database.

    Returns dict with: acres, type, operator, lease_name, field_name, county, row_count
    or None if not found.
    """
    db = get_firestore_client()
    doc_id = f"{district}-{lease_number}"

    oil_data = None
    gas_data = None

    # Check oil collection
    oil_doc = await db.collection(RRC_OIL_COLLECTION).document(doc_id).get()
    if oil_doc.exists:
        oil_data = oil_doc.to_dict()

    # Check gas collection
    gas_doc = await db.collection(RRC_GAS_COLLECTION).document(doc_id).get()
    if gas_doc.exists:
        gas_data = gas_doc.to_dict()

    if oil_data is None and gas_data is None:
        return None

    # Determine well type and pick best data source
    if oil_data and gas_data:
        well_type = "both"
        acres = max(oil_data.get("unit_acres") or 0, gas_data.get("unit_acres") or 0)
        primary = oil_data if (oil_data.get("unit_acres") or 0) >= (gas_data.get("unit_acres") or 0) else gas_data
    elif oil_data:
        well_type = "oil"
        acres = oil_data.get("unit_acres")
        primary = oil_data
    else:
        well_type = "gas"
        acres = gas_data.get("unit_acres")
        primary = gas_data

    return {
        "acres": acres,
        "type": well_type,
        "operator": primary.get("operator_name"),
        "lease_name": primary.get("lease_name"),
        "field_name": primary.get("field_name"),
        "county": primary.get("county"),
        "row_count": 1,
    }


async def lookup_rrc_by_lease_number(lease_number: str) -> Optional[dict]:
    """
    Look up RRC lease data by lease number only (searches across all districts).

    Returns dict with: acres, type, districts_found, operator, lease_name
    or None if not found.
    """
    db = get_firestore_client()

    total_acres = 0.0
    well_type = None
    districts_found = 0
    primary_data = None

    # Query oil collection for matching lease_number
    oil_query = db.collection(RRC_OIL_COLLECTION).where("lease_number", "==", lease_number)
    oil_docs = await oil_query.get()
    for doc in oil_docs:
        data = doc.to_dict()
        total_acres += data.get("unit_acres") or 0
        districts_found += 1
        if primary_data is None:
            primary_data = data
        well_type = "oil"

    # Query gas collection for matching lease_number
    gas_query = db.collection(RRC_GAS_COLLECTION).where("lease_number", "==", lease_number)
    gas_docs = await gas_query.get()
    for doc in gas_docs:
        data = doc.to_dict()
        gas_acres = data.get("unit_acres") or 0
        total_acres += gas_acres
        districts_found += 1
        if primary_data is None:
            primary_data = data
        well_type = "both" if well_type == "oil" else "gas"

    if primary_data is None:
        return None

    return {
        "acres": total_acres,
        "type": well_type or "unknown",
        "districts_found": districts_found,
        "operator": primary_data.get("operator_name"),
        "lease_name": primary_data.get("lease_name"),
        "row_count": districts_found,
    }


async def get_rrc_data_status() -> dict:
    """Get RRC data status from Firestore."""
    db = get_firestore_client()

    # Count oil records
    oil_count_query = db.collection(RRC_OIL_COLLECTION).count()
    oil_count_result = await oil_count_query.get()
    oil_rows = oil_count_result[0][0].value if oil_count_result else 0

    # Get latest oil update
    oil_latest_query = db.collection(RRC_OIL_COLLECTION).order_by(
        "updated_at", direction=firestore.Query.DESCENDING
    ).limit(1)
    oil_latest_docs = await oil_latest_query.get()
    oil_modified = None
    if oil_latest_docs:
        oil_modified = oil_latest_docs[0].to_dict().get("updated_at")

    # Count gas records
    gas_count_query = db.collection(RRC_GAS_COLLECTION).count()
    gas_count_result = await gas_count_query.get()
    gas_rows = gas_count_result[0][0].value if gas_count_result else 0

    # Get latest gas update
    gas_latest_query = db.collection(RRC_GAS_COLLECTION).order_by(
        "updated_at", direction=firestore.Query.DESCENDING
    ).limit(1)
    gas_latest_docs = await gas_latest_query.get()
    gas_modified = None
    if gas_latest_docs:
        gas_modified = gas_latest_docs[0].to_dict().get("updated_at")

    # Get last sync info
    sync_query = db.collection(RRC_SYNC_COLLECTION).where(
        "success", "==", True
    ).order_by("completed_at", direction=firestore.Query.DESCENDING).limit(1)
    sync_docs = await sync_query.get()
    last_sync = None
    if sync_docs:
        sync_data = sync_docs[0].to_dict()
        last_sync = {
            "completed_at": sync_data.get("completed_at").isoformat() if sync_data.get("completed_at") else None,
            "new_records": sync_data.get("new_records", 0),
            "updated_records": sync_data.get("updated_records", 0),
        }

    return {
        "oil_available": oil_rows > 0,
        "gas_available": gas_rows > 0,
        "oil_rows": oil_rows,
        "gas_rows": gas_rows,
        "oil_modified": oil_modified.isoformat() if oil_modified else None,
        "gas_modified": gas_modified.isoformat() if gas_modified else None,
        "last_sync": last_sync,
    }


async def start_rrc_sync(data_type: str) -> str:
    """Start a new RRC data sync and return sync ID."""
    db = get_firestore_client()
    sync_id = str(uuid4())

    sync_data = {
        "id": sync_id,
        "data_type": data_type,
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "total_records": 0,
        "new_records": 0,
        "updated_records": 0,
        "unchanged_records": 0,
        "success": False,
        "error_message": None,
    }

    await db.collection(RRC_SYNC_COLLECTION).document(sync_id).set(sync_data)
    return sync_id


async def complete_rrc_sync(
    sync_id: str,
    total_records: int,
    new_records: int,
    updated_records: int,
    unchanged_records: int,
    success: bool = True,
    error_message: Optional[str] = None,
) -> None:
    """Complete an RRC data sync."""
    db = get_firestore_client()
    completed_at = datetime.utcnow()

    sync_ref = db.collection(RRC_SYNC_COLLECTION).document(sync_id)
    sync_doc = await sync_ref.get()

    duration_seconds = None
    if sync_doc.exists:
        started_at = sync_doc.to_dict().get("started_at")
        if started_at:
            duration_seconds = (completed_at - started_at).total_seconds()

    await sync_ref.update({
        "completed_at": completed_at,
        "total_records": total_records,
        "new_records": new_records,
        "updated_records": updated_records,
        "unchanged_records": unchanged_records,
        "success": success,
        "error_message": error_message,
        "duration_seconds": duration_seconds,
    })


# =============================================================================
# Audit Log Operations
# =============================================================================


async def create_audit_log(
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Create an audit log entry."""
    db = get_firestore_client()

    log_data = {
        "id": str(uuid4()),
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": datetime.utcnow(),
    }

    await db.collection(AUDIT_LOGS_COLLECTION).add(log_data)
    return log_data


# =============================================================================
# App Config Operations (persistent settings)
# =============================================================================


async def get_config_doc(doc_id: str) -> Optional[dict]:
    """Get a config document from Firestore."""
    db = get_firestore_client()
    doc = await db.collection(APP_CONFIG_COLLECTION).document(doc_id).get()
    return doc.to_dict() if doc.exists else None


async def set_config_doc(doc_id: str, data: dict) -> None:
    """Set a config document in Firestore."""
    db = get_firestore_client()
    data["_updated_at"] = datetime.utcnow()
    await db.collection(APP_CONFIG_COLLECTION).document(doc_id).set(data)


# =============================================================================
# User Preferences Operations
# =============================================================================


async def get_user_preferences(email: str) -> Optional[dict]:
    """Get a user's preferences from Firestore."""
    db = get_firestore_client()
    doc_id = email.lower().replace("@", "_at_").replace(".", "_")
    doc = await db.collection(USER_PREFERENCES_COLLECTION).document(doc_id).get()
    return doc.to_dict() if doc.exists else None


async def set_user_preferences(email: str, prefs: dict) -> None:
    """Save a user's preferences to Firestore."""
    db = get_firestore_client()
    doc_id = email.lower().replace("@", "_at_").replace(".", "_")
    prefs["email"] = email.lower()
    prefs["_updated_at"] = datetime.utcnow()
    await db.collection(USER_PREFERENCES_COLLECTION).document(doc_id).set(prefs)
