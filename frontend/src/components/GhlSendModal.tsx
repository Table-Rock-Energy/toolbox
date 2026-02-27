import { useState, useEffect, useMemo } from 'react'
import { Send, Loader2, CheckCircle, XCircle, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react'
import Modal from './Modal'
import { ghlApi } from '../utils/api'
import type {
  GhlConnectionResponse,
  GhlUserResponse,
  BulkContactData,
  BulkSendRequest,
  BulkSendValidationResponse,
  BulkSendResponse,
  ContactResult
} from '../utils/api'

interface GhlSendModalProps {
  isOpen: boolean
  onClose: () => void
  connections: GhlConnectionResponse[]
  contactCount: number
  defaultTag?: string
  rows: Record<string, string>[]
}

type SendStep = 'idle' | 'validating' | 'confirmed' | 'sending' | 'results'

// Helper function to map rows to BulkContactData
function mapRowsToContacts(rows: Record<string, string>[]): BulkContactData[] {
  return rows.map(row => ({
    mineral_contact_system_id: row['Mineral Contact System Id'] || row['mineral_contact_system_id'] || '',
    first_name: row['First Name'] || row['first_name'] || undefined,
    last_name: row['Last Name'] || row['last_name'] || undefined,
    email: row['Email'] || row['email'] || undefined,
    phone: row['Phone'] || row['phone'] || undefined,
    address1: row['Address 1'] || row['address1'] || undefined,
    city: row['City'] || row['city'] || undefined,
    state: row['State'] || row['state'] || undefined,
    postal_code: row['Postal Code'] || row['postal_code'] || undefined,
  })).filter(c => c.mineral_contact_system_id) // Skip rows without ID
}

export default function GhlSendModal({
  isOpen,
  onClose,
  connections,
  contactCount,
  defaultTag = '',
  rows,
}: GhlSendModalProps) {
  const [selectedConnectionId, setSelectedConnectionId] = useState('')
  const [campaignTag, setCampaignTag] = useState(defaultTag)
  const [contactOwner, setContactOwner] = useState('')
  const [smartListName, setSmartListName] = useState('')
  const [manualSms, setManualSms] = useState(false)
  const [users, setUsers] = useState<GhlUserResponse[]>([])
  const [isLoadingUsers, setIsLoadingUsers] = useState(false)

  // Multi-step flow state
  const [sendStep, setSendStep] = useState<SendStep>('idle')
  const [validationResult, setValidationResult] = useState<BulkSendValidationResponse | null>(null)
  const [sendResult, setSendResult] = useState<BulkSendResponse | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [showFailedContacts, setShowFailedContacts] = useState(false)

  // Reset form when modal opens
  useMemo(() => {
    if (isOpen) {
      setSelectedConnectionId('')
      setCampaignTag(defaultTag)
      setContactOwner('')
      setSmartListName('')
      setManualSms(false)
      setUsers([])
      setSendStep('idle')
      setValidationResult(null)
      setSendResult(null)
      setSendError(null)
      setShowFailedContacts(false)
    }
  }, [isOpen, defaultTag])

  // Fetch users when connection is selected
  useEffect(() => {
    if (!selectedConnectionId) {
      setUsers([])
      setContactOwner('')
      return
    }

    const fetchUsers = async () => {
      setIsLoadingUsers(true)
      try {
        const res = await ghlApi.getUsers(selectedConnectionId)
        if (res.data) {
          setUsers(res.data.users)
        }
      } catch {
        setUsers([])
      } finally {
        setIsLoadingUsers(false)
      }
    }

    fetchUsers()
  }, [selectedConnectionId])

  const selectedConnection = connections.find(c => c.id === selectedConnectionId)
  const selectedConnectionName = selectedConnection?.name || ''
  const isReadyToValidate = selectedConnectionId && campaignTag && contactCount > 0

  // Build bulk send request from form state
  const buildRequest = (): BulkSendRequest => ({
    connection_id: selectedConnectionId,
    contacts: mapRowsToContacts(rows),
    campaign_tag: campaignTag,
    manual_sms: manualSms,
    assigned_to: contactOwner || undefined,
    smart_list_name: smartListName || undefined,
  })

  // Step 1 → 2: Validate batch
  const handleValidate = async () => {
    setSendStep('validating')
    setSendError(null)

    try {
      const request = buildRequest()
      const res = await ghlApi.validateBatch(request)

      if (res.error) {
        setSendError(res.error)
        setSendStep('idle')
        return
      }

      if (res.data) {
        setValidationResult(res.data)
        setSendStep('confirmed')
      }
    } catch (err) {
      setSendError(err instanceof Error ? err.message : 'Validation failed')
      setSendStep('idle')
    }
  }

  // Step 3 → 4: Send contacts
  const handleSend = async () => {
    setSendStep('sending')
    setSendError(null)

    try {
      const request = buildRequest()
      const res = await ghlApi.bulkSend(request)

      if (res.error) {
        setSendError(res.error)
        setSendStep('confirmed')
        return
      }

      if (res.data) {
        setSendResult(res.data)
        setSendStep('results')
      }
    } catch (err) {
      setSendError(err instanceof Error ? err.message : 'Send failed')
      setSendStep('confirmed')
    }
  }

  // Go back to idle from confirmed step
  const handleBackToIdle = () => {
    setSendStep('idle')
    setValidationResult(null)
  }

  // Retry send after error
  const handleRetry = () => {
    setSendError(null)
    handleSend()
  }

  // Render footer based on current step
  const renderFooter = () => {
    // Step 1: Idle (form visible)
    if (sendStep === 'idle') {
      return (
        <>
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleValidate}
            disabled={!isReadyToValidate}
            className="flex items-center gap-2 px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
            title={!isReadyToValidate ? 'Fill in connection and campaign tag' : 'Validate and send contacts'}
          >
            <Send className="w-4 h-4" />
            Validate & Send
          </button>
        </>
      )
    }

    // Step 2: Validating
    if (sendStep === 'validating') {
      return (
        <div className="flex items-center gap-2 text-gray-500 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" />
          Validating contacts...
        </div>
      )
    }

    // Step 3: Confirmed (validation split)
    if (sendStep === 'confirmed') {
      const validCount = validationResult?.valid_count || 0
      return (
        <>
          <button
            onClick={handleBackToIdle}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSend}
            className="flex items-center gap-2 px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors text-sm"
          >
            <Send className="w-4 h-4" />
            Send {validCount} Contacts
          </button>
        </>
      )
    }

    // Step 4: Sending
    if (sendStep === 'sending') {
      return (
        <div className="flex items-center gap-2 text-gray-500 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" />
          Sending contacts to GHL...
        </div>
      )
    }

    // Step 5: Results
    if (sendStep === 'results') {
      return (
        <button
          onClick={onClose}
          className="px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors text-sm"
        >
          Close
        </button>
      )
    }

    return null
  }

  // Render content based on current step
  const renderContent = () => {
    // Step 1: Idle (form visible)
    if (sendStep === 'idle') {
      return (
        <div className="space-y-4">
          {sendError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-red-700 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{sendError}</span>
            </div>
          )}

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

          {/* Contact Owner Dropdown */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Contact Owner
            </label>
            {!selectedConnectionId ? (
              <select
                disabled
                className="w-full px-3 py-2 border border-gray-200 rounded-lg disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed"
              >
                <option>Select a connection first</option>
              </select>
            ) : isLoadingUsers ? (
              <div className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 text-gray-500 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading users...
              </div>
            ) : (
              <select
                value={contactOwner}
                onChange={(e) => setContactOwner(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
              >
                <option value="">No owner (optional)</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name} ({user.email})
                  </option>
                ))}
              </select>
            )}
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
      )
    }

    // Step 2: Validating
    if (sendStep === 'validating') {
      return (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <Loader2 className="w-12 h-12 animate-spin text-tre-teal mb-4" />
          <p className="text-gray-600">Validating {contactCount} contacts...</p>
        </div>
      )
    }

    // Step 3: Confirmed (validation split)
    if (sendStep === 'confirmed') {
      const validCount = validationResult?.valid_count || 0
      const invalidCount = validationResult?.invalid_count || 0

      return (
        <div className="space-y-4">
          {sendError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-red-700 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{sendError}</span>
            </div>
          )}

          <div className="text-center py-4">
            <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
            <p className="text-lg font-medium text-green-600 mb-1">
              {validCount} contacts ready to send
            </p>
            {invalidCount > 0 && (
              <p className="text-sm text-amber-600">
                {invalidCount} contacts will be skipped (missing email/phone)
              </p>
            )}
          </div>

          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
            <p><strong>Sub-Account:</strong> {selectedConnectionName}</p>
            <p><strong>Campaign Tag:</strong> {campaignTag}</p>
            {contactOwner && (
              <p><strong>Contact Owner:</strong> {users.find(u => u.id === contactOwner)?.name || 'Unknown'}</p>
            )}
            {smartListName && (
              <p><strong>SmartList:</strong> {smartListName}</p>
            )}
            {manualSms && (
              <p><strong>Manual SMS:</strong> Yes</p>
            )}
          </div>
        </div>
      )
    }

    // Step 4: Sending
    if (sendStep === 'sending') {
      return (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <Loader2 className="w-12 h-12 animate-spin text-tre-teal mb-4" />
          <p className="text-gray-600">Sending contacts to GHL...</p>
          <p className="text-sm text-gray-500 mt-2">This may take a moment...</p>
        </div>
      )
    }

    // Step 5: Results
    if (sendStep === 'results') {
      const createdCount = sendResult?.created_count || 0
      const updatedCount = sendResult?.updated_count || 0
      const failedCount = sendResult?.failed_count || 0
      const skippedCount = sendResult?.skipped_count || 0
      const failedContacts = sendResult?.results.filter(r => r.status === 'failed') || []

      return (
        <div className="space-y-4">
          <div className="text-center py-4">
            <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
            <h3 className="text-lg font-medium text-gray-900 mb-4">Send Complete</h3>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            {createdCount > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-green-600">{createdCount}</div>
                <div className="text-gray-600">Created</div>
              </div>
            )}
            {updatedCount > 0 && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-blue-600">{updatedCount}</div>
                <div className="text-gray-600">Updated</div>
              </div>
            )}
            {failedCount > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-red-600">{failedCount}</div>
                <div className="text-gray-600">Failed</div>
              </div>
            )}
            {skippedCount > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-amber-600">{skippedCount}</div>
                <div className="text-gray-600">Skipped</div>
              </div>
            )}
          </div>

          {/* Failed contacts expandable section */}
          {failedCount > 0 && failedContacts.length > 0 && (
            <div className="border border-red-200 rounded-lg overflow-hidden">
              <button
                onClick={() => setShowFailedContacts(!showFailedContacts)}
                className="w-full flex items-center justify-between px-4 py-3 bg-red-50 hover:bg-red-100 transition-colors text-sm font-medium text-red-800"
              >
                <span>View Failed Contacts</span>
                {showFailedContacts ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </button>
              {showFailedContacts && (
                <div className="p-3 bg-white max-h-60 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="text-left border-b border-gray-200">
                      <tr>
                        <th className="pb-2 font-medium text-gray-700">Contact ID</th>
                        <th className="pb-2 font-medium text-gray-700">Error</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {failedContacts.map((contact, i) => (
                        <tr key={i}>
                          <td className="py-2 text-gray-600">{contact.mineral_contact_system_id}</td>
                          <td className="py-2 text-red-600">{contact.error || 'Unknown error'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )
    }

    return null
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Send to GoHighLevel"
      size="lg"
      footer={renderFooter()}
    >
      {renderContent()}
    </Modal>
  )
}
