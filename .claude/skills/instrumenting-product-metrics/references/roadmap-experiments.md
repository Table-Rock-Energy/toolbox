# Roadmap & Experiments Reference

## Contents
- Feature Flag Implementation
- A/B Test Tracking
- Rollout Verification

---

## WARNING: No Feature Flags or Experiments

Table Rock Tools has **no experimentation infrastructure**:
- No feature flags
- No A/B testing framework
- No gradual rollouts

All features ship to 100% of users immediately. This is appropriate for a small internal tool (5-10 users), but lightweight feature flags are still useful for safely testing new parsers (e.g., new Revenue PDF format) before enabling for everyone.

---

## Feature Flag via Firestore

### Backend Flag Service

```python
# backend/app/services/feature_flags.py
import hashlib
from app.services.firestore_service import get_firestore_client

FEATURE_FLAGS_COLLECTION = "feature_flags"

async def is_feature_enabled(flag_name: str, user_id: str) -> bool:
    """Check if feature is enabled for user. Returns False on any error."""
    try:
        db = get_firestore_client()
        flag_doc = await db.collection(FEATURE_FLAGS_COLLECTION).document(flag_name).get()

        if not flag_doc.exists:
            return False

        flag_data = flag_doc.to_dict()

        if flag_data.get("enabled_for_all"):
            return True

        if user_id in flag_data.get("enabled_users", []):
            return True

        rollout_pct = flag_data.get("rollout_percentage", 0)
        if rollout_pct > 0:
            # Deterministic hash-based bucketing — same user always gets same variant
            bucket = int(hashlib.md5(f"{flag_name}:{user_id}".encode()).hexdigest(), 16) % 100
            return bucket < rollout_pct

        return False
    except Exception:
        logger.warning("Feature flag check failed for %s, defaulting to False", flag_name)
        return False
```

### Feature Flag Document Structure

```json
// Firestore: feature_flags/new_energytransfer_parser
{
  "enabled_for_all": false,
  "enabled_users": ["firebase_uid_james"],
  "rollout_percentage": 0,
  "description": "New Energy Transfer PDF parser with improved table extraction"
}
```

### Frontend Flag Hook

```typescript
// frontend/src/hooks/useFeatureFlag.ts
import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'

export function useFeatureFlag(flagName: string): boolean {
  const { user } = useAuth()
  const [isEnabled, setIsEnabled] = useState(false)

  useEffect(() => {
    if (!user) return

    fetch(`/api/feature-flags/${flagName}`)
      .then(r => r.json())
      .then(data => setIsEnabled(data.enabled))
      .catch(() => setIsEnabled(false))  // Always fail safe to disabled
  }, [flagName, user])

  return isEnabled
}
```

### Using a Flag in Revenue Tool

```typescript
// frontend/src/pages/Revenue.tsx
const useNewParser = useFeatureFlag('new_energytransfer_parser')
const { track } = useAnalytics()

const handleUpload = async (files: File[]) => {
  track('revenue_upload_started', {
    parser_variant: useNewParser ? 'energytransfer_v2' : 'energytransfer_v1',
  })

  const endpoint = useNewParser
    ? '/api/revenue/upload?parser=energytransfer_v2'
    : '/api/revenue/upload'

  // ... upload logic
}
```

**WHY:** Always include the active flag/variant in event properties. Without it, you can't split analytics by which users saw which version.

---

## A/B Test Tracking

Small user base (5-10 users) means true A/B tests have no statistical significance. Use feature flags for user-level rollouts instead. If you need to test UI changes:

```python
# backend/app/services/experiments.py
import hashlib
from datetime import datetime, timezone
from app.services.firestore_service import get_firestore_client

EXPERIMENT_ASSIGNMENTS_COLLECTION = "experiment_assignments"

async def get_experiment_variant(experiment_name: str, user_id: str) -> str:
    """Assign user to variant deterministically. Persisted for consistency."""
    db = get_firestore_client()
    doc_id = f"{experiment_name}_{user_id}"
    assignment_ref = db.collection(EXPERIMENT_ASSIGNMENTS_COLLECTION).document(doc_id)
    doc = await assignment_ref.get()

    if doc.exists:
        return doc.to_dict()["variant"]

    variant = "B" if int(hashlib.md5(f"{experiment_name}:{user_id}".encode()).hexdigest(), 16) % 2 == 0 else "A"

    await assignment_ref.set({
        "experiment_name": experiment_name,
        "user_id": user_id,
        "variant": variant,
        "assigned_at": datetime.now(tz=timezone.utc),
    })

    return variant
```

---

## Rollout Verification

After enabling a flag, verify users actually ADOPT the feature (not just have access):

```python
async def get_flag_adoption_rate(flag_name: str, usage_event: str, days: int = 7) -> dict:
    """Enabled ≠ adopted. Measures how many enabled users actually triggered the feature."""
    db = get_firestore_client()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    flag_doc = await db.collection(FEATURE_FLAGS_COLLECTION).document(flag_name).get()
    enabled_users: list[str] = flag_doc.to_dict().get("enabled_users", []) if flag_doc.exists else []

    if not enabled_users:
        return {"enabled_count": 0, "used_count": 0, "adoption_rate": 0}

    # Query usage events in batches of 10 (Firestore `in` limit)
    users_who_used: set[str] = set()
    for i in range(0, len(enabled_users), 10):
        chunk = enabled_users[i:i + 10]
        events = db.collection(EVENTS_COLLECTION).where(
            "event_name", "==", usage_event
        ).where("user_id", "in", chunk).where("timestamp", ">=", cutoff).stream()
        async for doc in events:
            users_who_used.add(doc.to_dict()["user_id"])

    return {
        "flag_name": flag_name,
        "enabled_count": len(enabled_users),
        "used_count": len(users_who_used),
        "adoption_rate": len(users_who_used) / len(enabled_users),
    }
```

See the **firestore** skill for collection naming conventions and the **fastapi** skill for building the feature-flag API endpoint.
