# Fixtures Reference

## Contents
- Static Assets (public/)
- Imported Assets in Source
- Test Data Fixtures
- JSON Imports
- Asset URL Handling in Tests

---

## Static Assets (public/)

Files in `frontend/public/` are served as-is at the root URL. Vite does NOT process them (no hashing, no transformation).

```
frontend/
├── public/
│   ├── favicon.ico          → served at /favicon.ico
│   ├── table-rock-logo.png  → served at /table-rock-logo.png
│   └── mockServiceWorker.js → required for MSW (see mocking.md)
```

**When to use `public/`:**
- Files referenced by `index.html` directly (favicon, Open Graph images)
- Files that need stable, predictable URLs (MSW service worker)
- Files NOT imported via JavaScript/TypeScript

**When NOT to use `public/`:** Assets used in components should be imported from `src/assets/` — Vite hashes them for caching and tree-shakes unused ones.

---

## Imported Assets in Source

Assets imported in TypeScript are processed by Vite: hashed filename, optimized, included in the bundle manifest.

```tsx
// Import as URL string
import logoUrl from '../assets/table-rock-logo.svg';

function Sidebar() {
  return <img src={logoUrl} alt="Table Rock Energy" className="h-8 w-auto" />;
}
```

```typescript
// vite.config.ts — customize asset inlining threshold
build: {
  assetsInlineLimit: 4096, // Inline assets < 4KB as base64 (default)
}
```

**TypeScript declaration** (if needed for non-standard asset types):
```typescript
// frontend/src/vite-env.d.ts — already provided by vite/client types
/// <reference types="vite/client" />
// Provides: ImportMeta, import.meta.env types, asset module declarations
```

The `tsconfig.app.json` includes `"types": ["vite/client"]` which provides `*.svg`, `*.png`, `*.json` import type declarations automatically.

---

## Test Data Fixtures

The project stores test fixtures in `test-data/` (gitignored). For unit tests, use inline fixtures or a `src/test/fixtures/` directory.

```typescript
// frontend/src/test/fixtures/extract.ts
export const mockPartyEntry = {
  name: 'JOHN SMITH',
  entity_type: 'INDIVIDUAL' as const,
  address: '123 Main Street, Oklahoma City, OK 73102',
  tract_number: 'Tract 1',
  working_interest: '0.25000000',
};

export const mockExtractionResult = {
  parties: [mockPartyEntry],
  total_count: 1,
  job_id: 'test-job-123',
  filename: 'exhibit-a-test.pdf',
};
```

```typescript
// frontend/src/test/fixtures/proration.ts
export const mockMineralHolder = {
  name: 'JANE DOE',
  lease_number: '12345',
  county: 'REEVES',
  nra: '0.00390625',
  gross_acres: '640.000',
};

export const mockRrcResult = {
  lease_number: '12345',
  lease_name: 'TEST WELL 1H',
  operator: 'TABLE ROCK ENERGY',
  oil_allowable: '150',
  gas_allowable: '500',
};
```

**DO:** Keep fixtures in typed files — TypeScript catches stale fixtures when API response shapes change.

**DON'T:**
```typescript
// BAD - Untyped object literals spread throughout test files
const party = { name: 'John', type: 'individual' }; // Wrong shape, won't be caught
```

---

## JSON Imports

Vite supports importing JSON files directly. Useful for static lookup data.

```typescript
// Import entire JSON file
import rrcCountyCodes from '../data/rrc-county-codes.json';

// Vite tree-shakes named exports if JSON has top-level keys
// (with { assert: { type: 'json' } } in Node, but Vite handles it natively)
```

**Production consideration:** Large JSON files are bundled into the JS chunk that imports them. For large datasets (RRC county data), prefer fetching from the API rather than bundling.

```typescript
// BAD for large data - adds to bundle size
import allRrcData from '../data/rrc-oil-proration.json'; // Could be 10MB+

// GOOD - fetch from backend API, cached in memory there
const data = await fetch('/api/proration/rrc/status').then(r => r.json());
```

---

## Asset URL Handling in Tests

Tests run in jsdom — there's no actual file serving. Asset imports return the filename string or a mock.

```typescript
// In jsdom, imported SVGs resolve to the filename
// frontend/src/test/setup.ts — mock SVG imports
vi.mock('../assets/table-rock-logo.svg', () => ({
  default: 'table-rock-logo.svg',
}));

// Or configure in vite.config.ts test section
test: {
  asset: 'empty', // Returns empty string for all asset imports in tests
}
```

**For file upload tests** — create `File` objects directly, no actual files needed:

```typescript
// Create PDF fixture in test — no real file needed
const pdfFixture = new File(
  ['%PDF-1.4 fake pdf content'],
  'exhibit-a.pdf',
  { type: 'application/pdf' }
);

// Create CSV fixture
const csvFixture = new File(
  ['name,lease_number\nJohn Smith,12345\n'],
  'mineral-holders.csv',
  { type: 'text/csv' }
);
```

This matches how `FileUpload.tsx` receives files from drag-drop or file input — both give `File` objects.
