import { useState, useMemo } from 'react'
import { Send } from 'lucide-react'
import Modal from './Modal'
import type { GhlConnection } from '../hooks/useLocalStorage'

interface GhlSendModalProps {
  isOpen: boolean
  onClose: () => void
  connections: GhlConnection[]
  contactCount: number
  defaultTag?: string
}

export default function GhlSendModal({
  isOpen,
  onClose,
  connections,
  contactCount,
  defaultTag = '',
}: GhlSendModalProps) {
  const [selectedConnectionId, setSelectedConnectionId] = useState('')
  const [campaignTag, setCampaignTag] = useState(defaultTag)
  const [smartListName, setSmartListName] = useState('')
  const [manualSms, setManualSms] = useState(false)

  // Reset form when modal opens
  useMemo(() => {
    if (isOpen) {
      setSelectedConnectionId('')
      setCampaignTag(defaultTag)
      setSmartListName('')
      setManualSms(false)
    }
  }, [isOpen, defaultTag])

  // Get selected connection name for summary
  const selectedConnection = connections.find(c => c.id === selectedConnectionId)
  const selectedConnectionName = selectedConnection?.name || ''

  const footer = (
    <>
      <button
        onClick={onClose}
        className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
      >
        Cancel
      </button>
      <button
        disabled
        className="flex items-center gap-2 px-4 py-2 bg-tre-teal text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm"
        title="GHL integration coming soon"
      >
        <Send className="w-4 h-4" />
        Send to GHL
      </button>
      <span className="px-2 py-1 bg-amber-100 text-amber-700 text-xs font-medium rounded">
        Preview
      </span>
    </>
  )

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Send to GoHighLevel"
      size="lg"
      footer={footer}
    >
      <div className="space-y-4">
        {/* Sub-Account Selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Sub-Account
          </label>
          <select
            value={selectedConnectionId}
            onChange={(e) => setSelectedConnectionId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
          >
            <option value="">Select a connection...</option>
            {connections.map((connection) => (
              <option key={connection.id} value={connection.id}>
                {connection.name}
              </option>
            ))}
          </select>
        </div>

        {/* Campaign Tag Input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Campaign Tag
          </label>
          <input
            type="text"
            value={campaignTag}
            onChange={(e) => setCampaignTag(e.target.value)}
            placeholder="e.g., Spring 2026 Mailing"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
          />
        </div>

        {/* Contact Owner Dropdown (disabled in stub mode) */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Contact Owner
          </label>
          <select
            disabled
            className="w-full px-3 py-2 border border-gray-200 rounded-lg disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed"
          >
            <option>Connect GHL to load owners</option>
          </select>
        </div>

        {/* SmartList Name Field */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            SmartList Name
          </label>
          <input
            type="text"
            value={smartListName}
            onChange={(e) => setSmartListName(e.target.value)}
            placeholder="e.g., Spring 2026 Campaign"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
          />
        </div>

        {/* Manual SMS Checkbox */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="manualSms"
            checked={manualSms}
            onChange={(e) => setManualSms(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-tre-teal focus:ring-tre-teal"
          />
          <label htmlFor="manualSms" className="text-sm text-gray-700">
            Apply manual SMS tag to all contacts
          </label>
        </div>

        {/* Summary Line */}
        {selectedConnectionId && contactCount > 0 && (
          <div className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3 mt-4">
            Sending {contactCount} contacts to {selectedConnectionName} with tag "{campaignTag || '(no tag)'}"
          </div>
        )}
      </div>
    </Modal>
  )
}
