# Services Reference

## Contents
- Service Layer Architecture
- Storage Service with GCS Fallback
- Lazy Client Initialization
- Helper Class Pattern
- RRC Data Service

## Service Layer Architecture

### Tool-Specific Service Organization

```
toolbox/backend/app/services/
├── extract/               # 6 files: pdf_extractor, parser, name_parser, address_parser, export_service
├── title/                 # 6 files: excel_processor, csv_processor, entity_detector, name_parser, export_service
├── proration/             # 8 files: rrc_data_service, csv_processor, calculation_service, legal_description_parser, export_service
├── revenue/               # 6 files: pdf_extractor, format_detector, energylink_parser, m1_transformer, export_service
├── storage_service.py     # GCS + local fallback
├── firestore_service.py   # Firestore async client + operations
└── db_service.py          # PostgreSQL (optional, disabled by default)
```

**WHY:** Each tool gets isolated service logic, shared infrastructure (storage, DB) in root services. Service files use `{domain}_service.py` or `{type}_parser.py` naming.

### DO: Keep Routes Thin, Services Fat

```python
# GOOD - Route delegates to service
# toolbox/backend/app/api/extract.py
@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile) -> UploadResponse:
    file_bytes = await file.read()
    
    # All logic in service layer
    full_text = extract_text_from_pdf(file_bytes)
    party_text = extract_party_list(full_text)
    entries = parse_exhibit_a(party_text)
    
    return UploadResponse(
        message=f"Extracted {len(entries)} entries",
        result=ExtractionResult(success=True, entries=entries)
    )

# GOOD - Service handles complex logic
# toolbox/backend/app/services/extract/pdf_extractor.py
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF (primary) or PDFPlumber (fallback)."""
    try:
        # Try PyMuPDF first (faster)
        return _extract_with_pymupdf(file_bytes)
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed: {e}, trying PDFPlumber")
        return _extract_with_pdfplumber(file_bytes)
```

**WHY:** Routes are testable without real PDFs, business logic reusable across endpoints (e.g., debugging endpoint uses same parser).

### DON'T: Put Business Logic in Routes

```python
# BAD - Complex logic in route
@router.post("/upload")
async def upload_pdf(file: UploadFile):
    file_bytes = await file.read()
    
    # WRONG: Extraction logic here
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    
    # WRONG: Parsing logic here
    pattern = re.compile(r"^(\d+)\.\s+(.+)$", re.MULTILINE)
    matches = pattern.findall(text)
    entries = [{"number": m[0], "name": m[1]} for m in matches]
    
    return {"entries": entries}
```

**WHY THIS BREAKS:** Can't test extraction without UploadFile mocks, can't reuse logic for debugging endpoint, can't swap PDF libraries without touching routes.

## Storage Service with GCS Fallback

### Transparent Fallback Pattern

```python
# toolbox/backend/app/services/storage_service.py
class StorageService:
    def upload_file(self, content: bytes | BinaryIO, path: str, content_type: str) -> str:
        """Upload to GCS, fall back to local if GCS unavailable."""
        if self.is_gcs_enabled:
            try:
                return self._upload_to_gcs(content, path, content_type)
            except Exception as e:
                logger.warning(f"GCS upload failed, falling back to local: {e}")
                if hasattr(content, 'seek'):
                    content.seek(0)  # Reset stream position
                return self._upload_to_local(content, path)
        else:
            return self._upload_to_local(content, path)
    
    def download_file(self, path: str) -> bytes | None:
        """Download from GCS, fall back to local."""
        if self.is_gcs_enabled:
            result = self._download_from_gcs(path)
            if result is not None:
                return result
            # Fallback: check local in case file was saved locally
            return self._download_from_local(path)
        else:
            return self._download_from_local(path)
```

**WHY:** Works in dev without GCP credentials, seamlessly switches to GCS in production. Service layer doesn't know/care where files are stored.

**WARNING: GCS get_signed_url() Returns None**

```python
# toolbox/backend/app/services/storage_service.py
def get_signed_url(self, path: str, expiration_minutes: int = 60) -> str | None:
    """Get signed URL for temporary access. Only available with GCS."""
    if not self.is_gcs_enabled:
        return None  # IMPORTANT: Not available for local storage
    
    try:
        blob = self._bucket.blob(path)
        if not blob.exists():
            return None
        
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )
    except Exception as e:
        logger.error(f"Error generating signed URL: {e}")
        return None
```

**WHY THIS BREAKS:** Code that assumes signed URLs will always work crashes when GCS is unavailable.

**THE FIX:**

```python
# GOOD - Always provide fallback URL
# toolbox/backend/app/services/storage_service.py (ProfileStorage helper)
def get_profile_image_url(self, user_id: str) -> str | None:
    """Get URL for profile image. Always returns API proxy endpoint."""
    for ext in ["jpg", "jpeg", "png", "gif"]:
        path = f"{self.folder}/{user_id}/avatar.{ext}"
        if self.storage.file_exists(path):
            # Always use API endpoint (proxies from GCS or local)
            # Avoids GCS signed URL issues on Cloud Run
            return f"/api/admin/profile-image/{user_id}"
    return None

# GOOD - API proxies image from storage
# toolbox/backend/app/api/admin.py
@router.get("/profile-image/{user_id}")
async def get_profile_image(user_id: str):
    for ext in ["jpg", "jpeg", "png", "gif"]:
        path = f"{settings.gcs_profiles_folder}/{user_id}/avatar.{ext}"
        content = storage_service.download_file(path)
        if content:
            return Response(
                content=content,
                media_type=f"image/{ext}",
                headers={"Cache-Control": "public, max-age=3600"}
            )
    raise HTTPException(status_code=404, detail="Profile image not found")
```

## Lazy Client Initialization

### Avoiding Startup Crashes

```python
# toolbox/backend/app/services/storage_service.py
class StorageService:
    def __init__(self):
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None
        self._initialized = False
    
    def _init_client(self) -> bool:
        """Initialize GCS client lazily."""
        if self._initialized:
            return self._client is not None
        
        self._initialized = True
        
        if not GCS_AVAILABLE:
            logger.info("GCS not available, using local storage")
            return False
        
        if not settings.use_gcs:
            logger.info("GCS not configured, using local storage")
            return False
        
        try:
            self._client = storage.Client(project=settings.gcs_project_id)
            self._bucket = self._client.bucket(settings.gcs_bucket_name)
            
            if not self._bucket.exists():
                self._bucket = self._client.create_bucket(
                    settings.gcs_bucket_name,
                    location="us-central1"
                )
            
            logger.info(f"GCS initialized: {settings.gcs_bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize GCS: {e}")
            self._client = None
            self._bucket = None
            return False
    
    @property
    def is_gcs_enabled(self) -> bool:
        """Check if GCS is available."""
        return self._init_client()
```

**WHY:** App starts even without GCP credentials (dev mode), defers auth errors until first actual GCS operation.

### DO: Use Property for Lazy Init Check

```python
# GOOD - Property triggers lazy init
@property
def is_gcs_enabled(self) -> bool:
    return self._init_client()

# Usage
if self.is_gcs_enabled:
    return self._upload_to_gcs(content, path)
```

### DON'T: Initialize Clients at Import Time

```python
# BAD - Crashes on import if GCS credentials missing
from google.cloud import storage

client = storage.Client()  # WRONG - fails at import time
bucket = client.bucket("my-bucket")
```

**WHY THIS BREAKS:** App won't start in local dev without GCP credentials, can't unit test without mocking global state.

## Helper Class Pattern

### Specialized Storage Helpers

```python
# toolbox/backend/app/services/storage_service.py
class RRCDataStorage:
    """Helper for RRC proration data storage."""
    
    def __init__(self, storage: StorageService):
        self.storage = storage
        self.folder = settings.gcs_rrc_data_folder
    
    @property
    def oil_path(self) -> str:
        return f"{self.folder}/oil_proration.csv"
    
    @property
    def gas_path(self) -> str:
        return f"{self.folder}/gas_proration.csv"
    
    def save_oil_data(self, content: bytes) -> str:
        return self.storage.upload_file(content, self.oil_path, "text/csv")
    
    def get_status(self) -> dict:
        oil_info = self.storage.get_file_info(self.oil_path)
        gas_info = self.storage.get_file_info(self.gas_path)
        return {
            "oil_available": oil_info is not None,
            "gas_available": gas_info is not None,
            "storage_type": "gcs" if self.storage.is_gcs_enabled else "local"
        }

# Global instances
storage_service = StorageService()
rrc_storage = RRCDataStorage(storage_service)
upload_storage = UploadStorage(storage_service)
profile_storage = ProfileStorage(storage_service)
```

**WHY:** Encapsulates domain-specific paths/logic, DRY for common operations, easy to mock in tests.

### DO: Use Type Hints for Binary Content

```python
# GOOD - Accepts both bytes and file-like objects
def upload_file(self, content: bytes | BinaryIO, path: str) -> str:
    if isinstance(content, bytes):
        local_path.write_bytes(content)
    else:
        local_path.write_bytes(content.read())
```

## RRC Data Service

### Custom SSL Adapter for Legacy API

```python
# toolbox/backend/app/services/proration/rrc_data_service.py
class RRCSSLAdapter(HTTPAdapter):
    """Custom SSL adapter for RRC website (outdated SSL config)."""
    
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)

class RRCDataService:
    def _create_session(self) -> requests.Session:
        """Create session with custom SSL adapter."""
        session = requests.Session()
        session.mount("https://", RRCSSLAdapter())
        return session
```

**WHY:** RRC website uses outdated SSL/TLS config that modern Python rejects. Custom adapter enables legacy ciphers.

**WARNING:** Only use `verify=False` for specific known legacy APIs. NEVER disable SSL verification globally.