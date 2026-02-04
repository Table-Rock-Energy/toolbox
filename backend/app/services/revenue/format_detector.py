"""Detect PDF statement format based on content patterns."""

from app.models.revenue import StatementFormat


def detect_format(text: str) -> StatementFormat:
    """
    Detect the statement format based on text patterns.

    Returns:
        StatementFormat.ENERGYLINK - Multi-page detailed statements
        StatementFormat.ENERGY_TRANSFER - Simple tabular format
        StatementFormat.UNKNOWN - Unable to determine format
    """
    text_lower = text.lower()

    # Check for Energy Transfer format
    energy_transfer_patterns = [
        "energy transfer crude marketing",
        "energy transfer crude",
        "p.o. box 4933",
        "houston, tx 77210",
        "payment number:",
        "owner no:",
    ]

    for pattern in energy_transfer_patterns:
        if pattern in text_lower:
            return StatementFormat.ENERGY_TRANSFER

    # Check for EnergyLink format
    energylink_patterns = [
        "energylink",
        "www.energylink.com",
        "hibernia resources",
        "magnolia oil",
        "oxyrock operating",
        "petro-hunt",
        "check date:",
        "check number:",
        "owner code:",
        "product codes",
        "interest codes",
        "tax codes",
        "deduct codes",
    ]

    energylink_matches = sum(1 for p in energylink_patterns if p in text_lower)
    if energylink_matches >= 2:
        return StatementFormat.ENERGYLINK

    # Check for specific column headers
    if "sale date" in text_lower and "prd." in text_lower and "int." in text_lower:
        return StatementFormat.ENERGYLINK

    if "sales date" in text_lower and "mm/yy" in text_lower and "product" in text_lower:
        return StatementFormat.ENERGY_TRANSFER

    return StatementFormat.UNKNOWN


def get_parser_for_format(format_type: StatementFormat):
    """Get the appropriate parser for a statement format."""
    from app.services.revenue.energylink_parser import parse_energylink_statement
    from app.services.revenue.energytransfer_parser import parse_energy_transfer_statement

    if format_type == StatementFormat.ENERGYLINK:
        return parse_energylink_statement
    elif format_type == StatementFormat.ENERGY_TRANSFER:
        return parse_energy_transfer_statement
    else:
        return None
