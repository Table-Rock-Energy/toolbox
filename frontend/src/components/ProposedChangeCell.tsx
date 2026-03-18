import { useState } from 'react'
import type { ProposedChange } from '../utils/api'

interface ProposedChangeCellProps {
  change: ProposedChange
  children?: React.ReactNode
}

const SOURCE_LABELS: Record<string, string> = {
  ai_cleanup: 'AI',
  google_maps: 'Maps',
  pdl: 'PDL',
  searchbug: 'SB',
}

export default function ProposedChangeCell({ change, children }: ProposedChangeCellProps) {
  const [showOriginal, setShowOriginal] = useState(false)

  return (
    <div
      className="cursor-pointer group relative"
      onClick={() => setShowOriginal(!showOriginal)}
      title={showOriginal
        ? `Proposed: ${change.proposed_value} (click to toggle)`
        : `Original: ${change.current_value} (click to toggle)`
      }
    >
      {showOriginal ? (
        <span className="text-red-600 line-through text-xs">
          {change.current_value || '\u2014'}
        </span>
      ) : (
        <span className="text-xs">
          {children ?? change.proposed_value}
        </span>
      )}
      <span className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <span className={`inline-block px-1 py-0.5 rounded text-[9px] font-medium leading-none ${
          change.source === 'google_maps' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
        }`}>
          {SOURCE_LABELS[change.source] || change.source}
        </span>
      </span>
    </div>
  )
}
