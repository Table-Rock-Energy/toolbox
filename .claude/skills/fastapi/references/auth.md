# Auth Reference

## Contents
- Firebase Token Verification
- JSON Allowlist Pattern
- Lazy Firebase Admin Init
- Dependency Injection for Protected Routes
- Admin Management Endpoints

## Firebase Token Verification

### Lazy Firebase Admin SDK Initialization

```python
# toolbox/backend/app/core/auth.py
_firebase_app = None

def get_firebase_app():
    """Get or initialize Firebase Admin SDK."""
    global _firebase_app
    if _firebase_app is None:
        try:
            import firebase_admin
            from firebase_admin import credentials
            
            try:
                # Try to get existing app
                _firebase_app = firebase_admin.get_app()
            except ValueError:
                # Initialize with Application Default Credentials (Cloud Run)
                try:
                    _firebase_app = firebase_admin.initialize_app()
                except Exception:
                    logger.warning("Firebase Admin SDK not initialized - running without server-side auth")
                    return None
        except ImportError:
            logger.warning("firebase-admin not installed")
            return None
    return _firebase_app

async def verify_firebase_token(token: str) -> Optional[dict]:
    """Verify a Firebase ID token and return decoded token."""
    app = get_firebase_app()
    if app is None:
        # Fall back to client-side only auth in dev
        logger.warning("Firebase not configured - skipping server-side verification")
        return None
    
    try:
        from firebase_admin import auth
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None
```

**WHY:** App runs in dev without Firebase credentials, gracefully degrades to client-side auth only. Production uses Application Default Credentials (Cloud Run service account).

**WARNING: Don't Fail Startup If Firebase Unavailable**

```python
# BAD - Crashes app startup
import firebase_admin
firebase_admin.initialize_app()  # WRONG - fails if credentials missing
```

**WHY THIS BREAKS:** Local dev without GCP credentials can't start app. Always use lazy init with try/except.

## JSON Allowlist Pattern

### File-Based User Authorization

```python
# toolbox/backend/app/core/auth.py
ALLOWLIST_FILE = Path(__file__).parent.parent.parent / "data" / "allowed_users.json"

DEFAULT_ALLOWED_USERS = ["james@tablerocktx.com"]

def load_allowlist() -> list[str]:
    """Load allowed users from file, or return defaults."""
    if ALLOWLIST_FILE.exists():
        try:
            with open(ALLOWLIST_FILE, "r") as f:
                data = json.load(f)
                # Handle both string and dict formats
                return [u.get("email", u) if isinstance(u, dict) else u for u in data]
        except Exception as e:
            logger.error(f"Error loading allowlist: {e}")
    return DEFAULT_ALLOWED_USERS.copy()

def save_allowlist(users: list[dict]) -> None:
    """Save allowed users to file."""
    ALLOWLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALLOWLIST_FILE, "w") as f:
        json.dump(users, f, indent=2)

def is_user_allowed(email: str) -> bool:
    """Check if user is in allowlist."""
    allowed = load_allowlist()
    return email.lower() in [e.lower() for e in allowed]
```

**WHY:** Simple authorization without database dependency. Primary admin `james@tablerocktx.com` always allowed (hardcoded default).

### DO: Normalize Email Comparisons

```python
# GOOD - Case-insensitive email matching
return email.lower() in [e.lower() for e in allowed]
```

**WHY:** Email addresses are case-insensitive per RFC. User might sign in as `James@TableRockTX.com` but allowlist has `james@tablerocktx.com`.

### DON'T: Remove Primary Admin

```python
# GOOD - Protect primary admin
# toolbox/backend/app/api/admin.py
@router.delete("/users/{email}")
async def remove_user(email: str):
    if email.lower() == "james@tablerocktx.com":
        raise HTTPException(status_code=400, detail="Cannot remove primary admin user")
    
    success = remove_allowed_user(email)
    if not success:
        raise HTTPException(status_code=404, detail=f"User {email} not found")
    
    return {"message": f"User {email} removed"}
```

**WHY:** Prevents lockout. Primary admin removal requires direct file edit (intentionally harder).

## Dependency Injection for Protected Routes

### Optional Auth Dependency

```python
# toolbox/backend/app/core/auth.py
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """Get current authenticated user. Returns None if unauthenticated."""
    if credentials is None:
        return None
    
    token = credentials.credentials
    decoded = await verify_firebase_token(token)
    
    if decoded is None:
        # Development: Firebase Admin not configured
        return None
    
    # Check allowlist
    email = decoded.get("email")
    if email and not is_user_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized to access this application"
        )
    
    return decoded

async def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    """Require authentication for a route."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user
```

**WHY:** `auto_error=False` allows routes without auth. `require_auth` dependency enforces auth. Separation of concerns.

### DO: Use Dependency for Protected Endpoints

```python
# GOOD - Auth required
@router.get("/protected-data")
async def get_protected_data(user: dict = Depends(require_auth)):
    return {"user_email": user.get("email"), "data": "sensitive"}

# GOOD - Optional auth
@router.get("/public-data")
async def get_public_data(user: Optional[dict] = Depends(get_current_user)):
    if user:
        return {"message": f"Hello {user.get('email')}"}
    return {"message": "Hello guest"}
```

**WHY:** Declarative auth enforcement, easy to see which routes require auth, testable by mocking dependency.

### DON'T: Check Auth Manually in Every Route

```python
# BAD - Repetitive, error-prone
@router.get("/protected")
async def get_protected(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="No auth")
    
    token = auth_header.replace("Bearer ", "")
    decoded = await verify_firebase_token(token)
    if not decoded:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # WRONG - duplicated in every route
```

**WHY THIS BREAKS:** Auth logic scattered across routes, easy to forget, hard to update (e.g., adding allowlist check).

## Admin Management Endpoints

### Allowlist CRUD Operations

```python
# toolbox/backend/app/api/admin.py
class AddUserRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None

@router.post("/users", response_model=UserResponse)
async def add_user(request: AddUserRequest):
    """Add user to allowlist."""
    success = add_allowed_user(
        email=request.email,
        name=request.name,
        added_by="admin"  # In production, get from auth context
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=f"User {request.email} already in allowlist")
    
    logger.info(f"Added user to allowlist: {request.email}")
    return UserResponse(email=request.email.lower(), name=request.name, added_by="admin")

@router.get("/users/{email}/check")
async def check_user(email: str):
    """Check if user is authorized."""
    allowed = is_user_allowed(email)
    return {"email": email, "allowed": allowed}
```

**WHY:** Admin can add users via API without editing JSON file manually. Check endpoint useful for debugging auth issues.

### DO: Use Pydantic EmailStr for Validation

```python
# GOOD - Built-in email validation
class AddUserRequest(BaseModel):
    email: EmailStr  # Validates email format
    name: Optional[str] = None
```

**WHY:** Rejects invalid emails (missing @, malformed domain) before hitting database/storage.

### DON'T: Trust User Input Without Validation

```python
# BAD - No email validation
@router.post("/users")
async def add_user(email: str, name: str):
    add_allowed_user(email, name)  # WRONG - could be "not-an-email"
```

**WHY THIS BREAKS:** Invalid emails in allowlist break auth checks, hard to debug (silently fail to match).