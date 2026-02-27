import { useState, useEffect, useMemo } from 'react'
import { Repeat, Download, Upload, AlertCircle, Send } from 'lucide-react'
import { FileUpload, GhlSendModal } from '../components'
import { useAuth } from '../contexts/AuthContext'
import { ghlApi } from '../utils/api'
import type { GhlConnectionResponse } from '../utils/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

interface TransformResult {
  success: boolean
  rows: Record<string, string>[]
  total_count: number
  transformed_fields: {
    title_cased: number
    campaigns_extracted: number
    phone_mapped: number
    contact_owner_added: number
  }
  warnings: string[]
  source_filename: string
  job_id?: string
}

interface UploadResponse {
  message: string
  result?: TransformResult
}

export default function GhlPrep() {
  const { user, userName } = useAuth()
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<TransformResult | null>(null)
  const [sortColumn, setSortColumn] = useState<string | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [connections, setConnections] = useState<GhlConnectionResponse[]>([])
  const [showSendModal, setShowSendModal] = useState(false)

  // Fetch GHL connections from backend
  useEffect(() => {
    const fetchConnections = async () => {
      const res = await ghlApi.listConnections()
      if (res.data) {
        setConnections(res.data.connections)
      }
    }
    fetchConnections()
  }, [])
  // Get dynamic columns from first row
  const columns = useMemo(() => {
    if (!result?.rows || result.rows.length === 0) return []
    return Object.keys(result.rows[0])
  }, [result])

  // Derive campaign tag from result data
  const defaultTag = useMemo(() => {
    if (!result?.rows || result.rows.length === 0) return ''
    const firstRow = result.rows[0]
    return firstRow['Tags'] || firstRow['tags'] || firstRow['Campaign'] || firstRow['campaign'] || ''
  }, [result])

  // Sort rows client-side
  const sortedRows = useMemo(() => {
    if (!result?.rows || !sortColumn) return result?.rows || []

    const sorted = [...result.rows].sort((a, b) => {
      const aVal = a[sortColumn] || ''
      const bVal = b[sortColumn] || ''

      if (sortDirection === 'asc') {
        return aVal.localeCompare(bVal)
      } else {
        return bVal.localeCompare(aVal)
      }
    })

    return sorted
  }, [result?.rows, sortColumn, sortDirection])

  const handleColumnClick = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(column)
      setSortDirection('asc')
    }
  }

  const handleFilesSelected = async (files: File[]) => {
    if (files.length === 0) return

    const file = files[0]
    setIsProcessing(true)
    setError(null)
    setResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API_BASE}/ghl-prep/upload`, {
        method: 'POST',
        headers: {
          'X-User-Email': user?.email || '',
          'X-User-Name': userName || user?.displayName || '',
        },
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data: UploadResponse = await response.json()
      if (data.result) {
        setResult(data.result)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process file')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleExport = async () => {
    if (!result?.rows || result.rows.length === 0) {
      setError('No data to export')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/ghl-prep/export/csv`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rows: result.rows,
          filename: result.source_filename?.replace(/\.[^.]+$/, '') || 'ghl_export',
        }),
      })

      if (!response.ok) throw new Error('Export failed')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const baseName = result.source_filename?.replace(/\.[^.]+$/, '') || 'ghl_export'
      a.download = `${baseName}_ghl_prep.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch {
      setError('Failed to export file')
    }
  }

  const handleReset = () => {
    setResult(null)
    setError(null)
    setSortColumn(null)
    setSortDirection('asc')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-orange-100 rounded-lg">
          <Repeat className="w-6 h-6 text-orange-600" />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            GHL Prep
          </h1>
          <p className="text-gray-500 text-sm">
            Transform Mineral export CSVs for GoHighLevel import
          </p>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      )}

      {/* Upload Section */}
      {!result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <FileUpload
            onFilesSelected={handleFilesSelected}
            accept=".csv"
            multiple={false}
            label="Upload Mineral Export"
            description="Drop your Mineral CSV export here"
          />
          {isProcessing && (
            <div className="mt-4 flex items-center gap-2 text-tre-teal">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-tre-teal"></div>
              <span className="text-sm">Processing...</span>
            </div>
          )}
        </div>
      )}

      {/* Results Section */}
      {result && (
        <div className="bg-white rounded-xl border border-gray-200">
          {/* Results Header */}
          <div className="px-6 py-4 border-b border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-oswald font-semibold text-tre-navy">
                  {result.source_filename}
                </h3>
                <p className="text-sm text-gray-500">
                  Transformation complete
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleReset}
                  className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                >
                  <Upload className="w-4 h-4" />
                  Upload New File
                </button>
                <button
                  onClick={() => setShowSendModal(true)}
                  disabled={connections.length === 0}
                  title={connections.length === 0 ? 'Add a GHL connection in Settings first' : 'Send contacts to GoHighLevel'}
                  className="flex items-center gap-2 px-3 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                  Send to GHL
                </button>
                <button
                  onClick={handleExport}
                  className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                >
                  <Download className="w-4 h-4" />
                  Download CSV
                </button>
              </div>
            </div>
          </div>

          {/* Warnings */}
          {result.warnings && result.warnings.length > 0 && (
            <div className="mx-6 mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-yellow-800 mb-1">Warnings:</p>
                  <ul className="text-sm text-yellow-700 space-y-1">
                    {result.warnings.map((warning, i) => (
                      <li key={i}>{warning}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Preview Table */}
          <div className="p-6">
            <h4 className="font-medium text-gray-900 mb-3">
              {sortedRows.length} rows
            </h4>
            <div className="overflow-x-auto overflow-y-auto max-h-[75vh]">
              <table className="text-sm">
                <thead className="sticky top-0 bg-white z-10">
                  <tr className="border-b border-gray-200">
                    {columns.map((column) => (
                      <th
                        key={column}
                        onClick={() => handleColumnClick(column)}
                        className="text-left py-2 px-4 font-medium text-gray-600 cursor-pointer hover:bg-gray-50 transition-colors whitespace-nowrap"
                        title="Click to sort"
                      >
                        <div className="flex items-center gap-1">
                          {column}
                          {sortColumn === column && (
                            <span className="text-tre-teal">
                              {sortDirection === 'asc' ? '↑' : '↓'}
                            </span>
                          )}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {sortedRows.map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      {columns.map((column) => {
                        const value = String(row[column] ?? '')
                        return (
                          <td
                            key={column}
                            className="py-2 px-4 text-gray-600 whitespace-nowrap"
                          >
                            {value || <span className="text-gray-400">{'\u2014'}</span>}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Send to GHL Modal */}
      <GhlSendModal
        isOpen={showSendModal}
        onClose={() => setShowSendModal(false)}
        connections={connections}
        contactCount={result?.rows?.length || 0}
        defaultTag={defaultTag}
        rows={result?.rows || []}
      />
    </div>
  )
}
