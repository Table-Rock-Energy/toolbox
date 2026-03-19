import { createContext, useContext, useCallback, useState, useRef, useEffect, useMemo } from 'react'
import type { ReactNode } from 'react'
import { pipelineApi } from '../utils/api'
import type { PipelineStep, PipelineStatus, StepStatus, EnrichmentCellChange } from '../hooks/useEnrichmentPipeline'

const DEFAULT_BATCH_SIZE = 25
const DEFAULT_MAX_RETRIES = 1

// --- Interfaces ---

interface BatchProgress {
  currentBatch: number
  totalBatches: number
  failedBatches: number
  skippedEntries: number
  currentStep: PipelineStep
  batchTimings: number[] // ms per completed batch, for ETA
}

interface StepBatchResult {
  failedBatches: number
  totalBatches: number
  skippedEntries: number
}

interface OperationState {
  tool: string
  status: PipelineStatus
  stepStatuses: StepStatus[]
  stepBatchResults: Map<PipelineStep, StepBatchResult>
  batchProgress: BatchProgress | null
  enrichmentChanges: Map<string, EnrichmentCellChange>
  completedSteps: Set<PipelineStep>
  entriesSnapshot: Record<string, unknown>[] | null
  resultEntries: Record<string, unknown>[] | null
  errorMessage: string | null
}

interface StartOperationOpts {
  tool: string
  entries: Record<string, unknown>[]
  updateEntries: (entries: Record<string, unknown>[]) => void
  editedFields: Map<string, unknown>
  keyField: string
  featureFlags: { cleanUpEnabled: boolean; validateEnabled: boolean; enrichEnabled: boolean }
  sourceData?: Record<string, unknown>[]
}

interface OperationActions {
  startOperation: (opts: StartOperationOpts) => void | Promise<void>
  abortOperation: () => void
  undoOperation: () => void
  clearOperation: () => void
  getResultsForTool: (tool: string) => Record<string, unknown>[] | null
}

// --- Split contexts (avoids re-render storms) ---

const OperationStateContext = createContext<OperationState | null>(null)
const OperationActionsContext = createContext<OperationActions | null>(null)

// --- Provider ---

export function OperationProvider({ children }: { children: ReactNode }) {
  const [operation, setOperation] = useState<OperationState | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const updateEntriesRef = useRef<((entries: Record<string, unknown>[]) => void) | null>(null)
  const batchConfigRef = useRef({ batchSize: DEFAULT_BATCH_SIZE, maxRetries: DEFAULT_MAX_RETRIES })

  // beforeunload: abort in-flight fetches on tab/window close only
  useEffect(() => {
    const handleBeforeUnload = () => {
      abortControllerRef.current?.abort()
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])

  // Fetch batch config from admin settings (falls back to defaults if non-admin or error)
  const fetchBatchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/admin/settings/google-cloud')
      if (res.ok) {
        const data = await res.json()
        batchConfigRef.current = {
          batchSize: data.batch_size ?? DEFAULT_BATCH_SIZE,
          maxRetries: data.batch_max_retries ?? DEFAULT_MAX_RETRIES,
        }
      }
    } catch {
      // Falls back to defaults
    }
  }, [])

  // Core batch-aware pipeline engine
  const runPipeline = useCallback(async (
    opts: StartOperationOpts,
    controller: AbortController,
  ) => {
    const { tool, entries, editedFields, keyField, featureFlags, sourceData } = opts
    const batchSize = batchConfigRef.current.batchSize
    const maxRetries = batchConfigRef.current.maxRetries

    // Determine enabled steps
    const steps: PipelineStep[] = []
    if (featureFlags.cleanUpEnabled) steps.push('cleanup')
    if (featureFlags.validateEnabled) steps.push('validate')
    if (featureFlags.enrichEnabled) steps.push('enrich')
    if (steps.length === 0) {
      setOperation(prev => prev ? { ...prev, status: 'completed' } : prev)
      return
    }

    // Initialize step statuses
    const initialStatuses: StepStatus[] = steps.map(s => ({
      step: s, status: 'pending' as const, changesApplied: 0,
    }))
    setOperation(prev => prev ? { ...prev, stepStatuses: initialStatuses } : prev)

    // Local variables for the batch loop (NOT React state -- avoids stale closure)
    const currentEntries = entries.map(e => ({ ...e }))
    const allChanges = new Map<string, EnrichmentCellChange>()
    const stepBatchResults = new Map<PipelineStep, StepBatchResult>()

    for (let si = 0; si < steps.length; si++) {
      if (controller.signal.aborted) break

      const step = steps[si]

      // Mark step active
      setOperation(prev => {
        if (!prev) return prev
        const updated = prev.stepStatuses.map((s, idx) =>
          idx === si ? { ...s, status: 'active' as const, startedAt: Date.now() } : s
        )
        return { ...prev, stepStatuses: updated }
      })

      const apiMethod = step === 'cleanup' ? pipelineApi.cleanup
        : step === 'validate' ? pipelineApi.validate
        : pipelineApi.enrich

      const totalBatches = Math.ceil(currentEntries.length / batchSize)
      const batchTimings: number[] = []
      let failedBatches = 0
      let skippedEntries = 0
      const failedBatchRanges: { start: number; end: number }[] = []
      let stepChangesApplied = 0

      for (let bi = 0; bi < totalBatches; bi++) {
        if (controller.signal.aborted) break

        const batchStart = bi * batchSize
        const batch = currentEntries.slice(batchStart, batchStart + batchSize)
        const batchStartTime = Date.now()

        try {
          const response = await apiMethod(
            tool,
            batch,
            undefined,
            step === 'cleanup' ? sourceData : undefined,
          )

          if (controller.signal.aborted) break

          const elapsed = Date.now() - batchStartTime
          batchTimings.push(elapsed)

          if (response.data?.success && response.data.proposed_changes) {
            for (const change of response.data.proposed_changes) {
              const globalIndex = batchStart + change.entry_index
              if (globalIndex >= currentEntries.length) continue

              // Respect manual edits
              const entryKey = String(currentEntries[globalIndex][keyField])
              const userEdits = editedFields.get(entryKey)
              if (userEdits && change.field in (userEdits as Record<string, unknown>)) continue

              const originalValue = String(currentEntries[globalIndex][change.field] ?? '')
              currentEntries[globalIndex][change.field] = change.proposed_value
              stepChangesApplied++

              // First-change-only tracking
              const changeKey = `${globalIndex}:${change.field}`
              if (!allChanges.has(changeKey)) {
                allChanges.set(changeKey, {
                  entry_index: globalIndex,
                  field: change.field,
                  original_value: originalValue,
                  new_value: change.proposed_value,
                  step,
                })
              } else {
                const existing = allChanges.get(changeKey)!
                allChanges.set(changeKey, { ...existing, new_value: change.proposed_value })
              }
            }
          }

          // Progressive apply: push updated entries to the tool page
          updateEntriesRef.current?.(currentEntries.map(e => ({ ...e })))

          // Update batch progress
          setOperation(prev => {
            if (!prev) return prev
            return {
              ...prev,
              enrichmentChanges: new Map(allChanges),
              batchProgress: {
                currentBatch: bi + 1,
                totalBatches,
                failedBatches,
                skippedEntries,
                currentStep: step,
                batchTimings: [...batchTimings],
              },
            }
          })
        } catch {
          // Skip and continue (RESIL-03)
          failedBatches++
          skippedEntries += batch.length
          failedBatchRanges.push({ start: batchStart, end: batchStart + batch.length })

          // Update batch progress with failure counts
          setOperation(prev => {
            if (!prev) return prev
            return {
              ...prev,
              batchProgress: {
                currentBatch: bi + 1,
                totalBatches,
                failedBatches,
                skippedEntries,
                currentStep: step,
                batchTimings: [...batchTimings],
              },
            }
          })
          continue
        }
      }

      // --- End-of-step retry for failed batches (RESIL-04) ---
      if (failedBatchRanges.length > 0 && maxRetries > 0 && !controller.signal.aborted) {
        let retriesLeft = maxRetries
        while (failedBatchRanges.length > 0 && retriesLeft > 0 && !controller.signal.aborted) {
          retriesLeft--
          const retryRanges = [...failedBatchRanges]
          failedBatchRanges.length = 0

          for (const range of retryRanges) {
            if (controller.signal.aborted) break
            const batch = currentEntries.slice(range.start, range.end)
            const batchStartTime = Date.now()

            try {
              const response = await apiMethod(
                tool,
                batch,
                undefined,
                step === 'cleanup' ? sourceData : undefined,
              )

              if (controller.signal.aborted) break

              const elapsed = Date.now() - batchStartTime
              batchTimings.push(elapsed)

              if (response.data?.success && response.data.proposed_changes) {
                for (const change of response.data.proposed_changes) {
                  const globalIndex = range.start + change.entry_index
                  if (globalIndex >= currentEntries.length) continue
                  const entryKey = String(currentEntries[globalIndex][keyField])
                  const userEdits = editedFields.get(entryKey)
                  if (userEdits && change.field in (userEdits as Record<string, unknown>)) continue
                  const originalValue = String(currentEntries[globalIndex][change.field] ?? '')
                  currentEntries[globalIndex][change.field] = change.proposed_value
                  stepChangesApplied++
                  const changeKey = `${globalIndex}:${change.field}`
                  if (!allChanges.has(changeKey)) {
                    allChanges.set(changeKey, {
                      entry_index: globalIndex,
                      field: change.field,
                      original_value: originalValue,
                      new_value: change.proposed_value,
                      step,
                    })
                  } else {
                    const existing = allChanges.get(changeKey)!
                    allChanges.set(changeKey, { ...existing, new_value: change.proposed_value })
                  }
                }
              }
              updateEntriesRef.current?.(currentEntries.map(e => ({ ...e })))
              failedBatches--
              skippedEntries -= batch.length
            } catch {
              // Still failed after retry -- re-add to failed ranges
              failedBatchRanges.push(range)
            }
          }
        }
      }

      // Step complete: store batch failure info in stepBatchResults
      stepBatchResults.set(step, { failedBatches, totalBatches, skippedEntries })

      // Mark step completed, persist stepBatchResults
      setOperation(prev => {
        if (!prev) return prev
        const updatedStatuses = prev.stepStatuses.map((s, idx) =>
          idx === si ? { ...s, status: 'completed' as const, changesApplied: stepChangesApplied, completedAt: Date.now() } : s
        )
        const updatedCompleted = new Set(prev.completedSteps)
        updatedCompleted.add(step)
        return {
          ...prev,
          stepStatuses: updatedStatuses,
          stepBatchResults: new Map(stepBatchResults),
          completedSteps: updatedCompleted,
          batchProgress: null, // Reset before next step
        }
      })
    }

    // All steps done
    const finalStatus: PipelineStatus = controller.signal.aborted ? 'idle' : 'completed'
    setOperation(prev => {
      if (!prev) return prev
      return {
        ...prev,
        status: finalStatus,
        resultEntries: currentEntries.map(e => ({ ...e })),
        batchProgress: null,
      }
    })
    abortControllerRef.current = null
  }, [])

  // --- Actions ---

  const startOperation = useCallback(async (opts: StartOperationOpts) => {
    // Abort any running operation first
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }

    const controller = new AbortController()
    abortControllerRef.current = controller

    // Store updateEntries callback in ref for progressive apply
    updateEntriesRef.current = opts.updateEntries

    // Fetch latest batch config before starting
    await fetchBatchConfig()

    // Snapshot entries for undo
    const entriesSnapshot = opts.entries.map(e => ({ ...e }))

    // Initialize operation state
    setOperation({
      tool: opts.tool,
      status: 'running',
      stepStatuses: [],
      stepBatchResults: new Map(),
      batchProgress: null,
      enrichmentChanges: new Map(),
      completedSteps: new Set(),
      entriesSnapshot,
      resultEntries: null,
      errorMessage: null,
    })

    // Run the pipeline (fire-and-forget async)
    runPipeline(opts, controller)
  }, [runPipeline, fetchBatchConfig])

  const abortOperation = useCallback(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setOperation(prev => {
      if (!prev) return prev
      return { ...prev, status: 'idle', batchProgress: null }
    })
  }, [])

  const undoOperation = useCallback(() => {
    if (!operation?.entriesSnapshot) return
    updateEntriesRef.current?.(operation.entriesSnapshot)
    setOperation(null)
  }, [operation?.entriesSnapshot])

  const clearOperation = useCallback(() => {
    setOperation(null)
  }, [])

  const getResultsForTool = useCallback((tool: string): Record<string, unknown>[] | null => {
    if (operation?.tool === tool && operation?.status === 'completed') {
      return operation.resultEntries
    }
    return null
  }, [operation?.tool, operation?.status, operation?.resultEntries])

  // Memoize actions so OperationActionsContext value is stable
  const actions = useMemo<OperationActions>(() => ({
    startOperation,
    abortOperation,
    undoOperation,
    clearOperation,
    getResultsForTool,
  }), [startOperation, abortOperation, undoOperation, clearOperation, getResultsForTool])

  return (
    <OperationStateContext.Provider value={operation}>
      <OperationActionsContext.Provider value={actions}>
        {children}
      </OperationActionsContext.Provider>
    </OperationStateContext.Provider>
  )
}

// --- Consumer hooks ---

// eslint-disable-next-line react-refresh/only-export-components
export function useOperationState() {
  return useContext(OperationStateContext)
}

// eslint-disable-next-line react-refresh/only-export-components
export function useOperationActions() {
  const ctx = useContext(OperationActionsContext)
  if (!ctx) throw new Error('useOperationActions must be used within OperationProvider')
  return ctx
}

// Convenience: combines both
// eslint-disable-next-line react-refresh/only-export-components
export function useOperationContext() {
  return { operation: useOperationState(), ...useOperationActions() }
}

// --- Exported types ---

export type { OperationState, BatchProgress, StepBatchResult, StartOperationOpts, OperationActions }
