---
phase: quick
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/utils/patterns.py
  - backend/app/services/extract/parser.py
  - backend/app/services/ghl_prep/transform_service.py
  - frontend/src/pages/GhlPrep.tsx
autonomous: true
requirements: [QUICK-01]

must_haves:
  truths:
    - "GHL Prep results show an Entity Type column classifying each row"
    - "User can toggle a filter to show only Individual contacts"
    - "Filtered count vs total count is visible in the UI"
    - "CSV export and GHL send use filtered rows (excluding Entity Type column from export)"
  artifacts:
    - path: "backend/app/utils/patterns.py"
      provides: "Shared detect_entity_type() function"
      contains: "def detect_entity_type"
    - path: "backend/app/services/ghl_prep/transform_service.py"
      provides: "Entity Type classification in each row"
      contains: "detect_entity_type"
    - path: "frontend/src/pages/GhlPrep.tsx"
      provides: "Filter UI and Entity Type column display"
      contains: "showIndividualsOnly"
  key_links:
    - from: "backend/app/utils/patterns.py"
      to: "backend/app/services/extract/parser.py"
      via: "import detect_entity_type"
      pattern: "from app\\.utils\\.patterns import.*detect_entity_type"
    - from: "backend/app/utils/patterns.py"
      to: "backend/app/services/ghl_prep/transform_service.py"
      via: "import detect_entity_type"
      pattern: "from app\\.utils\\.patterns import.*detect_entity_type"
---

<objective>
Add entity type filtering to the GHL Prep tool so users can exclude commercial entities (LLCs, Corporations, Trusts, etc.) and send only Individual contacts to GoHighLevel.

Purpose: GHL outreach only targets people — commercial entities waste API quota and produce bad contacts.
Output: Entity Type column in GHL Prep results, filter toggle, filtered export/send.
</objective>

<execution_context>
@/Users/ventinco/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ventinco/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@backend/app/utils/patterns.py
@backend/app/services/extract/parser.py (lines 393-426 — _detect_entity_type)
@backend/app/models/extract.py (EntityType enum)
@backend/app/services/ghl_prep/transform_service.py
@backend/app/models/ghl_prep.py
@frontend/src/pages/GhlPrep.tsx

<interfaces>
<!-- EntityType enum from extract models — reused for classification -->
From backend/app/models/extract.py:
```python
class EntityType(str, Enum):
    INDIVIDUAL = "Individual"
    TRUST = "Trust"
    LLC = "LLC"
    CORPORATION = "Corporation"
    PARTNERSHIP = "Partnership"
    GOVERNMENT = "Government"
    ESTATE = "Estate"
    UNKNOWN_HEIRS = "Unknown Heirs"
```

<!-- Existing patterns already in utils/patterns.py (lines 199-213) -->
From backend/app/utils/patterns.py:
```python
LLC_PATTERN = re.compile(r"\bL\.?L\.?C\.?\b", re.IGNORECASE)
INC_PATTERN = re.compile(r"\b(?:Inc\.?|Incorporated)\b", re.IGNORECASE)
CORP_PATTERN = re.compile(r"\b(?:Corp\.?|Corporation)\b", re.IGNORECASE)
LP_PATTERN = re.compile(r"\bL\.?P\.?\b(?!\s*\d)", re.IGNORECASE)
PARTNERSHIP_PATTERN = re.compile(r"\bPartnership\b", re.IGNORECASE)
TRUST_PATTERN = re.compile(r"\b(?:Trust|Trustee)\b", re.IGNORECASE)
ESTATE_PATTERN = re.compile(r"\b(?:Estate\s+of|,\s*Deceased)\b", re.IGNORECASE)
UNKNOWN_HEIRS_PATTERN = re.compile(r"\b(?:Unknown\s+Heirs|heirs\s+and\s+assigns)\b", re.IGNORECASE)
GOVERNMENT_PATTERN = re.compile(r"\b(?:Bureau|County|Commission|Board\s+of|State\s+of|United\s+States)\b", re.IGNORECASE)
```

<!-- TransformResult model -->
From backend/app/models/ghl_prep.py:
```python
class TransformResult(BaseModel):
    success: bool
    rows: list[dict]
    total_count: int
    transformed_fields: dict[str, int]
    warnings: list[str]
    source_filename: str
    campaign_name: Optional[str]
    job_id: Optional[str]
```

<!-- GHL Prep output columns (Entity Type NOT included — display only) -->
From backend/app/services/ghl_prep/transform_service.py:
```python
OUTPUT_COLUMNS = [
    "Contact Owner", "M1neral Contact System ID", "First Name", "Last Name",
    "Phone", "Phone 1", "Phone 2", "Phone 3", "Phone 4", "Phone 5",
    "Email", "Address", "City", "State", "County", "Territory", "Zip",
    "Campaign Name", "Bankruptcy", "Deceased", "Lien", "Campaign System ID",
]
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extract detect_entity_type to shared utils and add to GHL Prep transform</name>
  <files>backend/app/utils/patterns.py, backend/app/services/extract/parser.py, backend/app/services/ghl_prep/transform_service.py</files>
  <action>
1. In `backend/app/utils/patterns.py`, add a public `detect_entity_type(text: str) -> str` function at the bottom of the file (after line 236). Import `EntityType` from `app.models.extract` at the top. The function body is identical to `_detect_entity_type` in parser.py (lines 393-426) but returns `entity_type.value` (the string like "Individual", "LLC") instead of the enum, to keep it dependency-light for cross-tool use.

```python
def detect_entity_type(text: str) -> str:
    """Detect entity type from name text. Returns EntityType string value."""
    from app.models.extract import EntityType

    if UNKNOWN_HEIRS_PATTERN.search(text):
        return EntityType.UNKNOWN_HEIRS.value
    if ESTATE_PATTERN.search(text):
        return EntityType.ESTATE.value
    if TRUST_PATTERN.search(text):
        return EntityType.TRUST.value
    if LLC_PATTERN.search(text):
        return EntityType.LLC.value
    if INC_PATTERN.search(text) or CORP_PATTERN.search(text):
        return EntityType.CORPORATION.value
    if LP_PATTERN.search(text):
        if not re.search(r"\bPartners\b", text) or PARTNERSHIP_PATTERN.search(text):
            return EntityType.PARTNERSHIP.value
    if PARTNERSHIP_PATTERN.search(text):
        return EntityType.PARTNERSHIP.value
    if GOVERNMENT_PATTERN.search(text):
        return EntityType.GOVERNMENT.value
    return EntityType.INDIVIDUAL.value
```

Note: Use lazy import for EntityType inside the function to avoid circular imports (patterns.py is imported by extract modules).

2. In `backend/app/services/extract/parser.py`, replace the `_detect_entity_type` function body with a delegation to the shared version:
```python
def _detect_entity_type(text: str) -> EntityType:
    from app.utils.patterns import detect_entity_type
    return EntityType(detect_entity_type(text))
```
This preserves the existing return type (EntityType enum) for all extract tool callers.

3. In `backend/app/services/ghl_prep/transform_service.py`:
   - Add import: `from app.utils.patterns import detect_entity_type`
   - After the final DataFrame is built (after line 358 `df = final_df`), but BEFORE the fillna/stringify block, add entity type classification:
   ```python
   # Classify entity type from First Name + Last Name (display/filter only, not exported)
   def _classify_row(row: pd.Series) -> str:
       full_name = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
       return detect_entity_type(full_name) if full_name else "Individual"

   df["Entity Type"] = df.apply(_classify_row, axis=1)
   ```
   - Add entity type counts to `transformed_fields`:
   ```python
   entity_counts = df["Entity Type"].value_counts().to_dict()
   transformed_fields["entity_types"] = entity_counts
   ```
   - IMPORTANT: Do NOT add "Entity Type" to OUTPUT_COLUMNS. It is added after the OUTPUT_COLUMNS filter, so it will be present in rows for display/filtering but can be stripped before export.
  </action>
  <verify>
    <automated>cd /Users/ventinco/Documents/Projects/Table Rock TX/Tools/toolbox && python3 -c "from app.utils.patterns import detect_entity_type; assert detect_entity_type('John Smith') == 'Individual'; assert detect_entity_type('Smith Family Trust') == 'Trust'; assert detect_entity_type('Acme LLC') == 'LLC'; assert detect_entity_type('Unknown Heirs of Jones') == 'Unknown Heirs'; print('All entity detection tests passed')" && python3 -c "from app.services.extract.parser import _detect_entity_type; from app.models.extract import EntityType; assert _detect_entity_type('John Smith') == EntityType.INDIVIDUAL; print('Extract parser delegation works')"</automated>
  </verify>
  <done>detect_entity_type is a shared public function in patterns.py. Extract parser delegates to it. GHL Prep transform adds "Entity Type" to each row dict with correct classification. transformed_fields includes entity_types counts.</done>
</task>

<task type="auto">
  <name>Task 2: Add entity type filter UI and filtered export/send to GHL Prep frontend</name>
  <files>frontend/src/pages/GhlPrep.tsx</files>
  <action>
In `frontend/src/pages/GhlPrep.tsx`:

1. Add state for filter (after the existing useState declarations, around line 49):
```typescript
const [showIndividualsOnly, setShowIndividualsOnly] = useState(false)
```

2. Add a `filteredRows` useMemo (after the `currentRows` memo, around line 124):
```typescript
const filteredRows = useMemo(() => {
  if (!showIndividualsOnly) return currentRows
  return currentRows.filter(row => row['Entity Type'] === 'Individual')
}, [currentRows, showIndividualsOnly])
```

3. Update `sortedRows` to use `filteredRows` instead of `currentRows`:
- Change the dependency from `currentRows` to `filteredRows`
- Change `if (currentRows.length === 0` to `if (filteredRows.length === 0`
- Change `const sorted = [...currentRows]` to `const sorted = [...filteredRows]`

4. Add filter UI in the Results Header section. Inside the existing `<div className="flex items-center justify-between">`, after the title/subtitle `<div>` and before the buttons `<div className="flex gap-2">`, add a middle section with the filter controls (only visible in normal viewMode):
```tsx
{viewMode === 'normal' && result && (
  <div className="flex items-center gap-4">
    <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={showIndividualsOnly}
        onChange={(e) => setShowIndividualsOnly(e.target.checked)}
        className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
      />
      Individuals only
    </label>
    <span className="text-xs text-gray-400">
      {showIndividualsOnly
        ? `${filteredRows.length} of ${currentRows.length} contacts`
        : `${currentRows.length} contacts`}
    </span>
  </div>
)}
```

5. Update the row count display (line 525 area) from `{sortedRows.length} rows` to:
```tsx
{sortedRows.length} rows{showIndividualsOnly ? ` (filtered from ${currentRows.length})` : ''}
```

6. Update `handleExport` to use filtered rows and strip Entity Type:
- Change the empty check to use `filteredRows` (or the computed sorted rows)
- In the JSON body, strip "Entity Type" from each row before sending:
```typescript
const exportRows = (showIndividualsOnly ? filteredRows : result.rows).map(row => {
  const { 'Entity Type': _, ...rest } = row
  return rest
})
```
Use `exportRows` in the fetch body instead of `result.rows`.

7. Update the Send to GHL modal props to use filtered rows (strip Entity Type):
- Change `rows={result?.rows || []}` to:
```tsx
rows={(showIndividualsOnly
  ? filteredRows.map(({ 'Entity Type': _, ...rest }) => rest)
  : (result?.rows || []).map(({ 'Entity Type': _, ...rest }) => rest)
)}
```
- Update `contactCount` similarly: `contactCount={showIndividualsOnly ? filteredRows.length : (result?.rows?.length || 0)}`

8. In the `columns` memo, keep "Entity Type" visible in the table (it comes from the backend rows automatically via `Object.keys(result.rows[0])`). No change needed — it will appear naturally.

9. Reset filter on new upload: In `handleReset`, add `setShowIndividualsOnly(false)`. In `handleFilesSelected`, the existing `setResult(null)` already clears data.
  </action>
  <verify>
    <automated>cd /Users/ventinco/Documents/Projects/Table Rock TX/Tools/toolbox/frontend && npx tsc --noEmit 2>&1 | head -20</automated>
  </verify>
  <done>GhlPrep page shows Entity Type column, has "Individuals only" checkbox filter, displays filtered/total counts, exports and sends only filtered rows with Entity Type stripped from export data. TypeScript compiles without errors.</done>
</task>

</tasks>

<verification>
1. Backend: `cd toolbox && python3 -c "from app.utils.patterns import detect_entity_type; print(detect_entity_type('John Smith'), detect_entity_type('Acme LLC'), detect_entity_type('Smith Trust'))"` outputs `Individual LLC Trust`
2. Frontend: `cd toolbox/frontend && npx tsc --noEmit` passes with no errors
3. Manual: Upload a Mineral CSV in GHL Prep, verify Entity Type column appears, toggle "Individuals only" filter, confirm counts update and CSV export excludes commercial entities
</verification>

<success_criteria>
- Entity Type column visible in GHL Prep results table with correct classifications
- "Individuals only" checkbox filters out non-Individual rows
- Filtered vs total count displayed
- CSV export and GHL send use filtered rows, Entity Type column excluded from export
- Extract tool entity detection still works (delegation preserved)
- TypeScript and Python both pass syntax checks
</success_criteria>

<output>
After completion, create `.planning/quick/1-add-entity-type-filtering-to-ghl-prep-to/1-SUMMARY.md`
</output>
