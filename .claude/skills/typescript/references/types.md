# TypeScript Types Reference

## Contents
- Interface vs Type
- Utility Types
- Generic Constraints
- Discriminated Unions
- Type Inference

---

## Interface vs Type

### When to Use Interface

```typescript
// GOOD - Component props (extendable)
interface ButtonProps {
  label: string;
  onClick: () => void;
}

interface PrimaryButtonProps extends ButtonProps {
  color: 'blue' | 'green';
}
```

```typescript
// GOOD - API response shapes (can merge declarations)
interface User {
  email: string;
  uid: string;
}

interface User {
  displayName?: string; // Declaration merging
}
```

**Use `interface` for:**
- React component props (extendable, clear intent)
- Object shapes that might need declaration merging
- Public APIs where consumers might extend types

---

### When to Use Type

```typescript
// GOOD - Unions
type Status = 'idle' | 'loading' | 'success' | 'error';

type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string };
```

```typescript
// GOOD - Mapped types
type Readonly<T> = {
  readonly [K in keyof T]: T[K];
};

type Optional<T> = {
  [K in keyof T]?: T[K];
};
```

**Use `type` for:**
- Union types (`'a' | 'b' | 'c'`)
- Intersection types (`A & B`)
- Mapped types (`{ [K in keyof T]: ... }`)
- Tuple types (`[string, number]`)

---

## WARNING: Interface Declaration Merging

```typescript
// BAD - Accidental global pollution
// file1.ts
interface Window {
  myCustomProp: string;
}

// file2.ts
interface Window {
  anotherProp: number;
}

// Both declarations merge into global Window
// This can cause conflicts in large codebases
```

**Why this breaks:**
Interface merging is implicit. If two files declare the same interface, TypeScript silently merges them. This can hide conflicts until runtime.

**The fix:**
Use `type` for internal types, `interface` only for extensibility contracts.

---

## Utility Types

### Pick, Omit, Partial, Required

```typescript
// GOOD - toolbox/frontend/src/pages/Extract.tsx
interface PartyEntry {
  name: string;
  address: string;
  entity_type: 'Individual' | 'Trust' | 'LLC' | 'Corporation';
  ownership_decimal: number;
  notes?: string;
}

// Extract subset for display
type PartyPreview = Pick<PartyEntry, 'name' | 'entity_type'>;

// Exclude sensitive fields
type PublicParty = Omit<PartyEntry, 'ownership_decimal'>;

// Make all fields optional for updates
type PartyUpdate = Partial<PartyEntry>;

// Ensure all fields are required
type CompleteParty = Required<PartyEntry>;
```

**Real-world usage:**
When rendering a table, use `Pick` to select only displayed columns. When sending PATCH requests, use `Partial` to allow partial updates.

---

### Record for Type-Safe Maps

```typescript
// GOOD
type EntityTypeLabel = Record<
  'Individual' | 'Trust' | 'LLC' | 'Corporation',
  string
>;

const ENTITY_LABELS: EntityTypeLabel = {
  Individual: 'Individual',
  Trust: 'Trust',
  LLC: 'Limited Liability Company',
  Corporation: 'Corporation',
};

// TypeScript enforces all keys are present
```

```typescript
// BAD - Untyped object
const ENTITY_LABELS = {
  Individual: 'Individual',
  Trust: 'Trust',
  // Missing LLC and Corporation - no error
};

const label = ENTITY_LABELS['LLC']; // Undefined at runtime
```

**Why `Record` is superior:**
1. Guarantees all keys are present (no accidental `undefined`)
2. Autocomplete for keys
3. Prevents typos in key names

---

### ReturnType for Derived Types

```typescript
// GOOD - Infer return type from function
async function fetchUsers() {
  const response = await fetch('/api/admin/users');
  return response.json() as Promise<Array<{ email: string; role: string }>>;
}

type User = Awaited<ReturnType<typeof fetchUsers>>[number];
// User = { email: string; role: string }
```

**When to use:**
When a function's return type is the source of truth. This keeps types in sync with implementation.

---

## Generic Constraints

### Extending Object for Indexable Types

```typescript
// GOOD - toolbox/frontend/src/components/DataTable.tsx
interface DataTableProps<T extends object> {
  data: T[];
  columns: Array<{
    key: keyof T; // Only works if T is an object
    label: string;
  }>;
}
```

```typescript
// BAD - No constraint
interface DataTableProps<T> {
  data: T[];
  columns: Array<{ key: string; label: string }>; // Lost type safety
}

// Caller can pass T = number, breaking keyof
<DataTable<number> data={[1, 2, 3]} columns={[{ key: 'invalid', label: 'Bad' }]} />
```

**Why constraints matter:**
`keyof T` requires `T` to be an object. Without `extends object`, TypeScript allows primitive types, breaking the contract.

---

### Constraining to Specific Keys

```typescript
// GOOD - Only allow string keys
function getValue<T extends object, K extends keyof T>(
  obj: T,
  key: K
): T[K] {
  return obj[key];
}

const user = { name: 'Alice', age: 30 };
const name = getValue(user, 'name'); // Type: string
const age = getValue(user, 'age');   // Type: number
const invalid = getValue(user, 'email'); // ERROR: 'email' not in user
```

**Real-world usage:**
This pattern is used in `DataTable` to ensure `col.render` receives the correct value type for each column.

---

## Discriminated Unions

### Type-Safe State Machines

```typescript
// GOOD - Proration upload states
type UploadState =
  | { status: 'idle' }
  | { status: 'uploading'; progress: number }
  | { status: 'processing'; rowsProcessed: number }
  | { status: 'complete'; results: MineralHolderRow[] }
  | { status: 'error'; message: string };

function UploadStatus({ state }: { state: UploadState }) {
  switch (state.status) {
    case 'idle':
      return <div>Ready to upload</div>;
    case 'uploading':
      return <ProgressBar value={state.progress} />; // TypeScript knows progress exists
    case 'processing':
      return <div>Processed {state.rowsProcessed} rows</div>;
    case 'complete':
      return <div>Found {state.results.length} entries</div>;
    case 'error':
      return <div className="error">{state.message}</div>;
  }
}
```

**Why discriminated unions prevent bugs:**
1. **Impossible states are unrepresentable** - Can't have `status: 'error'` with `results` present
2. **Exhaustiveness checking** - If you add a new status, TypeScript forces you to handle it
3. **Type narrowing** - In each `case`, TypeScript knows exactly which properties exist

---

### Exhaustiveness Checking

```typescript
// GOOD - Compiler enforces all cases
function assertNever(value: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(value)}`);
}

function getStatusColor(state: UploadState): string {
  switch (state.status) {
    case 'idle': return 'gray';
    case 'uploading': return 'blue';
    case 'processing': return 'yellow';
    case 'complete': return 'green';
    case 'error': return 'red';
    default:
      return assertNever(state); // Compile error if a case is missing
  }
}
```

**Real-world impact:**
Add a new state `{ status: 'cancelled' }` to `UploadState`. Without `assertNever`, the code compiles but returns `undefined` for cancelled states. With it, you get a compile error pointing to every switch that needs updating.

---

## Type Inference

### Const Assertions for Literal Types

```typescript
// GOOD
const ENTITY_TYPES = ['Individual', 'Trust', 'LLC', 'Corporation'] as const;
type EntityType = typeof ENTITY_TYPES[number];
// EntityType = 'Individual' | 'Trust' | 'LLC' | 'Corporation'
```

```typescript
// BAD - Inferred as string[]
const ENTITY_TYPES = ['Individual', 'Trust', 'LLC', 'Corporation'];
type EntityType = typeof ENTITY_TYPES[number];
// EntityType = string (too broad)
```

**Why `as const` is critical:**
Without it, TypeScript infers mutable arrays (`string[]`). With it, you get a readonly tuple of literal types.

---

### Inferring Generic Parameters

```typescript
// GOOD - TypeScript infers T from usage
function useState<T>(initialValue: T): [T, (value: T) => void] {
  // Implementation
}

const [count, setCount] = useState(0); // T inferred as number
const [name, setName] = useState('Alice'); // T inferred as string
```

**When to explicitly specify:**
```typescript
const [user, setUser] = useState<User | null>(null);
// Without <User | null>, TypeScript infers null, preventing setUser(user)