# Product Analytics Reference

## Contents
- Event Schema Design
- Usage Event Capture
- Funnel Analysis
- Admin Analytics Dashboard
- Privacy Considerations

---

## Event Schema Design

**Keep it simple.** For internal tools, you don't need Segment/Mixpanel. Store events in Firestore.

### Core Schema

```python
# models/analytics.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class UsageEvent(BaseModel):
    """Usage event for product analytics."""
    user_email: str = Field(..., description="User who performed action")
    tool: Literal["extract", "title", "proration", "revenue", "ghl_prep"] = Field(..., description="Tool name")
    action: Literal["upload", "export", "view", "calculate", "delete"] = Field(..., description="Action type")
    metadata: dict = Field(default_factory=dict, description="Additional context (file size, record count, etc.)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: str | None = Field(None, description="Browser session ID for grouping")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

### Firestore Collection Structure

```
usage_events/
  {event_id}/
    user_email: "james@tablerocktx.com"
    tool: "extract"
    action: "upload"
    metadata:
      filename: "exhibit_a_2024.pdf"
      file_size_kb: 1024
      parties_found: 47
    timestamp: "2026-02-09T14:30:00Z"
    session_id: "a3f8d9e1-..."
```

---

## Usage Event Capture

### Backend: Track in API Routes

```python
# api/extract.py
from app.services import firestore_service as db
from app.core.auth import get_current_user_email

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_email)
):
    # Process document
    result = await extract_service.process_pdf(file)
    
    # Track usage event
    await db.track_tool_usage(
        user_email=current_user,
        tool="extract",
        action="upload",
        metadata={
            "filename": file.filename,
            "file_size_kb": file.size // 1024,
            "parties_found": len(result.entries),
            "processing_time_seconds": result.processing_time,
        }
    )
    
    return result


@router.post("/export/excel")
async def export_excel(
    entries: list[PartyEntry],
    current_user: str = Depends(get_current_user_email)
):
    # Generate Excel file
    excel_bytes = await export_service.to_excel(entries)
    
    # Track export event
    await db.track_tool_usage(
        user_email=current_user,
        tool="extract",
        action="export",
        metadata={
            "format": "excel",
            "record_count": len(entries),
        }
    )
    
    return Response(content=excel_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
```

### Firestore Service Implementation

```python
# services/firestore_service.py
async def track_tool_usage(
    user_email: str,
    tool: str,
    action: str,
    metadata: dict | None = None,
    session_id: str | None = None
):
    """Log usage event to Firestore."""
    if not settings.firestore_enabled:
        logger.warning("Firestore disabled, skipping usage tracking")
        return
    
    db = get_firestore_client()
    
    event = {
        "user_email": user_email,
        "tool": tool,
        "action": action,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow(),
        "session_id": session_id,
    }
    
    try:
        await db.collection("usage_events").add(event)
        logger.debug(f"Tracked event: {tool}.{action} by {user_email}")
    except Exception as e:
        # Don't fail requests if tracking fails
        logger.error(f"Failed to track usage event: {e}")
```

### Frontend: Track Client-Side Events

For interactions that don't hit the backend (e.g., clicking help links, dismissing modals):

```tsx
// utils/analytics.ts
export async function trackClientEvent(
  action: string,
  metadata?: Record<string, unknown>
) {
  const sessionId = sessionStorage.getItem('session_id') || crypto.randomUUID();
  sessionStorage.setItem('session_id', sessionId);
  
  try {
    await fetch('/api/analytics/client-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        metadata,
        session_id: sessionId,
        url: window.location.pathname,
      }),
    });
  } catch (error) {
    // Silent failure - don't block UI
    console.warn('Analytics tracking failed:', error);
  }
}

// Usage:
import { trackClientEvent } from '@/utils/analytics';

// Help.tsx
const handleFaqClick = (faqId: string) => {
  trackClientEvent('faq_clicked', { faq_id: faqId });
  setExpandedFaq(faqId);
};
```

---

## Funnel Analysis

**Key funnels for document processing tools:**

| Funnel Stage | Event | Metric |
|--------------|-------|--------|
| 1. Upload | `action: "upload"` | Upload attempts |
| 2. Success | `action: "upload"` with `parties_found > 0` | Successful extractions |
| 3. Export | `action: "export"` | Downloads |

### Backend: Funnel Query

```python
# api/analytics.py
from collections import defaultdict

@router.get("/funnel/{tool}")
async def get_tool_funnel(tool: str):
    """Get funnel metrics for a specific tool."""
    from datetime import datetime, timedelta
    from app.services import firestore_service as db
    
    # Get last 30 days of events
    cutoff = datetime.utcnow() - timedelta(days=30)
    events = await db.get_usage_events_since(cutoff, tool=tool)
    
    # Count by action
    funnel = defaultdict(int)
    successful_uploads = 0
    
    for event in events:
        action = event["action"]
        funnel[action] += 1
        
        # Track successful uploads (e.g., parties_found > 0)
        if action == "upload" and event.get("metadata", {}).get("parties_found", 0) > 0:
            successful_uploads += 1
    
    total_uploads = funnel.get("upload", 0)
    total_exports = funnel.get("export", 0)
    
    return {
        "tool": tool,
        "period_days": 30,
        "funnel": {
            "uploads_attempted": total_uploads,
            "uploads_successful": successful_uploads,
            "exports": total_exports,
        },
        "conversion_rates": {
            "upload_success_rate": round(successful_uploads / total_uploads * 100, 1) if total_uploads > 0 else 0,
            "upload_to_export": round(total_exports / total_uploads * 100, 1) if total_uploads > 0 else 0,
        }
    }
```

---

## Admin Analytics Dashboard

**Create a new page: `frontend/src/pages/Analytics.tsx`**

```tsx
// Analytics.tsx - Admin-only analytics dashboard
import { useEffect, useState } from 'react';
import { BarChart3, Users, TrendingUp } from 'lucide-react';

interface ToolStats {
  tool: string;
  uploads: number;
  exports: number;
  unique_users: number;
}

export default function Analytics() {
  const [stats, setStats] = useState<ToolStats[]>([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchStats = async () => {
      const response = await fetch('/api/analytics/overview?days=30');
      const data = await response.json();
      setStats(data.by_tool);
      setLoading(false);
    };
    
    fetchStats();
  }, []);
  
  if (loading) return <div>Loading analytics...</div>;
  
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
        Analytics Dashboard
      </h1>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {stats.map(tool => (
          <div key={tool.tool} className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-oswald font-semibold text-tre-navy mb-3 capitalize">
              {tool.tool}
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-600">Uploads</span>
                <span className="font-semibold">{tool.uploads}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-600">Exports</span>
                <span className="font-semibold">{tool.exports}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-600">Users</span>
                <span className="font-semibold">{tool.unique_users}</span>
              </div>
              <div className="flex items-center justify-between border-t border-gray-100 pt-2">
                <span className="text-gray-600">Conversion</span>
                <span className="font-semibold text-tre-teal">
                  {Math.round(tool.exports / tool.uploads * 100)}%
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Add route in App.tsx:**

```tsx
// App.tsx
import Analytics from './pages/Analytics';

// Inside Routes:
<Route path="/analytics" element={<Analytics />} />
```

---

## Privacy Considerations

**For internal tools:** GDPR/CCPA less of a concern (employees, not end consumers), but still follow best practices.

1. **Don't track PII in metadata:** File content, addresses, SSNs should NOT be in analytics events
2. **User email is OK:** Since it's internal auth, tracking `user_email` is acceptable
3. **Retention policy:** Auto-delete events >1 year old

```python
# services/firestore_service.py
async def cleanup_old_events():
    """Delete usage events older than 1 year."""
    from datetime import datetime, timedelta
    
    db = get_firestore_client()
    cutoff = datetime.utcnow() - timedelta(days=365)
    
    # Query old events
    old_events = db.collection("usage_events").where("timestamp", "<", cutoff).stream()
    
    # Batch delete (Firestore limit: 500 per batch)
    batch = db.batch()
    count = 0
    
    for event in old_events:
        batch.delete(event.reference)
        count += 1
        
        if count % 500 == 0:
            await batch.commit()
            batch = db.batch()
    
    if count % 500 != 0:
        await batch.commit()
    
    logger.info(f"Deleted {count} old usage events")
```

**Schedule cleanup monthly via APScheduler:**

```python
# main.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    # ... existing RRC scheduler ...
    
    # Cleanup old analytics events monthly
    scheduler.add_job(
        cleanup_old_events,
        trigger="cron",
        day=15,  # 15th of each month
        hour=3,
        minute=0,
    )
    scheduler.start()