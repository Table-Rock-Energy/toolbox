---
name: pymupdf
description: |
  Extracts text from PDFs as primary extraction method for party extraction and revenue processing.
  Use when: processing OCC Exhibit A PDFs, revenue statements, or any PDF text extraction before fallback to pdfplumber
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# PyMuPDF Skill

PyMuPDF (fitz) is the **primary** PDF text extraction library for this project. It handles OCC Exhibit A PDFs in the Extract tool and revenue statement PDFs in the Revenue tool. PDFPlumber serves as fallback only when PyMuPDF fails to extract text.

## Quick Start

### Basic Text Extraction

```python
import fitz  # PyMuPDF

# Open PDF and extract all text
doc = fitz.open(pdf_path)
full_text = ""
for page in doc:
    full_text += page.get_text()
doc.close()
```

### Page-by-Page Extraction (Extract Tool Pattern)

```python
import fitz

def extract_text_from_pdf(pdf_path: str) -> str:
    """Primary extraction method used in backend/app/services/extract/"""
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            text_parts.append(text)
        
        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed: {e}")
        # Fallback to pdfplumber
        return extract_with_pdfplumber(pdf_path)
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| `fitz.open()` | Opens PDF, returns Document object | `doc = fitz.open("path.pdf")` |
| `doc[page_num]` | Access page by index (0-based) | `page = doc[0]  # First page` |
| `page.get_text()` | Extract text from page | `text = page.get_text()` |
| `len(doc)` | Get total page count | `for i in range(len(doc)):` |
| `doc.close()` | Always close document | `doc.close()  # Prevent leaks` |

## Common Patterns

### Primary Extraction with Fallback (Current Architecture)

**When:** Processing any PDF upload (Extract or Revenue tools)

```python
import fitz
import pdfplumber

def extract_text(pdf_path: str) -> str:
    """Try PyMuPDF first, fallback to pdfplumber."""
    # Primary: PyMuPDF
    try:
        doc = fitz.open(pdf_path)
        text = "\n\n".join(page.get_text() for page in doc)
        doc.close()
        if text.strip():
            return text
    except Exception as e:
        logger.warning(f"PyMuPDF failed: {e}")
    
    # Fallback: pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        raise ValueError(f"Both extractors failed: {e}")
```

### Context Manager Pattern (Recommended)

**When:** Writing new extraction logic

```python
import fitz

def extract_with_context_manager(pdf_path: str) -> str:
    """Safer pattern - auto-closes document."""
    with fitz.open(pdf_path) as doc:
        return "\n\n".join(page.get_text() for page in doc)
```

### Extract Specific Pages

**When:** Processing multi-page PDFs where only certain pages matter

```python
def extract_pages(pdf_path: str, page_numbers: list[int]) -> str:
    """Extract text from specific pages (0-indexed)."""
    with fitz.open(pdf_path) as doc:
        pages = [doc[i].get_text() for i in page_numbers if i < len(doc)]
        return "\n\n".join(pages)
```

## See Also

- [patterns](references/patterns.md) - Extraction patterns, error handling, integration with storage
- [workflows](references/workflows.md) - Upload → extract → parse workflows for Extract and Revenue tools

## Related Skills

- **python** - Python service layer patterns
- **fastapi** - API endpoints that receive PDF uploads
- **pdfplumber** - Fallback extraction library
- **pandas** - Data processing after text extraction
- **pydantic** - Response models for extraction results

## Documentation Resources

> Fetch latest PyMuPDF documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "pymupdf"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** `/pymupdf/PyMuPDF` _(resolve using mcp__plugin_context7_context7__resolve-library-id, prefer /websites/ when available)_

**Recommended Queries:**
- "pymupdf text extraction methods"
- "pymupdf page iteration best practices"
- "pymupdf error handling patterns"