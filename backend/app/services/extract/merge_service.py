"""Merge service: combine ECF PDF + Convey 640 CSV parse results.

CSV is the base (structured data from Convey 640). PDF enriches matched
entries with fields the CSV lacks (notes, section_type, entity details).
Metadata merges with PDF winning when both present.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.models.extract import CaseMetadata, PartyEntry
from app.services.extract.convey640_parser import Convey640ParseResult
from app.services.extract.ecf_parser import ECFParseResult

logger = logging.getLogger(__name__)

# Fields where PDF can enrich CSV entries (CSV already has address data)
_PDF_ENRICH_FIELDS = (
    "notes", "section_type", "mailing_address_2",
)


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

    CSV (Convey 640) is the base — it has cleaner structured address data.
    PDF enriches matched entries with notes, section_type, and fills any
    address gaps.  Entries are matched by exact ``entry_number``.

    Unmatched CSV entries are included as-is (unflagged).
    Unmatched PDF entries are appended and flagged for review since they
    were not in the Convey 640 respondent list.
    """
    if csv_result is None:
        return MergeResult(
            entries=list(pdf_result.entries),
            metadata=pdf_result.metadata.model_copy(),
            warnings=[],
        )

    # Build lookups
    pdf_by_entry: dict[str, PartyEntry] = {
        e.entry_number: e for e in pdf_result.entries
    }
    csv_count = len(csv_result.entries)
    matched_count = 0

    final_entries: list[PartyEntry] = []

    # Start with CSV entries as the base
    for csv_entry in csv_result.entries:
        pdf_entry = pdf_by_entry.pop(csv_entry.entry_number, None)
        if pdf_entry is not None:
            matched_count += 1
            final_entries.append(_enrich_from_pdf(csv_entry, pdf_entry))
        else:
            final_entries.append(csv_entry)

    # Append PDF-only entries (not in CSV) — flagged for review
    for pdf_entry in pdf_by_entry.values():
        flagged = pdf_entry.model_copy(
            update={
                "flagged": True,
                "flag_reason": (
                    "Not in Convey 640 respondent list — "
                    "data from PDF only"
                ),
            }
        )
        final_entries.append(flagged)

    warnings: list[str] = []
    pdf_only = len(pdf_by_entry)
    csv_only = csv_count - matched_count
    warnings.append(
        f"{matched_count} matched, {csv_only} CSV-only, {pdf_only} PDF-only"
    )
    logger.info(
        "Merge: %d matched, %d CSV-only, %d PDF-only",
        matched_count, csv_only, pdf_only,
    )

    # Always merge metadata
    merged_meta = _merge_metadata(pdf_result.metadata, csv_result.metadata)

    return MergeResult(
        entries=final_entries,
        metadata=merged_meta,
        warnings=warnings,
    )


def _enrich_from_pdf(csv_entry: PartyEntry, pdf_entry: PartyEntry) -> PartyEntry:
    """Enrich a CSV entry with data from the matched PDF entry.

    CSV is the base (has clean address data). PDF contributes:
    - notes, section_type, mailing_address_2 (fields CSV typically lacks)
    - Any address fields the CSV is missing (fill blanks only)
    - Flagging from PDF if the PDF flagged the entry
    """
    updates: dict[str, object] = {}

    # Pull enrichment fields from PDF when CSV doesn't have them
    for fld in _PDF_ENRICH_FIELDS:
        csv_val = getattr(csv_entry, fld)
        pdf_val = getattr(pdf_entry, fld)
        if not csv_val and pdf_val:
            updates[fld] = pdf_val

    # Fill blank address fields from PDF (CSV usually has these, but just in case)
    for fld in ("mailing_address", "city", "state", "zip_code"):
        csv_val = getattr(csv_entry, fld)
        pdf_val = getattr(pdf_entry, fld)
        if not csv_val and pdf_val:
            updates[fld] = pdf_val

    # Merge notes if both have them
    csv_notes = csv_entry.notes or ""
    pdf_notes = pdf_entry.notes or ""
    if csv_notes and pdf_notes and csv_notes != pdf_notes:
        updates["notes"] = f"{csv_notes}; {pdf_notes}"
    elif pdf_notes and not csv_notes:
        updates["notes"] = pdf_notes

    if updates:
        return csv_entry.model_copy(update=updates)
    return csv_entry


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
