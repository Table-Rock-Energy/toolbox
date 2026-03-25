"""Database service for CRUD operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Sequence
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import (
    AppConfig,
    AuditLog,
    ExtractEntry,
    GHLConnection,
    Job,
    JobStatus,
    ProrationRow,
    RRCCountyStatus,
    RRCMetadata,
    RevenueRow,
    RevenueStatement,
    RRCDataSync,
    RRCGasProration,
    RRCOilProration,
    TitleEntry,
    ToolType,
    User,
    UserPreference,
)

logger = logging.getLogger(__name__)


# =============================================================================
# User Operations
# =============================================================================


async def get_or_create_user(
    db: AsyncSession,
    firebase_uid: str,
    email: str,
    display_name: Optional[str] = None,
    photo_url: Optional[str] = None,
) -> User:
    """Get existing user or create new one from Firebase auth."""
    result = await db.execute(select(User).where(User.id == firebase_uid))
    user = result.scalar_one_or_none()

    if user:
        # Update last login
        user.last_login_at = datetime.utcnow()
        if display_name:
            user.display_name = display_name
        if photo_url:
            user.photo_url = photo_url
        await db.flush()
        return user

    # Create new user
    user = User(
        id=firebase_uid,
        email=email,
        display_name=display_name,
        photo_url=photo_url,
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()
    logger.info(f"Created new user: {email}")
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# =============================================================================
# Job Operations
# =============================================================================


async def create_job(
    db: AsyncSession,
    tool: ToolType,
    source_filename: str,
    user_id: Optional[str] = None,
    source_file_size: Optional[int] = None,
    options: Optional[dict] = None,
) -> Job:
    """Create a new processing job."""
    job = Job(
        id=str(uuid4()),
        user_id=user_id,
        tool=tool,
        status=JobStatus.PENDING,
        source_filename=source_filename,
        source_file_size=source_file_size,
        options=options or {},
    )
    db.add(job)
    await db.flush()
    logger.info(f"Created job {job.id} for {tool.value}")
    return job


async def update_job_status(
    db: AsyncSession,
    job_id: str,
    status: JobStatus,
    total_count: int = 0,
    success_count: int = 0,
    error_count: int = 0,
    error_message: Optional[str] = None,
) -> Optional[Job]:
    """Update job status and counts."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if job:
        job.status = status
        job.total_count = total_count
        job.success_count = success_count
        job.error_count = error_count
        job.error_message = error_message
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = datetime.utcnow()
        await db.flush()
        logger.info(f"Updated job {job_id} status to {status.value}")

    return job


async def get_job(db: AsyncSession, job_id: str) -> Optional[Job]:
    """Get job by ID."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def get_job_with_entries(db: AsyncSession, job_id: str) -> Optional[Job]:
    """Get job with all related entries loaded."""
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(
            selectinload(Job.extract_entries),
            selectinload(Job.title_entries),
            selectinload(Job.proration_rows),
            selectinload(Job.revenue_statements).selectinload(RevenueStatement.rows),
        )
    )
    return result.scalar_one_or_none()


async def get_user_jobs(
    db: AsyncSession,
    user_id: str,
    tool: Optional[ToolType] = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Job]:
    """Get jobs for a user, optionally filtered by tool."""
    query = select(Job).where(Job.user_id == user_id)
    if tool:
        query = query.where(Job.tool == tool)
    query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


async def get_recent_jobs(
    db: AsyncSession,
    tool: Optional[ToolType] = None,
    limit: int = 20,
) -> Sequence[Job]:
    """Get recent jobs across all users."""
    query = select(Job)
    if tool:
        query = query.where(Job.tool == tool)
    query = query.order_by(Job.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


# =============================================================================
# Extract Entry Operations
# =============================================================================


async def save_extract_entries(
    db: AsyncSession,
    job_id: str,
    entries: list[dict],
) -> int:
    """Save extract entries for a job."""
    count = 0
    for entry_data in entries:
        entry = ExtractEntry(
            job_id=job_id,
            entry_number=entry_data.get("entry_number", ""),
            primary_name=entry_data.get("primary_name", ""),
            first_name=entry_data.get("first_name"),
            middle_name=entry_data.get("middle_name"),
            last_name=entry_data.get("last_name"),
            suffix=entry_data.get("suffix"),
            entity_type=entry_data.get("entity_type", "Unknown"),
            mailing_address=entry_data.get("mailing_address"),
            city=entry_data.get("city"),
            state=entry_data.get("state"),
            zip_code=entry_data.get("zip_code"),
            notes=entry_data.get("notes"),
            flagged=entry_data.get("flagged", False),
            flag_reason=entry_data.get("flag_reason"),
        )
        db.add(entry)
        count += 1
    await db.flush()
    logger.info(f"Saved {count} extract entries for job {job_id}")
    return count


async def get_extract_entries(
    db: AsyncSession,
    job_id: str,
) -> Sequence[ExtractEntry]:
    """Get extract entries for a job."""
    result = await db.execute(
        select(ExtractEntry).where(ExtractEntry.job_id == job_id)
    )
    return result.scalars().all()


# =============================================================================
# Title Entry Operations
# =============================================================================


async def save_title_entries(
    db: AsyncSession,
    job_id: str,
    entries: list[dict],
) -> int:
    """Save title entries for a job."""
    count = 0
    for entry_data in entries:
        entry = TitleEntry(
            job_id=job_id,
            full_name=entry_data.get("full_name", ""),
            first_name=entry_data.get("first_name"),
            last_name=entry_data.get("last_name"),
            entity_type=entry_data.get("entity_type", "UNKNOWN"),
            address=entry_data.get("address"),
            city=entry_data.get("city"),
            state=entry_data.get("state"),
            zip_code=entry_data.get("zip_code"),
            legal_description=entry_data.get("legal_description", ""),
            notes=entry_data.get("notes"),
            duplicate_flag=entry_data.get("duplicate_flag", False),
            has_address=entry_data.get("has_address", False),
        )
        db.add(entry)
        count += 1
    await db.flush()
    logger.info(f"Saved {count} title entries for job {job_id}")
    return count


async def get_title_entries(
    db: AsyncSession,
    job_id: str,
) -> Sequence[TitleEntry]:
    """Get title entries for a job."""
    result = await db.execute(
        select(TitleEntry).where(TitleEntry.job_id == job_id)
    )
    return result.scalars().all()


# =============================================================================
# Proration Row Operations
# =============================================================================


async def save_proration_rows(
    db: AsyncSession,
    job_id: str,
    rows: list[dict],
) -> int:
    """Save proration rows for a job."""
    count = 0
    for row_data in rows:
        row = ProrationRow(
            job_id=job_id,
            owner=row_data.get("owner", ""),
            county=row_data.get("county", ""),
            state=row_data.get("state"),
            interest=row_data.get("interest", 0.0),
            interest_type=row_data.get("interest_type"),
            appraisal_value=row_data.get("appraisal_value"),
            legal_description=row_data.get("legal_description"),
            property_name=row_data.get("property"),
            property_id=row_data.get("property_id"),
            operator=row_data.get("operator"),
            raw_rrc=row_data.get("raw_rrc"),
            rrc_lease=row_data.get("rrc_lease"),
            district=row_data.get("district"),
            lease_number=row_data.get("lease_number"),
            block=row_data.get("block"),
            section=row_data.get("section"),
            abstract=row_data.get("abstract"),
            rrc_acres=row_data.get("rrc_acres"),
            est_nra=row_data.get("est_nra"),
            dollars_per_nra=row_data.get("dollars_per_nra"),
            well_type=row_data.get("well_type"),
            notes=row_data.get("notes"),
        )
        db.add(row)
        count += 1
    await db.flush()
    logger.info(f"Saved {count} proration rows for job {job_id}")
    return count


async def get_proration_rows(
    db: AsyncSession,
    job_id: str,
) -> Sequence[ProrationRow]:
    """Get proration rows for a job."""
    result = await db.execute(
        select(ProrationRow).where(ProrationRow.job_id == job_id)
    )
    return result.scalars().all()


# =============================================================================
# Revenue Statement Operations
# =============================================================================


async def save_revenue_statement(
    db: AsyncSession,
    job_id: str,
    statement_data: dict,
) -> RevenueStatement:
    """Save a revenue statement with its rows."""
    # Calculate totals from rows
    rows = statement_data.get("rows", [])
    total_gross = sum(r.get("owner_value", 0) or 0 for r in rows)
    total_tax = sum(r.get("owner_tax_amount", 0) or 0 for r in rows)
    total_deductions = sum(r.get("owner_deduct_amount", 0) or 0 for r in rows)
    total_net = sum(r.get("owner_net_revenue", 0) or 0 for r in rows)

    statement = RevenueStatement(
        job_id=job_id,
        filename=statement_data.get("filename", ""),
        format=statement_data.get("format", "unknown"),
        payor=statement_data.get("payor"),
        operator_name=statement_data.get("operator_name"),
        check_number=statement_data.get("check_number"),
        check_amount=statement_data.get("check_amount"),
        check_date=statement_data.get("check_date"),
        owner_number=statement_data.get("owner_number"),
        owner_name=statement_data.get("owner_name"),
        total_rows=len(rows),
        total_gross=total_gross,
        total_tax=total_tax,
        total_deductions=total_deductions,
        total_net=total_net,
        errors=statement_data.get("errors", []),
    )
    db.add(statement)
    await db.flush()

    # Save rows
    for row_data in rows:
        row = RevenueRow(
            statement_id=statement.id,
            property_name=row_data.get("property_name"),
            property_number=row_data.get("property_number"),
            sales_date=row_data.get("sales_date"),
            product_code=row_data.get("product_code"),
            product_description=row_data.get("product_description"),
            decimal_interest=row_data.get("decimal_interest"),
            interest_type=row_data.get("interest_type"),
            avg_price=row_data.get("avg_price"),
            property_gross_volume=row_data.get("property_gross_volume"),
            property_gross_revenue=row_data.get("property_gross_revenue"),
            owner_volume=row_data.get("owner_volume"),
            owner_value=row_data.get("owner_value"),
            owner_tax_amount=row_data.get("owner_tax_amount"),
            tax_type=row_data.get("tax_type"),
            owner_deduct_amount=row_data.get("owner_deduct_amount"),
            deduct_code=row_data.get("deduct_code"),
            owner_net_revenue=row_data.get("owner_net_revenue"),
        )
        db.add(row)

    await db.flush()
    logger.info(f"Saved revenue statement with {len(rows)} rows for job {job_id}")
    return statement


async def get_revenue_statements(
    db: AsyncSession,
    job_id: str,
) -> Sequence[RevenueStatement]:
    """Get revenue statements for a job with rows loaded."""
    result = await db.execute(
        select(RevenueStatement)
        .where(RevenueStatement.job_id == job_id)
        .options(selectinload(RevenueStatement.rows))
    )
    return result.scalars().all()


# =============================================================================
# Audit Log Operations
# =============================================================================


async def create_audit_log(
    db: AsyncSession,
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """Create an audit log entry."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    await db.flush()
    return log


# =============================================================================
# Statistics Operations
# =============================================================================


async def get_job_statistics(
    db: AsyncSession,
    user_id: Optional[str] = None,
) -> dict:
    """Get job statistics, optionally filtered by user."""
    query = select(
        Job.tool,
        func.count(Job.id).label("total_jobs"),
        func.sum(Job.total_count).label("total_entries"),
    ).group_by(Job.tool)

    if user_id:
        query = query.where(Job.user_id == user_id)

    result = await db.execute(query)
    rows = result.all()

    stats = {}
    for row in rows:
        stats[row.tool.value] = {
            "total_jobs": row.total_jobs,
            "total_entries": row.total_entries or 0,
        }

    return stats


# =============================================================================
# RRC Data Operations
# =============================================================================


async def start_rrc_sync(
    db: AsyncSession,
    data_type: str,  # 'oil' or 'gas'
) -> RRCDataSync:
    """Start a new RRC data sync."""
    sync = RRCDataSync(
        data_type=data_type,
    )
    db.add(sync)
    await db.flush()
    return sync


async def complete_rrc_sync(
    db: AsyncSession,
    sync_id: int,
    total_records: int,
    new_records: int,
    updated_records: int,
    unchanged_records: int,
    success: bool = True,
    error_message: Optional[str] = None,
) -> None:
    """Complete an RRC data sync."""
    result = await db.execute(select(RRCDataSync).where(RRCDataSync.id == sync_id))
    sync = result.scalar_one_or_none()

    if sync:
        sync.completed_at = datetime.utcnow()
        sync.total_records = total_records
        sync.new_records = new_records
        sync.updated_records = updated_records
        sync.unchanged_records = unchanged_records
        sync.success = success
        sync.error_message = error_message
        if sync.started_at:
            sync.duration_seconds = (sync.completed_at - sync.started_at).total_seconds()
        await db.flush()


async def upsert_rrc_oil_record(
    db: AsyncSession,
    district: str,
    lease_number: str,
    operator_name: Optional[str] = None,
    lease_name: Optional[str] = None,
    field_name: Optional[str] = None,
    county: Optional[str] = None,
    unit_acres: Optional[float] = None,
    allowable: Optional[float] = None,
    raw_data: Optional[dict] = None,
) -> tuple[RRCOilProration, bool, bool]:
    """
    Insert or update an RRC oil proration record.

    Returns: (record, is_new, is_updated)
    """
    # Check if record exists
    result = await db.execute(
        select(RRCOilProration).where(
            RRCOilProration.district == district,
            RRCOilProration.lease_number == lease_number,
        )
    )
    record = result.scalar_one_or_none()

    if record:
        # Check if data changed
        changed = False
        if operator_name and record.operator_name != operator_name:
            record.operator_name = operator_name
            changed = True
        if lease_name and record.lease_name != lease_name:
            record.lease_name = lease_name
            changed = True
        if field_name and record.field_name != field_name:
            record.field_name = field_name
            changed = True
        if county and record.county != county:
            record.county = county
            changed = True
        if unit_acres is not None and record.unit_acres != unit_acres:
            record.unit_acres = unit_acres
            changed = True
        if allowable is not None and record.allowable != allowable:
            record.allowable = allowable
            changed = True
        if raw_data and record.raw_data != raw_data:
            record.raw_data = raw_data
            changed = True

        if changed:
            record.data_date = datetime.utcnow()
            await db.flush()

        return record, False, changed
    else:
        # Create new record
        record = RRCOilProration(
            district=district,
            lease_number=lease_number,
            operator_name=operator_name,
            lease_name=lease_name,
            field_name=field_name,
            county=county,
            unit_acres=unit_acres,
            allowable=allowable,
            raw_data=raw_data,
            data_date=datetime.utcnow(),
        )
        db.add(record)
        await db.flush()
        return record, True, False


async def upsert_rrc_gas_record(
    db: AsyncSession,
    district: str,
    lease_number: str,
    operator_name: Optional[str] = None,
    lease_name: Optional[str] = None,
    field_name: Optional[str] = None,
    county: Optional[str] = None,
    unit_acres: Optional[float] = None,
    allowable: Optional[float] = None,
    raw_data: Optional[dict] = None,
) -> tuple[RRCGasProration, bool, bool]:
    """
    Insert or update an RRC gas proration record.

    Returns: (record, is_new, is_updated)
    """
    # Check if record exists
    result = await db.execute(
        select(RRCGasProration).where(
            RRCGasProration.district == district,
            RRCGasProration.lease_number == lease_number,
        )
    )
    record = result.scalar_one_or_none()

    if record:
        # Check if data changed
        changed = False
        if operator_name and record.operator_name != operator_name:
            record.operator_name = operator_name
            changed = True
        if lease_name and record.lease_name != lease_name:
            record.lease_name = lease_name
            changed = True
        if field_name and record.field_name != field_name:
            record.field_name = field_name
            changed = True
        if county and record.county != county:
            record.county = county
            changed = True
        if unit_acres is not None and record.unit_acres != unit_acres:
            record.unit_acres = unit_acres
            changed = True
        if allowable is not None and record.allowable != allowable:
            record.allowable = allowable
            changed = True
        if raw_data and record.raw_data != raw_data:
            record.raw_data = raw_data
            changed = True

        if changed:
            record.data_date = datetime.utcnow()
            await db.flush()

        return record, False, changed
    else:
        # Create new record
        record = RRCGasProration(
            district=district,
            lease_number=lease_number,
            operator_name=operator_name,
            lease_name=lease_name,
            field_name=field_name,
            county=county,
            unit_acres=unit_acres,
            allowable=allowable,
            raw_data=raw_data,
            data_date=datetime.utcnow(),
        )
        db.add(record)
        await db.flush()
        return record, True, False


async def lookup_rrc_acres(
    db: AsyncSession,
    district: str,
    lease_number: str,
) -> Optional[dict]:
    """
    Look up RRC lease data from PostgreSQL.

    Returns dict with: acres, type, operator, lease_name, field_name, county, row_count
    or None if not found.
    """
    oil_data = None
    gas_data = None

    # Check oil table
    result = await db.execute(
        select(RRCOilProration).where(
            RRCOilProration.district == district,
            RRCOilProration.lease_number == lease_number,
        )
    )
    oil_record = result.scalar_one_or_none()
    if oil_record is not None:
        oil_data = oil_record

    # Check gas table
    result = await db.execute(
        select(RRCGasProration).where(
            RRCGasProration.district == district,
            RRCGasProration.lease_number == lease_number,
        )
    )
    gas_record = result.scalar_one_or_none()
    if gas_record is not None:
        gas_data = gas_record

    if oil_data is None and gas_data is None:
        return None

    # Determine well type and pick best data source
    if oil_data and gas_data:
        well_type = "both"
        acres = max(oil_data.unit_acres or 0, gas_data.unit_acres or 0)
        primary = oil_data if (oil_data.unit_acres or 0) >= (gas_data.unit_acres or 0) else gas_data
    elif oil_data:
        well_type = "oil"
        acres = oil_data.unit_acres
        primary = oil_data
    else:
        well_type = "gas"
        acres = gas_data.unit_acres
        primary = gas_data

    return {
        "acres": acres,
        "type": well_type,
        "operator": primary.operator_name,
        "lease_name": primary.lease_name,
        "field_name": primary.field_name,
        "county": primary.county,
        "row_count": 1,
    }


async def get_rrc_data_status(db: AsyncSession) -> dict:
    """Get RRC data status from database."""
    # Count oil records
    oil_count = await db.execute(select(func.count(RRCOilProration.id)))
    oil_rows = oil_count.scalar() or 0

    # Get latest oil update
    oil_latest = await db.execute(
        select(func.max(RRCOilProration.updated_at))
    )
    oil_modified = oil_latest.scalar()

    # Count gas records
    gas_count = await db.execute(select(func.count(RRCGasProration.id)))
    gas_rows = gas_count.scalar() or 0

    # Get latest gas update
    gas_latest = await db.execute(
        select(func.max(RRCGasProration.updated_at))
    )
    gas_modified = gas_latest.scalar()

    # Get last sync info
    last_sync = await db.execute(
        select(RRCDataSync)
        .where(RRCDataSync.success == True)  # noqa: E712
        .order_by(RRCDataSync.completed_at.desc())
        .limit(1)
    )
    last_sync_record = last_sync.scalar_one_or_none()

    return {
        "oil_available": oil_rows > 0,
        "gas_available": gas_rows > 0,
        "oil_rows": oil_rows,
        "gas_rows": gas_rows,
        "oil_modified": oil_modified.isoformat() if oil_modified else None,
        "gas_modified": gas_modified.isoformat() if gas_modified else None,
        "last_sync": {
            "completed_at": last_sync_record.completed_at.isoformat() if last_sync_record else None,
            "new_records": last_sync_record.new_records if last_sync_record else 0,
            "updated_records": last_sync_record.updated_records if last_sync_record else 0,
        } if last_sync_record else None,
    }


# =============================================================================
# Job Deletion
# =============================================================================


async def delete_job(db: AsyncSession, job_id: str) -> bool:
    """Delete a job and all associated entries (cascade handles children)."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return False

    await db.delete(job)
    await db.flush()
    logger.info(f"Deleted job {job_id} ({job.tool.value})")
    return True


# =============================================================================
# RRC Lease Lookup (cross-district)
# =============================================================================


async def lookup_rrc_by_lease_number(
    db: AsyncSession,
    lease_number: str,
) -> list[dict]:
    """
    Search across ALL districts in both oil and gas tables by lease_number.

    Returns list of dicts with district, lease_name, operator, acres, type, field_name.
    """
    results = []

    # Query oil table
    oil_result = await db.execute(
        select(RRCOilProration).where(
            RRCOilProration.lease_number == lease_number
        )
    )
    for record in oil_result.scalars().all():
        results.append({
            "district": record.district,
            "lease_name": record.lease_name,
            "operator": record.operator_name,
            "acres": record.unit_acres,
            "type": "oil",
            "field_name": record.field_name,
        })

    # Query gas table
    gas_result = await db.execute(
        select(RRCGasProration).where(
            RRCGasProration.lease_number == lease_number
        )
    )
    for record in gas_result.scalars().all():
        results.append({
            "district": record.district,
            "lease_name": record.lease_name,
            "operator": record.operator_name,
            "acres": record.unit_acres,
            "type": "gas",
            "field_name": record.field_name,
        })

    return results


# =============================================================================
# RRC Metadata / Cached Status
# =============================================================================


async def get_rrc_cached_status(db: AsyncSession) -> Optional[dict]:
    """Read cached RRC status from rrc_metadata 'counts' row (O(1) read)."""
    result = await db.execute(
        select(RRCMetadata).where(RRCMetadata.key == "counts")
    )
    meta = result.scalar_one_or_none()
    if not meta:
        return None

    return {
        "oil_available": (meta.oil_rows or 0) > 0,
        "gas_available": (meta.gas_rows or 0) > 0,
        "oil_rows": meta.oil_rows or 0,
        "gas_rows": meta.gas_rows or 0,
        "oil_modified": meta.last_sync_at.isoformat() if meta.last_sync_at else None,
        "gas_modified": meta.last_sync_at.isoformat() if meta.last_sync_at else None,
        "last_sync": {
            "completed_at": meta.last_sync_at.isoformat() if meta.last_sync_at else None,
            "new_records": meta.new_records or 0,
            "updated_records": meta.updated_records or 0,
        } if meta.last_sync_at else None,
    }


async def update_rrc_metadata_counts(
    db: AsyncSession,
    oil_rows: int,
    gas_rows: int,
    last_sync_at: Optional[datetime] = None,
    new_records: int = 0,
    updated_records: int = 0,
) -> None:
    """Write/merge RRC counts to rrc_metadata 'counts' row."""
    result = await db.execute(
        select(RRCMetadata).where(RRCMetadata.key == "counts")
    )
    meta = result.scalar_one_or_none()

    if meta:
        meta.oil_rows = oil_rows
        meta.gas_rows = gas_rows
        if last_sync_at:
            meta.last_sync_at = last_sync_at
            meta.new_records = new_records
            meta.updated_records = updated_records
    else:
        meta = RRCMetadata(
            key="counts",
            oil_rows=oil_rows,
            gas_rows=gas_rows,
            last_sync_at=last_sync_at,
            new_records=new_records,
            updated_records=updated_records,
        )
        db.add(meta)

    await db.flush()


# =============================================================================
# RRC County Status Operations
# =============================================================================


async def get_counties_status(
    db: AsyncSession,
    keys: list[str],
) -> dict[str, RRCCountyStatus]:
    """Batch read county freshness status by key list.

    Returns dict mapping key -> RRCCountyStatus model instance.
    """
    if not keys:
        return {}

    result = await db.execute(
        select(RRCCountyStatus).where(RRCCountyStatus.key.in_(keys))
    )
    rows = result.scalars().all()
    return {row.key: row for row in rows}


async def update_county_status(
    db: AsyncSession,
    key: str,
    data: dict,
) -> None:
    """Upsert county download status by key (e.g. '08-003').

    data dict may contain: status, oil_record_count, error_message, last_downloaded_at.
    """
    result = await db.execute(
        select(RRCCountyStatus).where(RRCCountyStatus.key == key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        for field, value in data.items():
            if hasattr(existing, field):
                setattr(existing, field, value)
    else:
        county = RRCCountyStatus(key=key, **{
            k: v for k, v in data.items() if hasattr(RRCCountyStatus, k)
        })
        db.add(county)

    await db.flush()


async def get_all_tracked_county_keys(db: AsyncSession) -> list[str]:
    """Return all distinct county keys that have ever been downloaded."""
    result = await db.execute(select(RRCCountyStatus.key))
    return [row[0] for row in result.all()]


async def get_stale_counties(
    db: AsyncSession,
    keys: list[str],
) -> list[str]:
    """Return county keys that need a fresh download.

    A county is stale if:
    - No status row exists (never downloaded)
    - last_downloaded_at is before the 1st of the current month
    - status is 'failed'
    - oil_record_count is 0 with status 'success'
    """
    from datetime import timezone

    statuses = await get_counties_status(db, keys)

    first_of_month = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    stale = []
    for key in keys:
        status = statuses.get(key)
        if not status:
            stale.append(key)
            continue
        if status.status == "failed":
            stale.append(key)
            continue
        if (status.oil_record_count or 0) == 0 and status.status == "success":
            stale.append(key)
            continue
        last_dl = status.last_downloaded_at
        if not last_dl:
            stale.append(key)
            continue
        if last_dl.tzinfo is None:
            last_dl = last_dl.replace(tzinfo=timezone.utc)
        if last_dl < first_of_month:
            stale.append(key)

    return stale


# =============================================================================
# App Config Operations
# =============================================================================


async def get_config_doc(db: AsyncSession, doc_id: str) -> Optional[dict]:
    """Get a config document by key (e.g. 'enrichment_settings')."""
    result = await db.execute(
        select(AppConfig).where(AppConfig.key == doc_id)
    )
    config = result.scalar_one_or_none()
    return config.data if config else None


async def set_config_doc(db: AsyncSession, doc_id: str, data: dict) -> None:
    """Upsert a config document by key."""
    result = await db.execute(
        select(AppConfig).where(AppConfig.key == doc_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.data = data
    else:
        config = AppConfig(key=doc_id, data=data)
        db.add(config)

    await db.flush()


# =============================================================================
# User Preferences Operations
# =============================================================================


async def get_user_preferences(
    db: AsyncSession,
    user_email: str,
) -> Optional[dict]:
    """Get a user's preferences by looking up their user_id from email."""
    user_result = await db.execute(
        select(User).where(User.email == user_email)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return None

    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    pref = result.scalar_one_or_none()
    return pref.data if pref else None


async def set_user_preferences(
    db: AsyncSession,
    user_email: str,
    preferences: dict,
) -> None:
    """Upsert a user's preferences by email."""
    user_result = await db.execute(
        select(User).where(User.email == user_email)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        logger.warning(f"Cannot set preferences for unknown user: {user_email}")
        return

    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.data = preferences
    else:
        pref = UserPreference(user_id=user.id, data=preferences)
        db.add(pref)

    await db.flush()


# =============================================================================
# GHL Connection Operations
# =============================================================================


async def save_ghl_connection(
    db: AsyncSession,
    connection_data: dict,
) -> GHLConnection:
    """Create or update a GHL connection.

    connection_data should contain: name, encrypted_token, token_last4, location_id,
    and optionally: id (for update), notes, validation_status.
    """
    conn_id = connection_data.get("id")

    if conn_id:
        result = await db.execute(
            select(GHLConnection).where(GHLConnection.id == conn_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            for field in ("name", "encrypted_token", "token_last4", "location_id",
                          "notes", "validation_status"):
                if field in connection_data:
                    setattr(existing, field, connection_data[field])
            await db.flush()
            return existing

    conn = GHLConnection(
        name=connection_data.get("name", ""),
        encrypted_token=connection_data.get("encrypted_token", ""),
        token_last4=connection_data.get("token_last4", ""),
        location_id=connection_data.get("location_id", ""),
        notes=connection_data.get("notes"),
        validation_status=connection_data.get("validation_status", "pending"),
    )
    db.add(conn)
    await db.flush()
    return conn


async def get_ghl_connections(db: AsyncSession) -> Sequence[GHLConnection]:
    """Get all GHL connections."""
    result = await db.execute(
        select(GHLConnection).order_by(GHLConnection.created_at.desc())
    )
    return result.scalars().all()


async def get_ghl_connection(
    db: AsyncSession,
    connection_id: str,
) -> Optional[GHLConnection]:
    """Get a single GHL connection by id."""
    result = await db.execute(
        select(GHLConnection).where(GHLConnection.id == connection_id)
    )
    return result.scalar_one_or_none()


async def delete_ghl_connection(
    db: AsyncSession,
    connection_id: str,
) -> bool:
    """Delete a GHL connection by id."""
    result = await db.execute(
        select(GHLConnection).where(GHLConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return False

    await db.delete(conn)
    await db.flush()
    logger.info(f"Deleted GHL connection {connection_id}")
    return True
