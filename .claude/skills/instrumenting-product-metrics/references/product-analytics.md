# Product Analytics Reference

## Contents
- Event Schema Design
- Firestore Collections Structure
- Event Properties Standards
- Metrics Calculation Queries

---

## Event Schema

### Standard Event Structure

```typescript
// All events follow this schema
interface ProductEvent {
  event_name: string               // snake_case: "tool_upload_started"
  user_id: string                  // Firebase UID
  timestamp: Date                  // UTC datetime
  properties: Record<string, unknown>  // Event-specific data
}
```

**CRITICAL:** All timestamps MUST be UTC. Use `datetime.now(tz=timezone.utc)` on backend (not `datetime.utcnow()` which is naive).

### DO/DON'T: Event Naming

**BAD - Inconsistent naming:**
```typescript
track('UploadStarted', { tool: 'extract' })      // PascalCase
track('processing-complete', { tool: 'title' })   // kebab-case
track('Export', { format: 'csv' })                // Too vague
```

**GOOD - Consistent `{object}_{action}` in snake_case:**
```typescript
track('tool_upload_started', { tool: 'extract' })
track('tool_processing_complete', { tool: 'title' })
track('export_downloaded', { tool: 'revenue', format: 'csv' })
```

---

## Firestore Collections

### Events Collection

```python
# Add to backend/app/services/firestore_service.py
EVENTS_COLLECTION = "events"

# Document structure (written by analytics_service.py)
{
  "event_name": "tool_upload_started",
  "user_id": "firebase_uid_123",
  "timestamp": datetime(2026, 2, 9, 14, 30, 0, tzinfo=timezone.utc),
  "properties": {
    "tool": "extract",
    "file_name": "exhibit_a.pdf",
    "file_size_mb": 2.3,
  },
}
```

**Indexes required** (add to Firestore console or `firestore.indexes.json`):

```json
{
  "indexes": [
    {
      "collectionGroup": "events",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id", "order": "ASCENDING" },
        { "fieldPath": "timestamp", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "events",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "event_name", "order": "ASCENDING" },
        { "fieldPath": "timestamp", "order": "DESCENDING" }
      ]
    }
  ]
}
```

---

## Event Properties Standards

### All Tool Events Must Include

```typescript
{
  tool: 'extract' | 'title' | 'proration' | 'revenue' | 'ghl_prep',
}
```

### Upload Events

```typescript
track('tool_upload_started', {
  tool: 'extract',
  file_name: file.name,
  file_size_mb: file.size / 1024 / 1024,
  file_type: file.type,
})
```

**WARNING:** NEVER include PII in event properties:
- `file_content`, `user_email`, `party_names` → NEVER include
- `file_name`, `file_size_mb`, `entry_count` → safe to include

### Processing Events

```typescript
track('tool_processing_complete', {
  tool: 'extract',
  success: true,
  total_entries: 45,
  flagged_entries: 3,
  processing_time_seconds: 12.5,
})
```

### Export Events

```typescript
track('export_downloaded', {
  tool: 'proration',
  format: 'excel' | 'pdf' | 'csv',
  row_count: 120,
})
```

---

## Metrics Calculation

### Conversion Funnel Query

```python
# backend/app/api/analytics.py
from datetime import datetime, date, timedelta, timezone
from app.services.firestore_service import get_firestore_client, EVENTS_COLLECTION

async def get_funnel_conversion(
    funnel_steps: list[str],
    start_date: date,
    end_date: date,
) -> dict[str, int]:
    """Calculate how many unique users completed each funnel step."""
    db = get_firestore_client()

    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    # Collect all users for first step in date range
    first_events = db.collection(EVENTS_COLLECTION).where(
        "event_name", "==", funnel_steps[0]
    ).where("timestamp", ">=", start_dt).where("timestamp", "<", end_dt).stream()

    cohort: set[str] = set()
    async for doc in first_events:
        cohort.add(doc.to_dict()["user_id"])

    funnel_counts = {funnel_steps[0]: len(cohort)}

    # WARNING: Firestore `in` operator limited to 10 values.
    # For cohorts >10, batch into chunks of 10.
    for step in funnel_steps[1:]:
        step_users: set[str] = set()
        cohort_list = list(cohort)
        for i in range(0, len(cohort_list), 10):
            chunk = cohort_list[i:i + 10]
            step_events = db.collection(EVENTS_COLLECTION).where(
                "event_name", "==", step
            ).where("user_id", "in", chunk).stream()
            async for doc in step_events:
                step_users.add(doc.to_dict()["user_id"])
        funnel_counts[step] = len(step_users)

    return funnel_counts
```

### DAU/WAU Calculation

```python
async def get_dau(target_date: date | None = None) -> int:
    """Count unique users who fired any event on target_date."""
    d = target_date or datetime.now(tz=timezone.utc).date()
    db = get_firestore_client()

    start = datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    events = db.collection(EVENTS_COLLECTION).where(
        "timestamp", ">=", start
    ).where("timestamp", "<", end).stream()

    unique_users: set[str] = set()
    async for doc in events:
        unique_users.add(doc.to_dict()["user_id"])
    return len(unique_users)
```

**WARNING:** Firestore has no `COUNT(DISTINCT)`. Must fetch all events and deduplicate in memory. For >10k events/day, export to BigQuery instead.

See the **firestore** skill for Firestore client patterns and batch operation limits.
