"""SQLAlchemy database models for persistent storage."""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ToolType(str, PyEnum):
    """Tool types in the toolbox."""

    EXTRACT = "extract"
    TITLE = "title"
    PRORATION = "proration"
    REVENUE = "revenue"


class JobStatus(str, PyEnum):
    """Status of a processing job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# User Model
# =============================================================================


class User(Base):
    """User model - synced from Firebase Auth."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # Firebase UID
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    photo_url: Mapped[Optional[str]] = mapped_column(String(512))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# =============================================================================
# Job Model (Processing History)
# =============================================================================


class Job(Base):
    """Processing job - tracks all tool executions."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(128), ForeignKey("users.id"), nullable=True
    )
    tool: Mapped[ToolType] = mapped_column(Enum(ToolType), index=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING
    )

    # File info
    source_filename: Mapped[str] = mapped_column(String(255))
    source_file_size: Mapped[Optional[int]] = mapped_column(Integer)

    # Processing results
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Processing options (stored as JSON)
    options: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="jobs")
    extract_entries: Mapped[list["ExtractEntry"]] = relationship(
        "ExtractEntry", back_populates="job", cascade="all, delete-orphan"
    )
    title_entries: Mapped[list["TitleEntry"]] = relationship(
        "TitleEntry", back_populates="job", cascade="all, delete-orphan"
    )
    proration_rows: Mapped[list["ProrationRow"]] = relationship(
        "ProrationRow", back_populates="job", cascade="all, delete-orphan"
    )
    revenue_statements: Mapped[list["RevenueStatement"]] = relationship(
        "RevenueStatement", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Job {self.id} {self.tool.value} {self.status.value}>"


# =============================================================================
# Extract Tool Models
# =============================================================================


class ExtractEntry(Base):
    """Extracted party entry from OCC Exhibit A."""

    __tablename__ = "extract_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id"), index=True
    )

    # Entry data
    entry_number: Mapped[str] = mapped_column(String(20))
    primary_name: Mapped[str] = mapped_column(String(500))
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    middle_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    suffix: Mapped[Optional[str]] = mapped_column(String(20))
    entity_type: Mapped[str] = mapped_column(String(50))

    # Address
    mailing_address: Mapped[Optional[str]] = mapped_column(String(500))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(2))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationship
    job: Mapped["Job"] = relationship("Job", back_populates="extract_entries")

    def __repr__(self) -> str:
        return f"<ExtractEntry {self.entry_number} {self.primary_name}>"


# =============================================================================
# Title Tool Models
# =============================================================================


class TitleEntry(Base):
    """Owner entry from title opinion."""

    __tablename__ = "title_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id"), index=True
    )

    # Owner data
    full_name: Mapped[str] = mapped_column(String(500))
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))

    # Address
    address: Mapped[Optional[str]] = mapped_column(String(500))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(2))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))

    # Title info
    legal_description: Mapped[str] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    has_address: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationship
    job: Mapped["Job"] = relationship("Job", back_populates="title_entries")

    def __repr__(self) -> str:
        return f"<TitleEntry {self.full_name}>"


# =============================================================================
# Proration Tool Models
# =============================================================================


class ProrationRow(Base):
    """Proration calculation row."""

    __tablename__ = "proration_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id"), index=True
    )

    # Owner info
    owner: Mapped[str] = mapped_column(String(500))
    county: Mapped[str] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(2))

    # Interest data
    interest: Mapped[float] = mapped_column(Float)
    interest_type: Mapped[Optional[str]] = mapped_column(String(50))
    appraisal_value: Mapped[Optional[float]] = mapped_column(Float)

    # Property info
    legal_description: Mapped[Optional[str]] = mapped_column(String(255))
    property_name: Mapped[Optional[str]] = mapped_column(String(255))
    property_id: Mapped[Optional[str]] = mapped_column(String(100))
    operator: Mapped[Optional[str]] = mapped_column(String(255))

    # RRC data
    raw_rrc: Mapped[Optional[str]] = mapped_column(String(100))
    rrc_lease: Mapped[Optional[str]] = mapped_column(String(100))
    district: Mapped[Optional[str]] = mapped_column(String(10))
    lease_number: Mapped[Optional[str]] = mapped_column(String(50))

    # Parsed legal description
    block: Mapped[Optional[str]] = mapped_column(String(50))
    section: Mapped[Optional[str]] = mapped_column(String(50))
    abstract: Mapped[Optional[str]] = mapped_column(String(50))

    # Calculated values
    rrc_acres: Mapped[Optional[float]] = mapped_column(Float)
    est_nra: Mapped[Optional[float]] = mapped_column(Float)
    dollars_per_nra: Mapped[Optional[float]] = mapped_column(Float)
    well_type: Mapped[Optional[str]] = mapped_column(String(20))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationship
    job: Mapped["Job"] = relationship("Job", back_populates="proration_rows")

    def __repr__(self) -> str:
        return f"<ProrationRow {self.owner} {self.county}>"


# =============================================================================
# Revenue Tool Models
# =============================================================================


class RevenueStatement(Base):
    """Revenue statement from PDF."""

    __tablename__ = "revenue_statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id"), index=True
    )

    # Statement info
    filename: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(50))  # energylink, energy_transfer
    payor: Mapped[Optional[str]] = mapped_column(String(255))
    operator_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Check info
    check_number: Mapped[Optional[str]] = mapped_column(String(100))
    check_amount: Mapped[Optional[float]] = mapped_column(Float)
    check_date: Mapped[Optional[str]] = mapped_column(String(20))

    # Owner info
    owner_number: Mapped[Optional[str]] = mapped_column(String(100))
    owner_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Totals
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    total_gross: Mapped[Optional[float]] = mapped_column(Float)
    total_tax: Mapped[Optional[float]] = mapped_column(Float)
    total_deductions: Mapped[Optional[float]] = mapped_column(Float)
    total_net: Mapped[Optional[float]] = mapped_column(Float)

    # Errors (stored as JSON array)
    errors: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # Relationship
    job: Mapped["Job"] = relationship("Job", back_populates="revenue_statements")
    rows: Mapped[list["RevenueRow"]] = relationship(
        "RevenueRow", back_populates="statement", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<RevenueStatement {self.filename} {self.payor}>"


class RevenueRow(Base):
    """Individual revenue row from statement."""

    __tablename__ = "revenue_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    statement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("revenue_statements.id"), index=True
    )

    # Property info
    property_name: Mapped[Optional[str]] = mapped_column(String(255))
    property_number: Mapped[Optional[str]] = mapped_column(String(100))

    # Sales info
    sales_date: Mapped[Optional[str]] = mapped_column(String(20))
    product_code: Mapped[Optional[str]] = mapped_column(String(20))
    product_description: Mapped[Optional[str]] = mapped_column(String(100))

    # Interest
    decimal_interest: Mapped[Optional[float]] = mapped_column(Float)
    interest_type: Mapped[Optional[str]] = mapped_column(String(50))

    # Values
    avg_price: Mapped[Optional[float]] = mapped_column(Float)
    property_gross_volume: Mapped[Optional[float]] = mapped_column(Float)
    property_gross_revenue: Mapped[Optional[float]] = mapped_column(Float)
    owner_volume: Mapped[Optional[float]] = mapped_column(Float)
    owner_value: Mapped[Optional[float]] = mapped_column(Float)
    owner_tax_amount: Mapped[Optional[float]] = mapped_column(Float)
    tax_type: Mapped[Optional[str]] = mapped_column(String(50))
    owner_deduct_amount: Mapped[Optional[float]] = mapped_column(Float)
    deduct_code: Mapped[Optional[str]] = mapped_column(String(50))
    owner_net_revenue: Mapped[Optional[float]] = mapped_column(Float)

    # Relationship
    statement: Mapped["RevenueStatement"] = relationship(
        "RevenueStatement", back_populates="rows"
    )

    def __repr__(self) -> str:
        return f"<RevenueRow {self.property_name} {self.sales_date}>"


# =============================================================================
# RRC Data Models
# =============================================================================


class RRCOilProration(Base):
    """RRC Oil proration schedule data."""

    __tablename__ = "rrc_oil_proration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Key fields for lookup
    district: Mapped[str] = mapped_column(String(10), index=True)
    lease_number: Mapped[str] = mapped_column(String(50), index=True)

    # RRC data fields
    operator_name: Mapped[Optional[str]] = mapped_column(String(255))
    lease_name: Mapped[Optional[str]] = mapped_column(String(255))
    field_name: Mapped[Optional[str]] = mapped_column(String(255))
    county: Mapped[Optional[str]] = mapped_column(String(100))

    # Proration data
    unit_acres: Mapped[Optional[float]] = mapped_column(Float)
    allowable: Mapped[Optional[float]] = mapped_column(Float)

    # Additional RRC fields (stored as JSON for flexibility)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Tracking
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    data_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Composite unique constraint
    __table_args__ = (
        {"postgresql_ignore_search_path": True},
    )

    def __repr__(self) -> str:
        return f"<RRCOilProration {self.district}-{self.lease_number}>"


class RRCGasProration(Base):
    """RRC Gas proration schedule data."""

    __tablename__ = "rrc_gas_proration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Key fields for lookup
    district: Mapped[str] = mapped_column(String(10), index=True)
    lease_number: Mapped[str] = mapped_column(String(50), index=True)

    # RRC data fields
    operator_name: Mapped[Optional[str]] = mapped_column(String(255))
    lease_name: Mapped[Optional[str]] = mapped_column(String(255))
    field_name: Mapped[Optional[str]] = mapped_column(String(255))
    county: Mapped[Optional[str]] = mapped_column(String(100))

    # Proration data
    unit_acres: Mapped[Optional[float]] = mapped_column(Float)
    allowable: Mapped[Optional[float]] = mapped_column(Float)

    # Additional RRC fields (stored as JSON for flexibility)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Tracking
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    data_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<RRCGasProration {self.district}-{self.lease_number}>"


class RRCDataSync(Base):
    """Track RRC data sync history."""

    __tablename__ = "rrc_data_syncs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_type: Mapped[str] = mapped_column(String(20))  # 'oil' or 'gas'

    # Sync results
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    new_records: Mapped[int] = mapped_column(Integer, default=0)
    updated_records: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_records: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)

    # Status
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<RRCDataSync {self.data_type} {self.started_at}>"


# =============================================================================
# Audit Log Model
# =============================================================================


class AuditLog(Base):
    """Audit log for tracking all actions."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(128), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100))  # e.g., "export", "upload", "login"
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))  # e.g., "job", "user"
    resource_id: Mapped[Optional[str]] = mapped_column(String(128))
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.created_at}>"
