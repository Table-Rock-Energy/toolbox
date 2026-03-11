# Phase 8: GHL Prep Tool - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform Mineral export CSVs into GoHighLevel-ready import files. User uploads CSV, tool applies transformations (title-casing, campaign extraction, phone mapping, contact owner column), user previews results in table, user downloads transformed CSV. Follows established CSV processing patterns from Title tool.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- Page layout and structure (follow existing tool patterns — upload area, results table, export button)
- Data preview table design (use existing DataTable component patterns)
- Title-casing edge case handling (Mc/Mac/O' prefixes, LLC/Jr suffixes, all-caps company names)
- Transform feedback (summary stats, progress indicators)
- Error/warning display for malformed rows or missing columns
- Column ordering in preview and export

</decisions>

<specifics>
## Specific Ideas

No specific requirements — user indicated the requirements are straightforward. Follow established patterns from existing tools (especially Title tool's CSV processing flow). Open to standard approaches across all implementation decisions.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. v2 features (GHL-08 through GHL-11: direct API export, contact owner dropdown, smartlist/tag assignment) are already captured in REQUIREMENTS.md.

</deferred>

---

*Phase: 08-ghl-prep-tool*
*Context gathered: 2026-02-26*
