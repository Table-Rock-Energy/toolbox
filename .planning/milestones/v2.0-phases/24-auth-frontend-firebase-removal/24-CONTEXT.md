# Phase 24: Auth Frontend & Firebase Removal - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Rewrite frontend AuthContext to use local JWT auth (POST /api/auth/login, localStorage token, 401 refresh). Remove all Firebase imports, packages (firebase npm), and firebase.ts. Remove Google Sign-In button. Keep same Login page UI but call local API. npx tsc --noEmit must pass cleanly after all removals.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — infrastructure phase with UI changes limited to auth provider swap. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key research findings to incorporate:
- Pitfall 3: Firebase User object has displayName, photoURL, getIdToken() — new LocalUser interface needs equivalent fields
- AuthContext.tsx currently uses onAuthStateChanged listener — replace with token check on mount
- api.ts already has setAuthToken/clearAuthToken/setUnauthorizedHandler — reuse these
- 401 handler currently calls auth.currentUser.getIdToken(true) — replace with localStorage token read
- 4 files import from firebase/auth or ../lib/firebase: AuthContext.tsx, AdminSettings.tsx, Settings.tsx, firebase.ts
- Remove firebase.ts LAST after all imports are removed (get clean TypeScript errors first)
- Login page keeps email/password form, removes Google Sign-In button
- JWT stored in localStorage (access token) — no refresh token per STATE.md decisions (24h expiry)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/contexts/AuthContext.tsx` — Firebase auth state, user object, login/logout
- `frontend/src/utils/api.ts` — ApiClient with setAuthToken, clearAuthToken, setUnauthorizedHandler
- `frontend/src/lib/firebase.ts` — Firebase app + auth init (to be deleted)
- `frontend/src/pages/Login.tsx` — Login page with email/password + Google Sign-In

### Established Patterns
- AuthContext provides user, loading, login, logout via useAuth() hook
- ProtectedRoute checks useAuth() context
- api.ts interceptor handles 401 with unauthorized handler callback

### Integration Points
- AuthContext.tsx → remove Firebase, add fetch-based JWT
- Login.tsx → remove Google Sign-In, call POST /api/auth/login
- AdminSettings.tsx → remove Firebase password change, use local API
- Settings.tsx → remove Firebase imports
- api.ts 401 handler → read token from localStorage instead of Firebase getIdToken

</code_context>

<specifics>
## Specific Ideas

No specific requirements — keep existing UI layout, just swap auth provider.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
