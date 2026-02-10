import { useState, useMemo, useEffect, useRef } from 'react'
import { FileSearch, Download, Upload, Users, AlertCircle, CheckCircle, Flag, Filter, RotateCcw, Edit2, Columns, Sparkles, X, Search } from 'lucide-react'
import { FileUpload, Modal, AiReviewPanel, EnrichmentPanel } from '../components'
import { aiApi } from '../utils/api'
import type { AiSuggestion } from '../utils/api'
import { useAuth } from '../contexts/AuthContext'

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
  flagged: boolean
  flag_reason?: string
}

interface ExtractionResult {
  success: boolean
  entries?: PartyEntry[]
  total_count?: number
  flagged_count?: number
  source_filename?: string
  error_message?: string
  job_id?: string
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
  const { user } = useAuth()
  const storageKey = `${STORAGE_KEY_PREFIX}-${user?.uid || 'anon'}`
  const [jobs, setJobs] = useState<ExtractJob[]>([])
  const [activeJob, setActiveJob] = useState<ExtractJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isLoadingEntries, setIsLoadingEntries] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filter states
  const [showIndividualsOnly, setShowIndividualsOnly] = useState(false)
  const [hideFlagged, setHideFlagged] = useState(false)
  const [hideUnknownAddresses, setHideUnknownAddresses] = useState(true)

  // Row selection state (set of excluded entry numbers)
  const [excludedEntries, setExcludedEntries] = useState<Set<string>>(new Set())

  // AI Review state
  const [showAiReview, setShowAiReview] = useState(false)
  const [aiEnabled, setAiEnabled] = useState(false)

  // Enrichment state
  const [showEnrichment, setShowEnrichment] = useState(false)

  // Edit modal state
  const [editingEntry, setEditingEntry] = useState<PartyEntry | null>(null)

  // Column visibility (persisted in localStorage per user)
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) return new Set(JSON.parse(saved))
    } catch { /* use defaults */ }
    return new Set(DEFAULT_EXTRACT_VISIBLE)
  })
  const [showColumnPicker, setShowColumnPicker] = useState(false)
  const columnPickerRef = useRef<HTMLDivElement>(null)

  // Persist column visibility to localStorage
  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify([...visibleColumns]))
  }, [visibleColumns, storageKey])

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
        const response = await fetch(`${API_BASE}/history/jobs?tool=extract&limit=20`)
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
  }, [])

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

    setActiveJob({
      ...activeJob,
      result: {
        ...activeJob.result,
        entries: updatedEntries,
      },
    })
    setShowAiReview(false)
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

      const response = await fetch(`${API_BASE}/extract/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data: UploadResponse = await response.json()
      newJob.result = data.result
      newJob.job_id = data.result?.job_id

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

  const handleExport = async (format: 'csv' | 'excel') => {
    if (entriesToExport.length === 0) {
      setError('No entries selected for export')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/extract/export/${format}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          entries: entriesToExport,
          filename: activeJob?.documentName?.replace(/\.[^.]+$/, '') || 'extract',
        }),
      })

      if (!response.ok) throw new Error('Export failed')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activeJob?.documentName?.replace(/\.[^.]+$/, '') || 'extract'}_mineral.${format === 'csv' ? 'csv' : 'xlsx'}`
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
    setExcludedEntries(new Set())

    // Lazy-load entries if not already loaded
    if (!job.result && job.job_id) {
      setIsLoadingEntries(true)
      try {
        const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}/entries`)
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
      await fetch(`${API_BASE}/history/jobs/${job.job_id}`, { method: 'DELETE' })
    } catch { /* best-effort */ }
    setJobs((prev) => prev.filter((j) => j.id !== job.id))
    if (activeJob?.id === job.id) setActiveJob(null)
  }

  // Get filtered entries based on filter state
  const filteredEntries = useMemo(() => {
    if (!activeJob?.result?.entries) return []

    return activeJob.result.entries.filter((entry) => {
      if (showIndividualsOnly && entry.entity_type !== 'Individual') return false
      if (hideFlagged && entry.flagged) return false
      if (hideUnknownAddresses && entry.entry_number.startsWith('U')) return false
      return true
    })
  }, [activeJob?.result?.entries, showIndividualsOnly, hideFlagged, hideUnknownAddresses])

  // Get entries to export (filtered + not excluded)
  const entriesToExport = useMemo(() => {
    return filteredEntries.filter((entry) => !excludedEntries.has(entry.entry_number))
  }, [filteredEntries, excludedEntries])

  // Selection helpers
  const isAllSelected = filteredEntries.length > 0 &&
    filteredEntries.every((e) => !excludedEntries.has(e.entry_number))
  const isSomeSelected = filteredEntries.some((e) => !excludedEntries.has(e.entry_number)) && !isAllSelected

  const toggleSelectAll = () => {
    if (isAllSelected) {
      setExcludedEntries(new Set(filteredEntries.map((e) => e.entry_number)))
    } else {
      const newExcluded = new Set(excludedEntries)
      filteredEntries.forEach((e) => newExcluded.delete(e.entry_number))
      setExcludedEntries(newExcluded)
    }
  }

  const toggleEntry = (entryNumber: string) => {
    const newExcluded = new Set(excludedEntries)
    if (newExcluded.has(entryNumber)) {
      newExcluded.delete(entryNumber)
    } else {
      newExcluded.add(entryNumber)
    }
    setExcludedEntries(newExcluded)
  }

  const resetFilters = () => {
    setShowIndividualsOnly(false)
    setHideFlagged(false)
    setHideUnknownAddresses(true)
    setExcludedEntries(new Set())
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-100 rounded-lg">
          <FileSearch className="w-6 h-6 text-blue-600" />
        </div>
        <div>
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Extract
          </h1>
          <p className="text-gray-500 text-sm">
            Extract party and stakeholder data from OCC Exhibit A PDFs
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
              label="Upload OCC Exhibit A"
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

        {/* Right Column - Results */}
        <div className="lg:col-span-2">
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
                      onClick={() => setShowEnrichment(true)}
                      disabled={entriesToExport.length === 0}
                      className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm disabled:opacity-50"
                    >
                      <Search className="w-4 h-4" />
                      Enrich ({entriesToExport.length})
                    </button>
                    <button
                      onClick={() => handleExport('excel')}
                      className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
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
                  ({entriesToExport.length} selected for export)
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 p-6 border-b border-gray-100">
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {activeJob.result.total_count}
                  </p>
                  <p className="text-sm text-gray-500">Total Parties</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-yellow-600">
                    {activeJob.result.flagged_count}
                  </p>
                  <p className="text-sm text-gray-500">Flagged for Review</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-green-600">
                    {entriesToExport.length}
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
                            checked={isAllSelected}
                            ref={(el) => {
                              if (el) el.indeterminate = isSomeSelected
                            }}
                            onChange={toggleSelectAll}
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
                        {isColVisible('status') && <th className="text-left py-2 px-3 font-medium text-gray-600">Status</th>}
                        <th className="text-left py-2 px-3 font-medium text-gray-600 w-10"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {filteredEntries.map((entry) => {
                        const isExcluded = excludedEntries.has(entry.entry_number)
                        return (
                          <tr
                            key={entry.entry_number}
                            className={`
                              ${entry.flagged ? 'bg-yellow-50' : ''}
                              ${isExcluded ? 'opacity-50 bg-gray-100' : ''}
                            `}
                          >
                            <td className="py-2 px-3">
                              <input
                                type="checkbox"
                                checked={!isExcluded}
                                onChange={() => toggleEntry(entry.entry_number)}
                                className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                              />
                            </td>
                            {isColVisible('entry_number') && (
                              <td className={`py-2 px-3 text-gray-500 ${isExcluded ? 'line-through' : ''}`}>
                                {entry.entry_number}
                              </td>
                            )}
                            {isColVisible('primary_name') && (
                              <td className={`py-2 px-3 text-gray-900 ${isExcluded ? 'line-through' : ''}`} title={entry.primary_name}>
                                {entry.primary_name.length > 30
                                  ? entry.primary_name.substring(0, 30) + '...'
                                  : entry.primary_name}
                              </td>
                            )}
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
                              <td className="py-2 px-3 text-gray-600 text-xs">{entry.entity_type}</td>
                            )}
                            {isColVisible('mailing_address') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">
                                {entry.mailing_address || <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColVisible('mailing_address_2') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">
                                {entry.mailing_address_2 || <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColVisible('city') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">
                                {entry.city || <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColVisible('state') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">
                                {entry.state || <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColVisible('zip_code') && (
                              <td className="py-2 px-3 text-gray-600 text-xs">
                                {entry.zip_code || <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColVisible('notes') && (
                              <td className="py-2 px-3 text-gray-600 text-xs max-w-[200px] truncate" title={entry.notes}>
                                {entry.notes || <span className="text-gray-400">{'\u2014'}</span>}
                              </td>
                            )}
                            {isColVisible('status') && (
                              <td className="py-2 px-3">
                                {entry.flagged ? (
                                  <span className="inline-flex items-center gap-1 text-yellow-600 text-xs" title={entry.flag_reason}>
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
            {/* AI Review Panel */}
            {showAiReview && activeJob?.result?.entries && (
              <AiReviewPanel
                tool="extract"
                entries={activeJob.result.entries}
                onApplySuggestions={handleApplySuggestions}
                onClose={() => setShowAiReview(false)}
              />
            )}
            {/* Enrichment Panel */}
            <EnrichmentPanel
              isOpen={showEnrichment}
              onClose={() => setShowEnrichment(false)}
              persons={entriesToExport.map((e) => ({
                name: e.primary_name,
                address: e.mailing_address || undefined,
                city: e.city || undefined,
                state: e.state || undefined,
                zip_code: e.zip_code || undefined,
              }))}
            />
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
        {editingEntry && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={editingEntry.primary_name}
                onChange={(e) => setEditingEntry({ ...editingEntry, primary_name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
              <input
                type="text"
                value={editingEntry.mailing_address || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, mailing_address: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                placeholder="Street address"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Address 2</label>
              <input
                type="text"
                value={editingEntry.mailing_address_2 || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, mailing_address_2: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">State</label>
                <input
                  type="text"
                  value={editingEntry.state || ''}
                  onChange={(e) => setEditingEntry({ ...editingEntry, state: e.target.value.toUpperCase().slice(0, 2) })}
                  maxLength={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ZIP</label>
                <input
                  type="text"
                  value={editingEntry.zip_code || ''}
                  onChange={(e) => setEditingEntry({ ...editingEntry, zip_code: e.target.value })}
                  maxLength={10}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
              <input
                type="text"
                value={editingEntry.notes || ''}
                onChange={(e) => setEditingEntry({ ...editingEntry, notes: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal"
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
