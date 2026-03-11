# Firebase Patterns Reference

## Contents
- Allowlist Format and Management
- Backend Auth Dependencies
- Firebase Admin SDK Lazy Init
- Frontend Auth Flow (onAuthStateChanged)
- Error Code Handling
- Anti-Patterns

---

## Allowlist Format and Management

The allowlist is a **list of dicts** stored in `backend/data/allowed_users.json`. Firestore is the source of truth; the JSON file is a local cache synced on startup.

```json
[
  {
    "email": "james@tablerocktx.com",
    "first_name": "James",
    "last_name": "Smith",
    "role": "admin",
    "scope": "all",
    "tools": ["extract", "title", "proration", "revenue"]
  },
  {
    "email": "user@tablerocktx.com",
    "role": "user",
    "scope": "land",
    "tools": ["extract", "title"]
  }
]
```

Available roles: `admin`, `user`, `viewer`
Available scopes: `all`, `land`, `revenue`, `operations`
Available tools: `extract`, `title`, `proration`, `revenue`

```python
# backend/app/core/auth.py — load/check pattern
def load_allowlist() -> list[str]:
    """Returns list of allowed email strings (lowercased)."""
    if ALLOWLIST_FILE.exists():
        with open(ALLOWLIST_FILE) as f:
            data = json.load(f)  # list of dicts
            return [u.get("email", u) if isinstance(u, dict) else u for u in data]
    return DEFAULT_ALLOWED_USERS.copy()

def is_user_allowed(email: str) -> bool:
    allowed = load_allowlist()
    return email.lower() in [e.lower() for e in allowed]
```

### WARNING: Wrong Allowlist JSON Format

**The Problem:**

```json
// BAD — this is NOT the actual format
{ "allowed_users": ["james@tablerocktx.com"] }
```

**Why This Breaks:** `load_allowlist()` calls `json.load()` and expects a top-level list. A dict format will cause a `TypeError` on the list comprehension.

**The Fix:** Always write a top-level JSON array of user dicts.

---

## Backend Auth Dependencies

Three dependency levels in `backend/app/core/auth.py`:

```python
# get_current_user — soft auth, user may be None
# Use for endpoints that work for both authenticated and unauthenticated users
@router.get("/public-data")
async def get_data(user: Optional[dict] = Depends(get_current_user)):
    if user:
        return full_response
    return limited_response

# require_auth — hard auth, 401 if missing/invalid token
# Use for all tool endpoints (upload, export, etc.)
@router.post("/upload")
async def upload(user: dict = Depends(require_auth)):
    email = user.get("email")  # guaranteed present and in allowlist
    ...

# require_admin — admin only, 403 if not admin role
# Use for /api/admin/* endpoints
@router.post("/admin/users")
async def add_user(user: dict = Depends(require_admin)):
    ...
```

The dependency chain is: `require_admin` → `require_auth` → `get_current_user`. Don't use `get_current_user` directly when you need guaranteed auth.

```python
# get_current_user uses HTTPBearer, not Header(None)
security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    if credentials is None:
        return None
    token = credentials.credentials
    decoded = await verify_firebase_token(token)
    ...
```

---

## Firebase Admin SDK Lazy Init

```python
# backend/app/core/auth.py
_firebase_app = None

def get_firebase_app():
    """Get or initialize Firebase Admin SDK (lazy)."""
    global _firebase_app
    if _firebase_app is None:
        try:
            import firebase_admin
            try:
                _firebase_app = firebase_admin.get_app()  # Already initialized?
            except ValueError:
                # Not yet initialized — use Application Default Credentials
                _firebase_app = firebase_admin.initialize_app()
        except ImportError:
            logger.warning("firebase-admin not installed")
            return None
    return _firebase_app
```

When `get_firebase_app()` returns `None`, `verify_firebase_token()` returns `None` (not an error), and `get_current_user()` returns `None`. Routes using `require_auth` will then 401. This is intentional — the backend degrades gracefully when Firebase Admin isn't configured.

### WARNING: Initializing Firebase Admin at Module Level

**The Problem:**

```python
# BAD — top-level import causes crash if credentials not present
import firebase_admin
firebase_admin.initialize_app()  # Crashes on import in local dev
```

**Why This Breaks:** When `GOOGLE_APPLICATION_CREDENTIALS` isn't set and gcloud ADC isn't configured, this raises `DefaultCredentialsError` at startup, preventing the entire FastAPI app from starting.

**The Fix:** Use `get_firebase_app()` pattern — lazy init inside a function, never at module level.

---

## Frontend Auth Flow (onAuthStateChanged)

Token is injected into `ApiClient` **once** when auth state changes, not refreshed per request:

```typescript
// AuthContext.tsx — the actual pattern
useEffect(() => {
  const unsubscribe = onAuthStateChanged(auth, async (user) => {
    setUser(user);
    if (user?.email) {
      try {
        const token = await user.getIdToken();
        api.setAuthToken(token);  // Sets Authorization header on ApiClient
      } catch {
        // Token not available yet, retry on next state change
      }
      const authData = await checkAuthorization(user.email);
      // ... set isAuthorized, isAdmin, userTools
    } else {
      api.clearAuthToken();  // Remove header on sign-out
    }
  });
  return () => unsubscribe();
}, []);
```

Firebase ID tokens expire after 1 hour. The token set in `ApiClient` can go stale. For long-running sessions, call `getIdToken()` directly when you need a fresh token:

```typescript
const { getIdToken } = useAuth();

// For sensitive operations or when you need a guaranteed-fresh token
const freshToken = await getIdToken();
if (freshToken) {
  api.setAuthToken(freshToken);
}
```

---

## Error Code Handling

```typescript
// AuthContext.tsx — signInWithEmail maps Firebase codes to user messages
const firebaseError = error as { code?: string };
switch (firebaseError.code) {
  case 'auth/user-not-found':
    throw new Error('No account found with this email address.');
  case 'auth/wrong-password':
  case 'auth/invalid-credential':
    throw new Error('Invalid email or password.');
  case 'auth/invalid-email':
    throw new Error('Invalid email address.');
  case 'auth/too-many-requests':
    throw new Error('Too many failed attempts. Please try again later.');
  default:
    throw new Error('Login failed. Please try again.');
}
```

NEVER surface raw Firebase error codes to users — they expose implementation details and are confusing. Always map to user-friendly messages.

---

## Anti-Patterns

### WARNING: Calling getIdToken() Per Request

**The Problem:**

```typescript
// BAD — unnecessary async overhead on every fetch
async function fetchData() {
  const user = auth.currentUser;
  const token = await user.getIdToken();  // Network call each time
  return fetch('/api/data', {
    headers: { Authorization: `Bearer ${token}` }
  });
}
```

**Why This Breaks:** `getIdToken()` makes a network request when the token is expired. Calling it per request adds latency on every API call.

**The Fix:** Use `api.setAuthToken()` once in `onAuthStateChanged`. For genuinely sensitive operations where staleness matters, call `user.getIdToken(true)` to force-refresh explicitly.

### WARNING: Allowlist Check Only on Frontend

**The Problem:**

```typescript
// BAD — frontend-only RBAC is not security
if (userTools.includes('proration')) {
  // Show proration UI
  // But backend still serves the data to anyone!
}
```

**Why This Breaks:** Frontend RBAC is UI-only. Nothing stops a user from hitting `/api/proration/upload` directly. Backend `require_auth` verifies the allowlist, but doesn't check tool scope.

**The Fix:** Frontend checks control UI visibility. Backend checks (`require_auth`) enforce authentication. For strict tool-level authorization, add scope checking in the route handler using the decoded token's email + `get_user_by_email()`.
