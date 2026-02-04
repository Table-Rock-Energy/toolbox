"""Calculation service for mineral holder metrics."""

from __future__ import annotations

from app.models.proration import MineralHolderRow


def calculate_metrics(row: MineralHolderRow) -> None:
    """
    Calculate metrics for a mineral holder row.

    Modifies the row in place with calculated values:
    - Est NRA = Interest * RRC Acres
    - $/NRA = Appraisal Value / Est NRA

    Args:
        row: MineralHolderRow to calculate metrics for
    """
    # Calculate Est NRA
    if row.interest is not None and row.rrc_acres is not None:
        row.est_nra = round(row.interest * row.rrc_acres, 4)
    else:
        row.est_nra = None

    # Calculate $/NRA
    if row.appraisal_value is not None and row.est_nra is not None and row.est_nra > 0:
        row.dollars_per_nra = round(row.appraisal_value / row.est_nra, 2)
    else:
        row.dollars_per_nra = None
