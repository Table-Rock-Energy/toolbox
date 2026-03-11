# Mocking Reference

## Contents
- Mocking `import.meta.env`
- Mocking Firebase Auth
- Mocking API Responses (fetch)
- Dev Server API Mocking (MSW)
- Mocking Browser APIs

---

## Mocking `import.meta.env`

Vite replaces `import.meta.env.*` at build time. In tests (Vitest), you must mock it explicitly — the actual `.env` files are NOT loaded during test runs by default.

```typescript
// frontend/src/test/setup.ts — global mock for all tests
Object.defineProperty(import.meta, 'env', {
  value: {
    VITE_API_BASE_URL: '/api',
    VITE_FIREBASE_API_KEY: 'test-api-key',
    VITE_FIREBASE_AUTH_DOMAIN: 'test.firebaseapp.com',
    VITE_FIREBASE_PROJECT_ID: 'test-project',
    MODE: 'test',
    DEV: false,
    PROD: false,
  },
  writable: true,
});
```

**Per-test override:**

```typescript
// Override for a specific test
test('uses custom API base URL', () => {
  const originalEnv = import.meta.env.VITE_API_BASE_URL;
  import.meta.env.VITE_API_BASE_URL = 'https://staging.tablerocktx.com/api';

  // ... test code

  import.meta.env.VITE_API_BASE_URL = originalEnv; // restore
});
```

**Alternatively, use Vitest's `vi.stubEnv`:**
```typescript
import { vi } from 'vitest';

test('uses staging URL', () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://staging.tablerocktx.com/api');
  // vi.unstubAllEnvs() is called automatically after each test
});
```

---

## Mocking Firebase Auth

Firebase Auth calls real Google services. NEVER allow real Firebase calls in tests — they're flaky, slow, and require network.

```typescript
// vi.mock hoisted to top of module — mock the entire firebase module
vi.mock('../lib/firebase', () => ({
  auth: {
    currentUser: null,
    onAuthStateChanged: vi.fn(),
    signInWithPopup: vi.fn(),
    signOut: vi.fn(),
  },
}));

// Mock the AuthContext so components get a controlled user
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'james@tablerocktx.com', uid: 'test-uid' },
    loading: false,
    signOut: vi.fn(),
  }),
  AuthContext: {
    Provider: ({ children, value }: { children: React.ReactNode; value: unknown }) => children,
  },
}));
```

**For testing the login flow:**

```typescript
import { signInWithPopup } from 'firebase/auth';
vi.mock('firebase/auth');

test('handles login error', async () => {
  vi.mocked(signInWithPopup).mockRejectedValueOnce(new Error('popup-closed-by-user'));
  render(<Login />);

  await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

  expect(screen.getByText(/sign in failed/i)).toBeInTheDocument();
});
```

See the **firebase** skill for auth flow details.

---

## Mocking API Responses (fetch)

This project uses raw `fetch()` via `ApiClient` in `src/utils/api.ts`. Mock at the `fetch` level in tests.

```typescript
// Mock global fetch
vi.stubGlobal('fetch', vi.fn());

test('displays extracted parties after upload', async () => {
  const mockResponse = {
    parties: [
      { name: 'John Smith', entity_type: 'INDIVIDUAL', address: '123 Main St' },
    ],
    total_count: 1,
  };

  vi.mocked(fetch).mockResolvedValueOnce({
    ok: true,
    json: async () => mockResponse,
  } as Response);

  render(<Extract />);
  const file = new File(['pdf'], 'exhibit-a.pdf', { type: 'application/pdf' });
  await userEvent.upload(screen.getByRole('button'), file);

  expect(await screen.findByText('John Smith')).toBeInTheDocument();
});

test('shows error on upload failure', async () => {
  vi.mocked(fetch).mockResolvedValueOnce({
    ok: false,
    status: 422,
    json: async () => ({ detail: 'Invalid PDF format' }),
  } as Response);

  render(<Extract />);
  // ... upload and assert error message shown
});
```

**WARNING: Don't mock `ApiClient` methods directly** — mock `fetch` instead. The `ApiClient` class wraps `fetch`, so testing at the `ApiClient` level tests implementation details that can change.

---

## Dev Server API Mocking (MSW)

For development without a running backend, use Mock Service Worker (MSW). MSW intercepts `fetch` calls at the Service Worker level — no code changes needed in components.

```bash
npm install -D msw
npx msw init public/ --save
```

```typescript
// frontend/src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.post('/api/extract/upload', () => {
    return HttpResponse.json({
      parties: [
        { name: 'Test Party', entity_type: 'INDIVIDUAL', address: '123 Test St' },
      ],
      total_count: 1,
    });
  }),

  http.get('/api/proration/rrc/status', () => {
    return HttpResponse.json({ oil_count: 15000, gas_count: 8000 });
  }),
];
```

```typescript
// frontend/src/mocks/browser.ts
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';
export const worker = setupWorker(...handlers);
```

```typescript
// frontend/src/main.tsx — enable in dev only
if (import.meta.env.DEV && import.meta.env.VITE_MOCK_API === 'true') {
  const { worker } = await import('./mocks/browser');
  await worker.start({ onUnhandledRequest: 'bypass' });
}
```

---

## Mocking Browser APIs

Some browser APIs aren't available in jsdom (Vitest's test environment).

```typescript
// Mock URL.createObjectURL for file download tests
global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
global.URL.revokeObjectURL = vi.fn();

// Mock window.location for redirect tests
Object.defineProperty(window, 'location', {
  value: { href: '', assign: vi.fn(), reload: vi.fn() },
  writable: true,
});

// Mock ResizeObserver (used by some layout components)
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));
```

Place persistent mocks in `src/test/setup.ts` — they run before every test file.
