import { Sparkles, Loader2, Check, RotateCcw, X } from 'lucide-react'
import type { PipelineStatus } from '../hooks/useEnrichmentPipeline'

interface UnifiedEnrichButtonProps {
  pipelineStatus: PipelineStatus
  entryCount: number
  anyStepEnabled: boolean
  onEnrich: () => void
  onReopen: () => void
  onUndo: () => void
  onClearHighlights: () => void
  hasChanges: boolean
  hasSnapshot: boolean
}

export default function UnifiedEnrichButton({
  pipelineStatus,
  entryCount,
  anyStepEnabled,
  onEnrich,
  onReopen,
  onUndo,
  onClearHighlights,
  hasChanges,
  hasSnapshot,
}: UnifiedEnrichButtonProps) {
  if (!anyStepEnabled) return null

  const isIdle = pipelineStatus === 'idle' && !hasChanges && !hasSnapshot
  const isRunning = pipelineStatus === 'running'
  const isCompleted = pipelineStatus === 'completed' || (pipelineStatus === 'idle' && (hasChanges || hasSnapshot))

  const handleMainClick = () => {
    if (isRunning) {
      onReopen()
    } else if (isCompleted) {
      const ok = window.confirm('Re-run enrichment? This will replace current results.')
      if (ok) onEnrich()
    } else {
      onEnrich()
    }
  }

  return (
    <div className="flex items-center gap-2">
      {/* Main button */}
      <button
        onClick={handleMainClick}
        disabled={isIdle && (entryCount === 0)}
        className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium shadow-sm transition hover:shadow disabled:cursor-not-allowed disabled:opacity-50 ${
          isRunning
            ? 'bg-gradient-to-r from-tre-teal to-tre-teal/80 text-white'
            : isCompleted
              ? 'bg-green-100 text-green-800 border border-green-300'
              : 'bg-gradient-to-r from-tre-teal to-tre-teal/80 text-white'
        }`}
      >
        {isRunning ? (
          <>
            <Loader2 size={15} className="animate-spin" />
            Running...
          </>
        ) : isCompleted ? (
          <>
            <Check size={15} />
            Enriched
          </>
        ) : (
          <>
            <Sparkles size={15} />
            Enrich ({entryCount})
          </>
        )}
      </button>

      {/* Secondary actions */}
      {hasSnapshot && (
        <button
          onClick={onUndo}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50"
        >
          <RotateCcw size={15} />
          Undo Enrichment
        </button>
      )}
      {hasChanges && (
        <button
          onClick={onClearHighlights}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50"
        >
          <X size={15} />
          Clear Highlights
        </button>
      )}
    </div>
  )
}
