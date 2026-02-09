import { useState, useEffect, useCallback } from 'react'
import { Sparkles, Check, X, CheckCircle, XCircle, AlertCircle, Loader2 } from 'lucide-react'
import { aiApi } from '../utils/api'
import type { AiSuggestion, AiValidationResult } from '../utils/api'

interface AiReviewPanelProps {
  tool: string
  entries: unknown[]
  onApplySuggestions: (accepted: AiSuggestion[]) => void
  onClose: () => void
}

const CONFIDENCE_STYLES: Record<string, string> = {
  high: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-gray-100 text-gray-600',
}

export default function AiReviewPanel({ tool, entries, onApplySuggestions, onClose }: AiReviewPanelProps) {
  const [loading, setLoading] = useState(true)
  const [result, setResult] = useState<AiValidationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Record<number, 'accept' | 'reject'>>({})

  const runValidation = useCallback(async () => {
    setLoading(true)
    setError(null)

    const response = await aiApi.validate(tool, entries)

    if (response.error) {
      setError(response.error)
      setLoading(false)
      return
    }

    if (response.data) {
      if (!response.data.success) {
        setError(response.data.error_message || 'Validation failed')
      }
      setResult(response.data)
    }

    setLoading(false)
  }, [tool, entries])

  useEffect(() => {
    runValidation()
  }, [runValidation])

  const handleDecision = (index: number, decision: 'accept' | 'reject') => {
    setDecisions(prev => ({ ...prev, [index]: decision }))
  }

  const handleAcceptAll = () => {
    if (!result) return
    const all: Record<number, 'accept' | 'reject'> = {}
    result.suggestions.forEach((_, i) => { all[i] = 'accept' })
    setDecisions(all)
  }

  const handleRejectAll = () => {
    if (!result) return
    const all: Record<number, 'accept' | 'reject'> = {}
    result.suggestions.forEach((_, i) => { all[i] = 'reject' })
    setDecisions(all)
  }

  const handleApply = () => {
    if (!result) return
    const accepted = result.suggestions.filter((_, i) => decisions[i] === 'accept')
    onApplySuggestions(accepted)
  }

  const acceptedCount = Object.values(decisions).filter(d => d === 'accept').length
  const rejectedCount = Object.values(decisions).filter(d => d === 'reject').length
  const pendingCount = result ? result.suggestions.length - acceptedCount - rejectedCount : 0

  return (
    <div className="bg-white rounded-xl border border-purple-200 mt-4">
      {/* Header */}
      <div className="px-6 py-4 border-b border-purple-100 bg-purple-50/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-purple-600" />
          <h3 className="font-oswald font-semibold text-tre-navy">AI Review</h3>
          {result && !loading && (
            <span className="text-sm text-gray-500">
              {result.summary}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 p-1"
          title="Close AI Review"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="p-6">
        {loading && (
          <div className="flex flex-col items-center justify-center py-8 gap-3">
            <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
            <p className="text-sm text-gray-500">
              Reviewing {entries.length} entries with AI...
            </p>
          </div>
        )}

        {error && !loading && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {result && !loading && result.suggestions.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 gap-2">
            <CheckCircle className="w-10 h-10 text-green-500" />
            <p className="font-medium text-gray-900">No issues found</p>
            <p className="text-sm text-gray-500">All {result.entries_reviewed} entries look good.</p>
          </div>
        )}

        {result && !loading && result.suggestions.length > 0 && (
          <>
            {/* Suggestion Cards */}
            <div className="space-y-3 max-h-[50vh] overflow-y-auto">
              {result.suggestions.map((suggestion, i) => {
                const decision = decisions[i]
                return (
                  <div
                    key={i}
                    className={`border rounded-lg p-4 transition-colors ${
                      decision === 'accept' ? 'border-green-300 bg-green-50/50' :
                      decision === 'reject' ? 'border-gray-200 bg-gray-50 opacity-60' :
                      'border-gray-200'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-medium text-gray-500">
                            Entry #{suggestion.entry_index}
                          </span>
                          <span className="text-xs text-gray-400">&middot;</span>
                          <span className="text-xs font-medium text-gray-700">
                            {suggestion.field}
                          </span>
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            CONFIDENCE_STYLES[suggestion.confidence]
                          }`}>
                            {suggestion.confidence}
                          </span>
                        </div>

                        {/* Diff display */}
                        <div className="flex items-center gap-2 text-sm mt-1">
                          <span className="text-red-600 line-through bg-red-50 px-1.5 py-0.5 rounded text-xs">
                            {suggestion.current_value || '(empty)'}
                          </span>
                          <span className="text-gray-400">&rarr;</span>
                          <span className="text-green-700 bg-green-50 px-1.5 py-0.5 rounded text-xs font-medium">
                            {suggestion.suggested_value}
                          </span>
                        </div>

                        <p className="text-xs text-gray-500 mt-1">{suggestion.reason}</p>
                      </div>

                      {/* Accept/Reject buttons */}
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <button
                          onClick={() => handleDecision(i, 'accept')}
                          className={`p-1.5 rounded transition-colors ${
                            decision === 'accept'
                              ? 'bg-green-500 text-white'
                              : 'text-gray-400 hover:text-green-600 hover:bg-green-50'
                          }`}
                          title="Accept suggestion"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDecision(i, 'reject')}
                          className={`p-1.5 rounded transition-colors ${
                            decision === 'reject'
                              ? 'bg-red-500 text-white'
                              : 'text-gray-400 hover:text-red-600 hover:bg-red-50'
                          }`}
                          title="Reject suggestion"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Bottom Action Bar */}
            <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  {acceptedCount} accepted
                </span>
                <span className="flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5 text-red-500" />
                  {rejectedCount} rejected
                </span>
                {pendingCount > 0 && (
                  <span>{pendingCount} pending</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleAcceptAll}
                  className="text-xs px-3 py-1.5 text-green-700 border border-green-300 rounded-lg hover:bg-green-50 transition-colors"
                >
                  Accept All
                </button>
                <button
                  onClick={handleRejectAll}
                  className="text-xs px-3 py-1.5 text-red-700 border border-red-300 rounded-lg hover:bg-red-50 transition-colors"
                >
                  Reject All
                </button>
                <button
                  onClick={handleApply}
                  disabled={acceptedCount === 0}
                  className={`text-xs px-4 py-1.5 rounded-lg transition-colors ${
                    acceptedCount > 0
                      ? 'bg-tre-navy text-white hover:bg-tre-navy/90'
                      : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  }`}
                >
                  Apply {acceptedCount > 0 ? `(${acceptedCount})` : ''}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
