"""Tests for ECF PDF parser - Task 1: Model and enum additions."""

from app.models.extract import PartyEntry, ExtractionResult
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
