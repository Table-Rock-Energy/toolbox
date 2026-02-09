import { useState, useEffect, useRef } from 'react'
import { DollarSign, Download, Upload, FileText, AlertCircle, CheckCircle, ChevronDown, ChevronRight, Edit2, Columns } from 'lucide-react'
import { FileUpload, Modal } from '../components'
import { useAuth } from '../contexts/AuthContext'

interface RevenueRow {
  property_name?: string
  property_number?: string
  sales_date?: string
  product_code?: string
  product_description?: string
  decimal_interest?: number
  interest_type?: string
  avg_price?: number
  property_gross_volume?: number
  property_gross_revenue?: number
  owner_volume?: number
  owner_value?: number
  owner_tax_amount?: number
  tax_type?: string
  owner_deduct_amount?: number
  deduct_code?: string
  owner_net_revenue?: number
}

interface RevenueStatement {
  filename: string
  format: string
  payor?: string
  check_number?: string
  check_amount?: number
  check_date?: string
  operator_name?: string
  owner_number?: string
  owner_name?: string
  rows: RevenueRow[]
  errors: string[]
}

interface UploadResponse {
  success: boolean
  statements?: RevenueStatement[]
  total_rows?: number
  errors?: string[]
  job_id?: string
}

interface RevenueJob {
  id: string
  job_id?: string
  documentName: string
  user: string
  timestamp: string
  result?: UploadResponse
}

interface ColumnConfig {
  key: string
  label: string
  alwaysVisible?: boolean
}

const COLUMNS: ColumnConfig[] = [
  { key: 'property_name', label: 'Property' },
  { key: 'sales_date', label: 'Date' },
  { key: 'product', label: 'Product' },
  { key: 'interest', label: 'Interest' },
  { key: 'volume', label: 'Volume' },
  { key: 'gross', label: 'Gross' },
  { key: 'tax', label: 'Tax' },
  { key: 'net', label: 'Net' },
  { key: 'edit', label: '', alwaysVisible: true },
]

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Revenue() {
  const { user } = useAuth()
  const [jobs, setJobs] = useState<RevenueJob[]>([])
  const [activeJob, setActiveJob] = useState<RevenueJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedStatement, setExpandedStatement] = useState<number | null>(null)

  // Edit modal state
  const [editingRow, setEditingRow] = useState<{ statementIdx: number; rowIdx: number; row: RevenueRow } | null>(null)

  // Column visibility
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(
    new Set(COLUMNS.map((c) => c.key))
  )
  const [showColumnPicker, setShowColumnPicker] = useState(false)
  const columnPickerRef = useRef<HTMLDivElement>(null)

  // Close column picker on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (columnPickerRef.current && !columnPickerRef.current.contains(e.target as Node)) {
        setShowColumnPicker(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Load recent jobs from Firestore on mount
  useEffect(() => {
    const loadJobs = async () => {
      try {
        const response = await fetch(`${API_BASE}/history/jobs?tool=revenue&limit=20`)
        if (!response.ok) return
        const data = await response.json()
        if (data.jobs?.length) {
          const loaded: RevenueJob[] = data.jobs.map((j: Record<string, unknown>) => ({
            id: j.id as string,
            job_id: j.id as string,
            documentName: (j.source_filename as string) || 'Unknown',
            user: (j.user_id as string) || 'System',
            timestamp: j.created_at
              ? new Date(j.created_at as string).toLocaleString()
              : '',
          }))
          setJobs(loaded)
        }
      } catch {
        // Firestore unavailable
      }
    }
    loadJobs()
  }, [])

  const handleFilesSelected = async (files: File[]) => {
    if (files.length === 0) return

    const file = files[0]
    setIsProcessing(true)
    setError(null)

    const newJob: RevenueJob = {
      id: String(Date.now()),
      documentName: file.name,
      user: user?.displayName || user?.email || 'Unknown',
      timestamp: new Date().toLocaleString(),
    }

    try {
      const formData = new FormData()
      formData.append('files', file)

      const response = await fetch(`${API_BASE}/revenue/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data: UploadResponse = await response.json()
      newJob.result = data
      newJob.job_id = data.job_id

      setJobs((prev) => [newJob, ...prev])
      setActiveJob(newJob)
      setExpandedStatement(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process files')
      newJob.result = {
        success: false,
        errors: [err instanceof Error ? err.message : 'Failed to process files'],
      }
      setJobs((prev) => [newJob, ...prev])
    } finally {
      setIsProcessing(false)
    }
  }

  const handleExport = async () => {
    if (!activeJob?.result?.statements) return

    try {
      const response = await fetch(`${API_BASE}/revenue/export/csv`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          statements: activeJob.result.statements,
        }),
      })

      if (!response.ok) throw new Error('Export failed')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activeJob.documentName.replace(/\.[^.]+$/, '')}_m1_export.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch {
      setError('Failed to export file')
    }
  }

  const handleSelectJob = async (job: RevenueJob) => {
    setActiveJob(job)
    setError(null)

    // Lazy-load entries if not already loaded
    if (!job.result && job.job_id) {
      try {
        const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}/entries`)
        if (response.ok) {
          const data = await response.json()
          const statements = data.entries as RevenueStatement[]
          const totalRows = statements.reduce((sum: number, s: RevenueStatement) => sum + s.rows.length, 0)
          const result: UploadResponse = {
            success: true,
            statements,
            total_rows: totalRows,
            job_id: job.job_id,
          }
          const updatedJob = { ...job, result }
          setJobs((prev) => prev.map((j) => (j.id === job.id ? updatedJob : j)))
          setActiveJob(updatedJob)
        }
      } catch {
        // Failed to load
      }
    }
  }

  const formatCurrency = (amount?: number): string => {
    if (amount === undefined || amount === null) return '\u2014'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount)
  }

  const getAllRows = (): RevenueRow[] => {
    if (!activeJob?.result?.statements) return []
    return activeJob.result.statements.flatMap(s => s.rows)
  }

  const getTotals = () => {
    const rows = getAllRows()
    return {
      gross: rows.reduce((sum, r) => sum + (r.owner_value || 0), 0),
      tax: rows.reduce((sum, r) => sum + (r.owner_tax_amount || 0), 0),
      deductions: rows.reduce((sum, r) => sum + (r.owner_deduct_amount || 0), 0),
      net: rows.reduce((sum, r) => sum + (r.owner_net_revenue || 0), 0),
    }
  }

  const handleEditRow = (statementIdx: number, rowIdx: number, row: RevenueRow) => {
    setEditingRow({ statementIdx, rowIdx, row: { ...row } })
  }

  const handleSaveEditRow = () => {
    if (!editingRow || !activeJob?.result?.statements) return

    const updatedStatements = [...activeJob.result.statements]
    const stmt = { ...updatedStatements[editingRow.statementIdx] }
    const updatedRows = [...stmt.rows]
    updatedRows[editingRow.rowIdx] = editingRow.row
    stmt.rows = updatedRows
    updatedStatements[editingRow.statementIdx] = stmt

    setActiveJob({
      ...activeJob,
      result: {
        ...activeJob.result,
        statements: updatedStatements,
      },
    })
    setEditingRow(null)
  }

  const toggleColumn = (key: string) => {
    const next = new Set(visibleColumns)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setVisibleColumns(next)
  }

  const isColVisible = (key: string) => visibleColumns.has(key)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-amber-100 rounded-lg">
          <DollarSign className="w-6 h-6 text-amber-600" />
        </div>
        <div>
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Revenue
          </h1>
          <p className="text-gray-500 text-sm">
            Extract revenue statements from EnergyLink and Energy Transfer PDFs
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Upload and History */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <FileUpload
              onFilesSelected={handleFilesSelected}
              accept=".pdf"
              multiple={false}
              label="Upload Revenue Statement"
              description="Drop your PDF file here"
            />
            {isProcessing && (
              <div className="mt-4 flex items-center gap-2 text-tre-teal">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-tre-teal"></div>
                <span className="text-sm">Processing...</span>
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200">
            <div className="px-4 py-3 border-b border-gray-100">
              <h3 className="font-medium text-gray-900">Recent Jobs</h3>
            </div>
            {jobs.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                <Upload className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p className="text-sm">No jobs yet</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100 max-h-80 overflow-y-auto">
                {jobs.map((job) => (
                  <button
                    key={job.id}
                    onClick={() => handleSelectJob(job)}
                    className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                      activeJob?.id === job.id ? 'bg-tre-teal/5 border-l-2 border-tre-teal' : ''
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {job.documentName}
                        </p>
                        <p className="text-xs text-gray-500">{job.user}</p>
                        <p className="text-xs text-gray-400">{job.timestamp}</p>
                      </div>
                      {job.result?.success ? (
                        <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                      ) : job.result?.errors?.length ? (
                        <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                      ) : null}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column - Results */}
        <div className="lg:col-span-2">
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          )}

          {activeJob?.result?.success ? (
            <div className="bg-white rounded-xl border border-gray-200">
              {/* Results Header */}
              <div className="px-6 py-4 border-b border-gray-100">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-oswald font-semibold text-tre-navy">
                      {activeJob.documentName}
                    </h3>
                    <p className="text-sm text-gray-500">
                      Processed by {activeJob.user} on {activeJob.timestamp}
                    </p>
                  </div>
                  <button
                    onClick={handleExport}
                    className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
                  >
                    <Download className="w-4 h-4" />
                    M1 CSV
                  </button>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-4 gap-4 p-6 border-b border-gray-100">
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {activeJob.result.statements?.length || 0}
                  </p>
                  <p className="text-sm text-gray-500">Statements</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {activeJob.result.total_rows || getAllRows().length}
                  </p>
                  <p className="text-sm text-gray-500">Total Rows</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-oswald font-semibold text-green-600">
                    {formatCurrency(getTotals().gross)}
                  </p>
                  <p className="text-sm text-gray-500">Gross Value</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-oswald font-semibold text-tre-teal">
                    {formatCurrency(getTotals().net)}
                  </p>
                  <p className="text-sm text-gray-500">Net Revenue</p>
                </div>
              </div>

              {/* Statements List */}
              {activeJob.result.statements && activeJob.result.statements.length > 0 && (
                <div className="p-6 border-b border-gray-100">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-medium text-gray-900 flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      Statements ({activeJob.result.statements.length})
                    </h4>
                    <div className="relative" ref={columnPickerRef}>
                      <button
                        onClick={() => setShowColumnPicker(!showColumnPicker)}
                        className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
                      >
                        <Columns className="w-4 h-4" />
                        Columns
                      </button>
                      {showColumnPicker && (
                        <div className="absolute right-0 mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-2">
                          {COLUMNS.filter((c) => !c.alwaysVisible).map((col) => (
                            <label key={col.key} className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-gray-50 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={visibleColumns.has(col.key)}
                                onChange={() => toggleColumn(col.key)}
                                className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                              />
                              {col.label}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="space-y-2">
                    {activeJob.result.statements.map((statement, idx) => (
                      <div key={idx} className="border border-gray-200 rounded-lg overflow-hidden">
                        <button
                          onClick={() => setExpandedStatement(expandedStatement === idx ? null : idx)}
                          className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
                        >
                          <div className="flex items-center gap-4 text-sm">
                            {expandedStatement === idx ? (
                              <ChevronDown className="w-4 h-4 text-gray-500" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-gray-500" />
                            )}
                            <span className="font-medium text-gray-900">{statement.filename}</span>
                            <span className="text-gray-500">|</span>
                            <span className="text-gray-600">{statement.format}</span>
                            {statement.payor && (
                              <>
                                <span className="text-gray-500">|</span>
                                <span className="text-gray-600">{statement.payor}</span>
                              </>
                            )}
                            {statement.check_number && (
                              <>
                                <span className="text-gray-500">|</span>
                                <span className="text-gray-600">Check #{statement.check_number}</span>
                              </>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-sm">
                            <span className="text-gray-600">{statement.rows.length} rows</span>
                            {statement.errors.length > 0 ? (
                              <span className="text-yellow-600 flex items-center gap-1">
                                <AlertCircle className="w-4 h-4" />
                                {statement.errors.length} warnings
                              </span>
                            ) : (
                              <span className="text-green-600 flex items-center gap-1">
                                <CheckCircle className="w-4 h-4" />
                                Success
                              </span>
                            )}
                          </div>
                        </button>

                        {expandedStatement === idx && (
                          <div className="p-4 bg-white">
                            <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-4 pb-3 border-b border-gray-100">
                              {statement.check_date && (
                                <span><strong>Check Date:</strong> {statement.check_date}</span>
                              )}
                              {statement.check_amount && (
                                <span><strong>Check Amount:</strong> {formatCurrency(statement.check_amount)}</span>
                              )}
                              {statement.owner_name && (
                                <span><strong>Owner:</strong> {statement.owner_name}</span>
                              )}
                            </div>

                            <div className="overflow-x-auto overflow-y-auto max-h-[60vh]">
                              <table className="w-full text-sm">
                                <thead className="sticky top-0 bg-white z-10">
                                  <tr className="border-b border-gray-200">
                                    {isColVisible('property_name') && <th className="text-left py-2 px-2 font-medium text-gray-600">Property</th>}
                                    {isColVisible('sales_date') && <th className="text-left py-2 px-2 font-medium text-gray-600">Date</th>}
                                    {isColVisible('product') && <th className="text-left py-2 px-2 font-medium text-gray-600">Product</th>}
                                    {isColVisible('interest') && <th className="text-right py-2 px-2 font-medium text-gray-600">Interest</th>}
                                    {isColVisible('volume') && <th className="text-right py-2 px-2 font-medium text-gray-600">Volume</th>}
                                    {isColVisible('gross') && <th className="text-right py-2 px-2 font-medium text-gray-600">Gross</th>}
                                    {isColVisible('tax') && <th className="text-right py-2 px-2 font-medium text-gray-600">Tax</th>}
                                    {isColVisible('net') && <th className="text-right py-2 px-2 font-medium text-gray-600">Net</th>}
                                    <th className="text-left py-2 px-2 font-medium text-gray-600 w-8"></th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100">
                                  {statement.rows.map((row, rowIdx) => (
                                    <tr key={rowIdx}>
                                      {isColVisible('property_name') && <td className="py-2 px-2 text-gray-900 text-xs">{row.property_name || '\u2014'}</td>}
                                      {isColVisible('sales_date') && <td className="py-2 px-2 text-gray-600 text-xs">{row.sales_date || '\u2014'}</td>}
                                      {isColVisible('product') && (
                                        <td className="py-2 px-2 text-gray-600 text-xs">
                                          {row.product_description || row.product_code || '\u2014'}
                                        </td>
                                      )}
                                      {isColVisible('interest') && (
                                        <td className="py-2 px-2 text-gray-600 text-right text-xs">
                                          {row.decimal_interest ? `${(row.decimal_interest * 100).toFixed(6)}%` : '\u2014'}
                                        </td>
                                      )}
                                      {isColVisible('volume') && (
                                        <td className="py-2 px-2 text-gray-600 text-right text-xs">
                                          {row.owner_volume?.toFixed(2) || '\u2014'}
                                        </td>
                                      )}
                                      {isColVisible('gross') && (
                                        <td className="py-2 px-2 text-gray-600 text-right text-xs">
                                          {formatCurrency(row.owner_value)}
                                        </td>
                                      )}
                                      {isColVisible('tax') && (
                                        <td className="py-2 px-2 text-red-600 text-right text-xs">
                                          {row.owner_tax_amount ? `-${formatCurrency(row.owner_tax_amount)}` : '\u2014'}
                                        </td>
                                      )}
                                      {isColVisible('net') && (
                                        <td className="py-2 px-2 text-green-600 font-medium text-right text-xs">
                                          {formatCurrency(row.owner_net_revenue)}
                                        </td>
                                      )}
                                      <td className="py-2 px-2">
                                        <button
                                          onClick={() => handleEditRow(idx, rowIdx, row)}
                                          className="text-gray-400 hover:text-tre-teal"
                                          title="Edit row"
                                        >
                                          <Edit2 className="w-3.5 h-3.5" />
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>

                            {statement.errors.length > 0 && (
                              <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                                <p className="text-sm font-medium text-yellow-800 mb-1">Warnings:</p>
                                <ul className="text-xs text-yellow-700 list-disc list-inside">
                                  {statement.errors.map((err, errIdx) => (
                                    <li key={errIdx}>{err}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Summary Totals */}
              <div className="p-6">
                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                  <DollarSign className="w-4 h-4" />
                  Financial Summary
                </h4>
                <div className="grid grid-cols-4 gap-4">
                  <div className="p-3 bg-gray-50 rounded-lg text-center">
                    <p className="text-lg font-oswald font-semibold text-gray-900">
                      {formatCurrency(getTotals().gross)}
                    </p>
                    <p className="text-xs text-gray-500">Gross Value</p>
                  </div>
                  <div className="p-3 bg-red-50 rounded-lg text-center">
                    <p className="text-lg font-oswald font-semibold text-red-600">
                      -{formatCurrency(getTotals().tax)}
                    </p>
                    <p className="text-xs text-gray-500">Taxes</p>
                  </div>
                  <div className="p-3 bg-orange-50 rounded-lg text-center">
                    <p className="text-lg font-oswald font-semibold text-orange-600">
                      -{formatCurrency(getTotals().deductions)}
                    </p>
                    <p className="text-xs text-gray-500">Deductions</p>
                  </div>
                  <div className="p-3 bg-green-50 rounded-lg text-center">
                    <p className="text-lg font-oswald font-semibold text-green-600">
                      {formatCurrency(getTotals().net)}
                    </p>
                    <p className="text-xs text-gray-500">Net Revenue</p>
                  </div>
                </div>
              </div>
            </div>
          ) : activeJob?.result?.errors?.length ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-400" />
              <h3 className="font-medium text-gray-900 mb-1">Processing Failed</h3>
              <p className="text-sm text-gray-500">{activeJob.result.errors.join(', ')}</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500">
              <DollarSign className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="font-medium">No job selected</p>
              <p className="text-sm mt-1">Upload PDFs or select a job from the history</p>
            </div>
          )}
        </div>
      </div>

      {/* Edit Row Modal */}
      <Modal
        isOpen={!!editingRow}
        onClose={() => setEditingRow(null)}
        title="Edit Revenue Row"
        size="lg"
        footer={
          <>
            <button
              onClick={() => setEditingRow(null)}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveEditRow}
              className="px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors"
            >
              Save Changes
            </button>
          </>
        }
      >
        {editingRow && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property Name</label>
                <input
                  type="text"
                  value={editingRow.row.property_name || ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, property_name: e.target.value } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property Number</label>
                <input
                  type="text"
                  value={editingRow.row.property_number || ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, property_number: e.target.value } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Sales Date</label>
                <input
                  type="text"
                  value={editingRow.row.sales_date || ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, sales_date: e.target.value } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Product Code</label>
                <input
                  type="text"
                  value={editingRow.row.product_code || ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, product_code: e.target.value } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Product Description</label>
                <input
                  type="text"
                  value={editingRow.row.product_description || ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, product_description: e.target.value } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Interest</label>
                <input
                  type="number"
                  step="any"
                  value={editingRow.row.decimal_interest ?? ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, decimal_interest: e.target.value ? Number(e.target.value) : undefined } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Volume</label>
                <input
                  type="number"
                  step="any"
                  value={editingRow.row.owner_volume ?? ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, owner_volume: e.target.value ? Number(e.target.value) : undefined } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Gross</label>
                <input
                  type="number"
                  step="any"
                  value={editingRow.row.owner_value ?? ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, owner_value: e.target.value ? Number(e.target.value) : undefined } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tax</label>
                <input
                  type="number"
                  step="any"
                  value={editingRow.row.owner_tax_amount ?? ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, owner_tax_amount: e.target.value ? Number(e.target.value) : undefined } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Net</label>
                <input
                  type="number"
                  step="any"
                  value={editingRow.row.owner_net_revenue ?? ''}
                  onChange={(e) => setEditingRow({ ...editingRow, row: { ...editingRow.row, owner_net_revenue: e.target.value ? Number(e.target.value) : undefined } })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
