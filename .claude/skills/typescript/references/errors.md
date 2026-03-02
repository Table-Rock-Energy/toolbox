# TypeScript Errors Reference

## Contents
- Strict Null Checks
- Type Assertion Errors
- Generic Constraint Errors
- Module Resolution Errors
- React-Specific Errors

---

## Strict Null Checks

### ERROR: Object is possibly 'null' or 'undefined'

```typescript
// BAD
const user = users.find(u => u.email === email);
console.log(user.name); // ERROR: Object is possibly 'undefined'
```

```typescript
// FIX 1: Type guard
const user = users.find(u => u.email === email);
if (user) {
  console.log(user.name); // Safe
}
```

```typescript
// FIX 2: Nullish coalescing
const userName = users.find(u => u.email === email)?.name ?? 'Unknown';
```

```typescript
// FIX 3: Non-null assertion (use sparingly)
const user = users.find(u => u.email === email)!;
console.log(user.name); // Asserts user is not undefined
```

**When to use `!`:**
Only when you have external guarantees (e.g., data loaded from database with foreign key constraints). Prefer type guards.

---

### ERROR: Property 'x' does not exist on type 'never'

```typescript
// BAD
function getStatusColor(status: string) {
  if (status === 'success') {
    return 'green';
  } else if (status === 'error') {
    return 'red';
  }
  
  // TypeScript narrows status to never here
  return status.toLowerCase(); // ERROR: Property 'toLowerCase' does not exist on type 'never'
}
```

**Why this happens:**
TypeScript exhausted all possible values. After the if/else, `status` can't be any string because you checked for all cases.

```typescript
// FIX: Add default case
function getStatusColor(status: string) {
  if (status === 'success') {
    return 'green';
  } else if (status === 'error') {
    return 'red';
  } else {
    return 'gray'; // Handle remaining strings
  }
}
```

---

## Type Assertion Errors

### ERROR: Conversion of type 'X' to type 'Y' may be a mistake

```typescript
// BAD
const user = { name: 'Alice', age: 30 };
const admin = user as Admin; // ERROR: Conversion may be a mistake
```

**Why this fails:**
TypeScript blocks unsafe casts. `user` doesn't have `Admin` properties, so the cast is likely a bug.

```typescript
// FIX 1: Use type guard
function isAdmin(user: User): user is Admin {
  return 'permissions' in user;
}

if (isAdmin(user)) {
  const admin = user; // Type narrowed to Admin
}
```

```typescript
// FIX 2: Double assertion (escape hatch)
const admin = user as unknown as Admin;
// First cast to unknown, then to Admin
// ONLY use when you're certain TypeScript is wrong
```

**Real-world scenario:**
API returns `unknown`. You know the shape is `User`, but TypeScript doesn't.

```typescript
// GOOD
const response = await fetch('/api/users/me');
const data: unknown = await response.json();

if (
  typeof data === 'object' &&
  data !== null &&
  'email' in data &&
  'uid' in data
) {
  const user = data as User; // Safe after validation
}
```

---

## Generic Constraint Errors

### ERROR: Type 'T' is not assignable to type 'object'

```typescript
// BAD
function getKeys<T>(obj: T): Array<keyof T> {
  return Object.keys(obj); // ERROR: Type 'T' is not assignable to type 'object'
}
```

**Why this fails:**
`T` could be `string` or `number`, which don't have keys. TypeScript requires a constraint.

```typescript
// FIX: Constrain to object
function getKeys<T extends object>(obj: T): Array<keyof T> {
  return Object.keys(obj) as Array<keyof T>;
}
```

---

### ERROR: Property 'x' does not exist on type 'T'

```typescript
// BAD
function getValue<T>(obj: T, key: string): any {
  return obj[key]; // ERROR: Property 'key' does not exist on type 'T'
}
```

```typescript
// FIX: Use keyof constraint
function getValue<T extends object, K extends keyof T>(
  obj: T,
  key: K
): T[K] {
  return obj[key]; // Safe
}
```

---

## Module Resolution Errors

### ERROR: Cannot find module 'X' or its corresponding type declarations

```typescript
// BAD
import { auth } from 'firebase/auth';
// ERROR: Cannot find module 'firebase/auth'
```

**Common causes:**
1. Package not installed (`npm install firebase`)
2. Missing `@types/X` package for JavaScript libraries
3. Incorrect module path

```bash
# FIX 1: Install package
npm install firebase

# FIX 2: Install type definitions
npm install --save-dev @types/react

# FIX 3: Check tsconfig.json moduleResolution
# "moduleResolution": "bundler" (for Vite)
# "moduleResolution": "node" (for Node.js)
```

---

### ERROR: Module has no exported member 'X'

```typescript
// BAD
import { DataTable } from '../components/DataTable';
// ERROR: Module has no exported member 'DataTable'
```

**Why this fails:**
`DataTable.tsx` uses `export default`, not named export.

```typescript
// FIX 1: Use default import
import DataTable from '../components/DataTable';
```

```typescript
// FIX 2: Change component to named export
// DataTable.tsx
export function DataTable<T extends object>(props: DataTableProps<T>) {
  // ...
}

// Usage
import { DataTable } from '../components/DataTable';
```

**Project convention:** This codebase uses `export default` for components, named exports for utilities.

---

## React-Specific Errors

### ERROR: JSX element type 'X' does not have any construct or call signatures

```typescript
// BAD
const Component = 'div'; // string, not a component
return <Component />; // ERROR
```

```typescript
// FIX: Use proper component type
const Component: React.ComponentType<{ children?: React.ReactNode }> = 'div' as any;

// Better: Use string literals directly
return <div />;
```

---

### ERROR: Property 'children' does not exist on type 'PropsWithChildren<X>'

```typescript
// BAD
interface ModalProps {
  isOpen: boolean;
}

function Modal({ isOpen, children }: ModalProps) {
  // ERROR: Property 'children' does not exist on type 'ModalProps'
}
```

```typescript
// FIX 1: Explicitly add children
interface ModalProps {
  isOpen: boolean;
  children?: React.ReactNode;
}
```

```typescript
// FIX 2: Use PropsWithChildren
import type { PropsWithChildren } from 'react';

interface ModalProps {
  isOpen: boolean;
}

function Modal({ isOpen, children }: PropsWithChildren<ModalProps>) {
  // children is now available
}
```

---

### ERROR: Type 'X' is not assignable to type 'ReactNode'

```typescript
// BAD
interface CardProps {
  title: string;
  body: object; // Objects can't be rendered
}

function Card({ title, body }: CardProps) {
  return (
    <div>
      <h2>{title}</h2>
      <div>{body}</div> // ERROR: Type 'object' is not assignable to type 'ReactNode'
    </div>
  );
}
```

```typescript
// FIX: Use React.ReactNode
interface CardProps {
  title: string;
  body: React.ReactNode; // Can be string, number, JSX, etc.
}
```

**`ReactNode` includes:**
- `string`, `number`, `boolean`, `null`, `undefined`
- JSX elements (`<div />`)
- Arrays of ReactNodes
- Fragments (`<></>`)

---

## Advanced Error Fixes

### ERROR: Excessive stack depth comparing types

**Cause:** Recursive types or circular references.

```typescript
// BAD
type InfiniteArray<T> = T | InfiniteArray<T>[];
// TypeScript can't infer depth, hits recursion limit
```

```typescript
// FIX: Add depth limit
type LimitedArray<T, Depth extends number = 5> = Depth extends 0
  ? T
  : T | LimitedArray<T, [-1, 0, 1, 2, 3, 4, 5][Depth]>[];
```

**Real-world:**
This rarely happens in application code. If you see this, refactor recursive types.

---

### ERROR: Expression produces a union type that is too complex to represent

**Cause:** Too many union branches (TypeScript limit ~100,000).

```typescript
// BAD - Generating 10,000 union members
type HugeUnion = /* thousands of string literals */;
```

**Fix:** Use `string` or `enum` instead of literal unions for large sets.