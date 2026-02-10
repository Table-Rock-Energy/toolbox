"""Pydantic models for Revenue PDF extraction tool."""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StatementFormat(str, Enum):
    """Supported statement formats."""

    ENVERUS = "enverus"
    ENERGYLINK = "energylink"
    ENERGY_TRANSFER = "energy_transfer"
    UNKNOWN = "unknown"


class RevenueRow(BaseModel):
    """Single line item from a revenue statement."""

    property_name: Optional[str] = None
    property_number: Optional[str] = None
    sales_date: Optional[date] = None
    product_code: Optional[str] = None
    product_description: Optional[str] = None
    decimal_interest: Optional[float] = None
    interest_type: Optional[str] = None
    avg_price: Optional[float] = None
    property_gross_volume: Optional[float] = None
    property_gross_revenue: Optional[float] = None
    owner_volume: Optional[float] = None
    owner_value: Optional[float] = None
    owner_tax_amount: Optional[float] = None
    tax_type: Optional[str] = None
    owner_deduct_amount: Optional[float] = None
    deduct_code: Optional[str] = None
    owner_net_revenue: Optional[float] = None


class RevenueStatement(BaseModel):
    """Full revenue statement with header info and line items."""

    filename: str
    format: StatementFormat
    payor: Optional[str] = None
    check_number: Optional[str] = None
    check_amount: Optional[float] = None
    check_date: Optional[date] = None
    operator_name: Optional[str] = None
    owner_number: Optional[str] = None
    owner_name: Optional[str] = None
    rows: list[RevenueRow] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class M1UploadRow(BaseModel):
    """M1 Upload CSV format row (29 columns)."""

    uid: str = ""
    payor: str = ""
    check_number: str = ""
    check_amount: str = ""
    check_date: str = ""
    m1_property_id: str = ""
    payor_prop_number: str = ""
    operator_prop_number: str = ""
    accounting_ref_id: str = ""
    property_name: str = ""
    operator_name: str = ""
    owner_number: str = ""
    owner_name: str = ""
    sales_date: str = ""
    product_code: str = ""
    property_description: str = ""
    decimal_interest: str = ""
    interest_type: str = ""
    avg_price: str = ""
    property_gross_volume: str = ""
    property_gross_revenue: str = ""
    owner_volume: str = ""
    owner_value: str = ""
    owner_tax_amount: str = ""
    tax_type: str = ""
    owner_deduct_amount: str = ""
    deduct_code: str = ""
    owner_net_revenue: str = ""
    line_number: str = ""


M1_COLUMNS = [
    "UID",
    "Payor",
    "Check Number",
    "Check Amount",
    "Check Date",
    "M1 Property ID",
    "Payor Prop #",
    "Operator Prop #",
    "Accounting Ref ID",
    "Property Name",
    "Operator Name",
    "Owner Number",
    "Owner Name",
    "Sales Date",
    "Product Code",
    "Property Description",
    "Decimal Interest",
    "Interest Type",
    "Avg Price",
    "Property Gross Volume",
    "Property Gross Revenue",
    "Owner Volume",
    "Owner Value",
    "Owner Tax Amount",
    "Tax Type",
    "Owner Deduct Amount",
    "Deduct Code",
    "Owner Net Revenue",
    "Line Number",
]


class UploadResponse(BaseModel):
    """API response for upload endpoint."""

    success: bool
    statements: list[RevenueStatement] = Field(default_factory=list)
    total_rows: int = 0
    errors: list[str] = Field(default_factory=list)
    job_id: Optional[str] = Field(None, description="Firestore job ID")


class ExportRequest(BaseModel):
    """Request for export endpoint."""

    statements: list[RevenueStatement]


class ExportResponse(BaseModel):
    """Response for export endpoint."""

    success: bool
    filename: str = ""
    content: str = ""
    row_count: int = 0
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    service: str = "revenue-tool"
