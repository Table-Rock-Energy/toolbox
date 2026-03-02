# Pdfplumber Patterns Reference

## Contents
- Layout-Aware Text Extraction
- Table Detection and Extraction
- Coordinate-Based Cropping
- Character-Level Analysis
- Integration with PyMuPDF Fallback
- Memory Management

---

## Layout-Aware Text Extraction

pdfplumber preserves layout by analyzing character positions. Use this for multi-column documents.

### Multi-Column Detection

```python
# toolbox/backend/app/services/extract/pdf_extractor.py
import pdfplumber

def extract_with_layout(pdf_path: str) -> str:
    """Preserve multi-column layout"""
    with pdfplumber.open(pdf_path) as pdf:
        text_parts = []
        
        for page in pdf.pages:
            # Use layout parameter to preserve columns
            text = page.extract_text(layout=True)
            if text:
                text_parts.append(text)
        
        return "\n\n".join(text_parts)
```

### WARNING: Layout Mode Performance

**The Problem:**

```python
# BAD - Layout mode on simple single-column PDFs
with pdfplumber.open(simple_pdf) as pdf:
    for page in pdf.pages:
        text = page.extract_text(layout=True)  # 3-5x slower
```

**Why This Breaks:**
1. Layout mode analyzes character positioning for every character
2. Single-column PDFs don't need layout preservation
3. Unnecessary 3-5x performance penalty

**The Fix:**

```python
# GOOD - Detect layout complexity first
def needs_layout_mode(page) -> bool:
    """Check if page has multiple columns"""
    chars = page.chars
    if not chars:
        return False
    
    # Simple heuristic: check x-position variance
    x_positions = [c['x0'] for c in chars]
    return len(set(int(x / 50) for x in x_positions)) > 2

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text(layout=needs_layout_mode(page))
```

---

## Table Detection and Extraction

pdfplumber excels at table extraction. Critical for Revenue tool.

### Revenue Statement Tables

```python
# toolbox/backend/app/services/revenue/statement_parser.py
import pdfplumber
from typing import List, Dict

def extract_revenue_tables(pdf_path: str) -> List[Dict[str, str]]:
    """Extract all tables, normalize headers"""
    all_rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Extract tables with custom settings
            tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_tolerance": 3
            })
            
            for table in tables:
                if not table or len(table) < 2:
                    continue
                
                # First row is header
                headers = [h.strip() if h else "" for h in table[0]]
                
                # Convert rows to dicts
                for row in table[1:]:
                    if any(cell for cell in row):  # Skip empty rows
                        row_dict = dict(zip(headers, row))
                        all_rows.append(row_dict)
    
    return all_rows
```

### Custom Table Settings

```python
# For borderless tables (common in OCC exhibits)
def extract_borderless_tables(page):
    """Extract tables without explicit borders"""
    return page.extract_tables({
        "vertical_strategy": "text",  # Use text alignment
        "horizontal_strategy": "text",
        "snap_tolerance": 3,
        "join_tolerance": 3
    })
```

### WARNING: Table Extraction on Malformed PDFs

**The Problem:**

```python
# BAD - Assumes tables exist and are well-formed
with pdfplumber.open(pdf_path) as pdf:
    tables = pdf.pages[0].extract_tables()
    headers = tables[0][0]  # IndexError if no tables
    data = tables[0][1:]    # Assumes at least 2 rows
```

**Why This Breaks:**
1. `extract_tables()` returns empty list if no tables detected
2. Malformed tables may have inconsistent column counts per row
3. Scanned PDFs return empty lists without error

**The Fix:**

```python
# GOOD - Validate before accessing
with pdfplumber.open(pdf_path) as pdf:
    tables = pdf.pages[0].extract_tables()
    
    if not tables:
        raise ValueError("No tables detected. PDF may be scanned or unstructured.")
    
    table = tables[0]
    if len(table) < 2:
        raise ValueError(f"Table has only {len(table)} rows, need at least 2 (header + data)")
    
    # Validate column consistency
    header_cols = len(table[0])
    for i, row in enumerate(table):
        if len(row) != header_cols:
            logger.warning(f"Row {i} has {len(row)} columns, expected {header_cols}")
```

---

## Coordinate-Based Cropping

Extract specific regions by coordinates. Useful for headers, footers, signature blocks.

### Extract Header Region

```python
# toolbox/backend/app/services/extract/pdf_extractor.py
def extract_header(pdf_path: str) -> str:
    """Extract top 2 inches of first page"""
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        
        # PDF coordinates: (x0, y0, x1, y1) from bottom-left
        # 72 points = 1 inch, so 144 points = 2 inches
        header_bbox = (0, 0, first_page.width, 144)
        
        header_region = first_page.crop(header_bbox)
        return header_region.extract_text() or ""
```

### Extract Footer (Pagination, Disclaimers)

```python
def extract_footer(pdf_path: str) -> str:
    """Extract bottom 1 inch of last page"""
    with pdfplumber.open(pdf_path) as pdf:
        last_page = pdf.pages[-1]
        
        # 72 points from bottom
        footer_bbox = (0, last_page.height - 72, last_page.width, last_page.height)
        
        footer_region = last_page.crop(footer_bbox)
        return footer_region.extract_text() or ""
```

### WARNING: Coordinate System Confusion

**The Problem:**

```python
# BAD - Assumes top-left origin like images
header = page.crop((0, 0, page.width, 100))  # Actually crops BOTTOM
```

**Why This Breaks:**
1. PDFs use **bottom-left** origin, not top-left like images
2. Y-axis increases **upward**, not downward
3. This crops the bottom 100 points, not the top

**The Fix:**

```python
# GOOD - Use correct PDF coordinate system
# To crop TOP 100 points:
header = page.crop((0, page.height - 100, page.width, page.height))

# To crop BOTTOM 100 points:
footer = page.crop((0, 0, page.width, 100))
```

---

## Character-Level Analysis

Access individual characters with positioning data for advanced parsing.

### Detect Multi-Column Layout

```python
def is_multi_column(page) -> bool:
    """Detect if page has multiple columns"""
    chars = page.chars
    if not chars:
        return False
    
    # Group characters by X position (50pt buckets)
    x_buckets = {}
    for char in chars:
        bucket = int(char['x0'] / 50)
        x_buckets[bucket] = x_buckets.get(bucket, 0) + 1
    
    # Multi-column if 2+ buckets have significant text
    significant_buckets = [count for count in x_buckets.values() if count > 50]
    return len(significant_buckets) >= 2
```

### Extract Bold Text (Section Headings)

```python
def extract_bold_text(page) -> List[str]:
    """Extract text in bold font (often headings)"""
    bold_text = []
    
    for char in page.chars:
        # Check if font name contains "Bold"
        if 'Bold' in char.get('fontname', ''):
            bold_text.append(char['text'])
    
    # Join consecutive bold chars into words
    return [''.join(bold_text).split()]
```

---

## Integration with PyMuPDF Fallback

See **pymupdf** skill for primary extraction. pdfplumber is the fallback.

### Primary/Fallback Pattern

```python
# toolbox/backend/app/services/extract/pdf_extractor.py
import fitz  # PyMuPDF
import pdfplumber
import logging

logger = logging.getLogger(__name__)

def extract_pdf_text(pdf_path: str) -> str:
    """Try PyMuPDF first, fallback to pdfplumber"""
    
    # Primary: PyMuPDF (faster)
    try:
        doc = fitz.open(pdf_path)
        text = "\n\n".join(page.get_text() for page in doc)
        doc.close()
        
        if text and len(text.strip()) > 50:
            logger.info("Extracted with PyMuPDF")
            return text
    except Exception as e:
        logger.warning(f"PyMuPDF failed: {e}")
    
    # Fallback: pdfplumber (better layout handling)
    logger.info("Falling back to pdfplumber")
    with pdfplumber.open(pdf_path) as pdf:
        return "\n\n".join(
            page.extract_text() or "" 
            for page in pdf.pages
        )
```

### When to Use Each Library

| Use PyMuPDF When | Use pdfplumber When |
|------------------|---------------------|
| Simple text extraction | Table extraction needed |
| Speed is critical | Multi-column layouts |
| Single-column documents | Borderless tables |
| Large PDFs (100+ pages) | Layout preservation critical |

---

## Memory Management

pdfplumber loads entire PDF structure into memory. Manage carefully for large files.

### Process Large PDFs

```python
# GOOD - Process pages in batches
def process_large_pdf(pdf_path: str, batch_size: int = 10):
    """Process large PDF in batches"""
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        
        for start in range(0, total_pages, batch_size):
            end = min(start + batch_size, total_pages)
            batch = pdf.pages[start:end]
            
            for page in batch:
                text = page.extract_text()
                yield text  # Stream results
```

### WARNING: Loading Full PDF Into Memory

**The Problem:**

```python
# BAD - Loads entire 200-page PDF into list
with pdfplumber.open(large_pdf) as pdf:
    all_text = [page.extract_text() for page in pdf.pages]  # 500MB+ memory
    return "\n".join(all_text)
```

**Why This Breaks:**
1. List comprehension loads all pages before processing any
2. 200-page PDF with images can use 500MB+ RAM
3. Multiple concurrent requests exhaust memory

**The Fix:**

```python
# GOOD - Stream pages with generator
def extract_text_stream(pdf_path: str):
    """Stream text extraction to avoid memory spike"""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            yield page.extract_text() or ""

# Use with join or process incrementally
text = "\n\n".join(extract_text_stream(pdf_path))