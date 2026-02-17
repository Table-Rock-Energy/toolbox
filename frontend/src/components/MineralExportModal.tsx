import { useState } from 'react'
import { Download } from 'lucide-react'
import Modal from './Modal'

interface MineralExportModalProps {
  isOpen: boolean
  onClose: () => void
  onExport: (county: string, campaignName: string) => void
}

export default function MineralExportModal({ isOpen, onClose, onExport }: MineralExportModalProps) {
  const [county, setCounty] = useState('')
  const [campaignName, setCampaignName] = useState('')

  const handleSubmit = () => {
    onExport(county, campaignName)
    onClose()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Mineral Export"
      size="sm"
      footer={
        <>
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-gray-500">
          Optional fields to include in the mineral export.
        </p>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">County</label>
          <input
            type="text"
            value={county}
            onChange={(e) => setCounty(e.target.value)}
            placeholder="e.g. Canadian"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal focus:border-transparent"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Campaign Name</label>
          <input
            type="text"
            value={campaignName}
            onChange={(e) => setCampaignName(e.target.value)}
            placeholder="e.g. Q1 2026 Outreach"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal focus:border-transparent"
          />
        </div>
      </div>
    </Modal>
  )
}
