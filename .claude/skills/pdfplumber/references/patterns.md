# Pdfplumber Patterns Reference

## Contents
- Bytes-Based Opening (Required Pattern)
- Layout-Aware Text Extraction
- Table Detection and Extraction
- Coordinate-Based Cropping
- Character-Level Analysis
- Integration with PyMuPDF

---

## Bytes-Based Opening (Required Pattern)

All PDFs in this codebase arrive as `bytes` from FastAPI `UploadFile.read()`. NEVER open pdfplumber with a file path in route handlers or services.

```python
# backend/app/services/revenue/pdf_extractor.py
import io
import pdfplumber

# GOOD - bytes-based opening (actual pattern used throughout codebase)
def extract_text_pdfplumber(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n\n".join(page.extract_text() or "" for page in pdf.pages)

# BAD - requires disk I/O, incompatible with FastAPI upload bytes
def extract_text_pdfplumber(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:  # NEVER do this in services
        ...
```

---

## Layout-Aware Text Extraction

### Multi-Column Detection via `layout=True`

The extract tool's pdfplumber fallback uses `layout=True` to preserve column order in multi-column Exhibit A PDFs.

```python
# backend/app/services/extract/pdf_extractor.py
import io
import pdfplumber

def _extract_with_pdfplumber(file_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            all_text = []
            for page in pdf.pages:
                text = page.extract_text(layout=True)  # preserves column order
                if text:
                    all_text.append(text)
            return "\n\n".join(all_text)
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        return ""
```

### WARNING: layout=True Performance

**The Problem:**

```python
# BAD - layout mode on every page regardless of content
with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
    for page in pdf.pages:
        text = page.extract_text(layout=True)  # 3-5x slower than default
```

**Why This Breaks:**
1. `layout=True` analyzes every character's position before assembling text
2. Single-column documents don't benefit from layout analysis
3. Revenue PDFs (EnergyLink, Energy Transfer) are typically single-column — no need for `layout=True`
4. The Extract tool only triggers pdfplumber as fallback, so performance hit is acceptable there

**The Fix:** Use `layout=True` only in the Extract tool fallback (multi-column Exhibit A). Use default `extract_text()` in the Revenue tool fallback.

---

## Table Detection and Extraction

### Exhibit A Table Parsing (Devon/Mewbourne style)

```python
# backend/app/services/extract/table_parser.py
import io
import pdfplumber

def parse_table_pdf(file_bytes: bytes, fmt) -> list:
    entries = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                logger.debug("No tables on page %d, skipping", page_num + 1)
                continue
            for table in tables:
                if not table:
                    continue
                for row in table:
                    if not row or not any(cell for cell in row if cell and cell.strip()):
                        continue
                    # process row...
    return entries
```

### Custom Table Settings for Borderless Tables

```python
# For tables without explicit borders (text-alignment based)
def extract_borderless_tables(page):
    return page.extract_tables({
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "snap_tolerance": 3,
        "join_tolerance": 3,
    })

# For tables with explicit line borders (default for revenue statements)
def extract_line_tables(page):
    return page.extract_tables({
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "intersection_tolerance": 3,
    })
```

### WARNING: Table Extraction on Malformed PDFs

**The Problem:**

```python
# BAD - assumes tables exist and rows are consistent
with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
    tables = pdf.pages[0].extract_tables()
    headers = tables[0][0]  # IndexError if no tables detected
    data = tables[0][1:]    # Assumes header + data rows
```

**Why This Breaks:**
1. `extract_tables()` returns `[]` when no table borders are detected — not an exception
2. Scanned PDFs have no text layer, so tables are always empty
3. Merged cells produce inconsistent column counts per row

**The Fix:**

```python
# GOOD - validate before accessing
with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
    tables = pdf.pages[0].extract_tables()
    if not tables:
        logger.warning("No tables detected — PDF may be scanned or unstructured")
        return []
    table = tables[0]
    if len(table) < 2:
        logger.warning(f"Table has only {len(table)} rows, need header + data")
        return []
    # safe to access table[0] for headers
```

---

## Coordinate-Based Cropping

pdfplumber uses **top-left origin** with y increasing downward (same as screen/image coordinates). This differs from raw PDF spec.

`page.crop((x0, top, x1, bottom))` where `top` and `bottom` are distances from the **top** of the page.

```python
import io
import pdfplumber

def extract_header_region(pdf_bytes: bytes) -> str:
    """Extract top 2 inches of first page (144 points)."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        first_page = pdf.pages[0]
        # top-left origin: (x0, top, x1, bottom)
        header = first_page.crop((0, 0, first_page.width, 144))
        return header.extract_text() or ""

def extract_footer_region(pdf_bytes: bytes) -> str:
    """Extract bottom 1 inch (72 points) of last page."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        last_page = pdf.pages[-1]
        footer = last_page.crop((0, last_page.height - 72, last_page.width, last_page.height))
        return footer.extract_text() or ""
```

### WARNING: Coordinate System Confusion

**The Problem:**

```python
# BAD - confuses pdfplumber coordinates with raw PDF coordinates
# Raw PDF uses bottom-left origin; pdfplumber normalizes to top-left
header = page.crop((0, page.height - 100, page.width, page.height))  # This crops the BOTTOM
```

**Why This Breaks:**
pdfplumber normalizes PDF coordinates to top-left origin. `page.chars` use `top` and `bottom` keys, both measured from the **top** of the page. The `crop()` method follows the same convention.

**The Fix:**
- `page.crop((0, 0, width, 100))` → top 100 points
- `page.crop((0, height - 100, width, height))` → bottom 100 points

---

## Character-Level Analysis

### Detect Multi-Column Layout

```python
def is_multi_column(page) -> bool:
    """Check if page has multiple text columns."""
    chars = page.chars[:500]  # sample first 500 chars for speed
    if not chars:
        return False
    x_positions = [c["x0"] for c in chars]
    # Multi-column if characters span 2+ distinct x-regions (100pt buckets)
    return len(set(int(x / 100) for x in x_positions)) > 1
```

### Extract Bold Text

```python
def extract_bold_segments(page) -> list[str]:
    """Extract text in bold font (section headings in Exhibit A)."""
    bold_chars = [c["text"] for c in page.chars if "Bold" in c.get("fontname", "")]
    return "".join(bold_chars)
```

---

## Integration with PyMuPDF

See **pymupdf** skill for the primary extraction layer. pdfplumber activates only on failure.

### When to Use Each

| Use PyMuPDF When | Use pdfplumber When |
|------------------|---------------------|
| Fast simple text extraction | Table extraction needed |
| Span-level positioning data | Multi-column layout (Exhibit A) |
| Large PDFs (speed critical) | PyMuPDF returns garbled text |
| `extract_spans_by_page()` needed | Font encoding issues detected |

### Garbled Text Score Comparison

```python
# backend/app/services/revenue/pdf_extractor.py
def extract_text(pdf_bytes: bytes) -> str:
    """Pick cleaner output by comparing garbling scores."""
    pymupdf_text = extract_text_pymupdf(pdf_bytes)
    pdfplumber_text = extract_text_pdfplumber(pdf_bytes)

    if pymupdf_text and pdfplumber_text:
        pymupdf_score = detect_garbled_text(pymupdf_text)["score"]
        plumber_score = detect_garbled_text(pdfplumber_text)["score"]
        return pdfplumber_text if plumber_score < pymupdf_score else pymupdf_text

    return pymupdf_text or pdfplumber_text or ""
```
