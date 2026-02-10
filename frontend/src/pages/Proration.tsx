import { useState, useEffect, useRef } from 'react'
import { Calculator, Download, Upload, Users, AlertCircle, CheckCircle, AlertTriangle, Database, RefreshCw, Filter, Settings, Edit2, Columns, Sparkles, X, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { FileUpload, Modal, AiReviewPanel } from '../components'
import { aiApi } from '../utils/api'
import type { AiSuggestion } from '../utils/api'
import { useAuth } from '../contexts/AuthContext'
import { useToolLayout } from '../hooks/useToolLayout'

interface MineralHolderRow {
  county: string
  state?: string
  year?: number
  owner_id?: string
  owner: string
  interest: number
  interest_type?: string
  appraisal_value?: number
  legal_description?: string
  property_id?: string
  property?: string
  operator?: string
  raw_rrc?: string
  rrc_lease?: string
  new_record?: string
  estimated_monthly_revenue?: number
  district?: string
  lease_number?: string
  block?: string
  section?: string
  abstract?: string
  rrc_acres?: number
  est_nra?: number
  dollars_per_nra?: number
  notes?: string
  well_type?: string
}

interface ProcessingResult {
  success: boolean
  total_rows?: number
  filtered_rows?: number
  processed_rows?: number
  failed_rows?: number
  matched_rows?: number
  rows?: MineralHolderRow[]
  error_message?: string
  source_filename?: string
  job_id?: string
}

interface UploadResponse {
  message: string
  result?: ProcessingResult
}

interface ProrationJob {
  id: string
  job_id?: string
  documentName: string
  user: string
  timestamp: string
  result?: ProcessingResult
}

interface RRCDataStatus {
  oil_available: boolean
  gas_available: boolean
  oil_rows: number
  gas_rows: number
  oil_modified?: string
  gas_modified?: string
  db_oil_rows?: number
  db_gas_rows?: number
  db_available?: boolean
  last_sync?: {
    completed_at?: string
    new_records?: number
    updated_records?: number
  } | null
}

interface ColumnConfig {
  key: string
  label: string
  alwaysVisible?: boolean
}

const COLUMNS: ColumnConfig[] = [
  { key: 'owner', label: 'Owner' },
  { key: 'county', label: 'County' },
  { key: 'year', label: 'Year' },
  { key: 'interest', label: 'Interest' },
  { key: 'interest_type', label: 'Int Type' },
  { key: 'appraisal_value', label: 'Appraisal Value' },
  { key: 'legal_description', label: 'Legal Desc' },
  { key: 'property', label: 'Property' },
  { key: 'operator', label: 'Operator' },
  { key: 'raw_rrc', label: 'Raw RRC' },
  { key: 'new_record', label: 'New Record' },
  { key: 'block', label: 'Block' },
  { key: 'section', label: 'Section' },
  { key: 'abstract', label: 'Abstract' },
  { key: 'rrc_acres', label: 'RRC Acres' },
  { key: 'est_nra', label: 'Est NRA' },
  { key: 'dollars_per_nra', label: '$/NRA' },
  { key: 'estimated_monthly_revenue', label: 'Est Monthly Rev' },
  { key: 'well_type', label: 'Well Type' },
  { key: 'notes', label: 'Notes' },
  { key: 'edit', label: '', alwaysVisible: true },
]

const DEFAULT_PRORATION_VISIBLE = new Set([
  'owner', 'county', 'interest', 'rrc_acres', 'est_nra', 'dollars_per_nra', 'edit',
])

const STORAGE_KEY_PREFIX = 'proration-visible-columns'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Proration() {
  const { user } = useAuth()
  const { panelCollapsed, togglePanel, activeStorageKey } = useToolLayout('proration', user?.uid, STORAGE_KEY_PREFIX)
  const [jobs, setJobs] = useState<ProrationJob[]>([])
  const [activeJob, setActiveJob] = useState<ProrationJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isLoadingEntries, setIsLoadingEntries] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // RRC Data State (initialize from sessionStorage cache to avoid flash on navigation)
  const [rrcStatus, setRrcStatus] = useState<RRCDataStatus | null>(() => {
    try {
      const cached = sessionStorage.getItem('rrc-status-cache')
      if (cached) {
        const { data, ts } = JSON.parse(cached)
        // Use cache if less than 5 minutes old
        if (Date.now() - ts < 5 * 60 * 1000) return data
      }
    } catch { /* ignore */ }
    return null
  })
  const [rrcLoading, setRrcLoading] = useState(!rrcStatus)
  const [isDownloadingRRC, setIsDownloadingRRC] = useState(false)
  const [rrcMessage, setRrcMessage] = useState<string | null>(null)

  // Processing Options State
  const [showProcessingOptions, setShowProcessingOptions] = useState(false)
  const [newRecordOnly, setNewRecordOnly] = useState(false)
  const [deduplicateByPropertyId, setDeduplicateByPropertyId] = useState(false)
  const [minAppraisalValue, setMinAppraisalValue] = useState<number>(0)
  const [wellTypeOverride, setWellTypeOverride] = useState<string>('auto')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  // AI Review state
  const [showAiReview, setShowAiReview] = useState(false)
  const [aiEnabled, setAiEnabled] = useState(false)

  // Edit Row Modal State
  const [editingRow, setEditingRow] = useState<MineralHolderRow | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  // Column Visibility State (persisted in localStorage per user, separate keys for narrow/wide)
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(activeStorageKey)
      if (saved) return new Set(JSON.parse(saved))
    } catch { /* use defaults */ }
    return new Set(DEFAULT_PRORATION_VISIBLE)
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
        setVisibleColumns(new Set(DEFAULT_PRORATION_VISIBLE))
      }
    } catch {
      setVisibleColumns(new Set(DEFAULT_PRORATION_VISIBLE))
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
    if (showColumnPicker) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showColumnPicker])

  // Check RRC data status on mount (skip if cache is fresh)
  useEffect(() => {
    if (!rrcStatus) {
      checkRRCStatus()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Load recent jobs on mount
  useEffect(() => {
    const loadRecentJobs = async () => {
      try {
        const response = await fetch(`${API_BASE}/history/jobs?tool=proration&limit=20`)
        if (response.ok) {
          const data = await response.json()
          const loadedJobs: ProrationJob[] = (data.jobs || []).map((j: Record<string, unknown>) => ({
            id: j.id as string,
            job_id: j.id as string,
            documentName: (j.source_filename as string) || 'Unknown',
            user: (j.user_id as string) || 'System',
            timestamp: j.created_at
              ? new Date(j.created_at as string).toLocaleString()
              : '',
          }))
          setJobs(loadedJobs)
        }
      } catch (err) {
        console.error('Failed to load recent jobs:', err)
      }
    }
    loadRecentJobs()
  }, [])

  // Check AI status on mount
  useEffect(() => {
    aiApi.getStatus().then(res => {
      if (res.data?.enabled) setAiEnabled(true)
    })
  }, [])

  const handleApplySuggestions = (accepted: AiSuggestion[]) => {
    if (!activeJob?.result?.rows) return

    const updatedRows = [...activeJob.result.rows]
    for (const suggestion of accepted) {
      const row = updatedRows[suggestion.entry_index]
      if (row && suggestion.field in row) {
        (row as unknown as Record<string, unknown>)[suggestion.field] = suggestion.suggested_value
      }
    }

    setActiveJob({
      ...activeJob,
      result: {
        ...activeJob.result,
        rows: updatedRows,
      },
    })
    setShowAiReview(false)
  }

  const checkRRCStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/proration/rrc/status`)
      if (response.ok) {
        const data = await response.json()
        setRrcStatus(data)
        try {
          sessionStorage.setItem('rrc-status-cache', JSON.stringify({ data, ts: Date.now() }))
        } catch { /* ignore storage errors */ }
      }
    } catch (err) {
      console.error('Failed to check RRC status:', err)
    } finally {
      setRrcLoading(false)
    }
  }

  const handleDownloadRRC = async () => {
    setIsDownloadingRRC(true)
    setRrcMessage(null)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/proration/rrc/download`, {
        method: 'POST',
      })

      const data = await response.json()

      if (response.ok && data.success) {
        setRrcMessage(data.message || `Downloaded ${data.oil_rows?.toLocaleString() || 0} oil and ${data.gas_rows?.toLocaleString() || 0} gas records`)
        // Refresh status
        await checkRRCStatus()
      } else {
        setError(data.message || 'Failed to download RRC data')
      }
    } catch {
      setError('Failed to download RRC data. Please try again.')
    } finally {
      setIsDownloadingRRC(false)
    }
  }

  const handleFilesSelected = async (files: File[]) => {
    if (files.length === 0) return

    const file = files[0]
    setSelectedFile(file)
    setShowProcessingOptions(true)
    setError(null)
  }

  const processFile = async () => {
    if (!selectedFile) return

    setIsProcessing(true)
    setShowProcessingOptions(false)
    setError(null)

    const newJob: ProrationJob = {
      id: String(Date.now()),
      documentName: selectedFile.name,
      user: user?.displayName || user?.email || 'Unknown',
      timestamp: new Date().toLocaleString(),
    }

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('new_record_only', String(newRecordOnly))
      formData.append('deduplicate_by_property_id', String(deduplicateByPropertyId))
      formData.append('min_appraisal_value', String(minAppraisalValue))
      formData.append('well_type_override', wellTypeOverride)

      const response = await fetch(`${API_BASE}/proration/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data: UploadResponse = await response.json()
      newJob.result = data.result
      if (data.result?.job_id) {
        newJob.job_id = data.result.job_id
      }

      setJobs((prev) => [newJob, ...prev])
      setActiveJob(newJob)
      setSelectedFile(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process file')
      newJob.result = {
        success: false,
        error_message: err instanceof Error ? err.message : 'Failed to process file',
      }
      setJobs((prev) => [newJob, ...prev])
    } finally {
      setIsProcessing(false)
    }
  }

  const cancelProcessing = () => {
    setShowProcessingOptions(false)
    setSelectedFile(null)
  }

  const handleExport = async (format: 'csv' | 'excel' | 'pdf') => {
    if (!activeJob?.result?.rows) return

    try {
      const response = await fetch(`${API_BASE}/proration/export/${format}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rows: activeJob.result.rows,
          filename: activeJob.documentName.replace(/\.[^.]+$/, ''),
        }),
      })

      if (!response.ok) throw new Error('Export failed')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const ext = format === 'excel' ? 'xlsx' : format === 'pdf' ? 'pdf' : 'csv'
      a.download = `${activeJob.documentName.replace(/\.[^.]+$/, '')}_proration.${ext}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch {
      setError('Failed to export file')
    }
  }

  const handleSelectJob = async (job: ProrationJob) => {
    setActiveJob(job)
    setError(null)

    // Lazy-load entries if not already loaded
    if (!job.result?.rows && job.job_id) {
      setIsLoadingEntries(true)
      try {
        const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}/entries`)
        if (response.ok) {
          const data = await response.json()
          const updatedJob = {
            ...job,
            result: {
              ...job.result,
              success: true,
              rows: data.entries || data.rows || data,
            } as ProcessingResult,
          }
          setActiveJob(updatedJob)
          setJobs((prev) =>
            prev.map((j) => (j.id === job.id ? updatedJob : j))
          )
        }
      } catch (err) {
        console.error('Failed to load job entries:', err)
      } finally {
        setIsLoadingEntries(false)
      }
    }
  }

  const handleDeleteJob = async (e: React.MouseEvent, job: ProrationJob) => {
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

  const handleEditRow = (row: MineralHolderRow, index: number) => {
    setEditingRow({ ...row })
    setEditingIndex(index)
  }

  const handleSaveEdit = () => {
    if (editingRow === null || editingIndex === null || !activeJob?.result?.rows) return

    const updatedRows = [...activeJob.result.rows]
    updatedRows[editingIndex] = editingRow

    setActiveJob({
      ...activeJob,
      result: {
        ...activeJob.result,
        rows: updatedRows,
      },
    })

    setEditingRow(null)
    setEditingIndex(null)
  }

  const handleCancelEdit = () => {
    setEditingRow(null)
    setEditingIndex(null)
  }

  const isColumnVisible = (key: string): boolean => {
    const col = COLUMNS.find(c => c.key === key)
    if (col?.alwaysVisible) return true
    return visibleColumns.has(key)
  }

  const toggleColumn = (key: string) => {
    setVisibleColumns(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const formatCurrency = (amount?: number): string => {
    if (amount === undefined || amount === null) return '\u2014'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount)
  }

  const formatNumber = (num?: number, decimals: number = 4): string => {
    if (num === undefined || num === null) return '\u2014'
    return num.toFixed(decimals)
  }

  const formatDate = (isoString?: string): string => {
    if (!isoString) return 'Never'
    const date = new Date(isoString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  }

  const hasDBData = (rrcStatus?.db_oil_rows || 0) + (rrcStatus?.db_gas_rows || 0) > 0
  const hasCSVData = rrcStatus?.oil_available || rrcStatus?.gas_available
  const hasRRCData = hasDBData || hasCSVData

  // Use DB counts when available, fall back to CSV counts
  const totalRecords = hasDBData
    ? (rrcStatus?.db_oil_rows || 0) + (rrcStatus?.db_gas_rows || 0)
    : (rrcStatus?.oil_rows || 0) + (rrcStatus?.gas_rows || 0)
  const oilRecords = hasDBData ? (rrcStatus?.db_oil_rows || 0) : (rrcStatus?.oil_rows || 0)
  const gasRecords = hasDBData ? (rrcStatus?.db_gas_rows || 0) : (rrcStatus?.gas_rows || 0)

  // Check if monthly update is needed: last sync is before the 1st of the current month
  const isDataExpired = (): boolean => {
    const syncDate = rrcStatus?.last_sync?.completed_at || rrcStatus?.oil_modified
    if (!syncDate) return false
    const lastUpdated = new Date(syncDate)
    const firstOfMonth = new Date()
    firstOfMonth.setDate(1)
    firstOfMonth.setHours(0, 0, 0, 0)
    return lastUpdated < firstOfMonth
  }

  const dataExpired = hasRRCData && isDataExpired()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-purple-100 rounded-lg">
          <Calculator className="w-6 h-6 text-purple-600" />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Proration
          </h1>
          <p className="text-gray-500 text-sm">
            Calculate interest prorations and NRA allocations with RRC data
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

      {/* RRC Data Status Banner */}
      {rrcLoading ? (
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-gray-50 border border-gray-200">
          <div className="w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-gray-500">Checking RRC data status...</span>
        </div>
      ) : hasRRCData && !dataExpired ? (
        /* Compact green info line when data is loaded and current */
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-green-50 border border-green-200">
          <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
          <span className="text-sm text-green-800">
            <span className="font-medium">{totalRecords.toLocaleString()}</span> RRC records
            <span className="text-green-600 mx-1">({oilRecords.toLocaleString()} oil, {gasRecords.toLocaleString()} gas)</span>
            <span className="text-green-600/70">&bull; Synced {rrcStatus?.last_sync?.completed_at
              ? formatDate(rrcStatus.last_sync.completed_at)
              : rrcStatus?.oil_modified
                ? formatDate(rrcStatus.oil_modified)
                : 'Never'
            }</span>
          </span>
          {rrcMessage && (
            <span className="text-sm text-green-700 ml-auto flex items-center gap-1">
              <CheckCircle className="w-3.5 h-3.5" />
              {rrcMessage}
            </span>
          )}
        </div>
      ) : (
        /* Full banner when action is needed (no data or expired) */
        <div className={`rounded-xl border p-4 ${
          dataExpired ? 'bg-orange-50 border-orange-200' : 'bg-yellow-50 border-yellow-200'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Database className={`w-5 h-5 ${
                dataExpired ? 'text-orange-600' : 'text-yellow-600'
              }`} />
              <div>
                <h3 className={`font-medium ${
                  dataExpired ? 'text-orange-800' : 'text-yellow-800'
                }`}>
                  RRC Master Database
                  {dataExpired && (
                    <span className="ml-2 text-xs font-normal bg-orange-200 text-orange-800 px-2 py-0.5 rounded">
                      Monthly Update Available
                    </span>
                  )}
                </h3>
                {rrcStatus ? (
                  <div className="text-sm mt-1 space-y-0.5">
                    {hasRRCData ? (
                      <>
                        <div className="text-orange-700">
                          <span className="font-medium">{totalRecords.toLocaleString()}</span> records
                          ({oilRecords.toLocaleString()} oil, {gasRecords.toLocaleString()} gas)
                        </div>
                        <div className="text-gray-500 text-xs">
                          Last synced: {rrcStatus.last_sync?.completed_at
                            ? formatDate(rrcStatus.last_sync.completed_at)
                            : rrcStatus.oil_modified
                              ? formatDate(rrcStatus.oil_modified)
                              : 'Never'
                          }
                          {rrcStatus.last_sync?.new_records ? (
                            <span className="ml-2">&bull; {rrcStatus.last_sync.new_records.toLocaleString()} new, {(rrcStatus.last_sync.updated_records || 0).toLocaleString()} updated</span>
                          ) : null}
                        </div>
                      </>
                    ) : (
                      <div className="text-yellow-700">
                        No RRC data available. Download to build the master database.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">Checking status...</div>
                )}
              </div>
            </div>
            <button
              onClick={handleDownloadRRC}
              disabled={isDownloadingRRC}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors text-sm whitespace-nowrap ${
                dataExpired
                  ? 'bg-orange-600 text-white hover:bg-orange-700'
                  : 'bg-yellow-600 text-white hover:bg-yellow-700'
              } ${isDownloadingRRC ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <RefreshCw className={`w-4 h-4 ${isDownloadingRRC ? 'animate-spin' : ''}`} />
              {isDownloadingRRC ? 'Syncing...' : dataExpired ? 'Download & Sync' : 'Download & Build'}
            </button>
          </div>
          {rrcMessage && (
            <div className="mt-2 text-sm text-green-700 flex items-center gap-1">
              <CheckCircle className="w-4 h-4" />
              {rrcMessage}
            </div>
          )}
        </div>
      )}

      {/* Upload Section - compact row when panel collapsed */}
      {panelCollapsed && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          {!showProcessingOptions ? (
            <>
              <FileUpload
                onFilesSelected={handleFilesSelected}
                accept=".csv"
                label="Upload Mineral Holders CSV"
                description="Drop your CSV file from mineralholders.com"
              />
              {isProcessing && (
                <div className="mt-4 flex items-center gap-2 text-tre-teal">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-tre-teal"></div>
                  <span className="text-sm">Processing...</span>
                </div>
              )}
              {!hasRRCData && !isProcessing && (
                <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-xs text-yellow-700">
                    <AlertTriangle className="w-3 h-3 inline mr-1" />
                    Download RRC data first for accurate NRA calculations
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-gray-700">
                <Settings className="w-4 h-4" />
                <span className="font-medium">Processing Options</span>
              </div>

              <div className="p-3 bg-gray-50 rounded-lg text-sm">
                <span className="text-gray-600">File:</span>{' '}
                <span className="font-medium text-gray-900">{selectedFile?.name}</span>
              </div>

              {/* Filter Options */}
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Filter className="w-4 h-4" />
                  <span>Filters</span>
                </div>

                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={newRecordOnly}
                    onChange={(e) => setNewRecordOnly(e.target.checked)}
                    className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                  />
                  <span>New Records Only (Y)</span>
                </label>

                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={deduplicateByPropertyId}
                    onChange={(e) => setDeduplicateByPropertyId(e.target.checked)}
                    className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                  />
                  <span>Deduplicate by Property ID</span>
                </label>

                <div className="flex items-center gap-2">
                  <label className="text-sm">Min Appraisal Value:</label>
                  <input
                    type="number"
                    value={minAppraisalValue}
                    onChange={(e) => setMinAppraisalValue(Number(e.target.value))}
                    min={0}
                    className="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-tre-teal focus:border-tre-teal"
                  />
                </div>
              </div>

              {/* Well Type Override */}
              <div className="space-y-2">
                <label className="text-sm text-gray-600">Well Type Override:</label>
                <select
                  value={wellTypeOverride}
                  onChange={(e) => setWellTypeOverride(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
                >
                  <option value="auto">Auto-detect from RRC data</option>
                  <option value="oil">Oil</option>
                  <option value="gas">Gas</option>
                  <option value="both">Both</option>
                </select>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-2">
                <button
                  onClick={cancelProcessing}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={processFile}
                  className="flex-1 px-4 py-2 bg-tre-navy text-white rounded-lg text-sm hover:bg-tre-navy/90 transition-colors"
                >
                  Process CSV
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className={`grid grid-cols-1 ${panelCollapsed ? '' : 'lg:grid-cols-3'} gap-6`}>
        {/* Left Column - Upload and History */}
        {!panelCollapsed && (
        <div className="space-y-6">
          {/* Upload Section */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            {!showProcessingOptions ? (
              <>
                <FileUpload
                  onFilesSelected={handleFilesSelected}
                  accept=".csv"
                  label="Upload Mineral Holders CSV"
                  description="Drop your CSV file from mineralholders.com"
                />
                {isProcessing && (
                  <div className="mt-4 flex items-center gap-2 text-tre-teal">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-tre-teal"></div>
                    <span className="text-sm">Processing...</span>
                  </div>
                )}
                {!hasRRCData && !isProcessing && (
                  <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                    <p className="text-xs text-yellow-700">
                      <AlertTriangle className="w-3 h-3 inline mr-1" />
                      Download RRC data first for accurate NRA calculations
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-gray-700">
                  <Settings className="w-4 h-4" />
                  <span className="font-medium">Processing Options</span>
                </div>

                <div className="p-3 bg-gray-50 rounded-lg text-sm">
                  <span className="text-gray-600">File:</span>{' '}
                  <span className="font-medium text-gray-900">{selectedFile?.name}</span>
                </div>

                {/* Filter Options */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Filter className="w-4 h-4" />
                    <span>Filters</span>
                  </div>

                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={newRecordOnly}
                      onChange={(e) => setNewRecordOnly(e.target.checked)}
                      className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                    />
                    <span>New Records Only (Y)</span>
                  </label>

                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={deduplicateByPropertyId}
                      onChange={(e) => setDeduplicateByPropertyId(e.target.checked)}
                      className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                    />
                    <span>Deduplicate by Property ID</span>
                  </label>

                  <div className="flex items-center gap-2">
                    <label className="text-sm">Min Appraisal Value:</label>
                    <input
                      type="number"
                      value={minAppraisalValue}
                      onChange={(e) => setMinAppraisalValue(Number(e.target.value))}
                      min={0}
                      className="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-tre-teal focus:border-tre-teal"
                    />
                  </div>
                </div>

                {/* Well Type Override */}
                <div className="space-y-2">
                  <label className="text-sm text-gray-600">Well Type Override:</label>
                  <select
                    value={wellTypeOverride}
                    onChange={(e) => setWellTypeOverride(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
                  >
                    <option value="auto">Auto-detect from RRC data</option>
                    <option value="oil">Oil</option>
                    <option value="gas">Gas</option>
                    <option value="both">Both</option>
                  </select>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={cancelProcessing}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={processFile}
                    className="flex-1 px-4 py-2 bg-tre-navy text-white rounded-lg text-sm hover:bg-tre-navy/90 transition-colors"
                  >
                    Process CSV
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Job History */}
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
                        ) : job.result?.error_message ? (
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
                      onClick={() => handleExport('csv')}
                      className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      CSV
                    </button>
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-4 gap-4 p-6 border-b border-gray-100">
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {activeJob.result.total_rows}
                  </p>
                  <p className="text-sm text-gray-500">Total Rows</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {activeJob.result.processed_rows}
                  </p>
                  <p className="text-sm text-gray-500">Processed</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-green-600">
                    {activeJob.result.matched_rows}
                  </p>
                  <p className="text-sm text-gray-500">RRC Matched</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-red-600">
                    {activeJob.result.failed_rows}
                  </p>
                  <p className="text-sm text-gray-500">Failed</p>
                </div>
              </div>

              {/* Preview Table */}
              <div className="p-6">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900 flex items-center gap-2">
                    <Users className="w-4 h-4" />
                    Proration Preview
                  </h4>
                  <div className="relative" ref={columnPickerRef}>
                    <button
                      onClick={() => setShowColumnPicker(!showColumnPicker)}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <Columns className="w-4 h-4" />
                      Columns
                    </button>
                    {showColumnPicker && (
                      <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-2 min-w-[160px]">
                        {COLUMNS.filter(c => !c.alwaysVisible).map((col) => (
                          <label
                            key={col.key}
                            className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-gray-50 cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={visibleColumns.has(col.key)}
                              onChange={() => toggleColumn(col.key)}
                              className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                            />
                            <span>{col.label}</span>
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
                        {isColumnVisible('owner') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Owner</th>}
                        {isColumnVisible('county') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">County</th>}
                        {isColumnVisible('year') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Year</th>}
                        {isColumnVisible('interest') && <th className="text-right py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Interest</th>}
                        {isColumnVisible('interest_type') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Int Type</th>}
                        {isColumnVisible('appraisal_value') && <th className="text-right py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Appraisal Value</th>}
                        {isColumnVisible('legal_description') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Legal Desc</th>}
                        {isColumnVisible('property') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Property</th>}
                        {isColumnVisible('operator') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Operator</th>}
                        {isColumnVisible('raw_rrc') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Raw RRC</th>}
                        {isColumnVisible('new_record') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">New Record</th>}
                        {isColumnVisible('block') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Block</th>}
                        {isColumnVisible('section') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Section</th>}
                        {isColumnVisible('abstract') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Abstract</th>}
                        {isColumnVisible('rrc_acres') && <th className="text-right py-2 px-3 font-medium text-gray-600 whitespace-nowrap">RRC Acres</th>}
                        {isColumnVisible('est_nra') && <th className="text-right py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Est NRA</th>}
                        {isColumnVisible('dollars_per_nra') && <th className="text-right py-2 px-3 font-medium text-gray-600 whitespace-nowrap">$/NRA</th>}
                        {isColumnVisible('estimated_monthly_revenue') && <th className="text-right py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Est Monthly Rev</th>}
                        {isColumnVisible('well_type') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Well Type</th>}
                        {isColumnVisible('notes') && <th className="text-left py-2 px-3 font-medium text-gray-600 whitespace-nowrap">Notes</th>}
                        <th className="text-center py-2 px-3 font-medium text-gray-600 w-10"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {activeJob.result.rows?.map((row, i) => (
                        <tr key={i} className={!row.rrc_acres ? 'bg-red-50' : ''}>
                          {isColumnVisible('owner') && <td className="py-2 px-3 text-gray-900 whitespace-nowrap">{row.owner}</td>}
                          {isColumnVisible('county') && <td className="py-2 px-3 text-gray-600">{row.county}</td>}
                          {isColumnVisible('year') && <td className="py-2 px-3 text-gray-600 text-xs">{row.year ?? '\u2014'}</td>}
                          {isColumnVisible('interest') && (
                            <td className="py-2 px-3 text-gray-600 text-right">
                              {(row.interest * 100).toFixed(6)}%
                            </td>
                          )}
                          {isColumnVisible('interest_type') && <td className="py-2 px-3 text-gray-600 text-xs">{row.interest_type || '\u2014'}</td>}
                          {isColumnVisible('appraisal_value') && (
                            <td className="py-2 px-3 text-gray-600 text-right">{formatCurrency(row.appraisal_value)}</td>
                          )}
                          {isColumnVisible('legal_description') && <td className="py-2 px-3 text-gray-600 text-xs max-w-[200px] truncate" title={row.legal_description}>{row.legal_description || '\u2014'}</td>}
                          {isColumnVisible('property') && <td className="py-2 px-3 text-gray-600 text-xs whitespace-nowrap">{row.property || '\u2014'}</td>}
                          {isColumnVisible('operator') && <td className="py-2 px-3 text-gray-600 text-xs whitespace-nowrap">{row.operator || '\u2014'}</td>}
                          {isColumnVisible('raw_rrc') && <td className="py-2 px-3 text-gray-600 text-xs max-w-[150px] truncate" title={row.raw_rrc}>{row.raw_rrc || '\u2014'}</td>}
                          {isColumnVisible('new_record') && <td className="py-2 px-3 text-gray-600 text-xs">{row.new_record || '\u2014'}</td>}
                          {isColumnVisible('block') && <td className="py-2 px-3 text-gray-600 text-xs">{row.block || '\u2014'}</td>}
                          {isColumnVisible('section') && <td className="py-2 px-3 text-gray-600 text-xs">{row.section || '\u2014'}</td>}
                          {isColumnVisible('abstract') && <td className="py-2 px-3 text-gray-600 text-xs">{row.abstract || '\u2014'}</td>}
                          {isColumnVisible('rrc_acres') && (
                            <td className="py-2 px-3 text-gray-600 text-right">
                              {formatNumber(row.rrc_acres, 2)}
                            </td>
                          )}
                          {isColumnVisible('est_nra') && (
                            <td className="py-2 px-3 text-gray-600 text-right">
                              {formatNumber(row.est_nra, 4)}
                            </td>
                          )}
                          {isColumnVisible('dollars_per_nra') && (
                            <td className="py-2 px-3 text-gray-600 text-right">
                              {formatCurrency(row.dollars_per_nra)}
                            </td>
                          )}
                          {isColumnVisible('estimated_monthly_revenue') && (
                            <td className="py-2 px-3 text-gray-600 text-right">{formatCurrency(row.estimated_monthly_revenue)}</td>
                          )}
                          {isColumnVisible('well_type') && <td className="py-2 px-3 text-gray-600 text-xs">{row.well_type || '\u2014'}</td>}
                          {isColumnVisible('notes') && <td className="py-2 px-3 text-gray-600 text-xs max-w-[150px] truncate" title={row.notes}>{row.notes || '\u2014'}</td>}
                          <td className="py-2 px-3 text-center">
                            <button
                              onClick={() => handleEditRow(row, i)}
                              className="p-1 rounded hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600"
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
              </div>
            </div>

            {/* AI Review Panel */}
            {showAiReview && activeJob?.result?.rows && (
              <AiReviewPanel
                tool="proration"
                entries={activeJob.result.rows}
                onApplySuggestions={handleApplySuggestions}
                onClose={() => setShowAiReview(false)}
              />
            )}
            </>
          ) : activeJob?.result?.error_message ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-400" />
              <h3 className="font-medium text-gray-900 mb-1">Processing Failed</h3>
              <p className="text-sm text-gray-500">{activeJob.result.error_message}</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500">
              <Calculator className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="font-medium">No job selected</p>
              <p className="text-sm mt-1">Upload a CSV or select a job from the history</p>
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
                      ) : job.result?.error_message ? (
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

      {/* Edit Row Modal */}
      <Modal
        isOpen={editingRow !== null}
        onClose={handleCancelEdit}
        title="Edit Row"
        size="lg"
        footer={
          <>
            <button
              onClick={handleCancelEdit}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveEdit}
              className="px-4 py-2 bg-tre-navy text-white rounded-lg text-sm hover:bg-tre-navy/90 transition-colors"
            >
              Save
            </button>
          </>
        }
      >
        {editingRow && (
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Owner</label>
              <input
                type="text"
                value={editingRow.owner}
                onChange={(e) => setEditingRow({ ...editingRow, owner: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">County</label>
              <input
                type="text"
                value={editingRow.county}
                onChange={(e) => setEditingRow({ ...editingRow, county: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Interest</label>
              <input
                type="number"
                step="any"
                value={editingRow.interest}
                onChange={(e) => setEditingRow({ ...editingRow, interest: Number(e.target.value) })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Interest Type</label>
              <input
                type="text"
                value={editingRow.interest_type || ''}
                onChange={(e) => setEditingRow({ ...editingRow, interest_type: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Legal Description</label>
              <input
                type="text"
                value={editingRow.legal_description || ''}
                onChange={(e) => setEditingRow({ ...editingRow, legal_description: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Property</label>
              <input
                type="text"
                value={editingRow.property || ''}
                onChange={(e) => setEditingRow({ ...editingRow, property: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Operator</label>
              <input
                type="text"
                value={editingRow.operator || ''}
                onChange={(e) => setEditingRow({ ...editingRow, operator: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Block</label>
              <input
                type="text"
                value={editingRow.block || ''}
                onChange={(e) => setEditingRow({ ...editingRow, block: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Section</label>
              <input
                type="text"
                value={editingRow.section || ''}
                onChange={(e) => setEditingRow({ ...editingRow, section: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Abstract</label>
              <input
                type="text"
                value={editingRow.abstract || ''}
                onChange={(e) => setEditingRow({ ...editingRow, abstract: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">RRC Acres</label>
              <input
                type="number"
                step="any"
                value={editingRow.rrc_acres ?? ''}
                onChange={(e) => setEditingRow({ ...editingRow, rrc_acres: e.target.value ? Number(e.target.value) : undefined })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Est NRA</label>
              <input
                type="number"
                step="any"
                value={editingRow.est_nra ?? ''}
                onChange={(e) => setEditingRow({ ...editingRow, est_nra: e.target.value ? Number(e.target.value) : undefined })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">$/NRA</label>
              <input
                type="number"
                step="any"
                value={editingRow.dollars_per_nra ?? ''}
                onChange={(e) => setEditingRow({ ...editingRow, dollars_per_nra: e.target.value ? Number(e.target.value) : undefined })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Well Type</label>
              <select
                value={editingRow.well_type || 'auto'}
                onChange={(e) => setEditingRow({ ...editingRow, well_type: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              >
                <option value="auto">Auto-detect</option>
                <option value="oil">Oil</option>
                <option value="gas">Gas</option>
                <option value="both">Both</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
              <input
                type="text"
                value={editingRow.notes || ''}
                onChange={(e) => setEditingRow({ ...editingRow, notes: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
