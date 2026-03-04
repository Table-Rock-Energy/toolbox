"""PDF text extraction service using PyMuPDF and pdfplumber."""

from __future__ import annotations

import io
import logging
import re
from typing import Optional

import fitz  # PyMuPDF
import pdfplumber

from app.utils.patterns import clean_text

logger = logging.getLogger(__name__)

# Exhibit A boundary detection patterns
EXHIBIT_A_START_PATTERN = re.compile(
    r"(?:^|\n)\s*Exhibit\s*[\"']?A[\"']?\s*\n\s*(?=\d+\.\s)",
    re.IGNORECASE | re.MULTILINE,
)

EXHIBIT_END_PATTERN = re.compile(
    r"Exhibit\s*[\"']?[B-Z][\"']?",
    re.IGNORECASE,
)


def extract_text_from_pdf(
    file_bytes: bytes, num_columns: int | None = None
) -> str:
    """
    Extract text from a PDF file.

    Uses PyMuPDF as primary extractor, falls back to pdfplumber if needed.
    Handles multi-column layouts by analyzing text block positions.

    Args:
        file_bytes: Raw bytes of the PDF file
        num_columns: Number of columns to assume (auto-detected if None)

    Returns:
        Extracted text from the PDF
    """
    # Auto-detect column count if not specified
    if num_columns is None:
        num_columns = detect_column_count(file_bytes)

    # Try PyMuPDF first
    text = _extract_with_pymupdf(file_bytes, num_columns=num_columns)

    # Fall back to pdfplumber if PyMuPDF returns minimal text
    if not text or len(text.strip()) < 100:
        logger.info("PyMuPDF returned minimal text, falling back to pdfplumber")
        text = _extract_with_pdfplumber(file_bytes)

    return clean_text(text)


def _extract_with_pymupdf(
    file_bytes: bytes, num_columns: int = 3
) -> str:
    """
    Extract text using PyMuPDF with column-aware extraction.

    Args:
        file_bytes: Raw bytes of the PDF file
        num_columns: Number of columns to assume for layout

    Returns:
        Extracted text
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        all_text = []

        for page_num, page in enumerate(doc):
            # Get text blocks with position information
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            # Filter to text blocks only (skip images)
            text_blocks = []
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    text_blocks.append(block)

            # Sort blocks for multi-column reading order
            # Group by approximate row (y-position), then sort by x-position
            sorted_blocks = _sort_blocks_by_columns(
                text_blocks, page.rect.width, num_columns=num_columns
            )

            page_text = []
            for block in sorted_blocks:
                block_text = ""
                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                    block_text += line_text + "\n"
                page_text.append(block_text.strip())

            all_text.append("\n".join(page_text))

        doc.close()
        return "\n\n".join(all_text)

    except Exception as e:
        logger.error(f"PyMuPDF extraction failed: {e}")
        return ""


def _sort_blocks_by_columns(
    blocks: list[dict], page_width: float, num_columns: int = 3
) -> list[dict]:
    """
    Sort text blocks to handle multi-column layouts.

    Reads columns left-to-right, top-to-bottom within each column.

    Args:
        blocks: List of text block dictionaries from PyMuPDF
        page_width: Width of the page
        num_columns: Expected number of columns (default 3 for Exhibit A)

    Returns:
        Sorted list of text blocks
    """
    if not blocks:
        return []

    column_width = page_width / num_columns

    # Assign each block to a column based on its x-position
    def get_column(block: dict) -> int:
        bbox = block.get("bbox", (0, 0, 0, 0))
        x_center = (bbox[0] + bbox[2]) / 2
        return min(int(x_center / column_width), num_columns - 1)

    # Group blocks by column
    columns: dict[int, list[dict]] = {i: [] for i in range(num_columns)}
    for block in blocks:
        col = get_column(block)
        columns[col].append(block)

    # Sort blocks within each column by y-position (top to bottom)
    for col in columns:
        columns[col].sort(key=lambda b: b.get("bbox", (0, 0, 0, 0))[1])

    # Interleave columns row by row for better reading order
    # Group by approximate row across all columns
    result = []
    row_height = 50  # Approximate row height for grouping

    # Get all blocks with their row assignment
    all_blocks_with_rows = []
    for col_idx, col_blocks in columns.items():
        for block in col_blocks:
            y_pos = block.get("bbox", (0, 0, 0, 0))[1]
            row_idx = int(y_pos / row_height)
            all_blocks_with_rows.append((row_idx, col_idx, block))

    # Sort by row first, then by column
    all_blocks_with_rows.sort(key=lambda x: (x[0], x[1]))

    result = [item[2] for item in all_blocks_with_rows]
    return result


def detect_column_count(file_bytes: bytes) -> int:
    """Detect the number of text columns on the first page of a PDF.

    Analyzes the x-positions of text blocks and clusters them to determine
    whether the layout uses 2 or 3 columns. Defaults to 3 if unclear.

    Args:
        file_bytes: Raw PDF bytes.

    Returns:
        2 or 3 (detected column count).
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if len(doc) == 0:
            doc.close()
            return 3

        page = doc[0]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)[
            "blocks"
        ]
        doc.close()

        # Collect x-center positions of text blocks
        x_positions = []
        for block in blocks:
            if block.get("type") == 0:
                bbox = block.get("bbox", (0, 0, 0, 0))
                x_center = (bbox[0] + bbox[2]) / 2
                x_positions.append(x_center)

        if len(x_positions) < 4:
            return 3

        page_width = page.rect.width

        # Simple clustering: count blocks in thirds vs halves
        thirds = [0, 0, 0]
        halves = [0, 0]
        for x in x_positions:
            thirds[min(int(x / (page_width / 3)), 2)] += 1
            halves[min(int(x / (page_width / 2)), 1)] += 1

        # If one of the thirds is nearly empty, likely 2 columns
        third_min = min(thirds)
        if third_min < 2 and min(halves) >= 3:
            logger.info("Detected 2-column layout")
            return 2

        logger.info("Detected 3-column layout (default)")
        return 3

    except Exception as e:
        logger.warning("Column count detection failed: %s", e)
        return 3


def _extract_with_pdfplumber(file_bytes: bytes) -> str:
    """
    Extract text using pdfplumber as fallback.

    Args:
        file_bytes: Raw bytes of the PDF file

    Returns:
        Extracted text
    """
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            all_text = []
            for page in pdf.pages:
                # Use layout mode for better column handling
                text = page.extract_text(layout=True)
                if text:
                    all_text.append(text)
            return "\n\n".join(all_text)

    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        return ""


def extract_exhibit_a(text: str) -> Optional[str]:
    """
    Extract just the Exhibit A section from the full PDF text.

    Args:
        text: Full extracted text from PDF

    Returns:
        Text of Exhibit A section, or None if not found
    """
    # Find Exhibit A start
    start_match = EXHIBIT_A_START_PATTERN.search(text)
    if not start_match:
        logger.warning("Could not find Exhibit A start marker")
        return None

    start_pos = start_match.end()

    # Find Exhibit B or other exhibit marker for end
    end_match = EXHIBIT_END_PATTERN.search(text, start_pos)
    if end_match:
        end_pos = end_match.start()
    else:
        # No ending exhibit found, use rest of document
        end_pos = len(text)

    exhibit_a_text = text[start_pos:end_pos].strip()

    # Clean up common artifacts from multi-column extraction
    # Remove repeated header/footer patterns
    exhibit_a_text = _clean_exhibit_text(exhibit_a_text)

    return exhibit_a_text


def extract_party_list(text: str) -> str:
    """
    Extract text containing party/contact lists from a PDF.

    First tries to find Exhibit A section, then falls back to
    looking for numbered entries anywhere in the document.

    Args:
        text: Full extracted text from PDF

    Returns:
        Text containing party entries (may be full document if no section found)
    """
    # First, try to find Exhibit A section
    exhibit_a = extract_exhibit_a(text)
    if exhibit_a and len(exhibit_a.strip()) > 100:
        logger.info("Found Exhibit A section")
        return exhibit_a

    # Look for other common section headers for party lists
    section_patterns = [
        re.compile(r"(?:PARTIES|RESPONDENTS|NOTICE\s+LIST|MAILING\s+LIST)", re.IGNORECASE),
        re.compile(r"(?:entitled\s+to\s+notice|parties\s+entitled)", re.IGNORECASE),
    ]

    for pattern in section_patterns:
        match = pattern.search(text)
        if match:
            # Start from where we found the section header
            section_text = text[match.start():]
            section_text = _clean_exhibit_text(section_text)
            if len(section_text.strip()) > 100:
                logger.info(f"Found party list section via pattern: {pattern.pattern}")
                return section_text

    # No specific section found - return cleaned full text
    # The parser will find numbered entries wherever they are
    logger.info("No specific section found, using full document text")
    return _clean_exhibit_text(text)


def _clean_exhibit_text(text: str) -> str:
    """
    Clean up Exhibit A text by removing headers, footers, and artifacts.

    Args:
        text: Raw Exhibit A text

    Returns:
        Cleaned text
    """
    lines = text.split("\n")
    cleaned_lines = []

    # Patterns to skip
    skip_patterns = [
        re.compile(r"^Application of .+$", re.IGNORECASE),
        re.compile(r"^Cause CD No\.", re.IGNORECASE),
        re.compile(r"^MUH$", re.IGNORECASE),
        re.compile(r"^Page \d+ of \d+$", re.IGNORECASE),
        re.compile(r"^CASE CD .+$", re.IGNORECASE),
        re.compile(r"^Exhibit [\"']?A[\"']?$", re.IGNORECASE),
        re.compile(r"^ADDRESSES\s*$", re.IGNORECASE),
        re.compile(r"^UNKNOWN\s*$", re.IGNORECASE),
        re.compile(r"^IF ANY NAMED", re.IGNORECASE),
        re.compile(r"^PERSON IS", re.IGNORECASE),
        re.compile(r"^DECEASED,", re.IGNORECASE),
        re.compile(r"^RESPONDENTS\s+WITH\s+ADDRESS\s+UNKNOWN\s*$", re.IGNORECASE),
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip lines matching header/footer patterns
        skip = False
        for pattern in skip_patterns:
            if pattern.match(stripped):
                skip = True
                break

        if not skip:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)
