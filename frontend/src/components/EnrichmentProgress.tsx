import { MapPin, Bot, Users, Check, X, AlertCircle, Loader2, Home } from 'lucide-react'

export interface EnrichmentStep {
  id: string
  label: string
  icon: typeof MapPin
  status: 'pending' | 'active' | 'completed' | 'skipped' | 'error'
  progress?: number
  total?: number
  message?: string
  detail?: string
}

export interface EnrichmentSummary {
  originalCount: number
  finalCount: number
  addressesCorrected?: number
  propertiesFound?: number
  namesCorrected?: number
  entriesSplit?: number
}

interface EnrichmentProgressProps {
  isOpen: boolean
  onClose: () => void
  steps: EnrichmentStep[]
  summary: EnrichmentSummary | null
  isComplete: boolean
}

const statusIcons: Record<string, string> = {
  pending: 'text-gray-300',
  active: 'text-tre-teal animate-pulse',
  completed: 'text-green-500',
  skipped: 'text-gray-400',
  error: 'text-red-500',
}

export const DEFAULT_STEPS: EnrichmentStep[] = [
  { id: 'addresses', label: 'Validate Addresses', icon: MapPin, status: 'pending' },
  { id: 'property', label: 'Property Lookup', icon: Home, status: 'pending' },
  { id: 'names', label: 'Clean Names', icon: Bot, status: 'pending' },
  { id: 'splitting', label: 'Split Multiple Names', icon: Users, status: 'pending' },
]

export default function EnrichmentProgress({
  isOpen,
  onClose,
  steps,
  summary,
  isComplete,
}: EnrichmentProgressProps) {
  if (!isOpen) return null

  const activeStep = steps.find(s => s.status === 'active')
  const completedCount = steps.filter(s => s.status === 'completed' || s.status === 'skipped').length

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={isComplete ? onClose : undefined} />
      <div className="relative bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-oswald font-semibold text-tre-navy">
              {isComplete ? 'Enrichment Complete' : 'Enriching Data...'}
            </h3>
            {isComplete && (
              <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Overall progress bar */}
          {!isComplete && (
            <div className="mb-6">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>{activeStep?.message || 'Processing...'}</span>
                <span>Step {completedCount + 1} of {steps.length}</span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-tre-teal rounded-full transition-all duration-300"
                  style={{ width: `${(completedCount / steps.length) * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Steps */}
          <div className="space-y-3">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-start gap-3">
                {/* Step indicator */}
                <div className="flex-shrink-0 mt-0.5">
                  {step.status === 'completed' ? (
                    <div className="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center">
                      <Check className="w-4 h-4 text-green-600" />
                    </div>
                  ) : step.status === 'active' ? (
                    <div className="w-6 h-6 bg-tre-teal/20 rounded-full flex items-center justify-center">
                      <Loader2 className="w-4 h-4 text-tre-teal animate-spin" />
                    </div>
                  ) : step.status === 'error' ? (
                    <div className="w-6 h-6 bg-red-100 rounded-full flex items-center justify-center">
                      <AlertCircle className="w-4 h-4 text-red-500" />
                    </div>
                  ) : step.status === 'skipped' ? (
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
                  <div className="flex items-center gap-2">
                    <step.icon className={`w-4 h-4 ${statusIcons[step.status]}`} />
                    <span className={`text-sm font-medium ${
                      step.status === 'active' ? 'text-tre-navy' :
                      step.status === 'completed' ? 'text-green-700' :
                      step.status === 'skipped' ? 'text-gray-400' :
                      step.status === 'error' ? 'text-red-600' :
                      'text-gray-500'
                    }`}>
                      {step.label}
                      {step.status === 'skipped' && ' (not configured)'}
                    </span>
                  </div>

                  {/* Step progress bar */}
                  {step.status === 'active' && step.total && step.total > 0 && (
                    <div className="mt-1">
                      <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-tre-teal rounded-full transition-all duration-200"
                          style={{ width: `${((step.progress || 0) / step.total) * 100}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {step.progress || 0} / {step.total}
                      </p>
                    </div>
                  )}

                  {/* Detail message */}
                  {step.detail && (
                    <p className="text-xs text-gray-500 mt-0.5">{step.detail}</p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Summary */}
          {isComplete && summary && (
            <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
              <h4 className="text-sm font-medium text-green-800 mb-2">Summary</h4>
              <div className="grid grid-cols-2 gap-2 text-xs text-green-700">
                {summary.addressesCorrected !== undefined && summary.addressesCorrected > 0 && (
                  <div className="flex items-center gap-1">
                    <MapPin className="w-3 h-3" />
                    <span>{summary.addressesCorrected} addresses corrected</span>
                  </div>
                )}
                {summary.propertiesFound !== undefined && summary.propertiesFound > 0 && (
                  <div className="flex items-center gap-1">
                    <Home className="w-3 h-3" />
                    <span>{summary.propertiesFound} property values found</span>
                  </div>
                )}
                {summary.namesCorrected !== undefined && summary.namesCorrected > 0 && (
                  <div className="flex items-center gap-1">
                    <Bot className="w-3 h-3" />
                    <span>{summary.namesCorrected} names corrected</span>
                  </div>
                )}
                {summary.entriesSplit !== undefined && summary.entriesSplit > 0 && (
                  <div className="flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    <span>{summary.entriesSplit} entries split</span>
                  </div>
                )}
                {summary.finalCount !== summary.originalCount && (
                  <div className="col-span-2 mt-1 pt-1 border-t border-green-200">
                    {summary.originalCount} entries → {summary.finalCount} entries
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Actions */}
          {isComplete && (
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
