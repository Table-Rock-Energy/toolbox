import { Wand2, MapPin, Search, Loader2 } from 'lucide-react'

interface EnrichmentToolbarProps {
  cleanUpEnabled: boolean
  validateEnabled: boolean
  enrichEnabled: boolean
  onCleanUp: () => void
  onValidate: () => void
  onEnrich: () => void
  isProcessing: boolean
  entryCount: number
  activeAction?: 'cleanup' | 'validate' | 'enrich' | null
  canValidate?: boolean
  canEnrich?: boolean
  hasProposedChanges?: boolean
}

export default function EnrichmentToolbar({
  cleanUpEnabled,
  validateEnabled,
  enrichEnabled,
  onCleanUp,
  onValidate,
  onEnrich,
  isProcessing,
  entryCount,
  activeAction = null,
}: EnrichmentToolbarProps) {
  const anyEnabled = cleanUpEnabled || validateEnabled || enrichEnabled
  if (!anyEnabled) return null

  const baseDisabled = isProcessing || entryCount === 0

  return (
    <div className="flex items-center gap-2">
      {cleanUpEnabled && (
        <button
          onClick={onCleanUp}
          disabled={baseDisabled}
          className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-tre-teal to-tre-teal/80 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:shadow disabled:cursor-not-allowed disabled:opacity-50"
        >
          {activeAction === 'cleanup'
            ? <Loader2 size={15} className="animate-spin" />
            : <Wand2 size={15} />}
          {activeAction === 'cleanup' ? 'Cleaning...' : 'Clean Up'}
        </button>
      )}

      {validateEnabled && (
        <button
          onClick={onValidate}
          disabled={baseDisabled}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {activeAction === 'validate'
            ? <Loader2 size={15} className="animate-spin" />
            : <MapPin size={15} />}
          {activeAction === 'validate' ? 'Validating...' : 'Validate'}
        </button>
      )}

      {enrichEnabled && (
        <button
          onClick={onEnrich}
          disabled={baseDisabled}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {activeAction === 'enrich'
            ? <Loader2 size={15} className="animate-spin" />
            : <Search size={15} />}
          {activeAction === 'enrich' ? 'Enriching...' : `Enrich (${entryCount})`}
        </button>
      )}
    </div>
  )
}
