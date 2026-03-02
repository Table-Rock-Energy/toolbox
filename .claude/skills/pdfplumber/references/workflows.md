# Pdfplumber Workflows Reference

## Contents
- Primary/Fallback Extraction Workflow
- Revenue Statement Processing Workflow
- Table Extraction and Validation Workflow
- Debugging Failed Extractions
- Performance Optimization Workflow

---

## Primary/Fallback Extraction Workflow

Used in Extract and Revenue tools. PyMuPDF first, pdfplumber fallback.

### Complete Extraction Pipeline

```python
# toolbox/backend/app/services/extract/pdf_extractor.py
from __future__ import annotations

import fitz  # PyMuPDF
import pdfplumber
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def extract_pdf_with_fallback(pdf_path: str | Path) -> tuple[str, str]:
    """
    Extract PDF text with fallback strategy.
    Returns (text, method_used)
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Step 1: Try PyMuPDF (primary)
    text, method = try_pymupdf(pdf_path)
    
    # Step 2: Validate extraction quality
    if is_valid_extraction(text):
        logger.info(f"Extracted {len(text)} chars with {method}")
        return text, method
    
    # Step 3: Fallback to pdfplumber
    logger.warning(f"PyMuPDF extraction insufficient ({len(text)} chars), falling back")
    text, method = try_pdfplumber(pdf_path)
    
    # Step 4: Final validation
    if not is_valid_extraction(text):
        raise ValueError(
            f"PDF extraction failed. Both PyMuPDF and pdfplumber returned "
            f"<50 characters. PDF may be scanned or image-based."
        )
    
    return text, method

def try_pymupdf(pdf_path: Path) -> tuple[str, str]:
    """Extract with PyMuPDF"""
    try:
        doc = fitz.open(pdf_path)
        text = "\n\n".join(page.get_text() for page in doc)
        doc.close()
        return text, "pymupdf"
    except Exception as e:
        logger.error(f"PyMuPDF failed: {e}")
        return "", "pymupdf_failed"

def try_pdfplumber(pdf_path: Path) -> tuple[str, str]:
    """Extract with pdfplumber"""
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n\n".join(
            page.extract_text() or "" 
            for page in pdf.pages
        )
    return text, "pdfplumber"

def is_valid_extraction(text: str) -> bool:
    """Check if extraction returned meaningful text"""
    return text and len(text.strip()) >= 50
```

### Checklist: Adding PDF Extraction to New Tool

Copy this checklist when implementing PDF processing:

- [ ] Import both `fitz` (PyMuPDF) and `pdfplumber`
- [ ] Try PyMuPDF first with error handling
- [ ] Validate extraction quality (min 50 chars)
- [ ] Fallback to pdfplumber if validation fails
- [ ] Log which method succeeded
- [ ] Raise descriptive error if both fail (mention OCR requirement)
- [ ] Close PyMuPDF documents explicitly or use context manager
- [ ] Use pdfplumber context manager (`with pdfplumber.open()`)

---

## Revenue Statement Processing Workflow

Multi-step workflow for parsing revenue PDFs into M1 CSV format.

### Complete Revenue Processing Pipeline

```python
# toolbox/backend/app/services/revenue/statement_parser.py
from __future__ import annotations

import pdfplumber
import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

def process_revenue_statement(pdf_path: Path) -> pd.DataFrame:
    """
    Extract revenue data from PDF and convert to M1 format.
    
    Steps:
    1. Extract all tables from PDF
    2. Identify revenue table (vs summary/header tables)
    3. Normalize column headers
    4. Validate required columns exist
    5. Transform to M1 format
    """
    
    # Step 1: Extract tables
    tables = extract_all_tables(pdf_path)
    if not tables:
        raise ValueError(f"No tables found in {pdf_path.name}")
    
    # Step 2: Identify revenue table
    revenue_table = identify_revenue_table(tables)
    if not revenue_table:
        raise ValueError("Could not identify revenue table (missing expected columns)")
    
    # Step 3: Normalize headers
    df = normalize_revenue_table(revenue_table)
    
    # Step 4: Validate required columns
    validate_columns(df)
    
    # Step 5: Transform to M1 format
    m1_df = transform_to_m1(df)
    
    logger.info(f"Processed {len(m1_df)} revenue rows from {pdf_path.name}")
    return m1_df

def extract_all_tables(pdf_path: Path) -> List[List[List[str]]]:
    """Extract all tables from PDF"""
    all_tables = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_tolerance": 3
            })
            
            logger.debug(f"Found {len(tables)} tables on page {page_num}")
            all_tables.extend(tables)
    
    return all_tables

def identify_revenue_table(tables: List[List[List[str]]]) -> List[List[str]] | None:
    """Find the main revenue table (has Well, Owner, Volume columns)"""
    required_keywords = ['well', 'owner', 'volume']
    
    for table in tables:
        if len(table) < 2:
            continue
        
        # Check if header row contains required keywords
        header = [str(cell).lower() for cell in table[0]]
        header_text = ' '.join(header)
        
        if all(keyword in header_text for keyword in required_keywords):
            return table
    
    return None

def normalize_revenue_table(table: List[List[str]]) -> pd.DataFrame:
    """Convert table to DataFrame with normalized headers"""
    if not table or len(table) < 2:
        raise ValueError("Table is empty or missing data rows")
    
    # Extract headers and rows
    headers = [str(h).strip() for h in table[0]]
    rows = table[1:]
    
    # Create DataFrame
    df = pd.DataFrame(rows, columns=headers)
    
    # Normalize column names
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    
    # Remove empty rows
    df = df[df.astype(str).apply(lambda row: row.str.strip().str.len().sum() > 0, axis=1)]
    
    return df

def validate_columns(df: pd.DataFrame) -> None:
    """Ensure required columns exist"""
    required = ['well_name', 'owner_name', 'volume', 'revenue']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Found: {list(df.columns)}")

def transform_to_m1(df: pd.DataFrame) -> pd.DataFrame:
    """Transform to M1 upload format (29 columns)"""
    # See Revenue tool spec for full M1 column mapping
    m1_columns = [
        'Property Number', 'Owner Number', 'Owner Name',
        'Production Month', 'Product', 'Volume', 'Revenue',
        # ... 22 more columns
    ]
    
    # Map revenue table to M1 format
    m1_df = pd.DataFrame({
        'Owner Name': df['owner_name'],
        'Volume': df['volume'],
        'Revenue': df['revenue'],
        # ... additional mappings
    })
    
    return m1_df
```

### Checklist: Revenue PDF Processing

Copy this when processing new revenue statement vendors:

- [ ] Extract all tables with `page.extract_tables()`
- [ ] Log table count per page for debugging
- [ ] Identify revenue table by header keywords
- [ ] Handle multiple tables (summary, detail, totals)
- [ ] Normalize column headers (lowercase, underscores)
- [ ] Remove empty rows after DataFrame creation
- [ ] Validate required columns exist before transformation
- [ ] Map to M1 29-column format
- [ ] Test with 3+ sample PDFs from vendor
- [ ] Document vendor-specific quirks in code comments

---

## Table Extraction and Validation Workflow

Robust table extraction with validation and error handling.

### Production-Grade Table Extraction

```python
# toolbox/backend/app/services/revenue/table_extractor.py
from __future__ import annotations

import pdfplumber
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def extract_validated_tables(
    pdf_path: str,
    min_rows: int = 2,
    min_cols: int = 2,
    require_headers: bool = True
) -> List[pd.DataFrame]:
    """
    Extract tables with comprehensive validation.
    
    Returns list of DataFrames, one per valid table found.
    """
    valid_tables = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            
            if not tables:
                logger.debug(f"Page {page_num}: no tables detected")
                continue
            
            for table_num, table in enumerate(tables, 1):
                # Validate table structure
                validation_result = validate_table(
                    table, 
                    page_num, 
                    table_num,
                    min_rows=min_rows,
                    min_cols=min_cols
                )
                
                if not validation_result['valid']:
                    logger.warning(
                        f"Page {page_num} Table {table_num}: "
                        f"{validation_result['reason']}"
                    )
                    continue
                
                # Convert to DataFrame
                df = table_to_dataframe(table, require_headers)
                valid_tables.append(df)
                
                logger.info(
                    f"Page {page_num} Table {table_num}: "
                    f"extracted {len(df)} rows × {len(df.columns)} cols"
                )
    
    if not valid_tables:
        raise ValueError(f"No valid tables found in {pdf_path}")
    
    return valid_tables

def validate_table(
    table: List[List[str]], 
    page_num: int,
    table_num: int,
    min_rows: int = 2,
    min_cols: int = 2
) -> Dict[str, any]:
    """Validate table structure"""
    
    if not table:
        return {'valid': False, 'reason': 'empty table'}
    
    if len(table) < min_rows:
        return {
            'valid': False, 
            'reason': f'only {len(table)} rows (need {min_rows})'
        }
    
    # Check column consistency
    col_counts = [len(row) for row in table]
    if len(set(col_counts)) > 1:
        return {
            'valid': False,
            'reason': f'inconsistent columns: {col_counts}'
        }
    
    if col_counts[0] < min_cols:
        return {
            'valid': False,
            'reason': f'only {col_counts[0]} columns (need {min_cols})'
        }
    
    return {'valid': True}

def table_to_dataframe(table: List[List[str]], require_headers: bool) -> pd.DataFrame:
    """Convert validated table to DataFrame"""
    import pandas as pd
    
    if require_headers:
        headers = [str(h).strip() for h in table[0]]
        rows = table[1:]
        df = pd.DataFrame(rows, columns=headers)
    else:
        df = pd.DataFrame(table)
    
    # Clean data
    df = df.applymap(lambda x: str(x).strip() if x else '')
    
    # Remove completely empty rows
    df = df[df.astype(bool).any(axis=1)]
    
    return df
```

### Iterate-Until-Pass: Table Extraction

When table extraction fails, follow this debugging loop:

1. **Extract with default settings**
   ```python
   tables = page.extract_tables()
   ```

2. **Validate extraction**: Check if tables exist and have expected structure
   ```bash
   # Run extraction and log table count
   python3 -m app.services.revenue.table_extractor
   ```

3. **If validation fails**, adjust extraction settings and repeat step 2:
   ```python
   # Try text-based strategy for borderless tables
   tables = page.extract_tables({
       "vertical_strategy": "text",
       "horizontal_strategy": "text"
   })
   ```

4. **If still failing**, visualize table detection:
   ```python
   # Debug: save page image with table boundaries
   im = page.to_image()
   im.debug_tablefinder()
   im.save('debug_tables.png')
   ```

5. **Only proceed when**:
   - Table count matches expected (e.g., 1 main table per page)
   - All tables pass validation (min rows/cols)
   - Headers extracted correctly

---

## Debugging Failed Extractions

When `extract_text()` or `extract_tables()` fails or returns poor results.

### Diagnostic Workflow

```python
# toolbox/backend/app/services/extract/pdf_diagnostics.py
import pdfplumber
from pathlib import Path

def diagnose_pdf(pdf_path: Path):
    """
    Run diagnostics on problematic PDF.
    Prints detailed info about PDF structure.
    """
    print(f"\n=== Diagnosing {pdf_path.name} ===\n")
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        print(f"Metadata: {pdf.metadata}\n")
        
        for i, page in enumerate(pdf.pages[:3], 1):  # First 3 pages
            print(f"--- Page {i} ---")
            print(f"Size: {page.width:.1f} × {page.height:.1f} points")
            
            # Character count
            chars = page.chars
            print(f"Characters: {len(chars)}")
            
            if chars:
                # Font analysis
                fonts = {}
                for char in chars:
                    font = char.get('fontname', 'Unknown')
                    fonts[font] = fonts.get(font, 0) + 1
                
                print(f"Fonts: {fonts}")
            
            # Text extraction quality
            text = page.extract_text()
            print(f"Extracted text length: {len(text) if text else 0}")
            print(f"First 100 chars: {text[:100] if text else 'EMPTY'}")
            
            # Table detection
            tables = page.extract_tables()
            print(f"Tables detected: {len(tables)}")
            
            if tables:
                for j, table in enumerate(tables, 1):
                    print(f"  Table {j}: {len(table)} rows × {len(table[0])} cols")
            
            print()

# Usage:
# python3 -c "from app.services.extract.pdf_diagnostics import diagnose_pdf; diagnose_pdf(Path('problem.pdf'))"
```

### Visual Debugging

```python
def debug_table_detection(pdf_path: Path, page_num: int = 0):
    """Save image showing detected table boundaries"""
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num]
        
        # Generate image with table boundaries
        im = page.to_image(resolution=150)
        im.debug_tablefinder()
        
        output_path = f"debug_page_{page_num}.png"
        im.save(output_path)
        print(f"Saved debug image to {output_path}")
```

### Common Failure Modes

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Empty string from `extract_text()` | Scanned PDF (images, no text layer) | Requires OCR preprocessing |
| `extract_tables()` returns `[]` | No table borders detected | Try `vertical_strategy="text"` |
| Mangled text, wrong order | Multi-column layout | Use `extract_text(layout=True)` |
| Table has wrong row/col count | Merged cells, complex borders | Adjust `intersection_tolerance` |
| Some characters missing | Font embedding issues | Fallback to PyMuPDF or OCR |

---

## Performance Optimization Workflow

Optimize pdfplumber for large PDFs or high-throughput scenarios.

### Benchmark and Optimize

```python
import time
import pdfplumber
from pathlib import Path

def benchmark_extraction(pdf_path: Path):
    """Measure extraction performance"""
    
    # Test 1: Default extraction
    start = time.time()
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    default_time = time.time() - start
    
    # Test 2: Layout mode
    start = time.time()
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text(layout=True) or "" for page in pdf.pages)
    layout_time = time.time() - start
    
    # Test 3: Table extraction
    start = time.time()
    with pdfplumber.open(pdf_path) as pdf:
        tables = [page.extract_tables() for page in pdf.pages]
    table_time = time.time() - start
    
    print(f"Default extraction: {default_time:.2f}s")
    print(f"Layout mode: {layout_time:.2f}s ({layout_time/default_time:.1f}x slower)")
    print(f"Table extraction: {table_time:.2f}s")
```

### Optimization Checklist

Copy this when optimizing PDF processing:

- [ ] Profile current performance (baseline timing)
- [ ] Use default `extract_text()` for single-column PDFs (3-5x faster than layout mode)
- [ ] Only enable `layout=True` when multi-column detected
- [ ] Process pages lazily with generators (avoid loading all into memory)
- [ ] Use PyMuPDF for simple text extraction (10x faster than pdfplumber)
- [ ] Cache extracted text in storage/DB to avoid re-extraction
- [ ] For 100+ page PDFs, process in batches of 10-20 pages
- [ ] Consider async processing for multiple PDFs (see **fastapi** skill)
- [ ] Monitor memory usage with large PDFs (use `psutil` or CloudWatch)
- [ ] Document extraction method used (PyMuPDF vs pdfplumber) in job metadata

### Production Optimization Pattern

```python
# toolbox/backend/app/services/extract/optimized_extractor.py
from __future__ import annotations

import fitz  # PyMuPDF
import pdfplumber
import logging
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

def extract_pdf_optimized(pdf_path: Path) -> str:
    """
    Optimized extraction:
    1. Try PyMuPDF (10x faster)
    2. Detect if layout mode needed
    3. Only use pdfplumber layout mode if necessary
    """
    
    # Try PyMuPDF first
    try:
        with fitz.open(pdf_path) as doc:
            text = "\n\n".join(page.get_text() for page in doc)
            if len(text.strip()) > 50:
                logger.info(f"Extracted with PyMuPDF in fast path")
                return text
    except Exception as e:
        logger.warning(f"PyMuPDF failed: {e}")
    
    # Fallback to pdfplumber with smart layout detection
    with pdfplumber.open(pdf_path) as pdf:
        # Check first page for layout complexity
        first_page = pdf.pages[0]
        needs_layout = is_multi_column(first_page)
        
        logger.info(f"Using pdfplumber (layout={needs_layout})")
        
        # Extract with appropriate settings
        return "\n\n".join(
            page.extract_text(layout=needs_layout) or ""
            for page in pdf.pages
        )

def is_multi_column(page) -> bool:
    """Quick check for multi-column layout"""
    chars = page.chars[:500]  # Sample first 500 chars
    if not chars:
        return False
    
    x_positions = [c['x0'] for c in chars]
    # Multi-column if characters span 2+ distinct x-regions
    return len(set(int(x / 100) for x in x_positions)) > 1