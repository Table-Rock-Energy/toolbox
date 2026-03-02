# Firebase Patterns Reference

## Contents
- Lazy Firestore Initialization
- Token Verification with Allowlist
- Firestore Service Layer
- Batch Document Syncing
- Frontend Auth Context
- Protected Routes

---

## Lazy Firestore Initialization

**Why:** Prevents crashes when GOOGLE_APPLICATION_CREDENTIALS is not set (local dev, testing).

### Backend Service Pattern

```python
# backend/app/services/firestore_service.py
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from google.cloud import firestore

class FirestoreService:
    _client: Optional[firestore.Client] = None
    
    def _get_client(self) -> firestore.Client:
        """Lazy-initialize Firestore client."""
        if self._client is None:
            from google.cloud import firestore
            self._client = firestore.Client()
        return self._client
    
    async def create_document(
        self, collection: str, doc_id: str, data: dict
    ) -> None:
        db = self._get_client()
        db.collection(collection).document(doc_id).set(data)
```

**DO:** Import inside functions, use TYPE_CHECKING for type hints  
**DON'T:** Import at module level (`from google.cloud import firestore` at top of file)

---

## Token Verification with Allowlist

**Why:** Backend must verify Firebase ID tokens AND check email against allowlist.

### Backend Auth Module

```python
# backend/app/core/auth.py
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer
import json
import os

# Lazy initialization
_app = None

def _init_firebase():
    global _app
    if _app is None:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            _app = firebase_admin.initialize_app(cred)
        else:
            _app = firebase_admin.initialize_app()
    return _app

def load_allowed_users() -> set[str]:
    """Load allowed emails from JSON file."""
    path = "backend/data/allowed_users.json"
    if not os.path.exists(path):
        return {"james@tablerocktx.com"}  # Default admin
    with open(path) as f:
        data = json.load(f)
        return set(data.get("allowed_emails", []))

async def verify_firebase_token(token: str) -> dict:
    """Verify Firebase ID token and check allowlist."""
    try:
        _init_firebase()
        decoded_token = auth.verify_id_token(token)
        email = decoded_token.get("email")
        
        allowed = load_allowed_users()
        if email not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"User {email} not authorized"
            )
        
        return {
            "uid": decoded_token["uid"],
            "email": email,
            "name": decoded_token.get("name", ""),
        }
    except firebase_admin.auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**DO:** Check both token validity AND allowlist membership  
**DON'T:** Trust tokens without verifying email authorization

### Route Handler Example

```python
# backend/app/api/extract.py
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import verify_firebase_token

router = APIRouter(prefix="/api/extract")
oauth2_scheme = HTTPBearer()

@router.post("/upload")
async def upload_extract(
    file: UploadFile,
    token: str = Depends(oauth2_scheme)
):
    user = await verify_firebase_token(token.credentials)
    # user["email"] is now verified and authorized
    # ... process upload
```

---

## Firestore Service Layer

**Why:** Centralize Firestore operations, handle errors gracefully, support optional Firestore.

### Full Service Implementation

```python
# backend/app/services/firestore_service.py
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any
import logging

if TYPE_CHECKING:
    from google.cloud import firestore

logger = logging.getLogger(__name__)

class FirestoreService:
    """Centralized Firestore operations with lazy initialization."""
    
    _client: Optional[firestore.Client] = None
    
    def _get_client(self) -> Optional[firestore.Client]:
        """Lazy-initialize Firestore client. Returns None if unavailable."""
        if self._client is None:
            try:
                from google.cloud import firestore
                self._client = firestore.Client()
                logger.info("Firestore client initialized")
            except Exception as e:
                logger.warning(f"Firestore unavailable: {e}")
                return None
        return self._client
    
    async def create_document(
        self, collection: str, doc_id: str, data: dict
    ) -> bool:
        """Create document. Returns False if Firestore unavailable."""
        db = self._get_client()
        if not db:
            return False
        try:
            db.collection(collection).document(doc_id).set(data)
            return True
        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            return False
    
    async def get_document(
        self, collection: str, doc_id: str
    ) -> Optional[dict]:
        """Get document. Returns None if not found or Firestore unavailable."""
        db = self._get_client()
        if not db:
            return None
        try:
            doc = db.collection(collection).document(doc_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            return None
    
    async def update_document(
        self, collection: str, doc_id: str, data: dict
    ) -> bool:
        """Update document. Returns False if Firestore unavailable."""
        db = self._get_client()
        if not db:
            return False
        try:
            db.collection(collection).document(doc_id).update(data)
            return True
        except Exception as e:
            logger.error(f"Failed to update document: {e}")
            return False
    
    async def query_documents(
        self, collection: str, filters: dict[str, Any]
    ) -> list[dict]:
        """Query documents. Returns empty list if Firestore unavailable."""
        db = self._get_client()
        if not db:
            return []
        try:
            query = db.collection(collection)
            for field, value in filters.items():
                query = query.where(field, "==", value)
            return [doc.to_dict() for doc in query.stream()]
        except Exception as e:
            logger.error(f"Failed to query documents: {e}")
            return []
```

**DO:** Return False/None on errors, log warnings, support optional Firestore  
**DON'T:** Crash the app if Firestore is unavailable

---

## Batch Document Syncing

**Why:** Syncing thousands of RRC records requires batching (Firestore limit: 500 ops/batch).

### RRC Data Sync Pattern

```python
# backend/app/services/proration/rrc_data_service.py
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from google.cloud import firestore

logger = logging.getLogger(__name__)

def sync_to_database(records: list[dict], well_type: str) -> int:
    """
    Sync RRC records to Firestore.
    
    Args:
        records: List of RRC records (up to 10,000+)
        well_type: "oil" or "gas"
    
    Returns:
        Number of records synced
    """
    try:
        from google.cloud import firestore
        db = firestore.Client()
    except Exception as e:
        logger.warning(f"Firestore unavailable: {e}")
        return 0
    
    collection_name = f"rrc_data_{well_type}"
    batch = db.batch()
    batch_count = 0
    total_synced = 0
    
    for i, record in enumerate(records):
        doc_id = f"{record['lease_number']}_{record['operator_number']}"
        ref = db.collection(collection_name).document(doc_id)
        batch.set(ref, record)
        batch_count += 1
        
        # Commit every 500 documents (Firestore limit)
        if batch_count >= 500:
            batch.commit()
            total_synced += batch_count
            logger.info(f"Synced {total_synced} {well_type} records")
            batch = db.batch()
            batch_count = 0
    
    # Commit remaining documents
    if batch_count > 0:
        batch.commit()
        total_synced += batch_count
        logger.info(f"Final sync: {total_synced} {well_type} records")
    
    return total_synced
```

**DO:** Track batch count, commit at 500, handle remainder  
**DON'T:** Assume all records fit in one batch

---

## Frontend Auth Context

**Why:** Centralize Firebase Auth state, provide user data to all components.

### AuthContext Implementation

```typescript
// frontend/src/contexts/AuthContext.tsx
import { 
  createContext, 
  useContext, 
  useEffect, 
  useState, 
  type ReactNode 
} from 'react';
import { 
  User, 
  onAuthStateChanged, 
  signInWithPopup, 
  signOut as firebaseSignOut,
  GoogleAuthProvider 
} from 'firebase/auth';
import { auth } from '../lib/firebase';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUser(user);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const signInWithGoogle = async () => {
    const provider = new GoogleAuthProvider();
    await signInWithPopup(auth, provider);
  };

  const signOut = async () => {
    await firebaseSignOut(auth);
  };

  return (
    <AuthContext.Provider value={{ user, loading, signInWithGoogle, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be inside AuthProvider');
  return context;
}
```

**DO:** Use onAuthStateChanged for real-time auth state  
**DON'T:** Poll for user state or manage manually

### Usage in Components

```typescript
// frontend/src/pages/Dashboard.tsx
import { useAuth } from '../contexts/AuthContext';

export default function Dashboard() {
  const { user, loading } = useAuth();
  
  if (loading) return <div>Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  
  return <div>Welcome, {user.displayName}</div>;
}
```

---

## Protected Routes

**Why:** Prevent unauthorized access to authenticated pages.

### ProtectedRoute Component

```typescript
// frontend/src/components/ProtectedRoute.tsx
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { LoadingSpinner } from './LoadingSpinner';
import type { ReactNode } from 'react';

interface ProtectedRouteProps {
  children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
```

### Router Setup

```typescript
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { MainLayout } from './layouts/MainLayout';
import { Login, Dashboard, Extract } from './pages';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/extract" element={<Extract />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

**DO:** Show loading state while checking auth  
**DON'T:** Flash login page before auth state resolves