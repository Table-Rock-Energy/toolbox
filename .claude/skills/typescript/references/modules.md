# TypeScript Modules Reference

## Contents
- tsconfig Hierarchy
- Barrel Exports
- Import Order
- Path Aliases
- Circular Dependencies

---

## tsconfig Hierarchy

```
frontend/
├── tsconfig.json          # Root: references only, no compilerOptions
├── tsconfig.app.json      # App code (src/) — strict mode
└── tsconfig.node.json     # Vite config (vite.config.ts)
```

```json
// tsconfig.json — root
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

```json
// tsconfig.app.json — actual file
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["src"]
}
```

**Why project references:**
- App code in `tsconfig.app.json` cannot accidentally import from `vite.config.ts`
- `noEmit: true` — compilation is for type-checking only; Vite handles bundling
- `moduleResolution: "bundler"` — enables `.tsx` extension imports without workarounds

---

## Barrel Exports

### Component Barrel (actual pattern)

```typescript
// src/components/index.ts
export { default as Sidebar } from './Sidebar'
export { default as FileUpload } from './FileUpload'
export { default as DataTable } from './DataTable'
export { default as StatusBadge } from './StatusBadge'
export { default as Modal } from './Modal'
export { default as LoadingSpinner } from './LoadingSpinner'
export { default as AiReviewPanel } from './AiReviewPanel'
export { default as EnrichmentPanel } from './EnrichmentPanel'
export { default as MineralExportModal } from './MineralExportModal'
export { default as GhlConnectionCard } from './GhlConnectionCard'
export { default as GhlSendModal } from './GhlSendModal'
```

```typescript
// Clean consumer imports
import { DataTable, Modal, LoadingSpinner } from '../components'
```

```typescript
// src/pages/index.ts — same pattern for pages
export { default as Dashboard } from './Dashboard'
export { default as Extract } from './Extract'
// ...
```

---

### WARNING: Circular Dependencies in Barrels

```typescript
// BAD — Modal.tsx imports from its own barrel
// components/Modal.tsx
import { Sidebar } from './index'  // Circular: Modal → index → Modal

// components/Sidebar.tsx
import { Modal } from './index'  // Circular: Sidebar → index → Sidebar
```

**Why this breaks:** Barrel exports create a hub. If `ComponentA.tsx` imports from `index.ts` which re-exports `ComponentA`, the module graph cycles. Vite/bundlers may resolve this incorrectly, causing `undefined` components at runtime.

**The fix — direct imports for internal component dependencies:**

```typescript
// GOOD — components import each other directly, never via barrel
// components/Modal.tsx
import Sidebar from './Sidebar'  // Direct, no barrel
```

**Safe barrel usage:** Only components that are **leaf nodes** (no cross-imports with siblings) should be in the barrel.

---

## Import Order

### Enforced grouping

```typescript
// 1. External packages (React, lucide-react, firebase)
import { useState, useEffect, type ReactNode } from 'react'
import { Upload, Download, X } from 'lucide-react'

// 2. Internal relative imports
import { DataTable, FileUpload, Modal } from '../components'
import { useAuth } from '../contexts/AuthContext'
import api from '../utils/api'

// 3. Type-only imports (when separate from values)
import type { PartyEntry, AiValidationResult } from '../utils/api'
```

**No path aliases** — this project uses relative imports (`../components`, `../utils/api`). Don't add `@/` aliases without updating both `tsconfig.app.json` and `vite.config.ts`.

---

## Path Aliases (Not currently used)

The project does NOT use path aliases. If you add them, sync both files:

```json
// tsconfig.app.json — add to compilerOptions
{
  "baseUrl": ".",
  "paths": {
    "@/*": ["src/*"]
  }
}
```

```typescript
// vite.config.ts — add resolve.alias
import path from 'path'
export default defineConfig({
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') }
  }
})
```

**Trade-off:** Shorter imports vs harder to trace where files actually are. Prefer relative imports unless nesting exceeds 3 levels.

---

## Circular Dependencies

### Detection

```bash
# From frontend/ directory
npx madge --circular --extensions ts,tsx src/
```

### Breaking Cycles

```typescript
// BAD — services import each other
// authService.ts imports from apiService.ts which imports from authService.ts

// GOOD — extract shared types to a types file
// types.ts
export interface AuthToken { token: string; expiresAt: number }

// authService.ts
import type { AuthToken } from './types'  // type-only import breaks the cycle

// apiService.ts
import type { AuthToken } from './types'
```

**Type-only imports (`import type`) don't create runtime dependencies** — they're completely erased. This is the primary technique for breaking circular dependency cycles at the value level.
