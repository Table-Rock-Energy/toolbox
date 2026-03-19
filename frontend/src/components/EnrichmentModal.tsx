import { useMemo } from 'react'
import { X, Check, Loader2, AlertCircle } from 'lucide-react'
import type { StepStatus, PipelineStatus, EnrichmentCellChange } from '../hooks/useEnrichmentPipeline'

interface EnrichmentModalProps {
  isOpen: boolean
  onClose: () => void
  stepStatuses: StepStatus[]
  pipelineStatus: PipelineStatus
  enrichmentChanges: Map<string, EnrichmentCellChange>
}

const STEP_LABELS: Record<string, string> = {
  cleanup: 'Clean Up',
  validate: 'Validate',
  enrich: 'Enrich',
}

export default function EnrichmentModal({
  isOpen,
  onClose,
  stepStatuses,
  pipelineStatus,
  enrichmentChanges,
}: EnrichmentModalProps) {
  const completedCount = stepStatuses.filter(
    s => s.status === 'completed' || s.status === 'skipped' || s.status === 'error'
  ).length
  const totalSteps = stepStatuses.length
  const isFinished = pipelineStatus === 'completed' || pipelineStatus === 'error'

  const activeStep = stepStatuses.find(s => s.status === 'active')
  const activeStepIndex = activeStep ? stepStatuses.indexOf(activeStep) : -1

  // ETA calculation
  const eta = useMemo(() => {
    if (completedCount === 0 || isFinished) return null
    const completedSteps = stepStatuses.filter(s => s.completedAt && s.startedAt)
    if (completedSteps.length === 0) return null
    const totalElapsed = completedSteps.reduce(
      (sum, s) => sum + ((s.completedAt ?? 0) - (s.startedAt ?? 0)),
      0
    )
    const avgStepTime = totalElapsed / completedSteps.length
    const remaining = totalSteps - completedCount
    const remainingMs = remaining * avgStepTime
    const remainingSec = Math.ceil(remainingMs / 1000)
    if (remainingSec >= 60) {
      return `~${Math.ceil(remainingSec / 60)} min remaining`
    }
    return `~${remainingSec}s remaining`
  }, [stepStatuses, completedCount, totalSteps, isFinished])

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
                <span>{eta || 'Estimating...'}</span>
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

                  {/* Error detail */}
                  {stepStatus.status === 'error' && stepStatus.error && (
                    <p className="text-xs text-red-500 mt-0.5">{stepStatus.error}</p>
                  )}
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
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
