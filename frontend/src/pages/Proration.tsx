import { useState } from 'react'
import { Calculator, Plus, History, Download } from 'lucide-react'
import { DataTable, StatusBadge, Modal } from '../components'

interface ProrationCalculation {
  id: string
  name: string
  effectiveDate: string
  totalInterest: string
  parties: number
  status: 'draft' | 'calculated' | 'finalized'
  createdAt: string
}

// Sample data
const sampleCalculations: ProrationCalculation[] = [
  {
    id: '1',
    name: 'Smith Family Trust Division',
    effectiveDate: '2024-01-01',
    totalInterest: '100.0%',
    parties: 5,
    status: 'finalized',
    createdAt: '2024-01-05',
  },
  {
    id: '2',
    name: 'Johnson Estate Allocation',
    effectiveDate: '2024-02-01',
    totalInterest: '50.0%',
    parties: 3,
    status: 'calculated',
    createdAt: '2024-01-10',
  },
  {
    id: '3',
    name: 'Williams LLC Interest Split',
    effectiveDate: '2024-03-01',
    totalInterest: '25.0%',
    parties: 2,
    status: 'draft',
    createdAt: '2024-01-12',
  },
]

export default function Proration() {
  const [calculations] = useState<ProrationCalculation[]>(sampleCalculations)
  const [selectedCalc, setSelectedCalc] = useState<ProrationCalculation | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isNewModalOpen, setIsNewModalOpen] = useState(false)

  const handleViewCalculation = (calc: ProrationCalculation) => {
    setSelectedCalc(calc)
    setIsModalOpen(true)
  }

  const getStatusBadge = (status: ProrationCalculation['status']) => {
    switch (status) {
      case 'finalized':
        return <StatusBadge status="success" label="Finalized" />
      case 'calculated':
        return <StatusBadge status="pending" label="Calculated" />
      default:
        return <StatusBadge status="warning" label="Draft" />
    }
  }

  const columns = [
    {
      key: 'name',
      header: 'Calculation Name',
      sortable: true,
      render: (item: ProrationCalculation) => (
        <span className="font-medium text-tre-navy">{item.name}</span>
      ),
    },
    {
      key: 'effectiveDate',
      header: 'Effective Date',
      sortable: true,
    },
    {
      key: 'totalInterest',
      header: 'Total Interest',
      render: (item: ProrationCalculation) => (
        <span className="font-medium">{item.totalInterest}</span>
      ),
    },
    {
      key: 'parties',
      header: 'Parties',
      sortable: true,
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: ProrationCalculation) => getStatusBadge(item.status),
    },
    {
      key: 'createdAt',
      header: 'Created',
      sortable: true,
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-100 rounded-lg">
            <Calculator className="w-6 h-6 text-purple-600" />
          </div>
          <div>
            <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
              Proration
            </h1>
            <p className="text-gray-500 text-sm">
              Calculate interest prorations and allocations
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            <History className="w-4 h-4" />
            History
          </button>
          <button
            onClick={() => setIsNewModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Calculation
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500 mb-1">Total Calculations</p>
          <p className="text-2xl font-oswald font-semibold text-tre-navy">
            {calculations.length}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500 mb-1">Finalized</p>
          <p className="text-2xl font-oswald font-semibold text-green-600">
            {calculations.filter((c) => c.status === 'finalized').length}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500 mb-1">In Progress</p>
          <p className="text-2xl font-oswald font-semibold text-yellow-600">
            {calculations.filter((c) => c.status !== 'finalized').length}
          </p>
        </div>
      </div>

      {/* Calculations Table */}
      <DataTable
        data={calculations}
        columns={columns}
        onRowClick={handleViewCalculation}
        emptyMessage="No proration calculations yet. Create a new calculation to get started."
      />

      {/* Calculation Details Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Proration Details"
        size="lg"
        footer={
          <>
            <button
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Close
            </button>
            <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              <Download className="w-4 h-4" />
              Export
            </button>
            {selectedCalc?.status !== 'finalized' && (
              <button className="px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors">
                Edit Calculation
              </button>
            )}
          </>
        }
      >
        {selectedCalc && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Calculation Name</p>
                <p className="font-medium text-gray-900">{selectedCalc.name}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                {getStatusBadge(selectedCalc.status)}
              </div>
              <div>
                <p className="text-sm text-gray-500">Effective Date</p>
                <p className="font-medium text-gray-900">{selectedCalc.effectiveDate}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Total Interest</p>
                <p className="font-medium text-gray-900">{selectedCalc.totalInterest}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Number of Parties</p>
                <p className="font-medium text-gray-900">{selectedCalc.parties}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Created</p>
                <p className="font-medium text-gray-900">{selectedCalc.createdAt}</p>
              </div>
            </div>

            <div className="border-t border-gray-200 pt-4">
              <h4 className="font-medium text-gray-900 mb-3">Interest Breakdown</h4>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm text-gray-500">
                  Detailed proration breakdown will be displayed here.
                </p>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* New Calculation Modal */}
      <Modal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        title="New Proration Calculation"
        size="lg"
        footer={
          <>
            <button
              onClick={() => setIsNewModalOpen(false)}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button className="px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors">
              Create Calculation
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Calculation Name
            </label>
            <input
              type="text"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
              placeholder="Enter calculation name"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Effective Date
            </label>
            <input
              type="date"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Total Interest (%)
            </label>
            <input
              type="number"
              step="0.01"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
              placeholder="100.00"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
