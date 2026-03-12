"""Tests for merge_service: ECF PDF + Convey 640 CSV entry merging.

Covers MRG-01 through MRG-04 behaviors and edge cases.
"""

from __future__ import annotations

import pytest

from app.models.extract import CaseMetadata, EntityType, PartyEntry
from app.services.extract.ecf_parser import ECFParseResult
from app.services.extract.convey640_parser import Convey640ParseResult
from app.services.extract.merge_service import MergeResult, merge_entries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(
    num: str,
    name: str = "TEST NAME",
    entity_type: EntityType = EntityType.INDIVIDUAL,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    notes: str | None = None,
    flagged: bool = False,
    flag_reason: str | None = None,
) -> PartyEntry:
    return PartyEntry(
        entry_number=num,
        primary_name=name,
        entity_type=entity_type,
        mailing_address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        notes=notes,
        flagged=flagged,
        flag_reason=flag_reason,
    )


# ---------------------------------------------------------------------------
# MRG-01: PDF wins contact fields
# ---------------------------------------------------------------------------

class TestPdfWinsContactFields:
    """PDF entry contact fields always take precedence over CSV."""

    def test_pdf_name_wins_over_csv_ocr_error(self):
        pdf = ECFParseResult(entries=[_entry("1", name="JOHN SMITH")])
        csv = Convey640ParseResult(entries=[_entry("1", name="J0HN SMITH")])
        result = merge_entries(pdf, csv)
        assert result.entries[0].primary_name == "JOHN SMITH"

    def test_pdf_address_wins_when_both_present(self):
        pdf = ECFParseResult(entries=[_entry("1", address="123 Main St")])
        csv = Convey640ParseResult(entries=[_entry("1", address="456 Oak Ave")])
        result = merge_entries(pdf, csv)
        assert result.entries[0].mailing_address == "123 Main St"

    def test_all_pdf_contact_fields_populated_ignores_csv(self):
        pdf = ECFParseResult(entries=[
            _entry("1", name="ALICE", address="100 Elm", city="Dallas", state="TX", zip_code="75201"),
        ])
        csv = Convey640ParseResult(entries=[
            _entry("1", name="AL1CE", address="999 Oak", city="Austin", state="OK", zip_code="73301"),
        ])
        result = merge_entries(pdf, csv)
        e = result.entries[0]
        assert e.primary_name == "ALICE"
        assert e.mailing_address == "100 Elm"
        assert e.city == "Dallas"
        assert e.state == "TX"
        assert e.zip_code == "75201"


# ---------------------------------------------------------------------------
# MRG-02: CSV metadata enriches merged result
# ---------------------------------------------------------------------------

class TestCsvMetadataEnriches:
    """CSV metadata fills gaps in PDF metadata."""

    def test_csv_county_fills_pdf_none(self):
        pdf = ECFParseResult(
            entries=[_entry("1")],
            metadata=CaseMetadata(county=None),
        )
        csv = Convey640ParseResult(
            entries=[_entry("1")],
            metadata=CaseMetadata(county="CADDO"),
        )
        result = merge_entries(pdf, csv)
        assert result.metadata.county == "CADDO"

    def test_pdf_county_wins_when_both_present(self):
        pdf = ECFParseResult(
            entries=[_entry("1")],
            metadata=CaseMetadata(county="CADDO"),
        )
        csv = Convey640ParseResult(
            entries=[_entry("1")],
            metadata=CaseMetadata(county="GRADY"),
        )
        result = merge_entries(pdf, csv)
        assert result.metadata.county == "CADDO"

    def test_csv_case_number_and_applicant_fill_gaps(self):
        pdf = ECFParseResult(
            entries=[_entry("1")],
            metadata=CaseMetadata(),
        )
        csv = Convey640ParseResult(
            entries=[_entry("1")],
            metadata=CaseMetadata(case_number="CD-2024-001", applicant="Acme Oil"),
        )
        result = merge_entries(pdf, csv)
        assert result.metadata.case_number == "CD-2024-001"
        assert result.metadata.applicant == "Acme Oil"

    def test_well_name_only_from_pdf(self):
        pdf = ECFParseResult(
            entries=[_entry("1")],
            metadata=CaseMetadata(well_name="Smith 1-19H"),
        )
        csv = Convey640ParseResult(
            entries=[_entry("1")],
            metadata=CaseMetadata(well_name="Wrong Well"),
        )
        result = merge_entries(pdf, csv)
        assert result.metadata.well_name == "Smith 1-19H"


# ---------------------------------------------------------------------------
# MRG-03: Entry-number matching
# ---------------------------------------------------------------------------

class TestEntryNumberMatching:
    """Entries match on exact entry_number string."""

    def test_all_entries_match(self):
        pdf = ECFParseResult(entries=[_entry("1"), _entry("2"), _entry("3")])
        csv = Convey640ParseResult(entries=[_entry("1"), _entry("2"), _entry("3")])
        result = merge_entries(pdf, csv)
        assert len(result.entries) == 3
        assert not any(e.flagged for e in result.entries)

    def test_partial_match_pdf_only_not_flagged(self):
        pdf = ECFParseResult(entries=[_entry("1"), _entry("2"), _entry("3")])
        csv = Convey640ParseResult(entries=[_entry("1"), _entry("3")])
        result = merge_entries(pdf, csv)
        # All 3 PDF entries present, none flagged
        assert len(result.entries) == 3
        assert not any(e.flagged for e in result.entries)

    def test_exact_string_match(self):
        # Need enough matched entries to stay above 50% threshold
        pdf = ECFParseResult(entries=[_entry("1"), _entry("2"), _entry("1A")])
        csv = Convey640ParseResult(entries=[_entry("1"), _entry("2"), _entry("1a")])
        result = merge_entries(pdf, csv)
        # "1A" != "1a" so "1a" CSV entry is unmatched (flagged)
        csv_only = [e for e in result.entries if e.flagged]
        assert len(csv_only) == 1
        assert csv_only[0].entry_number == "1a"


# ---------------------------------------------------------------------------
# MRG-04: Mismatch warnings
# ---------------------------------------------------------------------------

class TestMismatchWarnings:
    """CSV-only entries flagged; warnings generated; >50% fallback."""

    def test_csv_only_entries_flagged(self):
        pdf = ECFParseResult(entries=[_entry("1")])
        csv = Convey640ParseResult(entries=[_entry("1"), _entry("99", name="EXTRA")])
        result = merge_entries(pdf, csv)
        extra = [e for e in result.entries if e.entry_number == "99"]
        assert len(extra) == 1
        assert extra[0].flagged is True
        assert "No PDF match" in extra[0].flag_reason

    def test_warnings_include_match_summary(self):
        pdf = ECFParseResult(entries=[_entry("1"), _entry("2")])
        csv = Convey640ParseResult(entries=[_entry("1")])
        result = merge_entries(pdf, csv)
        assert any("1 of 2" in w for w in result.warnings)

    def test_fallback_when_over_50_percent_unmatched(self):
        # 10 PDF entries, CSV has only 4 matching -> 4/10 = 40% match rate < 50%
        pdf_entries = [_entry(str(i)) for i in range(1, 11)]
        csv_entries = [_entry(str(i)) for i in range(1, 5)]  # match 1-4 only
        pdf = ECFParseResult(entries=pdf_entries)
        csv = Convey640ParseResult(entries=csv_entries)
        result = merge_entries(pdf, csv)
        # In fallback mode: PDF entries returned unchanged, no CSV-only entries added
        assert len(result.entries) == 10
        assert any("falling back" in w.lower() for w in result.warnings)

    def test_fallback_still_merges_metadata(self):
        pdf_entries = [_entry(str(i)) for i in range(1, 11)]
        csv_entries = [_entry(str(i)) for i in range(1, 5)]
        pdf = ECFParseResult(
            entries=pdf_entries,
            metadata=CaseMetadata(county=None),
        )
        csv = Convey640ParseResult(
            entries=csv_entries,
            metadata=CaseMetadata(county="CADDO"),
        )
        result = merge_entries(pdf, csv)
        assert result.metadata.county == "CADDO"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: None CSV, empty PDF, blank-fill, notes preserved."""

    def test_csv_none_returns_pdf_unchanged(self):
        pdf = ECFParseResult(
            entries=[_entry("1", name="BOB")],
            metadata=CaseMetadata(county="CADDO"),
        )
        result = merge_entries(pdf, None)
        assert len(result.entries) == 1
        assert result.entries[0].primary_name == "BOB"
        assert result.metadata.county == "CADDO"
        assert result.warnings == []

    def test_empty_pdf_entries_returns_empty(self):
        pdf = ECFParseResult(entries=[])
        csv = Convey640ParseResult(entries=[_entry("1")])
        result = merge_entries(pdf, csv)
        # CSV-only entries still included (flagged)
        flagged = [e for e in result.entries if e.flagged]
        assert len(flagged) == 1

    def test_csv_fills_blank_pdf_address(self):
        pdf = ECFParseResult(entries=[_entry("1", address=None)])
        csv = Convey640ParseResult(entries=[_entry("1", address="200 Oak St")])
        result = merge_entries(pdf, csv)
        assert result.entries[0].mailing_address == "200 Oak St"

    def test_csv_fills_blank_pdf_city_state_zip(self):
        pdf = ECFParseResult(entries=[_entry("1")])
        csv = Convey640ParseResult(entries=[
            _entry("1", city="Tulsa", state="OK", zip_code="74101"),
        ])
        result = merge_entries(pdf, csv)
        assert result.entries[0].city == "Tulsa"
        assert result.entries[0].state == "OK"
        assert result.entries[0].zip_code == "74101"

    def test_existing_notes_preserved(self):
        pdf = ECFParseResult(entries=[
            _entry("1", notes="c/o Jane Smith"),
        ])
        csv = Convey640ParseResult(entries=[
            _entry("1", notes="Different note"),
        ])
        result = merge_entries(pdf, csv)
        assert result.entries[0].notes == "c/o Jane Smith"

    def test_no_mutation_of_input_entries(self):
        pdf_entry = _entry("1", address=None)
        pdf = ECFParseResult(entries=[pdf_entry])
        csv = Convey640ParseResult(entries=[_entry("1", address="200 Oak")])
        merge_entries(pdf, csv)
        # Original PDF entry should be unchanged
        assert pdf_entry.mailing_address is None
