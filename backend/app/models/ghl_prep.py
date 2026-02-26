"""Pydantic models for GHL Prep Tool."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TransformResult(BaseModel):
    """Result of transforming a Mineral export CSV for GoHighLevel import."""

    success: bool = Field(..., description="Whether the transformation succeeded")
    rows: list[dict] = Field(..., description="Transformed rows as dicts with all original columns preserved")
    total_count: int = Field(..., description="Total number of rows processed")
    transformed_fields: dict[str, int] = Field(
        default_factory=dict,
        description="Counts of transformations applied (e.g., {'title_cased': 45, 'campaigns_extracted': 30})"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about missing columns or malformed data"
    )
    source_filename: str = Field(..., description="Original filename")
    job_id: Optional[str] = Field(None, description="Unique job identifier")


class UploadResponse(BaseModel):
    """Response from GHL Prep upload endpoint."""

    message: str = Field(..., description="Human-readable status message")
    result: Optional[TransformResult] = Field(None, description="Transformation result if successful")


class ExportRequest(BaseModel):
    """Request to export transformed GHL Prep data."""

    rows: list[dict] = Field(..., description="Transformed rows to export")
    filename: Optional[str] = Field(None, description="Base filename for export (without extension)")
