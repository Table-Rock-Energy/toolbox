import { Wand2, MapPin, Search } from 'lucide-react'

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

  const isDisabled = isProcessing || entryCount === 0

  return (
    <div className="flex items-center gap-2">
      {cleanUpEnabled && (
        <button
          onClick={onCleanUp}
          disabled={isDisabled}
          className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-tre-teal to-tre-teal/80 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:shadow disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Wand2 size={15} />
          {activeAction === 'cleanup' ? 'Processing...' : 'Clean Up'}
        </button>
      )}

      {validateEnabled && (
        <button
          onClick={onValidate}
          disabled={isDisabled}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <MapPin size={15} />
          {activeAction === 'validate' ? 'Processing...' : 'Validate'}
        </button>
      )}

      {enrichEnabled && (
        <button
          onClick={onEnrich}
          disabled={isDisabled}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Search size={15} />
          {activeAction === 'enrich'
            ? 'Processing...'
            : `Enrich (${entryCount})`}
        </button>
      )}
    </div>
  )
}
