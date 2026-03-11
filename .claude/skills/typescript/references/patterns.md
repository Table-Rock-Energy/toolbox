# TypeScript Patterns Reference

## Contents
- Strict Mode Configuration (actual tsconfig)
- Generic Patterns
- Type Guards and Narrowing
- Error Handling Patterns
- Import Patterns

---

## Strict Mode Configuration

Actual `frontend/tsconfig.app.json` compiler options:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  }
}
```

Key constraints:
- `verbatimModuleSyntax` — all type-only imports MUST use inline `type` keyword
- `erasableSyntaxOnly` — no `const enum`, no decorators with metadata, no legacy namespace syntax
- `noUnusedLocals/Parameters` — compilation fails for unused variables or parameters

---

## Generic Patterns

### Generic Component with `extends object`

```typescript
// GOOD — DataTable.tsx actual pattern
interface Column<T> {
  key: keyof T | string   // string allows dot-path access like 'user.name'
  header: string
  render?: (item: T) => React.ReactNode
  sortable?: boolean
}

interface DataTableProps<T> {
  data: T[]
  columns: Column<T>[]
  pageSize?: number
  onRowClick?: (item: T) => void
}

export default function DataTable<T extends object>({ data, columns }: DataTableProps<T>) {
  // Dynamic key access requires Record cast — no other safe way with strict mode
  const getValue = (item: T, key: string): unknown => {
    const keys = key.split('.')
    let value: unknown = item
    for (const k of keys) {
      value = (value as Record<string, unknown>)?.[k]
    }
    return value
  }
}
```

```typescript
// BAD — No constraint allows primitives, breaking keyof
interface DataTableProps<T> {
  data: T[]
  columns: Array<{ key: string; label: string }>  // Lost type safety on key
}
// Allows: <DataTable<number> ...> which breaks keyof
```

**Why `extends object`:** Without it, TypeScript permits `T = string | number`, making `keyof T` meaningless. The constraint guarantees indexable object keys.

---

### Type-Safe API Client (Actual Pattern)

```typescript
// GOOD — utils/api.ts pattern
interface ApiResponse<T> {
  data: T | null
  error: string | null
  status: number
}

class ApiClient {
  private async request<T>(endpoint: string, options: ApiRequestOptions = {}): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, { ... })
      const data = await response.json() as T
      return { data, error: null, status: response.status }
    } catch (error) {
      return {
        data: null,
        error: error instanceof Error ? error.message : 'An unexpected error occurred',
        status: 0,
      }
    }
  }

  async get<T>(endpoint: string) {
    return this.request<T>(endpoint, { method: 'GET' })
  }
}
```

```typescript
// BAD — Untyped response
async getUsers() {
  const response = await fetch('/api/admin/users')
  return response.json()  // returns any — defeats TypeScript
}
```

**Real-world failure:** Backend renames `entity_type` to `entityType`. Untyped code compiles but crashes at runtime accessing `.entity_type` which is now `undefined`.

---

## Type Guards and Narrowing

### Discriminated Unions for State

```typescript
// GOOD — status field is the discriminant
type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string }

// In switch: TypeScript knows exactly what properties exist per case
switch (state.status) {
  case 'success':
    return <div>{state.data}</div>  // TypeScript knows data exists
  case 'error':
    return <div>{state.error}</div>  // TypeScript knows error exists
}
```

```typescript
// BAD — Boolean flags allow impossible combinations
interface State<T> {
  isLoading: boolean
  isError: boolean
  data?: T
  error?: string
}
// isLoading: true + isError: true + data present = impossible but representable
```

---

### Narrowing Firebase Auth errors

```typescript
// AuthContext.tsx pattern — cast to known error shape then check code
} catch (error: unknown) {
  const firebaseError = error as { code?: string }
  if (firebaseError.code === 'auth/wrong-password') {
    throw new Error('Incorrect password.')
  } else if (firebaseError.code === 'auth/too-many-requests') {
    throw new Error('Too many failed attempts. Please try again later.')
  }
  throw new Error('Login failed. Please try again.')
}
```

---

## Error Handling Patterns

### Typed catch blocks

```typescript
// GOOD — strict mode makes catch(error) type unknown
} catch (error) {
  if (error instanceof Error) {
    return { data: null, error: error.message, status: 0 }
  }
  return { data: null, error: 'An unexpected error occurred', status: 0 }
}
```

```typescript
// BAD — accessing .message without narrowing
} catch (error) {
  console.error(error.message)  // Type error: Object is of type 'unknown'
}
```

**Why this matters:** In strict mode, `catch (error)` is typed as `unknown`, not `any`. Every property access requires narrowing first or you get a compile error.

---

## Import Patterns

### verbatimModuleSyntax: inline type keyword

```typescript
// GOOD — inline type keyword (required by verbatimModuleSyntax)
import { createContext, useContext, type ReactNode } from 'react'
import { type User } from 'firebase/auth'
import { useState, useEffect } from 'react'  // values don't need 'type'

// ALSO GOOD but inconsistent with codebase style
import type { ReactNode } from 'react'

// BAD — importing type as value (fails with verbatimModuleSyntax)
import { User } from 'firebase/auth'  // if User is only used as a type
```

**Why verbatimModuleSyntax:** It prevents TypeScript from silently eliding imports, which can cause side effects from library imports to vanish unexpectedly. The `type` keyword makes elision explicit.

### Barrel Exports

```typescript
// components/index.ts — actual pattern
export { default as Sidebar } from './Sidebar'
export { default as FileUpload } from './FileUpload'
export { default as DataTable } from './DataTable'
export { default as StatusBadge } from './StatusBadge'
export { default as Modal } from './Modal'
```

**WARNING:** Components MUST NOT import from their own barrel (`index.ts`). `Modal.tsx` importing from `./index` creates a circular dependency that causes `undefined` at runtime in bundlers.

### Import order (enforced by ESLint)

```typescript
// 1. External packages
import { useState, useEffect, type ReactNode } from 'react'
import { Upload } from 'lucide-react'

// 2. Internal relative imports
import { DataTable, Modal } from '../components'
import { useAuth } from '../contexts/AuthContext'

// 3. Types (when using separate import type statement)
import type { PartyEntry } from '../utils/api'
```
