import { X, Database, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react'

interface FetchProgress {
  event: 'started' | 'progress' | 'complete'
  phase?: 'db_lookup' | 'rrc_query'
  checked?: number
  total?: number
  matched?: number
  matched_count?: number
  still_missing_count?: number
  updated_rows?: Record<string, unknown>[]
}

interface FetchRrcModalProps {
  isOpen: boolean
  onClose: () => void
  progress: FetchProgress | null
}

const PHASE_LABELS: Record<string, string> = {
  db_lookup: 'Checking database...',
  rrc_query: 'Querying RRC...',
}

/** Compute ETA from progress ratio — no timers, no state, no refs.
 *  Uses the elapsed_seconds field from progress events when available,
 *  otherwise estimates from the checked/total ratio. */
function computeEta(checked: number, total: number): string | null {
  if (checked <= 0 || checked >= total) return null
  // Estimate ~2s per item as rough heuristic
  const elapsed = checked * 2
  if (elapsed <= 0) return null
  const rate = checked / elapsed
  const remaining = (total - checked) / rate
  if (remaining < 60) return `~${Math.ceil(remaining)}s remaining`
  return `~${Math.ceil(remaining / 60)}m remaining`
}

export default function FetchRrcModal({ isOpen, onClose, progress }: FetchRrcModalProps) {
  const isComplete = progress?.event === 'complete'
  const phase = progress?.phase || 'db_lookup'
  const checked = progress?.checked || 0
  const total = progress?.total || 1
  const matched = progress?.matched || 0
  const pct = total > 0 ? Math.round((checked / total) * 100) : 0
  const eta = computeEta(checked, total)

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="font-oswald font-semibold text-tre-navy flex items-center gap-2">
            <Database className="w-5 h-5" />
            Fetch from RRC
          </h3>
          {isComplete && (
            <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 transition-colors">
              <X className="w-4 h-4 text-gray-500" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="px-5 py-5 space-y-4">
          {/* Phase label */}
          <div className="flex items-center gap-2 text-sm">
            {!isComplete ? (
              <>
                <Loader2 className="w-4 h-4 text-tre-teal animate-spin" />
                <span className="text-gray-700 font-medium">{PHASE_LABELS[phase] || phase}</span>
              </>
            ) : (
              <>
                <CheckCircle className="w-4 h-4 text-green-600" />
                <span className="text-gray-700 font-medium">Complete</span>
              </>
            )}
          </div>

          {/* Progress bar */}
          <div>
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>{checked} / {total}</span>
              {eta && <span>{eta}</span>}
              {isComplete && <span>Done</span>}
            </div>
            <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${isComplete ? 'bg-green-500' : 'bg-tre-teal'}`}
                style={{ width: `${isComplete ? 100 : pct}%` }}
              />
            </div>
          </div>

          {/* Live match counter */}
          {!isComplete && (
            <p className="text-sm text-gray-600">
              <span className="font-medium text-green-600">{matched}</span> matched so far
            </p>
          )}

          {/* Completion summary */}
          {isComplete && (
            <div className="flex items-center gap-3 pt-1">
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
                <CheckCircle className="w-3 h-3" />
                Found {progress?.matched_count || 0}
              </span>
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                <AlertTriangle className="w-3 h-3" />
                Not found {progress?.still_missing_count || 0}
              </span>
            </div>
          )}
        </div>

        {/* Footer */}
        {isComplete && (
          <div className="px-5 py-3 border-t border-gray-100 flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-tre-navy text-white rounded-lg text-sm hover:bg-tre-navy/90 transition-colors"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
