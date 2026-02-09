"""Pydantic models for Proration tool."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WellType(str, Enum):
    """Types of wells (oil or gas)."""

    OIL = "oil"
    GAS = "gas"
    BOTH = "both"
    UNKNOWN = "unknown"


class MineralHolderRow(BaseModel):
    """A single row from the mineral holders CSV."""

    county: str = Field(..., description="County name")
    state: Optional[str] = Field(None, description="State abbreviation")
    year: Optional[int] = Field(None, description="Year")
    interest_key: Optional[str] = Field(None, description="Interest Key")
    owner_id: Optional[str] = Field(None, description="Owner ID")
    owner: str = Field(..., description="Owner name")
    interest: float = Field(..., description="Interest as decimal (e.g., 0.25 for 25%)")
    interest_type: Optional[str] = Field(None, description="Interest Type")
    appraisal_value: Optional[float] = Field(None, description="Appraisal Value")
    legal_description: Optional[str] = Field(None, description="Legal Description")
    property_id: Optional[str] = Field(None, description="Property ID")
    property: Optional[str] = Field(None, description="Property name")
    operator: Optional[str] = Field(None, description="Operator name")
    raw_rrc: Optional[str] = Field(None, description="Raw RRC identifier")
    rrc_lease: Optional[str] = Field(None, description="RRC Lease # (e.g., '08-41100')")
    new_record: Optional[str] = Field(None, description="New Record flag (Y/N)")
    estimated_monthly_revenue: Optional[float] = Field(
        None, description="Estimated Monthly Revenue"
    )
    estimated_net_bbl: Optional[float] = Field(None, description="Estimated Net BBL")
    estimated_net_mcf: Optional[float] = Field(None, description="Estimated Net MCF")

    # Calculated fields
    district: Optional[str] = Field(None, description="RRC District (e.g., '08')")
    lease_number: Optional[str] = Field(None, description="RRC Lease Number (e.g., '41100')")
    block: Optional[str] = Field(None, description="Block extracted from Legal Description")
    section: Optional[str] = Field(None, description="Section extracted from Legal Description")
    abstract: Optional[str] = Field(None, description="Abstract extracted from Legal Description")
    rrc_acres: Optional[float] = Field(None, description="Unit Acres from RRC query")
    est_nra: Optional[float] = Field(None, description="Estimated Net Royalty Acres")
    dollars_per_nra: Optional[float] = Field(None, description="$/NRA")
    notes: Optional[str] = Field(None, description="Notes and error messages")
    well_type: Optional[WellType] = Field(None, description="Determined well type")


class FilterOptions(BaseModel):
    """Filtering options for CSV processing."""

    new_record_only: bool = Field(
        default=False, description="Filter to only rows where New Record = 'Y'"
    )
    min_appraisal_value: float = Field(
        default=0.0, description="Minimum Appraisal Value threshold"
    )
    counties: Optional[list[str]] = Field(
        default=None, description="List of counties to include (None = all)"
    )
    owners: Optional[list[str]] = Field(
        default=None, description="List of owners to include (None = all)"
    )
    deduplicate: bool = Field(
        default=False, description="Deduplicate by Property ID or RRC Lease #"
    )


class ProcessingOptions(BaseModel):
    """Options for processing mineral holder data."""

    filters: FilterOptions = Field(default_factory=FilterOptions)
    well_type_override: Optional[WellType] = Field(
        default=None, description="Override auto-detected well type"
    )
    query_rrc: bool = Field(
        default=True, description="Whether to query RRC websites for unit acres"
    )
    delay_between_queries: float = Field(
        default=1.5, description="Delay in seconds between RRC queries"
    )


class ProcessingResult(BaseModel):
    """Result of processing a CSV file."""

    success: bool = Field(..., description="Whether processing was successful")
    total_rows: int = Field(0, description="Total rows in CSV")
    filtered_rows: int = Field(0, description="Number of rows after filtering")
    processed_rows: int = Field(0, description="Number of rows successfully processed")
    failed_rows: int = Field(0, description="Number of rows that failed processing")
    matched_rows: int = Field(0, description="Number of rows matched with RRC data")
    rows: list[MineralHolderRow] = Field(
        default_factory=list, description="Processed rows with calculations"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if processing failed"
    )
    source_filename: Optional[str] = Field(None, description="Original CSV filename")
    job_id: Optional[str] = Field(None, description="Firestore job ID")


class RRCDataStatus(BaseModel):
    """Status of RRC proration data."""

    oil_available: bool = Field(False, description="Whether oil data is available")
    gas_available: bool = Field(False, description="Whether gas data is available")
    oil_rows: int = Field(0, description="Number of oil proration records")
    gas_rows: int = Field(0, description="Number of gas proration records")
    oil_modified: Optional[str] = Field(None, description="Last modified date for oil data")
    gas_modified: Optional[str] = Field(None, description="Last modified date for gas data")


class RRCDownloadResponse(BaseModel):
    """Response from RRC data download."""

    success: bool = Field(..., description="Whether download was successful")
    message: str = Field(..., description="Status message")
    oil_rows: int = Field(0, description="Number of oil records downloaded")
    gas_rows: int = Field(0, description="Number of gas records downloaded")


class UploadResponse(BaseModel):
    """Response model for CSV upload endpoint."""

    message: str = Field(..., description="Status message")
    result: Optional[ProcessingResult] = Field(
        None, description="Processing result if successful"
    )


class ExportRequest(BaseModel):
    """Request model for export endpoints."""

    rows: list[MineralHolderRow] = Field(
        ..., description="List of mineral holder rows to export"
    )
    filename: Optional[str] = Field(
        "proration_export", description="Base filename for export (without extension)"
    )


class RRCQueryResult(BaseModel):
    """Result of querying RRC website."""

    success: bool = Field(..., description="Whether query was successful")
    unit_acres: Optional[float] = Field(None, description="Unit Acres from RRC")
    field_name: Optional[str] = Field(None, description="Field Name from RRC")
    allowable: Optional[str] = Field(None, description="Allowable (BBL/Gas) from RRC")
    error_message: Optional[str] = Field(None, description="Error message if query failed")
    raw_html: Optional[str] = Field(None, description="Raw HTML response for debugging")
