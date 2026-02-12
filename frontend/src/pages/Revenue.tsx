import { useState, useMemo, useEffect, useRef } from 'react'
import { DollarSign, Download, Upload, AlertCircle, CheckCircle, Columns, Sparkles, X, PanelLeftClose, PanelLeftOpen, Edit2, Bug, ChevronDown, ChevronRight, RotateCcw, Filter } from 'lucide-react'
import { FileUpload, Modal, AiReviewPanel } from '../components'
import { aiApi } from '../utils/api'
import type { AiSuggestion } from '../utils/api'
import { useAuth } from '../contexts/AuthContext'
import { useToolLayout } from '../hooks/useToolLayout'

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

interface DebugGarbledAnalysis {
  garbled: boolean
  score: number
  indicators: string[]
}

interface DebugExtractorResult {
  success: boolean
  char_count: number
  text: string
  garbled_analysis?: DebugGarbledAnalysis
  error?: string
}

interface DebugFontInfo {
  page: number
  xref: number
  ext: string
  type: string
  basefont: string
  name: string
  encoding: string | null
}

interface DebugResult {
  filename: string
  size_bytes: number
  pymupdf?: DebugExtractorResult
  pdfplumber?: DebugExtractorResult
  pdfplumber_tables?: { success: boolean; table_count: number; tables: unknown[] }
  structured?: unknown
  fonts?: DebugFontInfo[]
  detected_format?: string
  recommendation?: string
  error?: string
}

// A flattened row that includes statement-level fields
interface FlatRow {
  _id: string // unique key for selection
  _statementIdx: number
  _rowIdx: number
  // Statement-level
  payor?: string
  check_number?: string
  check_amount?: number
  check_date?: string
  operator_name?: string
  owner_name?: string
  owner_number?: string
  // Row-level
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

interface ColumnConfig {
  key: string
  label: string
  alwaysVisible?: boolean
}

const COLUMNS: ColumnConfig[] = [
  { key: 'checkbox', label: '', alwaysVisible: true },
  { key: 'payor', label: 'Payor' },
  { key: 'check_number', label: 'Check #' },
  { key: 'check_amount', label: 'Check Amt' },
  { key: 'check_date', label: 'Check Date' },
  { key: 'property_name', label: 'Property' },
  { key: 'property_number', label: 'Prop #' },
  { key: 'operator_name', label: 'Operator' },
  { key: 'owner_name', label: 'Owner' },
  { key: 'owner_number', label: 'Owner #' },
  { key: 'sales_date', label: 'Sales Date' },
  { key: 'product_code', label: 'Prod Code' },
  { key: 'product_description', label: 'Prod Desc' },
  { key: 'decimal_interest', label: 'Interest' },
  { key: 'interest_type', label: 'Int Type' },
  { key: 'avg_price', label: 'Avg Price' },
  { key: 'property_gross_volume', label: 'Prop Vol' },
  { key: 'property_gross_revenue', label: 'Prop Rev' },
  { key: 'owner_volume', label: 'Owner Vol' },
  { key: 'owner_value', label: 'Owner Val' },
  { key: 'owner_tax_amount', label: 'Tax' },
  { key: 'tax_type', label: 'Tax Type' },
  { key: 'owner_deduct_amount', label: 'Deductions' },
  { key: 'deduct_code', label: 'Deduct Code' },
  { key: 'owner_net_revenue', label: 'Net Revenue' },
  { key: 'edit', label: '', alwaysVisible: true },
]

const DEFAULT_VISIBLE = new Set([
  'checkbox', 'property_name', 'sales_date', 'product_code', 'decimal_interest',
  'owner_volume', 'owner_value', 'owner_tax_amount', 'owner_net_revenue', 'edit',
])

const STORAGE_KEY_PREFIX = 'revenue-visible-columns'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Revenue() {
  const { user, userName } = useAuth()
  const { panelCollapsed, togglePanel, activeStorageKey } = useToolLayout('revenue', user?.uid, STORAGE_KEY_PREFIX)
  const [jobs, setJobs] = useState<RevenueJob[]>([])
  const [activeJob, setActiveJob] = useState<RevenueJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isLoadingEntries, setIsLoadingEntries] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // AI Review state
  const [showAiReview, setShowAiReview] = useState(false)
  const [aiEnabled, setAiEnabled] = useState(false)

  // Row selection state (set of excluded row IDs)
  const [excludedRows, setExcludedRows] = useState<Set<string>>(new Set())

  // Edit modal state
  const [editingRow, setEditingRow] = useState<{ statementIdx: number; rowIdx: number; row: RevenueRow } | null>(null)

  // Debug panel state
  const [showDebug, setShowDebug] = useState(false)
  const [debugResult, setDebugResult] = useState<DebugResult | null>(null)
  const [debugLoading, setDebugLoading] = useState(false)

  // Filter state
  const [filterProduct, setFilterProduct] = useState<string>('')
  const [filterProperty, setFilterProperty] = useState<string>('')

  // Column visibility (persisted in localStorage per user, separate keys for narrow/wide)
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(activeStorageKey)
      if (saved) return new Set(JSON.parse(saved))
    } catch { /* use defaults */ }
    return new Set(DEFAULT_VISIBLE)
  })
  const [showColumnPicker, setShowColumnPicker] = useState(false)
  const columnPickerRef = useRef<HTMLDivElement>(null)

  // Reload column visibility when panel collapse state changes
  useEffect(() => {
    try {
      const saved = localStorage.getItem(activeStorageKey)
      if (saved) {
        setVisibleColumns(new Set(JSON.parse(saved)))
      } else {
        setVisibleColumns(new Set(DEFAULT_VISIBLE))
      }
    } catch {
      setVisibleColumns(new Set(DEFAULT_VISIBLE))
    }
  }, [activeStorageKey])

  // Persist column visibility to localStorage
  useEffect(() => {
    localStorage.setItem(activeStorageKey, JSON.stringify([...visibleColumns]))
  }, [visibleColumns, activeStorageKey])

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

  // Check AI status on mount
  useEffect(() => {
    aiApi.getStatus().then(res => {
      if (res.data?.enabled) setAiEnabled(true)
    })
  }, [])

  // Flatten all statements into a single row list
  const flatRows = useMemo((): FlatRow[] => {
    if (!activeJob?.result?.statements) return []
    const rows: FlatRow[] = []
    activeJob.result.statements.forEach((stmt, si) => {
      stmt.rows.forEach((row, ri) => {
        rows.push({
          _id: `${si}-${ri}`,
          _statementIdx: si,
          _rowIdx: ri,
          payor: stmt.payor,
          check_number: stmt.check_number,
          check_amount: stmt.check_amount,
          check_date: stmt.check_date,
          operator_name: stmt.operator_name,
          owner_name: stmt.owner_name,
          owner_number: stmt.owner_number,
          ...row,
        })
      })
    })
    return rows
  }, [activeJob?.result?.statements])

  // Apply filters
  const filteredRows = useMemo(() => {
    return flatRows.filter((row) => {
      if (filterProduct && row.product_code !== filterProduct) return false
      if (filterProperty && !(row.property_name || '').toLowerCase().includes(filterProperty.toLowerCase())) return false
      return true
    })
  }, [flatRows, filterProduct, filterProperty])

  // Rows selected for export
  const rowsToExport = useMemo(() => {
    return filteredRows.filter((r) => !excludedRows.has(r._id))
  }, [filteredRows, excludedRows])

  // Unique product codes for filter dropdown
  const productCodes = useMemo(() => {
    const codes = new Set<string>()
    flatRows.forEach((r) => { if (r.product_code) codes.add(r.product_code) })
    return Array.from(codes).sort()
  }, [flatRows])

  // Selection helpers
  const isAllSelected = filteredRows.length > 0 &&
    filteredRows.every((r) => !excludedRows.has(r._id))
  const isSomeSelected = filteredRows.some((r) => !excludedRows.has(r._id)) && !isAllSelected

  const toggleSelectAll = () => {
    if (isAllSelected) {
      setExcludedRows(new Set(filteredRows.map((r) => r._id)))
    } else {
      const newExcluded = new Set(excludedRows)
      filteredRows.forEach((r) => newExcluded.delete(r._id))
      setExcludedRows(newExcluded)
    }
  }

  const toggleRow = (id: string) => {
    const next = new Set(excludedRows)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setExcludedRows(next)
  }

  const resetFilters = () => {
    setFilterProduct('')
    setFilterProperty('')
    setExcludedRows(new Set())
  }

  const handleApplySuggestions = (accepted: AiSuggestion[]) => {
    if (!activeJob?.result?.statements) return

    const updatedStatements = [...activeJob.result.statements]
    let flatIdx = 0
    for (let si = 0; si < updatedStatements.length; si++) {
      const stmt = { ...updatedStatements[si] }
      const updatedRows = [...stmt.rows]
      for (let ri = 0; ri < updatedRows.length; ri++) {
        const matching = accepted.filter(s => s.entry_index === flatIdx)
        if (matching.length > 0) {
          const row = { ...updatedRows[ri] }
          for (const suggestion of matching) {
            if (suggestion.field in row) {
              (row as Record<string, unknown>)[suggestion.field] = suggestion.suggested_value
            }
          }
          updatedRows[ri] = row
        }
        flatIdx++
      }
      stmt.rows = updatedRows
      updatedStatements[si] = stmt
    }

    setActiveJob({
      ...activeJob,
      result: {
        ...activeJob.result,
        statements: updatedStatements,
      },
    })
    setShowAiReview(false)
  }

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
      newJob.result = data
      newJob.job_id = data.job_id

      setJobs((prev) => [newJob, ...prev])
      setActiveJob(newJob)
      setExcludedRows(new Set())
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

    // Build filtered statements with only selected rows
    const selectedIds = new Set(rowsToExport.map((r) => r._id))
    const filteredStatements = activeJob.result.statements.map((stmt, si) => ({
      ...stmt,
      rows: stmt.rows.filter((_row, ri) => selectedIds.has(`${si}-${ri}`)),
    })).filter((stmt) => stmt.rows.length > 0)

    if (filteredStatements.length === 0) {
      setError('No rows selected for export')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/revenue/export/csv`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          statements: filteredStatements,
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
    setExcludedRows(new Set())

    if (!job.result && job.job_id) {
      setIsLoadingEntries(true)
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
      } finally {
        setIsLoadingEntries(false)
      }
    }
  }

  const handleDeleteJob = async (e: React.MouseEvent, job: RevenueJob) => {
    e.stopPropagation()
    if (!job.job_id) {
      setJobs((prev) => prev.filter((j) => j.id !== job.id))
      if (activeJob?.id === job.id) setActiveJob(null)
      return
    }
    try {
      await fetch(`${API_BASE}/history/jobs/${job.job_id}`, { method: 'DELETE' })
    } catch { /* best-effort */ }
    setJobs((prev) => prev.filter((j) => j.id !== job.id))
    if (activeJob?.id === job.id) setActiveJob(null)
  }

  const handleDebugUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setDebugLoading(true)
    setDebugResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch(`${API_BASE}/revenue/debug/extract-text`, {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      setDebugResult(data)
    } catch (err) {
      setDebugResult({ filename: '', size_bytes: 0, error: err instanceof Error ? err.message : 'Debug request failed' })
    } finally {
      setDebugLoading(false)
      e.target.value = ''
    }
  }

  const toNum = (v: unknown): number | undefined => {
    if (v === undefined || v === null) return undefined
    const n = Number(v)
    return isNaN(n) ? undefined : n
  }

  const formatCurrency = (amount?: unknown): string => {
    const n = toNum(amount)
    if (n === undefined) return '\u2014'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(n)
  }

  const getTotals = () => {
    const rows = rowsToExport
    return {
      gross: rows.reduce((sum, r) => sum + (toNum(r.owner_value) || 0), 0),
      tax: rows.reduce((sum, r) => sum + (toNum(r.owner_tax_amount) || 0), 0),
      deductions: rows.reduce((sum, r) => sum + (toNum(r.owner_deduct_amount) || 0), 0),
      net: rows.reduce((sum, r) => sum + (toNum(r.owner_net_revenue) || 0), 0),
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

  const getAllRows = (): RevenueRow[] => {
    if (!activeJob?.result?.statements) return []
    return activeJob.result.statements.flatMap(s => s.rows)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-amber-100 rounded-lg">
          <DollarSign className="w-6 h-6 text-amber-600" />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Revenue
          </h1>
          <p className="text-gray-500 text-sm">
            Extract revenue statements from EnergyLink and Energy Transfer PDFs
          </p>
        </div>
        <button
          onClick={togglePanel}
          className="hidden lg:flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-tre-navy border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          title={panelCollapsed ? 'Show side panel' : 'Hide side panel'}
        >
          {panelCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          {panelCollapsed ? 'Show Panel' : 'Hide Panel'}
        </button>
      </div>

      {/* Upload Section - compact row when panel collapsed */}
      {panelCollapsed && (
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
      )}

      <div className={`grid grid-cols-1 ${panelCollapsed ? '' : 'lg:grid-cols-3'} gap-6`}>
        {/* Left Column - Upload and History */}
        {!panelCollapsed && (
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
                    className={`group w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
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
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {job.result?.success ? (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        ) : job.result?.errors?.length ? (
                          <AlertCircle className="w-4 h-4 text-red-500" />
                        ) : null}
                        <span
                          role="button"
                          onClick={(e) => handleDeleteJob(e, job)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500 transition-all"
                          title="Delete job"
                        >
                          <X className="w-4 h-4" />
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        )}

        {/* Right Column - Results */}
        <div className={panelCollapsed ? '' : 'lg:col-span-2'}>
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          )}

          {isLoadingEntries ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-tre-teal mx-auto mb-3"></div>
              <p className="font-medium">Loading results...</p>
            </div>
          ) : activeJob?.result?.success ? (
            <>
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
                  <div className="flex gap-2">
                    {aiEnabled && (
                      <button
                        onClick={() => setShowAiReview(!showAiReview)}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors text-sm ${
                          showAiReview
                            ? 'bg-purple-100 text-purple-700 border border-purple-300'
                            : 'border border-gray-300 text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        <Sparkles className="w-4 h-4" />
                        AI Review
                      </button>
                    )}
                    <button
                      onClick={handleExport}
                      disabled={rowsToExport.length === 0}
                      className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm disabled:opacity-50"
                    >
                      <Download className="w-4 h-4" />
                      Mineral
                    </button>
                  </div>
                </div>
              </div>

              {/* Filter Controls */}
              <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex items-center gap-2 text-gray-600">
                    <Filter className="w-4 h-4" />
                    <span className="text-sm font-medium">Filters:</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-600">Product:</span>
                    <select
                      value={filterProduct}
                      onChange={(e) => setFilterProduct(e.target.value)}
                      className="text-sm border border-gray-300 rounded px-2 py-1 focus:ring-tre-teal focus:border-tre-teal"
                    >
                      <option value="">All Products</option>
                      {productCodes.map((code) => (
                        <option key={code} value={code}>{code}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-600">Property:</span>
                    <input
                      type="text"
                      placeholder="Search..."
                      value={filterProperty}
                      onChange={(e) => setFilterProperty(e.target.value)}
                      className="w-36 text-sm border border-gray-300 rounded px-2 py-1 focus:ring-tre-teal focus:border-tre-teal"
                    />
                  </div>
                  <button
                    onClick={resetFilters}
                    className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Reset
                  </button>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  Showing {filteredRows.length} of {flatRows.length} rows
                  ({rowsToExport.length} selected for export)
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-4 gap-4 p-6 border-b border-gray-100">
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {rowsToExport.length}
                  </p>
                  <p className="text-sm text-gray-500">Selected Rows</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-oswald font-semibold text-green-600">
                    {formatCurrency(getTotals().gross)}
                  </p>
                  <p className="text-sm text-gray-500">Gross Value</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-oswald font-semibold text-red-600">
                    -{formatCurrency(Math.abs(getTotals().tax))}
                  </p>
                  <p className="text-sm text-gray-500">Taxes</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-oswald font-semibold text-tre-teal">
                    {formatCurrency(getTotals().net)}
                  </p>
                  <p className="text-sm text-gray-500">Net Revenue</p>
                </div>
              </div>

              {/* Data Table */}
              <div className="p-6">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900 flex items-center gap-2">
                    <DollarSign className="w-4 h-4" />
                    Revenue Rows
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
                <div className="overflow-x-auto overflow-y-auto max-h-[60vh]">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-white z-10">
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-2 px-2 font-medium text-gray-600 w-10">
                          <input
                            type="checkbox"
                            checked={isAllSelected}
                            ref={(el) => {
                              if (el) el.indeterminate = isSomeSelected
                            }}
                            onChange={toggleSelectAll}
                            className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                          />
                        </th>
                        {isColVisible('payor') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Payor</th>}
                        {isColVisible('check_number') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Check #</th>}
                        {isColVisible('check_amount') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Check Amt</th>}
                        {isColVisible('check_date') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Check Date</th>}
                        {isColVisible('property_name') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Property</th>}
                        {isColVisible('property_number') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Prop #</th>}
                        {isColVisible('operator_name') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Operator</th>}
                        {isColVisible('owner_name') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Owner</th>}
                        {isColVisible('owner_number') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Owner #</th>}
                        {isColVisible('sales_date') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Sales Date</th>}
                        {isColVisible('product_code') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Prod Code</th>}
                        {isColVisible('product_description') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Prod Desc</th>}
                        {isColVisible('decimal_interest') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Interest</th>}
                        {isColVisible('interest_type') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Int Type</th>}
                        {isColVisible('avg_price') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Avg Price</th>}
                        {isColVisible('property_gross_volume') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Prop Vol</th>}
                        {isColVisible('property_gross_revenue') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Prop Rev</th>}
                        {isColVisible('owner_volume') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Owner Vol</th>}
                        {isColVisible('owner_value') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Owner Val</th>}
                        {isColVisible('owner_tax_amount') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Tax</th>}
                        {isColVisible('tax_type') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Tax Type</th>}
                        {isColVisible('owner_deduct_amount') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Deductions</th>}
                        {isColVisible('deduct_code') && <th className="text-left py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Deduct Code</th>}
                        {isColVisible('owner_net_revenue') && <th className="text-right py-2 px-2 font-medium text-gray-600 whitespace-nowrap">Net Revenue</th>}
                        <th className="text-left py-2 px-2 font-medium text-gray-600 w-8"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {filteredRows.map((row) => {
                        const isExcluded = excludedRows.has(row._id)
                        return (
                          <tr
                            key={row._id}
                            className={isExcluded ? 'opacity-50 bg-gray-100' : ''}
                          >
                            <td className="py-2 px-2">
                              <input
                                type="checkbox"
                                checked={!isExcluded}
                                onChange={() => toggleRow(row._id)}
                                className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                              />
                            </td>
                            {isColVisible('payor') && <td className="py-2 px-2 text-gray-600 text-xs whitespace-nowrap">{row.payor || '\u2014'}</td>}
                            {isColVisible('check_number') && <td className="py-2 px-2 text-gray-600 text-xs">{row.check_number || '\u2014'}</td>}
                            {isColVisible('check_amount') && <td className="py-2 px-2 text-gray-600 text-right text-xs">{formatCurrency(row.check_amount)}</td>}
                            {isColVisible('check_date') && <td className="py-2 px-2 text-gray-600 text-xs">{row.check_date || '\u2014'}</td>}
                            {isColVisible('property_name') && <td className="py-2 px-2 text-gray-900 text-xs whitespace-nowrap">{row.property_name || '\u2014'}</td>}
                            {isColVisible('property_number') && <td className="py-2 px-2 text-gray-600 text-xs">{row.property_number || '\u2014'}</td>}
                            {isColVisible('operator_name') && <td className="py-2 px-2 text-gray-600 text-xs whitespace-nowrap">{row.operator_name || '\u2014'}</td>}
                            {isColVisible('owner_name') && <td className="py-2 px-2 text-gray-600 text-xs whitespace-nowrap">{row.owner_name || '\u2014'}</td>}
                            {isColVisible('owner_number') && <td className="py-2 px-2 text-gray-600 text-xs">{row.owner_number || '\u2014'}</td>}
                            {isColVisible('sales_date') && <td className="py-2 px-2 text-gray-600 text-xs">{row.sales_date || '\u2014'}</td>}
                            {isColVisible('product_code') && <td className="py-2 px-2 text-gray-600 text-xs">{row.product_code || '\u2014'}</td>}
                            {isColVisible('product_description') && <td className="py-2 px-2 text-gray-600 text-xs">{row.product_description || '\u2014'}</td>}
                            {isColVisible('decimal_interest') && (
                              <td className="py-2 px-2 text-gray-600 text-right text-xs">
                                {toNum(row.decimal_interest) !== undefined ? `${(toNum(row.decimal_interest)! * 100).toFixed(6)}%` : '\u2014'}
                              </td>
                            )}
                            {isColVisible('interest_type') && <td className="py-2 px-2 text-gray-600 text-xs">{row.interest_type || '\u2014'}</td>}
                            {isColVisible('avg_price') && <td className="py-2 px-2 text-gray-600 text-right text-xs">{formatCurrency(row.avg_price)}</td>}
                            {isColVisible('property_gross_volume') && <td className="py-2 px-2 text-gray-600 text-right text-xs">{toNum(row.property_gross_volume)?.toFixed(2) ?? '\u2014'}</td>}
                            {isColVisible('property_gross_revenue') && <td className="py-2 px-2 text-gray-600 text-right text-xs">{formatCurrency(row.property_gross_revenue)}</td>}
                            {isColVisible('owner_volume') && <td className="py-2 px-2 text-gray-600 text-right text-xs">{toNum(row.owner_volume)?.toFixed(2) ?? '\u2014'}</td>}
                            {isColVisible('owner_value') && <td className="py-2 px-2 text-gray-600 text-right text-xs">{formatCurrency(row.owner_value)}</td>}
                            {isColVisible('owner_tax_amount') && (
                              <td className="py-2 px-2 text-red-600 text-right text-xs">
                                {toNum(row.owner_tax_amount) !== undefined ? `-${formatCurrency(Math.abs(toNum(row.owner_tax_amount)!))}` : '\u2014'}
                              </td>
                            )}
                            {isColVisible('tax_type') && <td className="py-2 px-2 text-gray-600 text-xs">{row.tax_type || '\u2014'}</td>}
                            {isColVisible('owner_deduct_amount') && (
                              <td className="py-2 px-2 text-orange-600 text-right text-xs">
                                {toNum(row.owner_deduct_amount) !== undefined ? `-${formatCurrency(Math.abs(toNum(row.owner_deduct_amount)!))}` : '\u2014'}
                              </td>
                            )}
                            {isColVisible('deduct_code') && <td className="py-2 px-2 text-gray-600 text-xs">{row.deduct_code || '\u2014'}</td>}
                            {isColVisible('owner_net_revenue') && (
                              <td className="py-2 px-2 text-green-600 font-medium text-right text-xs">
                                {formatCurrency(row.owner_net_revenue)}
                              </td>
                            )}
                            <td className="py-2 px-2">
                              <button
                                onClick={() => handleEditRow(row._statementIdx, row._rowIdx, {
                                  property_name: row.property_name,
                                  property_number: row.property_number,
                                  sales_date: row.sales_date,
                                  product_code: row.product_code,
                                  product_description: row.product_description,
                                  decimal_interest: row.decimal_interest,
                                  interest_type: row.interest_type,
                                  avg_price: row.avg_price,
                                  property_gross_volume: row.property_gross_volume,
                                  property_gross_revenue: row.property_gross_revenue,
                                  owner_volume: row.owner_volume,
                                  owner_value: row.owner_value,
                                  owner_tax_amount: row.owner_tax_amount,
                                  tax_type: row.tax_type,
                                  owner_deduct_amount: row.owner_deduct_amount,
                                  deduct_code: row.deduct_code,
                                  owner_net_revenue: row.owner_net_revenue,
                                })}
                                className="text-gray-400 hover:text-tre-teal"
                                title="Edit row"
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* AI Review Panel */}
            {showAiReview && activeJob?.result?.statements && (
              <AiReviewPanel
                tool="revenue"
                entries={getAllRows()}
                onApplySuggestions={handleApplySuggestions}
                onClose={() => setShowAiReview(false)}
              />
            )}
            </>
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

      {/* Recent Jobs - shown at bottom when panel collapsed */}
      {panelCollapsed && (
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
            <div className="divide-y divide-gray-100 max-h-60 overflow-y-auto">
              {jobs.map((job) => (
                <button
                  key={job.id}
                  onClick={() => handleSelectJob(job)}
                  className={`group w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
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
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {job.result?.success ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : job.result?.errors?.length ? (
                        <AlertCircle className="w-4 h-4 text-red-500" />
                      ) : null}
                      <span
                        role="button"
                        onClick={(e) => handleDeleteJob(e, job)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500 transition-all"
                        title="Delete job"
                      >
                        <X className="w-4 h-4" />
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Debug Extraction Panel */}
      <div className="bg-white rounded-xl border border-gray-200">
        <button
          onClick={() => setShowDebug(!showDebug)}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-2 text-sm font-medium text-gray-600">
            <Bug className="w-4 h-4" />
            Debug PDF Extraction
          </div>
          {showDebug ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
        </button>
        {showDebug && (
          <div className="px-4 pb-4 space-y-4">
            <p className="text-xs text-gray-500">
              Upload a PDF to see raw extracted text from each extraction method. Helps diagnose font encoding issues.
            </p>
            <div className="flex items-center gap-3">
              <label className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm cursor-pointer">
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleDebugUpload}
                  className="hidden"
                />
                Choose PDF
              </label>
              {debugLoading && (
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-tre-teal"></div>
                  Analyzing...
                </div>
              )}
            </div>
            {debugResult && (
              <div className="space-y-3">
                {debugResult.recommendation && (
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                    {debugResult.recommendation}
                  </div>
                )}

                {([
                  { data: debugResult.pymupdf, label: 'PyMuPDF' },
                  { data: debugResult.pdfplumber, label: 'pdfplumber' },
                ] as const).map(({ data, label }) => {
                  if (!data) return null
                  const garbled = data.garbled_analysis
                  return (
                    <div key={label} className="border border-gray-200 rounded-lg overflow-hidden">
                      <div className="px-3 py-2 bg-gray-50 flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-700">{label}</span>
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-gray-500">{data.char_count} chars</span>
                          {garbled && (
                            <span className={`px-2 py-0.5 rounded-full ${
                              garbled.garbled ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                            }`}>
                              {garbled.garbled ? `Garbled (score: ${garbled.score})` : 'Clean'}
                            </span>
                          )}
                        </div>
                      </div>
                      {garbled && garbled.indicators.length > 0 && (
                        <div className="px-3 py-2 bg-yellow-50 border-b border-gray-200">
                          <ul className="text-xs text-yellow-800 space-y-0.5">
                            {garbled.indicators.map((ind, i) => (
                              <li key={i}>{ind}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <pre className="px-3 py-2 text-xs text-gray-700 max-h-60 overflow-auto whitespace-pre-wrap font-mono bg-gray-50/50">
                        {data.text?.substring(0, 3000) || 'No text extracted'}
                        {data.text?.length > 3000 && '\n... (truncated)'}
                      </pre>
                    </div>
                  )
                })}

                {debugResult.pdfplumber_tables && (
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <div className="px-3 py-2 bg-gray-50">
                      <span className="text-sm font-medium text-gray-700">
                        pdfplumber Tables ({debugResult.pdfplumber_tables.table_count} found)
                      </span>
                    </div>
                    <pre className="px-3 py-2 text-xs text-gray-700 max-h-60 overflow-auto whitespace-pre-wrap font-mono bg-gray-50/50">
                      {JSON.stringify(debugResult.pdfplumber_tables.tables, null, 2)?.substring(0, 3000) || 'No tables'}
                    </pre>
                  </div>
                )}

                {debugResult.fonts && debugResult.fonts.length > 0 && (
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <div className="px-3 py-2 bg-gray-50">
                      <span className="text-sm font-medium text-gray-700">
                        Fonts ({debugResult.fonts.length})
                      </span>
                    </div>
                    <div className="px-3 py-2 text-xs">
                      <table className="w-full">
                        <thead>
                          <tr className="text-left text-gray-500">
                            <th className="pb-1">Name</th>
                            <th className="pb-1">Type</th>
                            <th className="pb-1">Base Font</th>
                            <th className="pb-1">Encoding</th>
                          </tr>
                        </thead>
                        <tbody className="text-gray-700">
                          {debugResult.fonts.map((f, i) => (
                            <tr key={i}>
                              <td className="py-0.5">{f.name}</td>
                              <td className="py-0.5">{f.type}</td>
                              <td className="py-0.5">{f.basefont}</td>
                              <td className="py-0.5">{f.encoding || '\u2014'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {debugResult.detected_format && (
                  <div className="text-sm text-gray-600">
                    Detected format: <span className="font-medium">{debugResult.detected_format}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
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
