# PyMuPDF Workflows Reference

## Contents
- Extract Tool Upload Workflow
- Revenue Tool Batch Processing
- Storage Integration Workflow
- Testing PDF Extraction
- Debugging Failed Extractions

---

## Extract Tool Upload Workflow

**Workflow:** User uploads OCC Exhibit A PDF → Extract parties → Display in table → Export to CSV/Excel

### End-to-End Flow

```
1. Frontend: POST /api/extract/upload (PDF file)
   ↓
2. FastAPI: backend/app/api/extract.py validates file
   ↓
3. StorageService: Upload PDF to GCS (or local fallback)
   ↓
4. PDFExtractor (PyMuPDF): Extract text from uploaded file
   ↓
5. PartyParser: Parse parties from extracted text
   ↓
6. FastAPI: Return PartyEntry[] JSON response
   ↓
7. Frontend: Display in DataTable, allow filtering/export
```

### Code Path

```python
# Step 1: API endpoint receives upload
# backend/app/api/extract.py
from app.services.extract.pdf_extractor import extract_text_from_pdf
from app.services.extract.party_parser import parse_parties
from app.services.storage_service import storage_service

@router.post("/upload")
async def upload_exhibit_a(file: UploadFile):
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    # Step 2: Save to storage
    file_path = await storage_service.upload_file(
        file.file,
        f"uploads/{file.filename}"
    )
    
    # Step 3: Extract text with PyMuPDF
    try:
        text = extract_text_from_pdf(file_path)
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(500, f"Cannot extract text: {e}")
    
    # Step 4: Parse parties
    parties = parse_parties(text)
    
    return {"parties": parties, "file": file.filename}
```

```python
# Step 3 implementation: PDF extraction
# backend/app/services/extract/pdf_extractor.py
import fitz
import pdfplumber

def extract_text_from_pdf(pdf_path: str) -> str:
    """Primary extraction with PyMuPDF."""
    # Try PyMuPDF first
    try:
        with fitz.open(pdf_path) as doc:
            pages = [page.get_text() for page in doc]
            text = "\n\n".join(pages)
            
            if text.strip():
                logger.info(f"PyMuPDF extracted {len(text)} chars")
                return text
            
            logger.warning("PyMuPDF returned empty text")
    except Exception as e:
        logger.warning(f"PyMuPDF failed: {e}")
    
    # Fallback to pdfplumber
    logger.info("Falling back to pdfplumber")
    return extract_with_pdfplumber(pdf_path)
```

### Workflow Checklist

Copy this checklist when implementing PDF upload:

- [ ] Validate file extension (.pdf only)
- [ ] Upload to StorageService (GCS or local)
- [ ] Extract text with PyMuPDF primary, pdfplumber fallback
- [ ] Validate extracted text is non-empty
- [ ] Parse extracted text into structured data
- [ ] Return structured JSON response
- [ ] Log extraction method used (PyMuPDF vs pdfplumber)
- [ ] Handle both extraction failures with HTTPException 500

---

## Revenue Tool Batch Processing

**Workflow:** User uploads multiple revenue PDFs → Extract from each → Parse into M1 rows → Export to CSV

### Batch Processing Pattern

```python
# backend/app/api/revenue.py
from typing import List
from app.services.revenue.pdf_processor import process_revenue_pdfs

@router.post("/upload")
async def upload_revenue_statements(files: List[UploadFile]):
    """Process multiple revenue PDFs in one upload."""
    if not files:
        raise HTTPException(400, "No files provided")
    
    # Upload all files to storage
    uploaded_paths = []
    for file in files:
        if not file.filename.endswith('.pdf'):
            logger.warning(f"Skipping non-PDF: {file.filename}")
            continue
        
        path = await storage_service.upload_file(
            file.file,
            f"revenue/{file.filename}"
        )
        uploaded_paths.append((file.filename, path))
    
    # Process each PDF independently
    results = []
    for filename, path in uploaded_paths:
        try:
            text = extract_text_from_pdf(path)  # PyMuPDF + fallback
            statement = parse_revenue_statement(text)
            results.append({
                "file": filename,
                "status": "success",
                "data": statement
            })
        except Exception as e:
            logger.error(f"Failed {filename}: {e}")
            results.append({
                "file": filename,
                "status": "error",
                "error": str(e)
            })
    
    return {"results": results}
```

### Iterate-Until-Pass Pattern

**Scenario:** Batch upload where some PDFs might fail extraction.

1. Upload all files to storage first
2. For each file:
   - Try PyMuPDF extraction
   - If PyMuPDF returns empty, try pdfplumber
   - If both fail, mark file as error and continue
3. Return mixed success/error results to user
4. User fixes problematic PDFs and re-uploads only failed files

```python
# Iterate pattern example
def process_with_retry_tracking(pdf_paths: List[str]) -> dict:
    """Track failures for user-driven retry."""
    successes = []
    failures = []
    
    for pdf_path in pdf_paths:
        try:
            text = extract_text_from_pdf(pdf_path)  # Auto-fallback
            parsed = parse_revenue_statement(text)
            successes.append({"file": pdf_path, "data": parsed})
        except Exception as e:
            failures.append({"file": pdf_path, "error": str(e)})
    
    return {
        "success_count": len(successes),
        "failure_count": len(failures),
        "successes": successes,
        "failures": failures  # User can retry these specific files
    }
```

### Batch Workflow Checklist

- [ ] Validate all files before processing any
- [ ] Upload all files to storage first (fail fast if storage unavailable)
- [ ] Process each file independently (one failure != batch failure)
- [ ] Track per-file success/error status
- [ ] Use PyMuPDF + pdfplumber fallback per file
- [ ] Return detailed results with file-level status
- [ ] Log extraction method per file
- [ ] Allow user to retry failed files without re-uploading successes

---

## Storage Integration Workflow

**Workflow:** Upload PDF to GCS → Download for extraction → Clean up temporary files

### GCS Upload → PyMuPDF Extraction

```python
# backend/app/services/storage_service.py integration
from app.services.storage_service import storage_service

async def process_uploaded_pdf(file: UploadFile) -> dict:
    """Upload to GCS, extract with PyMuPDF, parse."""
    # Step 1: Upload to GCS (or local fallback)
    remote_path = f"uploads/{file.filename}"
    uploaded_path = await storage_service.upload_file(file.file, remote_path)
    
    # Step 2: For local processing, download if in GCS
    if storage_service.is_gcs_file(uploaded_path):
        local_path = f"/tmp/{file.filename}"
        await storage_service.download_file(uploaded_path, local_path)
        processing_path = local_path
    else:
        processing_path = uploaded_path
    
    # Step 3: Extract with PyMuPDF
    try:
        text = extract_text_from_pdf(processing_path)
        parties = parse_parties(text)
        
        return {"status": "success", "parties": parties}
    finally:
        # Step 4: Clean up temp files
        if processing_path.startswith("/tmp/"):
            os.remove(processing_path)
```

### Local Filesystem Fallback

```python
# When GCS unavailable, storage_service uses local backend/data/
def extract_with_storage_fallback(file: UploadFile) -> str:
    """Handle both GCS and local storage paths."""
    # StorageService auto-detects GCS vs local
    remote_path = await storage_service.upload_file(
        file.file,
        f"uploads/{file.filename}"
    )
    
    # Path works for both GCS and local
    # If GCS: backend/data/uploads/file.pdf
    # If local: backend/data/uploads/file.pdf
    text = extract_text_from_pdf(remote_path)
    return text
```

**Why this works:**
1. StorageService abstracts GCS vs local
2. PyMuPDF works with local file paths only
3. No special handling needed - StorageService handles fallback
4. Development works without GCS credentials

---

## Testing PDF Extraction

### Unit Test Pattern

```python
# backend/tests/test_pdf_extraction.py
import pytest
from app.services.extract.pdf_extractor import extract_text_from_pdf

def test_pymupdf_extraction_success(tmp_path):
    """Test PyMuPDF extracts text from valid PDF."""
    # Create a simple test PDF (requires reportlab)
    from reportlab.pdfgen import canvas
    
    pdf_path = tmp_path / "test.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Test party: John Doe")
    c.save()
    
    # Extract
    text = extract_text_from_pdf(str(pdf_path))
    
    # Assert
    assert "John Doe" in text
    assert len(text) > 0

def test_pymupdf_fallback_to_pdfplumber():
    """Test fallback when PyMuPDF fails."""
    # Use a known-problematic PDF or mock fitz.open to raise exception
    with patch('fitz.open', side_effect=Exception("PyMuPDF error")):
        text = extract_text_from_pdf("test.pdf")
        # Should fall back to pdfplumber
        assert text is not None  # Fallback succeeded
```

### Integration Test with FastAPI

```python
# backend/tests/test_extract_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_upload_pdf_extract_parties():
    """Test full upload → extract → parse flow."""
    with open("tests/fixtures/exhibit_a.pdf", "rb") as f:
        response = client.post(
            "/api/extract/upload",
            files={"file": ("exhibit_a.pdf", f, "application/pdf")}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "parties" in data
    assert len(data["parties"]) > 0
```

### Testing Checklist

- [ ] Create fixture PDFs with known content (reportlab)
- [ ] Test successful PyMuPDF extraction
- [ ] Test fallback when PyMuPDF fails (mock or bad PDF)
- [ ] Test empty PDF handling
- [ ] Test batch processing with mixed success/failure
- [ ] Test storage integration (upload → download → extract)
- [ ] Test API endpoint with real HTTP upload

---

## Debugging Failed Extractions

### Diagnostic Workflow

When PyMuPDF extraction fails or returns garbage:

1. **Check logs** for extraction method used:
   ```
   INFO: PyMuPDF extracted 1234 chars
   vs
   WARNING: Falling back to pdfplumber
   ```

2. **Manually test extraction**:
   ```python
   import fitz
   
   doc = fitz.open("problematic.pdf")
   print(f"Pages: {len(doc)}")
   
   for i, page in enumerate(doc):
       text = page.get_text()
       print(f"Page {i}: {len(text)} chars")
       print(text[:200])  # First 200 chars
   ```

3. **Check if PDF is image-based**:
   ```python
   page = doc[0]
   images = page.get_images()
   print(f"Images on page: {len(images)}")
   # If many images and no text → scanned PDF, needs OCR
   ```

4. **Compare with pdfplumber**:
   ```python
   import pdfplumber
   
   with pdfplumber.open("problematic.pdf") as pdf:
       text = pdf.pages[0].extract_text()
       print(f"pdfplumber: {len(text)} chars")
   ```

5. **Validate** against expected patterns:
   ```python
   # For OCC Exhibit A, should contain party indicators
   if not any(keyword in text.lower() for keyword in ['grantor', 'grantee', 'lessor', 'lessee']):
       logger.warning("PDF missing expected party keywords")
   ```

### Debug Checklist

- [ ] Check CloudWatch/logs for extraction method (PyMuPDF vs pdfplumber)
- [ ] Manually extract with PyMuPDF in Python REPL
- [ ] Check page count and per-page text length
- [ ] Look for images (scanned PDFs need OCR, not text extraction)
- [ ] Compare PyMuPDF vs pdfplumber output
- [ ] Validate extracted text contains expected patterns
- [ ] If scanned: consider adding OCR (pytesseract) as third fallback
- [ ] Test with known-good PDF to isolate PDF issue vs code bug