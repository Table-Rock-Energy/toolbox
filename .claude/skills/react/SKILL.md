---
name: react
description: |
  Manages React components, hooks, and Context API for auth state management.
  Use when: building/modifying frontend components, managing auth state, implementing protected routes, creating reusable UI components with TypeScript generics, or working with Firebase Auth integration.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# React Skill

React 19 SPA with strict TypeScript, Firebase Auth via Context API, and protected routes. Uses **useState** for local UI state (NO Redux/Zustand), direct **fetch()** in useEffect (NO react-query), and Tailwind inline styling (NO CSS modules).

## Quick Start

### Protected Route with Auth Context

```tsx
// toolbox/frontend/src/contexts/AuthContext.tsx pattern
import { createContext, useContext, useState, useEffect } from 'react';
import { getAuth, onAuthStateChanged, User } from 'firebase/auth';

const AuthContext = createContext<{ user: User | null; loading: boolean } | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = getAuth();
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUser(user);
      setLoading(false);
    });
    return unsubscribe; // CRITICAL: cleanup prevents memory leaks
  }, []); // Empty deps - runs once on mount

  return <AuthContext.Provider value={{ user, loading }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
```

### Generic Data Table Component

```tsx
// toolbox/frontend/src/components/DataTable.tsx pattern
interface DataTableProps<T extends object> {
  data: T[];
  columns: { key: keyof T; label: string; render?: (value: T[keyof T], row: T) => React.ReactNode }[];
  onSort?: (key: keyof T) => void;
}

export default function DataTable<T extends object>({ data, columns, onSort }: DataTableProps<T>) {
  return (
    <table className="min-w-full divide-y divide-gray-200">
      <thead className="bg-tre-navy">
        <tr>
          {columns.map((col) => (
            <th key={String(col.key)} onClick={() => onSort?.(col.key)} className="px-6 py-3 text-left cursor-pointer">
              {col.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, idx) => (
          <tr key={idx}>
            {columns.map((col) => (
              <td key={String(col.key)} className="px-6 py-4 whitespace-nowrap">
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

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| **useState for UI state** | Local component state (loading, modals, filters) | `const [isLoading, setIsLoading] = useState(false)` |
| **Context API for auth only** | Global auth state, NOT general state management | `const { user } = useAuth()` |
| **Direct fetch in useEffect** | Data fetching (NO react-query in this codebase) | `useEffect(() => { fetchData(); }, [])` |
| **Tailwind inline** | All styling via utility classes | `className="bg-tre-navy text-tre-teal"` |
| **TypeScript generics** | Reusable components with type safety | `DataTable<PartyEntry>` |
| **Barrel exports** | Clean imports via index.ts | `export { DataTable } from './DataTable'` |

## Common Patterns

### File Upload with Drag-Drop

**When:** Building file upload interfaces

```tsx
// toolbox/frontend/src/components/FileUpload.tsx pattern
const [isDragging, setIsDragging] = useState(false);

const handleDrop = (e: React.DragEvent) => {
  e.preventDefault();
  setIsDragging(false);
  const files = Array.from(e.dataTransfer.files);
  onFileSelect(files.filter(f => f.type === 'application/pdf'));
};

return (
  <div
    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
    onDragLeave={() => setIsDragging(false)}
    onDrop={handleDrop}
    className={`border-2 border-dashed p-8 ${isDragging ? 'border-tre-teal bg-gray-50' : 'border-gray-300'}`}
  >
    Drop files here
  </div>
);
```

### Programmatic File Download

**When:** Exporting CSV/Excel/PDF from API

```tsx
// toolbox/frontend pattern for export
const handleExport = async () => {
  const response = await fetch('/api/extract/export/csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: entries })
  });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'export.csv';
  a.click();
  URL.revokeObjectURL(url); // CRITICAL: prevents memory leak
};
```

### Modal with Backdrop and ESC Close

**When:** Building dialogs/modals

```tsx
// toolbox/frontend/src/components/Modal.tsx pattern
useEffect(() => {
  const handleEsc = (e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  };
  document.addEventListener('keydown', handleEsc);
  return () => document.removeEventListener('keydown', handleEsc); // Cleanup
}, [onClose]);

return (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
    <div className="bg-white rounded-lg p-6 max-w-2xl w-full" onClick={(e) => e.stopPropagation()}>
      {children}
    </div>
  </div>
);
```

## See Also

- [hooks](references/hooks.md) - useEffect cleanup, dependency arrays, custom hooks
- [components](references/components.md) - Component patterns, PascalCase naming, barrel exports
- [data-fetching](references/data-fetching.md) - Direct fetch patterns (NO react-query)
- [state](references/state.md) - useState patterns, Context API for auth only
- [forms](references/forms.md) - Form handling, validation, file uploads
- [performance](references/performance.md) - Preventing re-renders, memoization, key props

## Related Skills

- **typescript** - Strict mode, interfaces, generics with `extends` constraints
- **tailwind** - Utility-first styling with `tre-*` brand colors
- **vite** - Dev server with API proxy to `/api`
- **firebase** - Auth integration via Context API

## Documentation Resources

> Fetch latest React documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "react"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Recommended Queries:**
- "React hooks useState useEffect useCallback useMemo cleanup"
- "React context API best practices"
- "React TypeScript generics component props"