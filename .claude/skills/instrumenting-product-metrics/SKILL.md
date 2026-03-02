---
name: instrumenting-product-metrics
description: |
  Defines product events, funnels, and activation metrics for Table Rock Tools FastAPI + React application.
  Use when: adding event tracking, measuring tool usage, building activation funnels, analyzing user engagement, or instrumenting feature adoption flows.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Instrumenting Product Metrics

Table Rock Tools currently has **NO analytics instrumentation**. This skill documents how to add product metrics tracking to the FastAPI backend and React frontend to measure activation, engagement, and feature adoption.

## Quick Start

### Backend Event Tracking

```python
# backend/app/services/analytics_service.py
from datetime import datetime
from app.services.firestore_service import get_firestore_client, EVENTS_COLLECTION

async def track_event(
    event_name: str,
    user_id: str,
    properties: dict | None = None,
):
    """Track a product event to Firestore."""
    db = get_firestore_client()
    event_doc = {
        "event_name": event_name,
        "user_id": user_id,
        "timestamp": datetime.utcnow(),
        "properties": properties or {},
    }
    await db.collection(EVENTS_COLLECTION).add(event_doc)
```

### Frontend Event Hook

```typescript
// frontend/src/hooks/useAnalytics.ts
export function useAnalytics() {
  const { user } = useAuth()
  
  const track = useCallback((eventName: string, properties?: Record<string, any>) => {
    if (!user) return
    
    fetch(`/api/events/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_name: eventName,
        user_id: user.uid,
        properties: properties || {},
      }),
    }).catch(console.error)
  }, [user])
  
  return { track }
}
```

## Key Metrics by Tool

| Metric | Event | Collection Point |
|--------|-------|------------------|
| File Upload Started | `tool_upload_started` | `FileUpload` component |
| Processing Complete | `tool_processing_complete` | Tool page after API response |
| Export Downloaded | `export_downloaded` | Export button click |
| Tool Abandoned | `tool_abandoned` | Page unload with unsaved data |

## Activation Funnel

Track new user activation through first successful workflow:

```typescript
// Track signup → first tool use → first export
const ACTIVATION_EVENTS = [
  'user_signed_up',
  'first_tool_opened',
  'first_file_uploaded',
  'first_export_downloaded',
]
```

## See Also

- [activation-onboarding](references/activation-onboarding.md) - First-run flows and empty states
- [engagement-adoption](references/engagement-adoption.md) - Feature usage and retention metrics
- [in-app-guidance](references/in-app-guidance.md) - Tooltips and feature discovery tracking
- [product-analytics](references/product-analytics.md) - Event schemas and data models
- [roadmap-experiments](references/roadmap-experiments.md) - A/B testing and feature flags
- [feedback-insights](references/feedback-insights.md) - User feedback collection

## Related Skills

For backend implementation patterns, see the **fastapi** and **firestore** skills.
For frontend tracking hooks, see the **react** and **typescript** skills.