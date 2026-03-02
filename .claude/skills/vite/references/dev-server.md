# Dev Server Reference

## Contents
- Dev Server Configuration
- API Proxy Setup
- HMR (Hot Module Replacement)
- HTTPS in Development
- Common Errors

---

## Dev Server Configuration

### Basic Setup

```typescript
// toolbox/frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // Expose to network (0.0.0.0)
    open: true, // Auto-open browser
    strictPort: true, // Fail if port 5173 is taken
  },
});
```

**Why `host: true`?** Allows access from other devices on LAN (mobile testing, Docker containers).

### Running the Dev Server

```bash
# From toolbox/frontend/
npm run dev

# Or via Makefile from toolbox/
make dev-frontend

# Expected output:
#   VITE v7.x.x ready in XXX ms
#   ➜ Local:   http://localhost:5173/
#   ➜ Network: http://192.168.1.x:5173/
```

**DO:** Use `make dev` to run both frontend and backend concurrently.
**DON'T:** Run only the frontend without the backend—API calls will fail.

---

## API Proxy Setup

### Proxy Configuration

```typescript
// toolbox/frontend/vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000', // FastAPI backend
      changeOrigin: true, // Needed for virtual hosted sites
      secure: false, // Accept self-signed certs
      ws: true, // Proxy WebSocket connections (if needed)
    },
  },
}
```

**How it works:**
- Frontend request: `fetch('/api/extract/upload')`
- Vite intercepts and forwards to: `http://localhost:8000/api/extract/upload`
- Response proxied back to frontend
- **No CORS issues** (same origin from browser's perspective)

### Multiple Proxy Targets

```typescript
// If backend has different services
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws': {
      target: 'ws://localhost:8080', // WebSocket server
      ws: true,
    },
    '/storage': {
      target: 'http://localhost:9000', // GCS emulator
      changeOrigin: true,
    },
  },
}
```

### Proxy Debugging

```typescript
// Enable detailed proxy logs
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      configure: (proxy, options) => {
        proxy.on('error', (err, req, res) => {
          console.error('Proxy error:', err);
        });
        proxy.on('proxyReq', (proxyReq, req, res) => {
          console.log('Proxying:', req.method, req.url);
        });
      },
    },
  },
}
```

**When to use:** Debugging proxy failures, inspecting request headers.

---

## HMR (Hot Module Replacement)

### How HMR Works

1. File change detected (`DataTable.tsx` modified)
2. Vite rebuilds only affected modules
3. HMR client updates browser without full reload
4. React Fast Refresh preserves component state

**DO:**
```tsx
// Component state preserved during HMR
function DataTable() {
  const [sortBy, setSortBy] = useState('name');
  // Change CSS, HMR updates styles without resetting sortBy
  return <table className="tre-table">...</table>;
}
```

**DON'T:**
```tsx
// BAD - Module-level state breaks HMR
let globalCounter = 0;

function Counter() {
  // HMR reloads module, globalCounter resets to 0
  return <div>{globalCounter++}</div>;
}
```

**Use `useState` or Context API for state**, not module-level variables.

### HMR Boundaries

**Files that trigger full reload:**
- `vite.config.ts` changes
- `.env` file changes
- `index.html` modifications
- Files imported in `main.tsx` with side effects

**Files that support HMR:**
- `.tsx/.jsx` components (React Fast Refresh)
- `.css` files (style injection)
- JSON imports (if used reactively)

### Debugging HMR Issues

```typescript
// vite.config.ts - Disable React Fast Refresh if buggy
plugins: [
  react({
    fastRefresh: false, // Forces full reload on changes
  }),
]
```

**Common HMR breakage:**
- Named exports instead of default exports for components
- Circular dependencies between modules
- Non-serializable values in component state

---

## HTTPS in Development

### When Needed

- Testing Firebase Auth with OAuth (requires HTTPS callback)
- Service Workers (only work on HTTPS or localhost)
- Secure cookies from backend

### Self-Signed Certificate

```typescript
// vite.config.ts
import fs from 'fs';

export default defineConfig({
  server: {
    https: {
      key: fs.readFileSync('certs/key.pem'),
      cert: fs.readFileSync('certs/cert.pem'),
    },
  },
});
```

**Generate cert:**

```bash
# Create self-signed cert (valid 365 days)
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/key.pem -out certs/cert.pem \
  -days 365 -subj "/CN=localhost"

# Add certs/ to .gitignore
echo "certs/" >> .gitignore
```

**Browser warning:** Self-signed certs show "Not Secure" warning. Accept risk for local dev.

---

## Common Errors

### Port Already in Use

```bash
# Error: Port 5173 is already in use
# Fix: Kill process on port 5173
lsof -ti:5173 | xargs kill -9

# Or use different port
vite --port 3000
```

### Proxy Target Refused Connection

```bash
# Error: [vite] http proxy error: ECONNREFUSED
# Cause: Backend not running on localhost:8000

# Fix: Start backend first
cd toolbox/backend
python3 -m uvicorn app.main:app --reload --port 8000
```

### Module Not Found in Browser

```bash
# Error: Failed to resolve module specifier "firebase/app"
# Cause: Missing dependency or incorrect import path

# Fix: Install dependency
npm install firebase

# Ensure import uses exact package name
import { initializeApp } from 'firebase/app'; // GOOD
import { initializeApp } from 'firebase'; // BAD (wrong entry)
```

### CORS Errors Despite Proxy

```typescript
// BAD - Absolute URL bypasses proxy
fetch('http://localhost:8000/api/extract/upload');

// GOOD - Relative URL uses proxy
fetch('/api/extract/upload');
```

**Fix:** Always use relative URLs (`/api/*`) for backend calls in dev.