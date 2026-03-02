# React Performance Reference

## Contents
- React.memo for Expensive Components
- useMemo for Expensive Computations
- useCallback for Stable Function References
- Key Prop for List Reconciliation
- Lazy Loading Routes
- WARNING: Premature Memoization
- WARNING: Missing Key Prop

---

## React.memo for Expensive Components

**Prevents re-renders when props haven't changed.**

### When to Use React.memo

```tsx
// GOOD - memoize DataTable (expensive to render)
interface DataTableProps<T extends object> {
  data: T[];
  columns: Array<{ key: keyof T; label: string }>;
}

const DataTable = React.memo(function DataTable<T extends object>({
  data,
  columns
}: DataTableProps<T>) {
  console.log('DataTable render');
  return (
    <table>
      {/* 500+ rows */}
    </table>
  );
});

// Parent component
function ExtractPage() {
  const [filterText, setFilterText] = useState('');
  const [entries, setEntries] = useState<PartyEntry[]>([]);

  const COLUMNS = useMemo(() => [
    { key: 'name' as const, label: 'Name' },
    { key: 'type' as const, label: 'Type' }
  ], []); // Stable reference

  return (
    <div>
      <input value={filterText} onChange={(e) => setFilterText(e.target.value)} />
      <DataTable data={entries} columns={COLUMNS} />
      {/* Typing in input doesn't re-render DataTable because data/columns unchanged */}
    </div>
  );
}
```

**Why this works:** `React.memo` compares props using shallow equality. If `data` and `columns` references are the same, DataTable doesn't re-render.

### Anti-Pattern: Inline Props Break Memoization

```tsx
// BAD - inline columns create new reference every render
<DataTable
  data={entries}
  columns={[
    { key: 'name', label: 'Name' } // New array every render
  ]}
/>
// React.memo is useless because columns is a new reference
```

**Fix:** Extract columns to constant outside component or use `useMemo`.

---

## useMemo for Expensive Computations

**Caches computed values to avoid re-computing on every render.**

### Expensive Filter/Sort

```tsx
// toolbox/frontend pattern - memoize filtered/sorted data
function ExtractPage() {
  const [entries, setEntries] = useState<PartyEntry[]>([]); // 5000 entries
  const [filterText, setFilterText] = useState('');
  const [sortKey, setSortKey] = useState<keyof PartyEntry>('name');

  const filteredEntries = useMemo(() => {
    console.log('Filtering entries');
    return entries.filter(e => e.name.toLowerCase().includes(filterText.toLowerCase()));
  }, [entries, filterText]); // Only recomputes when entries or filterText changes

  const sortedEntries = useMemo(() => {
    console.log('Sorting entries');
    return [...filteredEntries].sort((a, b) => {
      if (a[sortKey] < b[sortKey]) return -1;
      if (a[sortKey] > b[sortKey]) return 1;
      return 0;
    });
  }, [filteredEntries, sortKey]);

  return <DataTable data={sortedEntries} />;
}
```

**Why useMemo matters here:** Filtering/sorting 5000 entries takes ~10ms. Without useMemo, typing in a search box re-runs the filter on every keystroke, causing lag. With useMemo, filter only runs when `filterText` changes.

### Derived Columns Configuration

```tsx
// GOOD - memoize columns based on user preferences
function DataTable({ showAddress }: { showAddress: boolean }) {
  const columns = useMemo(() => {
    const cols = [
      { key: 'name' as const, label: 'Name' },
      { key: 'type' as const, label: 'Type' }
    ];
    if (showAddress) {
      cols.push({ key: 'address' as const, label: 'Address' });
    }
    return cols;
  }, [showAddress]); // Only recomputes when showAddress changes

  return <table>{/* render with columns */}</table>;
}
```

---

## useCallback for Stable Function References

**Memoizes functions to prevent child re-renders.**

### Why useCallback Matters

```tsx
// BAD - handleSort recreated every render
function ExtractPage() {
  const [sortKey, setSortKey] = useState<keyof PartyEntry>('name');

  const handleSort = (key: keyof PartyEntry) => {
    setSortKey(key);
  };

  return <DataTable onSort={handleSort} />; // New function every render
}

// If DataTable is memoized:
const DataTable = React.memo(DataTable);
// WRONG: handleSort is a new reference, so memo fails
```

**Fix with useCallback:**

```tsx
// GOOD - stable handleSort reference
function ExtractPage() {
  const [sortKey, setSortKey] = useState<keyof PartyEntry>('name');

  const handleSort = useCallback((key: keyof PartyEntry) => {
    setSortKey(key);
  }, []); // No dependencies, never recreated

  return <DataTable onSort={handleSort} />;
  // DataTable only re-renders when data/columns change
}
```

### useCallback with Dependencies

```tsx
// GOOD - callback depends on state
function ExtractPage() {
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const handleSort = useCallback((key: keyof PartyEntry) => {
    setSortKey(key);
    setSortDirection(prev => (prev === 'asc' ? 'desc' : 'asc'));
  }, [sortDirection]); // Recreated when sortDirection changes

  return <DataTable onSort={handleSort} />;
}
```

---

## Key Prop for List Reconciliation

**Helps React efficiently update lists by identifying which items changed.**

### Stable Unique Keys (GOOD)

```tsx
// toolbox/frontend pattern - use unique ID as key
function PartyList({ parties }: { parties: PartyEntry[] }) {
  return (
    <ul>
      {parties.map((party) => (
        <li key={party.id}>{party.name}</li> // Assumes each party has unique id
      ))}
    </ul>
  );
}
```

### Generating IDs if Missing

```tsx
// Pattern: generate stable IDs when data doesn't have them
const [parties, setParties] = useState(() =>
  initialParties.map((p, i) => ({
    ...p,
    id: `party-${i}-${Date.now()}` // Stable across re-renders
  }))
);
```

---

## Lazy Loading Routes

**Code-splits routes to reduce initial bundle size.**

### React.lazy with Suspense

```tsx
// toolbox/frontend/src/App.tsx pattern (recommended addition)
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { LoadingSpinner } from './components';

// Lazy load pages
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Extract = lazy(() => import('./pages/Extract'));
const Title = lazy(() => import('./pages/Title'));
const Proration = lazy(() => import('./pages/Proration'));
const Revenue = lazy(() => import('./pages/Revenue'));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/extract" element={<Extract />} />
          <Route path="/title" element={<Title />} />
          <Route path="/proration" element={<Proration />} />
          <Route path="/revenue" element={<Revenue />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
```

**Why this matters:** Without lazy loading, the initial bundle includes all 4 tool pages. With lazy loading, each page is a separate chunk loaded on-demand.

**Bundle size impact:**
- **Without lazy loading:** 500KB initial bundle
- **With lazy loading:** 150KB initial + 4x 100KB chunks (loaded when user navigates)

---

## WARNING: Premature Memoization

**The Problem:**

```tsx
// BAD - useMemo for trivial computation
function UserProfile({ firstName, lastName }: { firstName: string; lastName: string }) {
  const fullName = useMemo(() => `${firstName} ${lastName}`, [firstName, lastName]);
  // WRONG: string concatenation is faster than useMemo overhead

  return <div>{fullName}</div>;
}
```

**Why This Breaks:**
1. **useMemo has overhead:** Comparing dependencies and managing cache costs ~0.01ms. String concat costs ~0.001ms. You made it 10x slower.
2. **Harder to read:** useMemo adds noise for no benefit.

**The Fix:**

```tsx
// GOOD - compute during render
function UserProfile({ firstName, lastName }: { firstName: string; lastName: string }) {
  const fullName = `${firstName} ${lastName}`; // Simple, fast, readable
  return <div>{fullName}</div>;
}
```

**When to use useMemo:**
- Filtering/sorting arrays with 100+ items
- Expensive regex operations
- Complex object transformations

**When NOT to use useMemo:**
- String concatenation
- Simple math (addition, multiplication)
- Accessing object properties

**Rule of thumb:** Profile first, optimize second. If render time is <16ms (60fps), don't memoize.

---

## WARNING: Missing Key Prop

**The Problem:**

```tsx
// BAD - no key prop
function PartyList({ parties }: { parties: PartyEntry[] }) {
  return (
    <ul>
      {parties.map((party) => (
        <li>{party.name}</li> // WRONG: React warns "Each child should have a unique key"
      ))}
    </ul>
  );
}
```

**Why This Breaks:**
1. **Inefficient reconciliation:** React can't tell which items moved/changed, so it re-renders the entire list.
2. **State loss:** If list items have local state (e.g., checkbox checked), reordering loses that state.

**The Fix:**

```tsx
// GOOD - stable key
function PartyList({ parties }: { parties: PartyEntry[] }) {
  return (
    <ul>
      {parties.map((party) => (
        <li key={party.id}>{party.name}</li>
      ))}
    </ul>
  );
}
```

**When You Might Be Tempted:**
Using `key={index}` to silence the warning. **Don't.** Index as key breaks reconciliation for dynamic lists (see [components.md](components.md#warning-index-as-key)).