"""Pydantic models for OCC Exhibit A extraction (extract tool)."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
