# Node Patterns Reference

## Contents
- Frontend-Only Architecture
- Package Management Patterns
- Script Automation
- Dependency Versioning
- Module Resolution
- Build Output Management

---

## Frontend-Only Architecture

**This project uses Node ONLY for the frontend.** Never install Node packages in the backend.

### DO: Isolate Node to Frontend

```json
// toolbox/frontend/package.json
{
  "name": "table-rock-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

```bash
# GOOD - Frontend commands stay in frontend/
cd toolbox/frontend
npm install react

# BAD - Never install Node packages in backend
cd toolbox/backend
npm install express  # ❌ Backend is Python (FastAPI)
```

**Why:** The backend is FastAPI (Python). Mixing Node dependencies in the backend directory creates confusion about the runtime environment and breaks the architecture boundary.

---

## Package Management Patterns

### Pattern: Lock File Discipline

**Always commit `package-lock.json`.** This ensures deterministic builds across environments (local dev, CI/CD, Cloud Run).

```bash
# GOOD - Install from lockfile for reproducible builds
npm ci  # Faster, stricter than npm install

# BAD - npm install can update dependencies unexpectedly
npm install  # Use only when adding/updating packages
```

**Why:** `npm ci` (clean install) deletes `node_modules/` and installs exactly what's in the lockfile. This prevents "works on my machine" issues where different developers have different dependency versions.

### Pattern: Scoped Dependency Updates

```bash
# GOOD - Update a specific package
npm install lucide-react@latest
npm test  # Verify before committing

# BAD - Update all dependencies at once
npm update  # ❌ Can break multiple things simultaneously
```

**When You Might Be Tempted:** When you see many outdated dependencies in `npm outdated`. Resist the urge to update everything at once—update critical packages (security fixes) first, then test incrementally.

### Pattern: Dev vs Production Dependencies

```bash
# GOOD - Use --save-dev for build-time tools
npm install --save-dev @types/node vite typescript

# GOOD - Use default (--save) for runtime code
npm install react react-dom lucide-react

# BAD - Installing types as production dependencies
npm install @types/node  # ❌ Wastes production bundle size
```

**Why:** The production Docker build (`npm ci --omit=dev`) skips devDependencies to reduce image size. Miscategorized dependencies either bloat production builds or break the build entirely.

---

## Script Automation

### Pattern: Consistent Script Naming

```json
// toolbox/frontend/package.json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext ts,tsx",
    "type-check": "tsc --noEmit"
  }
}
```

**Convention:**
- `dev` - Start development server
- `build` - Production build
- `preview` - Serve production build locally
- `lint` - Run linters
- `type-check` - TypeScript validation without emitting files

**Why:** Standardized script names allow CI/CD pipelines to run `npm run build` without knowing implementation details (whether you use Vite, Webpack, etc.).

### Pattern: Makefile Wrappers for Convenience

```makefile
# toolbox/Makefile
.PHONY: dev-frontend install-frontend

dev-frontend:
	cd frontend && npm run dev

install-frontend:
	cd frontend && npm install
```

**Why:** Developers can run `make dev-frontend` from the `toolbox/` root without remembering to `cd frontend` first. The Makefile abstracts directory navigation.

---

## Dependency Versioning

### Pattern: Pinning Major Versions

```json
// GOOD - Allow patch + minor updates
{
  "dependencies": {
    "react": "^19.0.0",  // Allows 19.x.x
    "vite": "^7.0.0"     // Allows 7.x.x
  }
}

// BAD - Unpinned versions
{
  "dependencies": {
    "react": "*",        // ❌ Can jump to breaking versions
    "vite": "latest"     // ❌ Non-deterministic
  }
}
```

**Why:** The caret (`^`) allows safe updates (minor/patch) while preventing breaking changes (major version bumps). `*` or `latest` can install incompatible versions between `npm install` runs.

### WARNING: Peer Dependency Mismatches

**The Problem:**

```bash
npm install lucide-react@0.300.0
# Error: lucide-react requires react@^18.0.0, but you have react@19.0.0
```

**Why This Breaks:**
1. lucide-react explicitly declares React 18 as a peer dependency
2. Your project uses React 19
3. npm fails the install to prevent runtime errors

**The Fix:**

```bash
# Option 1: Use --legacy-peer-deps (ignores peer dependency checks)
npm install lucide-react --legacy-peer-deps

# Option 2: Wait for lucide-react to support React 19
# Option 3: Downgrade React to 18 (not recommended for this project)
```

**When You Might Be Tempted:** When you see peer dependency warnings but the library actually works at runtime (e.g., React 19 is backward-compatible with React 18 APIs).

---

## Module Resolution

### Pattern: Barrel Exports

```typescript
// toolbox/frontend/src/components/index.ts
export { default as DataTable } from './DataTable';
export { default as FileUpload } from './FileUpload';
export { default as Modal } from './Modal';

// Usage in pages:
import { DataTable, Modal } from '../components';
```

**Why:** Barrel exports (`index.ts`) centralize imports and hide internal file structure. If you rename `DataTable.tsx` to `Table.tsx`, only the barrel export changes—not every consumer.

### Pattern: ESM-Only (type: "module")

```json
// toolbox/frontend/package.json
{
  "type": "module"
}
```

**Effect:**
- `.js` files use ESM syntax (`import`/`export`)
- CommonJS requires `.cjs` extension
- Vite/TypeScript can tree-shake unused exports

**Why:** ESM is the modern standard and enables better build optimizations (dead code elimination). CommonJS (`require()`) is legacy.

---

## Build Output Management

### Pattern: .gitignore for Build Artifacts

```gitignore
# toolbox/.gitignore
frontend/node_modules/
frontend/dist/
frontend/.vite/
```

**Why:** Build artifacts (`dist/`) are generated from source code. Committing them bloats the repository and causes merge conflicts. The production Docker build regenerates `dist/` from source.

### Pattern: Serve Built Files in Production

```dockerfile
# toolbox/Dockerfile (multi-stage build)
FROM node:20 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build  # Outputs to frontend/dist/

FROM python:3.11-slim
# ... Python backend setup ...
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
```

**Why:** The production image only contains the compiled static assets (`dist/`), not source code or `node_modules/`. This reduces image size and attack surface.

---

## Cross-Skill Integration

### With Vite

```json
// package.json
{
  "scripts": {
    "dev": "vite",  // See vite skill for proxy config
    "build": "vite build"
  }
}
```

Vite is installed via npm and configured in `vite.config.ts`. See the **vite** skill for dev server proxy patterns.

### With TypeScript

```bash
# Type-check without building
npm run type-check  # Runs: tsc --noEmit

# Vite build includes type checking
npm run build  # Vite invokes tsc internally
```

TypeScript is a devDependency. See the **typescript** skill for `tsconfig.json` patterns.

### With React

```bash
npm install react react-dom
npm install --save-dev @types/react @types/react-dom
```

React requires Node for the build toolchain (JSX transformation). See the **react** skill for component patterns.