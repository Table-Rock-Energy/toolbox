"""Pydantic models for GoHighLevel API integration."""
from __future__ import annotations

from datetime import datetime
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
