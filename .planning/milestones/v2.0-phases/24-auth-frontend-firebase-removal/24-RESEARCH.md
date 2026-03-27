# Phase 24: Auth Frontend & Firebase Removal - Research

**Researched:** 2026-03-25
**Domain:** React auth context rewrite, Firebase SDK removal, JWT localStorage integration
**Confidence:** HIGH

## Summary

Phase 24 replaces the Firebase Auth frontend with a local JWT auth flow. The backend endpoints already exist (`POST /api/auth/login` returns `LoginResponse` with `access_token` + `UserProfile`, `GET /api/auth/me` returns `UserProfile`). The frontend must rewrite `AuthContext.tsx` to call these endpoints instead of Firebase, store the JWT in localStorage, and handle 401s by redirecting to login (no refresh token per STATE.md decisions).

The main complexity is the Firebase `User` object used across 14 files. The `User` type provides `displayName`, `photoURL`, `uid`, `email`, `getIdToken()`, `providerData`, and `reload()`. A new `LocalUser` interface must cover these properties using data from the `/api/auth/me` response. The `Settings.tsx` page has the deepest Firebase dependency (password change via `reauthenticateWithCredential` + `updatePassword`, profile update via `updateProfile`, photo upload using `user.uid`).

**Primary recommendation:** Define a `LocalUser` interface mapping to backend `UserProfile` response. Rewrite `AuthContext.tsx` to use `POST /api/auth/login` + localStorage JWT. Update Settings.tsx password change to call a backend API. Remove Google Sign-In from Login.tsx. Delete `firebase.ts` and `npm uninstall firebase` last.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None explicit -- all implementation choices at Claude's discretion per infrastructure phase.

### Claude's Discretion
All implementation choices are at Claude's discretion -- infrastructure phase with UI changes limited to auth provider swap. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key research findings to incorporate:
- Pitfall 3: Firebase User object has displayName, photoURL, getIdToken() -- new LocalUser interface needs equivalent fields
- AuthContext.tsx currently uses onAuthStateChanged listener -- replace with token check on mount
- api.ts already has setAuthToken/clearAuthToken/setUnauthorizedHandler -- reuse these
- 401 handler currently calls auth.currentUser.getIdToken(true) -- replace with localStorage token read
- 4 files import from firebase/auth or ../lib/firebase: AuthContext.tsx, AdminSettings.tsx, Settings.tsx, firebase.ts
- Remove firebase.ts LAST after all imports are removed (get clean TypeScript errors first)
- Login page keeps email/password form, removes Google Sign-In button
- JWT stored in localStorage (access token) -- no refresh token per STATE.md decisions (24h expiry)

### Deferred Ideas (OUT OF SCOPE)
None -- discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-05 | Frontend uses local auth context with JWT storage, 401 refresh, and logout (replacing Firebase AuthContext) | LocalUser interface, AuthContext rewrite pattern, api.ts 401 handler reuse |
| AUTH-06 | All Firebase imports, packages (frontend firebase npm + backend firebase-admin), and firebase.ts are removed | 4 frontend files with Firebase imports identified, deletion order documented |
| AUTH-07 | Google Sign-In provider removed -- email/password authentication only | Login.tsx Google button + divider removal, AuthContext signInWithGoogle removal |
</phase_requirements>

## Architecture Patterns

### Current Firebase Auth Flow (to be replaced)
```
Firebase Auth SDK → onAuthStateChanged listener → Firebase User object
→ user.getIdToken() → Bearer token → backend verifies Firebase token
→ checkAuthorization() → /api/admin/users/{email}/check → role/admin data
```

### New Local JWT Auth Flow
```
POST /api/auth/login {email, password} → {access_token, user: UserProfile}
→ store token in localStorage → set on ApiClient via api.setAuthToken()
→ AuthContext provides LocalUser from login response
→ On mount: read token from localStorage → GET /api/auth/me → restore user
→ On 401: clear token, redirect to /login with session-expired message
```

### LocalUser Interface Design

The Firebase `User` type properties used across the codebase:

| Firebase Property | Used In | LocalUser Equivalent | Source |
|-------------------|---------|---------------------|--------|
| `user.email` | 8 files (Settings, Login, tool pages, Sidebar) | `email: string` | LoginResponse.user.email |
| `user.displayName` | Sidebar, Settings, tool pages (fallback after userName) | `displayName: string \| null` | Computed from `first_name + last_name` |
| `user.photoURL` | Sidebar, Settings | `photoURL: string \| null` | Not in current backend -- hardcode `null` initially |
| `user.uid` | useToolLayout (localStorage key), Settings photo upload | `id: string` | Use email as stable ID (or add `id` to UserProfile) |
| `user.getIdToken()` | AuthContext, Settings authHeaders | Replaced by `getToken(): string \| null` (synchronous from localStorage) |
| `user.providerData` | Settings (isGoogleUser check) | Remove -- no Google auth |
| `user.reload()` | Settings (after profile/photo update) | Replace with re-fetch `/api/auth/me` |

```typescript
interface LocalUser {
  email: string
  displayName: string | null
  photoURL: string | null
  id: string  // email used as stable ID for localStorage keys
}
```

### AuthContext Rewrite Pattern

```typescript
// New AuthContextType -- changes from current
interface AuthContextType {
  user: LocalUser | null          // Was: Firebase User | null
  userName: string | null         // Keep as-is
  loading: boolean                // Keep as-is
  isAuthorized: boolean           // Simplified: true if logged in
  isAdmin: boolean                // Keep from login response
  userRole: string | null         // Keep from login response
  userScope: string | null        // Keep from login response
  userTools: string[]             // Keep from login response
  authError: string | null        // Keep as-is
  backendReachable: boolean       // Keep health check
  signInWithEmail: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  getToken: () => string | null   // Was: getIdToken() async
  // REMOVED: signInWithGoogle, getIdToken
}
```

### Key Implementation Details

**Login flow:**
1. `signInWithEmail` calls `POST /api/auth/login` with `{email, password}`
2. On success: store `access_token` in `localStorage('auth_token')`, build `LocalUser` from response
3. Call `api.setAuthToken(token)` to set Bearer header on all API calls
4. Set `isAuthorized=true`, populate role/admin/tools from response

**Mount/refresh flow:**
1. On mount: read token from `localStorage('auth_token')`
2. If token exists: call `api.setAuthToken(token)`, then `GET /api/auth/me`
3. If `/me` succeeds: build `LocalUser`, set authorized
4. If `/me` returns 401: clear token, set unauthorized (expired session)

**401 handler:**
1. `api.setUnauthorizedHandler` callback: clear localStorage token, set `authError` to session-expired message, set `user=null`
2. No refresh attempt (no refresh tokens per STATE.md)
3. ProtectedRoute redirects to `/login`

**Logout flow:**
1. Clear localStorage token
2. Call `api.clearAuthToken()`
3. Set `user=null`, `isAuthorized=false`

### Files to Modify (ordered)

| File | Change | Firebase Deps |
|------|--------|---------------|
| `contexts/AuthContext.tsx` | Full rewrite: LocalUser, JWT localStorage, POST /api/auth/login | `firebase/auth`, `../lib/firebase` |
| `pages/Login.tsx` | Remove Google Sign-In button + "or" divider, remove `signInWithGoogle` | None (uses AuthContext) |
| `pages/Settings.tsx` | Replace Firebase password change with backend API, remove `updateProfile`/`updatePassword`/`reauthenticateWithCredential`, replace `user.uid` with `user.id`, replace `user.providerData` check | `firebase/auth` (4 imports) |
| `pages/AdminSettings.tsx` | Remove Firebase password text reference (line 1316 only), cosmetic | None (text-only reference) |
| `components/Sidebar.tsx` | `user.photoURL` and `user.displayName` already work if LocalUser has same property names | None |
| `hooks/useToolLayout.ts` | Change `userId: string \| undefined` -- callers pass `user?.id` instead of `user?.uid` | None |
| Tool pages (Extract, Title, Proration, Revenue, GhlPrep) | Change `user?.uid` to `user?.id`, `user?.displayName` works as-is | None |
| `lib/firebase.ts` | DELETE entirely | Firebase SDK |
| `package.json` | `npm uninstall firebase` | Firebase npm pkg |

### Settings.tsx Password Change Replacement

Current flow: Firebase `reauthenticateWithCredential` + `updatePassword` (client-side).

New flow: `POST /api/auth/change-password` (backend needs this endpoint added or use existing admin password update).

**Backend gap:** No `change-password` endpoint exists. Options:
1. Add `POST /api/auth/change-password` accepting `{current_password, new_password}` -- clean, self-service
2. Use the admin user update endpoint -- but that doesn't verify current password

**Recommendation:** Add a minimal `POST /api/auth/change-password` endpoint to `backend/app/api/auth.py`. It verifies the current password, hashes the new one, and updates the user record. This is a small backend addition that keeps the Settings page functional.

### Settings.tsx Profile Update Replacement

Current flow: Firebase `updateProfile(user, { displayName })` + `user.reload()`.

New flow: `PUT /api/admin/users/{email}` already exists and can update `first_name`/`last_name`. After success, re-fetch `/api/auth/me` to update context.

### Settings.tsx Photo Upload

Current flow: Upload to backend, get URL, then `updateProfile(user, { photoURL })`.

New flow: Upload to backend (keep as-is), backend stores URL. The `LocalUser.photoURL` comes from backend profile data. Add `photo_url` to the `UserProfile` response, or defer photo feature (it's minor for internal tool).

**Recommendation:** Simplify -- keep photo upload backend call, add `photo_url` to `UserProfile` response model if the backend stores it. If not stored, drop photo display temporarily (internal tool, low priority).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token storage | Custom encryption/session | Plain localStorage | 24h expiry, internal tool, HTTPS only in prod |
| Token refresh | Refresh token rotation | Redirect to login on 401 | STATE.md decision: no refresh tokens |
| Auth state sync across tabs | BroadcastChannel listener | Single tab assumption | Internal tool, 1-2 users |

## Common Pitfalls

### Pitfall 1: Firebase User Properties Silently Undefined
**What goes wrong:** Components access `user.displayName`, `user.photoURL`, `user.uid` -- if LocalUser interface uses different names (`display_name`, `photo_url`, `id`), TypeScript catches it. But if the interface names match but values are `null`/`undefined`, the UI shows blanks.
**How to avoid:** Use identical property names in `LocalUser` (`displayName`, `photoURL`, `email`). Compute `displayName` from `first_name + last_name` at login/me response time, not in each component.

### Pitfall 2: getIdToken Was Async, getToken Is Sync
**What goes wrong:** 6 files call `getIdToken()` which returns `Promise<string | null>`. The new `getToken()` reads from localStorage synchronously. Every call site that `await`s the result needs updating.
**How to avoid:** Keep `getToken` returning `string | null` (synchronous). Update call sites: Settings.tsx `authHeaders()` callback, AdminSettings.tsx, Dashboard.tsx, MineralRights.tsx, GhlSendModal.tsx. The `await` on a sync value is harmless in JS but signals dead code.

### Pitfall 3: useToolLayout localStorage Keys Change
**What goes wrong:** `useToolLayout` uses `user?.uid` for localStorage keys. If `user.id` (email) is used instead, all existing localStorage entries become orphaned and user preferences reset.
**How to avoid:** Accept this one-time reset as harmless (internal tool, 1-2 users) or use email consistently (it was the stable identifier anyway).

### Pitfall 4: 401 Handler Infinite Loop
**What goes wrong:** The current api.ts 401 handler tries to refresh and retry. Without refresh tokens, the handler must NOT retry -- it should clear state and return false. If it retries, it hits 401 again, creating a loop.
**How to avoid:** The 401 handler should: (1) clear localStorage token, (2) clear ApiClient token, (3) return false. No retry attempt.

### Pitfall 5: Settings.tsx Has Multiple Firebase Imports
**What goes wrong:** Settings.tsx imports `updatePassword`, `updateProfile`, `EmailAuthProvider`, `reauthenticateWithCredential` from `firebase/auth`. Removing these without replacing the password change functionality leaves the Security section broken.
**How to avoid:** Replace password change with backend API call BEFORE removing Firebase imports. The profile save can use the admin user update endpoint.

### Pitfall 6: AdminSettings Firebase Text Reference
**What goes wrong:** Line 1316 of AdminSettings.tsx has a help text string mentioning "Creates a Firebase account". This is just a string, not an import, but it should be updated for accuracy.
**How to avoid:** Change text to "Sets an initial password for email/password sign-in" or similar.

## Code Examples

### AuthContext Login Implementation
```typescript
// POST /api/auth/login → store token + build LocalUser
const signInWithEmail = async (email: string, password: string) => {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) {
    const data = await response.json()
    throw new Error(data.detail || 'Login failed')
  }
  const data = await response.json()  // LoginResponse
  localStorage.setItem('auth_token', data.access_token)
  api.setAuthToken(data.access_token)
  const localUser: LocalUser = {
    email: data.user.email,
    displayName: [data.user.first_name, data.user.last_name].filter(Boolean).join(' ') || null,
    photoURL: null,
    id: data.user.email,
  }
  setUser(localUser)
  setIsAuthorized(true)
  setIsAdmin(data.user.is_admin)
  setUserRole(data.user.role)
  setUserScope(data.user.scope)
  setUserTools(data.user.tools)
  setUserName(localUser.displayName)
}
```

### Mount Token Restoration
```typescript
useEffect(() => {
  const restoreSession = async () => {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      setLoading(false)
      return
    }
    api.setAuthToken(token)
    try {
      const response = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!response.ok) throw new Error('Token expired')
      const profile = await response.json()  // UserProfile
      // Build LocalUser from profile...
    } catch {
      localStorage.removeItem('auth_token')
      api.clearAuthToken()
    }
    setLoading(false)
  }
  restoreSession()
}, [])
```

### 401 Handler (No Retry)
```typescript
api.setUnauthorizedHandler(async () => {
  localStorage.removeItem('auth_token')
  api.clearAuthToken()
  setUser(null)
  setIsAuthorized(false)
  setAuthError('Your session has expired. Please sign in again.')
  return false  // Do NOT retry
})
```

### Settings Password Change (Backend API)
```typescript
const handlePasswordChange = async (e: React.FormEvent) => {
  e.preventDefault()
  // Validate newPassword === confirmPassword, length >= 8
  const response = await fetch(`${API_BASE}/auth/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
  if (!response.ok) {
    const data = await response.json()
    setPasswordError(data.detail || 'Failed to update password')
    return
  }
  setPasswordSuccess('Password updated successfully!')
}
```

## Backend Gap: Change Password Endpoint

The backend `auth.py` has `login` and `me` but no `change-password`. This endpoint is needed for Settings.tsx password change functionality.

```python
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == user["email"]))
    db_user = result.scalar_one_or_none()
    if not db_user or not verify_password(body.current_password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    db_user.password_hash = get_password_hash(body.new_password)
    await db.commit()
    return {"message": "Password updated"}
```

## Firebase Removal Checklist

Ordered to preserve TypeScript compilation at each step:

1. Rewrite `AuthContext.tsx` (remove all Firebase imports, add LocalUser)
2. Update `Login.tsx` (remove Google Sign-In button, remove signInWithGoogle)
3. Update `Settings.tsx` (replace Firebase password/profile with backend API)
4. Update `AdminSettings.tsx` (fix help text string)
5. Update tool pages (change `user?.uid` to `user?.id` -- 5 files)
6. Update `Sidebar.tsx` (user properties already match if LocalUser uses same names)
7. Run `npx tsc --noEmit` -- should show only `firebase.ts` as unused import source
8. Delete `frontend/src/lib/firebase.ts`
9. Run `npm uninstall firebase` from `frontend/`
10. Run `npx tsc --noEmit` -- must pass clean
11. Verify `npm run build` succeeds

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && python3 -m pytest tests/test_auth.py -x -q` |
| Full suite command | `cd backend && python3 -m pytest -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-05 | Frontend login, token persistence, 401 redirect | manual | Open browser, login, refresh, wait for expiry | N/A (no frontend tests) |
| AUTH-05 | Backend /auth/change-password endpoint | unit | `cd backend && python3 -m pytest tests/test_auth.py -x -q` | Needs new test |
| AUTH-06 | No Firebase imports in frontend | smoke | `cd frontend && npx tsc --noEmit && ! grep -r 'firebase' src/` | N/A (CLI check) |
| AUTH-07 | No Google Sign-In in UI | manual | Visual inspection of Login page | N/A |

### Sampling Rate
- **Per task commit:** `cd frontend && npx tsc --noEmit` (catches type errors from Firebase removal)
- **Per wave merge:** `cd backend && python3 -m pytest -v` + `cd frontend && npm run build`
- **Phase gate:** Full suite green + `npx tsc --noEmit` + `grep -r firebase frontend/src/` returns nothing

### Wave 0 Gaps
- [ ] `backend/tests/test_auth.py` -- add test for `POST /api/auth/change-password` endpoint
- [ ] No frontend test infrastructure exists (documented in CLAUDE.md) -- rely on TypeScript compilation + manual testing

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of all 14 files using `useAuth()` hook
- Direct analysis of `AuthContext.tsx` (233 lines, full Firebase dependency map)
- Direct analysis of `Settings.tsx` (641 lines, deepest Firebase integration)
- Direct analysis of `backend/app/api/auth.py` (existing login/me endpoints)
- Direct analysis of `backend/app/core/security.py` (JWT creation/verification)
- Direct analysis of `api.ts` (401 handler, setAuthToken/clearAuthToken pattern)

### Secondary (MEDIUM confidence)
- STATE.md decisions: 24h JWT expiry, no refresh tokens
- PITFALLS.md Pitfall 3: JWT token shape differs from Firebase token

## Metadata

**Confidence breakdown:**
- Architecture: HIGH - direct codebase analysis, backend endpoints already exist
- Firebase dependency map: HIGH - grep-verified across entire frontend/src
- Password change gap: HIGH - confirmed no endpoint exists in backend
- Pitfalls: HIGH - based on actual property usage analysis across 14 files

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable internal codebase)
