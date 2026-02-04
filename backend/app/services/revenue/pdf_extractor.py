"""PDF text extraction service using pymupdf, pdfplumber, and OCR."""

import io
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


def extract_text(pdf_bytes: bytes, use_fallback: bool = True, use_ocr: bool = True) -> str:
    """
    Extract text from PDF, with fallback to pdfplumber and OCR.

    Args:
        pdf_bytes: The PDF file as bytes
        use_fallback: Whether to try pdfplumber if pymupdf fails
        use_ocr: Whether to try OCR if text extraction fails

    Returns:
        Extracted text from the PDF
    """
    # Try pymupdf first
    try:
        text = extract_text_pymupdf(pdf_bytes)
        if text and len(text.strip()) > 100:
            return text
    except Exception:
        pass

    # Try pdfplumber as fallback
    if use_fallback:
        try:
            text = extract_text_pdfplumber(pdf_bytes)
            if text and len(text.strip()) > 100:
                return text
        except Exception:
            pass

    # Try OCR as last resort for scanned/image-based PDFs
    if use_ocr and OCR_AVAILABLE:
        try:
            text = extract_text_ocr(pdf_bytes)
            if text and len(text.strip()) > 50:
                return text
        except Exception:
            pass

    # Return empty string if all methods fail
    return ""


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
