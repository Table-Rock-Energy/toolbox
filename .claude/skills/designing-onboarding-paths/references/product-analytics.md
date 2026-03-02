# Product Analytics Reference

## Contents
- Event Tracking (Not Yet Implemented)
- Funnel Analysis Patterns
- Session Recording Considerations
- A/B Test Instrumentation
- Privacy & Compliance

---

## Event Tracking (Not Yet Implemented)

Table Rock Tools currently has **NO analytics implementation**. No Google Analytics, no custom event tracking, no product metrics.

### Recommended Analytics Stack for Internal Tools

For internal B2B tools, avoid heavy external SDKs. Use **lightweight event logging to Firestore**:

```typescript
// toolbox/frontend/src/utils/analytics.ts
interface AnalyticsEvent {
  event_name: string
  user_email: string
  timestamp: string
  properties?: Record<string, unknown>
  session_id?: string
}

class Analytics {
  private sessionId: string
  private userId: string | null = null

  constructor() {
    this.sessionId = this.generateSessionId()
  }

  private generateSessionId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  setUser(email: string) {
    this.userId = email
  }

  async track(eventName: string, properties?: Record<string, unknown>) {
    if (!this.userId) {
      console.warn('Analytics: User not set, skipping event')
      return
    }

    const event: AnalyticsEvent = {
      event_name: eventName,
      user_email: this.userId,
      timestamp: new Date().toISOString(),
      session_id: this.sessionId,
      properties,
    }

    try {
      await fetch(`${import.meta.env.VITE_API_BASE_URL}/analytics/event`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(event),
      })
    } catch (err) {
      console.error('Analytics tracking failed:', err)
    }
  }
}

export const analytics = new Analytics()
```

**Backend endpoint:**

```python
# toolbox/backend/app/api/analytics.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class AnalyticsEvent(BaseModel):
    event_name: str
    user_email: str
    timestamp: str
    session_id: str | None = None
    properties: dict | None = None

@router.post("/event")
async def track_event(event: AnalyticsEvent):
    """Log analytics event to Firestore."""
    try:
        from app.services import firestore_service as db
        
        await db.store_analytics_event({
            "event_name": event.event_name,
            "user_email": event.user_email,
            "timestamp": datetime.fromisoformat(event.timestamp),
            "session_id": event.session_id,
            "properties": event.properties or {},
        })
        
        return {"status": "tracked"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Key Events to Track

```typescript
// App.tsx - Track user login
useEffect(() => {
  if (user?.email) {
    analytics.setUser(user.email)
    analytics.track('user_logged_in')
  }
}, [user])

// Dashboard.tsx - Track tool clicks
<Link
  to="/extract"
  onClick={() => analytics.track('tool_clicked', { tool: 'extract' })}
>
  Open Extract Tool
</Link>

// Extract.tsx - Track file uploads
const handleFilesSelected = async (files: File[]) => {
  analytics.track('file_uploaded', {
    tool: 'extract',
    file_count: files.length,
    file_type: files[0].type,
  })
  // ... upload logic
}

// Extract.tsx - Track export actions
const handleExport = async (format: 'csv' | 'excel') => {
  analytics.track('export_initiated', {
    tool: 'extract',
    format,
    entry_count: filteredEntries.length,
  })
  // ... export logic
}
```

---

## Funnel Analysis Patterns

### Activation Funnel for New Users

Track steps from login → first upload → first export:

```typescript
// Track funnel stages
// Stage 1: User logs in (tracked in App.tsx)
analytics.track('activation_step_1_login')

// Stage 2: User navigates to a tool
analytics.track('activation_step_2_tool_visit', { tool: 'extract' })

// Stage 3: User uploads first file
analytics.track('activation_step_3_first_upload', { tool: 'extract' })

// Stage 4: User exports results
analytics.track('activation_step_4_first_export', { tool: 'extract', format: 'csv' })
```

**Backend query for funnel analysis:**

```python
# toolbox/backend/app/api/analytics.py
@router.get("/funnel/activation")
async def get_activation_funnel():
    """Get activation funnel metrics."""
    from app.services import firestore_service as db
    
    events = await db.get_analytics_events(limit=10000)
    
    users_logged_in = set()
    users_visited_tool = set()
    users_uploaded = set()
    users_exported = set()
    
    for event in events:
        user = event["user_email"]
        if event["event_name"] == "activation_step_1_login":
            users_logged_in.add(user)
        elif event["event_name"] == "activation_step_2_tool_visit":
            users_visited_tool.add(user)
        elif event["event_name"] == "activation_step_3_first_upload":
            users_uploaded.add(user)
        elif event["event_name"] == "activation_step_4_first_export":
            users_exported.add(user)
    
    total_users = len(users_logged_in)
    
    return {
        "funnel": [
            {"step": "Logged In", "count": len(users_logged_in), "percentage": 100},
            {"step": "Visited Tool", "count": len(users_visited_tool), "percentage": round(len(users_visited_tool) / total_users * 100, 1)},
            {"step": "Uploaded File", "count": len(users_uploaded), "percentage": round(len(users_uploaded) / total_users * 100, 1)},
            {"step": "Exported Results", "count": len(users_exported), "percentage": round(len(users_exported) / total_users * 100, 1)},
        ]
    }
```

### Tool-Specific Conversion Tracking

```typescript
// Proration.tsx - Track prerequisite completion
analytics.track('proration_rrc_download_started')
// ... after download completes
analytics.track('proration_rrc_download_completed', {
  record_count: oilRecords + gasRecords,
  duration_seconds: downloadDuration,
})

// ... after CSV upload
analytics.track('proration_csv_uploaded', {
  row_count: mineralHolders.length,
})

// ... after calculations
analytics.track('proration_calculated', {
  row_count: results.length,
  flagged_count: flaggedRows,
  calculation_time_ms: calcTime,
})
```

---

## Session Recording Considerations

**DO NOT use session recording tools (Hotjar, FullStory, LogRocket)** for internal tools with sensitive data.

**Why:**
1. **Privacy risk** - Session recordings capture PII, financial data, mineral interests
2. **Compliance** - May violate internal data policies or GDPR/CCPA
3. **Overkill** - Internal tools have small user bases; direct user interviews more valuable

**Alternative:**

```typescript
// Track page views and time spent instead
let pageStartTime = Date.now()

useEffect(() => {
  pageStartTime = Date.now()
  
  return () => {
    const timeSpent = Date.now() - pageStartTime
    analytics.track('page_view', {
      page: window.location.pathname,
      time_spent_seconds: Math.round(timeSpent / 1000),
    })
  }
}, [location.pathname])
```

---

## A/B Test Instrumentation

For internal tools, avoid complex A/B testing platforms. Use **simple feature flags** in localStorage:

```typescript
// toolbox/frontend/src/utils/experiments.ts
interface Experiment {
  id: string
  variants: string[]
}

export function getVariant(experimentId: string, variants: string[]): string {
  const key = `experiment_${experimentId}`
  let variant = localStorage.getItem(key)
  
  if (!variant || !variants.includes(variant)) {
    // Randomly assign variant
    variant = variants[Math.floor(Math.random() * variants.length)]
    localStorage.setItem(key, variant)
    
    // Track assignment
    analytics.track('experiment_assigned', {
      experiment_id: experimentId,
      variant,
    })
  }
  
  return variant
}

// Usage in Dashboard.tsx
const dashboardLayout = getVariant('dashboard-layout-v2', ['cards', 'list'])

{dashboardLayout === 'cards' ? (
  <ToolCards tools={tools} />
) : (
  <ToolList tools={tools} />
)}
```

**Track variant-specific events:**

```typescript
analytics.track('tool_clicked', {
  tool: 'extract',
  experiment_variant: dashboardLayout,
})
```

---

## Privacy & Compliance

### Event Data Sanitization

**NEVER track:**
- PDF file contents
- Extracted party names/addresses
- Revenue amounts
- Legal descriptions

**DO track:**
- Event names (actions taken)
- Counts (number of entries, files, etc.)
- Durations (processing time)
- User identifiers (email, already controlled by allowlist)

```typescript
// BAD - Tracking PII
analytics.track('entry_extracted', {
  name: 'John Doe',
  address: '123 Main St',
})

// GOOD - Tracking counts only
analytics.track('entries_extracted', {
  total_count: 45,
  flagged_count: 3,
  entity_types: { individual: 30, trust: 10, llc: 5 },
})
```

### Data Retention Policy

```python
# toolbox/backend/app/services/firestore_service.py
from datetime import datetime, timedelta

async def cleanup_old_analytics_events():
    """Delete analytics events older than 90 days."""
    cutoff_date = datetime.now() - timedelta(days=90)
    
    db = firestore.client()
    events_ref = db.collection("analytics_events")
    
    old_events = events_ref.where("timestamp", "<", cutoff_date).stream()
    
    batch = db.batch()
    count = 0
    
    for doc in old_events:
        batch.delete(doc.reference)
        count += 1
        
        if count % 500 == 0:
            await batch.commit()
            batch = db.batch()
    
    if count % 500 != 0:
        await batch.commit()
    
    logger.info(f"Deleted {count} old analytics events")