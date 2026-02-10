import { useState, useMemo, useEffect, useRef } from 'react'
import { FileText, Download, Upload, Users, AlertCircle, CheckCircle, Filter, RotateCcw, Edit2, Columns, Sparkles, X, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { FileUpload, Modal, AiReviewPanel } from '../components'
import { aiApi } from '../utils/api'
import type { AiSuggestion } from '../utils/api'
import { useAuth } from '../contexts/AuthContext'
import { useToolLayout } from '../hooks/useToolLayout'

interface OwnerEntry {
  full_name: string
  first_name?: string
  middle_name?: string
  last_name?: string
  entity_type: string
  address?: string
  address_line_2?: string
  city?: string
  state?: string
  zip_code?: string
  legal_description: string
  notes?: string
  duplicate_flag: boolean
  has_address: boolean
}

interface ProcessingResult {
  success: boolean
  job_id?: string
  entries?: OwnerEntry[]
  total_count?: number
  duplicate_count?: number
  no_address_count?: number
  sections?: string[]
  source_filename?: string
  error_message?: string
}

interface UploadResponse {
  message: string
  result?: ProcessingResult
}

interface TitleJob {
  id: string
  job_id?: string
  documentName: string
  user: string
  timestamp: string
  result?: ProcessingResult
}

interface ColumnConfig {
  key: string
  label: string
  alwaysVisible?: boolean
}

const COLUMNS: ColumnConfig[] = [
  { key: 'checkbox', label: 'Select', alwaysVisible: true },
  { key: 'full_name', label: 'Full Name' },
  { key: 'first_name', label: 'First Name' },
  { key: 'middle_name', label: 'Middle Name' },
  { key: 'last_name', label: 'Last Name' },
  { key: 'entity_type', label: 'Entity Type' },
  { key: 'address', label: 'Address' },
  { key: 'address_line_2', label: 'Address 2' },
  { key: 'city', label: 'City' },
  { key: 'state', label: 'State' },
  { key: 'zip_code', label: 'ZIP' },
  { key: 'legal_description', label: 'Legal Desc' },
  { key: 'notes', label: 'Notes' },
  { key: 'duplicate_flag', label: 'Duplicate' },
  { key: 'has_address', label: 'Has Address' },
  { key: 'status', label: 'Status' },
  { key: 'edit', label: 'Edit', alwaysVisible: true },
]

const DEFAULT_TITLE_VISIBLE = new Set([
  'checkbox', 'full_name', 'entity_type', 'address', 'city', 'state',
  'zip_code', 'legal_description', 'status', 'edit',
])

const STORAGE_KEY_PREFIX = 'title-visible-columns'

const ENTITY_TYPE_OPTIONS = [
  'INDIVIDUAL',
  'CORPORATION',
  'TRUST',
  'ESTATE',
  'FOUNDATION',
  'MINERAL CO',
  'UNIVERSITY',
  'CHURCH',
  'UNKNOWN',
]

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Title() {
  const { user } = useAuth()
  const { panelCollapsed, togglePanel, activeStorageKey } = useToolLayout('title', user?.uid, STORAGE_KEY_PREFIX)
  const [jobs, setJobs] = useState<TitleJob[]>([])
  const [activeJob, setActiveJob] = useState<TitleJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isLoadingEntries, setIsLoadingEntries] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filter state
  const [hideNoAddress, setHideNoAddress] = useState(false)
  const [hideDuplicates, setHideDuplicates] = useState(false)
  const [showIndividualsOnly, setShowIndividualsOnly] = useState(false)
  const [selectedSection, setSelectedSection] = useState<string>('')

  // Row selection state
  const [excludedIndices, setExcludedIndices] = useState<Set<number>>(new Set())

  // AI Review state
  const [showAiReview, setShowAiReview] = useState(false)
  const [aiEnabled, setAiEnabled] = useState(false)

  // Edit modal state
  const [editingEntry, setEditingEntry] = useState<OwnerEntry | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  // Column visibility state (persisted in localStorage per user, separate keys for narrow/wide)
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(activeStorageKey)
      if (saved) return new Set(JSON.parse(saved))
    } catch { /* use defaults */ }
    return new Set(DEFAULT_TITLE_VISIBLE)
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
        setVisibleColumns(new Set(DEFAULT_TITLE_VISIBLE))
      }
    } catch {
      setVisibleColumns(new Set(DEFAULT_TITLE_VISIBLE))
    }
  }, [activeStorageKey])

  // Persist column visibility to localStorage
  useEffect(() => {
    localStorage.setItem(activeStorageKey, JSON.stringify([...visibleColumns]))
  }, [visibleColumns, activeStorageKey])

  // Click-outside handler for column picker
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        columnPickerRef.current &&
        !columnPickerRef.current.contains(event.target as Node)
      ) {
        setShowColumnPicker(false)
      }
    }
    if (showColumnPicker) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showColumnPicker])

  // Load recent jobs on mount
  useEffect(() => {
    const loadRecentJobs = async () => {
      try {
        const response = await fetch(`${API_BASE}/history/jobs?tool=title&limit=20`)
        if (!response.ok) return
        const data = await response.json()
        const jobsArray = data.jobs || (Array.isArray(data) ? data : [])
        if (jobsArray.length > 0) {
          const loadedJobs: TitleJob[] = jobsArray.map((j: Record<string, unknown>) => ({
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
      } catch {
        // Silently fail - jobs will load fresh from uploads
      }
    }
    loadRecentJobs()
  }, [])

  const isColumnVisible = (key: string): boolean => {
    const col = COLUMNS.find((c) => c.key === key)
    if (col?.alwaysVisible) return true
    return visibleColumns.has(key)
  }

  const toggleColumnVisibility = (key: string) => {
    const newVisible = new Set(visibleColumns)
    if (newVisible.has(key)) {
      newVisible.delete(key)
    } else {
      newVisible.add(key)
    }
    setVisibleColumns(newVisible)
  }

  // Apply filters to entries
  const filteredEntries = useMemo(() => {
    if (!activeJob?.result?.entries) return []
    let filtered = [...activeJob.result.entries]

    if (hideNoAddress) {
      filtered = filtered.filter(e => e.has_address)
    }

    if (hideDuplicates) {
      const seen = new Set<string>()
      filtered = filtered.filter(e => {
        const key = e.full_name.toUpperCase().trim()
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
    }

    if (showIndividualsOnly) {
      filtered = filtered.filter(e => e.entity_type === 'INDIVIDUAL')
    }

    if (selectedSection) {
      filtered = filtered.filter(e => e.legal_description === selectedSection)
    }

    return filtered
  }, [activeJob?.result?.entries, hideNoAddress, hideDuplicates, showIndividualsOnly, selectedSection])

  // Get entries to export (filtered + not excluded)
  const entriesToExport = useMemo(() => {
    return filteredEntries.filter((_, i) => !excludedIndices.has(i))
  }, [filteredEntries, excludedIndices])

  // Selection helpers
  const isAllSelected = filteredEntries.length > 0 &&
    filteredEntries.every((_, i) => !excludedIndices.has(i))
  const isSomeSelected = filteredEntries.some((_, i) => !excludedIndices.has(i)) && !isAllSelected

  const toggleSelectAll = () => {
    if (isAllSelected) {
      // Exclude all
      setExcludedIndices(new Set(filteredEntries.map((_, i) => i)))
    } else {
      // Include all
      setExcludedIndices(new Set())
    }
  }

  const toggleEntry = (index: number) => {
    const newExcluded = new Set(excludedIndices)
    if (newExcluded.has(index)) {
      newExcluded.delete(index)
    } else {
      newExcluded.add(index)
    }
    setExcludedIndices(newExcluded)
  }

  const getEntryStatus = (entry: OwnerEntry): { label: string; color: string } => {
    if (entry.duplicate_flag && !entry.has_address) {
      return { label: 'Dup + No Addr', color: 'text-purple-600 bg-purple-100' }
    }
    if (entry.duplicate_flag) {
      return { label: 'Duplicate', color: 'text-yellow-700 bg-yellow-100' }
    }
    if (!entry.has_address) {
      return { label: 'No Address', color: 'text-red-600 bg-red-100' }
    }
    return { label: 'OK', color: 'text-green-600 bg-green-100' }
  }


  // Check AI status on mount
  useEffect(() => {
    aiApi.getStatus().then(res => {
      if (res.data?.enabled) setAiEnabled(true)
    })
  }, [])

  const handleApplySuggestions = (accepted: AiSuggestion[]) => {
    if (!activeJob?.result?.entries) return

    const updatedEntries = [...activeJob.result.entries]
    for (const suggestion of accepted) {
      const entry = updatedEntries[suggestion.entry_index]
      if (entry && suggestion.field in entry) {
        (entry as unknown as Record<string, unknown>)[suggestion.field] = suggestion.suggested_value
      }
    }

    const updatedResult = { ...activeJob.result, entries: updatedEntries }
    const updatedJob = { ...activeJob, result: updatedResult }
    setActiveJob(updatedJob)
    setJobs(prev => prev.map(j => j.id === activeJob.id ? updatedJob : j))
    setShowAiReview(false)
  }

  const handleFilesSelected = async (files: File[]) => {
    if (files.length === 0) return

    const file = files[0]
    setIsProcessing(true)
    setError(null)

    const newJob: TitleJob = {
      id: String(Date.now()),
      documentName: file.name,
      user: user?.displayName || user?.email || 'Unknown',
      timestamp: new Date().toLocaleString(),
    }

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API_BASE}/title/upload`, {
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

  const handleExport = async (format: 'csv' | 'excel' | 'mineral') => {
    if (entriesToExport.length === 0) {
      setError('No entries selected for export')
      return
    }

    try {
      // For mineral format, use the same endpoint but with different filename convention
      const endpoint = format === 'mineral'
        ? `${API_BASE}/title/export/excel`
        : `${API_BASE}/title/export/${format}`

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          entries: entriesToExport,
          filters: {
            hide_no_address: hideNoAddress,
            hide_duplicates: hideDuplicates,
            sections: selectedSection ? [selectedSection] : null,
          },
          filename: activeJob?.documentName?.replace(/\.[^.]+$/, '') || 'title_export',
          format_type: format === 'mineral' ? 'mineral' : 'standard',
        }),
      })

      if (!response.ok) throw new Error('Export failed')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const ext = format === 'csv' ? 'csv' : 'xlsx'
      const suffix = format === 'mineral' ? '_mineral' : '_processed'
      a.download = `${activeJob?.documentName?.replace(/\.[^.]+$/, '') || 'title_export'}${suffix}.${ext}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      setError('Failed to export file')
    }
  }

  const handleSelectJob = async (job: TitleJob) => {
    setActiveJob(job)
    setError(null)
    setExcludedIndices(new Set())

    // Lazy-load entries if not already loaded
    if (job.job_id && (!job.result?.entries || job.result.entries.length === 0)) {
      setIsLoadingEntries(true)
      try {
        const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}/entries`)
        if (response.ok) {
          const data = await response.json()
          const entries = Array.isArray(data) ? data : data.entries || []
          const updatedResult: ProcessingResult = {
            ...job.result,
            success: true,
            entries,
            total_count: job.result?.total_count || entries.length,
            duplicate_count: job.result?.duplicate_count || 0,
            no_address_count: job.result?.no_address_count || 0,
          }
          const updatedJob = { ...job, result: updatedResult }
          setActiveJob(updatedJob)
          setJobs((prev) =>
            prev.map((j) => (j.id === job.id ? updatedJob : j))
          )
        }
      } catch {
        // Entries may not be available from history; that's okay
      } finally {
        setIsLoadingEntries(false)
      }
    }
  }

  const handleDeleteJob = async (e: React.MouseEvent, job: TitleJob) => {
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

  const resetFilters = () => {
    setHideNoAddress(false)
    setHideDuplicates(false)
    setShowIndividualsOnly(false)
    setSelectedSection('')
    setExcludedIndices(new Set())
  }

  const handleEditEntry = (entry: OwnerEntry, index: number) => {
    setEditingEntry({ ...entry })
    setEditingIndex(index)
  }

  const handleSaveEdit = () => {
    if (editingEntry === null || editingIndex === null || !activeJob?.result?.entries) return

    const updatedEntries = [...activeJob.result.entries]
    // Find the original index in the full entries array
    const filteredEntry = filteredEntries[editingIndex]
    const originalIndex = activeJob.result.entries.indexOf(filteredEntry)
    if (originalIndex !== -1) {
      updatedEntries[originalIndex] = editingEntry
    }

    const updatedResult = { ...activeJob.result, entries: updatedEntries }
    const updatedJob = { ...activeJob, result: updatedResult }
    setActiveJob(updatedJob)
    setJobs((prev) => prev.map((j) => (j.id === activeJob.id ? updatedJob : j)))

    setEditingEntry(null)
    setEditingIndex(null)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-green-100 rounded-lg">
          <FileText className="w-6 h-6 text-green-600" />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Title
          </h1>
          <p className="text-gray-500 text-sm">
            Consolidate owner and contact info from Oklahoma title opinions
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

      <div className={`grid grid-cols-1 ${panelCollapsed ? '' : 'lg:grid-cols-3'} gap-6`}>
        {/* Left Column - Upload and History */}
        {!panelCollapsed && (
        <div className="space-y-6">
          {/* Upload Section */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <FileUpload
              onFilesSelected={handleFilesSelected}
              accept=".xlsx,.xls,.csv"
              label="Upload Title Opinion"
              description="Drop your Excel or CSV file here"
            />
            {isProcessing && (
              <div className="mt-4 flex items-center gap-2 text-tre-teal">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-tre-teal"></div>
                <span className="text-sm">Processing...</span>
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
                      onClick={() => handleExport('mineral')}
                      className="flex items-center gap-2 px-3 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      Mineral
                    </button>
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-5 gap-4 p-6 border-b border-gray-100">
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {activeJob.result.total_count}
                  </p>
                  <p className="text-sm text-gray-500">Total</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-teal">
                    {filteredEntries.length}
                  </p>
                  <p className="text-sm text-gray-500">Filtered</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-green-600">
                    {entriesToExport.length}
                  </p>
                  <p className="text-sm text-gray-500">Selected</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-yellow-600">
                    {activeJob.result.duplicate_count}
                  </p>
                  <p className="text-sm text-gray-500">Duplicates</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-red-600">
                    {activeJob.result.no_address_count}
                  </p>
                  <p className="text-sm text-gray-500">No Address</p>
                </div>
              </div>

              {/* Filters */}
              <div className="px-6 py-3 border-b border-gray-100 bg-gray-50">
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
                    Individuals Only
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={hideNoAddress}
                      onChange={(e) => setHideNoAddress(e.target.checked)}
                      className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                    />
                    Hide No Address
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={hideDuplicates}
                      onChange={(e) => setHideDuplicates(e.target.checked)}
                      className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                    />
                    Hide Duplicates
                  </label>
                  {activeJob.result.sections && activeJob.result.sections.length > 1 && (
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-600">Section:</span>
                      <select
                        value={selectedSection}
                        onChange={(e) => setSelectedSection(e.target.value)}
                        className="text-sm border border-gray-300 rounded px-2 py-1 focus:ring-tre-teal focus:border-tre-teal"
                      >
                        <option value="">All Sections</option>
                        {activeJob.result.sections.map((section, i) => (
                          <option key={i} value={section}>{section}</option>
                        ))}
                      </select>
                    </div>
                  )}
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
                  ({entriesToExport.length} selected for export)
                </div>
              </div>

              {/* Preview Table */}
              <div className="p-6">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900 flex items-center gap-2">
                    <Users className="w-4 h-4" />
                    Owner Entries Preview
                  </h4>
                  <div className="relative" ref={columnPickerRef}>
                    <button
                      onClick={() => setShowColumnPicker(!showColumnPicker)}
                      className="flex items-center gap-1 px-2 py-1 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <Columns className="w-4 h-4" />
                      Columns
                    </button>
                    {showColumnPicker && (
                      <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-2 min-w-[160px]">
                        {COLUMNS.filter((c) => !c.alwaysVisible).map((col) => (
                          <label
                            key={col.key}
                            className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-gray-50 cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={visibleColumns.has(col.key)}
                              onChange={() => toggleColumnVisibility(col.key)}
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
                        {isColumnVisible('checkbox') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600 w-10">
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
                        )}
                        {isColumnVisible('full_name') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Full Name</th>
                        )}
                        {isColumnVisible('first_name') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">First Name</th>
                        )}
                        {isColumnVisible('middle_name') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Middle Name</th>
                        )}
                        {isColumnVisible('last_name') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Last Name</th>
                        )}
                        {isColumnVisible('entity_type') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Entity Type</th>
                        )}
                        {isColumnVisible('address') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Address</th>
                        )}
                        {isColumnVisible('address_line_2') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Address 2</th>
                        )}
                        {isColumnVisible('city') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">City</th>
                        )}
                        {isColumnVisible('state') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">State</th>
                        )}
                        {isColumnVisible('zip_code') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">ZIP</th>
                        )}
                        {isColumnVisible('legal_description') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Legal Desc</th>
                        )}
                        {isColumnVisible('notes') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Notes</th>
                        )}
                        {isColumnVisible('duplicate_flag') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Duplicate</th>
                        )}
                        {isColumnVisible('has_address') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Has Address</th>
                        )}
                        {isColumnVisible('status') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600">Status</th>
                        )}
                        {isColumnVisible('edit') && (
                          <th className="text-left py-2 px-3 font-medium text-gray-600 w-10"></th>
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {filteredEntries.map((entry, i) => {
                        const isExcluded = excludedIndices.has(i)
                        const status = getEntryStatus(entry)
                        return (
                          <tr
                            key={i}
                            className={`
                              ${entry.duplicate_flag && !entry.has_address ? 'bg-purple-50' :
                                entry.duplicate_flag ? 'bg-yellow-50' :
                                !entry.has_address ? 'bg-red-50' : ''}
                              ${isExcluded ? 'opacity-50' : ''}
                            `}
                          >
                            {isColumnVisible('checkbox') && (
                              <td className="py-2 px-3">
                                <input
                                  type="checkbox"
                                  checked={!isExcluded}
                                  onChange={() => toggleEntry(i)}
                                  className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                                />
                              </td>
                            )}
                            {isColumnVisible('full_name') && (
                              <td className={`py-2 px-3 text-gray-900 ${isExcluded ? 'line-through' : ''}`} title={entry.full_name}>
                                {entry.full_name.length > 30 ? entry.full_name.substring(0, 30) + '...' : entry.full_name}
                              </td>
                            )}
                            {isColumnVisible('first_name') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.first_name || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColumnVisible('middle_name') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.middle_name || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColumnVisible('last_name') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.last_name || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColumnVisible('entity_type') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.entity_type}</td>
                            )}
                            {isColumnVisible('address') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">
                                {entry.address || <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColumnVisible('address_line_2') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.address_line_2 || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColumnVisible('city') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.city || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColumnVisible('state') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.state || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColumnVisible('zip_code') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.zip_code || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColumnVisible('legal_description') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.legal_description}</td>
                            )}
                            {isColumnVisible('notes') && (
                              <td className="py-2 px-3 text-gray-600 text-xs max-w-[200px] truncate" title={entry.notes}>{entry.notes || <span className="text-gray-400">{'\u2014'}</span>}</td>
                            )}
                            {isColumnVisible('duplicate_flag') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.duplicate_flag ? 'Yes' : 'No'}</td>
                            )}
                            {isColumnVisible('has_address') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.has_address ? 'Yes' : 'No'}</td>
                            )}
                            {isColumnVisible('status') && (
                              <td className="py-2 px-3">
                                <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${status.color}`}>
                                  {status.label}
                                </span>
                              </td>
                            )}
                            {isColumnVisible('edit') && (
                              <td className="py-2 px-3">
                                <button
                                  onClick={() => handleEditEntry(entry, i)}
                                  className="p-1 text-gray-400 hover:text-tre-teal transition-colors rounded hover:bg-gray-100"
                                  title="Edit entry"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            )}
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                  {filteredEntries.length === 0 && (
                    <p className="text-sm text-gray-500 mt-3 text-center">
                      No entries match the current filters.
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* AI Review Panel */}
            {showAiReview && activeJob?.result?.entries && (
              <AiReviewPanel
                tool="title"
                entries={activeJob.result.entries}
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
              <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="font-medium">No job selected</p>
              <p className="text-sm mt-1">Upload a file or select a job from the history</p>
            </div>
          )}
        </div>
      </div>

      {/* Edit Entry Modal */}
      <Modal
        isOpen={editingEntry !== null}
        onClose={() => { setEditingEntry(null); setEditingIndex(null) }}
        title="Edit Entry"
        size="lg"
        footer={
          <>
            <button
              onClick={() => { setEditingEntry(null); setEditingIndex(null) }}
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
        {editingEntry && (
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
              <input
                type="text"
                value={editingEntry.full_name}
                onChange={(e) => setEditingEntry({ ...editingEntry, full_name: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
              <input
                type="text"
                value={editingEntry.first_name || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, first_name: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Middle Name</label>
              <input
                type="text"
                value={editingEntry.middle_name || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, middle_name: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
              <input
                type="text"
                value={editingEntry.last_name || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, last_name: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Entity Type</label>
              <select
                value={editingEntry.entity_type}
                onChange={(e) => setEditingEntry({ ...editingEntry, entity_type: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              >
                {ENTITY_TYPE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
              <input
                type="text"
                value={editingEntry.address || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, address: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Address 2</label>
              <input
                type="text"
                value={editingEntry.address_line_2 || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, address_line_2: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
              <input
                type="text"
                value={editingEntry.city || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, city: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">State</label>
              <input
                type="text"
                value={editingEntry.state || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, state: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">ZIP</label>
              <input
                type="text"
                value={editingEntry.zip_code || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, zip_code: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Legal Description</label>
              <input
                type="text"
                value={editingEntry.legal_description}
                onChange={(e) => setEditingEntry({ ...editingEntry, legal_description: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
              <input
                type="text"
                value={editingEntry.notes || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, notes: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-tre-teal focus:border-tre-teal"
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
