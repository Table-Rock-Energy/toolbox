# Phase 9: Tool-Specific AI Prompts - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Each tool gets tailored AI QA prompts that leverage tool-specific data patterns for better cleanup and validation. ECF gets a net-new cross-file accuracy prompt. Existing prompts get targeted refinements (suffix standardization, statistical outlier detection). A new 'ecf' tool key enables prompt routing for ECF uploads.

Requirements: ENRICH-11

</domain>

<decisions>
## Implementation Decisions

### ECF Cross-File Prompts
- Compare ALL overlapping fields between PDF-extracted and CSV-provided data (names, addresses, entity types, entry numbers, metadata like county/legal description/case number)
- Present discrepancies as ProposedChange: CSV value as current, PDF value as suggested, with reason explaining the mismatch -- follows "PDF is authoritative" principle from v1.4
- Cross-file checking runs as part of Clean Up (no separate button) -- when user clicks Clean Up on ECF data, the prompt does both standard name/address cleanup AND cross-file comparison in one pass
- AI receives both the merged result AND the original CSV data so it can see where merge chose PDF over CSV
- Both CLEANUP_PROMPTS and TOOL_PROMPTS get ECF-specific versions (cleanup for corrections + cross-file, validation for passive accuracy review)

### Prompt Improvement Scope
- Keep existing Extract/Title/Revenue/Proration prompts largely intact -- the enrichment pipeline just shipped and hasn't been tested enough to know what's missing
- Add suffix standardization to Extract and Title cleanup prompts: normalize Jr./Junior -> Jr, Sr./Senior -> Sr, III stays III, The Third -> III
- Add statistical outlier detection to Revenue prompts: flag values >3x median compared against the batch, for catching data extraction errors
- ECF prompt is the only net-new prompt

### Prompt Routing & Selection
- Add 'ecf' as a new valid tool key alongside extract/title/proration/revenue
- Frontend sends tool='ecf' when the upload was ECF format
- Add optional 'source_data' field to PipelineRequest for passing original CSV data alongside merged entries -- other tools ignore it, ECF uses it for cross-file comparison
- ECF gets both a CLEANUP_PROMPTS['ecf'] entry and a TOOL_PROMPTS['ecf'] entry

### Confidence & Filtering
- Show all proposed changes, sort by confidence (high first) -- no filtering, trust the user to review
- ECF cross-file discrepancies always marked as high confidence (objective factual mismatches between two data sources, even trivial formatting differences)
- Add confidence badge to ProposedChangesPanel: small colored badge (green=high, yellow=medium, gray=low) next to each proposed change

### Claude's Discretion
- Exact wording of ECF cross-file prompt instructions
- How to structure the statistical outlier detection in the Revenue prompt (whether to compute median in Python and pass to LLM, or let LLM estimate from the batch)
- ECF validation prompt scope (how much overlap with standard Extract validation)
- Confidence badge styling and placement within ProposedChangesPanel

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### AI/LLM Infrastructure
- `backend/app/services/llm/prompts.py` -- Current CLEANUP_PROMPTS dict (per-tool cleanup instructions) and CLEANUP_RESPONSE_SCHEMA
- `backend/app/services/llm/protocol.py` -- LLMProvider protocol class (cleanup_entries interface)
- `backend/app/services/llm/gemini_provider.py` -- GeminiProvider implementation using prompts.py
- `backend/app/services/gemini_service.py` -- TOOL_PROMPTS dict (per-tool validation instructions) and REVENUE_VERIFY_PROMPT

### Pipeline API
- `backend/app/api/pipeline.py` -- /api/pipeline/cleanup, /validate, /enrich endpoints with PipelineRequest model
- `backend/app/models/pipeline.py` -- ProposedChange model used across all pipeline responses

### ECF Infrastructure
- `backend/app/services/extract/ecf_parser.py` -- ECF PDF parsing logic
- `backend/app/services/extract/csv_processor.py` -- Convey 640 CSV processing
- `backend/app/api/extract.py` -- Extract endpoints including ECF format detection

### Frontend
- `frontend/src/components/ProposedChangesPanel.tsx` -- Proposed changes review UI (needs confidence badge addition)
- `frontend/src/hooks/useEnrichmentPipeline.ts` -- Pipeline orchestration hook (needs to pass tool='ecf' and source_data)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CLEANUP_PROMPTS` dict in `prompts.py`: Already per-tool, just needs 'ecf' key added and minor refinements to extract/title/revenue
- `TOOL_PROMPTS` dict in `gemini_service.py`: Already per-tool, needs 'ecf' key added
- `PipelineRequest` model: Accepts tool string + entries list, needs optional source_data field
- `ProposedChangesPanel`: Already renders proposed changes with checkboxes, needs confidence badge addition
- `useEnrichmentPipeline` hook: Already passes tool param, needs ECF-aware logic for source_data

### Established Patterns
- Prompt selection via dict lookup: `CLEANUP_PROMPTS[tool]` with fallback to 'extract'
- ProposedChange format: entry_index, field, current_value, suggested_value, reason, confidence, authoritative
- Pipeline endpoints validate tool against allowed set -- needs 'ecf' added to valid_tools

### Integration Points
- Frontend Extract.tsx: Must detect ECF format and pass tool='ecf' + source_data to pipeline
- Backend pipeline.py: Must accept optional source_data, pass to LLM provider for ECF
- LLM provider: cleanup_entries may need source_data param for ECF cross-file context

</code_context>

<specifics>
## Specific Ideas

- ECF cross-file comparison should leverage the "PDF is authoritative" principle already established in v1.4
- Statistical outlier detection for Revenue uses >3x median as the threshold
- Suffix standardization follows common genealogy/legal conventions: Jr, Sr, I, II, III, IV
- User hasn't tested the enrichment pipeline enough yet to know specific prompt gaps -- focus on ECF (net-new) and success criteria refinements (suffix, outliers)

</specifics>

<deferred>
## Deferred Ideas

- Admin-editable prompt templates -- deferred to v1.6+
- Prompt A/B testing or quality scoring -- future consideration
- Tool-specific confidence thresholds (different filtering per tool) -- not needed now, revisit if users report noise

</deferred>

---

*Phase: 09-tool-specific-ai-prompts*
*Context gathered: 2026-03-16*
