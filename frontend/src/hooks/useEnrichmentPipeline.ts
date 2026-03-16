import { useState, useCallback, useRef } from 'react'
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
}

export interface UseEnrichmentPipelineReturn {
  activeAction: PipelineStep | null
  proposedChanges: ProposedChange[] | null
  checkedIndices: Set<number>
  completedSteps: Set<PipelineStep>
  recentlyAppliedKeys: Set<string>
  canCleanUp: boolean
  canValidate: boolean
  canEnrich: boolean
  isProcessing: boolean
  onCleanUp: () => void
  onValidate: () => void
  onEnrich: () => void
  onApply: () => void
  onDismiss: () => void
  toggleCheck: (index: number) => void
  toggleCheckAll: () => void
}

export function useEnrichmentPipeline<T extends object>(
  options: UseEnrichmentPipelineOptions<T>
): UseEnrichmentPipelineReturn {
  const { tool, previewEntries, updateEntries, editedFields, keyField, featureFlags } = options

  const [completedSteps, setCompletedSteps] = useState<Set<PipelineStep>>(new Set())
  const [activeAction, setActiveAction] = useState<PipelineStep | null>(null)
  const [proposedChanges, setProposedChanges] = useState<ProposedChange[] | null>(null)
  const [checkedIndices, setCheckedIndices] = useState<Set<number>>(new Set())
  const [recentlyAppliedKeys, setRecentlyAppliedKeys] = useState<Set<string>>(new Set())
  const [lastStep, setLastStep] = useState<PipelineStep | null>(null)

  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isProcessing = activeAction !== null

  // Sequential unlock logic
  const canCleanUp = featureFlags.cleanUpEnabled && !isProcessing
  const canValidate = featureFlags.validateEnabled
    && (completedSteps.has('cleanup') || !featureFlags.cleanUpEnabled)
    && !isProcessing
  const canEnrich = featureFlags.enrichEnabled
    && (completedSteps.has('validate') || (
      !featureFlags.validateEnabled
      && (completedSteps.has('cleanup') || !featureFlags.cleanUpEnabled)
    ))
    && !isProcessing

  const runStep = useCallback(async (step: PipelineStep) => {
    // Re-run confirmation
    if (completedSteps.has(step)) {
      const ok = window.confirm('Re-running will replace previous results. Manual edits are preserved. Continue?')
      if (!ok) return
    }

    setActiveAction(step)
    setProposedChanges(null)

    try {
      const entries = previewEntries.map((e) => ({ ...e } as Record<string, unknown>))
      const apiMethod = step === 'cleanup'
        ? pipelineApi.cleanup
        : step === 'validate'
          ? pipelineApi.validate
          : pipelineApi.enrich

      const response = await apiMethod(tool, entries)

      if (response.data && response.data.success) {
        const changes = response.data.proposed_changes
        setProposedChanges(changes)
        setCheckedIndices(new Set(changes.map((_, i) => i)))
        setLastStep(step)
      } else {
        const errorMsg = response.data?.error || response.error || 'Pipeline step failed'
        console.error(`Pipeline ${step} error:`, errorMsg)
      }
    } catch (err) {
      console.error(`Pipeline ${step} error:`, err)
    } finally {
      setActiveAction(null)
    }
  }, [completedSteps, previewEntries, tool])

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

  const onDismiss = useCallback(() => {
    setProposedChanges(null)
    setCheckedIndices(new Set())
    setLastStep(null)
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

  return {
    activeAction,
    proposedChanges,
    checkedIndices,
    completedSteps,
    recentlyAppliedKeys,
    canCleanUp,
    canValidate,
    canEnrich,
    isProcessing,
    onCleanUp,
    onValidate,
    onEnrich,
    onApply,
    onDismiss,
    toggleCheck,
    toggleCheckAll,
  }
}
