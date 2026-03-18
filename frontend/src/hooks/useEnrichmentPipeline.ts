import { useState, useCallback, useRef, useMemo } from 'react'
import { pipelineApi } from '../utils/api'
import type { ProposedChange } from '../utils/api'

type PipelineStep = 'cleanup' | 'validate' | 'enrich'

export interface UseEnrichmentPipelineOptions<T> {
  tool: string
  previewEntries: T[]
  updateEntries: (entries: T[]) => void
  editedFields: Map<string, Partial<T>>
  keyField: keyof T
  featureFlags: { cleanUpEnabled: boolean; validateEnabled: boolean; enrichEnabled: boolean }
  sourceData?: Record<string, unknown>[]
}

export interface AutoAppliedChange {
  entry_index: number
  field: string
  original_value: string
  corrected_value: string
  source: string
  confidence: string
}

/** Lookup: entry_index → field → ProposedChange */
export type ChangesByEntry = Map<number, Map<string, ProposedChange>>

export interface UseEnrichmentPipelineReturn {
  activeAction: PipelineStep | null
  proposedChanges: ProposedChange[] | null
  changesByEntry: ChangesByEntry
  affectedEntryIndices: Set<number>
  checkedIndices: Set<number>
  completedSteps: Set<PipelineStep>
  recentlyAppliedKeys: Set<string>
  autoAppliedChanges: AutoAppliedChange[]
  errorMessage: string | null
  canCleanUp: boolean
  canValidate: boolean
  canEnrich: boolean
  isProcessing: boolean
  onCleanUp: () => void
  onValidate: () => void
  onEnrich: () => void
  onApply: () => void
  onDismiss: () => void
  onUndoAutoApplied: () => void
  toggleCheck: (index: number) => void
  toggleCheckAll: () => void
}

export function useEnrichmentPipeline<T extends object>(
  options: UseEnrichmentPipelineOptions<T>
): UseEnrichmentPipelineReturn {
  const { tool, previewEntries, updateEntries, editedFields, keyField, featureFlags, sourceData } = options

  const [completedSteps, setCompletedSteps] = useState<Set<PipelineStep>>(new Set())
  const [activeAction, setActiveAction] = useState<PipelineStep | null>(null)
  const [proposedChanges, setProposedChanges] = useState<ProposedChange[] | null>(null)
  const [checkedIndices, setCheckedIndices] = useState<Set<number>>(new Set())
  const [recentlyAppliedKeys, setRecentlyAppliedKeys] = useState<Set<string>>(new Set())
  const [autoAppliedChanges, setAutoAppliedChanges] = useState<AutoAppliedChange[]>([])
  const [preAutoApplySnapshot, setPreAutoApplySnapshot] = useState<T[] | null>(null)
  const [lastStep, setLastStep] = useState<PipelineStep | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isProcessing = activeAction !== null

  // All buttons are independently usable (no sequential lock)
  const canCleanUp = featureFlags.cleanUpEnabled && !isProcessing
  const canValidate = featureFlags.validateEnabled && !isProcessing
  const canEnrich = featureFlags.enrichEnabled && !isProcessing

  const runStep = useCallback(async (step: PipelineStep) => {
    // Re-run confirmation
    if (completedSteps.has(step)) {
      const ok = window.confirm('Re-running will replace previous results. Manual edits are preserved. Continue?')
      if (!ok) return
    }

    setActiveAction(step)
    setProposedChanges(null)
    setErrorMessage(null)

    try {
      const entries = previewEntries.map((e) => ({ ...e } as Record<string, unknown>))
      const apiMethod = step === 'cleanup'
        ? pipelineApi.cleanup
        : step === 'validate'
          ? pipelineApi.validate
          : pipelineApi.enrich

      const response = await apiMethod(tool, entries, undefined, step === 'cleanup' ? sourceData : undefined)

      if (response.data && response.data.success) {
        const allChanges = response.data.proposed_changes

        // For cleanup: auto-apply high-confidence changes, only show medium/low for review
        if (step === 'cleanup' && allChanges.length > 0) {
          const highConfidence = allChanges.filter((c) => c.confidence === 'high')
          const needsReview = allChanges.filter((c) => c.confidence !== 'high')

          if (highConfidence.length > 0) {
            // Snapshot entries before auto-apply for undo support
            setPreAutoApplySnapshot(previewEntries.map((e) => ({ ...e })))

            // Auto-apply high-confidence changes directly
            const updatedEntries = previewEntries.map((e) => ({ ...e }))
            const appliedKeys = new Set<string>()
            const applied: AutoAppliedChange[] = []

            for (const change of highConfidence) {
              const entry = updatedEntries[change.entry_index]
              if (!entry) continue

              const entryKey = String(entry[keyField])
              const userEdits = editedFields.get(entryKey)

              // Respect manual edits
              if (userEdits && change.field in userEdits) continue

              ;(entry as Record<string, unknown>)[change.field] = change.proposed_value
              appliedKeys.add(entryKey)
              applied.push({
                entry_index: change.entry_index,
                field: change.field,
                original_value: change.current_value,
                corrected_value: change.proposed_value,
                source: change.source,
                confidence: change.confidence,
              })
            }

            if (applied.length > 0) {
              updateEntries(updatedEntries)
              setAutoAppliedChanges(applied)

              // Flash green highlight on auto-applied rows
              setRecentlyAppliedKeys(appliedKeys)
              if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current)
              highlightTimeoutRef.current = setTimeout(() => {
                setRecentlyAppliedKeys(new Set())
              }, 2000)
            }
          }

          // Show remaining changes for manual review (or nothing if all were high)
          if (needsReview.length > 0) {
            setProposedChanges(needsReview)
            setCheckedIndices(new Set(needsReview.map((_, i) => i)))
            setLastStep(step)
          } else {
            setCompletedSteps((prev) => new Set([...prev, step]))
          }
        } else {
          // Validate / Enrich: show all changes for review as before
          setProposedChanges(allChanges)
          setCheckedIndices(new Set(allChanges.map((_, i) => i)))
          setLastStep(step)
        }
      } else {
        const errorMsg = response.data?.error || response.error || 'Pipeline step failed'
        setErrorMessage(errorMsg)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Pipeline step failed'
      setErrorMessage(msg)
    } finally {
      setActiveAction(null)
    }
  }, [completedSteps, previewEntries, tool, sourceData])

  const onCleanUp = useCallback(() => { runStep('cleanup') }, [runStep])
  const onValidate = useCallback(() => { runStep('validate') }, [runStep])
  const onEnrich = useCallback(() => { runStep('enrich') }, [runStep])

  const onApply = useCallback(() => {
    if (!proposedChanges || !lastStep) return

    const updatedEntries = previewEntries.map((e) => ({ ...e }))
    const appliedKeys = new Set<string>()

    for (let i = 0; i < proposedChanges.length; i++) {
      if (!checkedIndices.has(i)) continue

      const change = proposedChanges[i]
      const entry = updatedEntries[change.entry_index]
      if (!entry) continue

      const entryKey = String(entry[keyField])
      const userEdits = editedFields.get(entryKey)

      // If user edited this field and change is not authoritative, skip
      if (!change.authoritative && userEdits && change.field in userEdits) {
        continue
      }

      // Apply the change
      ;(entry as Record<string, unknown>)[change.field] = change.proposed_value
      appliedKeys.add(entryKey)
    }

    updateEntries(updatedEntries)

    // Track recently applied for green highlight
    setRecentlyAppliedKeys(appliedKeys)
    if (highlightTimeoutRef.current) {
      clearTimeout(highlightTimeoutRef.current)
    }
    highlightTimeoutRef.current = setTimeout(() => {
      setRecentlyAppliedKeys(new Set())
    }, 2000)

    // Mark step completed, clear proposals
    if (lastStep) {
      setCompletedSteps((prev) => new Set([...prev, lastStep]))
    }
    setProposedChanges(null)
    setCheckedIndices(new Set())
    setLastStep(null)
  }, [proposedChanges, lastStep, previewEntries, checkedIndices, keyField, editedFields, updateEntries])

  const onUndoAutoApplied = useCallback(() => {
    if (preAutoApplySnapshot) {
      updateEntries(preAutoApplySnapshot)
      setPreAutoApplySnapshot(null)
      setAutoAppliedChanges([])
    }
  }, [preAutoApplySnapshot, updateEntries])

  const onDismiss = useCallback(() => {
    setProposedChanges(null)
    setCheckedIndices(new Set())
    setLastStep(null)
    setErrorMessage(null)
  }, [])

  const toggleCheck = useCallback((index: number) => {
    setCheckedIndices((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }, [])

  const toggleCheckAll = useCallback(() => {
    if (!proposedChanges) return
    setCheckedIndices((prev) => {
      if (prev.size === proposedChanges.length) {
        return new Set()
      }
      return new Set(proposedChanges.map((_, i) => i))
    })
  }, [proposedChanges])

  // Build lookup maps for inline rendering: entry_index → field → change
  const changesByEntry = useMemo<ChangesByEntry>(() => {
    const map: ChangesByEntry = new Map()
    if (!proposedChanges) return map
    for (const change of proposedChanges) {
      let fieldMap = map.get(change.entry_index)
      if (!fieldMap) {
        fieldMap = new Map()
        map.set(change.entry_index, fieldMap)
      }
      fieldMap.set(change.field, change)
    }
    return map
  }, [proposedChanges])

  const affectedEntryIndices = useMemo(
    () => new Set(changesByEntry.keys()),
    [changesByEntry],
  )

  return {
    activeAction,
    proposedChanges,
    changesByEntry,
    affectedEntryIndices,
    checkedIndices,
    completedSteps,
    recentlyAppliedKeys,
    autoAppliedChanges,
    errorMessage,
    canCleanUp,
    canValidate,
    canEnrich,
    isProcessing,
    onCleanUp,
    onValidate,
    onEnrich,
    onApply,
    onDismiss,
    onUndoAutoApplied,
    toggleCheck,
    toggleCheckAll,
  }
}
