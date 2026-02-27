import { useState, useEffect } from 'react'
import { Send, Loader2, XCircle, AlertCircle, ChevronDown, ChevronUp, CheckCircle } from 'lucide-react'
import Modal from './Modal'
import { ghlApi } from '../utils/api'
import { useSSEProgress } from '../hooks/useSSEProgress'
import type {
  GhlConnectionResponse,
  GhlUserResponse,
  BulkContactData,
  BulkSendRequest,
  BulkSendValidationResponse,
  FailedContactDetail,
} from '../utils/api'

interface GhlSendModalProps {
  isOpen: boolean
  onClose: () => void
  connections: GhlConnectionResponse[]
  contactCount: number
  defaultTag?: string
  rows: Record<string, string>[]
  activeJobId?: string | null
  onJobStarted?: (jobId: string) => void
  onViewFailedContacts?: (failedContacts: FailedContactDetail[]) => void
}

type SendStep = 'idle' | 'validating' | 'confirmed' | 'sending' | 'summary'

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
  })).filter(c => c.mineral_contact_system_id?.trim()) // Skip rows without ID
}

export default function GhlSendModal({
  isOpen,
  onClose,
  connections,
  contactCount,
  defaultTag = '',
  rows,
  activeJobId: propActiveJobId = null,
  onJobStarted,
  onViewFailedContacts,
}: GhlSendModalProps) {
  const [selectedConnectionId, setSelectedConnectionId] = useState('')
  const [campaignTag, setCampaignTag] = useState(defaultTag)
  const [selectedOwners, setSelectedOwners] = useState<string[]>([])
  const [smartListName, setSmartListName] = useState('')
  const [manualSms, setManualSms] = useState(false)
  const [users, setUsers] = useState<GhlUserResponse[]>([])
  const [isLoadingUsers, setIsLoadingUsers] = useState(false)
  const [credentialError, setCredentialError] = useState<string | null>(null)
  const [isCheckingCredentials, setIsCheckingCredentials] = useState(false)

  // Multi-step flow state
  const [sendStep, setSendStep] = useState<SendStep>('idle')
  const [validationResult, setValidationResult] = useState<BulkSendValidationResponse | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [showUpdatedContacts, setShowUpdatedContacts] = useState(false)

  // Active job ID for SSE connection
  const [activeJobId, setActiveJobId] = useState<string | null>(propActiveJobId)

  // SSE progress hook
  const { progress, completionData, isComplete, error: sseError, disconnect } = useSSEProgress(activeJobId)

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      // Only reset if no active job (don't reset during reconnection)
      if (!propActiveJobId) {
        setSelectedConnectionId('')
        setCampaignTag(defaultTag)
        setSelectedOwners([])
        setSmartListName('')
        setManualSms(false)
        setUsers([])
        setSendStep('idle')
        setValidationResult(null)
        setSendError(null)
        setShowUpdatedContacts(false)
        setActiveJobId(null)
        setCredentialError(null)
      } else {
        // Reconnecting to active job
        setActiveJobId(propActiveJobId)
        setSendStep('sending')
      }
    }
  }, [isOpen, defaultTag, propActiveJobId])

  // When SSE completes, transition to summary step
  useEffect(() => {
    if (isComplete && completionData) {
      setSendStep('summary')
    }
  }, [isComplete, completionData])

  // Navigation warning during active send
  useEffect(() => {
    if (sendStep === 'sending') {
      const handleBeforeUnload = (e: BeforeUnloadEvent) => {
        e.preventDefault()
        e.returnValue = 'Send in progress — leaving will disconnect from progress updates. The send will continue on the server.'
      }
      window.addEventListener('beforeunload', handleBeforeUnload)
      return () => window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [sendStep])

  // Quick check credentials when modal opens with a selected connection
  useEffect(() => {
    if (isOpen && selectedConnectionId && sendStep === 'idle') {
      const checkCredentials = async () => {
        setIsCheckingCredentials(true)
        try {
          const res = await ghlApi.quickCheckConnection(selectedConnectionId)
          if (res.data && !res.data.valid) {
            setCredentialError(res.data.error || 'Invalid credentials')
          } else {
            setCredentialError(null)
          }
        } catch {
          setCredentialError('Failed to verify credentials')
        } finally {
          setIsCheckingCredentials(false)
        }
      }
      checkCredentials()
    }
  }, [isOpen, selectedConnectionId, sendStep])

  // Fetch users when connection is selected
  useEffect(() => {
    if (!selectedConnectionId) {
      setUsers([])
      setSelectedOwners([])
      setCredentialError(null)
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
  const isReadyToValidate = selectedConnectionId && campaignTag && contactCount > 0 && !credentialError && !isCheckingCredentials

  // Build bulk send request from form state
  const buildRequest = (): BulkSendRequest => ({
    connection_id: selectedConnectionId,
    contacts: mapRowsToContacts(rows),
    campaign_tag: campaignTag,
    manual_sms: manualSms,
    assigned_to_list: selectedOwners.length > 0 ? selectedOwners : undefined,
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

  // Step 3 → 4: Send contacts (async job)
  const handleSend = async () => {
    setSendStep('sending')
    setSendError(null)

    try {
      const request = buildRequest()
      const res = await ghlApi.startBulkSend(request)

      if (res.error) {
        setSendError(res.error)
        setSendStep('confirmed')
        return
      }

      if (res.data) {
        const jobId = res.data.job_id
        setActiveJobId(jobId)
        if (onJobStarted) {
          onJobStarted(jobId)
        }
        // SSE hook will start automatically when activeJobId is set
      }
    } catch (err) {
      setSendError(err instanceof Error ? err.message : 'Send failed')
      setSendStep('confirmed')
    }
  }

  // Cancel send
  const handleCancel = async () => {
    if (!activeJobId) return

    const confirmed = window.confirm('Stop sending? Already-sent contacts will be kept.')
    if (!confirmed) return

    try {
      await ghlApi.cancelJob(activeJobId)
      disconnect()
      setSendStep('summary')
    } catch (err) {
      console.error('Failed to cancel job:', err)
    }
  }

  // Go back to idle from confirmed step
  const handleBackToIdle = () => {
    setSendStep('idle')
    setValidationResult(null)
  }

  // View failed contacts
  const handleViewFailedContacts = () => {
    if (completionData?.failed_contacts && onViewFailedContacts) {
      onViewFailedContacts(completionData.failed_contacts)
      onClose()
    }
  }

  // Close modal
  const handleClose = () => {
    if (sendStep === 'sending') {
      const confirmed = window.confirm('Send in progress — close anyway? Progress will continue in background.')
      if (!confirmed) return
    }
    disconnect()
    onClose()
  }

  // Render footer based on current step
  const renderFooter = () => {
    // Step 1: Idle (form visible)
    if (sendStep === 'idle') {
      return (
        <>
          <button
            onClick={handleClose}
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
        <button
          onClick={handleCancel}
          className="px-4 py-2 border border-red-300 text-red-700 rounded-lg hover:bg-red-50 transition-colors text-sm"
        >
          Cancel Send
        </button>
      )
    }

    // Step 5: Summary
    if (sendStep === 'summary') {
      const failedCount = completionData?.failed || 0
      const dailyLimitHit = completionData?.dailyLimitHit || false
      return (
        <div className="flex gap-2">
          {failedCount > 0 && (
            <button
              onClick={handleViewFailedContacts}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
            >
              {dailyLimitHit ? 'View Remaining Contacts' : 'View Failed Contacts'}
            </button>
          )}
          <button
            onClick={handleClose}
            className="px-4 py-2 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors text-sm"
          >
            Close
          </button>
        </div>
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
          {credentialError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-red-700 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium mb-1">GHL connection expired</p>
                <p>{credentialError}</p>
                <a href="/admin#ghl-connections" className="text-red-800 underline hover:text-red-900 mt-2 inline-block">
                  Go to Settings to reconnect
                </a>
              </div>
            </div>
          )}
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

          {/* Contact Owner Multi-Select */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Contact Owner {selectedOwners.length > 0 && `(${selectedOwners.length} selected)`}
            </label>
            {selectedOwners.length === 2 && (
              <p className="text-xs text-gray-500 mb-2">
                Contacts will be split evenly between selected owners
              </p>
            )}
            {!selectedConnectionId ? (
              <div className="px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 text-gray-500 text-sm">
                Select a connection first
              </div>
            ) : isLoadingUsers ? (
              <div className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 text-gray-500 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading users...
              </div>
            ) : users.length === 0 ? (
              <div className="px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 text-gray-500 text-sm">
                No users available
              </div>
            ) : (
              <div className="border border-gray-300 rounded-lg p-3 space-y-2 max-h-48 overflow-y-auto">
                {users.map((user) => {
                  const isSelected = selectedOwners.includes(user.id)
                  const isDisabled = !isSelected && selectedOwners.length >= 2
                  return (
                    <label
                      key={user.id}
                      className={`flex items-center gap-2 p-2 rounded hover:bg-gray-50 cursor-pointer ${
                        isDisabled ? 'opacity-50 cursor-not-allowed' : ''
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={isDisabled}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedOwners([...selectedOwners, user.id])
                          } else {
                            setSelectedOwners(selectedOwners.filter(id => id !== user.id))
                          }
                        }}
                        className="w-4 h-4 rounded border-gray-300 text-tre-teal focus:ring-tre-teal disabled:cursor-not-allowed"
                      />
                      <span className="text-sm text-gray-700">
                        {user.name} ({user.email})
                      </span>
                    </label>
                  )
                })}
              </div>
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
            {selectedOwners.length > 0 && (
              <p><strong>Contact Owner{selectedOwners.length > 1 ? 's' : ''}:</strong>{' '}
                {selectedOwners.map(id => users.find(u => u.id === id)?.name || 'Unknown').join(', ')}
                {selectedOwners.length === 2 && ' (even split)'}
              </p>
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

    // Step 4: Sending (progress view)
    if (sendStep === 'sending') {
      const processed = progress?.processed || 0
      const total = progress?.total || contactCount
      const created = progress?.created || 0
      const updated = progress?.updated || 0
      const failed = progress?.failed || 0
      const percent = total > 0 ? (processed / total) * 100 : 0

      return (
        <div className="space-y-4">
          {completionData?.dailyLimitHit && (
            <div className="p-3 bg-yellow-50 border border-yellow-300 rounded-lg flex items-start gap-2 text-yellow-800 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium">Daily limit reached</p>
                <p>{processed} of {total} contacts sent. Remaining contacts can be sent after midnight UTC.</p>
              </div>
            </div>
          )}
          {sseError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-red-700 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{sseError}</span>
            </div>
          )}

          <div className="space-y-3">
            {/* Progress bar */}
            <div>
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>{processed} of {total} processed</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <div
                  className="bg-tre-teal h-full rounded-full transition-all duration-300"
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>

            {/* Counter boxes */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-green-600">{created}</div>
                <div className="text-xs text-gray-600">Created</div>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-blue-600">{updated}</div>
                <div className="text-xs text-gray-600">Updated</div>
              </div>
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-red-600">{failed}</div>
                <div className="text-xs text-gray-600">Failed</div>
              </div>
            </div>
          </div>
        </div>
      )
    }

    // Step 5: Summary
    if (sendStep === 'summary') {
      const created = completionData?.created || 0
      const updated = completionData?.updated || 0
      const failed = completionData?.failed || 0
      const status = completionData?.status || 'completed'
      const updatedContacts = completionData?.updated_contacts || []
      const dailyLimitHit = completionData?.dailyLimitHit || false

      return (
        <div className="space-y-4">
          {dailyLimitHit && (
            <div className="p-3 bg-yellow-50 border border-yellow-300 rounded-lg flex items-start gap-2 text-yellow-800 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium">Daily limit reached</p>
                <p>{created + updated} of {contactCount} contacts sent. Remaining contacts can be sent after midnight UTC.</p>
              </div>
            </div>
          )}
          <div className="text-center py-4">
            {status === 'cancelled' ? (
              <>
                <XCircle className="w-12 h-12 text-amber-600 mx-auto mb-3" />
                <h3 className="text-lg font-medium text-gray-900">Send Cancelled</h3>
              </>
            ) : dailyLimitHit ? (
              <>
                <AlertCircle className="w-12 h-12 text-yellow-600 mx-auto mb-3" />
                <h3 className="text-lg font-medium text-gray-900">Partial Send (Daily Limit)</h3>
              </>
            ) : (
              <>
                <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
                <h3 className="text-lg font-medium text-gray-900">Send Complete</h3>
              </>
            )}
          </div>

          {/* Count summary */}
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-600">{created}</div>
              <div className="text-gray-600">Created</div>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-blue-600">{updated}</div>
              <div className="text-gray-600">Updated</div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-red-600">{failed}</div>
              <div className="text-gray-600">Failed</div>
            </div>
          </div>

          {/* Updated contacts expandable */}
          {updated > 0 && updatedContacts.length > 0 && (
            <div className="border border-blue-200 rounded-lg overflow-hidden">
              <button
                onClick={() => setShowUpdatedContacts(!showUpdatedContacts)}
                className="w-full flex items-center justify-between px-4 py-3 bg-blue-50 hover:bg-blue-100 transition-colors text-sm font-medium text-blue-800"
              >
                <span>View Updated Contacts ({updatedContacts.length} shown)</span>
                {showUpdatedContacts ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </button>
              {showUpdatedContacts && (
                <div className="p-3 bg-white max-h-60 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="text-left border-b border-gray-200">
                      <tr>
                        <th className="pb-2 font-medium text-gray-700">Mineral Contact ID</th>
                        <th className="pb-2 font-medium text-gray-700">GHL Contact ID</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {updatedContacts.map((contact, i) => (
                        <tr key={i}>
                          <td className="py-2 text-gray-600">{contact.mineral_contact_system_id}</td>
                          <td className="py-2 text-blue-600">{contact.ghl_contact_id || 'N/A'}</td>
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
      onClose={handleClose}
      title="Send to GoHighLevel"
      size="lg"
      footer={renderFooter()}
    >
      {renderContent()}
    </Modal>
  )
}
