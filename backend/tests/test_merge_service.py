"""Tests for merge_service: ECF PDF + Convey 640 CSV entry merging.

Covers MRG-01 through MRG-04 behaviors and edge cases.
"""

from __future__ import annotations

import csv as csv_mod
import io

from app.models.extract import CaseMetadata, EntityType, PartyEntry
from app.services.extract.ecf_parser import ECFParseResult
from app.services.extract.convey640_parser import Convey640ParseResult
from app.services.extract.merge_service import merge_entries
from app.services.extract.export_service import to_csv, to_excel


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
# MRG-01: CSV is base, PDF enriches
# ---------------------------------------------------------------------------

class TestCsvIsBase:
    """CSV entry data is the base; PDF enriches with notes/section_type."""

    def test_csv_name_used_as_base(self):
        pdf = ECFParseResult(entries=[_entry("1", name="JOHN SMITH")])
        csv = Convey640ParseResult(entries=[_entry("1", name="J0HN SMITH")])
        result = merge_entries(pdf, csv)
        # CSV is base — CSV name is kept
        assert result.entries[0].primary_name == "J0HN SMITH"

    def test_csv_address_used_when_both_present(self):
        pdf = ECFParseResult(entries=[_entry("1", address="123 Main St")])
        csv = Convey640ParseResult(entries=[_entry("1", address="456 Oak Ave")])
        result = merge_entries(pdf, csv)
        # CSV is base — CSV address is kept
        assert result.entries[0].mailing_address == "456 Oak Ave"

    def test_csv_contact_fields_used_as_base(self):
        pdf = ECFParseResult(entries=[
            _entry("1", name="ALICE", address="100 Elm", city="Dallas", state="TX", zip_code="75201"),
        ])
        csv = Convey640ParseResult(entries=[
            _entry("1", name="AL1CE", address="999 Oak", city="Austin", state="OK", zip_code="73301"),
        ])
        result = merge_entries(pdf, csv)
        e = result.entries[0]
        # CSV is base — all CSV fields kept
        assert e.primary_name == "AL1CE"
        assert e.mailing_address == "999 Oak"
        assert e.city == "Austin"
        assert e.state == "OK"
        assert e.zip_code == "73301"


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

    def test_partial_match_pdf_only_flagged(self):
        pdf = ECFParseResult(entries=[_entry("1"), _entry("2"), _entry("3")])
        csv = Convey640ParseResult(entries=[_entry("1"), _entry("3")])
        result = merge_entries(pdf, csv)
        # 2 CSV + 1 PDF-only (flagged)
        assert len(result.entries) == 3
        flagged = [e for e in result.entries if e.flagged]
        assert len(flagged) == 1
        assert flagged[0].entry_number == "2"

    def test_exact_string_match(self):
        pdf = ECFParseResult(entries=[_entry("1"), _entry("2"), _entry("1A")])
        csv = Convey640ParseResult(entries=[_entry("1"), _entry("2"), _entry("1a")])
        result = merge_entries(pdf, csv)
        # "1A" != "1a" so both unmatched entries appear:
        # "1a" CSV entry is unflagged (CSV-only), "1A" PDF entry is flagged
        flagged = [e for e in result.entries if e.flagged]
        assert len(flagged) == 1
        assert flagged[0].entry_number == "1A"


# ---------------------------------------------------------------------------
# MRG-04: Mismatch warnings
# ---------------------------------------------------------------------------

class TestMismatchWarnings:
    """CSV-only entries unflagged; PDF-only flagged; warnings generated."""

    def test_csv_only_entries_not_flagged(self):
        pdf = ECFParseResult(entries=[_entry("1")])
        csv = Convey640ParseResult(entries=[_entry("1"), _entry("99", name="EXTRA")])
        result = merge_entries(pdf, csv)
        extra = [e for e in result.entries if e.entry_number == "99"]
        assert len(extra) == 1
        # CSV-only entries are NOT flagged (CSV is the base)
        assert extra[0].flagged is False

    def test_pdf_only_entries_flagged(self):
        pdf = ECFParseResult(entries=[_entry("1"), _entry("99", name="PDF ONLY")])
        csv = Convey640ParseResult(entries=[_entry("1")])
        result = merge_entries(pdf, csv)
        extra = [e for e in result.entries if e.entry_number == "99"]
        assert len(extra) == 1
        assert extra[0].flagged is True
        assert "Not in Convey 640" in extra[0].flag_reason

    def test_warnings_include_match_summary(self):
        pdf = ECFParseResult(entries=[_entry("1"), _entry("2")])
        csv = Convey640ParseResult(entries=[_entry("1")])
        result = merge_entries(pdf, csv)
        assert any("1 matched" in w for w in result.warnings)

    def test_many_unmatched_still_works(self):
        # 10 PDF entries, CSV has only 4 matching — no fallback mode in new logic
        pdf_entries = [_entry(str(i)) for i in range(1, 11)]
        csv_entries = [_entry(str(i)) for i in range(1, 5)]  # match 1-4 only
        pdf = ECFParseResult(entries=pdf_entries)
        csv = Convey640ParseResult(entries=csv_entries)
        result = merge_entries(pdf, csv)
        # 4 CSV + 6 PDF-only (flagged)
        assert len(result.entries) == 10
        flagged = [e for e in result.entries if e.flagged]
        assert len(flagged) == 6

    def test_metadata_always_merged(self):
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

    def test_empty_pdf_entries_csv_still_returned(self):
        pdf = ECFParseResult(entries=[])
        csv = Convey640ParseResult(entries=[_entry("1")])
        result = merge_entries(pdf, csv)
        # CSV entries included unflagged (CSV is base)
        assert len(result.entries) == 1
        assert not result.entries[0].flagged

    def test_pdf_fills_blank_csv_address(self):
        pdf = ECFParseResult(entries=[_entry("1", address="200 Oak St")])
        csv = Convey640ParseResult(entries=[_entry("1", address=None)])
        result = merge_entries(pdf, csv)
        assert result.entries[0].mailing_address == "200 Oak St"

    def test_csv_address_kept_when_both_present(self):
        pdf = ECFParseResult(entries=[_entry("1", address="PDF Addr")])
        csv = Convey640ParseResult(entries=[
            _entry("1", address="CSV Addr", city="Tulsa", state="OK", zip_code="74101"),
        ])
        result = merge_entries(pdf, csv)
        # CSV is base — CSV address kept
        assert result.entries[0].mailing_address == "CSV Addr"
        assert result.entries[0].city == "Tulsa"
        assert result.entries[0].state == "OK"
        assert result.entries[0].zip_code == "74101"

    def test_notes_merged_when_both_present(self):
        pdf = ECFParseResult(entries=[
            _entry("1", notes="c/o Jane Smith"),
        ])
        csv = Convey640ParseResult(entries=[
            _entry("1", notes="Different note"),
        ])
        result = merge_entries(pdf, csv)
        # Both notes merged
        assert "Different note" in result.entries[0].notes
        assert "c/o Jane Smith" in result.entries[0].notes

    def test_no_mutation_of_input_entries(self):
        pdf_entry = _entry("1", address=None)
        pdf = ECFParseResult(entries=[pdf_entry])
        csv = Convey640ParseResult(entries=[_entry("1", address="200 Oak")])
        merge_entries(pdf, csv)
        # Original PDF entry should be unchanged
        assert pdf_entry.mailing_address is None


# ---------------------------------------------------------------------------
# Export tests: case_metadata -> Notes/Comments
# ---------------------------------------------------------------------------


def _parse_csv_rows(csv_bytes: bytes) -> list[dict[str, str]]:
    """Parse CSV bytes into list of dicts."""
    text = csv_bytes.decode("utf-8-sig")
    reader = csv_mod.DictReader(io.StringIO(text))
    return list(reader)


def _parse_excel_rows(excel_bytes: bytes) -> list[dict[str, str]]:
    """Parse Excel bytes into list of dicts."""
    import pandas as pd

    df = pd.read_excel(io.BytesIO(excel_bytes))
    return df.fillna("").to_dict("records")


class TestMergeExport:
    """Export functions accept case_metadata and produce correct Notes/Comments."""

    def test_csv_with_case_metadata_produces_notes(self):
        entries = [_entry("1", name="JOHN SMITH")]
        meta = CaseMetadata(
            legal_description="S19 T10N R11W",
            applicant="Coterra",
            well_name="Diana Prince 1H",
        )
        result = to_csv(entries, case_metadata=meta)
        rows = _parse_csv_rows(result)
        assert len(rows) == 1
        notes = rows[0]["Notes/Comments"]
        assert "Legal: S19 T10N R11W" in notes
        assert "Applicant: Coterra" in notes
        assert "Well: Diana Prince 1H" in notes

    def test_csv_with_existing_notes_appends_metadata(self):
        entries = [_entry("1", name="JOHN SMITH", notes="c/o Jane Smith")]
        meta = CaseMetadata(
            legal_description="S19 T10N R11W",
            applicant="Coterra",
            well_name="Diana Prince 1H",
        )
        result = to_csv(entries, case_metadata=meta)
        rows = _parse_csv_rows(result)
        notes = rows[0]["Notes/Comments"]
        assert notes.startswith("c/o Jane Smith; ")
        assert "Legal: S19 T10N R11W" in notes

    def test_csv_county_only_metadata_no_metadata_note(self):
        """County goes in County column, not Notes/Comments."""
        entries = [_entry("1", name="JOHN SMITH")]
        meta = CaseMetadata(county="CADDO")
        result = to_csv(entries, county="CADDO", case_metadata=meta)
        rows = _parse_csv_rows(result)
        assert rows[0]["County"] == "CADDO"
        assert rows[0]["Notes/Comments"] == ""

    def test_csv_without_case_metadata_unchanged(self):
        entries = [_entry("1", name="JOHN SMITH", notes="existing note")]
        result = to_csv(entries, case_metadata=None)
        rows = _parse_csv_rows(result)
        assert rows[0]["Notes/Comments"] == "existing note"

    def test_excel_with_case_metadata_same_as_csv(self):
        entries = [_entry("1", name="JOHN SMITH")]
        meta = CaseMetadata(
            legal_description="S19 T10N R11W",
            applicant="Coterra",
            well_name="Diana Prince 1H",
        )
        result = to_excel(entries, case_metadata=meta)
        rows = _parse_excel_rows(result)
        notes = str(rows[0]["Notes/Comments"])
        assert "Legal: S19 T10N R11W" in notes
        assert "Applicant: Coterra" in notes
        assert "Well: Diana Prince 1H" in notes


class TestMetadataNotes:
    """_format_metadata_note helper produces correct pipe-separated strings."""

    def test_all_fields_populated(self):
        from app.services.extract.export_service import _format_metadata_note

        meta = CaseMetadata(
            legal_description="S19 T10N R11W",
            applicant="Coterra",
            well_name="Diana Prince 1H",
            county="CADDO",  # should NOT appear in note
            case_number="CD-2024-001",  # should NOT appear in note
        )
        note = _format_metadata_note(meta)
        assert "Legal: S19 T10N R11W" in note
        assert "Applicant: Coterra" in note
        assert "Well: Diana Prince 1H" in note
        assert "CADDO" not in note
        assert "CD-2024-001" not in note

    def test_partial_fields(self):
        from app.services.extract.export_service import _format_metadata_note

        meta = CaseMetadata(applicant="Coterra")
        note = _format_metadata_note(meta)
        assert note == "Applicant: Coterra"

    def test_no_relevant_fields_returns_empty(self):
        from app.services.extract.export_service import _format_metadata_note

        meta = CaseMetadata(county="CADDO", case_number="CD-2024-001")
        note = _format_metadata_note(meta)
        assert note == ""


class TestExportRequestModel:
    """ExportRequest accepts case_metadata field."""

    def test_export_request_with_case_metadata(self):
        from app.models.extract import ExportRequest

        req = ExportRequest(
            entries=[_entry("1", name="TEST")],
            case_metadata=CaseMetadata(county="CADDO", applicant="Coterra"),
        )
        assert req.case_metadata is not None
        assert req.case_metadata.county == "CADDO"

    def test_export_request_without_case_metadata(self):
        from app.models.extract import ExportRequest

        req = ExportRequest(entries=[_entry("1", name="TEST")])
        assert req.case_metadata is None
