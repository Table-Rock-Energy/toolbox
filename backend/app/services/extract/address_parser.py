"""Address parsing service for extracting structured address components.

Delegates to the shared address parser. This module re-exports the public API
so existing imports across the extract tool continue to work unchanged.
"""

from app.services.shared.address_parser import (
    format_full_address,
    has_apartment,
    is_po_box,
    parse_address,
)

__all__ = [
    "format_full_address",
    "has_apartment",
    "is_po_box",
    "parse_address",
]
