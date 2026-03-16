import { Wand2, MapPin, Search, Circle } from 'lucide-react'

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
  canValidate: canValidateOverride,
  canEnrich: canEnrichOverride,
  hasProposedChanges = false,
}: EnrichmentToolbarProps) {
  const anyEnabled = cleanUpEnabled || validateEnabled || enrichEnabled
  if (!anyEnabled) return null

  const baseDisabled = isProcessing || entryCount === 0

  // If canValidate/canEnrich overrides are provided, use them; otherwise fall back to enabled+baseDisabled
  const validateDisabled = canValidateOverride !== undefined
    ? !canValidateOverride || baseDisabled
    : baseDisabled
  const enrichDisabled = canEnrichOverride !== undefined
    ? !canEnrichOverride || baseDisabled
    : baseDisabled

  return (
    <div className="relative flex items-center gap-2">
      {hasProposedChanges && (
        <Circle size={8} className="absolute -top-1 -left-1 fill-tre-teal text-tre-teal" />
      )}

      {cleanUpEnabled && (
        <button
          onClick={onCleanUp}
          disabled={baseDisabled}
          className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-tre-teal to-tre-teal/80 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:shadow disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Wand2 size={15} />
          {activeAction === 'cleanup' ? 'Processing...' : 'Clean Up'}
        </button>
      )}

      {validateEnabled && (
        <button
          onClick={onValidate}
          disabled={validateDisabled}
          className={`inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50${
            canValidateOverride === false ? ' opacity-50 cursor-not-allowed' : ''
          }`}
        >
          <MapPin size={15} />
          {activeAction === 'validate' ? 'Processing...' : 'Validate'}
        </button>
      )}

      {enrichEnabled && (
        <button
          onClick={onEnrich}
          disabled={enrichDisabled}
          className={`inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50${
            canEnrichOverride === false ? ' opacity-50 cursor-not-allowed' : ''
          }`}
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
