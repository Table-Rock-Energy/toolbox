import { useState } from 'react'
import { Check, X, ChevronDown, ChevronRight } from 'lucide-react'
import type { ProposedChange } from '../utils/api'

interface ProposedChangesPanelProps {
  proposedChanges: ProposedChange[]
  checkedIndices: Set<number>
  onToggleCheck: (index: number) => void
  onToggleCheckAll: () => void
  onApply: () => void
  onDismiss: () => void
}

const SOURCE_COLORS: Record<string, string> = {
  ai_cleanup: 'border-l-tre-teal',
  google_maps: 'border-l-blue-500',
  pdl: 'border-l-purple-500',
  searchbug: 'border-l-purple-500',
}

const SOURCE_LABELS: Record<string, string> = {
  ai_cleanup: 'AI',
  google_maps: 'Google Maps',
  pdl: 'PDL',
  searchbug: 'SearchBug',
}

const CONFIDENCE_STYLES: Record<string, string> = {
  high: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-red-100 text-red-800',
}

const CONFIDENCE_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 }

export default function ProposedChangesPanel({
  proposedChanges,
  checkedIndices,
  onToggleCheck,
  onToggleCheckAll,
  onApply,
  onDismiss,
}: ProposedChangesPanelProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set())

  if (proposedChanges.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
        No changes proposed. Data looks good.
        <button onClick={onDismiss} className="ml-3 text-tre-teal hover:underline">
          Dismiss
        </button>
      </div>
    )
  }

  // Group changes by entry_index
  const groups = new Map<number, { indices: number[]; changes: ProposedChange[] }>()
  proposedChanges.forEach((change, idx) => {
    const existing = groups.get(change.entry_index)
    if (existing) {
      existing.indices.push(idx)
      existing.changes.push(change)
    } else {
      groups.set(change.entry_index, { indices: [idx], changes: [change] })
    }
  })

  // Sort groups by highest confidence (high first)
  const sortedGroups = [...groups.entries()].sort(([, a], [, b]) => {
    const aHighest = Math.min(...a.changes.map(c => CONFIDENCE_ORDER[c.confidence] ?? 3))
    const bHighest = Math.min(...b.changes.map(c => CONFIDENCE_ORDER[c.confidence] ?? 3))
    return aHighest - bHighest
  })

  const allChecked = checkedIndices.size === proposedChanges.length
  const someChecked = checkedIndices.size > 0 && !allChecked

  const toggleGroup = (entryIndex: number) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(entryIndex)) {
        next.delete(entryIndex)
      } else {
        next.add(entryIndex)
      }
      return next
    })
  }

  const isGroupChecked = (indices: number[]) => indices.every((i) => checkedIndices.has(i))
  const isGroupPartial = (indices: number[]) =>
    indices.some((i) => checkedIndices.has(i)) && !isGroupChecked(indices)

  const toggleGroupCheck = (indices: number[]) => {
    const allIn = isGroupChecked(indices)
    indices.forEach((i) => {
      if (allIn) {
        if (checkedIndices.has(i)) onToggleCheck(i)
      } else {
        if (!checkedIndices.has(i)) onToggleCheck(i)
      }
    })
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={allChecked}
              ref={(el) => { if (el) el.indeterminate = someChecked }}
              onChange={onToggleCheckAll}
              className="h-4 w-4 rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
            />
            <span className="text-sm font-medium text-gray-700">
              {proposedChanges.length} proposed change{proposedChanges.length !== 1 ? 's' : ''}
            </span>
          </label>
          {checkedIndices.size > 0 && checkedIndices.size < proposedChanges.length && (
            <span className="text-xs text-gray-500">
              ({checkedIndices.size} selected)
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onApply}
            disabled={checkedIndices.size === 0}
            className="inline-flex items-center gap-1.5 rounded-md bg-tre-teal px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-tre-teal/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Check size={14} />
            Apply ({checkedIndices.size})
          </button>
          <button
            onClick={onDismiss}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 shadow-sm transition hover:bg-gray-50"
          >
            <X size={14} />
            Dismiss
          </button>
        </div>
      </div>

      {/* Change groups */}
      <div className="max-h-64 overflow-y-auto divide-y divide-gray-50">
        {sortedGroups.map(([entryIndex, { indices, changes }]) => {
          const isExpanded = expandedGroups.has(entryIndex)
          const primarySource = changes[0].source
          const borderColor = SOURCE_COLORS[primarySource] || 'border-l-gray-300'
          const highestConfidence = changes.reduce((best, c) =>
            (CONFIDENCE_ORDER[c.confidence] ?? 3) < (CONFIDENCE_ORDER[best] ?? 3) ? c.confidence : best
          , changes[0].confidence)

          return (
            <div key={entryIndex} className={`border-l-4 ${borderColor}`}>
              {/* Group header */}
              <div
                className="flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-gray-50"
                onClick={() => toggleGroup(entryIndex)}
              >
                <input
                  type="checkbox"
                  checked={isGroupChecked(indices)}
                  ref={(el) => { if (el) el.indeterminate = isGroupPartial(indices) }}
                  onChange={(e) => { e.stopPropagation(); toggleGroupCheck(indices) }}
                  onClick={(e) => e.stopPropagation()}
                  className="h-4 w-4 rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                />
                {isExpanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                <span className="text-sm text-gray-700">
                  Row {entryIndex + 1}
                </span>
                <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-medium ${CONFIDENCE_STYLES[highestConfidence] || ''}`}>
                  {highestConfidence}
                </span>
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                  {changes.length} field{changes.length !== 1 ? 's' : ''}
                </span>
                {changes.some((c) => c.authoritative) && (
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                    authoritative
                  </span>
                )}
              </div>

              {/* Expanded details */}
              {isExpanded && (
                <div className="bg-gray-50/50 px-4 pb-3 pt-1 space-y-2">
                  {changes.map((change, changeIdx) => {
                    const globalIdx = indices[changeIdx]
                    return (
                      <div
                        key={`${change.field}-${changeIdx}`}
                        className="flex items-start gap-3 rounded bg-white p-2 text-sm border border-gray-100"
                      >
                        <input
                          type="checkbox"
                          checked={checkedIndices.has(globalIdx)}
                          onChange={() => onToggleCheck(globalIdx)}
                          className="mt-0.5 h-3.5 w-3.5 rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-gray-700">{change.field}</span>
                            <span className={`rounded px-1.5 py-0.5 text-xs ${CONFIDENCE_STYLES[change.confidence] || ''}`}>
                              {change.confidence}
                            </span>
                            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                              {SOURCE_LABELS[change.source] || change.source}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-xs">
                            <span className="text-red-600 line-through truncate max-w-[200px]" title={change.current_value}>
                              {change.current_value || '(empty)'}
                            </span>
                            <span className="text-gray-400">&rarr;</span>
                            <span className="text-green-700 font-medium truncate max-w-[200px]" title={change.proposed_value}>
                              {change.proposed_value || '(empty)'}
                            </span>
                          </div>
                          {change.reason && (
                            <p className="mt-1 text-xs text-gray-500">{change.reason}</p>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
