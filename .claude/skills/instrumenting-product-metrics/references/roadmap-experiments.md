# Roadmap & Experiments Reference

## Contents
- Feature Flag Implementation
- A/B Test Tracking
- Rollout Verification
- Experiment Analysis

---

## WARNING: No Feature Flags or Experiments

Table Rock Tools has **NO experimentation infrastructure**:
- No feature flags
- No A/B testing framework
- No gradual rollouts
- All features ship to 100% of users immediately

This is appropriate for a small internal tool (5-10 users), but tracking is still valuable.

---

## Feature Flag via Firestore

### Backend Flag Configuration

```python
# backend/app/services/feature_flags.py
from app.services.firestore_service import get_firestore_client

FEATURE_FLAGS_COLLECTION = "feature_flags"

async def get_feature_flag(flag_name: str, user_id: str) -> bool:
    """Check if feature is enabled for user."""
    db = get_firestore_client()
    flag_doc = await db.collection(FEATURE_FLAGS_COLLECTION).document(flag_name).get()
    
    if not flag_doc.exists:
        return False  # Default to disabled
    
    flag_data = flag_doc.to_dict()
    
    # Global enable/disable
    if flag_data.get("enabled_for_all"):
        return True
    
    # User allowlist
    if user_id in flag_data.get("enabled_users", []):
        return True
    
    # Percentage rollout
    rollout_pct = flag_data.get("rollout_percentage", 0)
    if rollout_pct > 0:
        # Deterministic hash-based bucketing
        user_hash = int(hashlib.md5(f"{flag_name}:{user_id}".encode()).hexdigest(), 16)
        bucket = user_hash % 100
        return bucket < rollout_pct
    
    return False
```

### Feature Flag Document Structure

```json
// Firestore: feature_flags/new_revenue_parser
{
  "enabled_for_all": false,
  "enabled_users": ["firebase_uid_admin", "firebase_uid_beta"],
  "rollout_percentage": 25,
  "description": "New EnergyTransfer PDF parser with improved extraction",
  "created_at": "2026-02-01T00:00:00Z",
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
    
    fetch(`/api/feature-flags/${flagName}?user_id=${user.uid}`)
      .then(r => r.json())
      .then(data => setIsEnabled(data.enabled))
      .catch(() => setIsEnabled(false))
  }, [flagName, user])
  
  return isEnabled
}
```

### Usage in Components

```typescript
// frontend/src/pages/Revenue.tsx
const useNewParser = useFeatureFlag('new_revenue_parser')

const handleUpload = async (files: File[]) => {
  track('revenue_upload_started', {
    parser_version: useNewParser ? 'v2' : 'v1',
  })
  
  const endpoint = useNewParser 
    ? '/api/revenue/upload-v2' 
    : '/api/revenue/upload'
  
  // ... upload logic
}
```

**WHY:** Track which users experience which variants to segment analysis.

---

## A/B Test Tracking

### Experiment Assignment

```python
# backend/app/services/experiments.py
EXPERIMENTS_COLLECTION = "experiments"
EXPERIMENT_ASSIGNMENTS_COLLECTION = "experiment_assignments"

async def assign_experiment_variant(
    experiment_name: str,
    user_id: str
) -> str:
    """Assign user to A or B variant (deterministic)."""
    db = get_firestore_client()
    
    # Check for existing assignment
    assignment_ref = db.collection(EXPERIMENT_ASSIGNMENTS_COLLECTION).document(
        f"{experiment_name}_{user_id}"
    )
    assignment_doc = await assignment_ref.get()
    
    if assignment_doc.exists:
        return assignment_doc.to_dict()["variant"]
    
    # New assignment - deterministic hash
    user_hash = int(hashlib.md5(f"{experiment_name}:{user_id}".encode()).hexdigest(), 16)
    variant = "B" if user_hash % 2 == 0 else "A"
    
    # Store assignment
    await assignment_ref.set({
        "experiment_name": experiment_name,
        "user_id": user_id,
        "variant": variant,
        "assigned_at": datetime.utcnow(),
    })
    
    # Track assignment event
    await track_event(
        "experiment_assigned",
        user_id=user_id,
        properties={
            "experiment_name": experiment_name,
            "variant": variant,
        }
    )
    
    return variant
```

### Frontend Experiment Hook

```typescript
export function useExperiment(experimentName: string): 'A' | 'B' {
  const { user } = useAuth()
  const [variant, setVariant] = useState<'A' | 'B'>('A')
  
  useEffect(() => {
    if (!user) return
    
    fetch(`/api/experiments/${experimentName}/assign?user_id=${user.uid}`)
      .then(r => r.json())
      .then(data => setVariant(data.variant))
  }, [experimentName, user])
  
  return variant
}
```

### Example: Testing Export Button Placement

```typescript
const variant = useExperiment('export_button_placement')

return (
  <div>
    {variant === 'A' && (
      // Control: Export button at bottom
      <button onClick={() => {
        track('export_attempted', { 
          experiment: 'export_button_placement',
          variant: 'A' 
        })
        exportData()
      }}>
        Export
      </button>
    )}
    
    {variant === 'B' && (
      // Treatment: Export button at top
      <div className="mb-4">
        <button onClick={() => {
          track('export_attempted', { 
            experiment: 'export_button_placement',
            variant: 'B' 
          })
          exportData()
        }}>
          Export
        </button>
      </div>
    )}
  </div>
)
```

---

## Rollout Verification

### Check Feature Flag Adoption

```python
async def get_feature_adoption(flag_name: str, days: int = 7) -> dict:
    """Measure how many users actually USE a feature after flag enabled."""
    db = get_firestore_client()
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get events with flag tracking
    events = db.collection(EVENTS_COLLECTION).where(
        f"properties.feature_flag_{flag_name}", "==", True
    ).where(
        "timestamp", ">=", cutoff
    ).stream()
    
    users_who_used = set()
    async for event in events:
        users_who_used.add(event.to_dict()["user_id"])
    
    # Get total users with flag enabled
    flag_doc = await db.collection(FEATURE_FLAGS_COLLECTION).document(flag_name).get()
    enabled_users = flag_doc.to_dict().get("enabled_users", [])
    
    return {
        "flag_name": flag_name,
        "enabled_count": len(enabled_users),
        "used_count": len(users_who_used),
        "adoption_rate": len(users_who_used) / len(enabled_users) if enabled_users else 0,
    }
```

**WHY:** Enabled ≠ adopted. Users may not discover new features.