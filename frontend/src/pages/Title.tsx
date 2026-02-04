import { useState } from 'react'
import { FileText, Search, Filter, Plus } from 'lucide-react'
import { DataTable, StatusBadge, Modal } from '../components'

interface TitleRecord {
  id: string
  tractId: string
  county: string
  state: string
  legalDescription: string
  owner: string
  mineralInterest: string
  status: 'active' | 'pending' | 'inactive'
  lastUpdated: string
}

// Sample data
const sampleTitles: TitleRecord[] = [
  {
    id: '1',
    tractId: 'TR-2024-001',
    county: 'Reeves',
    state: 'TX',
    legalDescription: 'Section 12, Block A-1, PSL Survey',
    owner: 'Smith Family Trust',
    mineralInterest: '12.5%',
    status: 'active',
    lastUpdated: '2024-01-10',
  },
  {
    id: '2',
    tractId: 'TR-2024-002',
    county: 'Ward',
    state: 'TX',
    legalDescription: 'Section 8, Block 34, H&TC RR Co Survey',
    owner: 'Johnson Estate',
    mineralInterest: '6.25%',
    status: 'active',
    lastUpdated: '2024-01-08',
  },
  {
    id: '3',
    tractId: 'TR-2024-003',
    county: 'Loving',
    state: 'TX',
    legalDescription: 'Section 22, Block 55, T&P RR Co Survey',
    owner: 'Williams LLC',
    mineralInterest: '25.0%',
    status: 'pending',
    lastUpdated: '2024-01-05',
  },
]

export default function Title() {
  const [titles] = useState<TitleRecord[]>(sampleTitles)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTitle, setSelectedTitle] = useState<TitleRecord | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  const filteredTitles = titles.filter((title) =>
    title.tractId.toLowerCase().includes(searchQuery.toLowerCase()) ||
    title.county.toLowerCase().includes(searchQuery.toLowerCase()) ||
    title.owner.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleViewTitle = (title: TitleRecord) => {
    setSelectedTitle(title)
    setIsModalOpen(true)
  }

  const columns = [
    {
      key: 'tractId',
      header: 'Tract ID',
      sortable: true,
      render: (item: TitleRecord) => (
        <span className="font-medium text-tre-navy">{item.tractId}</span>
      ),
    },
    {
      key: 'county',
      header: 'Location',
      sortable: true,
      render: (item: TitleRecord) => (
        <span>{item.county}, {item.state}</span>
      ),
    },
    {
      key: 'owner',
      header: 'Owner',
      sortable: true,
    },
    {
      key: 'mineralInterest',
      header: 'Interest',
      sortable: true,
      render: (item: TitleRecord) => (
        <span className="font-medium">{item.mineralInterest}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: TitleRecord) => (
        <StatusBadge
          status={item.status === 'active' ? 'success' : item.status === 'pending' ? 'pending' : 'warning'}
          label={item.status.charAt(0).toUpperCase() + item.status.slice(1)}
        />
      ),
    },
    {
      key: 'lastUpdated',
      header: 'Last Updated',
      sortable: true,
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-100 rounded-lg">
            <FileText className="w-6 h-6 text-green-600" />
          </div>
          <div>
            <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
              Title
            </h1>
            <p className="text-gray-500 text-sm">
              Manage and search mineral title records
            </p>
          </div>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors">
          <Plus className="w-4 h-4" />
          New Title
        </button>
      </div>

      {/* Search and Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex items-center gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by tract ID, county, or owner..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            <Filter className="w-4 h-4" />
            Filters
          </button>
        </div>
      </div>

      {/* Titles Table */}
      <DataTable
        data={filteredTitles}
        columns={columns}
        onRowClick={handleViewTitle}
        emptyMessage="No title records found. Add a new title to get started."
      />

      {/* Title Details Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Title Details"
        size="lg"
        footer={
          <>
            <button
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Close
            </button>
            <button className="px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors">
              Edit Title
            </button>
          </>
        }
      >
        {selectedTitle && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Tract ID</p>
                <p className="font-medium text-gray-900">{selectedTitle.tractId}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <StatusBadge
                  status={selectedTitle.status === 'active' ? 'success' : 'pending'}
                  label={selectedTitle.status.charAt(0).toUpperCase() + selectedTitle.status.slice(1)}
                />
              </div>
              <div>
                <p className="text-sm text-gray-500">County</p>
                <p className="font-medium text-gray-900">{selectedTitle.county}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">State</p>
                <p className="font-medium text-gray-900">{selectedTitle.state}</p>
              </div>
              <div className="col-span-2">
                <p className="text-sm text-gray-500">Legal Description</p>
                <p className="font-medium text-gray-900">{selectedTitle.legalDescription}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Owner</p>
                <p className="font-medium text-gray-900">{selectedTitle.owner}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Mineral Interest</p>
                <p className="font-medium text-gray-900">{selectedTitle.mineralInterest}</p>
              </div>
            </div>

            <div className="border-t border-gray-200 pt-4">
              <h4 className="font-medium text-gray-900 mb-2">Chain of Title</h4>
              <p className="text-sm text-gray-500">
                View the complete ownership history for this tract.
              </p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
