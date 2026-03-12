"""Comprehensive test suite for ECF PDF parser.

Covers ECF-01 through ECF-05 with inline text fixtures.
Test classes organized by requirement and behavior.
"""

from app.models.extract import CaseMetadata, EntityType, PartyEntry, ExtractionResult
from app.services.extract.ecf_parser import (
    ECFParseResult,
    parse_ecf_filing,
    _extract_metadata,
    _classify_ecf_entity,
    _strip_page_headers,
    _split_into_sections,
)
from app.services.extract.format_detector import ExhibitFormat, detect_format


# ---------------------------------------------------------------------------
# Shared inline fixtures
# ---------------------------------------------------------------------------

SAMPLE_ECF_TEXT = """APPLICANT: COTERRA ENERGY OPERATING CO.
CAUSE NO. CD
2026-000909-T
CADDO COUNTY, OKLAHOMA
SECTION(S) 19, 30 AND 31, TOWNSHIP 10 NORTH, RANGE 11 WEST
(the Diana Prince 1H-193031X well)

EXHIBIT "A"

RESPONDENTS

1. John A. Smith
123 Main St
Oklahoma City, OK 73101

2. Jane Marie Doe, deceased
456 Oak Ave
Tulsa, OK 74101

3. ACME ENERGY TRUST, dated January 1, 2020
c/o Oscar McCarter Jr
789 Elm Drive
Houston, TX 77002

4. Alisha Brummett now Recker
321 Pine Road
Anadarko, OK 73005

5. Heirs and Devisees of Robert Lee Wilson
555 Cedar Lane
Fort Worth, TX 76102

6. Billy Joe Thompson, possibly deceased
PO Box 123
Norman, OK 73069

MULTIUNIT HORIZONTAL WELL - CAUSE NO. CD 2026-000909-T
SECTION(S) 19, 30 AND 31-10N-11W, CADDO COUNTY, OKLAHOMA
COTERRA ENERGY OPERATING CO.
EXHIBIT "A"
7

7. Hammer Industries LLC
900 Industrial Blvd
Midwest City, OK 73110

8. Karen Sue Henderson
Ina Nadine Taylor Revocable Trust dated March 15, 2005
Successor Trustee
1234 Trust Ave
Edmond, OK 73003

CURATIVE RESPONDENTS:

9. Curative Person One
100 Court St
Lawton, OK 73501

10. Curative Person Two
200 Oak Way
Enid, OK 73701

RESPONDENTS WITH ADDRESS UNKNOWN:

11. Unknown Address Person

CURATIVE RESPONDENTS WITH ADDRESS UNKNOWN:

12. Curative Unknown Alpha
13. Curative Unknown Beta

FOR INFORMATIONAL PURPOSES ONLY:

14. COTERRA ENERGY OPERATING CO.

CASE CD CD2026-000909 ENTRY NO. 2 FILED IN OCC COURT CLERK'S OFFICE ON 03/03/2026 - PAGE 21 OF 21
"""


# ===========================================================================
# ECF-05: Format routing
# ===========================================================================


class TestECFFormatRouting:
    """ECF-05: ExhibitFormat.ECF exists but is not auto-detected."""

    def test_ecf_enum_exists(self):
        """ExhibitFormat.ECF exists with value 'ECF'."""
        assert ExhibitFormat.ECF.value == "ECF"

    def test_detect_format_never_returns_ecf(self):
        """detect_format() never returns ECF for any input."""
        ecf_text = """MULTIUNIT HORIZONTAL WELL
APPLICANT: TEST ENERGY CO.
CAUSE NO. CD 2026-000909-T
CADDO COUNTY, OKLAHOMA
EXHIBIT "A"
1. John Smith
123 Main St
Oklahoma City, OK 73101
"""
        result = detect_format(ecf_text)
        assert result != ExhibitFormat.ECF

    def test_detect_format_returns_valid_format_for_empty(self):
        """detect_format returns a valid format even for empty text."""
        result = detect_format("")
        assert result != ExhibitFormat.ECF


# ===========================================================================
# ECF-03: Metadata extraction
# ===========================================================================


class TestECFMetadata:
    """ECF-03: Case metadata fields are extracted correctly."""

    def test_county_extracted(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        assert result.metadata.county == "CADDO"

    def test_case_number_extracted(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        assert result.metadata.case_number is not None
        assert "2026-000909" in result.metadata.case_number

    def test_applicant_extracted(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        assert result.metadata.applicant == "COTERRA ENERGY OPERATING CO."

    def test_legal_description_extracted(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        assert result.metadata.legal_description is not None
        assert "19" in result.metadata.legal_description
        assert "10 NORTH" in result.metadata.legal_description
        assert "RANGE 11 WEST" in result.metadata.legal_description

    def test_well_name_extracted(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        assert result.metadata.well_name is not None
        assert "Diana Prince 1H-193031X" in result.metadata.well_name

    def test_missing_fields_return_none(self):
        """Handles missing fields gracefully."""
        text = """EXHIBIT "A"

RESPONDENTS

1. John Smith
123 Main St
Oklahoma City, OK 73101
"""
        result = parse_ecf_filing(text)
        # Missing fields should be None, not error
        assert result.metadata.county is None
        assert result.metadata.well_name is None

    def test_case_number_single_line(self):
        """Case number on single line is handled."""
        text = """CAUSE NO. CD 2026-000909-T
CADDO COUNTY, OKLAHOMA

EXHIBIT "A"

RESPONDENTS

1. Test Person
100 Main St
Tulsa, OK 74001
"""
        result = parse_ecf_filing(text)
        assert result.metadata.case_number is not None
        assert "2026-000909" in result.metadata.case_number

    def test_case_number_two_line(self):
        """Case number spanning two lines is handled."""
        text = """CAUSE NO. CD
2026-000909-T
CADDO COUNTY, OKLAHOMA

EXHIBIT "A"

RESPONDENTS

1. Test Person
100 Main St
Tulsa, OK 74001
"""
        result = parse_ecf_filing(text)
        assert result.metadata.case_number is not None
        assert "2026-000909" in result.metadata.case_number

    def test_extract_metadata_internal(self):
        """Direct _extract_metadata function works."""
        metadata = _extract_metadata(SAMPLE_ECF_TEXT)
        assert isinstance(metadata, CaseMetadata)
        assert metadata.county == "CADDO"
        assert metadata.applicant is not None


# ===========================================================================
# ECF-01, ECF-02: Entry parsing
# ===========================================================================


class TestECFParseEntries:
    """ECF-01: Correct entry count and basic parsing."""

    def test_correct_entry_count(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        assert len(result.entries) == 14

    def test_returns_ecf_parse_result(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        assert isinstance(result, ECFParseResult)

    def test_entry_number_is_string(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        for entry in result.entries:
            assert isinstance(entry.entry_number, str)

    def test_primary_name_is_cleaned(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry1 = next(e for e in result.entries if e.entry_number == "1")
        assert entry1.primary_name == "John A. Smith"
        # No entry number in name
        assert not entry1.primary_name.startswith("1.")

    def test_all_entries_are_party_entry(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        assert all(isinstance(e, PartyEntry) for e in result.entries)

    def test_regular_entries_have_addresses(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry1 = next(e for e in result.entries if e.entry_number == "1")
        assert entry1.city is not None
        assert entry1.state is not None
        assert entry1.zip_code is not None

    def test_entry_number_not_match_street_address(self):
        """Street addresses like '12801 N Central' not treated as entries."""
        text = """APPLICANT: TEST CO.
CADDO COUNTY, OKLAHOMA

EXHIBIT "A"

RESPONDENTS

1. John Smith
12801 N Central Expressway
Dallas, TX 75243
"""
        result = parse_ecf_filing(text)
        assert len(result.entries) == 1
        assert result.entries[0].entry_number == "1"


class TestECFMultiLine:
    """ECF-02: Multi-line names and addresses handled correctly."""

    def test_multi_line_trust_name_preserved(self):
        """Multi-line trust names with trustees are preserved as single entry."""
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry8 = next(e for e in result.entries if e.entry_number == "8")
        # Entry 8 has multi-line name: Karen + Trust + Trustee
        assert "Karen Sue Henderson" in entry8.primary_name
        assert entry8.entry_number == "8"

    def test_multi_line_address_parsed(self):
        """Multi-line addresses parsed into correct components."""
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry1 = next(e for e in result.entries if e.entry_number == "1")
        assert entry1.mailing_address is not None
        assert entry1.zip_code == "73101"

    def test_po_box_address(self):
        """PO Box addresses handled correctly."""
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry6 = next(e for e in result.entries if e.entry_number == "6")
        assert entry6.mailing_address is not None
        assert "PO" in entry6.mailing_address or "Box" in entry6.mailing_address


# ===========================================================================
# ECF-04: Entity type classification
# ===========================================================================


class TestECFEntityTypes:
    """ECF-04: Entity type detection for ECF entries."""

    def test_deceased_is_estate(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry2 = next(e for e in result.entries if e.entry_number == "2")
        assert entry2.entity_type == EntityType.ESTATE

    def test_possibly_deceased_is_estate(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry6 = next(e for e in result.entries if e.entry_number == "6")
        assert entry6.entity_type == EntityType.ESTATE

    def test_heirs_devisees_is_estate(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry5 = next(e for e in result.entries if e.entry_number == "5")
        assert entry5.entity_type == EntityType.ESTATE

    def test_trust_detected(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry3 = next(e for e in result.entries if e.entry_number == "3")
        assert entry3.entity_type == EntityType.TRUST

    def test_llc_detected(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry7 = next(e for e in result.entries if e.entry_number == "7")
        assert entry7.entity_type == EntityType.LLC

    def test_plain_individual(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry1 = next(e for e in result.entries if e.entry_number == "1")
        assert entry1.entity_type == EntityType.INDIVIDUAL

    def test_classify_ecf_entity_deceased(self):
        """Direct _classify_ecf_entity with deceased text."""
        entity_type, notes = _classify_ecf_entity("Jane Doe, deceased")
        assert entity_type == EntityType.ESTATE
        assert any("deceased" in n for n in notes)

    def test_classify_ecf_entity_possibly_deceased(self):
        entity_type, notes = _classify_ecf_entity("John Smith, possibly deceased")
        assert entity_type == EntityType.ESTATE
        assert any("possibly deceased" in n for n in notes)

    def test_classify_ecf_entity_heirs(self):
        entity_type, _ = _classify_ecf_entity("Heirs and Devisees of Robert Wilson")
        assert entity_type == EntityType.ESTATE

    def test_classify_ecf_entity_individual(self):
        entity_type, _ = _classify_ecf_entity("John Smith")
        assert entity_type == EntityType.INDIVIDUAL


# ===========================================================================
# Section tagging
# ===========================================================================


class TestECFSections:
    """Verifies section type tagging for all ECF sections."""

    def test_regular_section_tagged(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry1 = next(e for e in result.entries if e.entry_number == "1")
        assert entry1.section_type == "regular"

    def test_curative_section_tagged(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry9 = next(e for e in result.entries if e.entry_number == "9")
        assert entry9.section_type == "curative"

    def test_address_unknown_section_tagged(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry11 = next(e for e in result.entries if e.entry_number == "11")
        assert entry11.section_type == "address_unknown"

    def test_curative_unknown_section_tagged(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry12 = next(e for e in result.entries if e.entry_number == "12")
        assert entry12.section_type == "curative_unknown"

    def test_informational_section_tagged(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry14 = next(e for e in result.entries if e.entry_number == "14")
        assert entry14.section_type == "informational"

    def test_entries_without_addresses_not_filtered(self):
        """Address-unknown entries are NOT filtered from results."""
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        unknown = [
            e for e in result.entries
            if e.section_type in ("address_unknown", "curative_unknown")
        ]
        assert len(unknown) == 3

    def test_split_into_sections_correct_count(self):
        """_split_into_sections produces 5 sections."""
        # Extract exhibit text and clean it the same way parse_ecf_filing does
        import re
        text = SAMPLE_ECF_TEXT
        exhibit_match = re.search(r'EXHIBIT\s+"?A"?', text, re.IGNORECASE)
        if exhibit_match:
            text = text[exhibit_match.end():]
        resp_match = re.search(r"RESPONDENTS\s*\n", text)
        if resp_match:
            text = text[resp_match.end():]
        sections = _split_into_sections(text)
        assert len(sections) == 5
        types = [s[0] for s in sections]
        assert "regular" in types
        assert "curative" in types
        assert "address_unknown" in types
        assert "curative_unknown" in types
        assert "informational" in types


# ===========================================================================
# Page header/footer stripping
# ===========================================================================


class TestECFPageHeaders:
    """Page headers/footers stripped without creating false entries."""

    def test_page_headers_stripped(self):
        """Page headers don't create spurious entries."""
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        # The sample has a page header block inserted between entries 6 and 7.
        # MULTIUNIT HORIZONTAL WELL, EXHIBIT "A", applicant name, page number
        # These should NOT appear as entries.
        entry_numbers = [e.entry_number for e in result.entries]
        assert "MULTIUNIT" not in " ".join(e.primary_name for e in result.entries)

    def test_page_footer_stripped(self):
        """CASE CD footer text doesn't appear in entries."""
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        for entry in result.entries:
            assert "CASE CD" not in entry.primary_name
            assert "PAGE" not in (entry.primary_name or "")

    def test_strip_page_headers_internal(self):
        """Direct _strip_page_headers function removes headers."""
        text_with_headers = """MULTIUNIT HORIZONTAL WELL - CAUSE NO. CD 2026-000909-T
EXHIBIT "A"
7
1. John Smith
123 Main St
CASE CD CD2026-000909 ENTRY NO. 2 FILED IN OCC COURT CLERK'S OFFICE ON 03/03/2026 - PAGE 1 OF 21
"""
        cleaned = _strip_page_headers(text_with_headers)
        assert "MULTIUNIT HORIZONTAL WELL" not in cleaned
        assert "CASE CD CD2026" not in cleaned
        assert "John Smith" in cleaned

    def test_applicant_name_header_stripped(self):
        """Applicant name appearing as standalone header is stripped."""
        metadata = CaseMetadata(applicant="TEST CO.")
        text = """TEST CO.
1. John Smith
123 Main St
Oklahoma City, OK 73101
"""
        cleaned = _strip_page_headers(text, metadata)
        # The applicant name on its own line should be stripped
        assert cleaned.strip().startswith("1. John Smith")


# ===========================================================================
# "now [name]" married name pattern
# ===========================================================================


class TestECFNowPattern:
    """Verifies 'now [married name]' handling."""

    def test_now_uses_married_name_as_primary(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry4 = next(e for e in result.entries if e.entry_number == "4")
        assert "Recker" in entry4.primary_name
        # Maiden name should NOT be primary
        assert "Brummett" not in entry4.primary_name

    def test_now_maiden_name_in_notes(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry4 = next(e for e in result.entries if e.entry_number == "4")
        assert entry4.notes is not None
        assert "Brummett" in entry4.notes
        assert "f/k/a" in entry4.notes

    def test_now_pattern_standalone(self):
        """now pattern works in isolation."""
        text = """EXHIBIT "A"

RESPONDENTS

1. Sarah Johnson now Williams
100 Oak St
Tulsa, OK 74001
"""
        result = parse_ecf_filing(text)
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert "Williams" in entry.primary_name
        assert "Johnson" not in entry.primary_name
        assert entry.notes is not None
        assert "Johnson" in entry.notes


# ===========================================================================
# c/o (care of) handling
# ===========================================================================


class TestECFCareOf:
    """Verifies c/o lines captured in notes."""

    def test_co_captured_in_notes(self):
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry3 = next(e for e in result.entries if e.entry_number == "3")
        assert entry3.notes is not None
        assert "Oscar McCarter Jr" in entry3.notes
        assert "c/o" in entry3.notes

    def test_co_standalone(self):
        """c/o line captured correctly in isolation."""
        text = """EXHIBIT "A"

RESPONDENTS

1. Robert James Wilson
c/o Mary Wilson
500 Main St
Dallas, TX 75201
"""
        result = parse_ecf_filing(text)
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.notes is not None
        assert "Mary Wilson" in entry.notes

    def test_co_does_not_corrupt_address(self):
        """c/o line does not become part of the address."""
        result = parse_ecf_filing(SAMPLE_ECF_TEXT)
        entry3 = next(e for e in result.entries if e.entry_number == "3")
        # Address should be the line after c/o
        if entry3.mailing_address:
            assert "Oscar McCarter" not in entry3.mailing_address


# ===========================================================================
# Model tests (from Task 1, retained)
# ===========================================================================


class TestCaseMetadataModel:
    """CaseMetadata Pydantic model tests."""

    def test_case_metadata_accepts_all_fields(self):
        m = CaseMetadata(
            county="CADDO",
            legal_description="SECTION(S) 19, TOWNSHIP 10 NORTH, RANGE 11 WEST",
            applicant="COTERRA ENERGY OPERATING CO.",
            case_number="CD 2026-000909-T",
            well_name="Diana Prince 1H-193031X",
        )
        assert m.county == "CADDO"
        assert m.legal_description is not None
        assert m.applicant is not None
        assert m.case_number is not None
        assert m.well_name is not None

    def test_case_metadata_all_fields_optional(self):
        m = CaseMetadata()
        assert m.county is None
        assert m.legal_description is None

    def test_extraction_result_has_case_metadata(self):
        m = CaseMetadata(county="CADDO")
        r = ExtractionResult(success=True, case_metadata=m)
        assert r.case_metadata is not None
        assert r.case_metadata.county == "CADDO"

    def test_extraction_result_case_metadata_default_none(self):
        r = ExtractionResult(success=True)
        assert r.case_metadata is None


class TestPartyEntrySectionType:
    """PartyEntry section_type field tests."""

    def test_section_type_accepted(self):
        p = PartyEntry(entry_number="1", primary_name="Test", section_type="regular")
        assert p.section_type == "regular"

    def test_section_type_default_none(self):
        p = PartyEntry(entry_number="1", primary_name="Test")
        assert p.section_type is None
