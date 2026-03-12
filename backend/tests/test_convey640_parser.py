"""Tests for Convey 640 CSV/Excel parser.

Covers requirements CSV-01 through CSV-04:
- CSV-01: Schema validation (CSV and Excel, missing columns, empty data)
- CSV-02: Entry number stripping + name normalization pipeline
- CSV-03: ZIP code preservation (float-to-string, leading zeros, NaN)
- CSV-04: Metadata extraction (county, STR, applicant, case_no, curative)
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

from app.models.extract import EntityType
from app.services.extract.convey640_parser import Convey640ParseResult, parse_convey640

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLUMNS = [
    "county", "str", "applicant", "classification", "case_no",
    "curative", "_date", "name", "address", "city", "state", "postal_code",
]


def _make_csv(rows: list[dict], columns: list[str] | None = None) -> bytes:
    """Build CSV bytes from a list of row dicts."""
    cols = columns or COLUMNS
    df = pd.DataFrame(rows, columns=cols)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def _make_xlsx(rows: list[dict], columns: list[str] | None = None) -> bytes:
    """Build Excel bytes from a list of row dicts."""
    cols = columns or COLUMNS
    df = pd.DataFrame(rows, columns=cols)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _default_row(**overrides) -> dict:
    """Return a valid row dict with sensible defaults, applying overrides."""
    row = {
        "county": "CADDO",
        "str": "19-10N-11W",
        "applicant": "COTERRA ENERGY INC",
        "classification": "MULTIUNIT|HORIZONTAL",
        "case_no": "2026000909",
        "curative": "0",
        "_date": "2026-03-05",
        "name": "JOHN DOE",
        "address": "123 MAIN ST",
        "city": "OKLAHOMA CITY",
        "state": "OK",
        "postal_code": "73071",
    }
    row.update(overrides)
    return row


# ===========================================================================
# CSV-01: Schema Validation
# ===========================================================================


class TestSchemaValidation:
    """CSV-01: Parse CSV and Excel with 12-column schema."""

    def test_valid_csv_returns_result(self):
        csv_bytes = _make_csv([_default_row()])
        result = parse_convey640(csv_bytes, "test.csv")
        assert isinstance(result, Convey640ParseResult)
        assert len(result.entries) == 1

    def test_valid_xlsx_returns_result(self):
        xlsx_bytes = _make_xlsx([_default_row()])
        result = parse_convey640(xlsx_bytes, "test.xlsx")
        assert isinstance(result, Convey640ParseResult)
        assert len(result.entries) == 1

    def test_missing_columns_raises_valueerror(self):
        bad_cols = ["county", "name", "address"]
        rows = [{"county": "CADDO", "name": "JOHN DOE", "address": "123 MAIN ST"}]
        csv_bytes = _make_csv(rows, columns=bad_cols)
        with pytest.raises(ValueError, match="Missing expected columns"):
            parse_convey640(csv_bytes, "test.csv")

    def test_empty_csv_raises_valueerror(self):
        # CSV with headers only, no data rows
        header_only = ",".join(COLUMNS) + "\n"
        with pytest.raises(ValueError):
            parse_convey640(header_only.encode(), "test.csv")

    def test_multiple_rows_parsed(self):
        rows = [
            _default_row(name="JOHN DOE"),
            _default_row(name="JANE SMITH"),
            _default_row(name="BOB JONES"),
        ]
        result = parse_convey640(_make_csv(rows), "test.csv")
        assert len(result.entries) == 3


# ===========================================================================
# CSV-02: Entry Number Stripping
# ===========================================================================


class TestEntryNumberStripping:
    """CSV-02: Strip entry line numbers from names."""

    def test_entry_number_stripped(self):
        row = _default_row(name="104 INA NADINE TAYLOR")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.entry_number == "104"
        assert entry.primary_name.startswith("INA NADINE TAYLOR")

    def test_no_entry_number_uses_row_index(self):
        row = _default_row(name="AARON TRACY")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.primary_name == "AARON TRACY"
        # entry_number should be row-index-based (e.g., "1")
        assert entry.entry_number.isdigit()

    def test_digit_starting_name_not_stripped(self):
        """'2WOOD OIL & GAS LLC' -- digit is part of name, not entry number."""
        row = _default_row(name="2WOOD OIL & GAS LLC")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert "2WOOD" in entry.primary_name

    def test_entry_number_with_period(self):
        """'104. INA NADINE TAYLOR' -- period after entry number."""
        row = _default_row(name="104. INA NADINE TAYLOR")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.entry_number == "104"
        assert entry.primary_name.startswith("INA NADINE TAYLOR")


# ===========================================================================
# CSV-02: Name Normalization
# ===========================================================================


class TestNameNormalization:
    """CSV-02: Name normalization pipeline."""

    def test_deceased_sets_estate_type(self):
        row = _default_row(name="JOHN DOE DECEASED")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert "JOHN DOE" in entry.primary_name
        assert "DECEASED" not in entry.primary_name
        assert entry.entity_type == EntityType.ESTATE
        assert entry.notes and "deceased" in entry.notes.lower()

    def test_joint_names_split_for_individuals(self):
        row = _default_row(name="JAMES E DESHIELDS JR & RITA F DESHIELDS")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        # First person is primary
        assert "DESHIELDS" in entry.primary_name
        # Second person in notes
        assert entry.notes and "RITA F DESHIELDS" in entry.notes

    def test_llc_not_split_on_ampersand(self):
        row = _default_row(name="2WOOD OIL & GAS LLC")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.entity_type == EntityType.LLC
        assert "2WOOD OIL & GAS LLC" in entry.primary_name

    def test_trust_extracts_grantor(self):
        row = _default_row(
            name="INA NADINE TAYLOR REVOCABLE TRUST DATED THE 30TH DAY OF JUNE 2015"
        )
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.entity_type == EntityType.TRUST
        assert "INA NADINE TAYLOR" in entry.primary_name
        # Trust details in notes
        assert entry.notes and "trust" in entry.notes.lower()

    def test_trustee_as_grantor(self):
        row = _default_row(
            name="JUDI K SMITH AS TRUSTEE OF THE JUDI K SMITH TRUST"
        )
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.entity_type == EntityType.TRUST
        assert "JUDI K SMITH" in entry.primary_name

    def test_now_married_name(self):
        row = _default_row(name="ALISHA BRUMMETT NOW RECKER")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert "RECKER" in entry.primary_name
        assert entry.notes and "BRUMMETT" in entry.notes

    def test_nee_maiden_name(self):
        row = _default_row(name="ROSE MAURICE PODDER NEE YOUNGHEIM")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert "PODDER" in entry.primary_name
        assert entry.notes and "YOUNGHEIM" in entry.notes

    def test_deceased_clo(self):
        row = _default_row(name="JOHN YOUNGHEIM DECEASED CLO LYNNE YOFFE")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.entity_type == EntityType.ESTATE
        assert entry.notes
        assert "LYNNE YOFFE" in entry.notes

    def test_elo_care_of(self):
        row = _default_row(name="MARY SMITH ELO JANE JONES")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.notes
        assert "JANE JONES" in entry.notes

    def test_standard_co_pattern(self):
        row = _default_row(name="JOHN DOE C/O JANE SMITH")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert "JOHN DOE" in entry.primary_name
        assert entry.notes and "JANE SMITH" in entry.notes

    def test_aka_pattern(self):
        row = _default_row(name="JOHN DOE A/K/A JOHNNY DOE")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert "JOHN DOE" in entry.primary_name
        assert entry.notes and "JOHNNY DOE" in entry.notes

    def test_individual_name_parsed(self):
        """Individuals should get first/middle/last parsed."""
        row = _default_row(name="JAMES EDWARD SMITH")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.first_name == "JAMES"
        assert entry.last_name == "SMITH"

    def test_individual_with_suffix(self):
        row = _default_row(name="JAMES E DESHIELDS JR")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.suffix and "JR" in entry.suffix.upper()


# ===========================================================================
# CSV-03: ZIP Code Preservation
# ===========================================================================


class TestPostalCodeNormalization:
    """CSV-03: ZIP code preservation as strings."""

    def test_normal_zip(self):
        row = _default_row(postal_code="73071.0")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.entries[0].zip_code == "73071"

    def test_leading_zero_preserved(self):
        row = _default_row(postal_code="2668.0")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.entries[0].zip_code == "02668"

    def test_nan_becomes_empty(self):
        row = _default_row(postal_code="nan")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.entries[0].zip_code == ""

    def test_six_digit_truncated_and_flagged(self):
        row = _default_row(postal_code="783160.0")
        result = parse_convey640(_make_csv([row]), "test.csv")
        entry = result.entries[0]
        assert entry.zip_code == "78316"
        assert entry.flagged is True

    def test_plain_zip_string(self):
        row = _default_row(postal_code="73071")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.entries[0].zip_code == "73071"

    def test_empty_string_zip(self):
        row = _default_row(postal_code="")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.entries[0].zip_code == ""


# ===========================================================================
# CSV-04: Metadata Extraction
# ===========================================================================


class TestMetadataExtraction:
    """CSV-04: Metadata from first row."""

    def test_county_extracted(self):
        row = _default_row(county="CADDO")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.metadata.county == "CADDO"

    def test_str_as_legal_description(self):
        row = _default_row(**{"str": "19-10N-11W, 30-10N-11W"})
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.metadata.legal_description == "19-10N-11W, 30-10N-11W"

    def test_applicant_extracted(self):
        row = _default_row(applicant="COTERRA ENERGY INC")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.metadata.applicant == "COTERRA ENERGY INC"

    def test_case_number_normalized(self):
        row = _default_row(case_no="2026000909")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.metadata.case_number == "CD 2026-000909-T"

    def test_case_number_float_format(self):
        """case_no read as float string '2026000909.0'."""
        row = _default_row(case_no="2026000909.0")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.metadata.case_number == "CD 2026-000909-T"


# ===========================================================================
# Curative / Section Type Mapping
# ===========================================================================


class TestSectionTypeMapping:
    """Curative column maps to section_type."""

    def test_curative_zero_is_regular(self):
        row = _default_row(curative="0")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.entries[0].section_type == "regular"

    def test_curative_one_is_curative(self):
        row = _default_row(curative="1")
        result = parse_convey640(_make_csv([row]), "test.csv")
        assert result.entries[0].section_type == "curative"
