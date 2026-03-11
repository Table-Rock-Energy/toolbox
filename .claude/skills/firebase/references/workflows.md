# Firebase Workflows Reference

## Contents
- Add User to Allowlist
- Local Dev Without Firebase Credentials
- Troubleshoot 401/403 Errors
- Set User Password via Firebase Admin
- Startup: Allowlist Sync from Firestore

---

## Add User to Allowlist

**When:** A new user needs access to the application.

Use the admin API endpoint (preferred) or edit the JSON directly.

### Via Admin API (preferred)

```bash
# POST /api/admin/users — requires admin token
curl -X POST http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@tablerocktx.com",
    "first_name": "Jane",
    "last_name": "Doe",
    "role": "user",
    "scope": "land",
    "tools": ["extract", "title"]
  }'
```

This calls `add_allowed_user()` in `auth.py`, writes to JSON, and fires a background task to persist to Firestore.

### Via JSON (direct edit)

```bash
# backend/data/allowed_users.json — list of dicts, NOT {"allowed_users": [...]}
```

```json
[
  {"email": "james@tablerocktx.com", "role": "admin", "scope": "all", "tools": ["extract","title","proration","revenue"]},
  {"email": "newuser@tablerocktx.com", "first_name": "Jane", "last_name": "Doe", "role": "user", "scope": "land", "tools": ["extract","title"]}
]
```

Checklist:
- [ ] Add entry to `backend/data/allowed_users.json`
- [ ] Restart backend (or deploy) to pick up the change
- [ ] Verify: `GET /api/admin/users/{email}/check` returns `{"allowed": true}`
- [ ] For email/password auth: call `POST /api/admin/users/{email}/set-password` to create Firebase Auth account

---

## Local Dev Without Firebase Credentials

**When:** Running locally without `gcloud auth application-default login` or a service account key.

The backend starts fine — `get_firebase_app()` returns `None` and logs a warning. Token verification is skipped. Routes using `require_auth` will return 401 for all requests since `verify_firebase_token()` returns `None`.

### Option A: Disable auth check in dev (temporary)

```python
# backend/app/core/auth.py — verify_firebase_token() already handles this
async def verify_firebase_token(token: str) -> Optional[dict]:
    app = get_firebase_app()
    if app is None:
        # Firebase not configured — verification skipped
        logger.warning("Firebase not configured - skipping server-side verification")
        return None  # get_current_user returns None, require_auth 401s
    ...
```

To bypass auth entirely in dev, you need to either:

```bash
# Option A: Set up ADC
gcloud auth application-default login
```

```bash
# Option B: Use a service account key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/serviceAccountKey.json"
```

```bash
# Then start the backend
make dev-backend
```

### Option B: Disable Firestore to reduce startup noise

```bash
# backend/.env
FIRESTORE_ENABLED=false
```

This prevents Firestore connection errors without affecting Auth. Firebase Admin SDK init still requires credentials for token verification.

Checklist:
- [ ] `gcloud auth application-default login` OR set `GOOGLE_APPLICATION_CREDENTIALS`
- [ ] `make dev-backend` — confirm no Firebase errors in logs
- [ ] Sign in via frontend — confirm `Authorization` header appears in network tab
- [ ] Hit `/api/health` — returns 200

---

## Troubleshoot 401/403 Errors

### 401 Unauthorized

**Cause 1:** Missing `Authorization` header

```typescript
// Check in browser DevTools → Network → request headers
// Should see: Authorization: Bearer eyJhbGci...
// If missing: AuthContext didn't call api.setAuthToken()
```

Debug: Check `AuthContext.tsx` `onAuthStateChanged` — if `user` is null, `setAuthToken` never runs.

**Cause 2:** Expired token (sessions > 1 hour)

```typescript
// Force token refresh
const { getIdToken } = useAuth();
const token = await getIdToken();
if (token) api.setAuthToken(token);
```

**Cause 3:** Firebase Admin not initialized on backend

```bash
# Check backend logs for:
# "Firebase Admin SDK not initialized - running without server-side auth"
# Fix: gcloud auth application-default login
```

**Cause 4:** Token from wrong Firebase project

```python
# Backend verifies against project in Application Default Credentials
# Frontend config uses hardcoded projectId: "tablerockenergy"
# Mismatch = token rejected
```

### 403 Forbidden

**Cause:** Email not in allowlist

```bash
# Check the allowlist
cat backend/data/allowed_users.json | python3 -c "import json,sys; [print(u.get('email')) for u in json.load(sys.stdin)]"

# Or check via API
curl http://localhost:8000/api/admin/users/yourname@tablerocktx.com/check
```

Fix: Add email to allowlist (see above workflow).

Iterate-until-pass:
1. Identify error from backend logs or browser network tab
2. Apply fix from table above
3. Restart backend if you edited `allowed_users.json` directly
4. Re-test: sign out, sign in again, retry the failing request
5. Repeat if still failing

---

## Set User Password via Firebase Admin

**When:** Creating email/password auth for a new user who doesn't have Google Sign-In.

```bash
# POST /api/admin/users/{email}/set-password — admin only
curl -X POST http://localhost:8000/api/admin/users/newuser@tablerocktx.com/set-password \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "SecureP@ssword123"}'
```

This calls `set_user_password()` in `auth.py`:

```python
# auth.py — creates Firebase Auth user if not exists, or updates password
def set_user_password(email: str, password: str) -> dict:
    from firebase_admin import auth as fb_auth
    try:
        user = fb_auth.get_user_by_email(email)
        fb_auth.update_user(user.uid, password=password)
        return {"action": "updated", "email": email}
    except fb_auth.UserNotFoundError:
        fb_auth.create_user(email=email, password=password)
        return {"action": "created", "email": email}
```

Requires Firebase Admin SDK to be initialized. Requires the user to already be in the allowlist.

---

## Startup: Allowlist Sync from Firestore

`init_allowlist_from_firestore()` runs at app startup (`backend/app/main.py`). It:
1. Reads allowlist from Firestore collection `config/allowed_users`
2. If found, overwrites local `allowed_users.json` (migration: converts old `name` field to `first_name`/`last_name`)
3. If not found, seeds Firestore from the local JSON file

This means **Firestore is the source of truth in production**. Edits to the local JSON are overwritten on next startup unless Firestore is updated too. Always use the admin API to add/update users — it writes both JSON and Firestore.

```python
# Called at startup in main.py
@app.on_event("startup")
async def startup_event():
    await init_allowlist_from_firestore()
    ...
```

If Firestore is unavailable, startup logs a warning and falls back to the local JSON file.
