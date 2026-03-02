---
name: pdfplumber
description: |
  Extracts text from PDFs with fallback extraction methods for Table Rock TX Tools backend services
  Use when: processing OCC Exhibit A PDFs, revenue statements, or any PDF text extraction in Extract/Revenue tools
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Pdfplumber Skill

pdfplumber is the **fallback** PDF extraction library in Table Rock TX Tools, used when PyMuPDF (fitz) fails or produces poor results. It excels at table extraction and layout-aware text parsing, making it critical for structured documents like revenue statements and OCC exhibits.

## Quick Start

### Basic Text Extraction (Fallback Pattern)

```python
# toolbox/backend/app/services/extract/pdf_extractor.py
import pdfplumber

def extract_text_fallback(pdf_path: str) -> str:
    """Fallback extraction when PyMuPDF fails"""
    text_parts = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    
    return "\n\n".join(text_parts)
```

### Table Extraction (Revenue Tool)

```python
# toolbox/backend/app/services/revenue/statement_parser.py
import pdfplumber

def extract_revenue_table(pdf_path: str) -> list[dict]:
    """Extract tabular data from revenue statements"""
    rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                # Filter empty rows, normalize headers
                rows.extend([row for row in table if any(cell for cell in row)])
    
    return rows
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| `pdfplumber.open()` | Context manager for PDF files | `with pdfplumber.open(path) as pdf:` |
| `page.extract_text()` | Layout-aware text extraction | `text = page.extract_text()` |
| `page.extract_tables()` | Detect and extract tables | `tables = page.extract_tables()` |
| `page.chars` | Access individual characters with positioning | `chars = page.chars` |
| `page.crop()` | Extract from specific page region | `cropped = page.crop((x0, y0, x1, y1))` |

## Common Patterns

### Primary/Fallback Extraction

**When:** PyMuPDF fails or returns empty text

```python
# toolbox/backend/app/services/extract/pdf_extractor.py
import fitz  # PyMuPDF
import pdfplumber

def extract_pdf_text(pdf_path: str) -> str:
    # Try PyMuPDF first (faster)
    text = extract_with_pymupdf(pdf_path)
    
    if not text or len(text.strip()) < 50:
        # Fallback to pdfplumber for layout-heavy PDFs
        text = extract_with_pdfplumber(pdf_path)
    
    return text

def extract_with_pdfplumber(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n\n".join(
            page.extract_text() or "" 
            for page in pdf.pages
        )
```

### Table Extraction with Validation

**When:** Parsing structured revenue statements or proration data

```python
# toolbox/backend/app/services/revenue/statement_parser.py
import pdfplumber

def extract_validated_tables(pdf_path: str) -> list[list[str]]:
    """Extract tables and validate structure"""
    all_rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            
            for table in tables:
                # Skip empty or malformed tables
                if not table or len(table) < 2:
                    continue
                
                # Validate minimum column count
                if any(len(row) < 3 for row in table):
                    logger.warning(f"Skipping malformed table on page {page_num}")
                    continue
                
                all_rows.extend(table)
    
    return all_rows
```

### Region-Specific Extraction

**When:** Extracting specific sections (headers, footers, signature blocks)

```python
import pdfplumber

def extract_header_region(pdf_path: str) -> str:
    """Extract text from top 2 inches of first page"""
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        
        # Crop to header region (top 144 points = 2 inches)
        header = first_page.crop((0, 0, first_page.width, 144))
        return header.extract_text() or ""
```

## WARNING: Common Pitfalls

### Empty Text Without Error

**The Problem:**

```python
# BAD - Silent failure on scanned PDFs
with pdfplumber.open(scanned_pdf) as pdf:
    text = pdf.pages[0].extract_text()
    # text is empty string, no exception raised
```

**Why This Breaks:**
1. Scanned PDFs contain images, not text layers
2. pdfplumber returns empty string instead of raising an error
3. Downstream parsing fails silently with no indication of the root cause

**The Fix:**

```python
# GOOD - Validate and provide actionable feedback
with pdfplumber.open(pdf_path) as pdf:
    text = pdf.pages[0].extract_text()
    
    if not text or len(text.strip()) < 10:
        raise ValueError(
            f"PDF appears to be scanned or image-based. "
            f"Text extraction returned {len(text)} characters. "
            f"OCR preprocessing required."
        )
```

### Memory Leaks with Large PDFs

**The Problem:**

```python
# BAD - Holds entire PDF in memory
pdf = pdfplumber.open(large_pdf)
for page in pdf.pages:
    process_page(page)
# Forgot to close, file handle leaks
```

**Why This Breaks:**
1. pdfplumber loads entire PDF structure into memory
2. Missing `close()` leaks file handles
3. Processing 100+ page PDFs can exhaust memory

**The Fix:**

```python
# GOOD - Use context manager
with pdfplumber.open(large_pdf) as pdf:
    for page in pdf.pages:
        process_page(page)
# Automatically closes and releases memory
```

## See Also

- [patterns](references/patterns.md) - Table detection, layout analysis, coordinate systems
- [workflows](references/workflows.md) - Primary/fallback extraction, debugging failed extraction

## Related Skills

- **pymupdf** - Primary PDF extraction library, faster but less layout-aware
- **python** - Python backend patterns and async operations
- **fastapi** - FastAPI route handlers that use PDF extraction services
- **pandas** - DataFrame operations for structured table data from PDFs