"""PDF text extraction service using pymupdf, pdfplumber, and OCR."""

import io
import re
from collections import Counter
from typing import Optional

import fitz  # pymupdf
import pdfplumber

# OCR imports - optional, gracefully handle if not available
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


# Characters that indicate garbled font encoding
_GARBLED_CHARS = set("¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿")
# Pattern: doubled single-letter product codes (Oo, oO, Gg, gG)
_DOUBLED_CODE_RE = re.compile(r"\b[OoGg]{2}\b")
# Pattern: numbers missing decimal points (large integers in decimal positions)
_SUSPICIOUSLY_LARGE_INT_RE = re.compile(r"\b\d{7,}\b")


def extract_text_pymupdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF using pymupdf (fitz)."""
    text_parts = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            text_parts.append(text)
        doc.close()
    except Exception as e:
        raise RuntimeError(f"pymupdf extraction failed: {e}")

    return "\n\n".join(text_parts)


def extract_text_pdfplumber(pdf_bytes: bytes) -> str:
    """Extract text from PDF using pdfplumber (fallback)."""
    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                text_parts.append(text)
    except Exception as e:
        raise RuntimeError(f"pdfplumber extraction failed: {e}")

    return "\n\n".join(text_parts)


def extract_text_ocr(pdf_bytes: bytes) -> str:
    """Extract text from PDF using OCR (for scanned/image-based PDFs)."""
    if not OCR_AVAILABLE:
        raise RuntimeError("OCR is not available. Install pytesseract and pdf2image.")

    text_parts = []
    try:
        # Convert PDF to images
        images = convert_from_bytes(pdf_bytes, dpi=300)

        for i, image in enumerate(images):
            # Run OCR on each page
            text = pytesseract.image_to_string(image)
            text_parts.append(text)

    except Exception as e:
        raise RuntimeError(f"OCR extraction failed: {e}")

    return "\n\n".join(text_parts)


def extract_tables_pdfplumber(pdf_bytes: bytes) -> list[list[list[str]]]:
    """Extract tables from PDF using pdfplumber."""
    all_tables = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
    except Exception as e:
        raise RuntimeError(f"pdfplumber table extraction failed: {e}")

    return all_tables


def detect_garbled_text(text: str) -> dict:
    """Detect if extracted text has garbled font encoding.

    Returns a dict with:
      - garbled: bool — True if text appears garbled
      - score: int — number of garbled indicators found
      - indicators: list[str] — descriptions of what was detected
    """
    if not text:
        return {"garbled": False, "score": 0, "indicators": []}

    indicators: list[str] = []
    score = 0

    # Check for unusual characters from font encoding issues
    garbled_chars_found = [ch for ch in text if ch in _GARBLED_CHARS]
    if garbled_chars_found:
        counts = Counter(garbled_chars_found)
        score += len(garbled_chars_found)
        for ch, cnt in counts.most_common(5):
            indicators.append(f"Unusual character U+{ord(ch):04X} '{ch}' appears {cnt}x")

    # Check for doubled product codes (Oo, oO, Gg, gG)
    doubled = _DOUBLED_CODE_RE.findall(text)
    if doubled:
        score += len(doubled) * 2
        indicators.append(f"Doubled letter codes found {len(doubled)}x: {doubled[:5]}")

    # Check for suspiciously large integers where decimals expected
    large_ints = _SUSPICIOUSLY_LARGE_INT_RE.findall(text)
    if large_ints:
        score += len(large_ints)
        indicators.append(
            f"Large integers (possible missing decimals) found {len(large_ints)}x: "
            f"{large_ints[:5]}"
        )

    # Check ratio of non-ASCII to ASCII characters
    if len(text) > 100:
        non_ascii = sum(1 for ch in text if ord(ch) > 127)
        ratio = non_ascii / len(text)
        if ratio > 0.02:  # >2% non-ASCII is suspicious for financial docs
            score += int(ratio * 100)
            indicators.append(
                f"High non-ASCII ratio: {ratio:.1%} ({non_ascii} chars)"
            )

    return {
        "garbled": score >= 3,
        "score": score,
        "indicators": indicators,
    }


def extract_text(pdf_bytes: bytes, use_fallback: bool = True, use_ocr: bool = True) -> str:
    """
    Extract text from PDF, with fallback to pdfplumber and OCR.

    Tries PyMuPDF first. If the text appears garbled (font encoding issues),
    falls back to pdfplumber which sometimes handles custom fonts better.

    Args:
        pdf_bytes: The PDF file as bytes
        use_fallback: Whether to try pdfplumber if pymupdf fails
        use_ocr: Whether to try OCR if text extraction fails

    Returns:
        Extracted text from the PDF
    """
    pymupdf_text = None
    pdfplumber_text = None

    # Try pymupdf first
    try:
        pymupdf_text = extract_text_pymupdf(pdf_bytes)
    except Exception:
        pass

    # If PyMuPDF produced text, check if it's garbled
    if pymupdf_text and len(pymupdf_text.strip()) > 100:
        garbled = detect_garbled_text(pymupdf_text)
        if not garbled["garbled"]:
            return pymupdf_text
        # Text looks garbled — try pdfplumber before returning

    # Try pdfplumber as fallback
    if use_fallback:
        try:
            pdfplumber_text = extract_text_pdfplumber(pdf_bytes)
        except Exception:
            pass

    # Pick the cleaner text
    if pymupdf_text and pdfplumber_text:
        pymupdf_garbled = detect_garbled_text(pymupdf_text)
        plumber_garbled = detect_garbled_text(pdfplumber_text)
        # Prefer whichever is less garbled
        if plumber_garbled["score"] < pymupdf_garbled["score"]:
            return pdfplumber_text
        return pymupdf_text

    if pymupdf_text and len(pymupdf_text.strip()) > 100:
        return pymupdf_text

    if pdfplumber_text and len(pdfplumber_text.strip()) > 100:
        return pdfplumber_text

    # Try OCR as last resort for scanned/image-based PDFs
    if use_ocr and OCR_AVAILABLE:
        try:
            text = extract_text_ocr(pdf_bytes)
            if text and len(text.strip()) > 50:
                return text
        except Exception:
            pass

    # Return whatever we have, even if garbled
    return pymupdf_text or pdfplumber_text or ""


def get_page_count(pdf_bytes: bytes) -> int:
    """Get the number of pages in a PDF."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def extract_text_by_page(pdf_bytes: bytes) -> list[str]:
    """Extract text from each page separately."""
    pages = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            pages.append(text)
        doc.close()
    except Exception:
        # Fallback to pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)

    return pages


def extract_structured_text(pdf_bytes: bytes) -> Optional[dict]:
    """Extract text with position information for better parsing."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result = {"pages": []}

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            blocks = page.get_text("dict")["blocks"]

            page_data = {"page_num": page_num + 1, "lines": []}

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        line_text = ""
                        for span in line["spans"]:
                            line_text += span["text"]
                        if line_text.strip():
                            page_data["lines"].append({
                                "text": line_text,
                                "bbox": line["bbox"],
                                "y": line["bbox"][1]
                            })

            # Sort lines by y position
            page_data["lines"].sort(key=lambda x: x["y"])
            result["pages"].append(page_data)

        doc.close()
        return result
    except Exception:
        return None


def is_ocr_available() -> bool:
    """Check if OCR is available."""
    return OCR_AVAILABLE
