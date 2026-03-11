"""Regression tests for Revenue tool's EnergyLink parser."""

from datetime import date

from app.models.revenue import RevenueStatement, StatementFormat
from app.services.revenue.energylink_parser import parse_energylink_statement

# Representative EnergyLink revenue statement text fixture (inline, no PDF needed)
ENERGYLINK_SAMPLE = """Check Date: 2/24/2025
Check Number: 005468
Owner Code: TAB001
Owner Name: TABLE ROCK ENERGY, LLC

0012345678
SMITH WELL #1
DAWSON, TX

Dec 2024
101
RI
0.000
1500.000
65.50
98250.00
0.00125000
1.875
122.81"""


class TestParseEnergylinkStatement:
    """Tests for parsing EnergyLink format revenue statements."""

    def test_format_is_energylink(self):
        """parse_energylink_statement returns RevenueStatement with ENERGYLINK format."""
        result = parse_energylink_statement(ENERGYLINK_SAMPLE, "test.pdf")
        assert isinstance(result, RevenueStatement)
        assert result.format == StatementFormat.ENERGYLINK
        assert result.filename == "test.pdf"

    def test_header_fields_extracted(self):
        """Check number, check date, and owner name extracted from header."""
        result = parse_energylink_statement(ENERGYLINK_SAMPLE, "test.pdf")
        assert result.check_number == "005468"
        assert result.check_date == date(2025, 2, 24)
        assert result.owner_name == "TABLE ROCK ENERGY, LLC"
        assert result.owner_number == "TAB001"

    def test_at_least_one_row_parsed(self):
        """At least one RevenueRow parsed with property_number and product_code."""
        result = parse_energylink_statement(ENERGYLINK_SAMPLE, "test.pdf")
        assert len(result.rows) >= 1
        row = result.rows[0]
        assert row.property_number == "0012345678"
        assert row.product_code == "101"

    def test_row_has_interest_type(self):
        """Row has interest_type field populated."""
        result = parse_energylink_statement(ENERGYLINK_SAMPLE, "test.pdf")
        row = result.rows[0]
        assert row.interest_type == "RI"

    def test_row_has_numeric_fields(self):
        """Row has populated numeric fields for price, interest, and owner value."""
        result = parse_energylink_statement(ENERGYLINK_SAMPLE, "test.pdf")
        row = result.rows[0]
        assert row.decimal_interest is not None
        assert row.decimal_interest > 0
        assert row.avg_price is not None
        assert row.avg_price > 0
        assert row.owner_value is not None
        assert row.owner_value > 0

    def test_empty_text_returns_statement_with_no_rows(self):
        """Empty/minimal text returns statement with empty rows and no crash."""
        result = parse_energylink_statement("", "empty.pdf")
        assert isinstance(result, RevenueStatement)
        assert result.rows == []
        assert result.format == StatementFormat.ENERGYLINK
        assert result.filename == "empty.pdf"

    def test_no_errors_on_valid_input(self):
        """Valid input produces no parsing errors."""
        result = parse_energylink_statement(ENERGYLINK_SAMPLE, "test.pdf")
        assert result.errors == []
