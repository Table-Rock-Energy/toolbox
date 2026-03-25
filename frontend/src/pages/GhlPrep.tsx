import { useState, useEffect, useMemo, useCallback } from 'react'
import { Repeat, Download, Upload, AlertCircle, Send, XCircle, FileWarning, Pencil, CheckCircle, X, PanelLeftClose, PanelLeftOpen, ShieldAlert } from 'lucide-react'
import { FileUpload, GhlSendModal, Modal } from '../components'
import { useAuth } from '../contexts/AuthContext'
import { useToolLayout } from '../hooks/useToolLayout'
import { ghlApi } from '../utils/api'
import type { GhlConnectionResponse, FailedContactDetail, DailyRateLimitInfo } from '../utils/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const STORAGE_KEY_PREFIX = 'ghl-prep-visible-columns'

interface TransformResult {
  success: boolean
  rows: Record<string, string>[]
  total_count: number
  flagged_rows: Record<string, string>[]
  flagged_count: number
  transformed_fields: {
    title_cased: number
    campaigns_extracted: number
    phone_mapped: number
    contact_owner_added: number
    flagged: number
  }
  warnings: string[]
  source_filename: string
  campaign_name?: string
  job_id?: string
}

interface UploadResponse {
  message: string
  result?: TransformResult
}

interface GhlPrepJob {
  id: string
  job_id?: string
  documentName: string
  user: string
  timestamp: string
  result?: TransformResult
}

type ViewMode = 'normal' | 'flagged' | 'failed-contacts'

export default function GhlPrep() {
  const { user, userName, getToken } = useAuth()
  const { panelCollapsed, setPanelCollapsed, togglePanel } = useToolLayout('ghl-prep', user?.id, STORAGE_KEY_PREFIX)

  const authHeaders = useCallback((): Record<string, string> => {
    const token = getToken()
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }, [getToken])

  const [jobs, setJobs] = useState<GhlPrepJob[]>([])
  const [activeJob, setActiveJob] = useState<GhlPrepJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [isLoadingJobs, setIsLoadingJobs] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sortColumn, setSortColumn] = useState<string | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [connections, setConnections] = useState<GhlConnectionResponse[]>([])
  const [showSendModal, setShowSendModal] = useState(false)
  const [dailyLimit, setDailyLimit] = useState<DailyRateLimitInfo | null>(null)

  // Active GHL job tracking (stored in localStorage for persistence)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)

  // Failed contacts management
  const [viewMode, setViewMode] = useState<ViewMode>('normal')
  const [failedContacts, setFailedContacts] = useState<FailedContactDetail[]>([])
  const [showIndividualsOnly, setShowIndividualsOnly] = useState(false)

  // Row exclusion (checkboxes)
  const [excludedRows, setExcludedRows] = useState<Set<number>>(new Set())

  // Inline editing
  const [editingRow, setEditingRow] = useState<Record<string, string> | null>(null)
  const [editingIndex, setEditingIndex] = useState<number>(-1)

  // Convenience: derive result from activeJob
  const result = activeJob?.result ?? null

  // Auto-collapse panel when preview data loads
  useEffect(() => {
    if (result) setPanelCollapsed(true)
  }, [result, setPanelCollapsed])

  // Load recent jobs from Firestore on mount
  useEffect(() => {
    const loadJobs = async () => {
      setIsLoadingJobs(true)
      try {
        const hdrs = authHeaders()
        const response = await fetch(`${API_BASE}/history/jobs?tool=ghl-prep&limit=20`, { headers: hdrs })
        if (!response.ok) return
        const data = await response.json()
        const jobsArray = data.jobs || (Array.isArray(data) ? data : [])
        if (jobsArray.length > 0) {
          const loaded: GhlPrepJob[] = jobsArray.map((j: Record<string, unknown>) => ({
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
        // Firestore unavailable — continue with empty list
      } finally {
        setIsLoadingJobs(false)
      }
    }
    loadJobs()
  }, [authHeaders])

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

  // Fetch daily limit info after connections load
  useEffect(() => {
    const fetchDailyLimit = async () => {
      if (connections.length === 0) return
      const res = await ghlApi.getDailyLimit()
      if (res.data) {
        setDailyLimit(res.data)
      }
    }
    fetchDailyLimit()
  }, [connections])

  // Check for active GHL send job on mount
  useEffect(() => {
    const checkActiveJob = async () => {
      const storedJobId = localStorage.getItem('ghl_active_job_id')
      if (!storedJobId) return

      try {
        const res = await ghlApi.getJobStatus(storedJobId)
        if (res.data) {
          if (res.data.status === 'processing') {
            setActiveJobId(storedJobId)
            setShowSendModal(true)
          } else {
            localStorage.removeItem('ghl_active_job_id')
          }
        }
      } catch (err) {
        console.error('Failed to check active job:', err)
        localStorage.removeItem('ghl_active_job_id')
      }
    }

    checkActiveJob()
  }, [])

  const handleSelectJob = async (job: GhlPrepJob) => {
    setActiveJob(job)
    setError(null)
    setViewMode('normal')
    setFailedContacts([])
    setExcludedRows(new Set())
    setSortColumn(null)
    setSortDirection('asc')
  }

  const handleDeleteJob = async (e: React.MouseEvent, job: GhlPrepJob) => {
    e.stopPropagation()
    if (!job.job_id) {
      setJobs((prev) => prev.filter((j) => j.id !== job.id))
      if (activeJob?.id === job.id) setActiveJob(null)
      return
    }
    try {
      const hdrs = authHeaders()
      const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}`, { method: 'DELETE', headers: hdrs })
      if (response.status === 403) {
        setDeleteError('You can only delete jobs you created. Contact an admin if this job needs to be removed.')
        return
      }
      if (!response.ok) return
      setJobs((prev) => prev.filter((j) => j.id !== job.id))
      if (activeJob?.id === job.id) setActiveJob(null)
    } catch { /* network error, best-effort */ }
  }

  // Get dynamic columns from current data (normal result, flagged, or failed contacts)
  const columns = useMemo(() => {
    if (viewMode === 'failed-contacts' && failedContacts.length > 0) {
      const firstContact = failedContacts[0].contact_data
      const keys = Object.keys(firstContact)
      return [...keys, 'Error Category', 'Error Message']
    }

    if (viewMode === 'flagged' && result?.flagged_rows && result.flagged_rows.length > 0) {
      return Object.keys(result.flagged_rows[0])
    }

    if (!result?.rows || result.rows.length === 0) return []
    return Object.keys(result.rows[0])
  }, [result, viewMode, failedContacts])

  // Current rows being displayed
  const currentRows: Record<string, string>[] = useMemo(() => {
    if (viewMode === 'failed-contacts' && failedContacts.length > 0) {
      return failedContacts.map(fc => ({
        ...fc.contact_data,
        'Error Category': fc.error_category as string,
        'Error Message': fc.error_message,
      }))
    }
    if (viewMode === 'flagged') {
      return result?.flagged_rows || []
    }
    return result?.rows || []
  }, [result, viewMode, failedContacts])

  const filteredRows = useMemo(() => {
    if (!showIndividualsOnly) return currentRows
    return currentRows.filter(row => row['Entity Type'] === 'Individual')
  }, [currentRows, showIndividualsOnly])

  // Derive campaign name from transform result metadata
  const defaultTag = result?.campaign_name || ''

  // Sort rows client-side
  const sortedRows = useMemo(() => {
    if (filteredRows.length === 0 || !sortColumn) return filteredRows

    const sorted = [...filteredRows].sort((a, b) => {
      const aVal = a[sortColumn] || ''
      const bVal = b[sortColumn] || ''

      if (sortDirection === 'asc') {
        return String(aVal).localeCompare(String(bVal))
      } else {
        return String(bVal).localeCompare(String(aVal))
      }
    })

    return sorted
  }, [filteredRows, sortColumn, sortDirection])

  const handleColumnClick = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(column)
      setSortDirection('asc')
    }
  }

  // Row exclusion toggle
  const toggleRow = (index: number) => {
    const next = new Set(excludedRows)
    if (next.has(index)) next.delete(index)
    else next.add(index)
    setExcludedRows(next)
  }

  // Select-all checkbox state
  const isAllSelected = useMemo(() => {
    if (sortedRows.length === 0) return false
    return excludedRows.size === 0
  }, [sortedRows.length, excludedRows.size])

  const isSomeSelected = useMemo(() => {
    if (sortedRows.length === 0) return false
    return excludedRows.size > 0 && excludedRows.size < sortedRows.length
  }, [sortedRows.length, excludedRows.size])

  const toggleSelectAll = () => {
    if (isAllSelected) {
      setExcludedRows(new Set(sortedRows.map((_, i) => i)))
    } else {
      setExcludedRows(new Set())
    }
  }

  // Included rows count (for display)
  const includedCount = sortedRows.length - excludedRows.size

  // Edit row handlers
  const handleEditRow = (row: Record<string, string>, index: number) => {
    setEditingRow({ ...row })
    setEditingIndex(index)
  }

  const handleSaveEdit = () => {
    if (!editingRow || editingIndex < 0 || !result || !activeJob) return

    const updatedRows = [...result.rows]
    const originalRow = sortedRows[editingIndex]
    const realIndex = result.rows.findIndex(r =>
      r['M1neral Contact System ID'] === originalRow['M1neral Contact System ID'] &&
      r['First Name'] === originalRow['First Name'] &&
      r['Last Name'] === originalRow['Last Name']
    )

    if (realIndex >= 0) {
      updatedRows[realIndex] = editingRow
      const updatedResult = { ...result, rows: updatedRows }
      const updatedJob = { ...activeJob, result: updatedResult }
      setActiveJob(updatedJob)
      setJobs((prev) => prev.map((j) => j.id === activeJob.id ? updatedJob : j))
    }

    setEditingRow(null)
    setEditingIndex(-1)
  }

  const handleFilesSelected = async (files: File[]) => {
    if (files.length === 0) return

    const file = files[0]
    setIsProcessing(true)
    setError(null)
    setViewMode('normal')
    setFailedContacts([])
    setExcludedRows(new Set())

    const newJob: GhlPrepJob = {
      id: String(Date.now()),
      documentName: file.name,
      user: user?.displayName || user?.email || 'Unknown',
      timestamp: new Date().toLocaleString(),
    }

    try {
      const formData = new FormData()
      formData.append('file', file)

      const hdrs = authHeaders()
      const response = await fetch(`${API_BASE}/ghl-prep/upload`, {
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
      if (data.result) {
        newJob.result = data.result
        newJob.job_id = data.result.job_id
      }

      setJobs((prev) => [newJob, ...prev])
      setActiveJob(newJob)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process file')
      newJob.result = {
        success: false,
        rows: [],
        total_count: 0,
        flagged_rows: [],
        flagged_count: 0,
        transformed_fields: {
          title_cased: 0,
          campaigns_extracted: 0,
          phone_mapped: 0,
          contact_owner_added: 0,
          flagged: 0,
        },
        warnings: [],
        source_filename: file.name,
      }
      setJobs((prev) => [newJob, ...prev])
    } finally {
      setIsProcessing(false)
    }
  }

  const handleExport = async () => {
    if (!result?.rows || result.rows.length === 0) {
      setError('No data to export')
      return
    }

    const exportRows = sortedRows
      .filter((_, i) => !excludedRows.has(i))
      .map(
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        ({ 'Entity Type': _entityType, ...rest }) => rest
      )

    try {
      const hdrs = authHeaders()
      const response = await fetch(`${API_BASE}/ghl-prep/export/csv`, {
        method: 'POST',
        headers: {
          ...hdrs,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rows: exportRows,
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

  // Download flagged rows as Mineral update report
  const handleExportFlagged = async () => {
    if (!result?.flagged_rows || result.flagged_rows.length === 0) {
      setError('No flagged rows to export')
      return
    }

    try {
      const hdrs = authHeaders()
      const response = await fetch(`${API_BASE}/ghl-prep/export/flagged-csv`, {
        method: 'POST',
        headers: { ...hdrs, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rows: result.flagged_rows,
          filename: result.source_filename?.replace(/\.[^.]+$/, '') || 'mineral_export',
        }),
      })

      if (!response.ok) throw new Error('Export failed')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const baseName = result.source_filename?.replace(/\.[^.]+$/, '') || 'mineral_export'
      a.download = `${baseName}_mineral_updates.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch {
      setError('Failed to export flagged rows')
    }
  }

  // Download failed contacts as CSV
  const handleExportFailedContacts = () => {
    if (failedContacts.length === 0) {
      setError('No failed contacts to export')
      return
    }

    const headers = [
      'Mineral Contact System Id',
      'First Name',
      'Last Name',
      'Email',
      'Phone',
      'Phone 1',
      'Phone 2',
      'Phone 3',
      'Phone 4',
      'Phone 5',
      'Address 1',
      'City',
      'State',
      'County',
      'Territory',
      'Postal Code',
      'Campaign Name',
      'Bankruptcy',
      'Deceased',
      'Lien',
      'Campaign System Id',
      'Error Category',
      'Error Message',
    ]

    const rows = failedContacts.map(fc => {
      const cd = fc.contact_data
      return [
        cd.mineral_contact_system_id || '',
        cd.first_name || '',
        cd.last_name || '',
        cd.email || '',
        cd.phone || '',
        cd.phone_1 || '',
        cd.phone_2 || '',
        cd.phone_3 || '',
        cd.phone_4 || '',
        cd.phone_5 || '',
        cd.address1 || '',
        cd.city || '',
        cd.state || '',
        cd.county || '',
        cd.territory || '',
        cd.postal_code || '',
        cd.campaign_name || '',
        cd.bankruptcy || '',
        cd.deceased || '',
        cd.lien || '',
        cd.campaign_system_id || '',
        fc.error_category,
        fc.error_message,
      ]
    })

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(',')),
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'failed_contacts.csv'
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  const handleReset = () => {
    setActiveJob(null)
    setError(null)
    setSortColumn(null)
    setSortDirection('asc')
    setViewMode('normal')
    setFailedContacts([])
    setShowIndividualsOnly(false)
    setExcludedRows(new Set())
  }

  // Handle viewing failed contacts from send modal
  const handleViewFailedContacts = (contacts: FailedContactDetail[]) => {
    setFailedContacts(contacts)
    setViewMode('failed-contacts')
    setShowSendModal(false)
  }

  // Back to normal view
  const handleBackToNormalView = () => {
    setViewMode('normal')
    setFailedContacts([])
  }

  // Retry send with failed contacts
  const handleRetrySend = () => {
    if (!activeJob) return
    const retryRows = failedContacts.map(fc => fc.contact_data)
    const retryResult: TransformResult = {
      success: true,
      rows: retryRows,
      total_count: retryRows.length,
      flagged_rows: [],
      flagged_count: 0,
      transformed_fields: {
        title_cased: 0,
        campaigns_extracted: 0,
        phone_mapped: 0,
        contact_owner_added: 0,
        flagged: 0,
      },
      warnings: [],
      source_filename: 'failed_contacts_retry',
    }
    const updatedJob = { ...activeJob, result: retryResult }
    setActiveJob(updatedJob)
    setViewMode('normal')
    setShowSendModal(true)
  }

  // Handle job started (store in localStorage)
  const handleJobStarted = (jobId: string) => {
    setActiveJobId(jobId)
    localStorage.setItem('ghl_active_job_id', jobId)
  }

  // Handle modal close (clear activeJobId if job complete)
  const handleModalClose = async () => {
    setShowSendModal(false)
    setActiveJobId(null)
    localStorage.removeItem('ghl_active_job_id')
    const res = await ghlApi.getDailyLimit()
    if (res.data) {
      setDailyLimit(res.data)
    }
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
        <button
          onClick={togglePanel}
          className="hidden lg:flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-tre-navy border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          title={panelCollapsed ? 'Show side panel' : 'Hide side panel'}
        >
          {panelCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          {panelCollapsed ? 'Show Panel' : 'Hide Panel'}
        </button>
      </div>

      {/* Upload Section - shown above when panel is collapsed and no active result */}
      {panelCollapsed && !result && (
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

      <div className={`grid grid-cols-1 ${panelCollapsed ? '' : 'lg:grid-cols-3'} gap-6`}>
        {/* Left Column - Upload and History */}
        {!panelCollapsed && (
          <div className="space-y-6">
            {/* Upload Section */}
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

            {/* Recent Jobs */}
            <div className="bg-white rounded-xl border border-gray-200">
              <div className="px-4 py-3 border-b border-gray-100">
                <h3 className="font-medium text-gray-900">Recent Jobs</h3>
              </div>
              {isLoadingJobs ? (
                <div className="divide-y divide-gray-100">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="px-4 py-3 animate-pulse">
                      <div className="h-3 bg-gray-200 rounded w-3/4 mb-2"></div>
                      <div className="h-2 bg-gray-100 rounded w-1/2"></div>
                    </div>
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
                          ) : job.result && !job.result.success ? (
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

          {result?.success ? (
            <div className="bg-white rounded-xl border border-gray-200">
              {/* Results Header */}
              <div className="px-6 py-4 border-b border-gray-100">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-oswald font-semibold text-tre-navy">
                      {viewMode === 'failed-contacts' ? 'Failed Contacts'
                        : viewMode === 'flagged' ? 'Mineral Update Report'
                        : activeJob?.documentName ?? result.source_filename}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {viewMode === 'failed-contacts' ? 'Review and retry failed contacts'
                        : viewMode === 'flagged' ? 'These contacts need to be updated in Mineral before GHL import'
                        : activeJob
                          ? `Processed by ${activeJob.user} on ${activeJob.timestamp}`
                          : 'Transformation complete'}
                    </p>
                  </div>
                  {viewMode === 'normal' && result && (
                    <div className="flex items-center gap-4 mr-2">
                      <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={showIndividualsOnly}
                          onChange={(e) => setShowIndividualsOnly(e.target.checked)}
                          className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                        />
                        Individuals only
                      </label>
                      <span className="text-xs text-gray-400">
                        {showIndividualsOnly
                          ? `${filteredRows.length} of ${currentRows.length} contacts`
                          : `${currentRows.length} contacts`}
                      </span>
                    </div>
                  )}
                  <div className="flex gap-2">
                    {viewMode === 'flagged' && (
                      <>
                        <button
                          onClick={() => setViewMode('normal')}
                          className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                        >
                          <XCircle className="w-4 h-4" />
                          Back to Clean Export
                        </button>
                        <button
                          onClick={handleExportFlagged}
                          className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                        >
                          <Download className="w-4 h-4" />
                          Download Mineral Updates
                        </button>
                      </>
                    )}
                    {viewMode === 'failed-contacts' && (
                      <>
                        <button
                          onClick={handleBackToNormalView}
                          className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                        >
                          <XCircle className="w-4 h-4" />
                          Back to Results
                        </button>
                        <button
                          onClick={handleExportFailedContacts}
                          className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                        >
                          <Download className="w-4 h-4" />
                          Download Failed CSV
                        </button>
                        <button
                          onClick={handleRetrySend}
                          disabled={connections.length === 0 || failedContacts.length === 0}
                          title={connections.length === 0 ? 'Add a GHL connection in Admin Settings first' : 'Retry sending failed contacts'}
                          className="flex items-center gap-2 px-3 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <Send className="w-4 h-4" />
                          Retry Send
                        </button>
                      </>
                    )}
                    {viewMode === 'normal' && (
                      <>
                        <button
                          onClick={handleReset}
                          className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                        >
                          <Upload className="w-4 h-4" />
                          Upload New File
                        </button>
                        <div className="flex flex-col items-end gap-1">
                          <button
                            onClick={() => setShowSendModal(true)}
                            disabled={connections.length === 0 || connections.every(c => c.validation_status !== 'valid') || (!!activeJobId)}
                            title={
                              connections.length === 0
                                ? 'No GHL connection. Configure in Admin Settings.'
                                : connections.every(c => c.validation_status !== 'valid')
                                ? 'No valid GHL connection. Configure in Admin Settings.'
                                : activeJobId
                                ? 'Send in progress'
                                : 'Send contacts to GoHighLevel'
                            }
                            className="flex items-center gap-2 px-3 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <Send className="w-4 h-4" />
                            Send to GHL
                          </button>
                          {dailyLimit && connections.length > 0 && (
                            <p className={`text-xs ${
                              dailyLimit.warning_level === 'critical' ? 'text-red-600 font-medium' :
                              dailyLimit.warning_level === 'warning' ? 'text-yellow-600' :
                              'text-gray-400'
                            }`}>
                              Daily capacity: {dailyLimit.remaining.toLocaleString()} remaining
                            </p>
                          )}
                        </div>
                        <button
                          onClick={handleExport}
                          className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                        >
                          <Download className="w-4 h-4" />
                          Download CSV
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Warnings */}
              {viewMode === 'normal' && result.warnings && result.warnings.length > 0 && (
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

              {/* Flagged Rows Banner */}
              {viewMode === 'normal' && result.flagged_count > 0 && (
                <div className="mx-6 mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-start gap-2">
                      <FileWarning className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-amber-800">
                          {result.flagged_count} contact{result.flagged_count !== 1 ? 's' : ''} need updating in Mineral
                        </p>
                        <p className="text-xs text-amber-600 mt-0.5">
                          Deceased entries and trust/entity names in contact fields have been separated from the GHL export
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setViewMode('flagged')}
                        className="flex items-center gap-2 px-3 py-1.5 text-sm bg-amber-100 text-amber-800 rounded-lg hover:bg-amber-200 transition-colors"
                      >
                        <FileWarning className="w-4 h-4" />
                        Review
                      </button>
                      <button
                        onClick={handleExportFlagged}
                        className="flex items-center gap-2 px-3 py-1.5 text-sm border border-amber-300 text-amber-800 rounded-lg hover:bg-amber-100 transition-colors"
                      >
                        <Download className="w-4 h-4" />
                        Download
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Preview Table */}
              <div className="p-6">
                <h4 className="font-medium text-gray-900 mb-3">
                  {viewMode === 'normal' && excludedRows.size > 0
                    ? `${includedCount} of ${sortedRows.length} rows selected for export`
                    : `${sortedRows.length} rows`}
                  {showIndividualsOnly ? ` (filtered from ${currentRows.length})` : ''}
                </h4>
                <div className="overflow-x-auto overflow-y-auto max-h-[75vh]">
                  <table className="text-sm">
                    <thead className="sticky top-0 bg-white z-10">
                      <tr className="border-b border-gray-200">
                        {viewMode === 'normal' && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600 w-10">
                            <input
                              type="checkbox"
                              checked={isAllSelected}
                              ref={(el) => { if (el) el.indeterminate = isSomeSelected }}
                              onChange={toggleSelectAll}
                              className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                            />
                          </th>
                        )}
                        {viewMode === 'normal' && (
                          <th className="text-left py-2 px-2 font-medium text-gray-600 w-10" />
                        )}
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
                      {sortedRows.map((row, i) => {
                        const isExcluded = excludedRows.has(i)
                        return (
                          <tr key={i} className={`${isExcluded ? 'opacity-40 bg-gray-50' : 'hover:bg-gray-50'}`}>
                            {viewMode === 'normal' && (
                              <td className="py-2 px-3">
                                <input
                                  type="checkbox"
                                  checked={!isExcluded}
                                  onChange={() => toggleRow(i)}
                                  className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                                />
                              </td>
                            )}
                            {viewMode === 'normal' && (
                              <td className="py-2 px-2">
                                <button
                                  onClick={() => handleEditRow(row, i)}
                                  className="text-gray-400 hover:text-tre-teal transition-colors"
                                  title="Edit row"
                                >
                                  <Pencil className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            )}
                            {columns.map((column) => {
                              const value = String(row[column] ?? '')
                              const isError = column === 'Error Category' || column === 'Error Message'
                              const isFlagReason = column === 'Flag Reason'
                              return (
                                <td
                                  key={column}
                                  className={`py-2 px-4 whitespace-nowrap ${isError ? 'text-red-600' : isFlagReason ? 'text-amber-700 font-medium' : 'text-gray-600'}`}
                                >
                                  {value || <span className="text-gray-400">{'\u2014'}</span>}
                                </td>
                              )
                            })}
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : !result && !isProcessing ? (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
              <Repeat className="w-12 h-12 mx-auto mb-3 text-gray-200" />
              <p className="font-medium text-gray-500">No file processed yet</p>
              <p className="text-sm mt-1">Upload a Mineral export CSV to get started</p>
            </div>
          ) : null}
        </div>
      </div>

      {/* Send to GHL Modal */}
      <GhlSendModal
        isOpen={showSendModal}
        onClose={handleModalClose}
        connections={connections}
        contactCount={includedCount}
        defaultTag={defaultTag}
        rows={(() => {
          return sortedRows
            .filter((_, i) => !excludedRows.has(i))
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            .map(({ 'Entity Type': _entityType, ...rest }) => rest)
        })()}
        activeJobId={activeJobId}
        onJobStarted={handleJobStarted}
        onViewFailedContacts={handleViewFailedContacts}
      />

      {/* Edit Row Modal */}
      <Modal
        isOpen={!!editingRow}
        onClose={() => { setEditingRow(null); setEditingIndex(-1) }}
        title="Edit Contact"
        size="lg"
        footer={
          <div className="flex justify-end gap-2">
            <button
              onClick={() => { setEditingRow(null); setEditingIndex(-1) }}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveEdit}
              className="px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors text-sm"
            >
              Save Changes
            </button>
          </div>
        }
      >
        {editingRow && (
          <div className="grid grid-cols-2 gap-4">
            {columns
              .filter(col => col !== 'Entity Type' && col !== 'Flag Reason')
              .map((col) => (
                <div key={col} className={col === 'Address' ? 'col-span-2' : ''}>
                  <label className="block text-xs font-medium text-gray-500 mb-1">{col}</label>
                  <input
                    type="text"
                    value={editingRow[col] || ''}
                    onChange={(e) => setEditingRow({ ...editingRow, [col]: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-tre-teal focus:border-tre-teal"
                  />
                </div>
              ))}
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
