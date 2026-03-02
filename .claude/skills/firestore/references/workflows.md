# Firebase Workflows Reference

## Contents
- User Authorization Flow (End-to-End)
- RRC Data Sync Workflow
- Adding Users to Allowlist
- Frontend-to-Backend Auth Flow
- Testing Firebase Locally

---

## User Authorization Flow (End-to-End)

**Goal:** Authenticate a user with Google Sign-In and verify they're authorized.

### Workflow Steps

```markdown
Copy this checklist and track progress:
- [ ] Step 1: User clicks "Sign in with Google" on frontend
- [ ] Step 2: Firebase Auth returns ID token
- [ ] Step 3: Frontend stores token and sends to backend API
- [ ] Step 4: Backend verifies token with Firebase Admin SDK
- [ ] Step 5: Backend checks email against allowlist
- [ ] Step 6: Backend returns 200 (authorized) or 403 (forbidden)
```

### Frontend: Google Sign-In

```typescript
// frontend/src/pages/Login.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const { signInWithGoogle } = useAuth();
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleGoogleSignIn = async () => {
    try {
      await signInWithGoogle();
      navigate('/');  // Redirect to dashboard on success
    } catch (err) {
      setError('Failed to sign in. Contact admin if you need access.');
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-tre-navy">
      <div className="bg-white p-8 rounded-lg shadow-lg">
        <h1 className="text-2xl font-bold mb-4">Table Rock Tools</h1>
        <button
          onClick={handleGoogleSignIn}
          className="bg-tre-teal text-white px-6 py-2 rounded hover:bg-opacity-90"
        >
          Sign in with Google
        </button>
        {error && <p className="text-red-500 mt-4">{error}</p>}
      </div>
    </div>
  );
}
```

### Frontend: Send Token to Backend

```typescript
// frontend/src/utils/api.ts
import { auth } from '../lib/firebase';

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = '/api') {
    this.baseUrl = baseUrl;
  }

  private async getAuthHeaders(): Promise<HeadersInit> {
    const user = auth.currentUser;
    if (!user) throw new Error('Not authenticated');
    
    const token = await user.getIdToken();
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }

  async get<T>(endpoint: string): Promise<T> {
    const headers = await this.getAuthHeaders();
    const response = await fetch(`${this.baseUrl}${endpoint}`, { headers });
    
    if (response.status === 403) {
      throw new Error('Not authorized. Contact admin for access.');
    }
    if (!response.ok) throw new Error(`API error: ${response.statusText}`);
    
    return response.json();
  }
}
```

### Backend: Verify and Authorize

```python
# backend/app/api/extract.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.auth import verify_firebase_token

router = APIRouter(prefix="/api/extract")
security = HTTPBearer()

@router.post("/upload")
async def upload_extract(
    file: UploadFile,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # Step 1: Verify Firebase token
    user = await verify_firebase_token(credentials.credentials)
    # user = {"uid": "...", "email": "user@example.com", "name": "..."}
    
    # Step 2: Process request (user is now verified and authorized)
    logger.info(f"Upload from {user['email']}")
    # ... handle upload
```

### Validation

After implementing, test authorization:

```bash
# Test 1: Unauthorized user (should get 403)
curl -H "Authorization: Bearer INVALID_TOKEN" \
  http://localhost:8000/api/extract/upload

# Test 2: Authorized user (should succeed)
# Get token from browser DevTools after Google Sign-In:
# Application > Local Storage > firebase:authUser
curl -H "Authorization: Bearer YOUR_REAL_TOKEN" \
  http://localhost:8000/api/extract/upload
```

**Iterate until pass:**
1. Test with invalid token → should get 401
2. Test with valid token but unauthorized email → should get 403
3. Test with valid token and authorized email → should succeed
4. If any test fails, check logs and fix before proceeding

---

## RRC Data Sync Workflow

**Goal:** Download RRC CSV, parse into pandas, sync to Firestore with batching.

### Workflow Steps

```markdown
Copy this checklist and track progress:
- [ ] Step 1: Download CSV from RRC website (requires custom SSL)
- [ ] Step 2: Save to GCS or local storage
- [ ] Step 3: Parse CSV into pandas DataFrame
- [ ] Step 4: Cache DataFrame in memory for lookups
- [ ] Step 5: Sync to Firestore with 500-doc batching
- [ ] Step 6: Update status tracking
```

### Step 1-2: Download and Save

```python
# backend/app/services/proration/rrc_data_service.py
import requests
from requests.adapters import HTTPAdapter
import ssl
import logging
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)
storage = StorageService()

class RRCSSLAdapter(HTTPAdapter):
    """Custom SSL adapter for outdated RRC website."""
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

def download_rrc_data(well_type: str) -> str:
    """
    Download RRC CSV for oil or gas.
    
    Returns:
        Local file path to downloaded CSV
    """
    urls = {
        "oil": "https://webapps2.rrc.texas.gov/EWA/oilProQueryAction.do",
        "gas": "https://webapps2.rrc.texas.gov/EWA/gasProQueryAction.do",
    }
    
    session = requests.Session()
    session.mount("https://", RRCSSLAdapter())
    
    logger.info(f"Downloading {well_type} proration data...")
    response = session.get(urls[well_type], verify=False, timeout=120)
    response.raise_for_status()
    
    # Save to storage (GCS or local)
    remote_path = f"rrc-data/{well_type}_proration.csv"
    local_path = f"backend/data/rrc/{well_type}_proration.csv"
    
    with open(local_path, "wb") as f:
        f.write(response.content)
    
    storage.upload_file(local_path, remote_path)
    logger.info(f"Saved {well_type} data to {remote_path}")
    
    return local_path
```

### Step 3-4: Parse and Cache

```python
# backend/app/services/proration/csv_processor.py
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class RRCDataCache:
    """In-memory cache for RRC data (fast lookups)."""
    
    _oil_df: Optional[pd.DataFrame] = None
    _gas_df: Optional[pd.DataFrame] = None
    
    def load_csv(self, csv_path: str, well_type: str) -> int:
        """Load CSV into pandas DataFrame and cache."""
        df = pd.read_csv(csv_path, dtype=str)
        df = df.fillna("")  # Replace NaN with empty strings
        
        if well_type == "oil":
            self._oil_df = df
        else:
            self._gas_df = df
        
        logger.info(f"Cached {len(df)} {well_type} records")
        return len(df)
    
    def lookup_lease(
        self, lease_number: str, well_type: str
    ) -> Optional[dict]:
        """Fast lookup by lease number."""
        df = self._oil_df if well_type == "oil" else self._gas_df
        if df is None:
            return None
        
        result = df[df["lease_number"] == lease_number]
        if result.empty:
            return None
        
        return result.iloc[0].to_dict()
```

### Step 5: Sync to Firestore with Batching

```python
# backend/app/services/proration/rrc_data_service.py (continued)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud import firestore

def sync_to_firestore(csv_path: str, well_type: str) -> int:
    """
    Sync RRC CSV to Firestore with 500-doc batching.
    
    Returns:
        Number of documents synced
    """
    try:
        from google.cloud import firestore
        db = firestore.Client()
    except Exception as e:
        logger.warning(f"Firestore unavailable: {e}")
        return 0
    
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    records = df.to_dict("records")
    
    collection_name = f"rrc_data_{well_type}"
    batch = db.batch()
    batch_count = 0
    total_synced = 0
    
    for i, record in enumerate(records):
        doc_id = f"{record['lease_number']}_{record['operator_number']}"
        ref = db.collection(collection_name).document(doc_id)
        batch.set(ref, record)
        batch_count += 1
        
        # Commit every 500 documents
        if batch_count >= 500:
            batch.commit()
            total_synced += batch_count
            logger.info(f"Synced {total_synced}/{len(records)} {well_type} records")
            batch = db.batch()
            batch_count = 0
    
    # Commit remainder
    if batch_count > 0:
        batch.commit()
        total_synced += batch_count
    
    logger.info(f"Sync complete: {total_synced} {well_type} records")
    return total_synced
```

### Step 6: Update Status

```python
# backend/app/api/proration.py
from datetime import datetime
from app.services.firestore_service import FirestoreService

@router.post("/rrc/download")
async def download_rrc_data_endpoint(well_type: str = "oil"):
    # Download and sync
    csv_path = download_rrc_data(well_type)
    cache = RRCDataCache()
    csv_count = cache.load_csv(csv_path, well_type)
    db_count = sync_to_firestore(csv_path, well_type)
    
    # Update status tracking
    firestore = FirestoreService()
    await firestore.update_document(
        "rrc_status",
        well_type,
        {
            "last_download": datetime.utcnow().isoformat(),
            "csv_count": csv_count,
            "db_count": db_count,
        }
    )
    
    return {
        "well_type": well_type,
        "csv_count": csv_count,
        "db_count": db_count,
    }
```

### Validation

```bash
# Trigger download manually
curl -X POST http://localhost:8000/api/proration/rrc/download?well_type=oil

# Check logs for batch commits
# Should see: "Synced 500/10000 oil records", "Synced 1000/10000 oil records", etc.

# Verify Firestore (in GCP Console)
# Collection: rrc_data_oil
# Document count should match csv_count
```

**Iterate until pass:**
1. Download CSV → verify file exists locally and in GCS
2. Parse CSV → verify pandas DataFrame has expected columns
3. Sync to Firestore → verify batch commits logged every 500 docs
4. Check Firestore document count → should equal CSV row count
5. If batch fails, check Firestore quota limits and retry logic

---

## Adding Users to Allowlist

**Goal:** Grant access to a new user by adding their email to allowlist.

### Workflow Steps

```markdown
Copy this checklist and track progress:
- [ ] Step 1: Get user's Google email address
- [ ] Step 2: Add email to backend/data/allowed_users.json
- [ ] Step 3: Restart backend (or use admin API)
- [ ] Step 4: User signs in with Google
- [ ] Step 5: Verify user can access protected routes
```

### Manual Method (Local Dev)

```bash
# Step 1: Edit allowlist file
cd toolbox/backend/data
cat allowed_users.json
# {
#   "allowed_emails": ["james@tablerocktx.com"]
# }

# Step 2: Add new user
# Edit allowed_users.json to include new email
# {
#   "allowed_emails": [
#     "james@tablerocktx.com",
#     "newuser@tablerocktx.com"
#   ]
# }

# Step 3: Restart backend
cd ../..
make dev-backend
```

### Admin API Method (Production)

```python
# backend/app/api/admin.py
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import verify_firebase_token, load_allowed_users
import json
import os

router = APIRouter(prefix="/api/admin")

@router.post("/users")
async def add_user(
    email: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # Only admin can add users
    user = await verify_firebase_token(credentials.credentials)
    if user["email"] != "james@tablerocktx.com":
        raise HTTPException(status_code=403, detail="Admin only")
    
    # Load current allowlist
    path = "backend/data/allowed_users.json"
    with open(path) as f:
        data = json.load(f)
    
    # Add new email
    if email not in data["allowed_emails"]:
        data["allowed_emails"].append(email)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    return {"message": f"Added {email}", "allowed_emails": data["allowed_emails"]}
```

### Validation

```bash
# Test new user can access API
curl -H "Authorization: Bearer NEW_USER_TOKEN" \
  http://localhost:8000/api/health

# Should return 200, not 403
```

**Iterate until pass:**
1. Add email to allowlist
2. Restart backend (if manual method)
3. User signs in with Google → should succeed
4. User accesses protected route → should get 200, not 403
5. If 403 persists, check email matches exactly (case-sensitive)

---

## Frontend-to-Backend Auth Flow

**Goal:** Send authenticated API requests from React to FastAPI.

### Frontend Setup

```typescript
// frontend/src/lib/firebase.ts
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
```

### API Client with Auto-Refresh

```typescript
// frontend/src/utils/api.ts
import { auth } from '../lib/firebase';

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = '/api') {
    this.baseUrl = baseUrl;
  }

  private async getAuthToken(): Promise<string> {
    const user = auth.currentUser;
    if (!user) throw new Error('Not authenticated');
    
    // Firebase auto-refreshes tokens when expired
    const token = await user.getIdToken();
    return token;
  }

  async post<T>(endpoint: string, data: FormData | object): Promise<T> {
    const token = await this.getAuthToken();
    
    const headers: HeadersInit = {
      'Authorization': `Bearer ${token}`,
    };
    
    // Don't set Content-Type for FormData (browser handles it)
    if (!(data instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers,
      body: data instanceof FormData ? data : JSON.stringify(data),
    });
    
    if (response.status === 401) {
      // Token expired or invalid - force sign out
      await auth.signOut();
      throw new Error('Session expired. Please sign in again.');
    }
    
    if (response.status === 403) {
      throw new Error('Not authorized. Contact admin for access.');
    }
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'API request failed');
    }
    
    return response.json();
  }
}
```

### Usage in Component

```typescript
// frontend/src/pages/Extract.tsx
import { useState } from 'react';
import { ApiClient } from '../utils/api';

const api = new ApiClient();

export default function Extract() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const data = await api.post('/extract/upload', formData);
      setResult(data);
    } catch (err) {
      setError(err.message);
    }
  };

  return <div>{/* UI */}</div>;
}
```

---

## Testing Firebase Locally

**Goal:** Test Firebase Auth and Firestore without deploying to production.

### Local Emulator Setup (Optional)

```bash
# Install Firebase emulators
npm install -g firebase-tools

# Initialize Firebase in project
cd toolbox
firebase init emulators
# Select: Authentication, Firestore

# Start emulators
firebase emulators:start
```

### Test Without Emulator (Using Real Firebase)

```python
# backend/.env.development
GOOGLE_APPLICATION_CREDENTIALS=path/to/serviceAccount.json
GCS_BUCKET_NAME=table-rock-tools-storage-dev
FIRESTORE_ENABLED=true
```

```bash
# Run backend with real Firebase
cd toolbox
make dev-backend

# Test auth endpoint
curl http://localhost:8000/api/health
# Should return 200

# Frontend connects to real Firebase Auth
# (no emulator needed for Auth - it's client-side)
```

### Validation Checklist

```markdown
- [ ] Backend connects to Firestore (check logs for "Firestore client initialized")
- [ ] Frontend can sign in with Google (check browser console for auth state)
- [ ] API requests include Authorization header (check Network tab in DevTools)
- [ ] Backend verifies tokens (check backend logs for "User authenticated: email@example.com")
- [ ] 403 errors for unauthorized users (test with non-allowlisted email)