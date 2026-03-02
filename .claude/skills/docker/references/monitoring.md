# Monitoring Reference

## Contents
- Health Checks
- Logging Strategies
- Error Tracking
- Performance Monitoring
- Debugging Production Issues

---

## Health Checks

### FastAPI Health Endpoint (backend/app/api/health.py)

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Cloud Run health check endpoint.
    Returns 200 if service is running.
    """
    return {
        "status": "healthy",
        "service": "table-rock-tools",
        "version": "1.0.0"
    }
```

**Cloud Run Configuration:**

```bash
gcloud run services update table-rock-tools \
  --platform managed \
  --region us-central1 \
  --port 8080  # Implicitly uses /api/health if app serves HTTP
```

**Testing:**

```bash
# Local
curl http://localhost:8000/api/health

# Production
curl https://tools.tablerocktx.com/api/health
```

---

### Advanced Health Check (with Dependencies)

```python
from fastapi import APIRouter, HTTPException
from app.services.firestore_service import firestore_client
from app.core.config import settings

router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Deep health check: verify critical dependencies.
    Returns 503 if any dependency is unhealthy.
    """
    checks = {
        "service": "healthy",
        "firestore": "unknown",
        "gcs": "unknown"
    }
    
    # Check Firestore
    try:
        if settings.firestore_enabled:
            db = firestore_client()
            db.collection("health_check").limit(1).get()
            checks["firestore"] = "healthy"
    except Exception as e:
        checks["firestore"] = f"unhealthy: {str(e)}"
    
    # Check GCS
    try:
        if settings.use_gcs:
            from app.services.storage_service import StorageService
            storage = StorageService()
            storage.storage_client.list_buckets(max_results=1)
            checks["gcs"] = "healthy"
    except Exception as e:
        checks["gcs"] = f"unhealthy: {str(e)}"
    
    # Return 503 if any critical service is down
    if "unhealthy" in str(checks):
        raise HTTPException(status_code=503, detail=checks)
    
    return checks
```

**Trade-off:** Deep health checks add 100-300ms latency. Only use if critical dependencies fail silently.

---

## Logging Strategies

### Cloud Run Automatic Logging

Cloud Run automatically captures:
- **stdout/stderr** → Cloud Logging
- **HTTP requests** → Request logs (path, status, latency)
- **Crashes** → Error reporting

**View logs:**

```bash
# Last 50 entries
gcloud run services logs read table-rock-tools --limit 50

# Stream live
gcloud run services logs tail table-rock-tools

# Filter by severity
gcloud run services logs read table-rock-tools \
  --log-filter="severity>=ERROR" \
  --limit 100
```

---

### Structured Logging (Best Practice)

**Current:** Uses Python `logging` with plaintext output

```python
import logging
logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_file(file: UploadFile):
    logger.info(f"Processing file: {file.filename}")  # Plaintext
```

**Better:** JSON structured logs (parseable by Cloud Logging)

```python
import json
import logging
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        return json.dumps(log_obj)

# Configure in main.py
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(handlers=[handler], level=logging.INFO)
```

**Why:** Structured logs enable filtering by custom fields in Cloud Logging console.

**Current State:** Table Rock Tools uses plaintext logging. Acceptable for low traffic but harder to query at scale.

---

## Error Tracking

### Unhandled Exceptions

**FastAPI default:** Returns 500 with generic error message

```python
# Current behavior
@router.post("/upload")
async def upload_file(file: UploadFile):
    result = process_pdf(file)  # If this crashes, FastAPI returns 500
    return result
```

**Better:** Log stack traces before returning user-friendly errors

```python
import logging
import traceback
from fastapi import HTTPException

logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_file(file: UploadFile):
    try:
        result = process_pdf(file)
        return result
    except Exception as e:
        logger.error(f"Upload failed: {file.filename}", exc_info=True)
        # Log full traceback to Cloud Logging
        raise HTTPException(
            status_code=500,
            detail="File processing failed. Please try again or contact support."
        )
```

**Why:** Users see friendly message, developers see full stack trace in logs.

---

### Error Aggregation (Not Implemented)

**Current:** Errors only visible in Cloud Logging (no aggregation)

**Best Practice:** Send errors to Sentry or Cloud Error Reporting

```python
# Install sentry-sdk
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://...",
    integrations=[FastApiIntegration()],
    environment="production",
    traces_sample_rate=0.1  # 10% performance monitoring
)
```

**Why:** Aggregates errors by type, sends alerts on spike, tracks error frequency.

**Current State:** No error aggregation. Errors only visible in Cloud Logging.

---

## Performance Monitoring

### Request Latency (Cloud Run Built-In)

Cloud Run automatically tracks:
- **Request duration** (P50, P95, P99)
- **Cold start frequency**
- **Instance count**

**View metrics:**

```bash
# Cloud Console
# Navigate to: Cloud Run → table-rock-tools → Metrics

# Or via gcloud (returns JSON)
gcloud run services describe table-rock-tools \
  --region us-central1 \
  --format "value(status.traffic)"
```

---

### Application-Level Tracing

**Current:** No distributed tracing

**Best Practice:** OpenTelemetry for request tracing

```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

# Initialize tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Export to Cloud Trace
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(CloudTraceSpanExporter())
)

# Auto-instrument FastAPI
FastAPIInstrumentor.instrument_app(app)
```

**Why:** Visualize request flow across services (FastAPI → Firestore → GCS).

**Current State:** No tracing. Performance debugging relies on logs + manual timing.

---

## Debugging Production Issues

### SSH into Cloud Run Container (NOT POSSIBLE)

Cloud Run containers are **ephemeral** and **stateless**. No SSH access.

**Debugging workflow:**

1. **Reproduce locally:**
```bash
docker build -t debug-image .
docker run -p 8080:8080 \
  -e ENVIRONMENT=production \
  -e FIRESTORE_ENABLED=true \
  debug-image
```

2. **Inspect logs:**
```bash
gcloud run services logs read table-rock-tools \
  --log-filter="severity>=ERROR" \
  --limit 100
```

3. **Deploy debug version:**
```python
# Add debug logging
logger.info(f"DEBUG: Request headers: {request.headers}")
logger.info(f"DEBUG: Environment: {os.environ}")
```

Push to `main`, wait 5 minutes for deployment, check logs.

---

### WARNING: No Log Retention Policy

**The Problem:**

Cloud Logging retains logs for **30 days by default**. After that, logs are deleted.

**Why This Breaks:**
1. **Compliance:** Can't investigate issues from 60 days ago
2. **Trend Analysis:** No historical data for performance regression
3. **Audit Trail:** Can't prove what happened months ago

**The Fix:**

Export logs to BigQuery for long-term retention:

```bash
# Create log sink
gcloud logging sinks create table-rock-logs-archive \
  bigquery.googleapis.com/projects/tablerockenergy/datasets/logs_archive \
  --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="table-rock-tools"'
```

**Current State:** Logs deleted after 30 days. Acceptable for internal tools but NOT for compliance-heavy industries.

---

### WARNING: No Alerting on Errors

**The Problem:**

Errors only visible by manually checking logs. No proactive notifications.

**Why This Breaks:**
1. **Delayed Response:** Bugs go unnoticed for hours/days
2. **User Impact:** Users hit errors repeatedly before developers notice
3. **No SLA Tracking:** Can't measure uptime/error rate

**The Fix:**

Create Cloud Monitoring alert:

```bash
gcloud alpha monitoring policies create \
  --notification-channels="projects/tablerockenergy/notificationChannels/12345" \
  --display-name="Cloud Run Error Rate" \
  --condition-display-name="Error rate > 5%" \
  --condition-threshold-value=5 \
  --condition-threshold-duration=300s \
  --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class="5xx"'
```

**Notification channels:** Email, Slack, PagerDuty

**Current State:** No alerting configured. Developers rely on users reporting issues.