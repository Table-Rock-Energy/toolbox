import { useState, useMemo, useEffect, useRef, useCallback } from 'react'
import { Calculator, Download, Upload, Users, AlertCircle, CheckCircle, AlertTriangle, Database, RefreshCw, Filter, Settings, Edit2, Columns, X, PanelLeftClose, PanelLeftOpen, Search, ShieldAlert } from 'lucide-react'
import { FileUpload, Modal, EnrichmentModal, UnifiedEnrichButton, CancelConfirmDialog, FetchRrcModal } from '../components'
import type { PostProcessResult } from '../utils/api'
import { useAuth } from '../contexts/AuthContext'
import { useOperationContext } from '../contexts/OperationContext'
import type { StartOperationOpts } from '../contexts/OperationContext'
import { useToolLayout } from '../hooks/useToolLayout'
import { useFeatureFlags } from '../hooks/useFeatureFlags'
import { usePreviewState } from '../hooks/usePreviewState'
import type { PipelineStatus, EnrichmentCellChange, PipelineStep } from '../hooks/useEnrichmentPipeline'

interface MineralHolderRow {
  _uid: string
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
  fetch_status?: 'found' | 'not_found' | 'multiple_matches' | 'split_lookup' | null
  sub_lease_results?: Array<{
    district: string
    lease_number: string
    status: 'found' | 'not_found'
    acres: number | null
  }> | null
}

interface CountyDownloadInfo {
  county_name: string
  status: 'fresh' | 'downloaded' | 'failed' | 'skipped'
  records_downloaded: number
  duration_seconds?: number
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
  county_downloads?: CountyDownloadInfo[]
  post_process?: PostProcessResult | null
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

interface RRCSyncJob {
  id: string
  status: 'downloading_oil' | 'downloading_gas' | 'syncing_oil' | 'syncing_gas' | 'complete' | 'failed'
  started_at: string
  completed_at: string | null
  oil_rows: number
  gas_rows: number
  error: string | null
  steps: Array<{
    step: string
    started_at: string
    completed_at: string | null
    message: string | null
  }>
}

interface ColumnConfig {
  key: string
  label: string
  alwaysVisible?: boolean
}

const COLUMNS: ColumnConfig[] = [
  { key: 'checkbox', label: '', alwaysVisible: true },
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
  const { user, userName, getIdToken } = useAuth()

  const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getIdToken()
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }, [getIdToken])
  const { panelCollapsed, setPanelCollapsed, togglePanel, activeStorageKey } = useToolLayout('proration', user?.uid, STORAGE_KEY_PREFIX)
  const [jobs, setJobs] = useState<ProrationJob[]>([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [activeJob, setActiveJob] = useState<ProrationJob | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
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
  const [, setIsDownloadingRRC] = useState(false)
  const [, setRrcMessage] = useState<string | null>(null)
  const [, setRrcSyncJob] = useState<RRCSyncJob | null>(null)
  const rrcPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Processing Options State
  const [showProcessingOptions, setShowProcessingOptions] = useState(false)
  const [newRecordOnly, setNewRecordOnly] = useState(false)
  const [deduplicateByPropertyId, setDeduplicateByPropertyId] = useState(false)
  const [minAppraisalValue, setMinAppraisalValue] = useState<number>(0)
  const [wellTypeOverride, setWellTypeOverride] = useState<string>('auto')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  // Enrichment feature flags
  const featureFlags = useFeatureFlags()

  // OperationContext
  const { operation, startOperation, abortOperation, undoOperation, clearOperation, getResultsForTool } = useOperationContext()
  const [cancelConfirmPending, setCancelConfirmPending] = useState<StartOperationOpts | null>(null)

  // Fetch missing RRC data state
  const [isFetchingMissing, setIsFetchingMissing] = useState(false)
  const [fetchMissingMessage, setFetchMissingMessage] = useState<string | null>(null)
  const [filterMode, setFilterMode] = useState<'all' | 'matched' | 'fetchable' | 'not_found'>('all')
  const [showFetchModal, setShowFetchModal] = useState(false)
  const [fetchProgress, setFetchProgress] = useState<{
    event: 'started' | 'progress' | 'complete'
    phase?: 'db_lookup' | 'rrc_query'
    checked?: number
    total?: number
    matched?: number
    matched_count?: number
    still_missing_count?: number
    updated_rows?: Record<string, unknown>[]
  } | null>(null)

  // Edit Row Modal State
  const [editingRow, setEditingRow] = useState<MineralHolderRow | null>(null)
  const [editingUid, setEditingUid] = useState<string | null>(null)
  const [isRetryingRrc, setIsRetryingRrc] = useState(false)

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

  // Check for active RRC download job on mount
  useEffect(() => {
    const checkActiveJob = async () => {
      try {
        const response = await fetch(`${API_BASE}/proration/rrc/download/active`, {
          headers: await authHeaders(),
        })
        if (response.ok) {
          const data = await response.json()
          // Check if data is a job object or has a job property
          const job = data.job !== undefined ? data.job : (data.id ? data : null)

          if (job && job.status && job.status !== 'complete' && job.status !== 'failed') {
            // Active job found - resume polling
            setRrcSyncJob(job)
            setIsDownloadingRRC(true)
            startPolling(job.id)
          } else if (job && job.status === 'complete') {
            // Recently completed job - show briefly
            setRrcSyncJob(job)
            setRrcMessage(`Successfully synced ${(job.oil_rows + job.gas_rows).toLocaleString()} records`)
          }
        }
      } catch (err) {
        console.error('Failed to check for active job:', err)
      }
    }
    checkActiveJob()

    // Clean up polling on unmount
    return () => {
      stopPolling()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Load recent jobs on mount
  useEffect(() => {
    const loadRecentJobs = async () => {
      try {
        const response = await fetch(`${API_BASE}/history/jobs?tool=proration&limit=20`, {
          headers: await authHeaders(),
        })
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
      } finally {
        setJobsLoading(false)
      }
    }
    loadRecentJobs()
  }, [authHeaders])


  // Categorize rows: matched, fetchable (has lease info), unfetchable (no lease info)
  const isUnfetchable = (r: MineralHolderRow) => !r.rrc_acres && r.notes === 'No valid RRC Lease #'
  const isFetchable = (r: MineralHolderRow) => !r.rrc_acres && r.notes !== 'No valid RRC Lease #'

  // Add stable _uid keys, sort missing RRC to top, apply filters
  const rowsWithKeys = useMemo(() => {
    if (!activeJob?.result?.rows) return []
    let rows = activeJob.result.rows.map((row, i) => ({
      ...row,
      _uid: row._uid ?? `pror-${i}`,
    }))

    // Sort: fetchable missing first (orange), unfetchable next (gray), matched last
    rows.sort((a, b) => {
      const aOrder = isFetchable(a) ? 0 : isUnfetchable(a) ? 1 : 2
      const bOrder = isFetchable(b) ? 0 : isUnfetchable(b) ? 1 : 2
      return aOrder - bOrder
    })

    if (filterMode === 'matched') {
      rows = rows.filter(r => !!r.rrc_acres)
    } else if (filterMode === 'fetchable') {
      rows = rows.filter(r => isFetchable(r))
    } else if (filterMode === 'not_found') {
      rows = rows.filter(r => isUnfetchable(r))
    }

    return rows
  }, [activeJob?.result?.rows, filterMode])

  // Preview state: exclusion, row sorting
  const preview = usePreviewState({
    entries: rowsWithKeys,
    keyField: '_uid' as keyof MineralHolderRow,
  })

  // OperationContext derived state
  const toolName = 'proration'
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
  const enrichModalOpen = operation?.tool === toolName && (operation.status === 'running' || operation.status === 'completed' || operation.status === 'error')

  // Map _uid → original (unfiltered) index for correct highlight lookup
  const entryOriginalIndex = useMemo(() => {
    const map = new Map<string, number>()
    if (activeJob?.result?.rows) {
      activeJob.result.rows.forEach((row, i) => {
        map.set(row._uid ?? `pror-${i}`, i)
      })
    }
    return map
  }, [activeJob?.result?.rows])

  const affectedEntryIndices = useMemo(() => {
    const indices = new Set<number>()
    enrichmentChanges.forEach(c => indices.add(c.entry_index))
    return indices
  }, [enrichmentChanges])

  const { editedFields } = preview
  const handleStartEnrichment = useCallback(() => {
    const allRows = (activeJob?.result?.rows ?? []).map((row, i) => ({
      ...row, _uid: row._uid ?? `pror-${i}`,
    }))
    const opts: StartOperationOpts = {
      tool: toolName,
      entries: allRows.map(e => ({...e} as Record<string, unknown>)),
      updateEntries: (entries) => {
        if (activeJob) {
          setActiveJob({
            ...activeJob,
            result: { ...activeJob.result!, rows: entries as unknown as MineralHolderRow[] },
          })
        }
      },
      editedFields: editedFields as Map<string, unknown>,
      keyField: '_uid',
      featureFlags,
    }
    if (operation?.status === 'running') {
      setCancelConfirmPending(opts)
    } else {
      startOperation(opts)
    }
  }, [activeJob, editedFields, featureFlags, operation?.status, startOperation])

  // Auto-restore enriched entries on mount (PERSIST-01)
  useEffect(() => {
    const results = getResultsForTool(toolName)
    if (results && activeJob) {
      setTimeout(() => {
        setActiveJob({
          ...activeJob,
          result: { ...activeJob.result!, rows: results as unknown as MineralHolderRow[] },
        })
        clearOperation()
      }, 0)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-collapse panel when preview data loads
  useEffect(() => {
    if (activeJob?.result?.rows?.length) setPanelCollapsed(true)
  }, [activeJob?.result?.rows, setPanelCollapsed])

  const startPolling = (jobId: string) => {
    // Clear any existing poll interval
    stopPolling()

    // Poll every 3 seconds
    rrcPollRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/proration/rrc/download/${jobId}/status`, {
          headers: await authHeaders(),
        })
        if (response.ok) {
          const job: RRCSyncJob = await response.json()
          setRrcSyncJob(job)

          // Stop polling if terminal status
          if (job.status === 'complete') {
            stopPolling()
            setIsDownloadingRRC(false)
            // Refresh RRC status to get new counts
            await checkRRCStatus()
            setRrcMessage(`Successfully synced ${(job.oil_rows + job.gas_rows).toLocaleString()} records`)
          } else if (job.status === 'failed') {
            stopPolling()
            setIsDownloadingRRC(false)
            setError(job.error || 'Download failed')
          }
        }
      } catch (err) {
        console.error('Failed to poll job status:', err)
      }
    }, 3000)
  }

  const stopPolling = () => {
    if (rrcPollRef.current) {
      clearInterval(rrcPollRef.current)
      rrcPollRef.current = null
    }
  }

  const checkRRCStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/proration/rrc/status`, {
        headers: await authHeaders(),
      })
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

      const hdrs = await authHeaders()
      const response = await fetch(`${API_BASE}/proration/upload`, {
        method: 'POST',
        headers: {
          ...hdrs,
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
      if (data.result?.job_id) {
        newJob.job_id = data.result.job_id
      }

      setJobs((prev) => [newJob, ...prev])
      setActiveJob(newJob)
      setSelectedFile(null)
      setFetchMissingMessage(null)
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
    if (preview.entriesToExport.length === 0 || !activeJob) return

    try {
      const hdrs = await authHeaders()
      const response = await fetch(`${API_BASE}/proration/export/${format}`, {
        method: 'POST',
        headers: {
          ...hdrs,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rows: preview.entriesToExport,
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
    setFetchMissingMessage(null)

    // Lazy-load entries if not already loaded
    if (!job.result?.rows && job.job_id) {
      setIsLoadingEntries(true)
      try {
        const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}/entries`, {
          headers: await authHeaders(),
        })
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
      const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}`, {
        method: 'DELETE',
        headers: await authHeaders(),
      })
      if (response.status === 403) {
        setDeleteError('You can only delete jobs you created. Contact an admin if this job needs to be removed.')
        return
      }
      if (!response.ok) return
      setJobs((prev) => prev.filter((j) => j.id !== job.id))
      if (activeJob?.id === job.id) setActiveJob(null)
    } catch { /* network error, best-effort */ }
  }

  const handleEditRow = (row: MineralHolderRow) => {
    setEditingRow({ ...row })
    setEditingUid(row._uid ?? null)
  }

  const handleSaveEdit = () => {
    if (editingRow === null || editingUid === null || !activeJob?.result?.rows) return

    const updatedRows = activeJob.result.rows.map((r, i) => {
      const uid = r._uid ?? `pror-${i}`
      return uid === editingUid ? editingRow : r
    })

    setActiveJob({
      ...activeJob,
      result: {
        ...activeJob.result,
        rows: updatedRows,
      },
    })

    setEditingRow(null)
    setEditingUid(null)
  }

  const handleCancelEdit = () => {
    setEditingRow(null)
    setEditingUid(null)
    setIsRetryingRrc(false)
  }

  const handleRetryRrcLookup = async () => {
    if (!editingRow || !editingRow.district || !editingRow.lease_number) return
    setIsRetryingRrc(true)
    try {
      const hdrs = await authHeaders()
      const response = await fetch(`${API_BASE}/proration/rrc/fetch-missing`, {
        method: 'POST',
        headers: { ...hdrs, 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: [editingRow] }),
      })
      if (!response.ok) throw new Error('RRC lookup failed')
      const result = await response.json()
      if (result.updated_rows?.[0]) {
        const updated = result.updated_rows[0]
        setEditingRow(updated)
        if (updated.rrc_acres) {
          setFetchMissingMessage(`Found: ${updated.rrc_acres} acres`)
        } else {
          setFetchMissingMessage('No RRC data found for this lease')
        }
      }
    } catch {
      setFetchMissingMessage('RRC lookup failed')
    } finally {
      setIsRetryingRrc(false)
    }
  }

  const handleFetchMissing = async () => {
    if (!activeJob?.result?.rows) return

    const unmatchedRows = activeJob.result.rows.filter(r => !r.rrc_acres)
    if (unmatchedRows.length === 0) return

    setIsFetchingMissing(true)
    setFetchMissingMessage(null)
    setError(null)
    setShowFetchModal(true)
    setFetchProgress({ event: 'started', total: unmatchedRows.length })

    try {
      const hdrs = await authHeaders()
      const response = await fetch(`${API_BASE}/proration/rrc/fetch-missing`, {
        method: 'POST',
        headers: { ...hdrs, 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: unmatchedRows }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to fetch missing data')
      }

      // Read NDJSON stream
      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let finalResult: { matched_count: number; still_missing_count: number; updated_rows: MineralHolderRow[] } | null = null

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          // Process complete lines
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (!line.trim()) continue
            try {
              const event = JSON.parse(line)
              setFetchProgress(event)
              if (event.event === 'complete') {
                finalResult = event
              }
            } catch { /* skip malformed lines */ }
          }
        }
        // Process remaining buffer
        if (buffer.trim()) {
          try {
            const event = JSON.parse(buffer)
            setFetchProgress(event)
            if (event.event === 'complete') {
              finalResult = event
            }
          } catch { /* skip */ }
        }
      }

      if (finalResult) {
        // Merge updated rows back into the full row list
        const updatedMap = new Map<string, MineralHolderRow>()
        for (const row of finalResult.updated_rows) {
          const key = `${row.owner}|${row.county}|${row.rrc_lease || row.raw_rrc || ''}`
          updatedMap.set(key, row)
        }

        const mergedRows = activeJob.result.rows.map(row => {
          if (row.rrc_acres) return row
          const key = `${row.owner}|${row.county}|${row.rrc_lease || row.raw_rrc || ''}`
          return updatedMap.get(key) || row
        })

        setActiveJob({
          ...activeJob,
          result: {
            ...activeJob.result,
            rows: mergedRows,
            matched_rows: mergedRows.filter(r => r.rrc_acres).length,
          },
        })

        const foundCount = finalResult.updated_rows.filter((r: MineralHolderRow) => r.fetch_status === 'found' || r.fetch_status === 'split_lookup').length
        const notFoundCount = finalResult.updated_rows.filter((r: MineralHolderRow) => r.fetch_status === 'not_found').length
        const parts: string[] = []
        if (foundCount > 0) parts.push(`found ${foundCount}`)
        if (notFoundCount > 0) parts.push(`not found ${notFoundCount}`)
        setFetchMissingMessage(parts.length > 0 ? parts.join(', ') : 'No additional RRC data found')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch missing data')
      setShowFetchModal(false)
    } finally {
      setIsFetchingMissing(false)
    }
  }

  const STEP_SOURCE_LABELS: Record<string, string> = { cleanup: 'AI Cleanup', validate: 'Google Maps', enrich: 'Enrichment' }
  const getCellHighlight = (entryIndex: number, field: string) => {
    return enrichmentChanges.get(`${entryIndex}:${field}`) || null
  }
  const formatHighlightTitle = (hl: EnrichmentCellChange) => {
    const source = STEP_SOURCE_LABELS[hl.step] || hl.step
    return `Was: ${hl.original_value || '(empty)'} → Changed by ${source}`
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


  const hasDBData = (rrcStatus?.db_oil_rows || 0) + (rrcStatus?.db_gas_rows || 0) > 0

  // Use DB counts when available, fall back to CSV counts
  const totalRecords = hasDBData
    ? (rrcStatus?.db_oil_rows || 0) + (rrcStatus?.db_gas_rows || 0)
    : (rrcStatus?.oil_rows || 0) + (rrcStatus?.gas_rows || 0)
  const oilRecords = hasDBData ? (rrcStatus?.db_oil_rows || 0) : (rrcStatus?.oil_rows || 0)
  const gasRecords = hasDBData ? (rrcStatus?.db_gas_rows || 0) : (rrcStatus?.gas_rows || 0)


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

      {/* Upload Section - compact row when panel collapsed and no active results */}
      {panelCollapsed && !activeJob?.result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          {/* RRC Data Status */}
          {rrcLoading ? (
            <div className="flex items-center gap-2 mb-3 animate-pulse">
              <Database className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
              <span className="text-xs text-gray-400">Loading RRC status...</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 mb-3">
              <Database className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
              <span className="text-xs text-green-700">
                <span className="font-medium">{totalRecords.toLocaleString()}</span> RRC records
                <span className="text-green-600 ml-1">({oilRecords.toLocaleString()} oil, {gasRecords.toLocaleString()} gas)</span>
              </span>
            </div>
          )}
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
            {/* RRC Data Status */}
            {rrcLoading ? (
              <div className="flex items-center gap-2 mb-3 animate-pulse">
                <Database className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                <span className="text-xs text-gray-400">Loading RRC status...</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 mb-3">
                <Database className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
                <span className="text-xs text-green-700">
                  <span className="font-medium">{totalRecords.toLocaleString()}</span> RRC records
                  <span className="text-green-600 ml-1">({oilRecords.toLocaleString()} oil, {gasRecords.toLocaleString()} gas)</span>
                </span>
              </div>
            )}
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
            {jobsLoading ? (
              <div className="p-4 space-y-3 animate-pulse">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-12 bg-gray-100 rounded" />
                ))}
              </div>
            ) : jobs.length === 0 ? (
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
                      onClick={() => handleExport('excel')}
                      className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      Export
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

              {/* Stats — click to filter */}
              {(() => {
                const rows = activeJob.result.rows || []
                const totalCount = activeJob.result.total_rows || rows.length
                const matchedCount = rows.filter(r => r.rrc_acres).length
                const fetchableCount = rows.filter(r => isFetchable(r)).length
                const unfetchableCount = rows.filter(r => isUnfetchable(r)).length
                const toggle = (mode: typeof filterMode) => setFilterMode(prev => prev === mode ? 'all' : mode)
                return (
                  <div className="grid grid-cols-5 gap-4 p-6 border-b border-gray-100">
                    <button onClick={() => setFilterMode('all')} className={`text-center rounded-lg py-2 transition-colors ${filterMode === 'all' ? 'bg-tre-navy/5 ring-1 ring-tre-navy/20' : 'hover:bg-gray-50'}`}>
                      <p className="text-2xl font-oswald font-semibold text-tre-navy">
                        {totalCount}
                      </p>
                      <p className="text-sm text-gray-500">Total Rows</p>
                    </button>
                    <button onClick={() => toggle('matched')} className={`text-center rounded-lg py-2 transition-colors ${filterMode === 'matched' ? 'bg-green-50 ring-1 ring-green-200' : 'hover:bg-gray-50'}`}>
                      <p className="text-2xl font-oswald font-semibold text-green-600">
                        {matchedCount}
                      </p>
                      <p className="text-sm text-gray-500">RRC Matched</p>
                    </button>
                    <button onClick={() => toggle('fetchable')} className={`text-center rounded-lg py-2 transition-colors ${filterMode === 'fetchable' ? 'bg-orange-50 ring-1 ring-orange-200' : 'hover:bg-gray-50'}`}>
                      <p className={`text-2xl font-oswald font-semibold ${fetchableCount > 0 ? 'text-orange-500' : 'text-gray-400'}`}>
                        {fetchableCount}
                      </p>
                      <p className="text-sm text-gray-500">Fetchable</p>
                    </button>
                    <button onClick={() => toggle('not_found')} className={`text-center rounded-lg py-2 transition-colors ${filterMode === 'not_found' ? 'bg-gray-100 ring-1 ring-gray-300' : 'hover:bg-gray-50'}`}>
                      <p className={`text-2xl font-oswald font-semibold ${unfetchableCount > 0 ? 'text-gray-500' : 'text-gray-400'}`}>
                        {unfetchableCount}
                      </p>
                      <p className="text-sm text-gray-500">No Lease #</p>
                    </button>
                    <div className="text-center py-2">
                      <p className="text-2xl font-oswald font-semibold text-tre-teal">
                        {preview.entriesToExport.length}
                      </p>
                      <p className="text-sm text-gray-500">Selected</p>
                    </div>
                  </div>
                )
              })()}

              {/* County Download Summary */}
              {activeJob.result.county_downloads && activeJob.result.county_downloads.length > 0 && (
                <div className="px-6 py-3 border-b border-gray-100 bg-gray-50/50">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wide mr-1">RRC Data:</span>
                    {activeJob.result.county_downloads.map((cd, idx) => (
                      <span
                        key={idx}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                          cd.status === 'fresh'
                            ? 'bg-green-100 text-green-700'
                            : cd.status === 'downloaded'
                              ? 'bg-blue-100 text-blue-700'
                              : cd.status === 'failed'
                                ? 'bg-yellow-100 text-yellow-700'
                                : 'bg-gray-100 text-gray-600'
                        }`}
                        title={
                          cd.status === 'downloaded'
                            ? `${cd.records_downloaded.toLocaleString()} records in ${cd.duration_seconds}s`
                            : cd.status === 'fresh'
                              ? 'Already had current data'
                              : cd.status === 'failed'
                                ? 'Download failed, proceeded without'
                                : 'Skipped due to time budget'
                        }
                      >
                        {cd.status === 'fresh' && <CheckCircle className="w-3 h-3" />}
                        {cd.status === 'downloaded' && <Download className="w-3 h-3" />}
                        {cd.status === 'failed' && <AlertTriangle className="w-3 h-3" />}
                        {cd.county_name}
                        {cd.status === 'downloaded' && cd.records_downloaded > 0 && (
                          <span className="text-[10px] opacity-75">({cd.records_downloaded.toLocaleString()})</span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Unmatched Rows Banner */}
              {(() => {
                const unmatchedCount = activeJob.result.rows?.filter(r => !r.rrc_acres).length || 0
                if (unmatchedCount === 0) return null
                return (
                  <div className="px-6 py-3 border-b border-gray-100 bg-orange-50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-orange-500" />
                        <span className="text-sm text-orange-800">
                          <span className="font-medium">{unmatchedCount}</span> row{unmatchedCount !== 1 ? 's' : ''} missing RRC data
                          {fetchMissingMessage && (
                            <span className="ml-2 text-orange-600">&bull; {fetchMissingMessage}</span>
                          )}
                        </span>
                      </div>
                      <button
                        onClick={handleFetchMissing}
                        disabled={isFetchingMissing}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                          isFetchingMissing
                            ? 'bg-orange-200 text-orange-600 cursor-not-allowed'
                            : 'bg-orange-600 text-white hover:bg-orange-700'
                        }`}
                      >
                        {isFetchingMissing ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            Fetching from RRC...
                          </>
                        ) : (
                          <>
                            <Search className="w-3.5 h-3.5" />
                            Fetch from RRC
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                )
              })()}

              {/* Preview Table */}
              <div className="p-6">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900 flex items-center gap-2">
                    <Users className="w-4 h-4" />
                    Proration Preview
                    {filterMode !== 'all' && (
                      <span className="text-xs font-normal text-gray-500 ml-1">
                        ({rowsWithKeys.length} shown)
                      </span>
                    )}
                  </h4>
                  <div className="flex items-center gap-2">
                    {/* Inline filter pills */}
                    {(['all', 'matched', 'fetchable', 'not_found'] as const).map(mode => {
                      const labels: Record<typeof mode, string> = { all: 'All', matched: 'Matched', fetchable: 'Fetchable', not_found: 'No Lease #' }
                      const colors: Record<typeof mode, string> = {
                        all: filterMode === 'all' ? 'bg-tre-navy text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
                        matched: filterMode === 'matched' ? 'bg-green-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
                        fetchable: filterMode === 'fetchable' ? 'bg-orange-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
                        not_found: filterMode === 'not_found' ? 'bg-gray-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
                      }
                      return (
                        <button
                          key={mode}
                          onClick={() => setFilterMode(prev => prev === mode && mode !== 'all' ? 'all' : mode)}
                          className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${colors[mode]}`}
                        >
                          {labels[mode]}
                        </button>
                      )
                    })}
                  </div>
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
                      {(() => {
                        // Build display list with original indices, sort changed rows to top
                        const indexed = preview.previewEntries.map((entry) => ({
                          entry,
                          globalIdx: entryOriginalIndex.get(entry._uid ?? '') ?? -1,
                        }))
                        if (affectedEntryIndices.size > 0) {
                          indexed.sort((a, b) => {
                            const aChanged = affectedEntryIndices.has(a.globalIdx) ? 0 : 1
                            const bChanged = affectedEntryIndices.has(b.globalIdx) ? 0 : 1
                            return aChanged - bChanged
                          })
                        }
                        return indexed
                      })().map(({ entry: row, globalIdx: rowIdx }) => {
                        const rowKey = row._uid ?? ''
                        const isExcluded = preview.isExcluded(rowKey)
                        const hasChanges = affectedEntryIndices.has(rowIdx)
                        const rowUnfetchable = isUnfetchable(row)
                        const rowFetchable = isFetchable(row)
                        return (
                        <tr key={rowKey} className={`${hasChanges ? 'bg-blue-50' : rowUnfetchable ? 'bg-gray-100' : rowFetchable ? 'bg-orange-50' : row.fetch_status === 'multiple_matches' ? 'bg-yellow-50' : ''} ${isExcluded ? 'opacity-50 bg-gray-100' : ''} transition-colors duration-[2000ms]`}>
                          <td className="py-2 px-3">
                            <input
                              type="checkbox"
                              checked={!isExcluded}
                              onChange={() => preview.toggleExclude(rowKey)}
                              className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                            />
                          </td>
                          {isColumnVisible('owner') && (() => {
                            const hl = getCellHighlight(rowIdx, 'owner')
                            return (
                            <td className={`py-2 px-3 text-gray-900 whitespace-nowrap ${hl ? 'bg-green-50' : ''}`} title={hl ? formatHighlightTitle(hl) : undefined}>
                              {row.owner}
                            </td>
                            )
                          })()}
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
                              <span className="inline-flex items-center gap-1">
                                {formatNumber(row.rrc_acres, 2)}
                                {row.fetch_status === 'found' && <span title="RRC data found"><CheckCircle className="w-3.5 h-3.5 text-green-500" /></span>}
                                {row.fetch_status === 'split_lookup' && (
                                  <span title={row.sub_lease_results?.map(s =>
                                      `${s.district}-${s.lease_number}: ${s.status}${s.acres ? ` (${s.acres} acres)` : ''}`
                                    ).join('\n') || 'Split lookup'}>
                                    <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                                  </span>
                                )}
                                {row.fetch_status === 'not_found' && <span title="Not found in RRC"><X className="w-3.5 h-3.5 text-red-400" /></span>}
                                {row.fetch_status === 'multiple_matches' && <span title="Multiple RRC matches"><AlertTriangle className="w-3.5 h-3.5 text-amber-500" /></span>}
                              </span>
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
                          {isColumnVisible('notes') && (
                            <td className="py-2 px-3 text-gray-600 text-xs max-w-[200px]">
                              {row.notes?.includes('|http') ? (
                                <>
                                  <span>{row.notes.split('|')[0]}</span>
                                  {' '}
                                  <a
                                    href={row.notes.split('|')[1]}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-tre-teal hover:underline"
                                  >
                                    Verify on RRC
                                  </a>
                                </>
                              ) : (
                                <span className="truncate block" title={row.notes}>{row.notes || '\u2014'}</span>
                              )}
                            </td>
                          )}
                          <td className="py-2 px-3 text-center">
                            <button
                              onClick={() => handleEditRow(row)}
                              className="p-1 rounded hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600"
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

      {/* Fetch RRC Progress Modal */}
      <FetchRrcModal
        isOpen={showFetchModal}
        onClose={() => setShowFetchModal(false)}
        progress={fetchProgress}
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
            {editingRow && !editingRow.rrc_acres && editingRow.district && editingRow.lease_number && (
              <button
                onClick={handleRetryRrcLookup}
                disabled={isRetryingRrc}
                className="px-4 py-2 bg-tre-teal text-tre-navy rounded-lg text-sm hover:bg-tre-teal/80 transition-colors disabled:opacity-50 flex items-center gap-1"
              >
                {isRetryingRrc ? <RefreshCw size={14} className="animate-spin" /> : <Search size={14} />}
                {isRetryingRrc ? 'Looking up...' : 'Retry RRC Lookup'}
              </button>
            )}
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
            <div className="col-span-2 border-t pt-3 mt-1">
              <label className="block text-sm font-semibold text-tre-navy mb-2">RRC Lease Info</label>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">District</label>
                  <input
                    type="text"
                    value={editingRow.district || ''}
                    onChange={(e) => setEditingRow({ ...editingRow, district: e.target.value })}
                    placeholder="e.g. 08"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Lease Number</label>
                  <input
                    type="text"
                    value={editingRow.lease_number || ''}
                    onChange={(e) => setEditingRow({ ...editingRow, lease_number: e.target.value })}
                    placeholder="e.g. 33286"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">RRC Lease (raw)</label>
                  <input
                    type="text"
                    value={editingRow.rrc_lease || ''}
                    onChange={(e) => setEditingRow({ ...editingRow, rrc_lease: e.target.value })}
                    placeholder="e.g. 08-33286"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-tre-teal focus:border-tre-teal"
                  />
                </div>
              </div>
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
