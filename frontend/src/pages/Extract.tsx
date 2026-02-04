import { useState } from 'react'
import { FileSearch, Play, Download, Eye } from 'lucide-react'
import { FileUpload, DataTable, StatusBadge, Modal, LoadingSpinner } from '../components'

interface ExtractionJob {
  id: string
  filename: string
  status: 'pending' | 'processing' | 'success' | 'error'
  createdAt: string
  completedAt?: string
  extractedFields?: number
}

// Sample data for demonstration
const sampleJobs: ExtractionJob[] = [
  {
    id: '1',
    filename: 'lease_agreement_2024.pdf',
    status: 'success',
    createdAt: '2024-01-15 10:30 AM',
    completedAt: '2024-01-15 10:32 AM',
    extractedFields: 45,
  },
  {
    id: '2',
    filename: 'mineral_deed.pdf',
    status: 'processing',
    createdAt: '2024-01-15 11:00 AM',
  },
  {
    id: '3',
    filename: 'title_opinion.pdf',
    status: 'pending',
    createdAt: '2024-01-15 11:15 AM',
  },
]

export default function Extract() {
  const [jobs, setJobs] = useState<ExtractionJob[]>(sampleJobs)
  const [selectedJob, setSelectedJob] = useState<ExtractionJob | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)

  const handleFilesSelected = (files: File[]) => {
    // Add new jobs for each uploaded file
    const newJobs: ExtractionJob[] = files.map((file, index) => ({
      id: String(Date.now() + index),
      filename: file.name,
      status: 'pending',
      createdAt: new Date().toLocaleString(),
    }))
    setJobs((prev) => [...newJobs, ...prev])
  }

  const handleViewJob = (job: ExtractionJob) => {
    setSelectedJob(job)
    setIsModalOpen(true)
  }

  const handleProcessAll = () => {
    setIsProcessing(true)
    // Simulate processing
    setTimeout(() => {
      setJobs((prev) =>
        prev.map((job) =>
          job.status === 'pending' ? { ...job, status: 'processing' } : job
        )
      )
      setIsProcessing(false)
    }, 1000)
  }

  const columns = [
    {
      key: 'filename',
      header: 'Document',
      sortable: true,
    },
    {
      key: 'status',
      header: 'Status',
      render: (job: ExtractionJob) => (
        <StatusBadge status={job.status} />
      ),
    },
    {
      key: 'createdAt',
      header: 'Uploaded',
      sortable: true,
    },
    {
      key: 'extractedFields',
      header: 'Fields',
      render: (job: ExtractionJob) => (
        job.extractedFields ? (
          <span className="text-tre-navy font-medium">{job.extractedFields}</span>
        ) : (
          <span className="text-gray-400">-</span>
        )
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (job: ExtractionJob) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleViewJob(job)}
            className="p-2 hover:bg-tre-teal/10 rounded-lg transition-colors"
            title="View details"
          >
            <Eye className="w-4 h-4 text-tre-teal" />
          </button>
          {job.status === 'success' && (
            <button
              className="p-2 hover:bg-tre-teal/10 rounded-lg transition-colors"
              title="Download results"
            >
              <Download className="w-4 h-4 text-tre-teal" />
            </button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <FileSearch className="w-6 h-6 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
              Extract
            </h1>
            <p className="text-gray-500 text-sm">
              Extract structured data from documents using AI
            </p>
          </div>
        </div>
        <button
          onClick={handleProcessAll}
          disabled={isProcessing || !jobs.some((j) => j.status === 'pending')}
          className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isProcessing ? (
            <LoadingSpinner size="sm" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          Process All
        </button>
      </div>

      {/* Upload Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <FileUpload
          onFilesSelected={handleFilesSelected}
          accept=".pdf,.docx,.doc,.xlsx,.xls"
          label="Upload Documents"
          description="Drop your documents here to extract data"
        />
      </div>

      {/* Jobs Table */}
      <div>
        <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
          Extraction Jobs
        </h2>
        <DataTable
          data={jobs}
          columns={columns}
          onRowClick={handleViewJob}
          emptyMessage="No extraction jobs yet. Upload documents to get started."
        />
      </div>

      {/* Job Details Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Extraction Details"
        size="lg"
        footer={
          <>
            <button
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Close
            </button>
            {selectedJob?.status === 'success' && (
              <button className="px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors">
                Download Results
              </button>
            )}
          </>
        }
      >
        {selectedJob && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Document</p>
                <p className="font-medium text-gray-900">{selectedJob.filename}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <StatusBadge status={selectedJob.status} />
              </div>
              <div>
                <p className="text-sm text-gray-500">Uploaded</p>
                <p className="font-medium text-gray-900">{selectedJob.createdAt}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Completed</p>
                <p className="font-medium text-gray-900">
                  {selectedJob.completedAt || '-'}
                </p>
              </div>
            </div>

            {selectedJob.status === 'success' && (
              <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-2">Extracted Data Preview</h4>
                <p className="text-sm text-gray-500">
                  {selectedJob.extractedFields} fields extracted from this document.
                </p>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
