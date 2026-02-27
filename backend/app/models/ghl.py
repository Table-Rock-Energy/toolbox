"""Pydantic models for GoHighLevel API integration."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class GHLConnectionCreate(BaseModel):
    """Request model for creating a GHL connection."""
    name: str = Field(..., min_length=1, max_length=100, description="Connection display name")
    token: str = Field(..., min_length=10, description="Private Integration Token")
    location_id: str = Field(..., min_length=1, description="GHL Location ID")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")


class GHLConnectionUpdate(BaseModel):
    """Request model for updating a GHL connection. Token is optional (only set if changing)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    token: Optional[str] = Field(None, min_length=10, description="New token (omit to keep existing)")
    location_id: Optional[str] = Field(None, min_length=1)
    notes: Optional[str] = Field(None, max_length=500)


class GHLConnectionResponse(BaseModel):
    """Response model for GHL connection (never includes encrypted_token)."""
    id: str
    name: str
    token_last4: str = Field(description="Last 4 chars of token for masked display")
    location_id: str
    notes: str = ""
    validation_status: str = Field(description="pending | valid | invalid")
    created_at: datetime
    updated_at: datetime


class ContactUpsertRequest(BaseModel):
    """Request model for upserting a single contact to GHL."""
    connection_id: str = Field(..., description="GHL connection ID to use")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    assigned_to: Optional[str] = Field(None, description="GHL user ID for contact owner")


class ContactUpsertResponse(BaseModel):
    """Response model for contact upsert result."""
    success: bool
    action: str = Field(description="created | updated | failed")
    ghl_contact_id: Optional[str] = None
    error: Optional[str] = None


class GHLUserResponse(BaseModel):
    """GHL user from /users/ endpoint, used for contact owner dropdown."""
    id: str
    name: str
    email: str
    role: Optional[str] = None


class GHLValidationResult(BaseModel):
    """Result of validating a GHL connection."""
    valid: bool
    error: Optional[str] = None
    location_name: Optional[str] = None
    users: list[GHLUserResponse] = Field(default_factory=list)


class BulkContactData(BaseModel):
    """Single contact in a bulk send request. All field names match GHL field names."""
    mineral_contact_system_id: str = Field(..., description="Stable source identifier for result tracking")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    phone2: Optional[str] = None
    phone3: Optional[str] = None
    phone4: Optional[str] = None
    phone5: Optional[str] = None
    address1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None


class BulkSendRequest(BaseModel):
    """Request model for bulk contact send."""
    connection_id: str = Field(..., description="GHL connection ID")
    contacts: list[BulkContactData] = Field(..., min_length=1, description="Contacts to send")
    campaign_tag: str = Field(..., min_length=1, description="Campaign tag to apply to all contacts")
    manual_sms: bool = Field(False, description="Apply 'manual sms' tag to all contacts")
    assigned_to_list: Optional[list[str]] = Field(None, max_length=2, description="1-2 GHL user IDs for contact owner assignment (even split)")
    smart_list_name: Optional[str] = Field(None, description="SmartList/campaign name for reference")


class ContactResult(BaseModel):
    """Per-contact result in bulk send response."""
    mineral_contact_system_id: str
    status: str = Field(description="created | updated | failed | skipped")
    ghl_contact_id: Optional[str] = None
    error: Optional[str] = None


class BulkSendValidationResponse(BaseModel):
    """Response from batch validation (before sending)."""
    valid_count: int
    invalid_count: int
    invalid_contacts: list[ContactResult] = Field(default_factory=list, description="Contacts that failed validation with error details")


class BulkSendResponse(BaseModel):
    """Response from bulk send operation."""
    job_id: str
    total_count: int
    created_count: int
    updated_count: int
    failed_count: int
    skipped_count: int
    results: list[ContactResult]


class ErrorCategory(str, Enum):
    """Error categorization for actionable user feedback."""
    VALIDATION = "validation"
    API_ERROR = "api_error"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    UNKNOWN = "unknown"


class ProgressEvent(BaseModel):
    """SSE progress event data."""
    job_id: str
    processed: int
    total: int
    created: int
    updated: int
    failed: int
    status: str = Field(description="processing | completed | failed | cancelled")


class FailedContactDetail(BaseModel):
    """Failed contact with error category for retry decisions."""
    mineral_contact_system_id: str
    error_category: ErrorCategory
    error_message: str
    contact_data: dict = Field(default_factory=dict, description="Original contact data for retry")


class JobStatusResponse(BaseModel):
    """Full job status for reconnection and summary display."""
    job_id: str
    status: str = Field(description="processing | completed | failed | cancelled")
    total_count: int = 0
    processed_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    failed_contacts: list[FailedContactDetail] = Field(default_factory=list)
    updated_contacts: list[ContactResult] = Field(default_factory=list, description="Updated contacts for spot-checking")
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BulkSendStartResponse(BaseModel):
    """Response from async bulk-send start (returns immediately)."""
    job_id: str
    status: str = "processing"
    total_count: int


class DailyRateLimitInfo(BaseModel):
    """Daily rate limit status for user display."""
    daily_limit: int = Field(200000, description="Max requests per day")
    requests_today: int = Field(0, description="Requests made today")
    remaining: int = Field(200000, description="Remaining requests today")
    resets_at: str = Field(description="ISO timestamp when daily count resets (midnight UTC)")
    warning_level: str = Field("normal", description="normal | warning | critical")
