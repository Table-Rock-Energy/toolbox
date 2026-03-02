---
name: typescript
description: |
  Enforces strict TypeScript mode with comprehensive linting and type safety for React 19 + Vite 7 frontend.
  Use when: Writing or modifying TypeScript code in toolbox/frontend/, configuring tsconfig, fixing type errors, or enforcing type safety across the codebase.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# TypeScript Skill

This project uses **strict TypeScript mode** in `toolbox/frontend/` with comprehensive ESLint rules. All `.tsx` files must pass type checking via `npx tsc --noEmit` before deployment. The codebase enforces type safety at boundaries (API responses, Firebase auth, component props) and uses generics extensively (e.g., `DataTable<T extends object>`).

## Quick Start

### Generic Component with Type Constraints

```typescript
// toolbox/frontend/src/components/DataTable.tsx
interface DataTableProps<T extends object> {
  data: T[];
  columns: Array<{
    key: keyof T;
    label: string;
    render?: (value: T[keyof T], row: T) => React.ReactNode;
  }>;
  onRowClick?: (row: T) => void;
}

export default function DataTable<T extends object>({ 
  data, 
  columns, 
  onRowClick 
}: DataTableProps<T>) {
  return (
    <table>
      {data.map((row, idx) => (
        <tr key={idx} onClick={() => onRowClick?.(row)}>
          {columns.map(col => (
            <td key={String(col.key)}>
              {col.render ? col.render(row[col.key], row) : String(row[col.key])}
            </td>
          ))}
        </tr>
      ))}
    </table>
  );
}
```

### API Response Typing

```typescript
// toolbox/frontend/src/utils/api.ts
interface PartyEntry {
  name: string;
  address: string;
  entity_type: 'Individual' | 'Trust' | 'LLC' | 'Corporation';
  ownership_decimal: number;
}

class ApiClient {
  async extractParties(file: File): Promise<PartyEntry[]> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('/api/extract/upload', {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return response.json(); // Type-safe return
  }
}
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Strict mode | All nullable checks enforced | `strictNullChecks: true`, `strict: true` |
| Generic constraints | Reusable components with type safety | `<T extends object>` |
| Type-only imports | Avoid runtime overhead | `import type { User } from './types'` |
| Discriminated unions | Type-safe state management | `type Status = { state: 'loading' } \| { state: 'success'; data: T }` |
| `keyof` operator | Type-safe object keys | `columns: Array<{ key: keyof T }>` |

## Common Patterns

### Type-Safe Event Handlers

**When:** Handling React events with TypeScript

```typescript
// toolbox/frontend/src/pages/Extract.tsx
const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
  const files = event.target.files;
  if (!files || files.length === 0) return;
  
  const file = files[0];
  uploadFile(file); // Type-safe: file is File, not File | undefined
};
```

### Boolean Props with Explicit Naming

**When:** Defining component props

```typescript
// GOOD
interface ModalProps {
  isOpen: boolean;
  hasCloseButton: boolean;
  shouldTrapFocus: boolean;
}

// BAD - Ambiguous
interface ModalProps {
  open: boolean;
  close: boolean;
  focus: boolean;
}
```

### Type-Safe Context

**When:** Creating React Context providers

```typescript
// toolbox/frontend/src/contexts/AuthContext.tsx
interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context; // Never undefined
}
```

## See Also

- [patterns](references/patterns.md) - Idiomatic TypeScript patterns for this codebase
- [types](references/types.md) - Interface design, generics, utility types
- [modules](references/modules.md) - Import patterns, barrel exports, project references
- [errors](references/errors.md) - Common type errors and fixes

## Related Skills

- **react** - Component prop typing, hooks with TypeScript
- **vite** - TypeScript configuration in Vite builds
- **firebase** - Firebase SDK type definitions
- **frontend-design** - Type-safe component APIs

## Documentation Resources

> Fetch latest TypeScript documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "typescript"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** `/microsoft/TypeScript` _(resolve using mcp__plugin_context7_context7__resolve-library-id, prefer /websites/ when available)_

**Recommended Queries:**
- "Utility types Pick Omit Partial Required"
- "Generic constraints extends keyof"
- "Strict mode tsconfig options"