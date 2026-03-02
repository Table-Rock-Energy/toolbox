# PyMuPDF Patterns Reference

## Contents
- Extract Tool Integration
- Revenue Tool Integration
- Error Handling & Fallback
- Memory Management
- Common Pitfalls

---

## Extract Tool Integration

PyMuPDF is the **primary** extraction method in `backend/app/services/extract/pdf_extractor.py`.

### DO: Primary Extraction with Graceful Fallback

```python
# backend/app/services/extract/pdf_extractor.py
import fitz
import logging

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text using PyMuPDF, fallback to pdfplumber."""
    try:
        doc = fitz.open(pdf_path)
        pages = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():  # Only add non-empty pages
                pages.append(text)
        
        doc.close()
        
        full_text = "\n\n".join(pages)
        if not full_text.strip():
            logger.warning(f"PyMuPDF extracted empty text from {pdf_path}")
            raise ValueError("Empty extraction")
        
        return full_text
        
    except Exception as e:
        logger.warning(f"PyMuPDF failed for {pdf_path}: {e}, trying pdfplumber")
        return extract_with_pdfplumber(pdf_path)
```

**Why this works:**
1. Always validates extracted text is non-empty before returning
2. Explicit logging helps debugging which extractor was used
3. Graceful fallback prevents total failure
4. Page-by-page extraction allows filtering empty pages

### DON'T: Ignore Empty Extraction Results

```python
# BAD - Returns empty string silently
def extract_text_bad(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text = "".join(page.get_text() for page in doc)
    doc.close()
    return text  # Might be empty!
```

**Why this breaks:**
1. Downstream parsers receive empty input and fail cryptically
2. No fallback attempt, wasted extraction opportunity
3. No logging of the failure
4. User sees "no parties found" instead of actual parsing

---

## Revenue Tool Integration

The Revenue tool processes multiple PDFs in a single upload. PyMuPDF must handle batch operations efficiently.

### DO: Process Multiple PDFs with Per-File Fallback

```python
# backend/app/services/revenue/pdf_processor.py
from typing import List
import fitz

def process_multiple_pdfs(pdf_paths: List[str]) -> List[dict]:
    """Process multiple revenue statement PDFs."""
    results = []
    
    for pdf_path in pdf_paths:
        try:
            text = extract_single_pdf(pdf_path)
            parsed = parse_revenue_statement(text)
            results.append({
                "file": pdf_path,
                "status": "success",
                "data": parsed
            })
        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}")
            results.append({
                "file": pdf_path,
                "status": "error",
                "error": str(e)
            })
    
    return results

def extract_single_pdf(pdf_path: str) -> str:
    """Extract with PyMuPDF, fallback to pdfplumber."""
    try:
        with fitz.open(pdf_path) as doc:
            text = "\n\n".join(page.get_text() for page in doc)
            if text.strip():
                return text
            raise ValueError("Empty PyMuPDF extraction")
    except Exception:
        return extract_with_pdfplumber(pdf_path)
```

**Why this works:**
1. One file failure doesn't crash entire batch
2. Per-file error tracking for user feedback
3. Fallback per file, not for entire batch
4. Clean separation of extraction vs. parsing logic

### DON'T: Use Single Try-Catch for Batch Operations

```python
# BAD - One failure kills entire batch
def process_multiple_pdfs_bad(pdf_paths: List[str]) -> List[dict]:
    results = []
    for pdf_path in pdf_paths:
        doc = fitz.open(pdf_path)  # No error handling!
        text = "".join(page.get_text() for page in doc)
        doc.close()
        results.append(parse_revenue_statement(text))
    return results
```

**Why this breaks:**
1. First corrupted PDF crashes entire upload
2. No per-file status tracking
3. No fallback for problematic files
4. Users lose all work if one file is bad

---

## Error Handling & Fallback

### DO: Structured Fallback Chain

```python
import fitz
import pdfplumber

def extract_with_fallback_chain(pdf_path: str) -> str:
    """Multi-stage extraction with detailed logging."""
    errors = []
    
    # Stage 1: PyMuPDF (primary)
    try:
        with fitz.open(pdf_path) as doc:
            text = "\n\n".join(page.get_text() for page in doc)
            if text.strip():
                logger.info(f"PyMuPDF success: {pdf_path}")
                return text
            errors.append("PyMuPDF: empty extraction")
    except Exception as e:
        errors.append(f"PyMuPDF: {e}")
    
    # Stage 2: pdfplumber (fallback)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
            if text.strip():
                logger.warning(f"Fallback to pdfplumber: {pdf_path}")
                return text
            errors.append("pdfplumber: empty extraction")
    except Exception as e:
        errors.append(f"pdfplumber: {e}")
    
    # Stage 3: Total failure
    error_msg = " | ".join(errors)
    logger.error(f"All extractors failed for {pdf_path}: {error_msg}")
    raise ValueError(f"Cannot extract text: {error_msg}")
```

**Why this works:**
1. Each extractor gets a fair attempt
2. Detailed logging shows exactly what failed
3. Empty extraction treated as failure (triggers fallback)
4. User gets informative error message if all fail

### DON'T: Silent Fallback Without Logging

```python
# BAD - No visibility into which extractor worked
def extract_silent_fallback(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    except:
        with pdfplumber.open(pdf_path) as pdf:
            return "".join(page.extract_text() or "" for page in pdf.pages)
```

**Why this breaks:**
1. No way to know if PyMuPDF is failing frequently
2. Can't detect degraded performance
3. Empty extractions from PyMuPDF don't trigger fallback
4. Debugging is impossible without logs

---

## Memory Management

### DO: Close Documents Explicitly or Use Context Managers

```python
# Pattern 1: Explicit close
def extract_explicit_close(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    try:
        text = "\n\n".join(page.get_text() for page in doc)
        return text
    finally:
        doc.close()  # Always closes, even on error

# Pattern 2: Context manager (preferred)
def extract_context_manager(pdf_path: str) -> str:
    with fitz.open(pdf_path) as doc:
        return "\n\n".join(page.get_text() for page in doc)
```

**Why this works:**
1. Prevents file descriptor leaks
2. Context manager is more concise
3. Memory released immediately after extraction
4. Safe for batch operations processing hundreds of PDFs

### DON'T: Forget to Close Documents

```python
# BAD - Memory leak, file descriptor leak
def extract_leak(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text = "".join(page.get_text() for page in doc)
    # Oops, forgot doc.close()!
    return text
```

**Why this breaks:**
1. File descriptors remain open until GC runs
2. Processing 100+ PDFs can exhaust system resources
3. In long-running FastAPI workers, memory usage grows unbounded
4. Cloud Run may OOM and restart the container

**When you'll be tempted:** Quick scripts, testing, or "it's just one file" scenarios. ALWAYS close documents.

---

## Common Pitfalls

### WARNING: Assuming Text Extraction Always Succeeds

**The Problem:**

```python
# BAD - No validation of extracted content
def extract_assume_success(pdf_path: str) -> str:
    with fitz.open(pdf_path) as doc:
        return "".join(page.get_text() for page in doc)
```

**Why this breaks:**
1. Scanned PDFs (images) return empty string
2. Password-protected PDFs return empty string
3. Corrupted PDFs might return garbage characters
4. Downstream parsers choke on empty/invalid input

**The fix:**

```python
# GOOD - Validate and fallback
def extract_with_validation(pdf_path: str) -> str:
    with fitz.open(pdf_path) as doc:
        text = "".join(page.get_text() for page in doc)
    
    if not text.strip():
        logger.warning(f"Empty PyMuPDF extraction: {pdf_path}")
        raise ValueError("No extractable text")
    
    if len(text.strip()) < 50:  # Suspiciously short
        logger.warning(f"Short extraction ({len(text)} chars): {pdf_path}")
    
    return text
```

**When you might be tempted:** Testing with known-good PDFs, assuming users upload clean files, tight deadlines.

---

### WARNING: Not Handling Page Iteration Errors

**The Problem:**

```python
# BAD - One bad page crashes entire extraction
def extract_fragile(pdf_path: str) -> str:
    with fitz.open(pdf_path) as doc:
        return "".join(page.get_text() for page in doc)  # Fails on first bad page
```

**Why this breaks:**
1. Corrupted page in 50-page PDF loses all 50 pages
2. No visibility into which page failed
3. Partial extraction is often better than total failure

**The fix:**

```python
# GOOD - Per-page error handling
def extract_robust(pdf_path: str) -> str:
    pages = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            try:
                text = page.get_text()
                if text.strip():
                    pages.append(text)
            except Exception as e:
                logger.warning(f"Failed to extract page {i} from {pdf_path}: {e}")
                pages.append(f"[PAGE {i} EXTRACTION FAILED]")
    
    if not pages:
        raise ValueError("No pages extracted successfully")
    
    return "\n\n".join(pages)
```

**When you might be tempted:** Simple PDFs, trusted sources, "good enough" extraction quality.