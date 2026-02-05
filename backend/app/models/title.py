"""Pydantic models for Title Processing Tool."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Types of entities found in title documents."""

    INDIVIDUAL = "INDIVIDUAL"
    CORPORATION = "CORPORATION"
    TRUST = "TRUST"
    ESTATE = "ESTATE"
    FOUNDATION = "FOUNDATION"
    MINERAL_CO = "MINERAL CO"
    UNIVERSITY = "UNIVERSITY"
    CHURCH = "CHURCH"
    UNKNOWN = "UNKNOWN"


class OwnerEntry(BaseModel):
    """A single owner entry extracted from title documents."""

    full_name: str = Field(..., description="Complete entity name")
    first_name: Optional[str] = Field(None, description="Parsed first name (individuals only)")
    last_name: Optional[str] = Field(None, description="Parsed last name (individuals only)")
    entity_type: EntityType = Field(
        default=EntityType.INDIVIDUAL, description="Type of entity"
    )
    address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="2-letter state code")
    zip_code: Optional[str] = Field(None, description="ZIP code")
    legal_description: str = Field(..., description="Section-Township-Range")
    notes: Optional[str] = Field(None, description="Additional info, a/k/a, references")
    duplicate_flag: bool = Field(
        default=False, description="TRUE if name appears multiple times with different info"
    )
    has_address: bool = Field(
        default=False, description="TRUE if address info is present"
    )


class FilterOptions(BaseModel):
    """Options for filtering export results."""

    hide_no_address: bool = Field(
        default=False, description="Filter out entries without addresses"
    )
    hide_duplicates: bool = Field(
        default=False, description="Show only first occurrence of duplicate names"
    )
    sections: Optional[list[str]] = Field(
        None, description="Filter by specific legal descriptions"
    )


class ProcessingResult(BaseModel):
    """Result of processing title documents."""

    success: bool = Field(..., description="Whether processing was successful")
    entries: list[OwnerEntry] = Field(
        default_factory=list, description="List of extracted owner entries"
    )
    total_count: int = Field(0, description="Total number of entries extracted")
    duplicate_count: int = Field(0, description="Number of duplicate entries")
    no_address_count: int = Field(0, description="Number of entries without address")
    sections: list[str] = Field(
        default_factory=list, description="List of legal descriptions found"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if processing failed"
    )
    source_filename: Optional[str] = Field(None, description="Original filename")


class UploadResponse(BaseModel):
    """Response model for file upload endpoint."""

    message: str = Field(..., description="Status message")
    result: Optional[ProcessingResult] = Field(
        None, description="Processing result if successful"
    )


class ExportRequest(BaseModel):
    """Request model for export endpoints."""

    entries: list[OwnerEntry] = Field(
        ..., description="List of owner entries to export"
    )
    filters: Optional[FilterOptions] = Field(
        None, description="Filter options for export"
    )
    filename: Optional[str] = Field(
        "title_export", description="Base filename for export (without extension)"
    )
    format_type: Optional[str] = Field(
        "standard", description="Export format type: 'standard' or 'mineral'"
    )


# Column definitions for CSV/Excel export
EXPORT_COLUMNS = [
    "Full Name",
    "First Name",
    "Last Name",
    "Entity Type",
    "Address",
    "City",
    "State",
    "Zip",
    "Legal Description",
    "Notes",
    "Duplicate Flag",
    "Has Address",
]
