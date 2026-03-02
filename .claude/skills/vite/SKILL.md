---
name: vite
description: |
  Configures Vite 7 dev server with FastAPI proxy, production builds, and TypeScript strict mode for React 19 SPA
  Use when: configuring dev environment, setting up API proxying, optimizing builds, or debugging HMR issues
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Vite Skill

Vite 7 powers the React 19 frontend with a dev server on port 5173 that proxies `/api` requests to the FastAPI backend on port 8000. Production builds generate static assets served by FastAPI from `frontend/dist/`. Configuration lives in `toolbox/frontend/vite.config.ts` with TypeScript strict mode, path aliases, and optimized chunking for Firebase/Lucide dependencies.

## Quick Start

### Dev Server with Backend Proxy

```typescript
// toolbox/frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

**Run:** `make dev-frontend` or `npm run dev` from `toolbox/frontend/`

### Production Build

```bash
# From toolbox/frontend/
npm run build

# Output: toolbox/frontend/dist/
# - index.html (entry point)
# - assets/*.js (chunked bundles)
# - assets/*.css (extracted styles)
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| **Dev Server** | HMR on port 5173, proxies API calls | `server: { port: 5173, proxy: { '/api': ... } }` |
| **Build Output** | Static assets in `dist/`, served by FastAPI | `build: { outDir: 'dist' }` |
| **Code Splitting** | Manual chunks for large dependencies | `manualChunks: { firebase: ['firebase/auth'], lucide: ['lucide-react'] }` |
| **Path Aliases** | TypeScript path mapping (if configured) | `resolve: { alias: { '@': '/src' } }` |
| **Plugin System** | React Fast Refresh, SWC transpilation | `plugins: [react()]` |

## Common Patterns

### API Proxying (No CORS in Dev)

**When:** Frontend calls `/api/*` endpoints during local development

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000', // FastAPI backend
      changeOrigin: true,
      secure: false, // For self-signed certs in dev
    },
  },
}

// Frontend makes same-origin requests
// toolbox/frontend/src/utils/api.ts
const response = await fetch('/api/extract/upload', { 
  method: 'POST', 
  body: formData 
});
// Proxied to http://localhost:8000/api/extract/upload
```

### Manual Chunk Splitting

**When:** Large dependencies (Firebase, Lucide) bloat the main bundle

```typescript
// vite.config.ts
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        'firebase': ['firebase/app', 'firebase/auth'],
        'lucide': ['lucide-react'],
        'vendor': ['react', 'react-dom', 'react-router-dom'],
      },
    },
  },
}
```

**Why:** Improves caching (vendor code rarely changes), parallel download of chunks, faster initial page load.

### Environment Variables

**When:** Frontend needs runtime config (API base URL for production)

```typescript
// vite.config.ts - NO special config needed

// .env.development (git-ignored)
VITE_API_BASE_URL=/api

// .env.production (git-ignored)
VITE_API_BASE_URL=https://tools.tablerocktx.com/api

// toolbox/frontend/src/utils/api.ts
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
```

**IMPORTANT:** Only `VITE_` prefixed vars are exposed to client code. Backend vars (`GCS_BUCKET_NAME`) are NOT accessible.

## WARNING: Common Pitfalls

### Importing Node Modules in Client Code

**The Problem:**

```typescript
// BAD - Node.js 'fs' module in browser code
import fs from 'fs';

const file = fs.readFileSync('/path/to/file');
```

**Why This Breaks:**
1. Browser has no `fs` module → Vite build fails with "Module not found"
2. Even with polyfills, runtime errors occur
3. Bundle size explodes with Node.js polyfills

**The Fix:**

```typescript
// GOOD - Use browser APIs or fetch from backend
const response = await fetch('/api/files/data.json');
const data = await response.json();
```

**When You Might Be Tempted:** Processing files client-side instead of uploading to backend.

### Missing Proxy Configuration

**The Problem:**

```typescript
// BAD - Hardcoded localhost in fetch calls
const response = await fetch('http://localhost:8000/api/extract/upload', {
  method: 'POST',
  body: formData,
});
```

**Why This Breaks:**
1. CORS errors in dev (different origins: 5173 vs 8000)
2. Hardcoded URLs fail in production (backend on different host)
3. Mixed content warnings if production uses HTTPS

**The Fix:**

```typescript
// GOOD - Relative URLs proxied in dev, work in production
const response = await fetch('/api/extract/upload', {
  method: 'POST',
  body: formData,
});

// vite.config.ts
server: {
  proxy: {
    '/api': 'http://localhost:8000',
  },
}
```

**When You Might Be Tempted:** Quick testing without configuring proxy, copy-pasting examples from docs.

## See Also

- [dev-server](references/dev-server.md) - HMR, proxy config, debugging
- [build-optimization](references/build-optimization.md) - Chunking, tree-shaking, compression
- [environment-variables](references/environment-variables.md) - Runtime config, `.env` files
- [troubleshooting](references/troubleshooting.md) - Common errors, solutions

## Related Skills

- **react** - Component patterns, hooks, context API
- **typescript** - Strict mode, tsconfig integration with Vite
- **tailwind** - PostCSS integration, build-time purging
- **frontend-design** - Asset optimization, responsive design
- **firebase** - Auth SDK bundling, environment config
- **node** - Package management, scripts in `package.json`

## Documentation Resources

> Fetch latest Vite documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "vite"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** `/websites/vite.dev` _(prefer website docs)_

**Recommended Queries:**
- "vite dev server proxy configuration"
- "vite build optimization manual chunks"
- "vite environment variables best practices"
- "vite typescript integration"