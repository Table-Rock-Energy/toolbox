import { useState } from 'react'
import { DollarSign, Upload, TrendingUp, TrendingDown, BarChart2 } from 'lucide-react'
import { FileUpload, DataTable, StatusBadge } from '../components'

interface RevenueStatement {
  id: string
  filename: string
  operator: string
  period: string
  grossRevenue: number
  netRevenue: number
  status: 'pending' | 'processing' | 'success' | 'error'
  uploadedAt: string
}

// Sample data
const sampleStatements: RevenueStatement[] = [
  {
    id: '1',
    filename: 'chevron_jan_2024.pdf',
    operator: 'Chevron',
    period: 'January 2024',
    grossRevenue: 125000.50,
    netRevenue: 15625.06,
    status: 'success',
    uploadedAt: '2024-01-15',
  },
  {
    id: '2',
    filename: 'conocophillips_jan_2024.pdf',
    operator: 'ConocoPhillips',
    period: 'January 2024',
    grossRevenue: 87500.00,
    netRevenue: 10937.50,
    status: 'success',
    uploadedAt: '2024-01-14',
  },
  {
    id: '3',
    filename: 'eog_jan_2024.pdf',
    operator: 'EOG Resources',
    period: 'January 2024',
    grossRevenue: 0,
    netRevenue: 0,
    status: 'processing',
    uploadedAt: '2024-01-16',
  },
]

export default function Revenue() {
  const [statements, setStatements] = useState<RevenueStatement[]>(sampleStatements)

  const handleFilesSelected = (files: File[]) => {
    const newStatements: RevenueStatement[] = files.map((file, index) => ({
      id: String(Date.now() + index),
      filename: file.name,
      operator: 'Unknown',
      period: 'Unknown',
      grossRevenue: 0,
      netRevenue: 0,
      status: 'pending',
      uploadedAt: new Date().toISOString().split('T')[0],
    }))
    setStatements((prev) => [...newStatements, ...prev])
  }

  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount)
  }

  const totalGross = statements
    .filter((s) => s.status === 'success')
    .reduce((sum, s) => sum + s.grossRevenue, 0)

  const totalNet = statements
    .filter((s) => s.status === 'success')
    .reduce((sum, s) => sum + s.netRevenue, 0)

  const columns = [
    {
      key: 'filename',
      header: 'Document',
      sortable: true,
    },
    {
      key: 'operator',
      header: 'Operator',
      sortable: true,
    },
    {
      key: 'period',
      header: 'Period',
      sortable: true,
    },
    {
      key: 'grossRevenue',
      header: 'Gross Revenue',
      sortable: true,
      render: (item: RevenueStatement) => (
        <span className="font-medium">
          {item.status === 'success' ? formatCurrency(item.grossRevenue) : '-'}
        </span>
      ),
    },
    {
      key: 'netRevenue',
      header: 'Net Revenue',
      sortable: true,
      render: (item: RevenueStatement) => (
        <span className="font-medium text-green-600">
          {item.status === 'success' ? formatCurrency(item.netRevenue) : '-'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: RevenueStatement) => (
        <StatusBadge status={item.status} />
      ),
    },
  ]

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
            Analyze revenue statements and track distributions
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-gray-500">Total Gross Revenue</p>
            <BarChart2 className="w-4 h-4 text-gray-400" />
          </div>
          <p className="text-2xl font-oswald font-semibold text-tre-navy">
            {formatCurrency(totalGross)}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-gray-500">Total Net Revenue</p>
            <TrendingUp className="w-4 h-4 text-green-500" />
          </div>
          <p className="text-2xl font-oswald font-semibold text-green-600">
            {formatCurrency(totalNet)}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-gray-500">Avg. Net %</p>
            <TrendingDown className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-2xl font-oswald font-semibold text-tre-navy">
            {totalGross > 0 ? ((totalNet / totalGross) * 100).toFixed(2) : '0.00'}%
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-gray-500">Statements</p>
            <Upload className="w-4 h-4 text-gray-400" />
          </div>
          <p className="text-2xl font-oswald font-semibold text-tre-navy">
            {statements.filter((s) => s.status === 'success').length}
          </p>
        </div>
      </div>

      {/* Upload Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <FileUpload
          onFilesSelected={handleFilesSelected}
          accept=".pdf,.xlsx,.xls,.csv"
          label="Upload Revenue Statements"
          description="Drop revenue statements here to analyze"
        />
      </div>

      {/* Statements Table */}
      <div>
        <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
          Revenue Statements
        </h2>
        <DataTable
          data={statements}
          columns={columns}
          emptyMessage="No revenue statements uploaded. Upload statements to analyze."
        />
      </div>
    </div>
  )
}
