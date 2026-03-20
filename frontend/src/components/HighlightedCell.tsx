import { useState } from 'react'
import type { EnrichmentCellChange } from '../hooks/useEnrichmentPipeline'

const STEP_SOURCE_LABELS: Record<string, string> = {
  cleanup: 'AI Cleanup',
  validate: 'Google Maps',
  enrich: 'Enrichment',
}

interface HighlightedCellProps {
  value: string | number | null | undefined
  highlight: EnrichmentCellChange | null
  className?: string
  children?: React.ReactNode
}

export default function HighlightedCell({ value, highlight, className = '', children }: HighlightedCellProps) {
  const [expanded, setExpanded] = useState(false)

  if (!highlight) {
    return (
      <td className={className}>
        {children ?? (value || <span className="text-gray-400">{'\u2014'}</span>)}
      </td>
    )
  }

  const source = STEP_SOURCE_LABELS[highlight.step] || highlight.step
  const oldVal = highlight.original_value || '(empty)'

  return (
    <td
      className={`${className} bg-green-50 cursor-pointer select-none`}
      onClick={() => setExpanded(prev => !prev)}
      title={`Changed by ${source} — click to ${expanded ? 'hide' : 'show'} original`}
    >
      <div>
        {children ?? (value || <span className="text-gray-400">{'\u2014'}</span>)}
      </div>
      {expanded && (
        <div className="text-[10px] text-gray-400 line-through mt-0.5 leading-tight">
          {oldVal}
        </div>
      )}
    </td>
  )
}
