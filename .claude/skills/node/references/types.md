# Node Types Reference

## Contents
- TypeScript Integration
- Type Definitions (@types/*)
- Node.js Built-in Types
- Module Type Systems
- Package Type Exports

---

## TypeScript Integration

### Pattern: TypeScript as DevDependency

```json
// toolbox/frontend/package.json
{
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/node": "^20.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0"
  }
}
```

**Why:** TypeScript is a build-time tool. The compiled output (JavaScript) runs in production, so TypeScript doesn't need to be a production dependency.

### Pattern: Project References for Monorepo

```json
// toolbox/frontend/tsconfig.json
{
  "extends": "./tsconfig.app.json",
  "references": [
    { "path": "./tsconfig.node.json" }
  ]
}
```

```json
// toolbox/frontend/tsconfig.node.json
{
  "compilerOptions": {
    "composite": true,
    "types": ["node"]
  },
  "include": ["vite.config.ts"]
}
```

**Why:** `vite.config.ts` runs in Node, not the browser. Separating its TypeScript config prevents browser-only types (like `DOM`) from leaking into build scripts.

---

## Type Definitions (@types/*)

### Pattern: Auto-Discovery via @types

When you install a package without built-in types, TypeScript automatically checks `@types/[package-name]`:

```bash
# Install runtime package
npm install firebase

# TypeScript looks for @types/firebase
npm install --save-dev @types/firebase

# Alternatively, use the package's bundled types (if available)
# Check package.json for "types" field:
cat node_modules/firebase/package.json | grep '"types"'
```

### WARNING: Missing Type Definitions

**The Problem:**

```typescript
// src/utils/api.ts
import someLibrary from 'some-library';  // ❌ Could not find declaration file

// TypeScript error:
// Could not find a declaration file for module 'some-library'.
// Try `npm i --save-dev @types/some-library` if it exists.
```

**Why This Breaks:**
1. `some-library` is written in plain JavaScript (no `.d.ts` files)
2. No community-maintained `@types/some-library` package exists
3. TypeScript can't infer types without explicit declarations

**The Fix:**

```typescript
// Option 1: Declare module globally (quick fix)
// src/types/shims.d.ts
declare module 'some-library' {
  const content: any;
  export default content;
}

// Option 2: Write proper types (better)
// src/types/some-library.d.ts
declare module 'some-library' {
  export function doThing(arg: string): Promise<void>;
}
```

```json
// tsconfig.json
{
  "include": ["src/**/*", "src/types/**/*"]
}
```

**When You Might Be Tempted:** When using an obscure npm package or internal library. Don't ignore the error with `// @ts-ignore`—add proper type declarations.

---

## Node.js Built-in Types

### Pattern: Import Node Types for Build Scripts

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import path from 'path';  // Node.js built-in

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
});
```

```json
// tsconfig.node.json (for build scripts)
{
  "compilerOptions": {
    "types": ["node"]  // Enables NodeJS global types
  }
}
```

**Why:** `path`, `fs`, `process` are Node.js built-ins. The `@types/node` package provides TypeScript definitions for these modules.

### WARNING: Mixing Node and Browser Types

**The Problem:**

```typescript
// src/components/DataTable.tsx
import fs from 'fs';  // ❌ fs is a Node.js module, not available in browsers

export default function DataTable() {
  const data = fs.readFileSync('/data.json');  // Runtime error in browser
  return <div>{data}</div>;
}
```

**Why This Breaks:**
1. Browser code runs in the DOM (no filesystem access)
2. `fs` is a Node.js built-in module that doesn't exist in browsers
3. Vite bundles this code for the browser, but `fs.readFileSync` will fail at runtime

**The Fix:**

```typescript
// GOOD - Fetch data via API (browser-safe)
export default function DataTable() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch('/api/data').then(res => res.json()).then(setData);
  }, []);

  return <div>{JSON.stringify(data)}</div>;
}
```

**Rule:** Never import Node.js built-ins (`fs`, `path`, `crypto`) in browser code. Use them only in build scripts (`vite.config.ts`, `tailwind.config.js`).

---

## Module Type Systems

### Pattern: ESM with "type": "module"

```json
// package.json
{
  "type": "module"
}
```

**Effect:**
- `.js` files use ESM (`import`/`export`)
- `.cjs` files use CommonJS (`require()`)
- TypeScript emits ESM by default

**Why:** Vite requires ESM for optimal tree-shaking. CommonJS is legacy and doesn't support static analysis for dead code elimination.

### Pattern: TypeScript Module Resolution

```json
// tsconfig.json
{
  "compilerOptions": {
    "module": "ESNext",           // Emit ESM
    "moduleResolution": "bundler", // Vite-compatible resolution
    "resolveJsonModule": true      // Allow import of .json files
  }
}
```

**Why:**
- `"moduleResolution": "bundler"` matches Vite's resolution strategy (supports package.json `exports` field)
- `"resolveJsonModule": true` allows `import data from './data.json'`

---

## Package Type Exports

### Pattern: Conditional Exports in package.json

Modern packages expose different entry points for different environments:

```json
// node_modules/some-package/package.json
{
  "name": "some-package",
  "exports": {
    ".": {
      "import": "./dist/index.mjs",  // ESM
      "require": "./dist/index.cjs", // CommonJS
      "types": "./dist/index.d.ts"   // TypeScript definitions
    },
    "./client": {
      "import": "./dist/client.mjs",
      "types": "./dist/client.d.ts"
    }
  }
}
```

**Usage:**

```typescript
// Main export
import { foo } from 'some-package';

// Subpath export
import { bar } from 'some-package/client';
```

**Why:** The `exports` field prevents deep imports (e.g., `some-package/dist/internal`) and ensures you use the package's public API. TypeScript uses the `types` field to locate `.d.ts` files.

### WARNING: Missing "exports" Field

**The Problem:**

```typescript
// Trying to import a submodule
import { helper } from 'old-package/utils';  // ❌ Module not found

// Error:
// Package subpath './utils' is not defined by "exports" in
// /node_modules/old-package/package.json
```

**Why This Breaks:**
1. The package has an `exports` field that doesn't list `./utils`
2. Node's module resolution blocks unlisted subpaths for security
3. The package author didn't intend `./utils` to be public API

**The Fix:**

```typescript
// Option 1: Use the main export
import { helper } from 'old-package';  // If it re-exports helper

// Option 2: Check package documentation for correct import path
// Option 3: File an issue requesting the subpath be added to exports
```

**When You Might Be Tempted:** When upgrading from a legacy package that allowed deep imports like `lodash/debounce`. Modern packages restrict this via the `exports` field.

---

## Cross-Skill Integration

### With TypeScript Skill

TypeScript configuration (`tsconfig.json`) determines how Node resolves types. See the **typescript** skill for strict mode patterns.

### With Vite Skill

Vite's module resolution must align with TypeScript's `moduleResolution` setting. See the **vite** skill for `vite.config.ts` type imports.

### With React Skill

React type definitions (`@types/react`) enable JSX type checking. See the **react** skill for component prop type patterns.