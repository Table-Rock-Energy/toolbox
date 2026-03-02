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
  event_name: string           // snake_case, e.g., "tool_upload_started"
  user_id: string              // Firebase UID
  timestamp: Date              // UTC datetime
  properties: Record<string, any>  // Event-specific data
  session_id?: string          // Optional session grouping
}
```

**CRITICAL:** All timestamps MUST be UTC. Firestore stores `DateTime(timezone=True)` on backend.

### DO/DON'T: Event Naming

**BAD - Inconsistent naming:**
```typescript
track('UploadStarted', { tool: 'extract' })      // PascalCase
track('processing-complete', { tool: 'title' })   // kebab-case
track('Export', { format: 'csv' })                // Too vague
```

**GOOD - Consistent snake_case with object_action pattern:**
```typescript
track('tool_upload_started', { tool: 'extract' })
track('tool_processing_complete', { tool: 'title' })
track('export_downloaded', { tool: 'revenue', format: 'csv' })
```

**Standard:** `{object}_{action}_{context?}` in snake_case.

---

## Firestore Collections

### Events Collection

```python
# backend/app/services/firestore_service.py
EVENTS_COLLECTION = "events"

# Document structure
{
  "event_name": "tool_upload_started",
  "user_id": "firebase_uid_123",
  "timestamp": datetime(2026, 2, 9, 14, 30, 0, tzinfo=timezone.utc),
  "properties": {
    "tool": "extract",
    "file_name": "exhibit_a.pdf",
    "file_size_mb": 2.3,
  },
  "session_id": "uuid-session-123",
}
```

**Indexes Required:**
- Composite: `user_id ASC, timestamp DESC` (for user timelines)
- Composite: `event_name ASC, timestamp DESC` (for funnel queries)
- Single: `timestamp DESC` (for DAU/WAU calculations)

Create via Firestore console or `firestore.indexes.json`:

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
    }
  ]
}
```

---

## Event Properties Standards

### Tool Events

All tool-related events MUST include:

```typescript
{
  tool: 'extract' | 'title' | 'proration' | 'revenue',
  session_id: string,  // UUID generated at tool page mount
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
- ❌ `file_content`, `user_email`, `party_names`
- ✅ `file_name` (safe), `file_size_mb`, `entry_count`

### Processing Events

```typescript
track('tool_processing_complete', {
  tool: 'extract',
  success: true,
  total_entries: 45,
  flagged_entries: 3,
  processing_time_seconds: 12.5,
  error_message: null,
})
```

### Export Events

```typescript
track('export_downloaded', {
  tool: 'proration',
  format: 'excel' | 'pdf' | 'csv',
  row_count: 120,
  file_size_kb: 45.2,
})
```

---

## Metrics Calculation

### Conversion Funnel Query

```python
async def get_funnel_conversion(
    funnel_steps: list[str],
    start_date: date,
    end_date: date
) -> dict:
    """
    Calculate conversion rates between funnel steps.
    
    Args:
        funnel_steps: Ordered list of event names
        start_date: Cohort start date
        end_date: Cohort end date
    
    Returns:
        { step: count, step_2: count, conversion_rate: 0.75 }
    """
    db = get_firestore_client()
    
    # Get users who completed FIRST step in date range
    first_step_events = db.collection(EVENTS_COLLECTION).where(
        "event_name", "==", funnel_steps[0]
    ).where(
        "timestamp", ">=", datetime.combine(start_date, datetime.min.time())
    ).where(
        "timestamp", "<", datetime.combine(end_date, datetime.min.time())
    ).stream()
    
    first_step_users = set()
    async for event in first_step_events:
        first_step_users.add(event.to_dict()["user_id"])
    
    # For each subsequent step, count users who completed it
    funnel_counts = {funnel_steps[0]: len(first_step_users)}
    
    for step in funnel_steps[1:]:
        step_events = db.collection(EVENTS_COLLECTION).where(
            "event_name", "==", step
        ).where(
            "user_id", "in", list(first_step_users)  # Only cohort users
        ).stream()
        
        step_users = set()
        async for event in step_events:
            step_users.add(event.to_dict()["user_id"])
        
        funnel_counts[step] = len(step_users)
    
    return funnel_counts
```

**WARNING:** Firestore `in` operator limited to 10 values. For cohorts >10 users, batch queries in chunks of 10.

### Average Time Between Events

```python
async def get_avg_time_to_event(
    from_event: str,
    to_event: str,
    max_hours: int = 24
) -> float:
    """Calculate average time from event A to event B."""
    db = get_firestore_client()
    
    # Get all users who completed both events
    from_events = db.collection(EVENTS_COLLECTION).where(
        "event_name", "==", from_event
    ).stream()
    
    time_deltas = []
    
    async for from_event_doc in from_events:
        from_data = from_event_doc.to_dict()
        user_id = from_data["user_id"]
        from_timestamp = from_data["timestamp"]
        
        # Find FIRST occurrence of to_event AFTER from_event
        to_event_doc = db.collection(EVENTS_COLLECTION).where(
            "user_id", "==", user_id
        ).where(
            "event_name", "==", to_event
        ).where(
            "timestamp", ">", from_timestamp
        ).where(
            "timestamp", "<", from_timestamp + timedelta(hours=max_hours)
        ).order_by("timestamp").limit(1).get()
        
        if to_event_doc:
            to_timestamp = to_event_doc[0].to_dict()["timestamp"]
            delta_seconds = (to_timestamp - from_timestamp).total_seconds()
            time_deltas.append(delta_seconds)
    
    return sum(time_deltas) / len(time_deltas) if time_deltas else 0