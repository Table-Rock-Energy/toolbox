"""Merge service: combine ECF PDF + Convey 640 CSV parse results.

Entry-number matching with PDF as source of truth for contact fields.
CSV metadata fills gaps in PDF metadata (county, STR, case#, applicant).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.models.extract import CaseMetadata, PartyEntry
from app.services.extract.convey640_parser import Convey640ParseResult
from app.services.extract.ecf_parser import ECFParseResult

logger = logging.getLogger(__name__)

# Fields where CSV can fill blanks in PDF entries
_FILL_BLANK_FIELDS = ("mailing_address", "city", "state", "zip_code")

# Minimum match rate before falling back to PDF-only mode
_MIN_MATCH_RATE = 0.5


@dataclass
class MergeResult:
    """Result of merging ECF PDF and Convey 640 CSV parse results."""

    entries: list[PartyEntry] = field(default_factory=list)
    metadata: CaseMetadata = field(default_factory=CaseMetadata)
    warnings: list[str] = field(default_factory=list)


def merge_entries(
    pdf_result: ECFParseResult,
    csv_result: Convey640ParseResult | None,
) -> MergeResult:
    """Merge PDF and optional CSV parse results.

    PDF is the source of truth for contact fields (name, address, etc.).
    CSV metadata fills gaps in PDF metadata.  Entries are matched by
    exact ``entry_number`` string comparison.

    When more than 50% of PDF entries are unmatched the merge falls back
    to PDF-only mode (per-entry merge is skipped) but metadata is still
    merged.
    """
    if csv_result is None:
        return MergeResult(
            entries=list(pdf_result.entries),
            metadata=pdf_result.metadata.model_copy(),
            warnings=[],
        )

    # Build CSV lookup, popping matched entries as we go
    csv_by_entry: dict[str, PartyEntry] = {
        e.entry_number: e for e in csv_result.entries
    }

    merged_entries: list[PartyEntry] = []
    matched_count = 0

    for pdf_entry in pdf_result.entries:
        csv_entry = csv_by_entry.pop(pdf_entry.entry_number, None)
        if csv_entry is not None:
            matched_count += 1
        merged_entries.append(pdf_entry)

    # Compute match rate
    pdf_count = len(pdf_result.entries)
    match_rate = matched_count / pdf_count if pdf_count > 0 else 1.0

    warnings: list[str] = []

    if match_rate < _MIN_MATCH_RATE:
        # Fallback: skip per-entry merge, return PDF entries unchanged
        warnings.append(
            f"{matched_count} of {pdf_count} entries matched -- "
            f"falling back to PDF-only mode (match rate {match_rate:.0%})"
        )
        logger.warning("Merge fallback: only %d/%d matched", matched_count, pdf_count)
        final_entries = list(pdf_result.entries)
    else:
        # Normal merge: fill blanks from CSV for matched entries
        final_entries = []
        # Rebuild csv lookup (we popped from it above)
        csv_by_entry_full: dict[str, PartyEntry] = {
            e.entry_number: e for e in csv_result.entries
        }
        for pdf_entry in pdf_result.entries:
            csv_entry = csv_by_entry_full.get(pdf_entry.entry_number)
            if csv_entry is not None:
                final_entries.append(_fill_blanks(pdf_entry, csv_entry))
            else:
                final_entries.append(pdf_entry)

        # Add CSV-only entries (flagged)
        matched_numbers = {e.entry_number for e in pdf_result.entries}
        for csv_entry in csv_result.entries:
            if csv_entry.entry_number not in matched_numbers:
                flagged = csv_entry.model_copy(
                    update={
                        "flagged": True,
                        "flag_reason": (
                            "No PDF match -- data from Convey 640 only "
                            "(may contain OCR errors)"
                        ),
                    }
                )
                final_entries.append(flagged)

        warnings.append(f"{matched_count} of {pdf_count} entries matched")

    # Always merge metadata (even in fallback mode)
    merged_meta = _merge_metadata(pdf_result.metadata, csv_result.metadata)

    return MergeResult(
        entries=final_entries,
        metadata=merged_meta,
        warnings=warnings,
    )


def _fill_blanks(pdf_entry: PartyEntry, csv_entry: PartyEntry) -> PartyEntry:
    """Fill genuinely blank PDF fields from CSV.  Never overwrites existing values."""
    updates: dict[str, object] = {}
    for fld in _FILL_BLANK_FIELDS:
        pdf_val = getattr(pdf_entry, fld)
        csv_val = getattr(csv_entry, fld)
        if not pdf_val and csv_val:
            updates[fld] = csv_val

    if updates:
        return pdf_entry.model_copy(update=updates)
    return pdf_entry


def _merge_metadata(
    pdf_meta: CaseMetadata,
    csv_meta: CaseMetadata | None,
) -> CaseMetadata:
    """Merge metadata: PDF wins when both present, CSV fills None gaps.

    ``well_name`` always comes from PDF (CSV doesn't have it).
    """
    if csv_meta is None:
        return pdf_meta.model_copy()

    return CaseMetadata(
        county=pdf_meta.county or csv_meta.county,
        legal_description=pdf_meta.legal_description or csv_meta.legal_description,
        applicant=pdf_meta.applicant or csv_meta.applicant,
        case_number=pdf_meta.case_number or csv_meta.case_number,
        well_name=pdf_meta.well_name,  # PDF only
    )
