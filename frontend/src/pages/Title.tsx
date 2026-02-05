import { useState } from 'react'
import { FileText, Download, Upload, Users, AlertCircle, CheckCircle, Copy } from 'lucide-react'
import { FileUpload } from '../components'
import { useAuth } from '../contexts/AuthContext'

interface OwnerEntry {
  full_name: string
  first_name?: string
  last_name?: string
  entity_type: string
  address?: string
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
  documentName: string
  user: string
  timestamp: string
  result?: ProcessingResult
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Title() {
  const { user } = useAuth()
  const [jobs, setJobs] = useState<TitleJob[]>([])
  const [activeJob, setActiveJob] = useState<TitleJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filter state
  const [hideNoAddress, setHideNoAddress] = useState(false)
  const [hideDuplicates, setHideDuplicates] = useState(false)
  const [selectedSection, setSelectedSection] = useState<string>('')

  // Apply filters to entries
  const getFilteredEntries = (): OwnerEntry[] => {
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

    if (selectedSection) {
      filtered = filtered.filter(e => e.legal_description === selectedSection)
    }

    return filtered
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
    const filteredEntries = getFilteredEntries()
    if (filteredEntries.length === 0) return

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
          entries: filteredEntries,
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

  const handleSelectJob = (job: TitleJob) => {
    setActiveJob(job)
    setError(null)
  }

  const formatAddress = (entry: OwnerEntry): string => {
    const parts = []
    if (entry.address) parts.push(entry.address)
    if (entry.city) parts.push(entry.city)
    if (entry.state) parts.push(entry.state)
    if (entry.zip_code) parts.push(entry.zip_code)
    return parts.join(', ')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-green-100 rounded-lg">
          <FileText className="w-6 h-6 text-green-600" />
        </div>
        <div>
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Title
          </h1>
          <p className="text-gray-500 text-sm">
            Consolidate owner and contact info from Oklahoma title opinions
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
                      className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      CSV
                    </button>
                    <button
                      onClick={() => handleExport('excel')}
                      className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      Excel
                    </button>
                    <button
                      onClick={() => handleExport('mineral')}
                      className="flex items-center gap-2 px-3 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
                    >
                      <Copy className="w-4 h-4" />
                      Mineral Format
                    </button>
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-4 gap-4 p-6 border-b border-gray-100">
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {activeJob.result.total_count}
                  </p>
                  <p className="text-sm text-gray-500">Total Entries</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-teal">
                    {getFilteredEntries().length}
                  </p>
                  <p className="text-sm text-gray-500">Filtered</p>
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
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={hideNoAddress}
                      onChange={(e) => setHideNoAddress(e.target.checked)}
                      className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                    />
                    Hide no address
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={hideDuplicates}
                      onChange={(e) => setHideDuplicates(e.target.checked)}
                      className="rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
                    />
                    Hide duplicates
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
                  {(hideNoAddress || hideDuplicates || selectedSection) && (
                    <button
                      onClick={() => {
                        setHideNoAddress(false)
                        setHideDuplicates(false)
                        setSelectedSection('')
                      }}
                      className="text-sm text-tre-teal hover:underline"
                    >
                      Reset Filters
                    </button>
                  )}
                </div>
              </div>

              {/* Preview Table */}
              <div className="p-6">
                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                  <Users className="w-4 h-4" />
                  Owner Entries Preview
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Name</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Type</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Address</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Legal Desc</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Notes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {getFilteredEntries().slice(0, 15).map((entry, i) => (
                        <tr key={i} className={entry.duplicate_flag ? 'bg-yellow-50' : !entry.has_address ? 'bg-red-50' : ''}>
                          <td className="py-2 px-3 text-gray-900">{entry.full_name}</td>
                          <td className="py-2 px-3 text-gray-600 text-xs">{entry.entity_type}</td>
                          <td className="py-2 px-3 text-gray-600">
                            {entry.has_address
                              ? formatAddress(entry)
                              : <span className="text-red-500 text-xs">No address</span>
                            }
                          </td>
                          <td className="py-2 px-3 text-gray-600 text-xs">{entry.legal_description}</td>
                          <td className="py-2 px-3 text-gray-500 text-xs max-w-[200px] truncate" title={entry.notes || ''}>
                            {entry.notes || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {getFilteredEntries().length > 15 && (
                    <p className="text-sm text-gray-500 mt-3 text-center">
                      Showing 15 of {getFilteredEntries().length} filtered entries. Download to see all.
                    </p>
                  )}
                  {getFilteredEntries().length === 0 && (
                    <p className="text-sm text-gray-500 mt-3 text-center">
                      No entries match the current filters.
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
              <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="font-medium">No job selected</p>
              <p className="text-sm mt-1">Upload a file or select a job from the history</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
