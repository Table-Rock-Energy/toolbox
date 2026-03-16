"""Pydantic models for OCC Exhibit A extraction (extract tool)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.ai_validation import PostProcessResult  # noqa: F401


class EntityType(str, Enum):
    """Types of entities found in Exhibit A documents."""

    INDIVIDUAL = "Individual"
    TRUST = "Trust"
    LLC = "LLC"
    CORPORATION = "Corporation"
    PARTNERSHIP = "Partnership"
    GOVERNMENT = "Government"
    ESTATE = "Estate"
    UNKNOWN_HEIRS = "Unknown Heirs"


class CaseMetadata(BaseModel):
    """Metadata extracted from ECF filing header."""

    county: Optional[str] = Field(None, description="County name (e.g., 'CADDO')")
    legal_description: Optional[str] = Field(
        None, description="Section/Township/Range legal description"
    )
    applicant: Optional[str] = Field(None, description="Applicant company name")
    case_number: Optional[str] = Field(None, description="OCC cause number")
    well_name: Optional[str] = Field(None, description="Well name from application")


class PartyEntry(BaseModel):
    """A single party/stakeholder entry extracted from Exhibit A."""

    entry_number: str = Field(..., description="Entry number (e.g., '1', '2', 'U1')")
    primary_name: str = Field(..., description="Main legal name, cleaned")
    entity_type: EntityType = Field(
        default=EntityType.INDIVIDUAL, description="Type of entity"
    )
    mailing_address: Optional[str] = Field(
        None, description="Primary street address (number and street name)"
    )
    mailing_address_2: Optional[str] = Field(
        None, description="Secondary address line (apt, suite, unit, etc.)"
    )
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="2-letter state abbreviation")
    zip_code: Optional[str] = Field(None, description="ZIP or ZIP+4 code")
    first_name: Optional[str] = Field(
        None, description="First name (individuals only)"
    )
    middle_name: Optional[str] = Field(
        None, description="Middle name or initial (individuals only)"
    )
    last_name: Optional[str] = Field(
        None, description="Last name (individuals only)"
    )
    suffix: Optional[str] = Field(
        None, description="Name suffix (Jr., Sr., III, etc.)"
    )
    notes: Optional[str] = Field(
        None,
        description="All a/k/a, f/k/a, c/o, trustee info, trust dates, etc.",
    )
    flagged: bool = Field(
        default=False, description="True if parsing confidence is low"
    )
    flag_reason: Optional[str] = Field(None, description="Why entry was flagged")
    section_type: Optional[str] = Field(
        None,
        description="ECF section: regular, curative, address_unknown, curative_unknown, informational",
    )


class ExtractionResult(BaseModel):
    """Result of extracting party information from a PDF."""

    success: bool = Field(..., description="Whether extraction was successful")
    entries: list[PartyEntry] = Field(
        default_factory=list, description="List of extracted party entries"
    )
    total_count: int = Field(0, description="Total number of entries extracted")
    flagged_count: int = Field(0, description="Number of flagged entries")
    error_message: Optional[str] = Field(
        None, description="Error message if extraction failed"
    )
    source_filename: Optional[str] = Field(None, description="Original PDF filename")
    job_id: Optional[str] = Field(None, description="Firestore job ID")
    format_detected: Optional[str] = Field(
        None, description="Auto-detected format (e.g., TABLE_ATTENTION, FREE_TEXT_LIST)"
    )
    quality_score: Optional[float] = Field(
        None, description="Parsing quality score 0.0-1.0"
    )
    format_warning: Optional[str] = Field(
        None, description="Warning if quality is low or format uncertain"
    )
    case_metadata: Optional[CaseMetadata] = Field(
        None, description="Case metadata from ECF filing header"
    )
    merge_warnings: Optional[list[str]] = Field(
        None, description="Warnings from merge process"
    )
    original_csv_entries: Optional[list[dict]] = Field(
        None, description="Original CSV entries before merge (ECF only, for cross-file comparison)"
    )
    post_process: Optional[PostProcessResult] = Field(
        None, description="Auto-correction results from post-processing pipeline"
    )


class UploadResponse(BaseModel):
    """Response model for PDF upload endpoint."""

    message: str = Field(..., description="Status message")
    result: Optional[ExtractionResult] = Field(
        None, description="Extraction result if successful"
    )


class ExportRequest(BaseModel):
    """Request model for export endpoints."""

    entries: list[PartyEntry] = Field(
        ..., description="List of party entries to export"
    )
    filename: Optional[str] = Field(
        "exhibit_a_export", description="Base filename for export (without extension)"
    )
    county: Optional[str] = Field(
        None, description="County name to populate in mineral export"
    )
    campaign_name: Optional[str] = Field(
        None, description="Campaign name to populate in mineral export"
    )
    case_metadata: Optional[CaseMetadata] = Field(
        None, description="Case metadata for Notes/Comments population"
    )
