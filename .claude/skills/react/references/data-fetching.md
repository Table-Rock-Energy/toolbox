# React Data Fetching Reference

## Contents
- Current Pattern: Direct fetch() in useEffect
- AbortController for Cleanup
- ApiClient Class Pattern
- File Upload with FormData
- Blob Download for Exports
- WARNING: Missing AbortController
- WARNING: No Professional Fetching Library

---

## Current Pattern: Direct fetch() in useEffect

**This codebase uses direct `fetch()` calls in `useEffect` with `AbortController` cleanup. NO react-query or SWR.**

### Basic GET Request

```tsx
// toolbox/frontend pattern for fetching jobs list
function ExtractPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);

    fetch('/api/history/jobs?tool=extract', { signal: controller.signal })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setJobs(data);
        setLoading(false);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => controller.abort(); // Cleanup on unmount
  }, []); // Empty deps - fetch once on mount

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  return <JobsList jobs={jobs} />;
}
```

**Key Points:**
- **AbortController:** Cancels pending request if component unmounts
- **Error handling:** Check `res.ok` before calling `.json()`
- **Ignore AbortError:** Aborted requests shouldn't set error state

---

## AbortController for Cleanup

### Why AbortController Matters

```tsx
// BAD - memory leak and race condition
useEffect(() => {
  setLoading(true);
  fetch('/api/extract/jobs')
    .then(r => r.json())
    .then(data => {
      setJobs(data); // WRONG: may run after component unmounts
      setLoading(false);
    });
}, []); // No cleanup
```

**Race condition scenario:**
1. User loads Extract page → fetch starts
2. User navigates to Proration page → Extract component unmounts
3. Fetch completes → `setJobs` runs on unmounted component → React warning

**The Fix:**

```tsx
// GOOD - aborts pending request on unmount
useEffect(() => {
  const controller = new AbortController();
  setLoading(true);

  fetch('/api/extract/jobs', { signal: controller.signal })
    .then(r => r.json())
    .then(data => {
      setJobs(data);
      setLoading(false);
    })
    .catch(err => {
      if (err.name !== 'AbortError') { // Ignore aborted requests
        console.error(err);
        setLoading(false);
      }
    });

  return () => controller.abort();
}, []);
```

---

## ApiClient Class Pattern

### Centralized API Wrapper

```ts
// toolbox/frontend/src/utils/api.ts pattern
class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async get<T>(endpoint: string, signal?: AbortSignal): Promise<T> {
    const res = await fetch(`${this.baseUrl}${endpoint}`, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  async post<T>(endpoint: string, body: any, signal?: AbortSignal): Promise<T> {
    const res = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  async postFormData<T>(endpoint: string, formData: FormData, signal?: AbortSignal): Promise<T> {
    const res = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      body: formData, // NO Content-Type header (browser sets multipart/form-data boundary)
      signal
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  async downloadBlob(endpoint: string, body: any, signal?: AbortSignal): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.blob();
  }
}

export const apiClient = new ApiClient(import.meta.env.VITE_API_BASE_URL || '/api');

// Per-tool clients
export const extractApi = {
  uploadPdf: (file: File, signal?: AbortSignal) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.postFormData('/extract/upload', formData, signal);
  },
  exportCsv: (data: any[], signal?: AbortSignal) =>
    apiClient.downloadBlob('/extract/export/csv', { data }, signal)
};
```

### Usage in Components

```tsx
// toolbox/frontend/src/pages/Extract.tsx pattern
import { extractApi } from '../utils/api';

function Extract() {
  const handleUpload = async (file: File) => {
    const controller = new AbortController();
    setLoading(true);

    try {
      const result = await extractApi.uploadPdf(file, controller.signal);
      setEntries(result.entries);
    } catch (err) {
      if (err.name !== 'AbortError') setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return <FileUpload onFileSelect={handleUpload} />;
}
```

---

## File Upload with FormData

### PDF Upload to FastAPI Backend

```tsx
// toolbox/frontend pattern for file uploads
function handleFileUpload(file: File) {
  const formData = new FormData();
  formData.append('file', file);

  fetch('/api/extract/upload', {
    method: 'POST',
    body: formData // CRITICAL: NO Content-Type header (browser adds multipart/form-data boundary)
  })
    .then(res => res.json())
    .then(data => setEntries(data.entries))
    .catch(err => console.error(err));
}
```

**Why NO Content-Type header:** The browser automatically sets `Content-Type: multipart/form-data; boundary=...` with a unique boundary string. If you manually set `'Content-Type': 'multipart/form-data'`, the boundary is missing and the backend can't parse the request.

### Multiple File Upload

```tsx
// toolbox/frontend/src/pages/Revenue.tsx pattern (supports multiple PDFs)
function handleMultipleFiles(files: FileList) {
  const formData = new FormData();
  Array.from(files).forEach(file => formData.append('files', file)); // Same key for multiple files

  fetch('/api/revenue/upload', {
    method: 'POST',
    body: formData
  })
    .then(res => res.json())
    .then(data => setStatements(data.statements))
    .catch(err => console.error(err));
}
```

---

## Blob Download for Exports

### CSV/Excel Export Pattern

```tsx
// toolbox/frontend pattern for exporting data
async function handleExportCsv(entries: PartyEntry[]) {
  const response = await fetch('/api/extract/export/csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: entries })
  });

  if (!response.ok) throw new Error('Export failed');

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'extract_export.csv';
  a.click();
  URL.revokeObjectURL(url); // CRITICAL: prevents memory leak
}
```

**Why `URL.revokeObjectURL(url)` matters:** Each `createObjectURL` allocates memory. Without revoking, exporting 50 files leaks 50 blob URLs. In Chrome, this can consume hundreds of MB.

### PDF Export (Proration)

```tsx
// toolbox/frontend/src/pages/Proration.tsx pattern
async function handleExportPdf(results: ProrationResult[]) {
  const response = await fetch('/api/proration/export/pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ results })
  });

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `proration_${new Date().toISOString().split('T')[0]}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}
```

---

## WARNING: Missing AbortController

**The Problem:**

```tsx
// BAD - no cleanup
function JobsList() {
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    fetch('/api/history/jobs')
      .then(r => r.json())
      .then(setJobs);
  }, []); // WRONG: no AbortController
}
```

**Why This Breaks:**
1. **Memory leak:** If user navigates away mid-fetch, the promise chain still runs `setJobs` on an unmounted component
2. **Race condition:** Fast navigation between pages causes old requests to overwrite new data

**The Fix:**

```tsx
// GOOD - abort on unmount
useEffect(() => {
  const controller = new AbortController();

  fetch('/api/history/jobs', { signal: controller.signal })
    .then(r => r.json())
    .then(setJobs)
    .catch(err => {
      if (err.name !== 'AbortError') console.error(err);
    });

  return () => controller.abort();
}, []);
```

**When You Might Be Tempted:**
Every time you add a fetch call. It's easy to forget cleanup, especially for simple GET requests. **Always add AbortController** unless the request is user-triggered (button click) and you want it to complete even after unmount.

---

## WARNING: No Professional Fetching Library

**This codebase lacks react-query, SWR, or Apollo Client.** This causes:

1. **No caching:** Navigating back to Extract page refetches jobs every time
2. **No deduplication:** Two DataTable components fetching the same endpoint fire two requests
3. **Manual loading/error state:** Every component duplicates `useState` for loading/error
4. **No optimistic updates:** Deleting a job requires manual state updates
5. **No background refetching:** Stale data persists until manual refresh

**Recommended Migration:**

Install **TanStack Query (react-query)**:

```bash
npm install @tanstack/react-query
```

**Wrap App in QueryClientProvider:**

```tsx
// toolbox/frontend/src/main.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);
```

**Replace fetch with useQuery:**

```tsx
// BEFORE (current pattern)
function ExtractPage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetch('/api/history/jobs?tool=extract', { signal: controller.signal })
      .then(r => r.json())
      .then(setJobs)
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);
}

// AFTER (with react-query)
import { useQuery } from '@tanstack/react-query';

function ExtractPage() {
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['extract-jobs'],
    queryFn: () => fetch('/api/history/jobs?tool=extract').then(r => r.json())
  });
  // Caching, deduplication, error handling, AbortController all automatic
}
```

**Benefits:**
- **Automatic caching:** Second mount reuses cached data
- **Background refetch:** Stale data refreshes on window focus
- **Optimistic updates:** UI updates before API confirms
- **Deduplication:** Multiple components share same request

**When to Migrate:**
If the app grows to 10+ data-fetching components, migrate to react-query. For the current size (4 tools), direct fetch is acceptable but fragile.