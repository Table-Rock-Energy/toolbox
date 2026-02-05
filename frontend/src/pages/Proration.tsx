import { useState, useEffect } from 'react'
import { Calculator, Download, Upload, Users, AlertCircle, CheckCircle, AlertTriangle, Database, RefreshCw, Filter, Settings } from 'lucide-react'
import { FileUpload } from '../components'
import { useAuth } from '../contexts/AuthContext'

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
}

interface UploadResponse {
  message: string
  result?: ProcessingResult
}

interface ProrationJob {
  id: string
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
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Proration() {
  const { user } = useAuth()
  const [jobs, setJobs] = useState<ProrationJob[]>([])
  const [activeJob, setActiveJob] = useState<ProrationJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // RRC Data State
  const [rrcStatus, setRrcStatus] = useState<RRCDataStatus | null>(null)
  const [isDownloadingRRC, setIsDownloadingRRC] = useState(false)
  const [rrcMessage, setRrcMessage] = useState<string | null>(null)

  // Processing Options State
  const [showProcessingOptions, setShowProcessingOptions] = useState(false)
  const [newRecordOnly, setNewRecordOnly] = useState(false)
  const [deduplicateByPropertyId, setDeduplicateByPropertyId] = useState(false)
  const [minAppraisalValue, setMinAppraisalValue] = useState<number>(0)
  const [wellTypeOverride, setWellTypeOverride] = useState<string>('auto')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  // Check RRC data status on mount
  useEffect(() => {
    checkRRCStatus()
  }, [])

  const checkRRCStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/proration/rrc/status`)
      if (response.ok) {
        const data = await response.json()
        setRrcStatus(data)
      }
    } catch (err) {
      console.error('Failed to check RRC status:', err)
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
        setRrcMessage(`Downloaded ${data.oil_rows?.toLocaleString() || 0} oil and ${data.gas_rows?.toLocaleString() || 0} gas records`)
        // Refresh status
        await checkRRCStatus()
      } else {
        setError(data.message || 'Failed to download RRC data')
      }
    } catch (err) {
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

  const handleExport = async (format: 'excel' | 'pdf') => {
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
      a.download = `${activeJob.documentName.replace(/\.[^.]+$/, '')}_proration.${format === 'excel' ? 'xlsx' : 'pdf'}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      setError('Failed to export file')
    }
  }

  const handleSelectJob = (job: ProrationJob) => {
    setActiveJob(job)
    setError(null)
  }

  const formatCurrency = (amount?: number): string => {
    if (amount === undefined || amount === null) return '—'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount)
  }

  const formatNumber = (num?: number, decimals: number = 4): string => {
    if (num === undefined || num === null) return '—'
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

  const hasRRCData = rrcStatus?.oil_available || rrcStatus?.gas_available

  // Check if RRC data is older than 30 days
  const isDataStale = (): boolean => {
    if (!rrcStatus?.oil_modified) return false
    const lastModified = new Date(rrcStatus.oil_modified)
    const thirtyDaysAgo = new Date()
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)
    return lastModified < thirtyDaysAgo
  }

  const dataIsStale = hasRRCData && isDataStale()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-purple-100 rounded-lg">
          <Calculator className="w-6 h-6 text-purple-600" />
        </div>
        <div>
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Proration
          </h1>
          <p className="text-gray-500 text-sm">
            Calculate interest prorations and NRA allocations with RRC data
          </p>
        </div>
      </div>

      {/* RRC Data Status Banner */}
      <div className={`rounded-xl border p-4 ${
        dataIsStale ? 'bg-orange-50 border-orange-200' :
        hasRRCData ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className={`w-5 h-5 ${
              dataIsStale ? 'text-orange-600' :
              hasRRCData ? 'text-green-600' : 'text-yellow-600'
            }`} />
            <div>
              <h3 className={`font-medium ${
                dataIsStale ? 'text-orange-800' :
                hasRRCData ? 'text-green-800' : 'text-yellow-800'
              }`}>
                RRC Proration Data
                {dataIsStale && (
                  <span className="ml-2 text-xs font-normal bg-orange-200 text-orange-800 px-2 py-0.5 rounded">
                    Monthly Update Needed
                  </span>
                )}
              </h3>
              {rrcStatus ? (
                <div className="text-sm text-gray-600 mt-1">
                  {hasRRCData ? (
                    <>
                      <span className="font-medium">{(rrcStatus.oil_rows + rrcStatus.gas_rows).toLocaleString()}</span> total records
                      ({rrcStatus.oil_rows.toLocaleString()} oil, {rrcStatus.gas_rows.toLocaleString()} gas)
                      {rrcStatus.oil_modified && (
                        <span className={`ml-2 ${dataIsStale ? 'text-orange-600 font-medium' : 'text-gray-500'}`}>
                          • Last updated: {formatDate(rrcStatus.oil_modified)}
                        </span>
                      )}
                    </>
                  ) : (
                    'No RRC data available. Download to enable NRA calculations.'
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
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors text-sm ${
              dataIsStale
                ? 'bg-orange-600 text-white hover:bg-orange-700'
                : hasRRCData
                  ? 'border border-green-300 text-green-700 hover:bg-green-100'
                  : 'bg-yellow-600 text-white hover:bg-yellow-700'
            } ${isDownloadingRRC ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <RefreshCw className={`w-4 h-4 ${isDownloadingRRC ? 'animate-spin' : ''}`} />
            {isDownloadingRRC ? 'Downloading...' : dataIsStale ? 'Update Now' : hasRRCData ? 'Refresh Data' : 'Download Data'}
          </button>
        </div>
        {dataIsStale && !rrcMessage && (
          <div className="mt-2 text-sm text-orange-700 flex items-center gap-1">
            <AlertTriangle className="w-4 h-4" />
            RRC data is over 30 days old. Please download the latest data for accurate calculations.
          </div>
        )}
        {rrcMessage && (
          <div className="mt-2 text-sm text-green-700 flex items-center gap-1">
            <CheckCircle className="w-4 h-4" />
            {rrcMessage}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Upload and History */}
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
                      onClick={() => handleExport('excel')}
                      className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      Excel
                    </button>
                    <button
                      onClick={() => handleExport('pdf')}
                      className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
                    >
                      <Download className="w-4 h-4" />
                      PDF
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
                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                  <Users className="w-4 h-4" />
                  Proration Preview
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Owner</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">County</th>
                        <th className="text-right py-2 px-3 font-medium text-gray-600">Interest</th>
                        <th className="text-right py-2 px-3 font-medium text-gray-600">RRC Acres</th>
                        <th className="text-right py-2 px-3 font-medium text-gray-600">Est NRA</th>
                        <th className="text-right py-2 px-3 font-medium text-gray-600">$/NRA</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {activeJob.result.rows?.slice(0, 10).map((row, i) => (
                        <tr key={i} className={!row.rrc_acres ? 'bg-red-50' : ''}>
                          <td className="py-2 px-3 text-gray-900">{row.owner}</td>
                          <td className="py-2 px-3 text-gray-600">{row.county}</td>
                          <td className="py-2 px-3 text-gray-600 text-right">
                            {(row.interest * 100).toFixed(6)}%
                          </td>
                          <td className="py-2 px-3 text-gray-600 text-right">
                            {formatNumber(row.rrc_acres, 2)}
                          </td>
                          <td className="py-2 px-3 text-gray-600 text-right">
                            {formatNumber(row.est_nra, 4)}
                          </td>
                          <td className="py-2 px-3 text-gray-600 text-right">
                            {formatCurrency(row.dollars_per_nra)}
                          </td>
                          <td className="py-2 px-3">
                            {row.rrc_acres ? (
                              <span className="text-green-600 text-xs">Matched</span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-red-600 text-xs">
                                <AlertTriangle className="w-3 h-3" />
                                No Match
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {(activeJob.result.rows?.length || 0) > 10 && (
                    <p className="text-sm text-gray-500 mt-3 text-center">
                      Showing 10 of {activeJob.result.total_rows} rows. Download to see all.
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
              <Calculator className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="font-medium">No job selected</p>
              <p className="text-sm mt-1">Upload a CSV or select a job from the history</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
