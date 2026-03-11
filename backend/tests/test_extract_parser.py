"""Regression tests for Extract tool's Exhibit A parser."""

from app.models.extract import EntityType, PartyEntry
from app.services.extract.parser import parse_exhibit_a

# Representative OCC Exhibit A text fixture (inline, no PDF needed)
EXHIBIT_A_SAMPLE = """1. JOHN SMITH DOE
123 Main Street
Midland, TX 79701

2. ACME ENERGY, LLC
456 Oak Avenue, Suite 200
Dallas, TX 75201

3. THE DOE FAMILY TRUST
c/o Jane Doe, Trustee
789 Elm Drive
Houston, TX 77002

U1. UNKNOWN HEIRS OF JAMES DOE
ADDRESS UNKNOWN"""


class TestParseExhibitAMultiEntry:
    """Tests for parsing multi-entry Exhibit A text."""

    def test_multi_entry_produces_expected_count(self):
        """parse_exhibit_a returns at least 3 PartyEntry results from multi-entry text."""
        results = parse_exhibit_a(EXHIBIT_A_SAMPLE)
        assert len(results) >= 3
        assert all(isinstance(r, PartyEntry) for r in results)

    def test_individual_entry_parsed_correctly(self):
        """Individual entry has correct entry_number, non-empty name, and INDIVIDUAL type."""
        results = parse_exhibit_a(EXHIBIT_A_SAMPLE)
        entry_1 = next((r for r in results if r.entry_number == "1"), None)
        assert entry_1 is not None
        assert len(entry_1.primary_name) > 0
        assert entry_1.entity_type == EntityType.INDIVIDUAL

    def test_llc_entity_detected(self):
        """LLC entity detected with entity_type LLC."""
        results = parse_exhibit_a(EXHIBIT_A_SAMPLE)
        entry_2 = next((r for r in results if r.entry_number == "2"), None)
        assert entry_2 is not None
        assert entry_2.entity_type == EntityType.LLC
        assert "LLC" in entry_2.primary_name

    def test_trust_entity_detected(self):
        """Trust entity detected with entity_type TRUST."""
        results = parse_exhibit_a(EXHIBIT_A_SAMPLE)
        entry_3 = next((r for r in results if r.entry_number == "3"), None)
        assert entry_3 is not None
        assert entry_3.entity_type == EntityType.TRUST
        assert "TRUST" in entry_3.primary_name.upper()

    def test_address_unknown_entry_has_no_address(self):
        """Entry with ADDRESS UNKNOWN has None/empty address fields."""
        results = parse_exhibit_a(EXHIBIT_A_SAMPLE)
        unknown_entry = next((r for r in results if r.entry_number == "U1"), None)
        assert unknown_entry is not None
        assert unknown_entry.mailing_address is None
        assert unknown_entry.city is None
        assert unknown_entry.state is None
        assert unknown_entry.zip_code is None

    def test_empty_string_returns_empty_list(self):
        """Empty string input returns empty list without crashing."""
        results = parse_exhibit_a("")
        assert results == []

    def test_individual_has_address_fields(self):
        """Individual entry has populated address fields."""
        results = parse_exhibit_a(EXHIBIT_A_SAMPLE)
        entry_1 = next((r for r in results if r.entry_number == "1"), None)
        assert entry_1 is not None
        assert entry_1.mailing_address is not None
        assert entry_1.city is not None
        assert entry_1.state is not None
        assert entry_1.zip_code is not None
