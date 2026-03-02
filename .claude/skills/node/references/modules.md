# Node Modules Reference

## Contents
- ESM vs CommonJS
- Module Resolution
- Barrel Exports
- Dynamic Imports
- Node.js Built-in Modules
- Package Entry Points

---

## ESM vs CommonJS

### Pattern: ESM-Only Project (Modern Standard)

```json
// toolbox/frontend/package.json
{
  "type": "module"
}
```

**Effect:**
- All `.js` files use ESM syntax (`import`/`export`)
- CommonJS syntax requires `.cjs` extension
- Enables static analysis for tree-shaking

```typescript
// GOOD - ESM syntax
import React from 'react';
export default function App() {}

// BAD - CommonJS syntax (forbidden in ESM mode)
const React = require('react');  // ❌ SyntaxError
module.exports = App;
```

**Why:** ESM is the JavaScript standard. Vite requires ESM for optimal build performance (static imports enable dead code elimination). CommonJS is legacy and doesn't support tree-shaking.

### WARNING: Mixing ESM and CommonJS

**The Problem:**

```javascript
// vite.config.ts (ESM file)
import { defineConfig } from 'vite';

// Trying to import a CommonJS-only package
import oldLibrary from 'old-library';  // ❌ ERR_REQUIRE_ESM

// Error:
// require() of ES Module not supported. old-library is an ES module file.
```

**Why This Breaks:**
1. `old-library` is published as CommonJS (`module.exports`)
2. Your project is ESM (`"type": "module"`)
3. Node can't synchronously `require()` an ESM module

**The Fix:**

```javascript
// Option 1: Use dynamic import (async)
const { default: oldLibrary } = await import('old-library');

// Option 2: Switch config to .cjs extension
// vite.config.cjs
const { defineConfig } = require('vite');  // Use require syntax
```

**When You Might Be Tempted:** When using a legacy package that hasn't migrated to ESM. Check if a newer version exists with ESM support.

---

## Module Resolution

### Pattern: Relative vs Absolute Imports

```typescript
// GOOD - Relative imports for local modules
import { DataTable } from '../components/DataTable';

// GOOD - Absolute imports for npm packages
import React from 'react';

// BAD - Absolute imports for local modules without path aliases
import { DataTable } from 'components/DataTable';  // ❌ Module not found
```

**Setup for absolute imports (optional):**

```json
// tsconfig.json
{
  "compilerOptions": {
    "baseUrl": "./src",
    "paths": {
      "@/*": ["./*"]
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
      '@': path.resolve(__dirname, './src')
    }
  }
});
```

**Usage:**

```typescript
import { DataTable } from '@/components/DataTable';  // Now valid
```

**Why:** Path aliases reduce deep nesting (`../../../../components`) and make refactoring easier. But they require coordination between TypeScript and Vite configs.

### Pattern: Node.js Module Resolution Algorithm

Node resolves imports in this order:

1. **Core modules** (`fs`, `path`, `http`) - Node.js built-ins
2. **File or directory** - Relative paths (`./utils`, `../lib`)
3. **node_modules/** - Package names (`react`, `lodash`)

```typescript
// Core module (always available)
import path from 'path';

// Relative file
import { helper } from './utils/helper';

// Package from node_modules
import React from 'react';
```

**Extension resolution:**

```typescript
// All of these resolve to utils.ts:
import { helper } from './utils';      // Tries .ts, .tsx, .js, .jsx
import { helper } from './utils.ts';   // Explicit extension
```

**Why:** Understanding resolution order helps debug "Module not found" errors. Check core modules first, then file paths, then `node_modules/`.

---

## Barrel Exports

### Pattern: Centralized Component Exports

```typescript
// toolbox/frontend/src/components/index.ts
export { default as DataTable } from './DataTable';
export { default as FileUpload } from './FileUpload';
export { default as Modal } from './Modal';
export { default as Sidebar } from './Sidebar';
export { default as StatusBadge } from './StatusBadge';
export { default as LoadingSpinner } from './LoadingSpinner';
```

**Usage:**

```typescript
// GOOD - Single import statement
import { DataTable, Modal, LoadingSpinner } from '@/components';

// BAD - Multiple imports
import DataTable from '@/components/DataTable';
import Modal from '@/components/Modal';
import LoadingSpinner from '@/components/LoadingSpinner';
```

**Why:** Barrel exports hide internal file structure. If `DataTable.tsx` moves or renames, only the barrel export changes—not every consumer.

### WARNING: Barrel Export Performance Impact

**The Problem:**

```typescript
// components/index.ts (100+ components)
export { HeavyChart } from './HeavyChart';      // 500KB
export { RareModal } from './RareModal';        // 300KB
export { DataTable } from './DataTable';        // 50KB

// Usage:
import { DataTable } from '@/components';  // ❌ Loads ALL 100 components
```

**Why This Breaks:**
1. The barrel export (`index.ts`) re-exports 100+ components
2. Without tree-shaking, Vite bundles unused exports
3. Initial page load includes 800KB of unused code

**The Fix:**

```typescript
// GOOD - Direct imports for large, rarely-used components
import { HeavyChart } from '@/components/HeavyChart';

// GOOD - Barrel exports for small, commonly-used utilities
import { DataTable } from '@/components';
```

**When You Might Be Tempted:** When you have a large component library. Barrel exports are best for utilities and small components, not for heavy charting libraries.

---

## Dynamic Imports

### Pattern: Code Splitting with React.lazy

```typescript
// GOOD - Lazy load heavy components
import { lazy, Suspense } from 'react';

const HeavyChart = lazy(() => import('./components/HeavyChart'));

export default function Dashboard() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <HeavyChart />
    </Suspense>
  );
}
```

**Why:** Vite splits `HeavyChart` into a separate chunk. Users only download it when navigating to `/dashboard`, reducing initial bundle size.

### Pattern: Conditional Module Loading

```typescript
// Load module only when needed
async function initializeAnalytics() {
  if (process.env.NODE_ENV === 'production') {
    const { init } = await import('./analytics');
    init();
  }
}
```

**Why:** Development builds skip analytics initialization, reducing bundle size and startup time in local dev.

---

## Node.js Built-in Modules

### Pattern: Use Built-ins in Build Scripts Only

```typescript
// vite.config.ts (runs in Node, not browser)
import path from 'path';
import fs from 'fs';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
});
```

```typescript
// src/components/DataTable.tsx (runs in browser)
import path from 'path';  // ❌ NEVER do this - path is Node-only

// Error: Module "path" has been externalized for browser compatibility.
```

**Why:** Node built-ins (`path`, `fs`, `crypto`) don't exist in browsers. Vite externalizes them for build scripts but errors if you import them in browser code.

### Pattern: Polyfills for Node Built-ins (Legacy Compatibility)

Some old packages expect Node globals in the browser:

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import { nodePolyfills } from 'vite-plugin-node-polyfills';

export default defineConfig({
  plugins: [nodePolyfills()]  // Polyfills Buffer, process, etc.
});
```

**WARNING:** Polyfills add 100-500KB to your bundle. Only use for legacy packages that can't be updated.

---

## Package Entry Points

### Pattern: Package.json "main" and "exports"

```json
// Modern package structure
{
  "name": "my-library",
  "main": "./dist/index.cjs",    // Legacy CommonJS entry
  "module": "./dist/index.mjs",  // ESM entry (bundlers prefer this)
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs",
      "types": "./dist/index.d.ts"
    }
  }
}
```

**Why:**
- `main` - Fallback for old tools (Node <12)
- `module` - ESM entry for bundlers (Webpack, Vite)
- `exports` - Modern standard, supports subpath exports

### Pattern: Subpath Exports

```json
// node_modules/firebase/package.json
{
  "exports": {
    ".": "./dist/index.mjs",
    "./auth": "./dist/auth.mjs",
    "./firestore": "./dist/firestore.mjs"
  }
}
```

**Usage:**

```typescript
import { initializeApp } from 'firebase';        // Main export
import { getAuth } from 'firebase/auth';         // Subpath export
import { getFirestore } from 'firebase/firestore';
```

**Why:** Subpath exports prevent deep imports (`firebase/dist/internal/util`) and reduce bundle size (you only load `firebase/auth`, not all of Firebase).

---

## Cross-Skill Integration

### With Vite Skill

Vite's module resolution relies on Node's ESM algorithm. See the **vite** skill for `resolve.alias` patterns.

### With TypeScript Skill

TypeScript's `moduleResolution` must match Node's behavior. See the **typescript** skill for `tsconfig.json` module settings.

### With React Skill

React components use ESM exports. See the **react** skill for component import patterns and barrel exports.