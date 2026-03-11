The skill files are updated. Here's what changed:

**SKILL.md** — Rewrote to reflect the actual codebase:
- **Auth context**: Shows the real `AuthContextType` shape (`isAuthorized`, `isAdmin`, `userRole`, `userScope`, `userTools`, `userName`, `authError`) instead of a generic example
- **ApiClient**: Documents the actual singleton at `utils/api.ts` with `api.get()`, `api.post()`, `api.uploadFile()` — plus the auth token management via `setAuthToken`/`clearAuthToken`
- **SSE**: Added `useSSEProgress` hook with its actual return shape (`progress`, `completionData`, `isComplete`, `error`, `disconnect`)
- **DataTable**: Correct actual signature with `pageSize`, `onRowClick`, `emptyMessage`, `loading` props

The **reference files** (hooks, components, data-fetching, state, forms, performance) were already high quality and accurate to the codebase — no changes needed there.