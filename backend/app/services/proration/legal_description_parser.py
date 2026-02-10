"""Parser for legal descriptions to extract Block, Section, and Abstract."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def parse_legal_description(legal_desc: str) -> tuple[str | None, str | None, str | None]:
    """
    Parse legal description to extract Block, Section, and Abstract.

    Args:
        legal_desc: Legal description string

    Returns:
        Tuple of (block, section, abstract) - each can be None if not found
    """
    if not legal_desc:
        return None, None, None

    legal_desc_upper = legal_desc.upper()

    # Extract Block (e.g., "BLK 34", "T4N BLK 34", "BLOCK 34")
    block = None
    block_patterns = [
        r"BLK\s*(\d+)",
        r"BLOCK\s*(\d+)",
        r"T\d+[NS]\s*BLK\s*(\d+)",
    ]
    for pattern in block_patterns:
        match = re.search(pattern, legal_desc_upper)
        if match:
            block = match.group(1)
            break

    # Extract Section (e.g., "SEC 13", "SEC 32,33,40-45", "SECTION 13")
    section = None
    section_patterns = [
        r"SEC\s*([\d,-]+)",
        r"SECTION\s*([\d,-]+)",
    ]
    for pattern in section_patterns:
        match = re.search(pattern, legal_desc_upper)
        if match:
            section = match.group(1)
            break

    # Extract Abstract (e.g., "A 19", "A-942", "ABSTRACT 19")
    abstract = None
    abstract_patterns = [
        r"A\s*-?\s*(\d+)",
        r"ABSTRACT\s*(\d+)",
    ]
    for pattern in abstract_patterns:
        match = re.search(pattern, legal_desc_upper)
        if match:
            abstract = match.group(1)
            break

    return block, section, abstract
