# React Hooks Reference

## Contents
- useEffect Cleanup Patterns
- Dependency Array Rules
- Custom Hooks
- WARNING: useEffect for Data Fetching
- WARNING: Missing Dependencies
- WARNING: Stale Closures

---

## useEffect Cleanup Patterns

**ALWAYS return cleanup functions** for subscriptions, event listeners, and timers.

### Auth State Subscription (GOOD)

```tsx
// toolbox/frontend/src/contexts/AuthContext.tsx
useEffect(() => {
  const auth = getAuth();
  const unsubscribe = onAuthStateChanged(auth, (user) => {
    setUser(user);
    setLoading(false);
  });
  return unsubscribe; // CRITICAL: prevents memory leak
}, []); // Empty deps - Firebase subscription persists
```

**Why this works:** Firebase's `onAuthStateChanged` returns an unsubscribe function. If you don't call it, the listener persists after component unmount, causing memory leaks.

### Event Listener Cleanup (GOOD)

```tsx
// toolbox/frontend/src/components/Modal.tsx
useEffect(() => {
  const handleEsc = (e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  };
  document.addEventListener('keydown', handleEsc);
  return () => document.removeEventListener('keydown', handleEsc);
}, [onClose]);
```

**Why this works:** Without cleanup, every time the modal opens, a new listener is added. After 10 modal opens, pressing ESC fires 10 times.

### Timer Cleanup (GOOD)

```tsx
// Pattern for auto-dismiss notifications
useEffect(() => {
  if (!notification) return;
  
  const timer = setTimeout(() => {
    setNotification(null);
  }, 5000);
  
  return () => clearTimeout(timer); // CRITICAL: prevents multiple timers
}, [notification]);
```

---

## Dependency Array Rules

### Rule 1: Include ALL Used Values

```tsx
// BAD - missing dep causes stale closure
function SearchResults({ query }: { query: string }) {
  const [results, setResults] = useState([]);
  
  useEffect(() => {
    fetch(`/api/search?q=${query}`).then(r => r.json()).then(setResults);
  }, []); // WRONG: query is used but not in deps
  
  return <div>{results.map(r => <div key={r.id}>{r.name}</div>)}</div>;
}

// GOOD - all deps included
useEffect(() => {
  fetch(`/api/search?q=${query}`).then(r => r.json()).then(setResults);
}, [query]); // Runs when query changes
```

**Why the BAD version breaks:** The effect only runs once on mount. If `query` changes from "oil" to "gas", the effect doesn't re-run, so you see stale "oil" results.

### Rule 2: Functions in Dependencies

```tsx
// BAD - function recreated every render
function JobsList() {
  const fetchJobs = async () => {
    const res = await fetch('/api/history/jobs');
    const data = await res.json();
    setJobs(data);
  };
  
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]); // Runs every render because fetchJobs is new each time
}

// GOOD - define function inside useEffect
useEffect(() => {
  const fetchJobs = async () => {
    const res = await fetch('/api/history/jobs');
    const data = await res.json();
    setJobs(data);
  };
  fetchJobs();
}, []); // Only runs on mount

// GOOD - useCallback for reusable function
const fetchJobs = useCallback(async () => {
  const res = await fetch('/api/history/jobs');
  const data = await res.json();
  setJobs(data);
}, []); // Memoized, won't change

useEffect(() => {
  fetchJobs();
}, [fetchJobs]); // Safe to include
```

### Rule 3: Object/Array Props

```tsx
// BAD - inline object prop causes infinite loop
<DataTable 
  data={entries}
  columns={[
    { key: 'name', label: 'Name' }, // New array every render
    { key: 'type', label: 'Type' }
  ]}
/>

// Inside DataTable:
useEffect(() => {
  // Process columns
}, [columns]); // Runs every render because columns is a new array

// GOOD - extract to constant outside component
const COLUMNS = [
  { key: 'name', label: 'Name' },
  { key: 'type', label: 'Type' }
] as const;

<DataTable data={entries} columns={COLUMNS} />
```

---

## Custom Hooks

### useAuth (Existing Pattern)

```tsx
// toolbox/frontend/src/contexts/AuthContext.tsx
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};

// Usage in protected routes
const { user, loading } = useAuth();
if (loading) return <LoadingSpinner />;
if (!user) return <Navigate to="/login" />;
```

### useLocalStorage (Recommended Addition)

```tsx
// Pattern for persisting UI preferences
function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setValue = (value: T) => {
    setStoredValue(value);
    window.localStorage.setItem(key, JSON.stringify(value));
  };

  return [storedValue, setValue];
}

// Usage
const [darkMode, setDarkMode] = useLocalStorage('darkMode', false);
```

---

## WARNING: useEffect for Data Fetching

**The Problem:**

```tsx
// BAD - race conditions, no caching, memory leaks
function Extract() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    setLoading(true);
    fetch('/api/extract/jobs')
      .then(r => r.json())
      .then(data => {
        setEntries(data); // WRONG: sets state after unmount
        setLoading(false);
      });
  }, []);
}
```

**Why This Breaks:**
1. **Race conditions:** If the user navigates away before fetch completes, `setEntries` runs on an unmounted component
2. **No caching:** Every mount fetches again, even if data hasn't changed
3. **No deduplication:** Multiple components fetching the same endpoint fire multiple requests

**The Fix (Current Codebase Pattern):**

```tsx
// GOOD - cleanup with abort controller
useEffect(() => {
  const controller = new AbortController();
  setLoading(true);
  
  fetch('/api/extract/jobs', { signal: controller.signal })
    .then(r => r.json())
    .then(data => {
      setEntries(data);
      setLoading(false);
    })
    .catch(err => {
      if (err.name !== 'AbortError') {
        console.error(err);
        setLoading(false);
      }
    });
  
  return () => controller.abort(); // Cleanup cancels pending request
}, []);
```

**Professional Fix (Not in Codebase - Recommended):**

Use **TanStack Query (react-query)** or **SWR**:

```tsx
import { useQuery } from '@tanstack/react-query';

function Extract() {
  const { data: entries, isLoading } = useQuery({
    queryKey: ['extract-jobs'],
    queryFn: () => fetch('/api/extract/jobs').then(r => r.json())
  });
  // Handles caching, deduplication, race conditions automatically
}
```

**When You Might Be Tempted:**
Every time you need to fetch data on component mount. Resist the urge—use AbortController or migrate to react-query.

---

## WARNING: Missing Dependencies

**The Problem:**

```tsx
// BAD - ESLint warning, stale closure bug
function ProrationTool({ wellType }: { wellType: 'oil' | 'gas' }) {
  const [data, setData] = useState([]);
  
  const fetchData = async () => {
    const res = await fetch(`/api/proration/rrc/status?type=${wellType}`);
    setData(await res.json());
  };
  
  useEffect(() => {
    fetchData();
  }, []); // WRONG: fetchData uses wellType, not in deps
}
```

**Why This Breaks:**
1. **Stale closure:** `fetchData` captures `wellType` from first render. If `wellType` changes, `fetchData` still uses the old value.
2. **Real-world scenario:** User switches from Oil to Gas tab. UI shows "Gas" but data is still Oil results.

**The Fix:**

```tsx
// GOOD - fetchData defined inside useEffect
useEffect(() => {
  const fetchData = async () => {
    const res = await fetch(`/api/proration/rrc/status?type=${wellType}`);
    setData(await res.json());
  };
  fetchData();
}, [wellType]); // Runs when wellType changes
```

**When You Might Be Tempted:**
When ESLint complains about missing deps and you think "but it works fine". It doesn't—you just haven't hit the bug yet.

---

## WARNING: Stale Closures in Event Handlers

**The Problem:**

```tsx
// BAD - onClick captures stale state
function Counter() {
  const [count, setCount] = useState(0);
  
  useEffect(() => {
    const interval = setInterval(() => {
      setCount(count + 1); // WRONG: count is stale
    }, 1000);
    return () => clearInterval(interval);
  }, []); // Empty deps means count is always 0
  
  return <div>{count}</div>; // Stuck at 1
}
```

**Why This Breaks:**
The interval closure captures `count` from the first render (0). Every tick runs `setCount(0 + 1)`, so count never exceeds 1.

**The Fix:**

```tsx
// GOOD - functional setState
useEffect(() => {
  const interval = setInterval(() => {
    setCount(prev => prev + 1); // Uses current state
  }, 1000);
  return () => clearInterval(interval);
}, []); // Safe with functional setState
```

**When You Might Be Tempted:**
Any time you use state inside a callback (setTimeout, setInterval, event listeners) without thinking about closure scope.