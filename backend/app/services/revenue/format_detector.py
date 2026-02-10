"""Detect PDF statement format based on content patterns."""

from app.models.revenue import StatementFormat


def detect_format(text: str) -> StatementFormat:
    """
    Detect the statement format based on text patterns.

    Detection priority: Enverus → EnergyLink (Hibernia) → Energy Transfer → Unknown.

    Returns:
        StatementFormat.ENVERUS - Web-generated Enverus/EnergyLink tabular format
        StatementFormat.ENERGYLINK - Old Hibernia colon-delimited format
        StatementFormat.ENERGY_TRANSFER - Simple tabular format
        StatementFormat.UNKNOWN - Unable to determine format
    """
    text_lower = text.lower()
    # Use first 3000 chars for detection to avoid false matches in data rows
    text_head = text_lower[:3000]

    # Check for Energy Transfer format first (most distinctive)
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

    # Check for Enverus web-generated format (Magnolia, Oxyrock, Petro-Hunt)
    # The Enverus copyright notice is the most reliable marker. Column headers
    # like "Owner Interest" often span multiple lines in extracted text so we
    # also check for "Check Amount" (Enverus-specific) and "Copyright Notice".
    enverus_markers = [
        "enverus",              # copyright notice: "© 2026 Enverus"
        "copyright notice",     # label before copyright text
        "check amount",         # Enverus-specific header label
        "revenue statement",    # page title in Enverus PDFs
    ]
    enverus_matches = sum(1 for m in enverus_markers if m in text_head)
    # Need "enverus" + at least one other marker to be confident
    if "enverus" in text_head and enverus_matches >= 2:
        return StatementFormat.ENVERUS

    # Check for old EnergyLink/Hibernia format (colon-delimited, token-per-line)
    # Key distinguishers: uses colon-delimited labels ("Check Date:", "Owner Code:"),
    # "Prd." / "Int." column abbreviations, 10-digit property numbers
    energylink_patterns = [
        "owner code:",          # Hibernia-specific (Enverus doesn't use colons)
        "check date:",          # colon variant unique to old format
        "check number:",        # colon variant unique to old format
        "product codes",
        "interest codes",
        "tax codes",
        "deduct codes",
        "hibernia resources",
    ]

    energylink_matches = sum(1 for p in energylink_patterns if p in text_lower)
    if energylink_matches >= 2:
        return StatementFormat.ENERGYLINK

    # Check for specific column headers
    if "sale date" in text_lower and "prd." in text_lower and "int." in text_lower:
        return StatementFormat.ENERGYLINK

    if "sales date" in text_lower and "mm/yy" in text_lower and "product" in text_lower:
        return StatementFormat.ENERGY_TRANSFER

    # Fallback: operators that use Enverus but didn't match column headers
    enverus_operators = ["magnolia oil", "oxyrock operating", "petro-hunt"]
    for op in enverus_operators:
        if op in text_lower:
            return StatementFormat.ENVERUS

    return StatementFormat.UNKNOWN


def get_parser_for_format(format_type: StatementFormat):
    """Get the appropriate parser for a statement format.

    Note: ENVERUS format returns a sentinel string 'enverus' instead of a
    callable, because EnverusParser needs raw pdf_bytes, not extracted text.
    The API layer handles this case specially.
    """
    from app.services.revenue.energylink_parser import parse_energylink_statement
    from app.services.revenue.energytransfer_parser import parse_energy_transfer_statement

    if format_type == StatementFormat.ENVERUS:
        return "enverus"
    elif format_type == StatementFormat.ENERGYLINK:
        return parse_energylink_statement
    elif format_type == StatementFormat.ENERGY_TRANSFER:
        return parse_energy_transfer_statement
    else:
        return None
