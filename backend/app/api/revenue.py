"""API routes for the Revenue tool."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.core.config import settings
from app.core.ingestion import file_response, persist_job_result
from app.models.revenue import (
    ExportRequest,
    ExportResponse,
    HealthResponse,
    UploadResponse,
)
from app.services.revenue.export_service import export_to_csv, generate_summary_report, to_mineral_csv
from app.services.revenue.format_detector import detect_format, get_parser_for_format
from app.services.revenue.pdf_extractor import (
    detect_garbled_text,
    extract_tables_pdfplumber,
    extract_text,
    extract_text_pymupdf,
    extract_text_pdfplumber,
    extract_structured_text,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for revenue tool."""
    return HealthResponse(status="healthy", service="revenue")


@router.post("/upload", response_model=UploadResponse)
async def upload_pdfs(request: Request, files: list[UploadFile] = File(...)):
    """Upload and process multiple PDF revenue statements."""
    statements = []
    errors = []
    total_rows = 0

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            errors.append(f"Invalid file type: {file.filename}. Only PDF files are accepted.")
            continue

        try:
            content = await file.read()

            text = extract_text(content)

            if not text or len(text.strip()) < 50:
                from app.services.revenue.pdf_extractor import is_ocr_available
                if is_ocr_available():
                    errors.append(
                        f"Could not extract text from {file.filename}. "
                        "OCR was attempted but could not read the document."
                    )
                else:
                    errors.append(
                        f"Could not extract text from {file.filename}. "
                        "This appears to be a scanned PDF. OCR is not available in this environment."
                    )
                continue

            # Try Gemini-first parsing when enabled
            statement = None
            if settings.use_gemini:
                try:
                    from app.services.revenue.gemini_revenue_parser import gemini_parse_revenue
                    statement = await gemini_parse_revenue(text, file.filename)
                except Exception as e:
                    logger.warning(f"Gemini parsing failed for {file.filename}, falling back to traditional: {e}")
                    statement = None

            # Traditional format-specific parsing (fallback or primary)
            if statement is None:
                format_type = detect_format(text)
                parser = get_parser_for_format(format_type)

                if parser is None:
                    errors.append(
                        f"Unknown statement format for {file.filename}. "
                        "Text was extracted but did not match EnergyLink, Enverus, "
                        "or Energy Transfer format."
                    )
                    continue

                # Enverus parser needs raw PDF bytes for positional extraction
                if parser == "enverus":
                    from app.services.revenue.enverus_parser import parse_enverus_statement
                    statement = parse_enverus_statement(content, file.filename)
                else:
                    statement = parser(text, file.filename)

            statements.append(statement)
            total_rows += len(statement.rows)

            for err in statement.errors:
                errors.append(f"{file.filename}: {err}")

        except Exception as e:
            errors.append(f"Error processing {file.filename}: {e!s}")

    result = UploadResponse(
        success=len(statements) > 0,
        statements=statements,
        total_rows=total_rows,
        errors=errors,
    )

    # Persist to Firestore (non-blocking)
    if statements:
        filenames = ", ".join(s.filename for s in statements)
        user_email = request.headers.get("x-user-email") or None
        user_name = request.headers.get("x-user-name") or None
        job_id = await persist_job_result(
            tool="revenue",
            filename=filenames,
            entries=[s.model_dump(mode="json") for s in statements],
            total=total_rows,
            success=total_rows,
            errors=len(errors),
            user_id=user_email,
            user_name=user_name,
        )
        if job_id:
            result.job_id = job_id

        # ETL pipeline disabled - will be replaced with Supabase

    return result


@router.post("/export/csv")
async def export_csv(request: ExportRequest):
    """Export extracted data to CRM mineral format CSV."""
    if not request.statements:
        raise HTTPException(status_code=400, detail="No statements provided for export")

    try:
        csv_bytes = to_mineral_csv(
            request.statements,
            county=request.county or "",
            campaign_name=request.campaign_name or "",
        )
        filename = f"revenue_mineral_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return file_response(csv_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e!s}") from e


@router.post("/export/json", response_model=ExportResponse)
async def export_json(request: ExportRequest):
    """Export extracted data to JSON format (for preview)."""
    if not request.statements:
        raise HTTPException(status_code=400, detail="No statements provided for export")

    try:
        csv_content, filename, row_count = export_to_csv(request.statements)
        return ExportResponse(
            success=True,
            filename=filename,
            content=csv_content,
            row_count=row_count,
            errors=[],
        )
    except Exception as e:
        return ExportResponse(success=False, errors=[str(e)])


@router.post("/summary")
async def get_summary(request: ExportRequest):
    """Get a summary report of the processed statements."""
    if not request.statements:
        raise HTTPException(status_code=400, detail="No statements provided")

    try:
        summary = generate_summary_report(request.statements)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {e!s}") from e


@router.post("/validate")
async def validate_statements(request: ExportRequest):
    """Validate extracted statements against M1 Upload schema."""
    from app.services.revenue.m1_transformer import transform_to_m1, validate_m1_row

    if not request.statements:
        raise HTTPException(status_code=400, detail="No statements provided")

    validation_errors = []
    valid_rows = 0
    invalid_rows = 0

    try:
        m1_rows = transform_to_m1(request.statements)

        for row in m1_rows:
            row_errors = validate_m1_row(row)
            if row_errors:
                invalid_rows += 1
                for err in row_errors:
                    validation_errors.append(f"Row {row.line_number}: {err}")
            else:
                valid_rows += 1

        return {
            "valid": invalid_rows == 0,
            "total_rows": len(m1_rows),
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "errors": validation_errors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {e!s}") from e


@router.post("/debug/extract-text")
async def debug_extract_text(file: UploadFile = File(...)):
    """Debug endpoint: show raw extracted text from each extraction method.

    Returns the raw text from PyMuPDF and pdfplumber side-by-side,
    plus garbled text analysis, table extraction, and structured text
    with position info, so we can diagnose parsing issues caused by
    PDF font encoding problems.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF files only")

    content = await file.read()
    result: dict = {"filename": file.filename, "size_bytes": len(content)}

    # PyMuPDF extraction
    try:
        pymupdf_text = extract_text_pymupdf(content)
        garbled = detect_garbled_text(pymupdf_text)
        result["pymupdf"] = {
            "success": True,
            "char_count": len(pymupdf_text),
            "text": pymupdf_text,
            "garbled_analysis": garbled,
        }
    except Exception as e:
        result["pymupdf"] = {"success": False, "error": str(e)}

    # pdfplumber text extraction
    try:
        pdfplumber_text = extract_text_pdfplumber(content)
        garbled = detect_garbled_text(pdfplumber_text)
        result["pdfplumber"] = {
            "success": True,
            "char_count": len(pdfplumber_text),
            "text": pdfplumber_text,
            "garbled_analysis": garbled,
        }
    except Exception as e:
        result["pdfplumber"] = {"success": False, "error": str(e)}

    # pdfplumber table extraction (different algorithm, may work better)
    try:
        tables = extract_tables_pdfplumber(content)
        result["pdfplumber_tables"] = {
            "success": True,
            "table_count": len(tables),
            "tables": tables,
        }
    except Exception as e:
        result["pdfplumber_tables"] = {"success": False, "error": str(e)}

    # Structured text with position info (PyMuPDF dict mode)
    try:
        structured = extract_structured_text(content)
        result["structured"] = structured
    except Exception as e:
        result["structured"] = {"error": str(e)}

    # Font analysis from PyMuPDF (helps identify encoding issues)
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        fonts_info = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            font_list = page.get_fonts(full=True)
            for font in font_list:
                fonts_info.append({
                    "page": page_num + 1,
                    "xref": font[0],
                    "ext": font[1],
                    "type": font[2],
                    "basefont": font[3],
                    "name": font[4],
                    "encoding": font[5] if len(font) > 5 else None,
                })
        doc.close()
        result["fonts"] = fonts_info
    except Exception as e:
        result["fonts"] = {"error": str(e)}

    # Format detection on the primary text
    pymupdf_score = result.get("pymupdf", {}).get("garbled_analysis", {}).get("score", 999)
    plumber_score = result.get("pdfplumber", {}).get("garbled_analysis", {}).get("score", 999)
    primary_text = (
        result.get("pdfplumber", {}).get("text")
        if plumber_score < pymupdf_score
        else result.get("pymupdf", {}).get("text")
    ) or ""
    if primary_text:
        result["detected_format"] = detect_format(primary_text).value

    # Recommendation
    if pymupdf_score == 0 and plumber_score == 0:
        result["recommendation"] = "Both extractors produce clean text."
    elif pymupdf_score <= plumber_score:
        result["recommendation"] = (
            f"PyMuPDF is cleaner (score {pymupdf_score} vs {plumber_score}). "
            "Using PyMuPDF for parsing."
        )
    else:
        result["recommendation"] = (
            f"pdfplumber is cleaner (score {plumber_score} vs {pymupdf_score}). "
            "Using pdfplumber for parsing."
        )

    return result
