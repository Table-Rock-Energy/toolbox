#!/usr/bin/env python3
"""One-time migration script: Firestore -> PostgreSQL.

Reads all Firestore collections and writes them to PostgreSQL tables
using the SQLAlchemy models defined in app.models.db_models.

Prerequisites (one-time install, NOT in requirements.txt):
    pip install firebase-admin google-cloud-firestore psycopg2-binary

Usage:
    python3 migrate_firestore_to_postgres.py \
        --service-account /path/to/service-account.json \
        --database-url postgresql://user:pass@localhost:5432/toolbox

    # Dry run (report counts only):
    python3 migrate_firestore_to_postgres.py \
        --service-account /path/to/key.json \
        --database-url postgresql://... \
        --dry-run

    # Migrate specific collections only:
    python3 migrate_firestore_to_postgres.py \
        --service-account /path/to/key.json \
        --database-url postgresql://... \
        --collections users,jobs,extract_entries
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any

try:
    from google.cloud import firestore as google_firestore
except ImportError:
    print("ERROR: google-cloud-firestore not installed.")
    print("Run: pip install firebase-admin google-cloud-firestore")
    sys.exit(1)

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app.core.database import Base
from app.models.db_models import (
    AppConfig,
    AuditLog,
    ExtractEntry,
    GHLConnection,
    Job,
    JobStatus,
    ProrationRow,
    RevenueRow,
    RevenueStatement,
    RRCCountyStatus,
    RRCDataSync,
    RRCGasProration,
    RRCMetadata,
    RRCOilProration,
    RRCSyncJob,
    TitleEntry,
    ToolType,
    User,
    UserPreference,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500

# Results tracking
results: list[dict[str, Any]] = []


def doc_to_dict(doc) -> dict[str, Any]:
    """Convert Firestore document to dict with id."""
    data = doc.to_dict() or {}
    data["_doc_id"] = doc.id
    return data


def safe_datetime(val: Any) -> datetime | None:
    """Convert Firestore timestamp or string to Python datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if hasattr(val, "timestamp"):
        # google.protobuf.timestamp_pb2 or DatetimeWithNanoseconds
        return datetime.fromtimestamp(val.timestamp(), tz=timezone.utc)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def safe_float(val: Any) -> float | None:
    """Convert to float safely."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_int(val: Any) -> int:
    """Convert to int safely, default 0."""
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def safe_str(val: Any, max_len: int | None = None) -> str | None:
    """Convert to string safely with optional truncation."""
    if val is None:
        return None
    s = str(val)
    if max_len and len(s) > max_len:
        s = s[:max_len]
    return s


def map_tool_type(val: Any) -> str | None:
    """Map Firestore tool string to ToolType enum value."""
    if val is None:
        return None
    s = str(val).lower().strip()
    mapping = {
        "extract": ToolType.EXTRACT,
        "title": ToolType.TITLE,
        "proration": ToolType.PRORATION,
        "revenue": ToolType.REVENUE,
        "ghl_prep": ToolType.GHL_PREP,
        "ghl-prep": ToolType.GHL_PREP,
        "ghl_send": ToolType.GHL_SEND,
        "ghl-send": ToolType.GHL_SEND,
    }
    return mapping.get(s, ToolType.EXTRACT)


def map_job_status(val: Any) -> str | None:
    """Map Firestore status string to JobStatus enum value."""
    if val is None:
        return JobStatus.COMPLETED
    s = str(val).lower().strip()
    mapping = {
        "pending": JobStatus.PENDING,
        "processing": JobStatus.PROCESSING,
        "completed": JobStatus.COMPLETED,
        "failed": JobStatus.FAILED,
    }
    return mapping.get(s, JobStatus.COMPLETED)


# =============================================================================
# Per-collection migration functions
# =============================================================================


def migrate_users(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate users collection."""
    docs = list(fs.collection("users").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            User(
                id=d["_doc_id"],
                email=d.get("email", f"unknown-{d['_doc_id']}@migrated"),
                display_name=safe_str(d.get("display_name") or d.get("displayName")),
                photo_url=safe_str(d.get("photo_url") or d.get("photoURL")),
                is_admin=bool(d.get("is_admin", False)),
                is_active=bool(d.get("is_active", True)),
                created_at=safe_datetime(d.get("created_at")) or datetime.now(timezone.utc),
                updated_at=safe_datetime(d.get("updated_at")) or datetime.now(timezone.utc),
                last_login_at=safe_datetime(d.get("last_login_at")),
                # Skip password_hash -- users will re-register with local auth
                role=safe_str(d.get("role", "user")),
                scope=safe_str(d.get("scope", "all")),
                tools=d.get("tools", []),
                added_by=safe_str(d.get("added_by")),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_jobs(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate jobs collection."""
    docs = list(fs.collection("jobs").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            Job(
                id=d["_doc_id"],
                user_id=safe_str(d.get("user_id")),
                tool=map_tool_type(d.get("tool")),
                status=map_job_status(d.get("status")),
                source_filename=safe_str(d.get("source_filename", "unknown"), 255),
                source_file_size=safe_int(d.get("source_file_size")),
                total_count=safe_int(d.get("total_count")),
                success_count=safe_int(d.get("success_count")),
                error_count=safe_int(d.get("error_count")),
                error_message=safe_str(d.get("error_message")),
                options=d.get("options", {}),
                created_at=safe_datetime(d.get("created_at")) or datetime.now(timezone.utc),
                completed_at=safe_datetime(d.get("completed_at")),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_extract_entries(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate extract_entries collection."""
    docs = list(fs.collection("extract_entries").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            ExtractEntry(
                job_id=safe_str(d.get("job_id")),
                entry_number=safe_str(d.get("entry_number", ""), 20),
                primary_name=safe_str(d.get("primary_name", ""), 500),
                first_name=safe_str(d.get("first_name"), 100),
                middle_name=safe_str(d.get("middle_name"), 100),
                last_name=safe_str(d.get("last_name"), 100),
                suffix=safe_str(d.get("suffix"), 20),
                entity_type=safe_str(d.get("entity_type", "Unknown"), 50),
                mailing_address=safe_str(d.get("mailing_address"), 500),
                city=safe_str(d.get("city"), 100),
                state=safe_str(d.get("state"), 2),
                zip_code=safe_str(d.get("zip_code"), 20),
                notes=safe_str(d.get("notes")),
                flagged=bool(d.get("flagged", False)),
                flag_reason=safe_str(d.get("flag_reason"), 255),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_title_entries(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate title_entries collection."""
    docs = list(fs.collection("title_entries").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            TitleEntry(
                job_id=safe_str(d.get("job_id")),
                full_name=safe_str(d.get("full_name", ""), 500),
                first_name=safe_str(d.get("first_name"), 100),
                last_name=safe_str(d.get("last_name"), 100),
                entity_type=safe_str(d.get("entity_type", "Unknown"), 50),
                address=safe_str(d.get("address"), 500),
                city=safe_str(d.get("city"), 100),
                state=safe_str(d.get("state"), 2),
                zip_code=safe_str(d.get("zip_code"), 20),
                legal_description=safe_str(d.get("legal_description", ""), 100),
                notes=safe_str(d.get("notes")),
                duplicate_flag=bool(d.get("duplicate_flag", False)),
                has_address=bool(d.get("has_address", False)),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_proration_rows(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate proration_rows collection."""
    docs = list(fs.collection("proration_rows").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            ProrationRow(
                job_id=safe_str(d.get("job_id")),
                owner=safe_str(d.get("owner", ""), 500),
                county=safe_str(d.get("county", ""), 100),
                state=safe_str(d.get("state"), 2),
                interest=safe_float(d.get("interest")) or 0.0,
                interest_type=safe_str(d.get("interest_type"), 50),
                appraisal_value=safe_float(d.get("appraisal_value")),
                legal_description=safe_str(d.get("legal_description"), 255),
                property_name=safe_str(d.get("property_name"), 255),
                property_id=safe_str(d.get("property_id"), 100),
                operator=safe_str(d.get("operator"), 255),
                raw_rrc=safe_str(d.get("raw_rrc"), 100),
                rrc_lease=safe_str(d.get("rrc_lease"), 100),
                district=safe_str(d.get("district"), 10),
                lease_number=safe_str(d.get("lease_number"), 50),
                block=safe_str(d.get("block"), 50),
                section=safe_str(d.get("section"), 50),
                abstract=safe_str(d.get("abstract"), 50),
                rrc_acres=safe_float(d.get("rrc_acres")),
                est_nra=safe_float(d.get("est_nra")),
                dollars_per_nra=safe_float(d.get("dollars_per_nra")),
                well_type=safe_str(d.get("well_type"), 20),
                notes=safe_str(d.get("notes")),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_revenue_statements(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate revenue_statements collection (includes nested rows)."""
    docs = list(fs.collection("revenue_statements").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    pg_count = 0
    for doc in docs:
        d = doc_to_dict(doc)
        stmt = RevenueStatement(
            job_id=safe_str(d.get("job_id")),
            filename=safe_str(d.get("filename", ""), 255),
            format=safe_str(d.get("format", "unknown"), 50),
            payor=safe_str(d.get("payor"), 255),
            operator_name=safe_str(d.get("operator_name"), 255),
            check_number=safe_str(d.get("check_number"), 100),
            check_amount=safe_float(d.get("check_amount")),
            check_date=safe_str(d.get("check_date"), 20),
            owner_number=safe_str(d.get("owner_number"), 100),
            owner_name=safe_str(d.get("owner_name"), 255),
            total_rows=safe_int(d.get("total_rows")),
            total_gross=safe_float(d.get("total_gross")),
            total_tax=safe_float(d.get("total_tax")),
            total_deductions=safe_float(d.get("total_deductions")),
            total_net=safe_float(d.get("total_net")),
            errors=d.get("errors", []),
        )
        session.add(stmt)
        session.flush()  # Get the auto-generated stmt.id

        # Migrate nested rows (from subcollection or inline array)
        rows_data = d.get("rows", [])
        if isinstance(rows_data, list):
            for row_d in rows_data:
                if not isinstance(row_d, dict):
                    continue
                row = RevenueRow(
                    statement_id=stmt.id,
                    property_name=safe_str(row_d.get("property_name"), 255),
                    property_number=safe_str(row_d.get("property_number"), 100),
                    sales_date=safe_str(row_d.get("sales_date"), 20),
                    product_code=safe_str(row_d.get("product_code"), 20),
                    product_description=safe_str(row_d.get("product_description"), 100),
                    decimal_interest=safe_float(row_d.get("decimal_interest")),
                    interest_type=safe_str(row_d.get("interest_type"), 50),
                    avg_price=safe_float(row_d.get("avg_price")),
                    property_gross_volume=safe_float(row_d.get("property_gross_volume")),
                    property_gross_revenue=safe_float(row_d.get("property_gross_revenue")),
                    owner_volume=safe_float(row_d.get("owner_volume")),
                    owner_value=safe_float(row_d.get("owner_value")),
                    owner_tax_amount=safe_float(row_d.get("owner_tax_amount")),
                    tax_type=safe_str(row_d.get("tax_type"), 50),
                    owner_deduct_amount=safe_float(row_d.get("owner_deduct_amount")),
                    deduct_code=safe_str(row_d.get("deduct_code"), 50),
                    owner_net_revenue=safe_float(row_d.get("owner_net_revenue")),
                )
                session.add(row)

        # Also check for a subcollection named "revenue_rows"
        sub_rows = list(fs.collection("revenue_statements").document(doc.id).collection("revenue_rows").stream())
        for sub_doc in sub_rows:
            row_d = sub_doc.to_dict() or {}
            row = RevenueRow(
                statement_id=stmt.id,
                property_name=safe_str(row_d.get("property_name"), 255),
                property_number=safe_str(row_d.get("property_number"), 100),
                sales_date=safe_str(row_d.get("sales_date"), 20),
                product_code=safe_str(row_d.get("product_code"), 20),
                product_description=safe_str(row_d.get("product_description"), 100),
                decimal_interest=safe_float(row_d.get("decimal_interest")),
                interest_type=safe_str(row_d.get("interest_type"), 50),
                avg_price=safe_float(row_d.get("avg_price")),
                property_gross_volume=safe_float(row_d.get("property_gross_volume")),
                property_gross_revenue=safe_float(row_d.get("property_gross_revenue")),
                owner_volume=safe_float(row_d.get("owner_volume")),
                owner_value=safe_float(row_d.get("owner_value")),
                owner_tax_amount=safe_float(row_d.get("owner_tax_amount")),
                tax_type=safe_str(row_d.get("tax_type"), 50),
                owner_deduct_amount=safe_float(row_d.get("owner_deduct_amount")),
                deduct_code=safe_str(row_d.get("deduct_code"), 50),
                owner_net_revenue=safe_float(row_d.get("owner_net_revenue")),
            )
            session.add(row)

        pg_count += 1
        if pg_count % 100 == 0:
            session.commit()
            logger.info("  revenue_statements: %d committed", pg_count)

    session.commit()
    return fs_count, pg_count


def _migrate_rrc_batch(
    fs: google_firestore.Client,
    session: Session,
    collection_name: str,
    model_class: type,
    dry_run: bool,
) -> tuple[int, int]:
    """Batch-migrate large RRC collections (oil/gas proration)."""
    fs_count = 0
    pg_count = 0
    batch: list = []

    for doc in fs.collection(collection_name).stream():
        fs_count += 1
        if dry_run:
            continue

        d = doc_to_dict(doc)
        obj = model_class(
            district=safe_str(d.get("district"), 10) or "",
            lease_number=safe_str(d.get("lease_number"), 50) or "",
            operator_name=safe_str(d.get("operator_name"), 255),
            lease_name=safe_str(d.get("lease_name"), 255),
            field_name=safe_str(d.get("field_name"), 255),
            county=safe_str(d.get("county"), 100),
            unit_acres=safe_float(d.get("unit_acres")),
            allowable=safe_float(d.get("allowable")),
            raw_data=d.get("raw_data"),
            created_at=safe_datetime(d.get("created_at")) or datetime.now(timezone.utc),
            updated_at=safe_datetime(d.get("updated_at")) or datetime.now(timezone.utc),
            data_date=safe_datetime(d.get("data_date")),
        )
        batch.append(obj)

        if len(batch) >= BATCH_SIZE:
            session.bulk_save_objects(batch)
            session.commit()
            pg_count += len(batch)
            batch = []
            if pg_count % 1000 == 0:
                logger.info("  %s: %d records migrated", collection_name, pg_count)

    if batch and not dry_run:
        session.bulk_save_objects(batch)
        session.commit()
        pg_count += len(batch)

    return fs_count, pg_count


def migrate_rrc_oil(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate rrc_oil_proration (large collection, batched)."""
    return _migrate_rrc_batch(fs, session, "rrc_oil_proration", RRCOilProration, dry_run)


def migrate_rrc_gas(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate rrc_gas_proration (large collection, batched)."""
    return _migrate_rrc_batch(fs, session, "rrc_gas_proration", RRCGasProration, dry_run)


def migrate_rrc_data_syncs(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate rrc_data_syncs collection."""
    docs = list(fs.collection("rrc_data_syncs").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            RRCDataSync(
                data_type=safe_str(d.get("data_type", "unknown"), 20),
                total_records=safe_int(d.get("total_records")),
                new_records=safe_int(d.get("new_records")),
                updated_records=safe_int(d.get("updated_records")),
                unchanged_records=safe_int(d.get("unchanged_records")),
                started_at=safe_datetime(d.get("started_at")) or datetime.now(timezone.utc),
                completed_at=safe_datetime(d.get("completed_at")),
                duration_seconds=safe_float(d.get("duration_seconds")),
                success=bool(d.get("success", False)),
                error_message=safe_str(d.get("error_message")),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_rrc_county_status(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate rrc_county_status collection."""
    docs = list(fs.collection("rrc_county_status").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            RRCCountyStatus(
                key=safe_str(d["_doc_id"], 20),
                status=safe_str(d.get("status", "pending"), 20),
                oil_record_count=safe_int(d.get("oil_record_count")),
                last_downloaded_at=safe_datetime(d.get("last_downloaded_at")),
                error_message=safe_str(d.get("error_message")),
                updated_at=safe_datetime(d.get("updated_at")) or datetime.now(timezone.utc),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_audit_logs(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate audit_logs collection."""
    docs = list(fs.collection("audit_logs").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            AuditLog(
                user_id=safe_str(d.get("user_id")),
                action=safe_str(d.get("action", "unknown"), 100),
                resource_type=safe_str(d.get("resource_type"), 50),
                resource_id=safe_str(d.get("resource_id"), 128),
                details=d.get("details"),
                ip_address=safe_str(d.get("ip_address"), 45),
                user_agent=safe_str(d.get("user_agent"), 500),
                created_at=safe_datetime(d.get("created_at")) or datetime.now(timezone.utc),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_app_config(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate app_config collection (doc ID -> key, rest -> data JSONB)."""
    docs = list(fs.collection("app_config").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        doc_id = d.pop("_doc_id")
        objects.append(
            AppConfig(
                key=safe_str(doc_id, 100),
                data=d,
                updated_at=safe_datetime(d.get("updated_at")) or datetime.now(timezone.utc),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_user_preferences(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate user_preferences collection."""
    docs = list(fs.collection("user_preferences").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        doc_id = d.pop("_doc_id")
        objects.append(
            UserPreference(
                user_id=safe_str(d.get("user_id", doc_id), 128),
                data=d,
                updated_at=safe_datetime(d.get("updated_at")) or datetime.now(timezone.utc),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_ghl_connections(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate ghl_connections collection."""
    docs = list(fs.collection("ghl_connections").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            GHLConnection(
                id=d["_doc_id"],
                name=safe_str(d.get("name", ""), 255),
                encrypted_token=safe_str(d.get("encrypted_token", "")),
                token_last4=safe_str(d.get("token_last4", ""), 4),
                location_id=safe_str(d.get("location_id", ""), 255),
                notes=safe_str(d.get("notes")),
                validation_status=safe_str(d.get("validation_status", "pending"), 20),
                created_at=safe_datetime(d.get("created_at")) or datetime.now(timezone.utc),
                updated_at=safe_datetime(d.get("updated_at")) or datetime.now(timezone.utc),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_rrc_sync_jobs(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate rrc_sync_jobs collection."""
    docs = list(fs.collection("rrc_sync_jobs").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            RRCSyncJob(
                id=d["_doc_id"],
                status=safe_str(d.get("status", "completed"), 30),
                started_at=safe_datetime(d.get("started_at")) or datetime.now(timezone.utc),
                completed_at=safe_datetime(d.get("completed_at")),
                oil_rows=safe_int(d.get("oil_rows")),
                gas_rows=safe_int(d.get("gas_rows")),
                error=safe_str(d.get("error")),
                steps=d.get("steps", []),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


def migrate_rrc_metadata(
    fs: google_firestore.Client, session: Session, dry_run: bool
) -> tuple[int, int]:
    """Migrate rrc_metadata collection."""
    docs = list(fs.collection("rrc_metadata").stream())
    fs_count = len(docs)
    if dry_run:
        return fs_count, 0

    objects = []
    for doc in docs:
        d = doc_to_dict(doc)
        objects.append(
            RRCMetadata(
                key=safe_str(d["_doc_id"], 50),
                oil_rows=safe_int(d.get("oil_rows")),
                gas_rows=safe_int(d.get("gas_rows")),
                last_sync_at=safe_datetime(d.get("last_sync_at")),
                new_records=safe_int(d.get("new_records")),
                updated_records=safe_int(d.get("updated_records")),
                updated_at=safe_datetime(d.get("updated_at")) or datetime.now(timezone.utc),
            )
        )
    session.bulk_save_objects(objects)
    session.commit()
    return fs_count, len(objects)


# =============================================================================
# Collection registry
# =============================================================================

COLLECTION_HANDLERS = {
    "users": migrate_users,
    "jobs": migrate_jobs,
    "extract_entries": migrate_extract_entries,
    "title_entries": migrate_title_entries,
    "proration_rows": migrate_proration_rows,
    "revenue_statements": migrate_revenue_statements,
    "rrc_oil_proration": migrate_rrc_oil,
    "rrc_gas_proration": migrate_rrc_gas,
    "rrc_data_syncs": migrate_rrc_data_syncs,
    "rrc_county_status": migrate_rrc_county_status,
    "audit_logs": migrate_audit_logs,
    "app_config": migrate_app_config,
    "user_preferences": migrate_user_preferences,
    "ghl_connections": migrate_ghl_connections,
    "rrc_sync_jobs": migrate_rrc_sync_jobs,
    "rrc_metadata": migrate_rrc_metadata,
}


# =============================================================================
# Main
# =============================================================================


def print_summary(results: list[dict[str, Any]]) -> None:
    """Print migration summary table."""
    print()
    print("=" * 65)
    print("  Migration Summary")
    print("=" * 65)
    print(f"{'Collection':<25} | {'Firestore':>10} | {'PostgreSQL':>10} | {'Status':<8}")
    print("-" * 25 + " | " + "-" * 10 + " | " + "-" * 10 + " | " + "-" * 8)

    total_fs = 0
    total_pg = 0
    for r in results:
        total_fs += r["fs_count"]
        total_pg += r["pg_count"]
        print(
            f"{r['collection']:<25} | {r['fs_count']:>10} | {r['pg_count']:>10} | {r['status']:<8}"
        )

    print("-" * 25 + " | " + "-" * 10 + " | " + "-" * 10 + " | " + "-" * 8)
    print(f"{'TOTAL':<25} | {total_fs:>10} | {total_pg:>10} |")
    print("=" * 65)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate Firestore collections to PostgreSQL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full migration
  python3 migrate_firestore_to_postgres.py \\
    --service-account /path/to/key.json \\
    --database-url postgresql://user:pass@localhost:5432/toolbox

  # Dry run (counts only)
  python3 migrate_firestore_to_postgres.py \\
    --service-account /path/to/key.json \\
    --database-url postgresql://... \\
    --dry-run

  # Specific collections
  python3 migrate_firestore_to_postgres.py \\
    --service-account /path/to/key.json \\
    --database-url postgresql://... \\
    --collections users,jobs
        """,
    )
    parser.add_argument(
        "--service-account",
        required=True,
        help="Path to Firestore service account JSON key",
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="PostgreSQL connection URL (psycopg2 format: postgresql://user:pass@host:5432/db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report Firestore counts without writing to PostgreSQL",
    )
    parser.add_argument(
        "--collections",
        type=str,
        default=None,
        help="Comma-separated list of collections to migrate (default: all)",
    )

    args = parser.parse_args()

    # Determine which collections to migrate
    if args.collections:
        collections = [c.strip() for c in args.collections.split(",")]
        invalid = [c for c in collections if c not in COLLECTION_HANDLERS]
        if invalid:
            print(f"ERROR: Unknown collections: {', '.join(invalid)}")
            print(f"Valid collections: {', '.join(COLLECTION_HANDLERS.keys())}")
            sys.exit(1)
    else:
        collections = list(COLLECTION_HANDLERS.keys())

    # Initialize Firestore client
    logger.info("Connecting to Firestore with service account: %s", args.service_account)
    fs = google_firestore.Client.from_service_account_json(args.service_account)

    # Initialize PostgreSQL engine (sync, using psycopg2)
    logger.info("Connecting to PostgreSQL: %s", args.database_url.split("@")[-1])
    engine = create_engine(args.database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)

    # Create tables if they don't exist
    logger.info("Ensuring PostgreSQL tables exist...")
    Base.metadata.create_all(engine)

    if args.dry_run:
        logger.info("DRY RUN -- will report counts without writing")

    # Migrate each collection
    start_time = time.time()

    for collection_name in collections:
        handler = COLLECTION_HANDLERS[collection_name]
        logger.info("Migrating: %s", collection_name)

        try:
            session = SessionLocal()
            fs_count, pg_count = handler(fs, session, args.dry_run)
            session.close()

            status = "DRY-RUN" if args.dry_run else "OK"
            results.append(
                {
                    "collection": collection_name,
                    "fs_count": fs_count,
                    "pg_count": pg_count,
                    "status": status,
                }
            )
            logger.info(
                "  %s: %d Firestore docs -> %d PostgreSQL rows [%s]",
                collection_name,
                fs_count,
                pg_count,
                status,
            )

        except Exception as e:
            logger.error("  ERROR migrating %s: %s", collection_name, e)
            results.append(
                {
                    "collection": collection_name,
                    "fs_count": 0,
                    "pg_count": 0,
                    "status": "ERROR",
                }
            )

    elapsed = time.time() - start_time

    # Print summary
    print_summary(results)
    print(f"\nCompleted in {elapsed:.1f} seconds")

    # Verify counts by querying PostgreSQL
    if not args.dry_run:
        print("\n--- PostgreSQL Verification ---")
        session = SessionLocal()
        inspector = inspect(engine)
        for table_name in inspector.get_table_names():
            count = session.execute(
                __import__("sqlalchemy").text(f"SELECT COUNT(*) FROM {table_name}")
            ).scalar()
            print(f"  {table_name}: {count} rows")
        session.close()


if __name__ == "__main__":
    main()
