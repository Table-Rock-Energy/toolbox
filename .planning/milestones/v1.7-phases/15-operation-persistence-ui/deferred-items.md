# Deferred Items - Phase 15

## Pre-existing Build Errors

1. **Title.tsx OwnerEntry type cast** - `npm run build` fails on `results as OwnerEntry[]` cast in Title.tsx (lines 327, 344). The `_uid` property type mismatch (`string | undefined` vs `string`). Pre-existing, not introduced by phase 15 changes. `tsc --noEmit` passes but Vite build is stricter.
