import { useState, useMemo } from 'react'
import { FileSearch, Download, Upload, Users, AlertCircle, CheckCircle, Flag, Filter, RotateCcw, Edit2, X } from 'lucide-react'
import { FileUpload } from '../components'
import { useAuth } from '../contexts/AuthContext'

interface PartyEntry {
  entry_number: string
  primary_name: string
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
}

interface UploadResponse {
  message: string
  result?: ExtractionResult
}

interface ExtractJob {
  id: string
  documentName: string
  user: string
  timestamp: string
  result?: ExtractionResult
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Extract() {
  const { user } = useAuth()
  const [jobs, setJobs] = useState<ExtractJob[]>([])
  const [activeJob, setActiveJob] = useState<ExtractJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filter states
  const [showIndividualsOnly, setShowIndividualsOnly] = useState(false)
  const [hideFlagged, setHideFlagged] = useState(false)
  const [hideUnknownAddresses, setHideUnknownAddresses] = useState(true)

  // Row selection state (set of excluded entry numbers)
  const [excludedEntries, setExcludedEntries] = useState<Set<string>>(new Set())

  // Edit modal state
  const [editingEntry, setEditingEntry] = useState<PartyEntry | null>(null)

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
    } catch (err) {
      setError('Failed to export file')
    }
  }

  const handleSelectJob = (job: ExtractJob) => {
    setActiveJob(job)
    setError(null)
    // Reset filters and selection when switching jobs
    setExcludedEntries(new Set())
  }

  const formatAddress = (entry: PartyEntry): string => {
    const parts = []
    if (entry.city) parts.push(entry.city)
    if (entry.state) parts.push(entry.state)
    if (entry.zip_code) parts.push(entry.zip_code)
    return parts.length > 0 ? parts.join(', ') : ''
  }

  // Get filtered entries based on filter state
  const filteredEntries = useMemo(() => {
    if (!activeJob?.result?.entries) return []

    return activeJob.result.entries.filter((entry) => {
      // Filter: Show only Individuals
      if (showIndividualsOnly && entry.entity_type !== 'Individual') {
        return false
      }
      // Filter: Hide flagged entries
      if (hideFlagged && entry.flagged) {
        return false
      }
      // Filter: Hide unknown addresses (entry number starts with 'U')
      if (hideUnknownAddresses && entry.entry_number.startsWith('U')) {
        return false
      }
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
      // Exclude all filtered entries
      setExcludedEntries(new Set(filteredEntries.map((e) => e.entry_number)))
    } else {
      // Include all filtered entries (remove from excluded)
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

  // Handle entry edit
  const handleEditEntry = (entry: PartyEntry) => {
    setEditingEntry({ ...entry })
  }

  const handleSaveEdit = () => {
    if (!editingEntry || !activeJob?.result?.entries) return

    // Update the entry in the result
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
          {/* Upload Section */}
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
                      ) : job.result?.error_message ? (
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
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleExport('csv')}
                      className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      CSV
                    </button>
                    <button
                      onClick={() => handleExport('excel')}
                      className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      Excel
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
                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                  <Users className="w-4 h-4" />
                  Party Entries Preview
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
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
                        <th className="text-left py-2 px-3 font-medium text-gray-600">#</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Name</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Type</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Address</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Status</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600 w-10"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {filteredEntries.slice(0, 20).map((entry) => {
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
                            <td className={`py-2 px-3 text-gray-500 ${isExcluded ? 'line-through' : ''}`}>
                              {entry.entry_number}
                            </td>
                            <td className={`py-2 px-3 text-gray-900 ${isExcluded ? 'line-through' : ''}`} title={entry.primary_name}>
                              {entry.primary_name.length > 30
                                ? entry.primary_name.substring(0, 30) + '...'
                                : entry.primary_name}
                            </td>
                            <td className="py-2 px-3 text-gray-600 text-xs">{entry.entity_type}</td>
                            <td className="py-2 px-3 text-gray-600">
                              {formatAddress(entry) || <span className="text-gray-400">—</span>}
                            </td>
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
                  {filteredEntries.length > 20 && (
                    <p className="text-sm text-gray-500 mt-3 text-center">
                      Showing 20 of {filteredEntries.length} filtered entries. Download to see all.
                    </p>
                  )}
                </div>
              </div>
            </div>
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
      {editingEntry && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-oswald font-semibold text-tre-navy">Edit Entry #{editingEntry.entry_number}</h3>
              <button
                onClick={() => setEditingEntry(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
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
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
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
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
