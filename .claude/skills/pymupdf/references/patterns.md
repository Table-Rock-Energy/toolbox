# PyMuPDF Patterns Reference

## Contents
- Opening PDFs: Bytes vs File Paths
- Extraction Modes
- Garbled Text Detection
- Column-Aware Extraction (Extract Tool)
- Span-Level Extraction (Revenue Tool)
- Memory Management
- Anti-Patterns

---

## Opening PDFs: Bytes vs File Paths

**ALWAYS open from bytes.** FastAPI routes receive `UploadFile` — read bytes immediately, pass bytes throughout the service layer. Never assume a local file path exists.

```python
# GOOD — from bytes (actual pattern in this codebase)
async def upload(file: UploadFile):
    pdf_bytes = await file.read()
    text = extract_text_pymupdf(pdf_bytes)

def extract_text_pymupdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    # ...
    doc.close()
```

### WARNING: Opening by File Path

**The Problem:**
```python
# BAD — assumes local file system
doc = fitz.open(pdf_path)  # Path may not exist in GCS + Cloud Run
```

**Why This Breaks:**
1. GCS storage doesn't guarantee local paths — files live in Cloud Run's ephemeral filesystem
2. `StorageService` may use GCS blobs, not local paths
3. Breaks silently in production while working fine in local dev (where fallback uses `backend/data/`)

**The Fix:** Read bytes from `UploadFile` and pass `bytes` to all extraction functions.

---

## Extraction Modes

### `"text"` Mode — Revenue Tool

Simple string extraction. Use when you need full-page text for regex-based parsing.

```python
# backend/app/services/revenue/pdf_extractor.py
def extract_text_pymupdf(pdf_bytes: bytes) -> str:
    text_parts = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        text_parts.append(text)
    doc.close()
    return "\n\n".join(text_parts)
```

### `"dict"` Mode — Extract Tool

Returns structured blocks/lines/spans with bounding boxes. Required for column-aware layouts.

```python
# backend/app/services/extract/pdf_extractor.py
doc = fitz.open(stream=file_bytes, filetype="pdf")
page = doc[0]
blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

# Block structure:
# {
#   "type": 0,        # 0=text, 1=image
#   "bbox": (x0, y0, x1, y1),
#   "lines": [
#     {"spans": [{"text": "...", "bbox": (...)}]}
#   ]
# }
text_blocks = [b for b in blocks if b.get("type") == 0]  # Skip images
```

### `"dict"` Mode — Span Extraction (Revenue Enverus Parser)

```python
# backend/app/services/revenue/pdf_extractor.py — extract_spans_by_page()
from dataclasses import dataclass

@dataclass
class TextSpan:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page_num: int

def extract_spans_by_page(pdf_bytes: bytes) -> dict[int, list[TextSpan]]:
    pages: dict[int, list[TextSpan]] = {}
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        blocks = page.get_text("dict")["blocks"]
        spans: list[TextSpan] = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    bbox = span["bbox"]
                    spans.append(TextSpan(text=text, x0=bbox[0], y0=bbox[1],
                                         x1=bbox[2], y1=bbox[3], page_num=page_num))
        pages[page_num] = spans
    doc.close()
    return pages
```

Use span extraction when you need to reconstruct multi-column revenue statements by x/y position.

---

## Garbled Text Detection

Revenue PDFs with custom font encoding produce garbage characters. The `detect_garbled_text()` function in `backend/app/services/revenue/pdf_extractor.py` scores both PyMuPDF and pdfplumber output and returns whichever is cleaner.

```python
# Garbled indicators checked:
# 1. Characters in _GARBLED_CHARS set (¢£¤¥ etc.)
# 2. Doubled letter codes: Oo, oO, Gg, gG (font encoding artifacts)
# 3. Large integers where decimals expected (7+ digit numbers)
# 4. >2% non-ASCII character ratio in financial documents

def detect_garbled_text(text: str) -> dict:
    """Returns {"garbled": bool, "score": int, "indicators": list[str]}"""
    # score >= 3 → garbled = True
```

```python
# Comparison logic in extract_text()
if pymupdf_text and pdfplumber_text:
    pymupdf_garbled = detect_garbled_text(pymupdf_text)
    plumber_garbled = detect_garbled_text(pdfplumber_text)
    if plumber_garbled["score"] < pymupdf_garbled["score"]:
        return pdfplumber_text
    return pymupdf_text
```

**Do NOT assume PyMuPDF always wins.** Energy Transfer PDFs often have better pdfplumber output.

---

## Column-Aware Extraction (Extract Tool)

OCC Exhibit A PDFs use 2-3 column layouts. `_sort_blocks_by_columns()` in `backend/app/services/extract/pdf_extractor.py` assigns blocks to columns by x-position then reads left-to-right, top-to-bottom.

```python
# backend/app/services/extract/pdf_extractor.py
def detect_column_count(file_bytes: bytes) -> int:
    """Auto-detects 2 or 3 columns from first page block positions. Default: 3."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page = doc[0]
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    doc.close()

    x_positions = [(b["bbox"][0] + b["bbox"][2]) / 2
                   for b in blocks if b.get("type") == 0]
    # Clusters x-positions into thirds vs halves to detect 2 vs 3 columns
```

```python
def _sort_blocks_by_columns(blocks, page_width, num_columns=3):
    column_width = page_width / num_columns
    def get_column(block):
        x_center = (block["bbox"][0] + block["bbox"][2]) / 2
        return min(int(x_center / column_width), num_columns - 1)
    # Assigns to columns, sorts by y within each, then interleaves row-by-row
```

---

## Memory Management

### DO: Always Close Documents

```python
# Pattern 1: Explicit close in try/finally
doc = fitz.open(stream=pdf_bytes, filetype="pdf")
try:
    pages = [doc.load_page(i).get_text("text") for i in range(len(doc))]
finally:
    doc.close()

# Pattern 2: Context manager (preferred for simple cases)
with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
    pages = [page.get_text("text") for page in doc]
```

Note: The actual codebase uses explicit `doc.close()` (not context manager). Both are correct — choose one and be consistent within a file.

### WARNING: Unclosed Documents in Batch Loops

```python
# BAD — document leaks if exception occurs mid-loop
for pdf_bytes in batch:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    doc.close()  # Never reached if get_text() raises
```

```python
# GOOD — guaranteed close
for pdf_bytes in batch:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        text = "".join(page.get_text() for page in doc)
    finally:
        doc.close()
```

In Cloud Run with 1Gi memory, 50+ unclosed documents will OOM-kill the container.

---

## Anti-Patterns

### WARNING: Ignoring Empty Extraction

```python
# BAD — scanned PDFs return "" which downstream parsers choke on
def extract(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    doc.close()
    return text  # "" for image-based PDFs
```

```python
# GOOD — validate before returning
def extract(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        text = "\n\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()
    if not text.strip():
        raise RuntimeError("pymupdf extraction failed: empty text")
    return text
```

### WARNING: Bare `except` Hiding fitz Errors

```python
# BAD — swallows password-protected PDF errors silently
try:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = doc[0].get_text()
except:
    return ""
```

Catch `Exception` specifically and re-raise with context so the fallback chain can respond properly.
