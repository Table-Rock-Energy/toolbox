import { useState } from 'react'
import { CheckCircle, ChevronDown, ChevronUp, Undo2 } from 'lucide-react'

export interface AutoCorrection {
  entry_index: number
  field: string
  original_value: string
  corrected_value: string
  source: string
  confidence: string
}

interface PostProcessResult {
  corrections: AutoCorrection[]
  ai_suggestions: { entry_index: number; field: string; current_value: string; suggested_value: string; reason: string; confidence: string }[]
  steps_completed: string[]
  steps_skipped: string[]
}

interface AutoCorrectionsBannerProps {
  postProcess?: PostProcessResult
  corrections?: AutoCorrection[]
  onUndo: () => void
}

const SOURCE_LABELS: Record<string, string> = {
  programmatic: 'Auto',
  google_maps: 'Maps',
  ai: 'AI',
  ai_cleanup: 'AI',
}

const SOURCE_STYLES: Record<string, string> = {
  programmatic: 'bg-blue-100 text-blue-700',
  google_maps: 'bg-green-100 text-green-700',
  ai: 'bg-purple-100 text-purple-700',
  ai_cleanup: 'bg-purple-100 text-purple-700',
}

export default function AutoCorrectionsBanner({ postProcess, corrections: directCorrections, onUndo }: AutoCorrectionsBannerProps) {
  const [expanded, setExpanded] = useState(false)

  const corrections = directCorrections ?? postProcess?.corrections ?? []
  if (!corrections.length) return null

  // Group by source
  const bySource: Record<string, number> = {}
  for (const c of corrections) {
    bySource[c.source] = (bySource[c.source] || 0) + 1
  }

  const summaryParts = Object.entries(bySource).map(
    ([source, count]) => `${count} ${SOURCE_LABELS[source] || source}`
  )

  return (
    <div className="bg-green-50 border border-green-200 rounded-xl mt-4">
      <div className="px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-green-600" />
          <span className="text-sm font-medium text-green-800">
            Auto-corrected {corrections.length} field{corrections.length !== 1 ? 's' : ''}
          </span>
          <span className="text-xs text-green-600">
            ({summaryParts.join(', ')})
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onUndo}
            className="text-xs px-3 py-1.5 text-green-700 border border-green-300 rounded-lg hover:bg-green-100 transition-colors flex items-center gap-1"
          >
            <Undo2 className="w-3.5 h-3.5" />
            Undo all
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-green-600 hover:text-green-800 p-1"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-green-200 px-5 py-3">
          <div className="max-h-[40vh] overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-green-700 border-b border-green-100">
                  <th className="pb-2 pr-3">#</th>
                  <th className="pb-2 pr-3">Field</th>
                  <th className="pb-2 pr-3">Before</th>
                  <th className="pb-2 pr-3">After</th>
                  <th className="pb-2">Source</th>
                </tr>
              </thead>
              <tbody>
                {corrections.map((c, i) => (
                  <tr key={i} className="border-b border-green-50">
                    <td className="py-1.5 pr-3 text-gray-500">{c.entry_index}</td>
                    <td className="py-1.5 pr-3 font-medium text-gray-700">{c.field}</td>
                    <td className="py-1.5 pr-3">
                      <span className="text-red-600 line-through bg-red-50 px-1 rounded">
                        {c.original_value || '(empty)'}
                      </span>
                    </td>
                    <td className="py-1.5 pr-3">
                      <span className="text-green-700 bg-green-100 px-1 rounded font-medium">
                        {c.corrected_value}
                      </span>
                    </td>
                    <td className="py-1.5">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${SOURCE_STYLES[c.source] || 'bg-gray-100 text-gray-600'}`}>
                        {SOURCE_LABELS[c.source] || c.source}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
