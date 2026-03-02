# Firebase Patterns Reference

## Contents
- Lazy Initialization (Backend)
- Token Verification with Allowlist
- ID Token Refresh (Frontend)
- Firestore Client Initialization
- Environment Variables

---

## Lazy Initialization (Backend)

**Problem:** Importing Firebase Admin SDK at module level causes initialization errors when credentials are missing (local dev without GCS).

**Solution:** Lazy initialization — import and initialize only when first needed.

```python
# toolbox/backend/app/core/auth.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from firebase_admin import auth

_firebase_initialized = False

def _init_firebase():
    """Initialize Firebase Admin SDK with Application Default Credentials."""
    global _firebase_initialized
    if not _firebase_initialized:
        from firebase_admin import credentials, initialize_app
        try:
            initialize_app(credentials.ApplicationDefault())
            _firebase_initialized = True
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firebase Admin: {e}")

def verify_firebase_token(id_token: str) -> dict:
    """Verify Firebase ID token and return decoded claims."""
    _init_firebase()
    from firebase_admin import auth
    return auth.verify_id_token(id_token)
```

**Why:** Allows the app to start without Firebase credentials (useful for local dev with Firestore disabled). Initialization happens only when auth is actually used.

---

## Token Verification with Allowlist

**Problem:** Firebase Auth verifies the token signature, but doesn't check if the user is authorized for your app.

**Solution:** After token verification, check the email against a JSON allowlist.

```python
# toolbox/backend/app/core/auth.py
import json
from pathlib import Path
from fastapi import HTTPException, Header, Depends

ALLOWED_USERS_FILE = Path(__file__).parent.parent / "data" / "allowed_users.json"

def load_allowed_users() -> set[str]:
    """Load allowed user emails from JSON file."""
    if not ALLOWED_USERS_FILE.exists():
        return {"james@tablerocktx.com"}  # Default admin
    
    with open(ALLOWED_USERS_FILE) as f:
        data = json.load(f)
        return set(data.get("allowed_users", []))

def is_user_allowed(email: str) -> bool:
    """Check if user email is in allowlist."""
    allowed = load_allowed_users()
    return email.lower() in {u.lower() for u in allowed}

async def get_current_user(authorization: str = Header(None)) -> dict:
    """FastAPI dependency for protected routes."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization.split("Bearer ")[1]
    
    try:
        decoded = verify_firebase_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    
    if not is_user_allowed(decoded.get("email", "")):
        raise HTTPException(status_code=403, detail="User not authorized")
    
    return decoded
```

**Usage in routes:**

```python
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/extract")

@router.post("/upload")
async def upload_pdf(
    user: dict = Depends(get_current_user)
):
    # user["email"] is guaranteed to be in allowlist
    return {"message": f"Authenticated as {user['email']}"}
```

**Why:** Prevents unauthorized Firebase users from accessing the app. The allowlist is managed separately from Firebase Auth.

---

## WARNING: Synchronous Token Verification in Async Routes

**The Problem:**

```python
# BAD - Blocking the event loop
@router.post("/upload")
async def upload_pdf(user: dict = Depends(get_current_user)):
    # get_current_user calls auth.verify_id_token() synchronously
    # This BLOCKS the FastAPI event loop
    pass
```

**Why This Breaks:**
1. `auth.verify_id_token()` is a synchronous network call (verifies signature with Google's public keys)
2. Blocking the event loop degrades throughput for all requests
3. Under load, this causes request timeouts

**The Fix:**

```python
# GOOD - Run in thread pool
import asyncio
from functools import partial

async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization.split("Bearer ")[1]
    
    # Run synchronous Firebase call in thread pool
    loop = asyncio.get_event_loop()
    try:
        decoded = await loop.run_in_executor(
            None, 
            partial(verify_firebase_token, token)
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    
    if not is_user_allowed(decoded.get("email", "")):
        raise HTTPException(status_code=403, detail="User not authorized")
    
    return decoded
```

**When You Might Be Tempted:**
When the Firebase Admin SDK doesn't provide async alternatives. Always wrap synchronous calls in `run_in_executor` for async routes.

---

## ID Token Refresh (Frontend)

**Problem:** Firebase ID tokens expire after 1 hour. API calls with expired tokens return 401.

**Solution:** Refresh the token before each API call.

```typescript
// toolbox/frontend/src/utils/api.ts
import { auth } from '../lib/firebase';

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = '/api') {
    this.baseUrl = baseUrl;
  }

  private async getAuthHeaders(): Promise<Record<string, string>> {
    const user = auth.currentUser;
    if (!user) {
      throw new Error('Not authenticated');
    }

    // getIdToken() automatically refreshes if expired
    const token = await user.getIdToken();
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }

  async post<T>(endpoint: string, data: any): Promise<T> {
    const headers = await this.getAuthHeaders();
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }
}
```

**Why:** `getIdToken()` handles token refresh automatically. Never cache the token yourself — always call `getIdToken()` before API requests.

---

## Firestore Client Initialization

**Problem:** Firestore and Firebase Admin share the same initialization, but Firestore operations need the Firestore client.

**Solution:** Lazy initialization for Firestore client, separate from Auth.

```python
# toolbox/backend/app/services/firestore_service.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud import firestore

_firestore_client: firestore.Client | None = None

def get_firestore_client() -> firestore.Client:
    """Get or create Firestore client with lazy initialization."""
    global _firestore_client
    if _firestore_client is None:
        from google.cloud import firestore
        _firestore_client = firestore.Client()
    return _firestore_client

async def save_job(collection: str, job_data: dict) -> str:
    """Save job document to Firestore."""
    client = get_firestore_client()
    doc_ref = client.collection(collection).document()
    doc_ref.set(job_data)
    return doc_ref.id
```

**Why:** Firestore client initialization is separate from Firebase Admin Auth. Both can fail independently in local dev, so lazy init allows graceful degradation.

---

## Environment Variables

**Frontend (.env):**

```bash
VITE_FIREBASE_API_KEY=AIza...
VITE_FIREBASE_AUTH_DOMAIN=tablerockenergy.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=tablerockenergy
VITE_FIREBASE_STORAGE_BUCKET=tablerockenergy.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
```

**Backend (config.py):**

```python
# toolbox/backend/app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Firebase uses Application Default Credentials
    # Set GOOGLE_APPLICATION_CREDENTIALS env var or use gcloud auth
    firestore_enabled: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

**Local Development:**

```bash
# Backend authenticates with gcloud
gcloud auth application-default login

# Or set service account key path
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/serviceAccountKey.json"
```

**Production (Cloud Run):**
Uses the service's default service account — no explicit credentials needed.