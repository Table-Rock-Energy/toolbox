# Phase 29: Firebase & Config Cleanup - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Dead Firebase references removed from Dockerfile and hardcoded admin email extracted to configuration. This phase removes leftover VITE_FIREBASE_* ARG/ENV lines from the Dockerfile (dead since v2.0 Firebase removal) and replaces all hardcoded `james@tablerocktx.com` references in backend auth/admin code with a configurable `DEFAULT_ADMIN_EMAIL` environment variable.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
