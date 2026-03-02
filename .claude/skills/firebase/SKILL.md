---
name: firebase
description: |
  Integrates Firebase Auth with Google Sign-In and token verification for FastAPI backend and React frontend.
  Use when: implementing authentication, verifying ID tokens on backend, managing auth state in React, or configuring Firebase services
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Firebase Skill

Firebase provides authentication (Google Sign-In + email/password) and Firestore database for Table Rock Tools. The frontend uses Firebase Auth SDK v12, while the backend uses Firebase Admin SDK for token verification against a JSON allowlist (`data/allowed_users.json`).

## Quick Start

### Frontend: Initialize Firebase

```typescript
// toolbox/frontend/src/lib/firebase.ts
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  // ...other config
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
```

### Backend: Verify ID Token

```python
# toolbox/backend/app/core/auth.py
from firebase_admin import auth, credentials, initialize_app

# Lazy initialization to avoid import errors
_firebase_initialized = False

def verify_firebase_token(id_token: str) -> dict:
    global _firebase_initialized
    if not _firebase_initialized:
        initialize_app(credentials.ApplicationDefault())
        _firebase_initialized = True
    
    decoded_token = auth.verify_id_token(id_token)
    return decoded_token
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| **Lazy Initialization** | Import Firebase Admin only when needed | `if not _firebase_initialized: initialize_app()` |
| **ID Token Flow** | Frontend gets token → Backend verifies → Check allowlist | `const token = await user.getIdToken()` |
| **Allowlist** | JSON file of authorized emails | `data/allowed_users.json` |
| **Auth Context** | React Context for global auth state | `const { user } = useAuth()` |

## Common Patterns

### Google Sign-In (Frontend)

**When:** User clicks "Sign in with Google"

```typescript
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth';
import { auth } from '../lib/firebase';

async function handleGoogleSignIn() {
  const provider = new GoogleAuthProvider();
  try {
    const result = await signInWithPopup(auth, provider);
    const token = await result.user.getIdToken();
    // Send token to backend for verification
  } catch (error) {
    console.error('Sign-in failed:', error);
  }
}
```

### Protect API Routes (Backend)

**When:** Endpoint requires authenticated user

```python
from fastapi import Depends, HTTPException, Header
from app.core.auth import verify_firebase_token, is_user_allowed

async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.split("Bearer ")[1]
    decoded = verify_firebase_token(token)
    
    if not is_user_allowed(decoded["email"]):
        raise HTTPException(status_code=403, detail="User not authorized")
    
    return decoded

@router.post("/protected")
async def protected_endpoint(user: dict = Depends(get_current_user)):
    return {"message": f"Hello {user['email']}"}
```

### Auth State Management (Frontend)

**When:** Need global auth state across components

```typescript
// toolbox/frontend/src/contexts/AuthContext.tsx
import { createContext, useContext, useEffect, useState } from 'react';
import { onAuthStateChanged, User } from 'firebase/auth';
import { auth } from '../lib/firebase';

const AuthContext = createContext<{ user: User | null; loading: boolean }>(null!);

export function AuthProvider({ children }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    return onAuthStateChanged(auth, (user) => {
      setUser(user);
      setLoading(false);
    });
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

## See Also

- [patterns](references/patterns.md) - Token refresh, allowlist management, Firestore lazy init
- [workflows](references/workflows.md) - Add user to allowlist, deploy with new credentials, local dev without GCS

## Related Skills

- **react** - Auth context implementation, protected routes
- **typescript** - Firebase SDK types, async token handling
- **fastapi** - Dependency injection for auth, HTTPException patterns
- **python** - Lazy initialization, credential management
- **firestore** - Database operations with same Firebase project

## Documentation Resources

> Fetch latest Firebase documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "firebase"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Recommended Queries:**
- "firebase auth google sign-in react"
- "firebase admin sdk python token verification"
- "firebase auth get id token"