All 5 skill files are updated. Here's what changed:

**`SKILL.md`** — Fully rewritten to reflect the actual codebase:
- Accurate tsconfig flags (`verbatimModuleSyntax`, `erasableSyntaxOnly`, `noUncheckedSideEffectImports`)
- Correct `DataTable<T extends object>` pattern with `keyof T | string` key type (matching actual file)
- Actual `ApiResponse<T>` wrapper pattern from `utils/api.ts`
- Inline `import { type X }` syntax (not the separate `import type` form)
- Real `useAuth()` context guard pattern from `AuthContext.tsx`

**`references/patterns.md`** — Rewritten with:
- Exact tsconfig.app.json options (removed fake `strictNullChecks`, `noUncheckedIndexedAccess` that weren't in the file)
- Actual `getValue()` dot-path traversal pattern from `DataTable.tsx`
- Firebase error code narrowing pattern from `AuthContext.tsx`

**`references/modules.md`** — Rewritten with:
- Accurate tsconfig hierarchy (removed non-existent `composite`, `isolatedModules`, `resolveJsonModule`)
- Actual barrel export list from `components/index.ts`
- No lazy loading (not used in actual `App.tsx`)

**`references/types.md`** and **`references/errors.md`** — Kept as-is (content was accurate and comprehensive).