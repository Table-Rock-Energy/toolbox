import { useState, useMemo, useEffect, useRef, useCallback } from 'react'
import { FileSearch, Download, Upload, Users, AlertCircle, CheckCircle, Flag, Filter, RotateCcw, Edit2, Columns, X, PanelLeftClose, PanelLeftOpen, Play, ShieldAlert } from 'lucide-react'
import { FileUpload, Modal, EditableCell, EnrichmentModal, UnifiedEnrichButton, CancelConfirmDialog, HighlightedCell } from '../components'
import MineralExportModal from '../components/MineralExportModal'
import type { PostProcessResult } from '../utils/api'
import { useAuth } from '../contexts/AuthContext'
import { useOperationContext } from '../contexts/OperationContext'
import type { StartOperationOpts } from '../contexts/OperationContext'
import { useToolLayout } from '../hooks/useToolLayout'
import { useFeatureFlags } from '../hooks/useFeatureFlags'
import { usePreviewState } from '../hooks/usePreviewState'
import type { PipelineStatus, EnrichmentCellChange, PipelineStep } from '../hooks/useEnrichmentPipeline'

interface PartyEntry {
  entry_number: string
  primary_name: string
  first_name?: string
  middle_name?: string
  last_name?: string
  suffix?: string
  entity_type: string
  mailing_address?: string
  mailing_address_2?: string
  city?: string
  state?: string
  zip_code?: string
  notes?: string
  property_type?: string
  property_value?: number
  flagged: boolean
  flag_reason?: string
}

interface CaseMetadata {
  county?: string
  case_number?: string
  applicant?: string
  well_name?: string
  legal_description?: string
}

interface ExtractionResult {
  success: boolean
  entries?: PartyEntry[]
  total_count?: number
  flagged_count?: number
  source_filename?: string
  error_message?: string
  job_id?: string
  format_detected?: string
  quality_score?: number
  format_warning?: string
  case_metadata?: CaseMetadata
  merge_warnings?: string[]
  original_csv_entries?: Record<string, unknown>[]
  post_process?: PostProcessResult
}

interface UploadResponse {
  message: string
  result?: ExtractionResult
}

interface ExtractJob {
  id: string
  job_id?: string
  documentName: string
  user: string
  timestamp: string
  result?: ExtractionResult
}

interface ColumnConfig {
  key: string
  label: string
  alwaysVisible?: boolean
}

const COLUMNS: ColumnConfig[] = [
  { key: 'checkbox', label: '', alwaysVisible: true },
  { key: 'entry_number', label: '#' },
  { key: 'primary_name', label: 'Full Name' },
  { key: 'first_name', label: 'First Name' },
  { key: 'middle_name', label: 'Middle Name' },
  { key: 'last_name', label: 'Last Name' },
  { key: 'suffix', label: 'Suffix' },
  { key: 'entity_type', label: 'Owner Type' },
  { key: 'mailing_address', label: 'Address 1' },
  { key: 'mailing_address_2', label: 'Address 2' },
  { key: 'city', label: 'City' },
  { key: 'state', label: 'State' },
  { key: 'zip_code', label: 'ZIP' },
  { key: 'notes', label: 'Notes' },
  { key: 'property_type', label: 'Prop Type' },
  { key: 'property_value', label: 'Prop Value' },
  { key: 'status', label: 'Status' },
  { key: 'edit', label: '', alwaysVisible: true },
]

const DEFAULT_EXTRACT_VISIBLE = new Set([
  'checkbox', 'entry_number', 'primary_name', 'entity_type',
  'mailing_address', 'city', 'state', 'zip_code', 'status', 'edit',
])

const STORAGE_KEY_PREFIX = 'extract-visible-columns'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Extract() {
  const { user, userName, getIdToken } = useAuth()

  const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getIdToken()
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }, [getIdToken])
  const { panelCollapsed, setPanelCollapsed, togglePanel, activeStorageKey } = useToolLayout('extract', user?.uid, STORAGE_KEY_PREFIX)
  const [jobs, setJobs] = useState<ExtractJob[]>([])
  const [activeJob, setActiveJob] = useState<ExtractJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [isLoadingEntries, setIsLoadingEntries] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formatHint, setFormatHint] = useState<string>('')
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [originalCsvEntries, setOriginalCsvEntries] = useState<Record<string, unknown>[]>([])
  const [stagedFile, setStagedFile] = useState<File | null>(null)
  const [isDetecting, setIsDetecting] = useState(false)

  // Filter states
  const [showIndividualsOnly, setShowIndividualsOnly] = useState(false)
  const [hideFlagged, setHideFlagged] = useState(false)
  const [hideUnknownAddresses, setHideUnknownAddresses] = useState(true)
  const [filterPropertyType, setFilterPropertyType] = useState<string>('')
  const [filterMinValue, setFilterMinValue] = useState<string>('')
  const [filterMaxValue, setFilterMaxValue] = useState<string>('')

  // Enrichment feature flags
  const featureFlags = useFeatureFlags()

  // OperationContext
  const { operation, startOperation, abortOperation, undoOperation, clearOperation, getResultsForTool } = useOperationContext()
  const [cancelConfirmPending, setCancelConfirmPending] = useState<StartOperationOpts | null>(null)

  // Mineral export modal state
  const [showMineralModal, setShowMineralModal] = useState(false)

  // Edit modal state
  const [editingEntry, setEditingEntry] = useState<PartyEntry | null>(null)

  // Column visibility (persisted in localStorage per user, separate keys for narrow/wide)
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(activeStorageKey)
      if (saved) return new Set(JSON.parse(saved))
    } catch { /* use defaults */ }
    return new Set(DEFAULT_EXTRACT_VISIBLE)
  })
  const [showColumnPicker, setShowColumnPicker] = useState(false)
  const columnPickerRef = useRef<HTMLDivElement>(null)

  // Reload column visibility when panel collapse state changes (switching between narrow/wide keys)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(activeStorageKey)
      if (saved) {
        setVisibleColumns(new Set(JSON.parse(saved)))
      } else {
        setVisibleColumns(new Set(DEFAULT_EXTRACT_VISIBLE))
      }
    } catch {
      setVisibleColumns(new Set(DEFAULT_EXTRACT_VISIBLE))
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
        const hdrs = await authHeaders()
        const response = await fetch(`${API_BASE}/history/jobs?tool=extract&limit=20`, { headers: hdrs })
        if (!response.ok) return
        const data = await response.json()
        if (data.jobs?.length) {
          const loaded: ExtractJob[] = data.jobs.map((j: Record<string, unknown>) => ({
            id: j.id as string,
            job_id: j.id as string,
            documentName: j.source_filename as string || 'Unknown',
            user: (j.user_id as string) || 'System',
            timestamp: j.created_at
              ? new Date(j.created_at as string).toLocaleString()
              : '',
          }))
          setJobs(loaded)
        }
      } catch {
        // Firestore unavailable, continue with empty jobs
      }
    }
    loadJobs()
  }, [authHeaders])


  // Clear CSV file when switching away from ECF format
  useEffect(() => {
    if (formatHint !== 'ECF') {
      setCsvFile(null)
    }
  }, [formatHint])


  const handleFileStaged = async (files: File[]) => {
    if (files.length === 0) return
    const file = files[0]
    setStagedFile(file)
    setError(null)

    // Auto-detect format via backend (with timeout to avoid infinite hangs)
    setIsDetecting(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const headers = await authHeaders()
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 15000)
      const response = await fetch(`${API_BASE}/extract/detect-format`, {
        method: 'POST',
        headers,
        body: formData,
        signal: controller.signal,
      })
      clearTimeout(timeout)
      if (response.ok) {
        const data = await response.json()
        if (data.format) {
          setFormatHint(data.format) // auto-selects detected format in dropdown
        }
      }
    } catch {
      // Detection failed or timed out — user can still manually select format
    } finally {
      setIsDetecting(false)
    }
  }

  const handleProcess = () => {
    if (!stagedFile) return
    handleFilesSelected([stagedFile])
  }

  const handleClearStaged = () => {
    setStagedFile(null)
    setFormatHint('')
    setCsvFile(null)
  }

  const handleFilesSelected = async (files: File[]) => {
    if (files.length === 0) return

    const file = files[0]
    setIsProcessing(true)
    setError(null)

    const newJob: ExtractJob = {
      id: String(Date.now()),
      documentName: file.name,
      user: user?.displayName || user?.email || 'Unknown',
      timestamp: new Date().toLocaleString(),
    }

    try {
      const formData = new FormData()
      formData.append('file', file)
      if (formatHint === 'ECF' && csvFile) {
        formData.append('csv_file', csvFile)
      }

      const uploadUrl = `${API_BASE}/extract/upload${formatHint ? `?format_hint=${formatHint}` : ''}`
      const uploadHeaders = await authHeaders()
      const response = await fetch(uploadUrl, {
        method: 'POST',
        headers: {
          ...uploadHeaders,
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
      newJob.result = data.result
      newJob.job_id = data.result?.job_id

      // Capture post-process corrections from the result
      // Capture original CSV entries for ECF cross-file comparison
      if (data.result?.original_csv_entries) {
        setOriginalCsvEntries(data.result.original_csv_entries)
      } else {
        setOriginalCsvEntries([])
      }

      setJobs((prev) => [newJob, ...prev])
      setActiveJob(newJob)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process file')
      newJob.result = {
        success: false,
        error_message: err instanceof Error ? err.message : 'Failed to process file',
      }
      setJobs((prev) => [newJob, ...prev])
    } finally {
      setIsProcessing(false)
      setStagedFile(null)
    }
  }

  const handleExport = async (county: string, campaignName: string) => {
    if (preview.entriesToExport.length === 0) {
      setError('No entries selected for export')
      return
    }

    try {
      const exportHeaders = await authHeaders()
      const response = await fetch(`${API_BASE}/extract/export/csv`, {
        method: 'POST',
        headers: {
          ...exportHeaders,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          entries: preview.entriesToExport,
          filename: activeJob?.documentName?.replace(/\.[^.]+$/, '') || 'extract',
          county,
          campaign_name: campaignName,
          case_metadata: activeJob?.result?.case_metadata,
        }),
      })

      if (!response.ok) throw new Error('Export failed')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activeJob?.documentName?.replace(/\.[^.]+$/, '') || 'extract'}_mineral.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch {
      setError('Failed to export file')
    }
  }

  const handleSelectJob = async (job: ExtractJob) => {
    setActiveJob(job)
    setError(null)

    // Lazy-load entries if not already loaded
    if (!job.result && job.job_id) {
      setIsLoadingEntries(true)
      try {
        const entryHeaders = await authHeaders()
        const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}/entries`, { headers: entryHeaders })
        if (response.ok) {
          const data = await response.json()
          const entries = data.entries as PartyEntry[]
          const result: ExtractionResult = {
            success: true,
            entries,
            total_count: entries.length,
            flagged_count: entries.filter((e: PartyEntry) => e.flagged).length,
            job_id: job.job_id,
          }
          const updatedJob = { ...job, result }
          setJobs((prev) => prev.map((j) => (j.id === job.id ? updatedJob : j)))
          setActiveJob(updatedJob)
        }
      } catch {
        // Failed to load, non-critical
      } finally {
        setIsLoadingEntries(false)
      }
    }
  }

  const handleDeleteJob = async (e: React.MouseEvent, job: ExtractJob) => {
    e.stopPropagation()
    if (!job.job_id) {
      setJobs((prev) => prev.filter((j) => j.id !== job.id))
      if (activeJob?.id === job.id) setActiveJob(null)
      return
    }
    try {
      const delHeaders = await authHeaders()
      const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}`, { method: 'DELETE', headers: delHeaders })
      if (response.status === 403) {
        setDeleteError('You can only delete jobs you created. Contact an admin if this job needs to be removed.')
        return
      }
      if (!response.ok) return
      setJobs((prev) => prev.filter((j) => j.id !== job.id))
      if (activeJob?.id === job.id) setActiveJob(null)
    } catch { /* network error, best-effort */ }
  }

  // Get filtered entries based on filter state
  const filteredEntries = useMemo(() => {
    if (!activeJob?.result?.entries) return []

    const minVal = filterMinValue ? parseFloat(filterMinValue) : null
    const maxVal = filterMaxValue ? parseFloat(filterMaxValue) : null

    return activeJob.result.entries.filter((entry) => {
      if (showIndividualsOnly && entry.entity_type?.toLowerCase() !== 'individual') return false
      if (hideFlagged && entry.flagged) return false
      if (hideUnknownAddresses && (entry.entry_number.startsWith('U') || (!entry.mailing_address && !entry.city))) return false
      if (filterPropertyType && entry.property_type !== filterPropertyType) return false
      if (minVal !== null && (!entry.property_value || entry.property_value < minVal)) return false
      if (maxVal !== null && (!entry.property_value || entry.property_value > maxVal)) return false
      return true
    })
  }, [activeJob?.result?.entries, showIndividualsOnly, hideFlagged, hideUnknownAddresses, filterPropertyType, filterMinValue, filterMaxValue])

  // Preview state: exclusion, inline editing, flagged-row sorting
  const preview = usePreviewState({
    entries: filteredEntries,
    keyField: 'entry_number',
    flagField: 'flagged',
  })

  // Dynamic tool name based on format
  const toolName = formatHint === 'ECF' ? 'ecf' : 'extract'

  // Derived state from context
  const pipelineStatus: PipelineStatus = operation?.tool === toolName ? (operation.status as PipelineStatus) : 'idle'
  const stepStatuses = operation?.tool === toolName ? operation.stepStatuses : []
  const operationChanges = useMemo<Map<string, EnrichmentCellChange>>(
    () => operation?.tool === toolName ? operation.enrichmentChanges : new Map(),
    [operation?.tool, operation?.enrichmentChanges, toolName]
  )
  const [persistedChanges, setPersistedChanges] = useState<Map<string, EnrichmentCellChange>>(new Map())
  if (operationChanges.size > 0 && operationChanges !== persistedChanges && operationChanges.size !== persistedChanges.size) {
    setPersistedChanges(operationChanges)
  }
  const enrichmentChanges = operationChanges.size > 0 ? operationChanges : persistedChanges
  const completedSteps = operation?.tool === toolName ? operation.completedSteps : new Set<PipelineStep>()
  const batchProgress = operation?.tool === toolName ? operation.batchProgress : null
  const stepBatchResults = operation?.tool === toolName ? operation.stepBatchResults : new Map<PipelineStep, import('../contexts/OperationContext').StepBatchResult>()
  const errorMessage = operation?.tool === toolName ? operation.errorMessage : null

  // Derive modal isOpen from context
  const enrichModalOpen = operation?.tool === toolName && (operation.status === 'running' || operation.status === 'completed' || operation.status === 'error')

  // Derive set of entry keys that have enrichment changes
  const affectedEntryKeys = useMemo(() => {
    const keys = new Set<string>()
    enrichmentChanges.forEach(c => keys.add(c.entry_key))
    return keys
  }, [enrichmentChanges])

  // Start enrichment via OperationContext — only visible/filtered entries
  const { editedFields } = preview
  const handleStartEnrichment = useCallback(() => {
    const visibleEntries = preview.previewEntries
    const opts: StartOperationOpts = {
      tool: toolName,
      entries: visibleEntries.map(e => ({...e} as Record<string, unknown>)),
      updateEntries: (enrichedEntries) => {
        // Merge enriched entries back into full dataset by key
        if (activeJob?.result?.entries) {
          const enrichedMap = new Map<string, Record<string, unknown>>()
          for (const e of enrichedEntries) {
            enrichedMap.set(String((e as Record<string, unknown>).entry_number), e as Record<string, unknown>)
          }
          const merged = activeJob.result.entries.map(e => {
            const enriched = enrichedMap.get(e.entry_number)
            return enriched ? (enriched as unknown as PartyEntry) : e
          })
          setActiveJob({
            ...activeJob,
            result: { ...activeJob.result, entries: merged },
          })
        }
      },
      editedFields: editedFields as Map<string, unknown>,
      keyField: 'entry_number',
      featureFlags,
      sourceData: formatHint === 'ECF' ? originalCsvEntries : undefined,
    }
    if (operation?.status === 'running') {
      setCancelConfirmPending(opts)
    } else {
      startOperation(opts)
    }
  }, [activeJob, preview.previewEntries, editedFields, featureFlags, operation?.status, startOperation, toolName, formatHint, originalCsvEntries])

  // Auto-restore enriched entries on mount (PERSIST-01)
  useEffect(() => {
    const results = getResultsForTool(toolName)
    if (results && activeJob) {
      setTimeout(() => {
        setActiveJob({
          ...activeJob,
          result: { ...activeJob.result!, entries: results as unknown as PartyEntry[] },
        })
        clearOperation()
      }, 0)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-collapse panel when preview data loads
  useEffect(() => {
    if (activeJob?.result?.entries?.length) setPanelCollapsed(true)
  }, [activeJob?.result?.entries, setPanelCollapsed])

  const resetFilters = () => {
    setShowIndividualsOnly(false)
    setHideFlagged(false)
    setHideUnknownAddresses(true)
    setFilterPropertyType('')
    setFilterMinValue('')
    setFilterMaxValue('')
  }

  const handleEditEntry = (entry: PartyEntry) => {
    setEditingEntry({ ...entry })
  }

  const handleSaveEdit = () => {
    if (!editingEntry || !activeJob?.result?.entries) return

    const updatedEntries = activeJob.result.entries.map((e) =>
      e.entry_number === editingEntry.entry_number ? editingEntry : e
    )

    setActiveJob({
      ...activeJob,
      result: {
        ...activeJob.result,
        entries: updatedEntries,
      },
    })
    setEditingEntry(null)
  }

  const toggleColumn = (key: string) => {
    const next = new Set(visibleColumns)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setVisibleColumns(next)
  }

  const isColVisible = (key: string) => visibleColumns.has(key)

  const getCellHighlight = (entryKey: string, field: string) => {
    return enrichmentChanges.get(`${entryKey}:${field}`) || null
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-100 rounded-lg">
          <FileSearch className="w-6 h-6 text-blue-600" />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Extract
          </h1>
          <p className="text-gray-500 text-sm">
            Extract party and stakeholder data from PDF filings
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

      {/* Upload Section - compact row when panel collapsed and no active results */}
      {panelCollapsed && !activeJob?.result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <FileUpload
            onFilesSelected={handleFileStaged}
            accept=".pdf"
            label="Upload PDF File"
            description="Drop your PDF file here"
          />
          <div className="mt-3 flex items-center gap-2">
            <label className="text-xs text-gray-500">Format:</label>
            <select
              value={formatHint}
              onChange={(e) => setFormatHint(e.target.value)}
              className="text-xs border border-gray-300 rounded px-2 py-1 focus:ring-tre-teal focus:border-tre-teal"
            >
              <option value="">Auto-detect</option>
              <option value="FREE_TEXT_NUMBERED">Free Text (Default)</option>
              <option value="TABLE_ATTENTION">Table with Attention Column</option>
              <option value="TABLE_SPLIT_ADDR">Table with Split Address</option>
              <option value="FREE_TEXT_LIST">Two-Column Numbered List</option>
              <option value="ECF">ECF Filing (Convey 640)</option>
            </select>
          </div>
          {formatHint === 'ECF' && (
            <div className="mt-4">
              <FileUpload
                onFilesSelected={(files) => setCsvFile(files[0] || null)}
                accept=".csv,.xlsx,.xls"
                multiple={false}
                label="Convey 640 (Optional)"
                description="Drop CSV or Excel file here, or click to select"
              />
            </div>
          )}
          {stagedFile && (
            <div className="mt-4 flex items-center gap-3">
              <button
                onClick={handleProcess}
                disabled={isProcessing || isDetecting}
                className="flex items-center gap-2 px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {isProcessing ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                    Processing...
                  </>
                ) : isDetecting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                    Detecting format...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Process
                  </>
                )}
              </button>
              <span className="text-sm text-gray-500 flex items-center gap-1">
                {stagedFile.name}
                {formatHint === 'ECF' && (
                  <span className="text-tre-teal font-medium">(ECF Filing detected)</span>
                )}
              </span>
              <button
                onClick={handleClearStaged}
                disabled={isProcessing}
                className="text-gray-400 hover:text-gray-600 disabled:opacity-50"
                title="Clear file"
              >
                <X className="w-4 h-4" />
              </button>
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
              onFilesSelected={handleFileStaged}
              accept=".pdf"
              label="Upload PDF File"
              description="Drop your PDF file here"
            />
            <div className="mt-3 flex items-center gap-2">
              <label className="text-xs text-gray-500">Format:</label>
              <select
                value={formatHint}
                onChange={(e) => setFormatHint(e.target.value)}
                className="text-xs border border-gray-300 rounded px-2 py-1 focus:ring-tre-teal focus:border-tre-teal"
              >
                <option value="">Auto-detect</option>
                <option value="FREE_TEXT_NUMBERED">Free Text (Default)</option>
                <option value="TABLE_ATTENTION">Table with Attention Column</option>
                <option value="TABLE_SPLIT_ADDR">Table with Split Address</option>
                <option value="FREE_TEXT_LIST">Two-Column Numbered List</option>
                <option value="ECF">ECF Filing (Convey 640)</option>
              </select>
            </div>
            {formatHint === 'ECF' && (
              <div className="mt-4">
                <FileUpload
                  onFilesSelected={(files) => setCsvFile(files[0] || null)}
                  accept=".csv,.xlsx,.xls"
                  multiple={false}
                  label="Convey 640 (Optional)"
                  description="Drop CSV or Excel file here, or click to select"
                />
              </div>
            )}
            {stagedFile && (
              <div className="mt-4 flex items-center gap-3">
                <button
                  onClick={handleProcess}
                  disabled={isProcessing || isDetecting}
                  className="flex items-center gap-2 px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
                >
                  {isProcessing ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                      Processing...
                    </>
                  ) : isDetecting ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                      Detecting format...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Process
                    </>
                  )}
                </button>
                <span className="text-sm text-gray-500 flex items-center gap-1">
                  {stagedFile.name}
                  {formatHint === 'ECF' && (
                    <span className="text-tre-teal font-medium">(ECF Filing detected)</span>
                  )}
                </span>
                <button
                  onClick={handleClearStaged}
                  disabled={isProcessing}
                  className="text-gray-400 hover:text-gray-600 disabled:opacity-50"
                  title="Clear file"
                >
                  <X className="w-4 h-4" />
                </button>
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

        {/* Results */}
        <div className={panelCollapsed ? '' : 'lg:col-span-2'}>
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          )}

          {activeJob?.result?.format_warning && (
            <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center gap-2 text-yellow-700">
              <AlertCircle className="w-5 h-5" />
              <span className="text-sm">{activeJob.result.format_warning}</span>
              <span className="text-xs text-yellow-500 ml-2">Try selecting a format manually and re-uploading.</span>
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
                    {activeJob.result.format_detected && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        Format: {activeJob.result.format_detected.replace(/_/g, ' ')}
                        {activeJob.result.quality_score != null && (
                          <span className={`ml-2 ${activeJob.result.quality_score < 0.5 ? 'text-red-500' : activeJob.result.quality_score < 0.75 ? 'text-yellow-500' : 'text-green-500'}`}>
                            ({Math.round(activeJob.result.quality_score * 100)}% confidence)
                          </span>
                        )}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <UnifiedEnrichButton
                      pipelineStatus={pipelineStatus}
                      entryCount={preview.entriesToExport.length}
                      anyStepEnabled={featureFlags.cleanUpEnabled || featureFlags.validateEnabled || featureFlags.enrichEnabled}
                      onEnrich={handleStartEnrichment}
                      onReopen={() => {}}
                      onUndo={() => { undoOperation(); clearOperation() }}
                      onClearHighlights={() => { clearOperation() }}
                      hasChanges={enrichmentChanges.size > 0}
                      hasSnapshot={completedSteps.size > 0}
                    />
                    <EnrichmentModal
                      isOpen={!!enrichModalOpen}
                      onClose={() => clearOperation()}
                      onStop={() => abortOperation()}
                      stepStatuses={stepStatuses}
                      pipelineStatus={pipelineStatus}
                      enrichmentChanges={enrichmentChanges}
                      batchProgress={batchProgress}
                      stepBatchResults={stepBatchResults}
                    />
                    <button
                      onClick={() => setShowMineralModal(true)}
                      className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      Mineral
                    </button>
                  </div>
                </div>
              </div>

              {/* Pipeline Error */}
              {errorMessage && (
                <div className="px-6 py-3 border-b border-red-200 bg-red-50 flex items-center justify-between">
                  <p className="text-sm text-red-700">{errorMessage}</p>
                  <button onClick={() => clearOperation()} className="text-sm text-red-500 hover:underline">Dismiss</button>
                </div>
              )}

              {/* Case Metadata Panel - ECF results */}
              {activeJob?.result?.case_metadata && (
                <div className="px-6 py-4 border-b border-gray-100 bg-blue-50/30">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
                    Case Information
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: 'County', value: activeJob.result.case_metadata.county },
                      { label: 'Case Number', value: activeJob.result.case_metadata.case_number },
                      { label: 'Applicant', value: activeJob.result.case_metadata.applicant },
                      { label: 'Well Name', value: activeJob.result.case_metadata.well_name },
                    ].map(({ label, value }) => (
                      <div key={label}>
                        <p className="text-xs text-gray-500">{label}</p>
                        <p className="text-sm font-medium text-gray-900">{value || '\u2014'}</p>
                      </div>
                    ))}
                  </div>
                  {activeJob.result.case_metadata.legal_description && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-500">Legal Description</p>
                      <p className="text-sm font-medium text-gray-900">
                        {activeJob.result.case_metadata.legal_description}
                      </p>
                    </div>
                  )}
                  {(() => {
                    const warnings = (activeJob.result.merge_warnings || []).filter(w => !w.match(/^0 of 0/))
                    if (warnings.length === 0) return null
                    return (
                      <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded-lg">
                        <p className="text-xs font-medium text-yellow-800">Merge Warnings</p>
                        <ul className="text-xs text-yellow-700 mt-1 space-y-0.5">
                          {warnings.map((w, i) => (
                            <li key={i}>- {w}</li>
                          ))}
                        </ul>
                      </div>
                    )
                  })()}
                </div>
              )}

              {/* Filter Controls */}
              <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex items-center gap-2 text-gray-600">
                    <Filter className="w-4 h-4" />
                    <span className="text-sm font-medium">Filters:</span>
                  </div>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={showIndividualsOnly}
                      onChange={(e) => setShowIndividualsOnly(e.target.checked)}
                      className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                    />
                    <span>Show Individuals Only</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={hideFlagged}
                      onChange={(e) => setHideFlagged(e.target.checked)}
                      className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                    />
                    <span>Hide Flagged</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={hideUnknownAddresses}
                      onChange={(e) => setHideUnknownAddresses(e.target.checked)}
                      className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                    />
                    <span>Hide Unknown Addresses</span>
                  </label>
                  <button
                    onClick={resetFilters}
                    className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Reset
                  </button>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  Showing {filteredEntries.length} of {activeJob.result.total_count} entries
                  ({preview.entriesToExport.length} selected for export)
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 p-6 border-b border-gray-100">
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {filteredEntries.length}
                  </p>
                  <p className="text-sm text-gray-500">Total Parties</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-yellow-600">
                    {preview.flaggedCount}
                  </p>
                  <p className="text-sm text-gray-500">Flagged for Review</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-green-600">
                    {preview.entriesToExport.length}
                  </p>
                  <p className="text-sm text-gray-500">Selected for Export</p>
                </div>
              </div>

              {/* Preview Table */}
              <div className="p-6">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900 flex items-center gap-2">
                    <Users className="w-4 h-4" />
                    Party Entries
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
                        <th className="text-left py-2 px-3 font-medium text-gray-600 w-10">
                          <input
                            type="checkbox"
                            checked={preview.isAllSelected}
                            ref={(el) => {
                              if (el) el.indeterminate = preview.isSomeSelected
                            }}
                            onChange={() => preview.toggleExcludeAll()}
                            className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                          />
                        </th>
                        {isColVisible('entry_number') && <th className="text-left py-2 px-3 font-medium text-gray-600">#</th>}
                        {isColVisible('primary_name') && <th className="text-left py-2 px-3 font-medium text-gray-600">Full Name</th>}
                        {isColVisible('first_name') && <th className="text-left py-2 px-3 font-medium text-gray-600">First Name</th>}
                        {isColVisible('middle_name') && <th className="text-left py-2 px-3 font-medium text-gray-600">Middle Name</th>}
                        {isColVisible('last_name') && <th className="text-left py-2 px-3 font-medium text-gray-600">Last Name</th>}
                        {isColVisible('suffix') && <th className="text-left py-2 px-3 font-medium text-gray-600">Suffix</th>}
                        {isColVisible('entity_type') && <th className="text-left py-2 px-3 font-medium text-gray-600">Owner Type</th>}
                        {isColVisible('mailing_address') && <th className="text-left py-2 px-3 font-medium text-gray-600">Address 1</th>}
                        {isColVisible('mailing_address_2') && <th className="text-left py-2 px-3 font-medium text-gray-600">Address 2</th>}
                        {isColVisible('city') && <th className="text-left py-2 px-3 font-medium text-gray-600">City</th>}
                        {isColVisible('state') && <th className="text-left py-2 px-3 font-medium text-gray-600">State</th>}
                        {isColVisible('zip_code') && <th className="text-left py-2 px-3 font-medium text-gray-600">ZIP</th>}
                        {isColVisible('notes') && <th className="text-left py-2 px-3 font-medium text-gray-600">Notes</th>}
                        {isColVisible('property_type') && <th className="text-left py-2 px-3 font-medium text-gray-600">Prop Type</th>}
                        {isColVisible('property_value') && <th className="text-left py-2 px-3 font-medium text-gray-600">Prop Value</th>}
                        {isColVisible('status') && <th className="text-left py-2 px-3 font-medium text-gray-600">Status</th>}
                        <th className="text-left py-2 px-3 font-medium text-gray-600 w-10"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {(() => {
                        // Build display list, sort enriched rows to top
                        const rows = preview.previewEntries.map((entry) => ({
                          entry,
                          entryKey: entry.entry_number,
                        }))
                        if (affectedEntryKeys.size > 0) {
                          rows.sort((a, b) => {
                            const aChanged = affectedEntryKeys.has(a.entryKey) ? 0 : 1
                            const bChanged = affectedEntryKeys.has(b.entryKey) ? 0 : 1
                            return aChanged - bChanged
                          })
                        }
                        return rows
                      })().map(({ entry, entryKey }) => {
                        const isExcluded = preview.isExcluded(entry.entry_number)
                        const hasChanges = affectedEntryKeys.has(entryKey)
                        return (
                          <tr
                            key={entry.entry_number}
                            className={`
                              ${hasChanges ? 'bg-blue-50' : entry.flagged ? 'bg-yellow-50' : ''}
                              ${isExcluded ? 'opacity-50 bg-gray-100' : ''}
                              transition-colors duration-[2000ms]
                            `}
                          >
                            <td className="py-2 px-3">
                              <input
                                type="checkbox"
                                checked={!isExcluded}
                                onChange={() => preview.toggleExclude(entry.entry_number)}
                                className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                              />
                            </td>
                            {isColVisible('entry_number') && (
                              <td className={`py-2 px-3 text-gray-500 ${isExcluded ? 'line-through' : ''}`}>
                                {entry.entry_number}
                              </td>
                            )}
                            {isColVisible('primary_name') && (() => {
                              const hl = getCellHighlight(entryKey, 'primary_name')
                              return (
                              <HighlightedCell highlight={hl} value={entry.primary_name} className={`py-2 px-3 text-gray-900 ${isExcluded ? 'line-through' : ''}`}>
                                <EditableCell
                                  value={entry.primary_name}
                                  onCommit={(val) => preview.editField(entry.entry_number, 'primary_name', val)}
                                />
                              </HighlightedCell>
                              )
                            })()}
                            {isColVisible('first_name') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.first_name || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColVisible('middle_name') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.middle_name || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColVisible('last_name') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.last_name || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColVisible('suffix') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.suffix || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColVisible('entity_type') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">
                                <select
                                  value={entry.entity_type}
                                  onChange={(e) => preview.editField(entry.entry_number, 'entity_type', e.target.value)}
                                  className="bg-transparent border-0 p-0 text-xs text-gray-600 focus:ring-0 cursor-pointer hover:text-tre-navy"
                                >
                                  <option value="Individual">Individual</option>
                                  <option value="Trust">Trust</option>
                                  <option value="LLC">LLC</option>
                                  <option value="Corporation">Corporation</option>
                                  <option value="Partnership">Partnership</option>
                                  <option value="Government">Government</option>
                                  <option value="Estate">Estate</option>
                                  <option value="Unknown Heirs">Unknown Heirs</option>
                                </select>
                              </td>
                            )}
                            {isColVisible('mailing_address') && (() => {
                              const hl = getCellHighlight(entryKey, 'mailing_address')
                              return (
                              <HighlightedCell highlight={hl} value={entry.mailing_address} className="py-2 px-3 text-gray-600 text-xs">
                                <EditableCell
                                  value={entry.mailing_address}
                                  onCommit={(val) => preview.editField(entry.entry_number, 'mailing_address', val)}
                                />
                              </HighlightedCell>
                              )
                            })()}
                            {isColVisible('mailing_address_2') && (() => {
                              const hl = getCellHighlight(entryKey, 'mailing_address_2')
                              return (
                              <HighlightedCell highlight={hl} value={entry.mailing_address_2} className="py-2 px-3 text-gray-600 text-xs">
                                <EditableCell
                                  value={entry.mailing_address_2}
                                  onCommit={(val) => preview.editField(entry.entry_number, 'mailing_address_2', val)}
                                />
                              </HighlightedCell>
                              )
                            })()}
                            {isColVisible('city') && (() => {
                              const hl = getCellHighlight(entryKey, 'city')
                              return (
                              <HighlightedCell highlight={hl} value={entry.city} className="py-2 px-3 text-gray-600 text-xs">
                                <EditableCell
                                  value={entry.city}
                                  onCommit={(val) => preview.editField(entry.entry_number, 'city', val)}
                                />
                              </HighlightedCell>
                              )
                            })()}
                            {isColVisible('state') && (() => {
                              const hl = getCellHighlight(entryKey, 'state')
                              return (
                              <HighlightedCell highlight={hl} value={entry.state} className="py-2 px-3 text-gray-600 text-xs">
                                <EditableCell
                                  value={entry.state}
                                  onCommit={(val) => preview.editField(entry.entry_number, 'state', val)}
                                />
                              </HighlightedCell>
                              )
                            })()}
                            {isColVisible('zip_code') && (() => {
                              const hl = getCellHighlight(entryKey, 'zip_code')
                              return (
                              <HighlightedCell highlight={hl} value={entry.zip_code} className="py-2 px-3 text-gray-600 text-xs">
                                <EditableCell
                                  value={entry.zip_code}
                                  onCommit={(val) => preview.editField(entry.entry_number, 'zip_code', val)}
                                />
                              </HighlightedCell>
                              )
                            })()}
                            {isColVisible('notes') && (
                              <td className="py-2 px-3 text-gray-600 text-xs max-w-[200px] truncate" title={entry.notes}>
                                {entry.notes || <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColVisible('property_type') && (
                              <td className="py-2 px-3 text-xs">
                                {entry.property_type ? (
                                  <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
                                    entry.property_type === 'residential' ? 'text-blue-700 bg-blue-100' :
                                    entry.property_type === 'commercial' ? 'text-orange-700 bg-orange-100' :
                                    entry.property_type === 'land' ? 'text-green-700 bg-green-100' :
                                    'text-gray-600 bg-gray-100'
                                  }`}>
                                    {entry.property_type}
                                  </span>
                                ) : <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColVisible('property_value') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">
                                {entry.property_value ? (
                                  `$${entry.property_value.toLocaleString()}`
                                ) : <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColVisible('status') && (
                              <td className="py-2 px-3">
                                {entry.flagged ? (
                                  <span
                                    className="inline-flex items-center gap-1 text-yellow-600 text-xs cursor-help"
                                    title={entry.flag_reason || 'Flagged for review'}
                                  >
                                    <Flag className="w-3 h-3" />
                                    Review
                                  </span>
                                ) : (
                                  <span className="text-green-600 text-xs">OK</span>
                                )}
                              </td>
                            )}
                            <td className="py-2 px-3">
                              <button
                                onClick={() => handleEditEntry(entry)}
                                className="text-gray-400 hover:text-tre-teal"
                                title="Edit entry"
                              >
                                <Edit2 className="w-4 h-4" />
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
            </>
          ) : activeJob?.result?.error_message ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-400" />
              <h3 className="font-medium text-gray-900 mb-1">Processing Failed</h3>
              <p className="text-sm text-gray-500">{activeJob.result.error_message}</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500">
              <FileSearch className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="font-medium">No job selected</p>
              <p className="text-sm mt-1">Upload a PDF or select a job from the history</p>
            </div>
          )}
        </div>
      </div>

      {/* Recent Jobs - shown at bottom when panel collapsed and no active results */}
      {panelCollapsed && !activeJob?.result && (
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

      {/* Mineral Export Modal */}
      <MineralExportModal
        isOpen={showMineralModal}
        onClose={() => setShowMineralModal(false)}
        onExport={handleExport}
        initialCounty={activeJob?.result?.case_metadata?.county || ''}
      />

      {/* Cancel Confirm Dialog */}
      <CancelConfirmDialog
        isOpen={cancelConfirmPending !== null}
        onKeepRunning={() => setCancelConfirmPending(null)}
        onCancelAndStart={() => {
          abortOperation()
          if (cancelConfirmPending) {
            startOperation(cancelConfirmPending)
          }
          setCancelConfirmPending(null)
        }}
      />

      {/* Edit Modal */}
      <Modal
        isOpen={!!editingEntry}
        onClose={() => setEditingEntry(null)}
        title={editingEntry ? `Edit Entry #${editingEntry.entry_number}` : ''}
        size="lg"
        footer={
          <>
            <button
              onClick={() => setEditingEntry(null)}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveEdit}
              className="px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors"
            >
              Save Changes
            </button>
          </>
        }
      >
        {editingEntry && (() => {
          // Determine which field triggered the flag
          const reason = editingEntry.flag_reason || ''
          const nameHighlight = reason.toLowerCase().includes('name') ? 'ring-2 ring-yellow-400 border-yellow-400 bg-yellow-50' : ''
          const addrHighlight = reason.toLowerCase().includes('address') ? 'ring-2 ring-yellow-400 border-yellow-400 bg-yellow-50' : ''
          const inputBase = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal'
          return (
          <div className="space-y-4">
            {editingEntry.flagged && editingEntry.flag_reason && (
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800 flex items-center gap-2">
                <Flag className="w-4 h-4 text-yellow-600 flex-shrink-0" />
                {editingEntry.flag_reason}
              </div>
            )}
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={editingEntry.primary_name}
                  onChange={(e) => setEditingEntry({ ...editingEntry, primary_name: e.target.value })}
                  className={`${inputBase} ${nameHighlight}`}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Owner Type</label>
                <select
                  value={editingEntry.entity_type}
                  onChange={(e) => setEditingEntry({ ...editingEntry, entity_type: e.target.value })}
                  className={inputBase}
                >
                  <option value="Individual">Individual</option>
                  <option value="Trust">Trust</option>
                  <option value="LLC">LLC</option>
                  <option value="Corporation">Corporation</option>
                  <option value="Partnership">Partnership</option>
                  <option value="Government">Government</option>
                  <option value="Estate">Estate</option>
                  <option value="Unknown Heirs">Unknown Heirs</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
              <input
                type="text"
                value={editingEntry.mailing_address || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, mailing_address: e.target.value })}
                className={`${inputBase} ${addrHighlight}`}
                placeholder="Street address"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Address 2</label>
              <input
                type="text"
                value={editingEntry.mailing_address_2 || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, mailing_address_2: e.target.value })}
                className={`${inputBase} ${addrHighlight}`}
                placeholder="Apt, Suite, Unit, etc."
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
                <input
                  type="text"
                  value={editingEntry.city || ''}
                  onChange={(e) => setEditingEntry({ ...editingEntry, city: e.target.value })}
                  className={`${inputBase} ${addrHighlight}`}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">State</label>
                <input
                  type="text"
                  value={editingEntry.state || ''}
                  onChange={(e) => setEditingEntry({ ...editingEntry, state: e.target.value.toUpperCase().slice(0, 2) })}
                  maxLength={2}
                  className={`${inputBase} ${addrHighlight}`}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ZIP</label>
                <input
                  type="text"
                  value={editingEntry.zip_code || ''}
                  onChange={(e) => setEditingEntry({ ...editingEntry, zip_code: e.target.value })}
                  maxLength={10}
                  className={`${inputBase} ${addrHighlight}`}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
              <input
                type="text"
                value={editingEntry.notes || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, notes: e.target.value })}
                className={inputBase}
              />
            </div>
          </div>
          )
        })()}
      </Modal>
      {deleteError && (
        <Modal isOpen={true} onClose={() => setDeleteError(null)} title="" size="sm">
          <div className="flex flex-col items-center text-center py-4">
            <ShieldAlert className="w-12 h-12 text-red-500 mb-4" />
            <h3 className="text-xl font-oswald font-semibold text-tre-navy mb-2">Unable to Delete</h3>
            <p className="text-gray-600 mb-6">{deleteError}</p>
            <button
              onClick={() => setDeleteError(null)}
              className="px-6 py-2 bg-tre-navy text-white rounded hover:bg-tre-navy/90 transition-colors font-oswald"
            >
              Got it
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
