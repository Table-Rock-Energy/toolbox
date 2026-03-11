# Pdfplumber Workflows Reference

## Contents
- Primary/Fallback Extraction Pipeline
- Exhibit A Table Parsing Workflow
- Debugging Failed Extractions
- Adding pdfplumber to a New Tool
- Performance Optimization

---

## Primary/Fallback Extraction Pipeline

PyMuPDF runs first in both Extract and Revenue tools. pdfplumber activates on failure or garbled output. The two tools differ in their fallback strategy:

| Tool | Trigger | pdfplumber Mode |
|------|---------|-----------------|
| Extract | PyMuPDF returns `< 100 chars` | `extract_text(layout=True)` |
| Revenue | PyMuPDF garbled score `≥ 3` | `extract_text()` default |

### Revenue Tool Fallback (Garbled Text Comparison)

```python
# backend/app/services/revenue/pdf_extractor.py
import io
import fitz  # PyMuPDF
import pdfplumber

def extract_text(pdf_bytes: bytes, use_fallback: bool = True) -> str:
    """PyMuPDF first; pdfplumber if garbled."""
    pymupdf_text = None
    pdfplumber_text = None

    try:
        pymupdf_text = extract_text_pymupdf(pdf_bytes)
    except Exception:
        pass

    if pymupdf_text and len(pymupdf_text.strip()) > 100:
        garbled = detect_garbled_text(pymupdf_text)
        if not garbled["garbled"]:
            return pymupdf_text

    if use_fallback:
        try:
            pdfplumber_text = extract_text_pdfplumber(pdf_bytes)
        except Exception:
            pass

    if pymupdf_text and pdfplumber_text:
        pymupdf_score = detect_garbled_text(pymupdf_text)["score"]
        plumber_score = detect_garbled_text(pdfplumber_text)["score"]
        return pdfplumber_text if plumber_score < pymupdf_score else pymupdf_text

    return pymupdf_text or pdfplumber_text or ""
```

### Extract Tool Fallback (Length Check)

```python
# backend/app/services/extract/pdf_extractor.py
def extract_text_from_pdf(file_bytes: bytes, num_columns: int | None = None) -> str:
    if num_columns is None:
        num_columns = detect_column_count(file_bytes)

    text = _extract_with_pymupdf(file_bytes, num_columns=num_columns)

    if not text or len(text.strip()) < 100:
        logger.info("PyMuPDF returned minimal text, falling back to pdfplumber")
        text = _extract_with_pdfplumber(file_bytes)

    return clean_text(text)

def _extract_with_pdfplumber(file_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n\n".join(
                page.extract_text(layout=True) or ""
                for page in pdf.pages
            )
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        return ""
```

### Checklist: Adding PDF Extraction to New Tool

Copy this checklist when implementing PDF processing:

- [ ] Import `io`, `fitz`, and `pdfplumber`
- [ ] Wrap upload bytes in `io.BytesIO()` before opening with pdfplumber
- [ ] Try PyMuPDF first (faster, better for most PDFs)
- [ ] Validate extraction quality (`len(text.strip()) > 100`)
- [ ] Fallback to pdfplumber if PyMuPDF insufficient
- [ ] Guard `page.extract_text()` result with `or ""`
- [ ] Log which method succeeded for debugging
- [ ] Raise descriptive `RuntimeError` if both fail (mention OCR for scanned PDFs)
- [ ] Always use `with pdfplumber.open()` context manager (prevents file handle leaks)

---

## Exhibit A Table Parsing Workflow

OCC Exhibit A PDFs in Devon-style and Mewbourne-style formats have explicit tables. The `table_parser.py` uses pdfplumber directly for these.

### Full Table Parse Flow

```python
# backend/app/services/extract/table_parser.py
import io
import logging
import pdfplumber

from app.models.extract import PartyEntry
from app.services.extract.format_detector import ExhibitFormat

logger = logging.getLogger(__name__)

_HEADER_KEYWORDS = {
    "name", "attention", "attn", "address", "city", "state", "zip",
    "no", "no.", "number", "#", "mailing", "respondent",
}

def parse_table_pdf(file_bytes: bytes, fmt: ExhibitFormat) -> list[PartyEntry]:
    entries = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                logger.debug("No tables on page %d", page_num + 1)
                continue

            for table in tables:
                if not table:
                    continue
                for row in table:
                    # Skip empty rows and header rows
                    if not row or not any(cell for cell in row if cell and cell.strip()):
                        continue
                    cells = [c.strip() if c else "" for c in row]
                    first = cells[0].lower() if cells[0] else ""
                    if first in _HEADER_KEYWORDS:
                        continue
                    # parse row into PartyEntry...

    return entries
```

### Checklist: Exhibit A Table Parsing

- [ ] Open from `io.BytesIO(file_bytes)`
- [ ] Log pages with no tables (debug level, not warning)
- [ ] Skip rows where all cells are empty or whitespace
- [ ] Skip header rows by checking against `_HEADER_KEYWORDS`
- [ ] Strip whitespace from all cell values (`cell.strip() if cell else ""`)
- [ ] Handle `None` cells (pdfplumber returns `None` for empty table cells)
- [ ] Log entry count on completion

---

## Debugging Failed Extractions

When `extract_text()` or `extract_tables()` returns empty or garbled output.

### Diagnostic Script

```python
# Run from backend/ directory:
# python3 -c "from app.services.extract.pdf_diagnostics import diagnose_pdf; diagnose_pdf('problem.pdf')"
import io
import pdfplumber

def diagnose_pdf(pdf_path: str):
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        print(f"Pages: {len(pdf.pages)}")
        print(f"Metadata: {pdf.metadata}")

        for i, page in enumerate(pdf.pages[:3]):
            print(f"\n--- Page {i+1} ---")
            print(f"Size: {page.width:.0f} × {page.height:.0f} pt")
            print(f"Chars: {len(page.chars)}")

            text = page.extract_text()
            print(f"Text length: {len(text) if text else 0}")
            if text:
                print(f"Preview: {text[:120]!r}")

            tables = page.extract_tables()
            print(f"Tables: {len(tables)}")
            for j, t in enumerate(tables):
                print(f"  Table {j}: {len(t)} rows × {len(t[0]) if t else 0} cols")
```

### Visual Table Debugging

```python
def debug_table_detection(pdf_bytes: bytes, page_num: int = 0, output: str = "debug.png"):
    """Save image showing pdfplumber's detected table boundaries."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[page_num]
        im = page.to_image(resolution=150)
        im.debug_tablefinder()
        im.save(output)
        print(f"Saved: {output}")
```

### Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `extract_text()` returns `None` | Scanned PDF — no text layer | OCR required (pytesseract + pdf2image) |
| `extract_tables()` returns `[]` | No line borders detected | Try `vertical_strategy="text"` |
| Text order scrambled | Multi-column layout | Use `extract_text(layout=True)` |
| Table has inconsistent column counts | Merged cells | Adjust `intersection_tolerance` or handle in parser |
| Characters missing | Font subset embedding | pdfplumber may handle better than PyMuPDF; compare scores |
| `None` in table cells | Empty table cell | Always guard: `cell or ""` |

### Iterate-Until-Pass: Table Extraction

1. Run default: `tables = page.extract_tables()`
2. Validate: check table count, row count, column consistency
3. If empty → try `vertical_strategy="text"`:
   ```python
   tables = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
   ```
4. If still failing → visualize: `page.to_image().debug_tablefinder().save("debug.png")`
5. If visual shows correct detection but data wrong → adjust `intersection_tolerance`
6. Only proceed when tables pass: count matches expected, all rows have consistent columns

---

## Adding pdfplumber to a New Tool

Use this pattern when building a new tool that processes PDFs:

```python
# backend/app/services/new_tool/pdf_extractor.py
from __future__ import annotations

import io
import logging

import fitz  # PyMuPDF - primary
import pdfplumber  # fallback

logger = logging.getLogger(__name__)


def extract_text(pdf_bytes: bytes) -> str:
    """Extract text with PyMuPDF primary and pdfplumber fallback."""
    # Primary: PyMuPDF (fast)
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n\n".join(page.get_text("text") for page in doc)
        doc.close()
        if text and len(text.strip()) > 100:
            logger.info("Extracted %d chars with PyMuPDF", len(text))
            return text
    except Exception as e:
        logger.warning("PyMuPDF failed: %s", e)

    # Fallback: pdfplumber
    logger.info("Falling back to pdfplumber")
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
        if text and len(text.strip()) > 50:
            return text
    except Exception as e:
        logger.error("pdfplumber failed: %s", e)

    raise RuntimeError(
        "PDF text extraction failed with both PyMuPDF and pdfplumber. "
        "PDF may be scanned — OCR preprocessing required."
    )
```

---

## Performance Optimization

### Choose the Right Mode

```python
# Fast path — single-column, no layout needed (Revenue tool)
text = page.extract_text()                    # ~50ms/page

# Layout path — multi-column, column order matters (Extract tool fallback)
text = page.extract_text(layout=True)         # ~150-250ms/page

# Table path — structured data with borders (Exhibit A tables)
tables = page.extract_tables()                # ~100ms/page, varies by table count
```

### Optimization Checklist

- [ ] Profile baseline timing before optimizing
- [ ] Use `extract_text()` (no layout) for Revenue tool fallback — single-column PDFs
- [ ] Use `extract_text(layout=True)` only in Extract tool fallback — multi-column Exhibit A
- [ ] Check PyMuPDF first — it's 5-10x faster than pdfplumber for plain text
- [ ] Cache extracted text in GCS/Firestore to avoid re-extraction on re-upload
- [ ] Log extraction method and char count for each job (helps diagnose future issues)
- [ ] For 50+ page PDFs, consider processing pages in batches with generators
- [ ] See **fastapi** skill for async handling of concurrent PDF uploads
