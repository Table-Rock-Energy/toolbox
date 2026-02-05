import { useState } from 'react'
import { DollarSign, Download, Upload, FileText, AlertCircle, CheckCircle } from 'lucide-react'
import { FileUpload } from '../components'
import { useAuth } from '../contexts/AuthContext'

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
}

interface RevenueJob {
  id: string
  documentName: string
  user: string
  timestamp: string
  result?: UploadResponse
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Revenue() {
  const { user } = useAuth()
  const [jobs, setJobs] = useState<RevenueJob[]>([])
  const [activeJob, setActiveJob] = useState<RevenueJob | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data: UploadResponse = await response.json()
      newJob.result = data

      setJobs((prev) => [newJob, ...prev])
      setActiveJob(newJob)
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

    try {
      const response = await fetch(`${API_BASE}/revenue/export/csv`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          statements: activeJob.result.statements,
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
    } catch (err) {
      setError('Failed to export file')
    }
  }

  const handleSelectJob = (job: RevenueJob) => {
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

  // Flatten all rows from all statements for preview
  const getAllRows = (): RevenueRow[] => {
    if (!activeJob?.result?.statements) return []
    return activeJob.result.statements.flatMap(s => s.rows)
  }

  // Calculate totals
  const getTotals = () => {
    const rows = getAllRows()
    return {
      gross: rows.reduce((sum, r) => sum + (r.owner_value || 0), 0),
      tax: rows.reduce((sum, r) => sum + (r.owner_tax_amount || 0), 0),
      deductions: rows.reduce((sum, r) => sum + (r.owner_deduct_amount || 0), 0),
      net: rows.reduce((sum, r) => sum + (r.owner_net_revenue || 0), 0),
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-amber-100 rounded-lg">
          <DollarSign className="w-6 h-6 text-amber-600" />
        </div>
        <div>
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Revenue
          </h1>
          <p className="text-gray-500 text-sm">
            Extract revenue statements from EnergyLink and Energy Transfer PDFs
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
                      ) : job.result?.errors?.length ? (
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
                  <button
                    onClick={handleExport}
                    className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
                  >
                    <Download className="w-4 h-4" />
                    M1 CSV
                  </button>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-4 gap-4 p-6 border-b border-gray-100">
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {activeJob.result.statements?.length || 0}
                  </p>
                  <p className="text-sm text-gray-500">Statements</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">
                    {activeJob.result.total_rows || getAllRows().length}
                  </p>
                  <p className="text-sm text-gray-500">Total Rows</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-oswald font-semibold text-green-600">
                    {formatCurrency(getTotals().gross)}
                  </p>
                  <p className="text-sm text-gray-500">Gross Value</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-oswald font-semibold text-tre-teal">
                    {formatCurrency(getTotals().net)}
                  </p>
                  <p className="text-sm text-gray-500">Net Revenue</p>
                </div>
              </div>

              {/* Statement Info */}
              {activeJob.result.statements && activeJob.result.statements.length > 0 && activeJob.result.statements[0].payor && (
                <div className="px-6 py-3 border-b border-gray-100 bg-gray-50">
                  <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                    <span><strong>Payor:</strong> {activeJob.result.statements[0].payor}</span>
                    {activeJob.result.statements[0].check_number && (
                      <span><strong>Check #:</strong> {activeJob.result.statements[0].check_number}</span>
                    )}
                    {activeJob.result.statements[0].check_date && (
                      <span><strong>Date:</strong> {activeJob.result.statements[0].check_date}</span>
                    )}
                  </div>
                </div>
              )}

              {/* Preview Table */}
              <div className="p-6">
                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Revenue Preview
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Property</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">Product</th>
                        <th className="text-right py-2 px-3 font-medium text-gray-600">Interest</th>
                        <th className="text-right py-2 px-3 font-medium text-gray-600">Gross</th>
                        <th className="text-right py-2 px-3 font-medium text-gray-600">Tax</th>
                        <th className="text-right py-2 px-3 font-medium text-gray-600">Net</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {getAllRows().slice(0, 10).map((row, i) => (
                        <tr key={i}>
                          <td className="py-2 px-3 text-gray-900">{row.property_name || '—'}</td>
                          <td className="py-2 px-3 text-gray-600 text-xs">
                            {row.product_description || row.product_code || '—'}
                          </td>
                          <td className="py-2 px-3 text-gray-600 text-right">
                            {row.decimal_interest ? `${(row.decimal_interest * 100).toFixed(6)}%` : '—'}
                          </td>
                          <td className="py-2 px-3 text-gray-600 text-right">
                            {formatCurrency(row.owner_value)}
                          </td>
                          <td className="py-2 px-3 text-red-600 text-right">
                            {row.owner_tax_amount ? `-${formatCurrency(row.owner_tax_amount)}` : '—'}
                          </td>
                          <td className="py-2 px-3 text-green-600 font-medium text-right">
                            {formatCurrency(row.owner_net_revenue)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {getAllRows().length > 10 && (
                    <p className="text-sm text-gray-500 mt-3 text-center">
                      Showing 10 of {activeJob.result.total_rows || getAllRows().length} rows. Download to see all.
                    </p>
                  )}
                </div>
              </div>
            </div>
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
    </div>
  )
}
