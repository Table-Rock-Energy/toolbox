"""Column layout detection for Enverus/EnergyLink web-generated PDF statements.

Enverus PDFs have multi-row column headers with group labels ("Property", "Owner")
above individual column headers ("Volume", "Price", "Value"). This module detects
these headers from PyMuPDF text spans and builds a column position map.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.revenue.pdf_extractor import TextSpan

logger = logging.getLogger(__name__)


@dataclass
class EnverusColumnLayout:
    """Detected column layout with column name -> x-position mapping."""

    columns: dict[str, float] = field(default_factory=dict)
    header_y: float = 0.0
    page_width: float = 612.0

    def assign_span_to_column(self, span: TextSpan) -> str | None:
        """Assign a span to the nearest column based on x-position."""
        if not self.columns:
            return None

        span_center = (span.x0 + span.x1) / 2
        best_col = None
        best_dist = float("inf")

        for col_name, col_x in self.columns.items():
            dist = abs(span_center - col_x)
            if dist < best_dist:
                best_dist = dist
                best_col = col_name

        # Max tolerance: 50px from column center
        if best_dist > 50:
            return None

        return best_col


def detect_layout(
    spans: list[TextSpan], page_width: float = 612.0
) -> EnverusColumnLayout | None:
    """Detect column layout from header spans on page 0.

    Strategy:
    1. Find "Property" and "Owner" group headers (y < 350) to determine
       the boundary between property-level and owner-level columns.
    2. Collect all spans in the header band (group_y to group_y + 30).
    3. Map known single-word keywords ("Volume", "Price", "Value", etc.)
       to canonical column names, using the Property/Owner boundary to
       disambiguate duplicates.
    4. Detect multi-word headers by combining vertically adjacent spans
       at the same x-position ("Production" + "Date", "Owner" + "Interest").
    """
    if not spans:
        return None

    # Step 1: Find the group header row containing "Property" and "Owner"
    # These are section labels that appear slightly above the column headers
    property_group_x: float | None = None
    owner_group_x: float | None = None
    group_y: float | None = None

    for span in spans:
        if span.y0 > 350:
            continue
        text = span.text.strip()
        # "Property" or "Property Values" group header — take first match only
        if text in ("Property", "Property Values") and property_group_x is None:
            property_group_x = (span.x0 + span.x1) / 2
            group_y = span.y0
        # "Owner" or "Owner Share" group header — take first match only
        # Require x > 400 to skip "Owner" label in the address header area
        elif text in ("Owner", "Owner Share") and owner_group_x is None:
            if span.x0 > 400:
                owner_group_x = (span.x0 + span.x1) / 2
                if group_y is None:
                    group_y = span.y0

    if group_y is None:
        return None

    # Boundary x: midpoint between Property and Owner group headers
    if property_group_x is not None and owner_group_x is not None:
        boundary_x = (property_group_x + owner_group_x) / 2
    elif property_group_x is not None:
        boundary_x = property_group_x + 100
    else:
        boundary_x = page_width * 0.7

    # Step 2: Collect header spans in the band (group_y to group_y + 30)
    header_band = [
        s for s in spans
        if group_y - 2 <= s.y0 <= group_y + 30
    ]

    if not header_band:
        return None

    # Step 3: Build column map from single-word and multi-word headers
    columns: dict[str, float] = {}

    # First pass: detect "Volume" and "Value" pairs to refine boundary_x.
    # The group headers give an approximate boundary, but the actual gap
    # between Property Volume and Owner Volume is the true boundary.
    volume_xs: list[float] = []
    value_xs: list[float] = []
    for span in header_band:
        text_lower = span.text.lower().strip()
        span_cx = (span.x0 + span.x1) / 2
        if text_lower == "volume":
            volume_xs.append(span_cx)
        elif text_lower == "value":
            value_xs.append(span_cx)

    # If we found 2+ Volume or Value spans, refine boundary to their midpoint
    if len(volume_xs) >= 2:
        volume_xs.sort()
        boundary_x = (volume_xs[0] + volume_xs[-1]) / 2
    elif len(value_xs) >= 2:
        value_xs.sort()
        boundary_x = (value_xs[0] + value_xs[-1]) / 2

    # Process single-word matches
    for span in header_band:
        text_lower = span.text.lower().strip()
        span_cx = (span.x0 + span.x1) / 2

        if text_lower == "sales date":
            columns["sales_date"] = span_cx
        elif text_lower == "price":
            columns["price"] = span_cx
        elif text_lower in ("btu", "btu /"):
            columns["btu"] = span_cx
        elif text_lower == "volume":
            if span_cx < boundary_x:
                columns["volume"] = span_cx
            else:
                columns["owner_volume"] = span_cx
        elif text_lower == "value":
            if span_cx < boundary_x:
                columns["value"] = span_cx
            else:
                columns["owner_value"] = span_cx

    # Step 4: Detect multi-word headers by combining vertically stacked spans
    # at similar x-positions (within 25px)
    # E.g., "Production" (y=291, x=307) + "Date" (y=301, x=329) -> production_date
    # E.g., "Owner" (y=291, x=583) + "Interest" (y=301, x=579) -> owner_interest

    vertical_combos = _find_vertical_combinations(header_band)

    # Collect combo matches grouped by type. Some headers appear in both
    # Property and Owner sections (Taxes and Deductions, Amount after T&D).
    # We pair them by x-position: leftmost → Property, rightmost → Owner.
    td_combos: list[float] = []  # "Taxes and Deductions" x-positions
    after_td_combos: list[float] = []  # "Amount after Taxes and Deductions"

    for combo_text, cx in vertical_combos:
        combo_lower = combo_text.lower()
        if combo_lower in ("production date", "sales date"):
            columns.setdefault("sales_date", cx)
        elif combo_lower == "owner interest":
            columns.setdefault("owner_interest", cx)
        elif combo_lower in ("distribution interest", "dist interest"):
            columns.setdefault("dist_interest", cx)
        elif combo_lower == "interest type":
            columns.setdefault("interest_type", cx)
        elif combo_lower in ("tax or deduct code", "deduct code"):
            columns.setdefault("tax_deduct_code", cx)
        elif combo_lower == "btu / gravity":
            columns.setdefault("btu", cx)
        elif combo_lower == "taxes and deductions":
            td_combos.append(cx)
        elif combo_lower in ("amount after taxes and deductions",
                             "amount after deductions"):
            after_td_combos.append(cx)

    # Deduplicate combo positions
    td_combos_dedup = sorted(set(round(x) for x in td_combos))
    after_td_combos = sorted(set(round(x) for x in after_td_combos))

    # Remove T&D combos that overlap with "Amount after" combos (within 10px).
    # These are spurious matches from intermediate rows of the triple header.
    td_combos = [
        x for x in td_combos_dedup
        if not any(abs(x - ax) < 10 for ax in after_td_combos)
    ]

    if len(td_combos) >= 2:
        columns.setdefault("taxes_deductions", td_combos[0])
        columns.setdefault("owner_taxes_deductions", td_combos[-1])
    elif len(td_combos) == 1:
        if td_combos[0] < boundary_x:
            columns.setdefault("taxes_deductions", td_combos[0])
        else:
            columns.setdefault("owner_taxes_deductions", td_combos[0])

    if len(after_td_combos) >= 2:
        columns.setdefault("net_after_td", after_td_combos[0])
        columns.setdefault("owner_net_value", after_td_combos[-1])
    elif len(after_td_combos) == 1:
        if after_td_combos[0] < boundary_x:
            columns.setdefault("net_after_td", after_td_combos[0])
        else:
            columns.setdefault("owner_net_value", after_td_combos[0])

    # Also check for "Type" on its own (Petro-Hunt uses standalone "Type" for interest_type)
    for span in header_band:
        text_lower = span.text.lower().strip()
        span_cx = (span.x0 + span.x1) / 2
        if text_lower == "type" and "interest_type" not in columns:
            columns["interest_type"] = span_cx

    # The header_y should be the bottom of the header band (where data starts below)
    max_header_y = max(s.y0 for s in header_band)

    if len(columns) < 3:
        logger.debug(f"Only found {len(columns)} columns: {columns}")
        return None

    logger.debug(f"Detected {len(columns)} columns: {list(columns.keys())}")
    return EnverusColumnLayout(
        columns=columns,
        header_y=max_header_y,
        page_width=page_width,
    )


def _find_vertical_combinations(
    header_spans: list[TextSpan],
) -> list[tuple[str, float]]:
    """Find multi-word headers by combining vertically adjacent spans.

    Some column headers span 2-3 rows, e.g.:
      "Production" (y=291) + "Date" (y=301)
      "Owner" (y=291) + "Interest" (y=301)
      "Taxes and" (y=288) + "Deductions" (y=296)
      "Amount after" (y=288) + "Taxes and" (y=296) + "Deductions" (y=304)

    Combines spans that are vertically close (within 15px y) and horizontally
    aligned (within 25px x-center).
    """
    results: list[tuple[str, float]] = []

    # Sort by x then y
    sorted_spans = sorted(header_spans, key=lambda s: ((s.x0 + s.x1) / 2, s.y0))

    # Try pairwise combinations
    for i, s1 in enumerate(sorted_spans):
        for j, s2 in enumerate(sorted_spans):
            if i == j:
                continue
            # s2 must be below s1
            if s2.y0 <= s1.y0:
                continue
            # Vertical proximity (within 15px)
            if s2.y0 - s1.y0 > 15:
                continue
            # Horizontal alignment (x-center within 25px)
            cx1 = (s1.x0 + s1.x1) / 2
            cx2 = (s2.x0 + s2.x1) / 2
            if abs(cx1 - cx2) > 25:
                continue

            combo = f"{s1.text.strip()} {s2.text.strip()}"
            avg_cx = (cx1 + cx2) / 2
            results.append((combo, avg_cx))

            # Try triple combinations (s1 + s2 + s3)
            for k, s3 in enumerate(sorted_spans):
                if k in (i, j):
                    continue
                if s3.y0 <= s2.y0:
                    continue
                if s3.y0 - s2.y0 > 15:
                    continue
                cx3 = (s3.x0 + s3.x1) / 2
                if abs(cx2 - cx3) > 25:
                    continue

                triple = f"{s1.text.strip()} {s2.text.strip()} {s3.text.strip()}"
                avg_cx3 = (cx1 + cx2 + cx3) / 3
                results.append((triple, avg_cx3))

    return results
