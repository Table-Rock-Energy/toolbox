import { Check, X } from 'lucide-react'
import type { ProposedChange } from '../utils/api'

interface ProposedChangesSummaryProps {
  proposedChanges: ProposedChange[]
  checkedIndices: Set<number>
  onToggleCheckAll: () => void
  onApply: () => void
  onDismiss: () => void
}

export default function ProposedChangesSummary({
  proposedChanges,
  checkedIndices,
  onToggleCheckAll,
  onApply,
  onDismiss,
}: ProposedChangesSummaryProps) {
  if (proposedChanges.length === 0) {
    return (
      <div className="flex items-center justify-between px-5 py-3 bg-green-50 border border-green-200 rounded-lg">
        <span className="text-sm text-green-700">No changes proposed. Data looks good.</span>
        <button onClick={onDismiss} className="text-sm text-green-600 hover:underline">Dismiss</button>
      </div>
    )
  }

  const affectedRows = new Set(proposedChanges.map(c => c.entry_index)).size
  const allChecked = checkedIndices.size === proposedChanges.length
  const someChecked = checkedIndices.size > 0 && !allChecked

  return (
    <div className="flex items-center justify-between px-5 py-3 bg-blue-50 border border-blue-200 rounded-lg">
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={allChecked}
            ref={(el) => { if (el) el.indeterminate = someChecked }}
            onChange={onToggleCheckAll}
            className="h-4 w-4 rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
          />
          <span className="text-sm font-medium text-blue-800">
            {proposedChanges.length} change{proposedChanges.length !== 1 ? 's' : ''} across {affectedRows} row{affectedRows !== 1 ? 's' : ''}
          </span>
        </label>
        <span className="text-xs text-blue-600">
          Highlighted below — click a cell to see original value
        </span>
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
  )
}
