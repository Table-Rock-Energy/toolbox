# React Forms Reference

## Contents
- Controlled Inputs (toolbox/frontend pattern)
- File Upload with FileList
- Form Validation (Client-Side)
- FormData for File Uploads
- WARNING: Uncontrolled Inputs
- WARNING: Missing File Validation

---

## Controlled Inputs (toolbox/frontend pattern)

**All inputs in this codebase use controlled components (value + onChange).**

### Text Input

```tsx
function SearchForm() {
  const [query, setQuery] = useState('');

  return (
    <input
      type="text"
      value={query}
      onChange={(e) => setQuery(e.target.value)}
      placeholder="Search parties..."
      className="px-4 py-2 border border-gray-300 rounded"
    />
  );
}
```

### Select Dropdown

```tsx
// toolbox/frontend/src/pages/Proration.tsx pattern (oil/gas selector)
function ProrationPage() {
  const [wellType, setWellType] = useState<'oil' | 'gas'>('oil');

  return (
    <select
      value={wellType}
      onChange={(e) => setWellType(e.target.value as 'oil' | 'gas')}
      className="px-4 py-2 border border-gray-300 rounded"
    >
      <option value="oil">Oil</option>
      <option value="gas">Gas</option>
    </select>
  );
}
```

### Checkbox

```tsx
function SettingsForm() {
  const [autoRefresh, setAutoRefresh] = useState(false);

  return (
    <label className="flex items-center gap-2">
      <input
        type="checkbox"
        checked={autoRefresh}
        onChange={(e) => setAutoRefresh(e.target.checked)}
      />
      Auto-refresh data
    </label>
  );
}
```

---

## File Upload with FileList

### Single File Upload (toolbox/frontend pattern)

```tsx
// toolbox/frontend/src/components/FileUpload.tsx pattern
function FileUpload({ onFileSelect }: { onFileSelect: (file: File) => void }) {
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      onFileSelect(files[0]);
    }
  };

  return (
    <input
      type="file"
      accept="application/pdf"
      onChange={handleFileChange}
      className="hidden"
      id="file-input"
    />
  );
}
```

### Multiple File Upload (Revenue Tool Pattern)

```tsx
// toolbox/frontend/src/pages/Revenue.tsx pattern
function RevenueUpload({ onFilesSelect }: { onFilesSelect: (files: File[]) => void }) {
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      onFilesSelect(Array.from(files)); // Convert FileList to Array
    }
  };

  return (
    <input
      type="file"
      accept="application/pdf"
      multiple // Allows multiple file selection
      onChange={handleFileChange}
    />
  );
}
```

### Drag-and-Drop File Upload

```tsx
// toolbox/frontend/src/components/FileUpload.tsx pattern
function FileUploadDragDrop({ onFileSelect }: { onFileSelect: (files: File[]) => void }) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    const pdfFiles = files.filter(f => f.type === 'application/pdf');
    
    if (pdfFiles.length > 0) {
      onFileSelect(pdfFiles);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`border-2 border-dashed rounded-lg p-8 text-center ${
        isDragging ? 'border-tre-teal bg-gray-50' : 'border-gray-300'
      }`}
    >
      {isDragging ? 'Drop files here' : 'Drag and drop PDF files or click to browse'}
    </div>
  );
}
```

---

## Form Validation (Client-Side)

### Required Field Validation

```tsx
function UserForm() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validation
    if (!email.trim()) {
      setError('Email is required');
      return;
    }
    if (!email.includes('@')) {
      setError('Invalid email format');
      return;
    }
    
    setError('');
    // Submit form
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className={`px-4 py-2 border rounded ${error ? 'border-red-500' : 'border-gray-300'}`}
      />
      {error && <div className="text-red-600 text-sm mt-1">{error}</div>}
      <button type="submit" className="mt-4 px-6 py-2 bg-tre-navy text-white rounded">
        Submit
      </button>
    </form>
  );
}
```

### File Size Validation

```tsx
// toolbox/frontend pattern - validate PDF size before upload
function FileUpload({ onFileSelect }: { onFileSelect: (file: File) => void }) {
  const [error, setError] = useState('');
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB (matches backend config)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];

    // Validation
    if (file.size > MAX_FILE_SIZE) {
      setError(`File size exceeds 50MB (${(file.size / 1024 / 1024).toFixed(2)}MB)`);
      return;
    }
    if (file.type !== 'application/pdf') {
      setError('Only PDF files are allowed');
      return;
    }

    setError('');
    onFileSelect(file);
  };

  return (
    <div>
      <input type="file" accept="application/pdf" onChange={handleFileChange} />
      {error && <div className="text-red-600 text-sm mt-1">{error}</div>}
    </div>
  );
}
```

---

## FormData for File Uploads

### Single File Upload to FastAPI

```tsx
// toolbox/frontend pattern for uploading PDF to /api/extract/upload
async function uploadPdf(file: File) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/extract/upload', {
    method: 'POST',
    body: formData // NO Content-Type header (browser sets multipart/form-data)
  });

  if (!response.ok) throw new Error('Upload failed');
  return response.json();
}
```

**CRITICAL: NO Content-Type header.** The browser automatically sets `Content-Type: multipart/form-data; boundary=...` with a unique boundary string. If you manually set it, the boundary is missing and FastAPI can't parse the request.

### Multiple Files Upload

```tsx
// toolbox/frontend/src/pages/Revenue.tsx pattern
async function uploadRevenuePdfs(files: File[]) {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file)); // Same key for all files

  const response = await fetch('/api/revenue/upload', {
    method: 'POST',
    body: formData
  });

  return response.json();
}
```

---

## WARNING: Uncontrolled Inputs

**The Problem:**

```tsx
// BAD - uncontrolled input (no value prop)
function SearchForm() {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = () => {
    const query = inputRef.current?.value; // WRONG: reading DOM directly
    console.log(query);
  };

  return <input ref={inputRef} type="text" />; // WRONG: no value prop
}
```

**Why This Breaks:**
1. **React doesn't track changes:** The input value lives in the DOM, not React state. React doesn't know when it changes.
2. **Hard to validate:** You can't show real-time validation errors (e.g., "Email must contain @") because React doesn't re-render on input change.
3. **Hard to reset:** Clearing the form requires `inputRef.current.value = ''` instead of `setQuery('')`.

**The Fix:**

```tsx
// GOOD - controlled input
function SearchForm() {
  const [query, setQuery] = useState('');

  const handleSubmit = () => {
    console.log(query); // State is source of truth
  };

  return (
    <input
      type="text"
      value={query}
      onChange={(e) => setQuery(e.target.value)}
    />
  );
}
```

**When You Might Be Tempted:**
When you think "I only need the value on submit, why track it in state?" The answer: real-time validation, conditional rendering, and form reset are all easier with controlled inputs.

---

## WARNING: Missing File Validation

**The Problem:**

```tsx
// BAD - no validation before upload
function FileUpload({ onFileSelect }: { onFileSelect: (file: File) => void }) {
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      onFileSelect(files[0]); // WRONG: no size/type validation
    }
  };

  return <input type="file" onChange={handleFileChange} />;
}
```

**Why This Breaks:**
1. **Backend rejects large files:** FastAPI has a 50MB limit (configurable). Uploading a 100MB file wastes bandwidth and fails.
2. **Wrong file type:** Uploading a .txt file to PDF endpoint causes backend errors.
3. **Poor UX:** User waits 30 seconds for upload, then sees "File too large" error.

**The Fix:**

```tsx
// GOOD - validate before upload
function FileUpload({ onFileSelect }: { onFileSelect: (file: File) => void }) {
  const [error, setError] = useState('');
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];

    // Validate file type
    if (file.type !== 'application/pdf') {
      setError('Only PDF files are allowed');
      return;
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      setError(`File exceeds 50MB (${(file.size / 1024 / 1024).toFixed(2)}MB)`);
      return;
    }

    setError('');
    onFileSelect(file);
  };

  return (
    <div>
      <input type="file" accept="application/pdf" onChange={handleFileChange} />
      {error && <div className="text-red-600 text-sm">{error}</div>}
    </div>
  );
}
```

**When You Might Be Tempted:**
When you assume the backend will validate. Always validate on the client for better UX (instant feedback) AND on the backend for security (client validation can be bypassed).