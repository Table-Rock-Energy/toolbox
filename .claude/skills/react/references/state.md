# React State Management Reference

## Contents
- useState for Local UI State
- Context API for Auth Only
- Derived State (Computed Values)
- State Colocation
- WARNING: State for Derived Values
- WARNING: Prop Mutations
- WARNING: Over-Using Context

---

## useState for Local UI State

### UI State Examples

```tsx
// toolbox/frontend pattern - all UI state is local
function Extract() {
  const [isLoading, setIsLoading] = useState(false);           // Loading spinner
  const [showModal, setShowModal] = useState(false);          // Modal visibility
  const [selectedEntry, setSelectedEntry] = useState<PartyEntry | null>(null); // Selected row
  const [filterText, setFilterText] = useState('');           // Search filter
  const [sortKey, setSortKey] = useState<keyof PartyEntry>('name'); // Sort column
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  return (
    <div>
      <input value={filterText} onChange={(e) => setFilterText(e.target.value)} />
      <DataTable
        data={entries.filter(e => e.name.includes(filterText))}
        onSort={(key) => setSortKey(key)}
      />
      {showModal && <Modal onClose={() => setShowModal(false)} />}
    </div>
  );
}
```

**Why local state:** These values are only used in this component. If Extract unmounts, the state is discarded. No need to persist or share.

### Boolean State with is/has/should Prefix

```tsx
// GOOD - clear intent
const [isLoading, setIsLoading] = useState(false);
const [hasError, setHasError] = useState(false);
const [shouldAutoRefresh, setShouldAutoRefresh] = useState(true);

// BAD - unclear type
const [loading, setLoading] = useState(false); // Could be number, boolean, or string
```

---

## Context API for Auth Only

**This codebase uses Context ONLY for Firebase Auth. NO general state management via Context.**

### Auth Context (Existing Pattern)

```tsx
// toolbox/frontend/src/contexts/AuthContext.tsx
interface AuthContextType {
  user: User | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = getAuth();
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  return <AuthContext.Provider value={{ user, loading }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
```

### Usage in Components

```tsx
// toolbox/frontend/src/pages/Settings.tsx pattern
function Settings() {
  const { user } = useAuth();

  if (!user) return <Navigate to="/login" />;

  return (
    <div>
      <h1>Settings</h1>
      <p>Email: {user.email}</p>
      <p>Display Name: {user.displayName}</p>
    </div>
  );
}
```

---

## Derived State (Computed Values)

**NEVER store values that can be computed from other state.**

### Anti-Pattern: Redundant State

```tsx
// BAD - fullName is derived from firstName and lastName
function UserProfile() {
  const [firstName, setFirstName] = useState('John');
  const [lastName, setLastName] = useState('Doe');
  const [fullName, setFullName] = useState('John Doe'); // WRONG: duplicates data

  const handleFirstNameChange = (value: string) => {
    setFirstName(value);
    setFullName(`${value} ${lastName}`); // WRONG: manual sync
  };

  return <div>{fullName}</div>;
}
```

**Why this breaks:** If you forget to update `fullName` in one handler, the states desync.

### Correct Pattern: Compute During Render

```tsx
// GOOD - compute fullName from firstName and lastName
function UserProfile() {
  const [firstName, setFirstName] = useState('John');
  const [lastName, setLastName] = useState('Doe');

  const fullName = `${firstName} ${lastName}`; // Derived value

  return (
    <div>
      <input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
      <input value={lastName} onChange={(e) => setLastName(e.target.value)} />
      <div>{fullName}</div>
    </div>
  );
}
```

### Filtered/Sorted Data (toolbox/frontend pattern)

```tsx
// GOOD - filter/sort during render
function ExtractPage() {
  const [entries, setEntries] = useState<PartyEntry[]>([]);
  const [filterText, setFilterText] = useState('');
  const [sortKey, setSortKey] = useState<keyof PartyEntry>('name');

  // Derived values (computed during render)
  const filteredEntries = entries.filter(e => e.name.toLowerCase().includes(filterText.toLowerCase()));
  const sortedEntries = [...filteredEntries].sort((a, b) => {
    if (a[sortKey] < b[sortKey]) return -1;
    if (a[sortKey] > b[sortKey]) return 1;
    return 0;
  });

  return <DataTable data={sortedEntries} />;
}
```

**When to use useMemo:** If computing the derived value is expensive (e.g., sorting 10,000 rows), use `useMemo`:

```tsx
const sortedEntries = useMemo(() => {
  return [...filteredEntries].sort((a, b) => {
    // Expensive sort logic
  });
}, [filteredEntries, sortKey]); // Only recomputes when deps change
```

---

## State Colocation

**Keep state as close to where it's used as possible.**

### Anti-Pattern: Lifting State Too High

```tsx
// BAD - modal state in App component
function App() {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<PartyEntry | null>(null);

  return (
    <div>
      <ExtractPage onDelete={(item) => { setItemToDelete(item); setShowDeleteModal(true); }} />
      {showDeleteModal && <DeleteModal item={itemToDelete} onClose={() => setShowDeleteModal(false)} />}
    </div>
  );
}
```

**Why this is bad:** ExtractPage is the only component that uses the delete modal. Lifting state to App couples unrelated components.

### Correct Pattern: Colocate State

```tsx
// GOOD - modal state in ExtractPage
function ExtractPage() {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<PartyEntry | null>(null);

  return (
    <div>
      <DataTable onDelete={(item) => { setItemToDelete(item); setShowDeleteModal(true); }} />
      {showDeleteModal && <DeleteModal item={itemToDelete} onClose={() => setShowDeleteModal(false)} />}
    </div>
  );
}
```

**Rule of thumb:** Only lift state when 2+ sibling components need to share it. Otherwise, keep it local.

---

## WARNING: State for Derived Values

**The Problem:**

```tsx
// BAD - storing filtered entries in state
function ExtractPage() {
  const [entries, setEntries] = useState<PartyEntry[]>([]);
  const [filterText, setFilterText] = useState('');
  const [filteredEntries, setFilteredEntries] = useState<PartyEntry[]>([]); // WRONG

  useEffect(() => {
    setFilteredEntries(entries.filter(e => e.name.includes(filterText)));
  }, [entries, filterText]); // WRONG: manual sync

  return <DataTable data={filteredEntries} />;
}
```

**Why This Breaks:**
1. **Sync bugs:** If you update `entries` without triggering the useEffect (e.g., direct mutation), `filteredEntries` becomes stale
2. **Unnecessary complexity:** useEffect is overkill for a simple filter operation

**The Fix:**

```tsx
// GOOD - compute during render
function ExtractPage() {
  const [entries, setEntries] = useState<PartyEntry[]>([]);
  const [filterText, setFilterText] = useState('');

  const filteredEntries = entries.filter(e => e.name.includes(filterText)); // Derived

  return <DataTable data={filteredEntries} />;
}
```

**When You Might Be Tempted:**
Any time you want to "cache" a computed value in state. Use `useMemo` instead if performance is a concern.

---

## WARNING: Prop Mutations

**The Problem:**

```tsx
// BAD - mutating props
function PartyEditor({ entry }: { entry: PartyEntry }) {
  const handleNameChange = (name: string) => {
    entry.name = name; // WRONG: mutates prop directly
  };

  return <input value={entry.name} onChange={(e) => handleNameChange(e.target.value)} />;
}
```

**Why This Breaks:**
1. **One-way data flow violation:** Props flow down from parent. Child should not modify them.
2. **React doesn't detect change:** Mutating props doesn't trigger re-render because React compares object references, not deep values.

**The Fix:**

```tsx
// GOOD - emit event to parent
function PartyEditor({ entry, onChange }: { entry: PartyEntry; onChange: (updated: PartyEntry) => void }) {
  const handleNameChange = (name: string) => {
    onChange({ ...entry, name }); // Return new object
  };

  return <input value={entry.name} onChange={(e) => handleNameChange(e.target.value)} />;
}

// Parent component
function ExtractPage() {
  const [entries, setEntries] = useState<PartyEntry[]>([]);

  const handleUpdate = (updated: PartyEntry) => {
    setEntries(prev => prev.map(e => (e.id === updated.id ? updated : e)));
  };

  return <PartyEditor entry={entries[0]} onChange={handleUpdate} />;
}
```

**When You Might Be Tempted:**
When you want to "edit in place" for convenience. Always emit changes upward instead.

---

## WARNING: Over-Using Context

**The Problem:**

```tsx
// BAD - using Context for non-global state
const EntriesContext = createContext<PartyEntry[]>([]);

function App() {
  const [entries, setEntries] = useState<PartyEntry[]>([]);
  return (
    <EntriesContext.Provider value={entries}>
      <ExtractPage />
    </EntriesContext.Provider>
  );
}

function ExtractPage() {
  const entries = useContext(EntriesContext); // WRONG: entries are specific to Extract page
  return <DataTable data={entries} />;
}
```

**Why This Breaks:**
1. **Performance:** Every context update re-renders ALL consumers, even if they don't use the changed value
2. **Tight coupling:** ExtractPage is now coupled to EntriesContext, making it harder to reuse
3. **Context hell:** With 10+ contexts, provider nesting becomes unwieldy

**The Fix:**

```tsx
// GOOD - prop drilling (for single-use state)
function App() {
  return <ExtractPage />;
}

function ExtractPage() {
  const [entries, setEntries] = useState<PartyEntry[]>([]); // Local state
  return <DataTable data={entries} />;
}
```

**When to use Context:**
- **Auth state:** Needed by 5+ components across the tree (Sidebar, ProtectedRoute, Settings, etc.)
- **Theme:** Dark mode toggle used globally
- **Locale:** i18n language used globally

**When NOT to use Context:**
- State specific to one page/feature
- State that changes frequently (causes re-render storm)
- State that can be passed via props without drilling past 3 levels

**This codebase uses Context ONLY for auth.** If you're tempted to add another context, ask: "Is this truly global?" If not, use props or lift state only as high as needed.