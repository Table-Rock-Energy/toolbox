"""Tests for ECF PDF parser."""

from app.models.extract import EntityType, PartyEntry, ExtractionResult
from app.services.extract.format_detector import ExhibitFormat, detect_format


class TestECFFormatRouting:
    """ECF-05: ExhibitFormat.ECF exists but is not auto-detected."""

    def test_ecf_enum_exists(self):
        """ExhibitFormat.ECF exists with value 'ECF'."""
        assert ExhibitFormat.ECF.value == "ECF"

    def test_detect_format_never_returns_ecf(self):
        """detect_format() never returns ECF for any input."""
        # ECF-like text should NOT auto-detect as ECF
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


class TestCaseMetadataModel:
    """ECF-03: CaseMetadata model exists with correct fields."""

    def test_case_metadata_accepts_all_fields(self):
        """CaseMetadata model accepts county, legal_description, applicant, case_number, well_name."""
        from app.models.extract import CaseMetadata
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
        """CaseMetadata fields are all Optional with None defaults."""
        from app.models.extract import CaseMetadata
        m = CaseMetadata()
        assert m.county is None
        assert m.legal_description is None
        assert m.applicant is None
        assert m.case_number is None
        assert m.well_name is None

    def test_extraction_result_has_case_metadata(self):
        """ExtractionResult accepts case_metadata field."""
        from app.models.extract import CaseMetadata
        m = CaseMetadata(county="CADDO")
        r = ExtractionResult(success=True, case_metadata=m)
        assert r.case_metadata is not None
        assert r.case_metadata.county == "CADDO"

    def test_extraction_result_case_metadata_default_none(self):
        """ExtractionResult.case_metadata defaults to None."""
        r = ExtractionResult(success=True)
        assert r.case_metadata is None


class TestPartyEntrySectionType:
    """PartyEntry accepts section_type field."""

    def test_section_type_accepted(self):
        """PartyEntry accepts section_type as Optional[str]."""
        p = PartyEntry(entry_number="1", primary_name="Test", section_type="regular")
        assert p.section_type == "regular"

    def test_section_type_default_none(self):
        """PartyEntry.section_type defaults to None."""
        p = PartyEntry(entry_number="1", primary_name="Test")
        assert p.section_type is None


# ---------------------------------------------------------------------------
# Task 2: ECF parser smoke tests
# ---------------------------------------------------------------------------

SMOKE_ECF_TEXT = """APPLICANT: COTERRA ENERGY OPERATING CO.
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

CURATIVE RESPONDENTS:

7. Curative Person One
100 Court St
Lawton, OK 73501

RESPONDENTS WITH ADDRESS UNKNOWN:

8. Unknown Address Person

CURATIVE RESPONDENTS WITH ADDRESS UNKNOWN:

9. Curative Unknown One
10. Curative Unknown Two

FOR INFORMATIONAL PURPOSES ONLY:

11. COTERRA ENERGY OPERATING CO.
"""


class TestECFParserSmoke:
    """Basic smoke tests for parse_ecf_filing."""

    def test_parse_returns_ecf_parse_result(self):
        from app.services.extract.ecf_parser import parse_ecf_filing, ECFParseResult
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        assert isinstance(result, ECFParseResult)

    def test_correct_entry_count(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        assert len(result.entries) == 11

    def test_metadata_county(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        assert result.metadata.county == "CADDO"

    def test_metadata_case_number(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        assert result.metadata.case_number is not None
        assert "2026-000909" in result.metadata.case_number

    def test_metadata_applicant(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        assert result.metadata.applicant == "COTERRA ENERGY OPERATING CO."

    def test_metadata_legal_description(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        assert result.metadata.legal_description is not None
        assert "19" in result.metadata.legal_description
        assert "10 NORTH" in result.metadata.legal_description

    def test_metadata_well_name(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        assert result.metadata.well_name is not None
        assert "Diana Prince" in result.metadata.well_name

    def test_deceased_is_estate(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry2 = next(e for e in result.entries if e.entry_number == "2")
        assert entry2.entity_type == EntityType.ESTATE

    def test_possibly_deceased_is_estate(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry6 = next(e for e in result.entries if e.entry_number == "6")
        assert entry6.entity_type == EntityType.ESTATE

    def test_heirs_devisees_is_estate(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry5 = next(e for e in result.entries if e.entry_number == "5")
        assert entry5.entity_type == EntityType.ESTATE

    def test_now_pattern_uses_married_name(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry4 = next(e for e in result.entries if e.entry_number == "4")
        assert "Recker" in entry4.primary_name
        assert entry4.notes is not None
        assert "Brummett" in entry4.notes

    def test_co_captured_in_notes(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry3 = next(e for e in result.entries if e.entry_number == "3")
        assert entry3.notes is not None
        assert "Oscar McCarter" in entry3.notes

    def test_regular_section_type(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry1 = next(e for e in result.entries if e.entry_number == "1")
        assert entry1.section_type == "regular"

    def test_curative_section_type(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry7 = next(e for e in result.entries if e.entry_number == "7")
        assert entry7.section_type == "curative"

    def test_address_unknown_section_type(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry8 = next(e for e in result.entries if e.entry_number == "8")
        assert entry8.section_type == "address_unknown"

    def test_curative_unknown_section_type(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry9 = next(e for e in result.entries if e.entry_number == "9")
        assert entry9.section_type == "curative_unknown"

    def test_informational_section_type(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry11 = next(e for e in result.entries if e.entry_number == "11")
        assert entry11.section_type == "informational"

    def test_address_unknown_entries_not_filtered(self):
        """Address-unknown entries are kept in results."""
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        unknown_entries = [e for e in result.entries if e.section_type in ("address_unknown", "curative_unknown")]
        assert len(unknown_entries) == 3

    def test_entry_number_not_match_street_address(self):
        """Entry number pattern should not match street addresses."""
        from app.services.extract.ecf_parser import parse_ecf_filing
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

    def test_trust_detected_correctly(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry3 = next(e for e in result.entries if e.entry_number == "3")
        assert entry3.entity_type == EntityType.TRUST

    def test_individual_detected_correctly(self):
        from app.services.extract.ecf_parser import parse_ecf_filing
        result = parse_ecf_filing(SMOKE_ECF_TEXT)
        entry1 = next(e for e in result.entries if e.entry_number == "1")
        assert entry1.entity_type == EntityType.INDIVIDUAL
