# React Components Reference

## Contents
- Component Naming and Structure
- Barrel Exports Pattern
- TypeScript Generics for Reusable Components
- Layout Components with React Router
- WARNING: Prop Drilling Past 3 Levels
- WARNING: Index as Key
- WARNING: Inline Object/Array Props

---

## Component Naming and Structure

### File Naming: PascalCase.tsx

```
toolbox/frontend/src/
├── components/
│   ├── DataTable.tsx         # PascalCase
│   ├── FileUpload.tsx
│   ├── Modal.tsx
│   ├── Sidebar.tsx
│   ├── StatusBadge.tsx
│   ├── LoadingSpinner.tsx
│   └── index.ts             # Barrel export
├── pages/
│   ├── Dashboard.tsx        # PascalCase
│   ├── Extract.tsx
│   ├── Title.tsx
│   ├── Proration.tsx
│   ├── Revenue.tsx
│   ├── Settings.tsx
│   ├── Login.tsx
│   └── Help.tsx
├── contexts/
│   └── AuthContext.tsx      # PascalCase
└── layouts/
    └── MainLayout.tsx
```

### Component Function: PascalCase, Default Export

```tsx
// GOOD - toolbox/frontend pattern
export default function MainLayout() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1">
        <Outlet /> {/* React Router v7 */}
      </main>
    </div>
  );
}
```

### Props Interface: PascalCase

```tsx
// GOOD - toolbox/frontend/src/components/DataTable.tsx
interface DataTableProps<T extends object> {
  data: T[];
  columns: Array<{
    key: keyof T;
    label: string;
    render?: (value: T[keyof T], row: T) => React.ReactNode;
  }>;
  onSort?: (key: keyof T) => void;
  sortKey?: keyof T;
  sortDirection?: 'asc' | 'desc';
}

export default function DataTable<T extends object>({
  data,
  columns,
  onSort,
  sortKey,
  sortDirection
}: DataTableProps<T>) {
  // Implementation
}
```

**Why `<T extends object>`:** Ensures `T` has keys that can be used with `keyof`. Without `extends object`, TypeScript allows primitives like `string` or `number`, which break `keyof T`.

---

## Barrel Exports Pattern

### Index File for Clean Imports

```ts
// toolbox/frontend/src/components/index.ts
export { default as DataTable } from './DataTable';
export { default as FileUpload } from './FileUpload';
export { default as Modal } from './Modal';
export { default as Sidebar } from './Sidebar';
export { default as StatusBadge } from './StatusBadge';
export { default as LoadingSpinner } from './LoadingSpinner';
```

### Usage in Pages

```tsx
// GOOD - single import line
import { DataTable, Modal, StatusBadge } from '../components';

// BAD - verbose, scattered imports
import DataTable from '../components/DataTable';
import Modal from '../components/Modal';
import StatusBadge from '../components/StatusBadge';
```

---

## TypeScript Generics for Reusable Components

### Generic DataTable (Existing Pattern)

```tsx
// toolbox/frontend/src/components/DataTable.tsx
interface DataTableProps<T extends object> {
  data: T[];
  columns: Array<{
    key: keyof T;
    label: string;
    render?: (value: T[keyof T], row: T) => React.ReactNode;
  }>;
  onSort?: (key: keyof T) => void;
}

export default function DataTable<T extends object>({ data, columns, onSort }: DataTableProps<T>) {
  return (
    <table className="min-w-full divide-y divide-gray-200">
      <thead className="bg-tre-navy">
        <tr>
          {columns.map((col) => (
            <th
              key={String(col.key)}
              onClick={() => onSort?.(col.key)}
              className="px-6 py-3 text-left text-xs font-medium text-white uppercase tracking-wider cursor-pointer"
            >
              {col.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="bg-white divide-y divide-gray-200">
        {data.map((row, idx) => (
          <tr key={idx}>
            {columns.map((col) => (
              <td key={String(col.key)} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {col.render ? col.render(row[col.key], row) : String(row[col.key])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

### Usage with Type Safety

```tsx
// toolbox/frontend/src/pages/Extract.tsx pattern
interface PartyEntry {
  name: string;
  address: string;
  entity_type: string;
  decimal_interest: number;
}

function Extract() {
  const [entries, setEntries] = useState<PartyEntry[]>([]);

  return (
    <DataTable<PartyEntry>
      data={entries}
      columns={[
        { key: 'name', label: 'Party Name' },
        { key: 'entity_type', label: 'Entity Type' },
        {
          key: 'decimal_interest',
          label: 'Decimal Interest',
          render: (value) => (typeof value === 'number' ? value.toFixed(4) : '0.0000')
        }
      ]}
      onSort={(key) => console.log('Sort by', key)}
    />
  );
}
```

**Why this works:** TypeScript infers `T = PartyEntry` from `data={entries}`, so `col.key` autocompletes to `'name' | 'address' | 'entity_type' | 'decimal_interest'`. Typos like `'nam'` are caught at compile time.

---

## Layout Components with React Router

### MainLayout with Sidebar + Outlet

```tsx
// toolbox/frontend/src/layouts/MainLayout.tsx pattern
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components';

export default function MainLayout() {
  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet /> {/* Renders nested route components */}
      </main>
    </div>
  );
}
```

### Protected Route Wrapper

```tsx
// toolbox/frontend pattern for protected routes
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { LoadingSpinner } from '../components';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) return <LoadingSpinner />;
  if (!user) return <Navigate to="/login" replace />;

  return <>{children}</>;
}
```

### Router Setup with Nested Routes

```tsx
// toolbox/frontend/src/App.tsx pattern
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import { Dashboard, Extract, Title, Proration, Revenue, Settings, Login } from './pages';
import { ProtectedRoute } from './components/ProtectedRoute';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="extract" element={<Extract />} />
          <Route path="title" element={<Title />} />
          <Route path="proration" element={<Proration />} />
          <Route path="revenue" element={<Revenue />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

---

## WARNING: Prop Drilling Past 3 Levels

**The Problem:**

```tsx
// BAD - passing user through 4 levels
function App() {
  const [user, setUser] = useState(null);
  return <Dashboard user={user} />;
}

function Dashboard({ user }) {
  return <ToolsList user={user} />;
}

function ToolsList({ user }) {
  return <ToolCard user={user} />;
}

function ToolCard({ user }) {
  return <div>{user.name}</div>; // Finally used here
}
```

**Why This Breaks:**
1. **Brittle:** Refactoring middle components requires updating all intermediate props
2. **Maintenance nightmare:** Adding a new field to user requires touching 4 files
3. **Unused props:** ToolsList doesn't use `user`, just passes it through

**The Fix:**

```tsx
// GOOD - Context API (toolbox/frontend pattern for auth)
// contexts/AuthContext.tsx
export const AuthContext = createContext<{ user: User | null } | undefined>(undefined);

function App() {
  const [user, setUser] = useState(null);
  return (
    <AuthContext.Provider value={{ user }}>
      <Dashboard />
    </AuthContext.Provider>
  );
}

function ToolCard() {
  const { user } = useAuth(); // Direct access, no prop drilling
  return <div>{user.name}</div>;
}
```

**When You Might Be Tempted:**
When a component 3+ levels down needs global state (user, theme, locale). Always ask: "Is this being passed through intermediates that don't use it?" If yes, use Context.

---

## WARNING: Index as Key

**The Problem:**

```tsx
// BAD - index as key causes incorrect reconciliation
function PartyList({ parties }: { parties: PartyEntry[] }) {
  return (
    <ul>
      {parties.map((party, index) => (
        <li key={index}>{party.name}</li> // WRONG
      ))}
    </ul>
  );
}
```

**Why This Breaks:**
1. **State loss:** If you delete the first party, React reuses the DOM nodes for the remaining parties but their keys shift. Input focus, scroll position, and component state get mismatched.
2. **Real-world scenario:** User checks checkbox on "John Doe" (index 0), then sorts the list. Checkbox now appears on "Jane Smith" (new index 0).

**The Fix:**

```tsx
// GOOD - stable unique ID
function PartyList({ parties }: { parties: PartyEntry[] }) {
  return (
    <ul>
      {parties.map((party) => (
        <li key={party.id}>{party.name}</li> // Assumes each party has unique id
      ))}
    </ul>
  );
}

// If no ID exists, generate one
const [parties, setParties] = useState(() =>
  initialParties.map((p, i) => ({ ...p, id: `party-${i}-${Date.now()}` }))
);
```

**When You Might Be Tempted:**
Whenever you render a list. ESLint often suggests adding `key={index}` to silence the warning. **Ignore that suggestion** if the list can reorder, filter, or have items deleted.

---

## WARNING: Inline Object/Array Props

**The Problem:**

```tsx
// BAD - new object every render
function ExtractPage() {
  const [entries, setEntries] = useState<PartyEntry[]>([]);

  return (
    <DataTable
      data={entries}
      columns={[
        { key: 'name', label: 'Name' },      // New array every render
        { key: 'type', label: 'Type' }
      ]}
    />
  );
}

// Inside DataTable (if memoized):
const MemoizedTable = React.memo(DataTable);
// WRONG: columns prop is a new reference every render, so memoization fails
```

**Why This Breaks:**
1. **Breaks memoization:** If DataTable uses `React.memo`, it re-renders every time because `columns` is a new array reference
2. **Performance impact:** For large lists (500+ rows), this causes unnecessary reconciliation

**The Fix:**

```tsx
// GOOD - extract to constant outside component
const EXTRACT_COLUMNS = [
  { key: 'name' as const, label: 'Party Name' },
  { key: 'entity_type' as const, label: 'Entity Type' },
  { key: 'decimal_interest' as const, label: 'Decimal Interest' }
] as const;

function ExtractPage() {
  const [entries, setEntries] = useState<PartyEntry[]>([]);

  return <DataTable data={entries} columns={EXTRACT_COLUMNS} />;
}
```

**Alternative with useMemo (if columns are dynamic):**

```tsx
function ExtractPage({ showAddress }: { showAddress: boolean }) {
  const columns = useMemo(() => {
    const cols = [
      { key: 'name' as const, label: 'Name' },
      { key: 'type' as const, label: 'Type' }
    ];
    if (showAddress) cols.push({ key: 'address' as const, label: 'Address' });
    return cols;
  }, [showAddress]); // Only recomputes when showAddress changes

  return <DataTable data={entries} columns={columns} />;
}
```

**When You Might Be Tempted:**
Any time you pass `[]`, `{}`, or function literals as props. If the component is memoized or the prop is used in a dependency array, extract to a constant.