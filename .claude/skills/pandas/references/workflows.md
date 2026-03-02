# Pandas Workflows Reference

## Contents
- CSV Upload → Processing → Export Workflow
- RRC Data Download and Sync Workflow
- Multi-File Processing Workflow
- Excel Report Generation Workflow
- Data Validation and Error Handling Workflow

---

## CSV Upload → Processing → Export Workflow

**Used in:** All four tools (Extract, Title, Proration, Revenue)

### Step-by-Step Pattern

```python
# 1. Route Handler (FastAPI)
# toolbox/backend/app/api/proration.py
from fastapi import UploadFile, HTTPException
import pandas as pd
from io import BytesIO

@router.post("/upload")
async def upload_mineral_holders(file: UploadFile):
    # Step 1: Read uploaded file
    contents = await file.read()
    
    try:
        df = pd.read_csv(
            BytesIO(contents),
            dtype=str,
            encoding='utf-8-sig'  # Handle Excel BOM
        )
    except Exception as e:
        raise HTTPException(400, f"Invalid CSV: {str(e)}")
    
    # Step 2: Validate schema
    required_cols = ['Mineral Holder', 'NRI', 'Gross Acres', 'Lease Number']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")
    
    # Step 3: Process rows
    results = []
    for _, row in df.iterrows():  # OK here - processing with external lookups
        result = await process_mineral_holder(row)
        results.append(result)
    
    # Step 4: Return structured data
    return {"entries": results, "total": len(results)}

# 2. Processing Service
async def process_mineral_holder(row: pd.Series) -> dict:
    """Process single row with RRC lookup"""
    # Query cached RRC data
    rrc_data = csv_processor.query_lease(
        lease_no=row['Lease Number'],
        district=row['District']
    )
    
    # Calculate NRA
    nra = calculate_nra(
        nri=float(row['NRI']),
        gross_acres=float(row['Gross Acres']),
        rrc_factor=rrc_data['FACTOR'].iloc[0] if not rrc_data.empty else 1.0
    )
    
    return {
        'mineral_holder': row['Mineral Holder'],
        'nri': float(row['NRI']),
        'gross_acres': float(row['Gross Acres']),
        'net_revenue_acres': nra
    }
```

### Export Workflow

```python
# 3. Export Route Handler
@router.post("/export/excel")
async def export_excel(request: ExportRequest):
    # Convert Pydantic models back to DataFrame
    df = pd.DataFrame([entry.model_dump() for entry in request.entries])
    
    # Generate Excel file
    buffer = create_excel_export(df)
    
    return StreamingResponse(
        buffer,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=proration_results.xlsx'}
    )

# 4. Export Service
def create_excel_export(df: pd.DataFrame) -> BytesIO:
    # Format currency columns
    df['net_revenue_acres'] = df['net_revenue_acres'].map('${:,.2f}'.format)
    
    # Create summary sheet
    summary = df.groupby('operator').agg({
        'net_revenue_acres': 'sum',
        'gross_acres': 'sum'
    }).reset_index()
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Detail', index=False)
        summary.to_excel(writer, sheet_name='Summary', index=False)
    
    buffer.seek(0)
    return buffer
```

**Checklist for CSV Upload Processing:**

```markdown
Copy this checklist and track progress:
- [ ] Route handler accepts UploadFile
- [ ] Read contents with await file.read()
- [ ] Parse CSV with pd.read_csv(BytesIO(contents), dtype=str, encoding='utf-8-sig')
- [ ] Validate required columns present
- [ ] Validate data types for numeric columns
- [ ] Process rows (with external lookups if needed)
- [ ] Return structured JSON response
- [ ] Implement export endpoint with pd.ExcelWriter
- [ ] Test with sample CSV containing BOM, special characters, missing columns
```

---

## RRC Data Download and Sync Workflow

**Used in:** Proration tool for monthly RRC lease data updates

### Complete RRC Sync Flow

```python
# 1. Download RRC CSV
# toolbox/backend/app/services/proration/rrc_data_service.py
import requests
from requests.adapters import HTTPAdapter

class RRCSSLAdapter(HTTPAdapter):
    """Custom SSL adapter for RRC's outdated SSL config"""
    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_version'] = ssl.PROTOCOL_TLS
        return super().init_poolmanager(*args, **kwargs)

async def download_rrc_data(well_type: str) -> str:
    """Download CSV from RRC website"""
    url = (
        'https://webapps2.rrc.texas.gov/EWA/oilProQueryAction.do'
        if well_type == 'OIL' else
        'https://webapps2.rrc.texas.gov/EWA/gasProQueryAction.do'
    )
    
    session = requests.Session()
    session.mount('https://', RRCSSLAdapter())
    
    response = session.get(url, verify=False, timeout=300)
    response.raise_for_status()
    
    # Save to storage (GCS or local)
    file_path = f'rrc-data/{well_type.lower()}_proration.csv'
    await storage_service.upload_file(file_path, response.content)
    
    return file_path

# 2. Load CSV into Memory
csv_file_path = await download_rrc_data('OIL')

# Download to local temp file
local_path = await storage_service.download_file(csv_file_path)

# Load into DataFrame with caching
csv_processor.load_csv(local_path, 'OIL')

# 3. Sync to Firestore
await sync_to_database(csv_file_path, 'OIL')

async def sync_to_database(csv_path: str, well_type: str) -> dict:
    """Sync CSV data to Firestore for persistence"""
    df = pd.read_csv(csv_path, dtype=str)
    
    # Convert to records
    records = df.to_dict('records')
    
    # Batch write to Firestore (500 docs per batch)
    from google.cloud import firestore
    db = firestore.Client()
    collection = db.collection(f'rrc_data_{well_type.lower()}')
    
    batch = db.batch()
    batch_count = 0
    
    for idx, record in enumerate(records):
        doc_ref = collection.document(f"{record['LEASE_NO']}_{record['DISTRICT']}")
        batch.set(doc_ref, record)
        batch_count += 1
        
        # Commit every 500 docs (Firestore limit)
        if batch_count >= 500:
            batch.commit()
            batch = db.batch()
            batch_count = 0
    
    # Commit remaining
    if batch_count > 0:
        batch.commit()
    
    return {"synced_count": len(records), "well_type": well_type}
```

### APScheduler Integration

```python
# toolbox/backend/app/main.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    # Schedule monthly RRC download (1st of month at 2 AM)
    scheduler.add_job(
        download_and_sync_rrc_data,
        'cron',
        day=1,
        hour=2,
        minute=0,
        id='rrc_monthly_sync'
    )
    scheduler.start()

async def download_and_sync_rrc_data():
    """Monthly RRC data sync"""
    for well_type in ['OIL', 'GAS']:
        try:
            csv_path = await download_rrc_data(well_type)
            await sync_to_database(csv_path, well_type)
            logger.info(f"Successfully synced {well_type} RRC data")
        except Exception as e:
            logger.error(f"Failed to sync {well_type} RRC data: {e}")
```

**RRC Sync Workflow Checklist:**

```markdown
Copy this checklist and track progress:
- [ ] Implement RRCSSLAdapter for outdated SSL
- [ ] Download CSV from RRC website with custom adapter
- [ ] Save to storage (GCS or local fallback)
- [ ] Load CSV into pandas with dtype=str
- [ ] Cache DataFrame in CSVProcessor for in-memory lookups
- [ ] Convert DataFrame to records with .to_dict('records')
- [ ] Batch write to Firestore (500 docs per commit)
- [ ] Update RRC data status in separate Firestore collection
- [ ] Configure APScheduler for monthly sync
- [ ] Test: Download → Cache → Firestore sync → Query lookup
```

---

## Multi-File Processing Workflow

**Used in:** Revenue tool (processes multiple revenue PDFs)

### Batch PDF Processing Pattern

```python
# toolbox/backend/app/api/revenue.py
from fastapi import UploadFile

@router.post("/upload")
async def upload_revenue_pdfs(files: list[UploadFile]):
    """Process multiple revenue PDFs, combine into single DataFrame"""
    all_statements = []
    
    for file in files:
        # Extract text from PDF
        text = await extract_pdf_text(file)
        
        # Parse revenue statements
        statements = parse_revenue_statements(text)
        all_statements.extend(statements)
    
    # Combine into single DataFrame
    df = pd.DataFrame(all_statements)
    
    # Transform to M1 format (29 columns)
    m1_df = transform_to_m1_format(df)
    
    return {
        "file_count": len(files),
        "statement_count": len(all_statements),
        "entries": m1_df.to_dict('records')
    }

def transform_to_m1_format(df: pd.DataFrame) -> pd.DataFrame:
    """Transform revenue statements to M1 CSV format"""
    m1_df = pd.DataFrame()
    
    # Map columns to M1 format
    m1_df['Property Number'] = df['well_number']
    m1_df['Owner Number'] = df['owner_id']
    m1_df['Revenue Month'] = pd.to_datetime(df['statement_date']).dt.strftime('%m/%Y')
    m1_df['Product Type'] = df['product'].map({'OIL': '01', 'GAS': '02'})
    # ... 25 more columns
    
    return m1_df
```

**Iterate-Until-Pass Validation:**

```markdown
1. Process all PDFs and combine into DataFrame
2. Validate M1 format:
   ```python
   validate_m1_columns(m1_df)
   validate_m1_data_types(m1_df)
   ```
3. If validation fails:
   - Review error messages
   - Fix data mapping in transform_to_m1_format()
   - Repeat step 2
4. Only proceed to export when validation passes
```

---

## Excel Report Generation Workflow

**Used in:** Title, Proration tools for consolidated reporting

### Multi-Sheet Report with Formatting

```python
# toolbox/backend/app/services/title/export_service.py
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

def create_title_report(owners: list[dict]) -> BytesIO:
    """Generate formatted Excel report with multiple sheets"""
    df = pd.DataFrame(owners)
    
    # Create summary by entity type
    entity_summary = df.groupby('entity_type').agg({
        'owner_name': 'count',
        'ownership_percent': 'sum'
    }).reset_index()
    entity_summary.columns = ['Entity Type', 'Count', 'Total Ownership %']
    
    # Detect duplicates
    duplicates = df[df.duplicated(subset=['owner_name'], keep=False)]
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Sheet 1: All owners
        df.to_excel(writer, sheet_name='All Owners', index=False)
        
        # Sheet 2: Entity summary
        entity_summary.to_excel(writer, sheet_name='Summary', index=False)
        
        # Sheet 3: Duplicates (if any)
        if not duplicates.empty:
            duplicates.to_excel(writer, sheet_name='Duplicates', index=False)
        
        # Format header rows
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for cell in worksheet[1]:  # Header row
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color='0e2431', end_color='0e2431', fill_type='solid')
                cell.font = Font(color='FFFFFF', bold=True)
                cell.alignment = Alignment(horizontal='center')
    
    buffer.seek(0)
    return buffer
```

**Report Generation Checklist:**

```markdown
Copy this checklist and track progress:
- [ ] Convert input data to pandas DataFrame
- [ ] Generate summary sheets with groupby/agg
- [ ] Identify data quality issues (duplicates, missing values)
- [ ] Create BytesIO buffer for in-memory Excel file
- [ ] Use pd.ExcelWriter with engine='openpyxl'
- [ ] Write multiple sheets (detail, summary, issues)
- [ ] Apply header formatting (bold, background color)
- [ ] Freeze header rows with freeze_panes=(1, 0)
- [ ] Reset buffer position with buffer.seek(0)
- [ ] Return StreamingResponse with correct MIME type
```

---

## Data Validation and Error Handling Workflow

**Used in:** All tools for robust CSV/Excel processing

### Comprehensive Validation Pattern

```python
# toolbox/backend/app/services/validation_service.py
import pandas as pd
from fastapi import HTTPException

class DataValidator:
    @staticmethod
    def validate_required_columns(df: pd.DataFrame, required: list[str]) -> None:
        """Validate required columns exist"""
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required columns",
                    "missing_columns": missing,
                    "found_columns": list(df.columns),
                    "suggestion": "Ensure CSV has correct headers"
                }
            )
    
    @staticmethod
    def validate_numeric_columns(df: pd.DataFrame, numeric_cols: list[str]) -> None:
        """Validate columns contain numeric values"""
        errors = {}
        
        for col in numeric_cols:
            if col not in df.columns:
                continue
            
            # Try to convert to numeric
            numeric_series = pd.to_numeric(df[col], errors='coerce')
            invalid_mask = numeric_series.isna() & df[col].notna()
            
            if invalid_mask.any():
                invalid_values = df.loc[invalid_mask, col].unique()[:5]
                errors[col] = {
                    "invalid_count": invalid_mask.sum(),
                    "examples": list(invalid_values)
                }
        
        if errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid numeric values",
                    "columns": errors
                }
            )
    
    @staticmethod
    def validate_not_empty(df: pd.DataFrame) -> None:
        """Validate DataFrame is not empty"""
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="CSV file is empty or contains only headers"
            )

# Usage in route handler
@router.post("/upload")
async def upload_csv(file: UploadFile):
    df = pd.read_csv(BytesIO(await file.read()), dtype=str)
    
    # Validate step-by-step
    DataValidator.validate_not_empty(df)
    DataValidator.validate_required_columns(df, ['Name', 'NRI', 'Acres'])
    DataValidator.validate_numeric_columns(df, ['NRI', 'Acres'])
    
    # Proceed with processing...
```

**Validation Iterate-Until-Pass Pattern:**

```markdown
1. Upload CSV file
2. Run validation suite:
   - validate_not_empty()
   - validate_required_columns()
   - validate_numeric_columns()
3. If validation fails:
   - Review HTTPException detail (shows specific errors)
   - Fix CSV file based on error messages
   - Re-upload and repeat step 2
4. Only proceed to processing when all validations pass
5. Log successful validation for audit trail