# Unit Testing Reference (Vitest)

## Contents
- Vitest Setup
- Component Testing Patterns
- Testing Utilities and Custom Hooks
- Anti-Patterns
- Validation Loop

---

> **WARNING:** This project has no frontend test suite. No `vitest` is installed in `frontend/package.json`. Use this reference when adding tests.

## Vitest Setup

```bash
# Install Vitest + testing utilities
npm install -D vitest @vitest/ui jsdom @testing-library/react @testing-library/user-event
```

```typescript
// frontend/vite.config.ts — add test config
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
  // ... existing server/build config
});
```

```typescript
// frontend/src/test/setup.ts
import '@testing-library/jest-dom';
```

```json
// frontend/package.json — add test scripts
{
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:run": "vitest run"
  }
}
```

---

## Component Testing Patterns

### Testing a Tool Page Component

```tsx
// src/pages/Extract.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import Extract from './Extract';

// Wrap with router and auth context
import { MemoryRouter } from 'react-router-dom';
import { AuthContext } from '../contexts/AuthContext';

const mockUser = { email: 'james@tablerocktx.com', uid: 'test-uid' };
const mockAuthValue = { user: mockUser, loading: false };

function renderExtract() {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={mockAuthValue}>
        <Extract />
      </AuthContext.Provider>
    </MemoryRouter>
  );
}

test('shows file upload area on initial render', () => {
  renderExtract();
  expect(screen.getByText(/drop pdf files/i)).toBeInTheDocument();
});
```

### Testing FileUpload Component

```tsx
// src/components/FileUpload.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import FileUpload from './FileUpload';

test('calls onFilesSelected with dropped files', async () => {
  const onFilesSelected = vi.fn();
  render(<FileUpload onFilesSelected={onFilesSelected} accept=".pdf" />);

  const file = new File(['pdf content'], 'exhibit-a.pdf', { type: 'application/pdf' });
  const dropzone = screen.getByRole('button');

  await userEvent.upload(dropzone, file);

  expect(onFilesSelected).toHaveBeenCalledWith([file]);
});

test('rejects non-PDF files', async () => {
  const onFilesSelected = vi.fn();
  render(<FileUpload onFilesSelected={onFilesSelected} accept=".pdf" />);

  const file = new File(['text'], 'data.csv', { type: 'text/csv' });
  const dropzone = screen.getByRole('button');
  await userEvent.upload(dropzone, file);

  expect(onFilesSelected).not.toHaveBeenCalled();
});
```

### Testing Custom Hooks

```tsx
// src/hooks/useLocalStorage.test.ts
import { renderHook, act } from '@testing-library/react';
import useLocalStorage from './useLocalStorage';

test('reads from localStorage on init', () => {
  localStorage.setItem('testKey', JSON.stringify('stored-value'));
  const { result } = renderHook(() => useLocalStorage('testKey', 'default'));
  expect(result.current[0]).toBe('stored-value');
});

test('updates localStorage on set', () => {
  const { result } = renderHook(() => useLocalStorage('testKey2', 'initial'));
  act(() => {
    result.current[1]('updated');
  });
  expect(localStorage.getItem('testKey2')).toBe('"updated"');
});
```

---

## Anti-Patterns

### WARNING: Testing Implementation Details

**The Problem:**
```tsx
// BAD - Tests internal state, not user behavior
test('sets isLoading to true when uploading', () => {
  const { result } = renderHook(() => useState(false));
  // Testing internal state variable names
  expect(result.current[0]).toBe(false); // isLoading
});
```

**Why This Breaks:**
1. Refactoring internal state variable names breaks tests
2. State variable names are not user-visible behavior
3. Tests should document WHAT the component does, not HOW

**The Fix:**
```tsx
// GOOD - Tests visible behavior
test('shows loading spinner during upload', async () => {
  render(<Extract />);
  await userEvent.upload(screen.getByRole('button'), pdfFile);
  expect(screen.getByRole('progressbar')).toBeInTheDocument();
});
```

### WARNING: Forgetting to Mock Firebase Auth

If a component uses `useAuth()`, tests will fail because Firebase is not initialized in the test environment. Always mock the `AuthContext` or the hook itself.

```tsx
// GOOD - Mock the context value
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { email: 'test@test.com' }, loading: false }),
}));
```

---

## Validation Loop

Copy this checklist when setting up Vitest:

- [ ] Install: `npm install -D vitest @vitest/ui jsdom @testing-library/react @testing-library/user-event`
- [ ] Add `test` config block to `vite.config.ts`
- [ ] Create `src/test/setup.ts` with `@testing-library/jest-dom`
- [ ] Add `"test": "vitest"` to `package.json` scripts
- [ ] Add `"types": ["vitest/globals"]` to `tsconfig.app.json` compiler options
- [ ] Run `npm test` — verify no import errors
- [ ] Write first test for `FileUpload` or `StatusBadge`
- [ ] Run `npm test` — verify test passes

See the **react** skill for component patterns and the **typescript** skill for type-safe test helpers.
