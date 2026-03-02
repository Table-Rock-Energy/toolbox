---
name: firestore
description: |
  Integrates Firebase Auth with Google Sign-In and token verification for FastAPI backend and React frontend.
  Use when: implementing authentication, verifying ID tokens on backend, managing auth state in React, or configuring Firebase services
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Firebase Skill

Firebase provides authentication and Firestore database services for Table Rock Tools. The backend uses Firebase Admin SDK for token verification and Firestore CRUD operations. Frontend uses Firebase Auth for Google Sign-In and email/password authentication. All Firestore operations use lazy initialization to avoid import-time errors.

## Quick Start

### Backend: Verify Firebase ID Token

```python
from app.core.auth import verify_firebase_token

async def protected_endpoint(token: str = Depends(oauth2_scheme)):
    user = await verify_firebase_token(token)
    # user contains 'uid', 'email', 'name'
```

### Backend: Firestore CRUD Operations

```python
from app.services.firestore_service import FirestoreService

firestore = FirestoreService()
await firestore.create_document("jobs", job_id, {"status": "processing"})
doc = await firestore.get_document("jobs", job_id)
await firestore.update_document("jobs", job_id, {"status": "completed"})
```

### Frontend: Get Current User

```typescript
import { useAuth } from '../contexts/AuthContext';

function MyComponent() {
  const { user, loading } = useAuth();
  
  if (loading) return <LoadingSpinner />;
  if (!user) return <Navigate to="/login" />;
  
  return <div>Welcome, {user.displayName}</div>;
}
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Lazy initialization | Import Firebase/Firestore only when needed | `if TYPE_CHECKING: from google.cloud import firestore` |
| Batch operations | Commit every 500 docs (Firestore limit) | `if len(batch_items) >= 500: batch.commit()` |
| Token verification | Backend verifies Firebase ID tokens from frontend | `verify_firebase_token(token)` in route handlers |
| Allowlist | JSON file controls authorized emails | `james@tablerocktx.com` is primary admin |

## Common Patterns

### Protected Route (Frontend)

**When:** User must be authenticated to access a page

```typescript
<Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
  <Route path="/extract" element={<Extract />} />
</Route>
```

### Firestore Batch Write (Backend)

**When:** Syncing hundreds/thousands of documents

```python
batch = db.batch()
for i, item in enumerate(items):
    ref = db.collection("rrc_data").document(item["id"])
    batch.set(ref, item)
    if (i + 1) % 500 == 0:
        batch.commit()
        batch = db.batch()
if len(items) % 500 != 0:
    batch.commit()
```

## WARNING: Common Anti-Patterns

### Anti-Pattern: Importing Firebase at Module Level

**The Problem:**

```python
# BAD - Imports Firebase at module load time
from google.cloud import firestore
db = firestore.Client()
```

**Why This Breaks:**
1. Crashes if GOOGLE_APPLICATION_CREDENTIALS not set (e.g., local dev without GCP)
2. Prevents lazy initialization for optional features
3. Blocks testing without full Firebase setup

**The Fix:**

```python
# GOOD - Lazy initialization
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud import firestore

def _init_firestore() -> firestore.Client:
    from google.cloud import firestore
    return firestore.Client()
```

### Anti-Pattern: No Batch Limit Handling

**The Problem:**

```python
# BAD - Will fail after 500 documents
batch = db.batch()
for item in all_items:  # Could be 10,000 items
    batch.set(db.collection("data").document(), item)
batch.commit()  # CRASHES if > 500 items
```

**Why This Breaks:**
1. Firestore enforces 500 operations per batch
2. Silent data loss if you don't check batch size
3. No feedback about which documents failed

**The Fix:**

```python
# GOOD - Commit every 500 docs
batch = db.batch()
for i, item in enumerate(all_items):
    ref = db.collection("data").document()
    batch.set(ref, item)
    if (i + 1) % 500 == 0:
        batch.commit()
        batch = db.batch()
        logger.info(f"Committed {i + 1} documents")
if len(all_items) % 500 != 0:
    batch.commit()
```

## See Also

- [patterns](references/patterns.md) - Authentication patterns, Firestore service layer, allowlist management
- [workflows](references/workflows.md) - User authorization flow, RRC data sync workflow

## Related Skills

- **fastapi** - Backend API routes use Firebase token verification
- **react** - Frontend auth state management with AuthContext
- **python** - Pydantic Settings for Firebase configuration
- **typescript** - Frontend Firebase Auth integration

## Documentation Resources

> Fetch latest Firebase documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "firebase admin python" (backend) or "firebase javascript" (frontend)
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** Resolve separately for backend (`firebase-admin`) and frontend (`firebase`) using `mcp__plugin_context7_context7__resolve-library-id`

**Recommended Queries:**
- "firebase admin python authentication"
- "firestore batch writes python"
- "firebase auth react google sign-in"
- "firestore security rules best practices"