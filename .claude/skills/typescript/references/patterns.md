# TypeScript Patterns Reference

## Contents
- Strict Mode Configuration
- Generic Patterns
- Type Guards and Narrowing
- Error Handling Patterns
- Import Patterns

---

## Strict Mode Configuration

This project uses **strict mode** in `toolbox/frontend/tsconfig.app.json`:

```json
{
  "compilerOptions": {
    "strict": true,
    "strictNullChecks": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitAny": true,
    "noImplicitReturns": true
  }
}
```

**Why strict mode matters:**
1. Catches null/undefined bugs at compile time
2. Forces explicit handling of edge cases
3. Prevents `any` from leaking through the codebase

---

## Generic Patterns

### Generic Component with Constraints

```typescript
// GOOD - toolbox/frontend/src/components/DataTable.tsx
interface DataTableProps<T extends object> {
  data: T[];
  columns: Array<{
    key: keyof T;
    label: string;
    render?: (value: T[keyof T], row: T) => React.ReactNode;
  }>;
}

function DataTable<T extends object>({ data, columns }: DataTableProps<T>) {
  // TypeScript knows T has object keys
  return <table>...</table>;
}

// Usage is type-safe
<DataTable<PartyEntry> data={parties} columns={[
  { key: 'name', label: 'Name' },
  { key: 'invalid_key', label: 'Bad' } // ERROR: 'invalid_key' not in PartyEntry
]} />
```

```typescript
// BAD - No constraint
interface DataTableProps<T> {
  data: T[];
  columns: Array<{ key: string; label: string }>; // Lost type safety
}
```

**Why `extends object` is critical:**
Without the constraint, TypeScript allows `T = string` or `T = number`, breaking `keyof T` operations. The constraint ensures `T` has indexable keys.

---

### Type-Safe API Client

```typescript
// GOOD - toolbox/frontend/src/utils/api.ts
class ApiClient {
  private async request<TResponse>(
    endpoint: string,
    options?: RequestInit
  ): Promise<TResponse> {
    const response = await fetch(`/api${endpoint}`, options);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return response.json() as Promise<TResponse>;
  }
  
  async getUsers(): Promise<User[]> {
    return this.request<User[]>('/admin/users');
  }
  
  async uploadFile(file: File): Promise<ProcessingResult> {
    const formData = new FormData();
    formData.append('file', file);
    return this.request<ProcessingResult>('/extract/upload', {
      method: 'POST',
      body: formData,
    });
  }
}
```

```typescript
// BAD - Untyped responses
class ApiClient {
  async getUsers() {
    const response = await fetch('/api/admin/users');
    return response.json(); // Returns any
  }
}
```

**Why this breaks:**
Without generic return types, `response.json()` returns `any`, defeating TypeScript. This leads to runtime errors when the API changes but the frontend doesn't.

**Real-world failure:**
Backend renames `entity_type` to `entityType`. Untyped code compiles but crashes at runtime with "undefined is not an object".

---

## Type Guards and Narrowing

### Discriminated Unions for State

```typescript
// GOOD - Type-safe loading states
type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string };

function DataDisplay<T>({ state }: { state: AsyncState<T> }) {
  switch (state.status) {
    case 'idle':
      return <div>Click to load</div>;
    case 'loading':
      return <LoadingSpinner />;
    case 'success':
      return <div>{JSON.stringify(state.data)}</div>; // TypeScript knows data exists
    case 'error':
      return <div>Error: {state.error}</div>; // TypeScript knows error exists
  }
}
```

```typescript
// BAD - Boolean flags
interface State<T> {
  isLoading: boolean;
  isError: boolean;
  data?: T;
  error?: string;
}

// Problem: All states can be true simultaneously
const badState: State<User> = {
  isLoading: true,
  isError: true,
  data: user,
  error: 'Failed',
};
```

**Why discriminated unions are superior:**
1. **Mutually exclusive states** - Only one status can be true at a time
2. **TypeScript flow analysis** - In `case 'success'`, TypeScript knows `data` exists
3. **No invalid states** - Can't have `isLoading: true` with `data` present

---

### Type Guards for Firebase Auth

```typescript
// GOOD - toolbox/frontend/src/contexts/AuthContext.tsx
import type { User as FirebaseUser } from 'firebase/auth';

interface User {
  email: string;
  displayName: string;
  uid: string;
}

function isValidFirebaseUser(user: FirebaseUser | null): user is FirebaseUser {
  return user !== null && user.email !== null;
}

function mapFirebaseUser(firebaseUser: FirebaseUser): User {
  if (!firebaseUser.email) {
    throw new Error('User email is required');
  }
  
  return {
    email: firebaseUser.email,
    displayName: firebaseUser.displayName || 'Unknown',
    uid: firebaseUser.uid,
  };
}

// Usage
onAuthStateChanged(auth, (firebaseUser) => {
  if (isValidFirebaseUser(firebaseUser)) {
    setUser(mapFirebaseUser(firebaseUser)); // Type-safe
  } else {
    setUser(null);
  }
});
```

**Why this matters:**
Firebase's `User.email` is `string | null`. Without type guards, every access requires null checks. The guard centralizes validation.

---

## Error Handling Patterns

### Type-Safe Error Boundaries

```typescript
// GOOD - Typed error extraction
interface ApiError {
  status: number;
  message: string;
}

function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    'message' in error
  );
}

async function handleUpload(file: File) {
  try {
    const result = await apiClient.uploadFile(file);
    return result;
  } catch (error: unknown) {
    if (isApiError(error)) {
      console.error(`API error ${error.status}: ${error.message}`);
    } else if (error instanceof Error) {
      console.error(`Error: ${error.message}`);
    } else {
      console.error('Unknown error:', error);
    }
    throw error;
  }
}
```

```typescript
// BAD - Untyped catch
async function handleUpload(file: File) {
  try {
    return await apiClient.uploadFile(file);
  } catch (error) { // Implicitly any
    console.error(error.message); // Unsafe access
  }
}
```

**Why typed errors are critical:**
In strict mode, `catch (error)` is `unknown`, not `any`. You MUST narrow the type before accessing properties, preventing runtime crashes.

---

## Import Patterns

### Type-Only Imports

```typescript
// GOOD - toolbox/frontend/src/pages/Extract.tsx
import type { PartyEntry } from '../utils/api';
import { ApiClient } from '../utils/api';

function Extract() {
  const [parties, setParties] = useState<PartyEntry[]>([]);
  // PartyEntry is erased at runtime, no bundle bloat
}
```

```typescript
// BAD - Runtime import for types
import { PartyEntry, ApiClient } from '../utils/api';
// If PartyEntry has default values, they're bundled unnecessarily
```

**When to use `import type`:**
- Importing interfaces, type aliases, or types used only in type annotations
- Not needed for React components (they're values at runtime)

**Bundle impact:**
Type-only imports are erased during compilation, reducing bundle size by ~5-10% in large codebases.

---

### Barrel Exports

```typescript
// GOOD - toolbox/frontend/src/components/index.ts
export { default as DataTable } from './DataTable';
export { default as FileUpload } from './FileUpload';
export { default as Modal } from './Modal';
export type { DataTableProps } from './DataTable';
export type { FileUploadProps } from './FileUpload';
```

```typescript
// Usage
import { DataTable, Modal } from '../components';
import type { DataTableProps } from '../components';
```

**WARNING:** Barrel exports can cause circular dependencies. If `ComponentA.tsx` imports from `index.ts` which re-exports `ComponentA`, the module graph breaks.

**Fix:** Only barrel-export components that don't import from the same barrel.

---

## Async/Await Patterns

### Type-Safe Promise Handling

```typescript
// GOOD
async function fetchRRCStatus(): Promise<{ oil_count: number; gas_count: number }> {
  const response = await fetch('/api/proration/rrc/status');
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  const data: unknown = await response.json();
  
  if (
    typeof data === 'object' &&
    data !== null &&
    'oil_count' in data &&
    'gas_count' in data
  ) {
    return data as { oil_count: number; gas_count: number };
  }
  
  throw new Error('Invalid API response');
}
```

**Why validate `response.json()`:**
The API might return a different shape than expected. Runtime validation prevents `undefined` errors when accessing properties.