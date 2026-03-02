# Product Analytics Reference

## Contents
- Current Analytics State
- Event Tracking Patterns
- Journey Funnel Metrics
- Tool Usage Analytics
- Backend Performance Logging

---

## Current Analytics State

### WARNING: No Analytics Implementation

The Table Rock Tools application currently has **NO product analytics instrumentation**. No Mixpanel, Amplitude, Segment, or Google Analytics.

**Missing Metrics:**
- User activation rate (% who complete first extraction)
- Tool usage distribution (which tools are most popular)
- Drop-off points in upload → process → export flow
- RRC data download success rate
- Export format preferences (CSV vs Excel vs PDF)
- Session duration and repeat visit rate

**Recommendation:** Add PostHog (open-source, self-hosted option) or Mixpanel for SaaS analytics.

---

## Event Tracking Patterns

### Proposed Event Schema

**User Journey Events:**
```typescript
// utils/analytics.ts (to be created)
export enum AnalyticsEvent {
  // Auth
  USER_SIGNED_IN = 'user_signed_in',
  USER_SIGNED_OUT = 'user_signed_out',
  
  // Tool Usage
  TOOL_OPENED = 'tool_opened',
  FILE_UPLOADED = 'file_uploaded',
  PROCESSING_STARTED = 'processing_started',
  PROCESSING_COMPLETED = 'processing_completed',
  PROCESSING_FAILED = 'processing_failed',
  
  // Export
  EXPORT_STARTED = 'export_started',
  EXPORT_COMPLETED = 'export_completed',
  
  // RRC
  RRC_DOWNLOAD_STARTED = 'rrc_download_started',
  RRC_DOWNLOAD_COMPLETED = 'rrc_download_completed',
}

interface EventProperties {
  tool_name?: 'extract' | 'title' | 'proration' | 'revenue';
  file_type?: string;
  file_size_mb?: number;
  export_format?: 'csv' | 'excel' | 'pdf';
  error_type?: string;
  processing_duration_ms?: number;
}

export function trackEvent(event: AnalyticsEvent, properties?: EventProperties) {
  // Integration point for analytics provider
  if (window.analytics) {
    window.analytics.track(event, properties);
  }
  
  // Fallback: log to backend for later analysis
  fetch('/api/analytics/event', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({event, properties, timestamp: new Date().toISOString()}),
  }).catch(() => {
    // Silent fail - don't block user actions
  });
}
```

**Usage in components:**
```typescript
// pages/Extract.tsx
import { trackEvent, AnalyticsEvent } from '../utils/analytics';

const handleUpload = async (files: File[]) => {
  const file = files[0];
  
  trackEvent(AnalyticsEvent.FILE_UPLOADED, {
    tool_name: 'extract',
    file_type: file.type,
    file_size_mb: file.size / 1024 / 1024,
  });
  
  setIsProcessing(true);
  const startTime = Date.now();
  
  trackEvent(AnalyticsEvent.PROCESSING_STARTED, {tool_name: 'extract'});
  
  try {
    const result = await api.upload(file);
    const duration = Date.now() - startTime;
    
    trackEvent(AnalyticsEvent.PROCESSING_COMPLETED, {
      tool_name: 'extract',
      processing_duration_ms: duration,
    });
    
    setResults(result);
  } catch (err) {
    trackEvent(AnalyticsEvent.PROCESSING_FAILED, {
      tool_name: 'extract',
      error_type: err.message,
    });
    setError(err.message);
  } finally {
    setIsProcessing(false);
  }
};
```

---

## Journey Funnel Metrics

### Key Funnels to Track

**1. Extract Tool Funnel:**
```
Dashboard View (100%)
  ↓
Extract Tool Opened (?)
  ↓
File Uploaded (?)
  ↓
Processing Completed (?)
  ↓
Results Viewed (?)
  ↓
Export Downloaded (?)
```

**Implementation:**
```typescript
// pages/Extract.tsx
useEffect(() => {
  trackEvent(AnalyticsEvent.TOOL_OPENED, {tool_name: 'extract'});
}, []); // Track on mount

// Track each funnel step
const handleUpload = async (files: File[]) => {
  trackEvent(AnalyticsEvent.FILE_UPLOADED, {tool_name: 'extract'});
  // ... processing
};

const handleExport = async (format: 'csv' | 'excel') => {
  trackEvent(AnalyticsEvent.EXPORT_STARTED, {
    tool_name: 'extract',
    export_format: format,
  });
  
  // ... download logic
  
  trackEvent(AnalyticsEvent.EXPORT_COMPLETED, {
    tool_name: 'extract',
    export_format: format,
  });
};
```

**2. Proration RRC Setup Funnel:**
```
Proration Tool Opened (100%)
  ↓
RRC Data Status Checked (?)
  ↓
RRC Download Started (?)
  ↓
RRC Download Completed (?)
  ↓
CSV Uploaded (?)
  ↓
Calculations Completed (?)
```

**Why This Matters:** Identify where users drop off. If 80% start RRC download but only 20% complete, the 30-60s wait time needs progress indicators.

---

## Tool Usage Analytics

### Comparative Metrics

**Track relative tool popularity:**
```typescript
// Dashboard.tsx
const tools = ['extract', 'title', 'proration', 'revenue'];

tools.forEach(tool => {
  const button = document.querySelector(`[data-tool="${tool}"]`);
  button?.addEventListener('click', () => {
    trackEvent(AnalyticsEvent.TOOL_OPENED, {tool_name: tool});
  });
});
```

**Backend aggregation (proposed):**
```python
# backend/app/api/analytics.py (to be created)
from fastapi import APIRouter
from collections import Counter
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/analytics")

@router.get("/tool-usage")
async def get_tool_usage(days: int = 30):
    # Query Firestore for event logs
    events = firestore_service.get_events_since(
        datetime.now() - timedelta(days=days)
    )
    
    tool_opens = [
        e['properties']['tool_name'] 
        for e in events 
        if e['event'] == 'tool_opened'
    ]
    
    return {
        "period_days": days,
        "usage_by_tool": dict(Counter(tool_opens)),
        "total_sessions": len(tool_opens),
    }
```

**Dashboard visualization:**
```typescript
// pages/Dashboard.tsx
const [toolUsage, setToolUsage] = useState<Record<string, number>>({});

useEffect(() => {
  fetch('/api/analytics/tool-usage?days=30')
    .then(r => r.json())
    .then(data => setToolUsage(data.usage_by_tool));
}, []);

// Show usage badges on tool cards
<div className="text-sm text-gray-500">
  {toolUsage[tool.name] || 0} uses this month
</div>
```

**Why This Matters:** Product team can prioritize improvements based on actual usage, not assumptions.

---

## Backend Performance Logging

### Structured Logging for Analysis

**Current logging:**
```python
# backend/app/api/extract.py
logger = logging.getLogger(__name__)
logger.info("Processing PDF upload")
```

**GOOD - Structured logs for metrics:**
```python
# backend/app/api/extract.py
import time
from app.utils.logger import log_performance

@router.post("/upload")
async def upload_pdf(file: UploadFile):
    start = time.time()
    
    try:
        result = await extract_service.process_pdf(file)
        duration = time.time() - start
        
        log_performance({
            "event": "extract_pdf_success",
            "duration_seconds": duration,
            "file_size_mb": file.size / 1024 / 1024,
            "parties_found": len(result.entries),
        })
        
        return result
    except Exception as e:
        duration = time.time() - start
        
        log_performance({
            "event": "extract_pdf_failure",
            "duration_seconds": duration,
            "error_type": type(e).__name__,
            "error_message": str(e),
        })
        
        raise
```

**Logger utility:**
```python
# backend/app/utils/logger.py
import logging
import json

def log_performance(data: dict):
    """Log structured performance data for later analysis."""
    logger = logging.getLogger("performance")
    logger.info(json.dumps(data))  # JSON for easy parsing
```

**Analysis:**
```bash
# Extract all PDF processing times
grep "extract_pdf_success" logs/app.log | jq .duration_seconds | awk '{sum+=$1; count++} END {print "Avg:", sum/count, "Count:", count}'
```

**Why This Matters:** Identify slow operations (RRC download, large PDF processing) and optimize based on real data, not guesses.

---

## Common Analytics Anti-Patterns

### 1. Tracking Everything

**BAD - Event spam:**
```typescript
trackEvent('mouse_moved');
trackEvent('div_hovered');
trackEvent('button_focused');
```

**GOOD - Track meaningful milestones only:**
```typescript
trackEvent('processing_started');
trackEvent('processing_completed');
trackEvent('export_downloaded');
```

**Why This Breaks:** 10,000 meaningless events drown out the 10 important ones. Analytics dashboards become unusable.

### 2. No User Context

**BAD - Anonymous events:**
```typescript
trackEvent('file_uploaded');
```

**GOOD - Include user ID (if authenticated):**
```typescript
trackEvent('file_uploaded', {
  user_email: currentUser.email,
  tool_name: 'extract',
});
```

**Why This Breaks:** Can't calculate per-user metrics like retention, repeat usage, or power user behavior.

### 3. No Error Categorization

**BAD - Generic error tracking:**
```typescript
trackEvent('error', {message: err.toString()});
```

**GOOD - Categorize errors:**
```typescript
const errorCategory = err.status === 400 ? 'validation_error' 
  : err.status === 413 ? 'file_too_large'
  : err.status >= 500 ? 'server_error'
  : 'unknown_error';

trackEvent('processing_failed', {
  tool_name: 'extract',
  error_category: errorCategory,
  error_detail: err.message,
});
```

**Why This Breaks:** Can't prioritize fixes. "100 errors last week" means nothing without knowing if they're all the same issue.