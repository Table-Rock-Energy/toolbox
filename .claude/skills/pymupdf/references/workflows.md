# PyMuPDF Workflows Reference

## Contents
- Extract Tool: OCC Exhibit A Upload Flow
- Revenue Tool: Multi-PDF Batch Flow
- Fallback Chain with Garbled Detection
- Debugging Failed Extractions
- Testing PDF Extraction

---

## Extract Tool: OCC Exhibit A Upload Flow

**Path:** `backend/app/services/extract/pdf_extractor.py`

```
POST /api/extract/upload
  → Read UploadFile bytes
  → detect_column_count(pdf_bytes)      # Analyze first page: 2 or 3 columns?
  → _extract_with_pymupdf(pdf_bytes)    # dict mode + column sorting
  → if len < 100: _extract_with_pdfplumber(pdf_bytes)
  → clean_text(text)                    # app.utils.patterns.clean_text
  → extract_party_list(text)            # Find Exhibit A section or fallback to full doc
  → parse_parties(exhibit_text)         # Return PartyEntry[]
```

### Column-Aware Extraction Implementation

```python
# backend/app/services/extract/pdf_extractor.py

def extract_text_from_pdf(file_bytes: bytes, num_columns: int | None = None) -> str:
    if num_columns is None:
        num_columns = detect_column_count(file_bytes)  # Returns 2 or 3

    text = _extract_with_pymupdf(file_bytes, num_columns=num_columns)

    if not text or len(text.strip()) < 100:
        logger.info("PyMuPDF returned minimal text, falling back to pdfplumber")
        text = _extract_with_pdfplumber(file_bytes)

    return clean_text(text)


def _extract_with_pymupdf(file_bytes: bytes, num_columns: int = 3) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    all_text = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        text_blocks = [b for b in blocks if b.get("type") == 0]
        sorted_blocks = _sort_blocks_by_columns(text_blocks, page.rect.width, num_columns)
        page_text = []
        for block in sorted_blocks:
            lines = []
            for line in block.get("lines", []):
                lines.append("".join(s.get("text", "") for s in line.get("spans", [])))
            page_text.append("\n".join(lines))
        all_text.append("\n".join(page_text))
    doc.close()
    return "\n\n".join(all_text)
```

### Exhibit A Section Isolation

After extraction, `extract_party_list()` finds the Exhibit A section using regex:

```python
EXHIBIT_A_START_PATTERN = re.compile(
    r"(?:^|\n)\s*Exhibit\s*[\"']?A[\"']?\s*\n\s*(?=\d+\.\s)",
    re.IGNORECASE | re.MULTILINE,
)
EXHIBIT_END_PATTERN = re.compile(r"Exhibit\s*[\"']?[B-Z][\"']?", re.IGNORECASE)
```

If Exhibit A marker not found, `extract_party_list()` scans for "PARTIES", "RESPONDENTS", "NOTICE LIST" headings before falling back to full document text.

### Workflow Checklist

```
- [ ] Read UploadFile bytes immediately: pdf_bytes = await file.read()
- [ ] Detect column count (auto by default)
- [ ] Extract with PyMuPDF dict mode + column sort
- [ ] Check len(text.strip()) >= 100 before skipping fallback
- [ ] Apply clean_text() from app.utils.patterns
- [ ] Isolate Exhibit A section before parsing
- [ ] Return PartyEntry[] with entity type detection
```

---

## Revenue Tool: Multi-PDF Batch Flow

**Path:** `backend/app/services/revenue/pdf_extractor.py`

```
POST /api/revenue/upload (multiple files)
  → For each file:
      → Read bytes
      → extract_text(pdf_bytes)          # PyMuPDF + pdfplumber + OCR with garbled scoring
      → format_detector.detect(text)     # EnergyLink / Enverus / EnergyTransfer?
      → parser.parse(text OR spans)      # Parser-specific: text or span-based
  → Aggregate RevenueStatement[]
  → m1_transformer.transform()           # → M1 CSV rows
```

### Batch Per-File Independence

```python
# backend/app/api/revenue.py pattern
results = []
for file in files:
    pdf_bytes = await file.read()
    try:
        text = extract_text(pdf_bytes)          # Auto-fallback with garbled scoring
        statement = parse_revenue_statement(text)
        results.append({"file": file.filename, "status": "success", "data": statement})
    except Exception as e:
        logger.error(f"Failed {file.filename}: {e}")
        results.append({"file": file.filename, "status": "error", "error": str(e)})
# One bad PDF does NOT abort the batch
```

### Enverus: Span-Based Parsing

Enverus revenue PDFs use multi-column layouts that text-mode breaks. Use `extract_spans_by_page()` to get positioned spans, then reconstruct columns by x-coordinate.

```python
# backend/app/services/revenue/enverus_parser.py pattern
from app.services.revenue.pdf_extractor import extract_spans_by_page

spans_by_page = extract_spans_by_page(pdf_bytes)
# Group spans by page, then by x-band to identify column membership
for page_num, spans in spans_by_page.items():
    left_col = [s for s in spans if s.x0 < page_width * 0.5]
    right_col = [s for s in spans if s.x0 >= page_width * 0.5]
```

### Batch Workflow Checklist

```
- [ ] Read each UploadFile bytes independently (don't share state)
- [ ] Call extract_text(pdf_bytes) — handles PyMuPDF → pdfplumber → OCR automatically
- [ ] Detect format BEFORE choosing parser (EnergyLink vs Enverus vs EnergyTransfer)
- [ ] For Enverus: use extract_spans_by_page() not extract_text()
- [ ] Wrap each file in try/except — partial batch success is acceptable
- [ ] Return per-file status in response body
- [ ] Log which extractor won (garbled score comparison)
```

---

## Fallback Chain with Garbled Detection

The Revenue tool's `extract_text()` is the most sophisticated version:

```python
# backend/app/services/revenue/pdf_extractor.py
def extract_text(pdf_bytes: bytes, use_fallback=True, use_ocr=True) -> str:
    pymupdf_text = None
    pdfplumber_text = None

    try:
        pymupdf_text = extract_text_pymupdf(pdf_bytes)
    except Exception:
        pass

    # Short-circuit if PyMuPDF is clean and substantial
    if pymupdf_text and len(pymupdf_text.strip()) > 100:
        if not detect_garbled_text(pymupdf_text)["garbled"]:
            return pymupdf_text

    # Always try pdfplumber when PyMuPDF is garbled
    if use_fallback:
        try:
            pdfplumber_text = extract_text_pdfplumber(pdf_bytes)
        except Exception:
            pass

    # Pick winner by garbled score (lower = better)
    if pymupdf_text and pdfplumber_text:
        if detect_garbled_text(pdfplumber_text)["score"] < detect_garbled_text(pymupdf_text)["score"]:
            return pdfplumber_text
        return pymupdf_text

    # Fallback to whatever we have
    if pymupdf_text and len(pymupdf_text.strip()) > 100:
        return pymupdf_text
    if pdfplumber_text and len(pdfplumber_text.strip()) > 100:
        return pdfplumber_text

    # Last resort: OCR
    if use_ocr and OCR_AVAILABLE:
        text = extract_text_ocr(pdf_bytes)
        if text and len(text.strip()) > 50:
            return text

    return pymupdf_text or pdfplumber_text or ""
```

The Extract tool uses a simpler threshold: if `len(text.strip()) < 100`, fall back. **Do not apply the garbled detection from Revenue to Extract** — they use different approaches intentionally.

---

## Debugging Failed Extractions

### Step 1: Check Which Extractor Was Used

```python
# Temporary debug script — run in Python REPL
import fitz
import pdfplumber
import io

with open("problematic.pdf", "rb") as f:
    pdf_bytes = f.read()

# Check PyMuPDF
doc = fitz.open(stream=pdf_bytes, filetype="pdf")
print(f"Pages: {len(doc)}")
for i in range(len(doc)):
    page = doc.load_page(i)
    text = page.get_text("text")
    print(f"Page {i}: {len(text)} chars | First 100: {repr(text[:100])}")
doc.close()
```

### Step 2: Check for Scanned PDF (Image-Based)

```python
doc = fitz.open(stream=pdf_bytes, filetype="pdf")
page = doc.load_page(0)
images = page.get_images()
text = page.get_text("text")
print(f"Images: {len(images)}, Text chars: {len(text)}")
# Many images + no text → scanned PDF → needs OCR
doc.close()
```

### Step 3: Compare Extractors

```python
# Run garbled detection on both
from app.services.revenue.pdf_extractor import (
    extract_text_pymupdf, extract_text_pdfplumber, detect_garbled_text
)
mupdf = extract_text_pymupdf(pdf_bytes)
plumber = extract_text_pdfplumber(pdf_bytes)
print("PyMuPDF garbled:", detect_garbled_text(mupdf))
print("pdfplumber garbled:", detect_garbled_text(plumber))
```

### Step 4: Check Column Detection (Extract Tool)

```python
from app.services.extract.pdf_extractor import detect_column_count
cols = detect_column_count(pdf_bytes)
print(f"Detected columns: {cols}")
# If wrong: pass num_columns=2 explicitly to extract_text_from_pdf()
```

### Debug Checklist

```
- [ ] Check page count and per-page text length
- [ ] Check image count per page (many images = scanned)
- [ ] Compare PyMuPDF vs pdfplumber garbled scores
- [ ] For Extract tool: verify column count detection
- [ ] For Enverus PDFs: use extract_spans_by_page() not extract_text()
- [ ] Check log output for "falling back to pdfplumber" messages
- [ ] Test with OCR_AVAILABLE=True if image-based PDF suspected
```

---

## Testing PDF Extraction

```python
# backend/tests/test_pdf_extraction.py
import pytest
from unittest.mock import patch
from app.services.revenue.pdf_extractor import extract_text_pymupdf, detect_garbled_text

def test_extract_text_pymupdf_from_bytes(sample_pdf_bytes):
    """Verify extraction works from bytes (not file path)."""
    text = extract_text_pymupdf(sample_pdf_bytes)
    assert isinstance(text, str)
    assert len(text.strip()) > 0

def test_garbled_detection_flags_bad_text():
    garbled = "¢£¤ Oo Gg 1234567 normal text"
    result = detect_garbled_text(garbled)
    assert result["garbled"] is True
    assert result["score"] >= 3

def test_garbled_detection_passes_clean_text():
    clean = "John Doe, 123 Main St, Anytown TX 75001. Lease #12345. $1,234.56"
    result = detect_garbled_text(clean)
    assert result["garbled"] is False

@pytest.fixture
def sample_pdf_bytes(tmp_path):
    """Create a minimal PDF for testing without a real file."""
    from reportlab.pdfgen import canvas
    import io
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, "Test extraction content")
    c.save()
    return buffer.getvalue()
```

See the **pytest** skill for async test patterns and httpx-based API testing.
