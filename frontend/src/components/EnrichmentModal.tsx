import { useMemo, useState, useEffect, useRef } from 'react'
import { X, Check, Loader2, AlertCircle } from 'lucide-react'
import type { StepStatus, PipelineStatus, PipelineStep, EnrichmentCellChange } from '../hooks/useEnrichmentPipeline'
import type { BatchProgress, StepBatchResult } from '../contexts/OperationContext'

interface EnrichmentModalProps {
  isOpen: boolean
  onClose: () => void
  stepStatuses: StepStatus[]
  pipelineStatus: PipelineStatus
  enrichmentChanges: Map<string, EnrichmentCellChange>
  batchProgress: BatchProgress | null
  stepBatchResults: Map<PipelineStep, StepBatchResult>
}

const STEP_LABELS: Record<string, string> = {
  cleanup: 'Clean Up',
  validate: 'Validate',
  enrich: 'Enrich',
}

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return ''
  if (seconds >= 60) {
    const min = Math.floor(seconds / 60)
    const sec = seconds % 60
    return sec > 0 ? `${min}m ${sec}s remaining` : `${min}m remaining`
  }
  return `${seconds}s remaining`
}

function useCountdownEta(estimatedSeconds: number | null): string | null {
  const [remaining, setRemaining] = useState<number | null>(null)
  const targetRef = useRef<number | null>(null)

  useEffect(() => {
    if (estimatedSeconds === null || estimatedSeconds <= 0) {
      setRemaining(null)
      targetRef.current = null
      return
    }
    // Set target time when estimate changes
    targetRef.current = Date.now() + estimatedSeconds * 1000
    setRemaining(estimatedSeconds)

    const interval = setInterval(() => {
      if (!targetRef.current) return
      const left = Math.max(0, Math.ceil((targetRef.current - Date.now()) / 1000))
      setRemaining(left)
      if (left <= 0) clearInterval(interval)
    }, 1000)

    return () => clearInterval(interval)
  }, [estimatedSeconds])

  if (remaining === null || remaining <= 0) return null
  return formatCountdown(remaining)
}

function estimateBatchSeconds(batchTimings: number[], remainingBatches: number): number | null {
  if (batchTimings.length === 0 || remainingBatches <= 0) return null
  const avgMs = batchTimings.reduce((a, b) => a + b, 0) / batchTimings.length
  const sec = Math.max(0, Math.ceil((remainingBatches * avgMs) / 1000))
  return sec > 0 ? sec : null
}

export default function EnrichmentModal({
  isOpen,
  onClose,
  stepStatuses,
  pipelineStatus,
  enrichmentChanges,
  batchProgress,
  stepBatchResults,
}: EnrichmentModalProps) {
  const completedCount = stepStatuses.filter(
    s => s.status === 'completed' || s.status === 'skipped' || s.status === 'error'
  ).length
  const totalSteps = stepStatuses.length
  const isFinished = pipelineStatus === 'completed' || pipelineStatus === 'error'

  const activeStep = stepStatuses.find(s => s.status === 'active')
  const activeStepIndex = activeStep ? stepStatuses.indexOf(activeStep) : -1

  // ETA calculation (step-level) — estimate seconds for countdown
  const stepEtaSeconds = useMemo(() => {
    if (completedCount === 0 || isFinished) return null
    const completedSteps = stepStatuses.filter(s => s.completedAt && s.startedAt)
    if (completedSteps.length === 0) return null
    const totalElapsed = completedSteps.reduce(
      (sum, s) => sum + ((s.completedAt ?? 0) - (s.startedAt ?? 0)),
      0
    )
    const avgStepTime = totalElapsed / completedSteps.length
    const remaining = totalSteps - completedCount
    const sec = Math.max(0, Math.ceil((remaining * avgStepTime) / 1000))
    return sec > 0 ? sec : null
  }, [stepStatuses, completedCount, totalSteps, isFinished])

  // Batch-level ETA — estimate seconds for countdown
  const batchEtaSeconds = useMemo(() => {
    if (!batchProgress || batchProgress.batchTimings.length === 0) return null
    const remaining = batchProgress.totalBatches - batchProgress.currentBatch
    return estimateBatchSeconds(batchProgress.batchTimings, remaining)
  }, [batchProgress])

  // Countdown timers that tick every second
  const eta = useCountdownEta(stepEtaSeconds)
  const batchEta = useCountdownEta(batchEtaSeconds)

  // Completion summary
  const totalChanges = useMemo(() => {
    return enrichmentChanges.size
  }, [enrichmentChanges])

  const uniqueEntries = useMemo(() => {
    const entries = new Set<number>()
    enrichmentChanges.forEach(c => entries.add(c.entry_index))
    return entries.size
  }, [enrichmentChanges])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-tre-navy/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl max-w-md w-full mx-4">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-oswald font-semibold text-tre-navy">
              {isFinished ? 'Enrichment Complete' : 'Enriching Data...'}
            </h3>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
              aria-label="Close modal"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          {/* Overall progress bar */}
          {!isFinished && (
            <div className="mb-6">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>
                  {activeStep
                    ? `Step ${activeStepIndex + 1} of ${totalSteps}: ${STEP_LABELS[activeStep.step] || activeStep.step}...`
                    : 'Processing...'}
                </span>
                <span>{batchEta || eta || 'Estimating...'}</span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-tre-teal rounded-full transition-all duration-300"
                  style={{ width: `${totalSteps > 0 ? (completedCount / totalSteps) * 100 : 0}%` }}
                />
              </div>
            </div>
          )}

          {/* Step list */}
          <div className="space-y-3">
            {stepStatuses.map((stepStatus, index) => (
              <div key={stepStatus.step} className="flex items-start gap-3">
                {/* Step indicator */}
                <div className="flex-shrink-0 mt-0.5">
                  {stepStatus.status === 'completed' ? (
                    <div className="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center">
                      <Check className="w-4 h-4 text-green-600" />
                    </div>
                  ) : stepStatus.status === 'active' ? (
                    <div className="w-6 h-6 bg-tre-teal/20 rounded-full flex items-center justify-center">
                      <Loader2 className="w-4 h-4 text-tre-teal animate-spin" />
                    </div>
                  ) : stepStatus.status === 'error' ? (
                    <div className="w-6 h-6 bg-red-100 rounded-full flex items-center justify-center">
                      <AlertCircle className="w-4 h-4 text-red-500" />
                    </div>
                  ) : stepStatus.status === 'skipped' ? (
                    <div className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center">
                      <span className="text-gray-400 text-xs">-</span>
                    </div>
                  ) : (
                    <div className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center">
                      <span className="text-gray-400 text-xs font-medium">{index + 1}</span>
                    </div>
                  )}
                </div>

                {/* Step content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className={`text-sm font-medium ${
                      stepStatus.status === 'active' ? 'text-tre-navy' :
                      stepStatus.status === 'completed' ? 'text-green-700' :
                      stepStatus.status === 'skipped' ? 'text-gray-400' :
                      stepStatus.status === 'error' ? 'text-red-600' :
                      'text-gray-500'
                    }`}>
                      {STEP_LABELS[stepStatus.step] || stepStatus.step}
                    </span>
                    {stepStatus.status === 'completed' && stepStatus.changesApplied > 0 && (
                      <span className="text-xs text-green-600">
                        {stepStatus.changesApplied} change{stepStatus.changesApplied !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>

                  {/* Batch sub-progress -- only for the active step */}
                  {batchProgress && stepStatus.status === 'active' && batchProgress.currentStep === stepStatus.step && (
                    <div className="mt-1.5">
                      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                        <span>{STEP_LABELS[stepStatus.step] || stepStatus.step}: Batch {batchProgress.currentBatch} of {batchProgress.totalBatches}</span>
                        <span>{batchEta || 'Estimating...'}</span>
                      </div>
                      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-tre-teal rounded-full transition-all duration-300"
                          style={{ width: `${batchProgress.totalBatches > 0 ? (batchProgress.currentBatch / batchProgress.totalBatches) * 100 : 0}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Error detail */}
                  {stepStatus.status === 'error' && stepStatus.error && (
                    <p className="text-xs text-red-500 mt-0.5">{stepStatus.error}</p>
                  )}

                  {/* Partial batch failure summary -- amber text per UI-SPEC */}
                  {stepStatus.status === 'completed' && (() => {
                    const result = stepBatchResults.get(stepStatus.step as PipelineStep)
                    if (!result || result.failedBatches <= 0) return null
                    return (
                      <p className="text-xs text-amber-600 mt-0.5">
                        {result.totalBatches - result.failedBatches}/{result.totalBatches} batches &mdash; {result.skippedEntries} entries skipped ({result.failedBatches} batch failed)
                      </p>
                    )
                  })()}
                </div>
              </div>
            ))}
          </div>

          {/* Completion summary */}
          {isFinished && totalChanges > 0 && (
            <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm font-medium text-green-800">
                {totalChanges} field{totalChanges !== 1 ? 's' : ''} updated across {uniqueEntries} entr{uniqueEntries !== 1 ? 'ies' : 'y'}
              </p>
            </div>
          )}

          {isFinished && totalChanges === 0 && (
            <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
              <p className="text-sm text-gray-600">No changes were needed.</p>
            </div>
          )}

          {/* Done button */}
          {isFinished && (
            <div className="mt-4 flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
              >
                Close Summary
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// --- Cancel Confirm Dialog ---

interface CancelConfirmDialogProps {
  isOpen: boolean
  onKeepRunning: () => void
  onCancelAndStart: () => void
}

export function CancelConfirmDialog({ isOpen, onKeepRunning, onCancelAndStart }: CancelConfirmDialogProps) {
  if (!isOpen) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-tre-navy/60 backdrop-blur-sm" onClick={onKeepRunning} />
      <div className="relative bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 p-6">
        <h3 className="text-lg font-oswald font-semibold text-tre-navy mb-2">Cancel Operation?</h3>
        <p className="text-sm text-gray-600 mb-6">An enrichment operation is currently running. Starting a new one will cancel it.</p>
        <div className="flex justify-end gap-3">
          <button onClick={onKeepRunning} className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">Keep Running</button>
          <button onClick={onCancelAndStart} className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600">Cancel &amp; Start New</button>
        </div>
      </div>
    </div>
  )
}
