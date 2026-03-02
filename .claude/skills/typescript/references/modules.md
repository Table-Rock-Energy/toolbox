# TypeScript Modules Reference

## Contents
- Project References
- Barrel Exports
- Import Order
- Lazy Loading
- Circular Dependencies

---

## Project References

### TypeScript Configuration Hierarchy

```json
// toolbox/frontend/tsconfig.json (base)
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

```json
// toolbox/frontend/tsconfig.app.json (application code)
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

**Why project references:**
1. **Separate build configurations** - App code vs Vite config vs tests
2. **Incremental builds** - TypeScript only recompiles changed projects
3. **Strict boundaries** - Prevents app code from importing Vite config

---

## Barrel Exports

### Component Barrel

```typescript
// GOOD - toolbox/frontend/src/components/index.ts
export { default as DataTable } from './DataTable';
export { default as FileUpload } from './FileUpload';
export { default as Modal } from './Modal';
export { default as Sidebar } from './Sidebar';
export { default as StatusBadge } from './StatusBadge';
export { default as LoadingSpinner } from './LoadingSpinner';

// Re-export types
export type { DataTableProps } from './DataTable';
export type { FileUploadProps } from './FileUpload';
export type { ModalProps } from './Modal';
```

**Usage:**
```typescript
// Clean imports
import { DataTable, Modal, LoadingSpinner } from '../components';
import type { DataTableProps } from '../components';
```

```typescript
// BAD - Individual imports
import DataTable from '../components/DataTable';
import Modal from '../components/Modal';
import LoadingSpinner from '../components/LoadingSpinner';
```

---

### WARNING: Barrel Export Pitfalls

```typescript
// BAD - Circular dependency
// components/index.ts
export { default as Modal } from './Modal';
export { default as Sidebar } from './Sidebar';

// components/Modal.tsx
import { Sidebar } from './index'; // Circular: Modal -> index -> Modal

// components/Sidebar.tsx
import { Modal } from './index'; // Circular: Sidebar -> index -> Sidebar
```

**Why this breaks:**
Barrel exports create a hub. If `Modal.tsx` imports from `index.ts`, and `index.ts` re-exports `Modal`, the module graph has a cycle. This can cause `undefined` at runtime.

**The fix:**
```typescript
// GOOD - Direct imports for internal dependencies
// components/Modal.tsx
import Sidebar from './Sidebar'; // Direct import, no barrel

// components/Sidebar.tsx
import Modal from './Modal';
```

**When barrel exports are safe:**
- Leaf components (no internal imports)
- Utilities that don't import from the same barrel
- Pages that only import from `components/`, not from `pages/`

---

## Import Order

### Consistent Import Grouping

```typescript
// GOOD - toolbox/frontend/src/pages/Extract.tsx
// 1. External packages
import { useState, useEffect } from 'react';
import { Upload, Download } from 'lucide-react';

// 2. Internal modules (alphabetical)
import { DataTable, FileUpload, Modal } from '../components';
import { useAuth } from '../contexts/AuthContext';
import { ApiClient } from '../utils/api';

// 3. Type-only imports
import type { PartyEntry } from '../utils/api';

// 4. Styles (if any)
import '../styles/extract.css';
```

**Why import order matters:**
1. Readability - Clear separation between external and internal
2. Avoids merge conflicts - Alphabetical within groups
3. Bundle optimization - Type-only imports grouped separately

---

### ESLint Import Rules

This project enforces import order via ESLint. See **frontend-design** skill for ESLint configuration.

---

## Lazy Loading

### React.lazy for Code Splitting

```typescript
// GOOD - toolbox/frontend/src/App.tsx
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { LoadingSpinner } from './components';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Extract = lazy(() => import('./pages/Extract'));
const Title = lazy(() => import('./pages/Title'));
const Proration = lazy(() => import('./pages/Proration'));
const Revenue = lazy(() => import('./pages/Revenue'));

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/extract" element={<Extract />} />
          <Route path="/title" element={<Title />} />
          <Route path="/proration" element={<Proration />} />
          <Route path="/revenue" element={<Revenue />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
```

**Bundle impact:**
Without lazy loading, all pages bundle together (~500 KB). With lazy loading, initial bundle is ~120 KB, each page loads on demand.

---

### Dynamic Imports for Conditional Logic

```typescript
// GOOD - Load heavy library only when needed
async function exportToPDF(data: MineralHolderRow[]) {
  const { generatePDF } = await import('../utils/pdfGenerator');
  return generatePDF(data);
}

// pdfGenerator.ts uses ReportLab-equivalent (~200 KB), only loaded on export
```

**When to use dynamic imports:**
- Libraries > 50 KB used conditionally
- Admin-only features (most users never load the code)
- Export functionality (PDF/Excel generation)

---

## Circular Dependencies

### Detecting Cycles

```bash
# Use madge to detect circular dependencies
npx madge --circular --extensions ts,tsx toolbox/frontend/src
```

**Common causes:**
1. Barrel exports with internal cross-imports
2. Context providers importing components that use the context
3. Utility files importing each other

---

### Breaking Cycles with Interfaces

```typescript
// BAD - Circular dependency
// userService.ts
import { logEvent } from './analytics';

export function createUser(email: string) {
  logEvent('user_created', { email });
}

// analytics.ts
import { createUser } from './userService';

export function logEvent(event: string, data: any) {
  if (event === 'signup') {
    createUser(data.email); // Circular
  }
}
```

```typescript
// GOOD - Extract interface
// types.ts
export interface AnalyticsLogger {
  logEvent(event: string, data: any): void;
}

// userService.ts
import type { AnalyticsLogger } from './types';

export function createUser(email: string, logger: AnalyticsLogger) {
  logger.logEvent('user_created', { email });
}

// analytics.ts
import type { AnalyticsLogger } from './types';

export const analytics: AnalyticsLogger = {
  logEvent(event, data) {
    console.log(event, data);
  },
};
```

**Why this fixes the cycle:**
Type-only imports (`import type`) don't create runtime dependencies. The cycle is broken at the value level.

---

## Path Aliases (Optional)

This project does NOT use path aliases (`@/components`, etc.) but you can add them:

```json
// tsconfig.app.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/components/*": ["src/components/*"],
      "@/utils/*": ["src/utils/*"]
    }
  }
}
```

```typescript
// vite.config.ts
import path from 'path';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
```

**Trade-offs:**
- **Pro:** Shorter imports (`@/components` vs `../../../components`)
- **Con:** Harder to reason about relative locations
- **Con:** Requires Vite config + tsconfig sync