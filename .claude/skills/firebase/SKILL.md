All three files have been rewritten with accurate, codebase-grounded content. Key corrections made from the previous versions:

**SKILL.md:**
- Corrected: Firebase config is hardcoded (not env vars)
- Added the actual token injection pattern: set once in `onAuthStateChanged`, not per-request
- Documented the three auth dependency levels (`get_current_user`, `require_auth`, `require_admin`)

**references/patterns.md:**
- Corrected allowlist format: top-level list of dicts, not `{"allowed_users": [...]}`
- Documented `HTTPBearer` (not `Header(None)`) in `get_current_user`
- Corrected `get_firebase_app()` pattern: uses `firebase_admin.get_app()` check
- Added WARNING against per-request `getIdToken()` calls
- Added WARNING about frontend-only RBAC not being real security

**references/workflows.md:**
- Fixed all allowlist JSON examples to use correct format
- Added the Firestore-as-source-of-truth startup sync explanation (critical gotcha: local JSON gets overwritten on startup if Firestore has data)
- Accurate 401/403 troubleshooting matching the actual auth code
- Added `set_user_password()` workflow for email/password user setup