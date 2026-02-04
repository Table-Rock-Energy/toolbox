"""API routes for the Revenue tool."""

from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.models.revenue import (
    ExportRequest,
    ExportResponse,
    HealthResponse,
    UploadResponse,
)
from app.services.revenue.export_service import export_to_csv, generate_summary_report
from app.services.revenue.format_detector import detect_format, get_parser_for_format
from app.services.revenue.pdf_extractor import extract_text

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for revenue tool."""
    return HealthResponse(status="healthy", service="revenue")


@router.post("/upload", response_model=UploadResponse)
async def upload_pdfs(files: List[UploadFile] = File(...)):
    """
    Upload and process multiple PDF revenue statements.

    Accepts multiple PDF files and returns extracted data for all statements.
    """
    statements = []
    errors = []
    total_rows = 0

    for file in files:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            errors.append(f"Invalid file type: {file.filename}. Only PDF files are accepted.")
            continue

        try:
            # Read file content
            content = await file.read()

            # Extract text from PDF
            text = extract_text(content)

            if not text or len(text.strip()) < 50:
                errors.append(f"Could not extract text from {file.filename}")
                continue

            # Detect format
            format_type = detect_format(text)

            # Get appropriate parser
            parser = get_parser_for_format(format_type)

            if parser is None:
                errors.append(
                    f"Unknown statement format for {file.filename}. "
                    "This may be a scanned/image-based PDF that requires OCR. "
                    "Supported formats: EnergyLink, Energy Transfer"
                )
                continue

            # Parse the statement
            statement = parser(text, file.filename)
            statements.append(statement)
            total_rows += len(statement.rows)

            # Add any parsing errors to the main errors list
            for err in statement.errors:
                errors.append(f"{file.filename}: {err}")

        except Exception as e:
            errors.append(f"Error processing {file.filename}: {str(e)}")

    return UploadResponse(
        success=len(statements) > 0,
        statements=statements,
        total_rows=total_rows,
        errors=errors
    )


@router.post("/export/csv")
async def export_csv(request: ExportRequest):
    """
    Export extracted data to M1 Upload CSV format.

    Accepts the extracted statements and returns a downloadable CSV file.
    """
    if not request.statements:
        raise HTTPException(status_code=400, detail="No statements provided for export")

    try:
        csv_content, filename, row_count = export_to_csv(request.statements)

        return Response(
            content=csv_content.encode("utf-8"),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Row-Count": str(row_count)
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/export/json", response_model=ExportResponse)
async def export_json(request: ExportRequest):
    """
    Export extracted data to JSON format (for preview).

    Returns the CSV content as a string in the response body.
    """
    if not request.statements:
        raise HTTPException(status_code=400, detail="No statements provided for export")

    try:
        csv_content, filename, row_count = export_to_csv(request.statements)

        return ExportResponse(
            success=True,
            filename=filename,
            content=csv_content,
            row_count=row_count,
            errors=[]
        )
    except Exception as e:
        return ExportResponse(
            success=False,
            errors=[str(e)]
        )


@router.post("/summary")
async def get_summary(request: ExportRequest):
    """
    Get a summary report of the processed statements.
    """
    if not request.statements:
        raise HTTPException(status_code=400, detail="No statements provided")

    try:
        summary = generate_summary_report(request.statements)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")


@router.post("/validate")
async def validate_statements(request: ExportRequest):
    """
    Validate extracted statements against M1 Upload schema.
    """
    from app.services.revenue.m1_transformer import transform_to_m1, validate_m1_row

    if not request.statements:
        raise HTTPException(status_code=400, detail="No statements provided")

    validation_errors = []
    valid_rows = 0
    invalid_rows = 0

    try:
        m1_rows = transform_to_m1(request.statements)

        for row in m1_rows:
            errors = validate_m1_row(row)
            if errors:
                invalid_rows += 1
                for err in errors:
                    validation_errors.append(f"Row {row.line_number}: {err}")
            else:
                valid_rows += 1

        return {
            "valid": invalid_rows == 0,
            "total_rows": len(m1_rows),
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "errors": validation_errors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
