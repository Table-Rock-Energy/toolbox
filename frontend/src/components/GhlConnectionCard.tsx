import { useState, useEffect } from 'react'
import { Trash2, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import type { GhlConnectionResponse } from '../utils/api'

interface GhlConnectionCardProps {
  connection: GhlConnectionResponse
  isEditing: boolean
  onEdit: () => void
  onSave: (data: { name?: string; token?: string; location_id?: string }) => Promise<string | null>
  onDelete: () => Promise<void>
  onCancel: () => void
}

export default function GhlConnectionCard({
  connection,
  isEditing,
  onEdit,
  onSave,
  onDelete,
  onCancel,
}: GhlConnectionCardProps) {
  // Form state for edit mode
  const [name, setName] = useState(connection.name)
  const [token, setToken] = useState('')
  const [locationId, setLocationId] = useState(connection.location_id)
  const [validationError, setValidationError] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  // Delete confirmation state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Reset form data when connection prop changes or editing starts
  useEffect(() => {
    setName(connection.name)
    setToken('')
    setLocationId(connection.location_id)
    setValidationError('')
    setShowDeleteConfirm(false)
  }, [connection, isEditing])

  const handleSaveClick = async () => {
    if (name.trim().length === 0 || locationId.trim().length === 0) {
      setValidationError('Connection name and Location ID are required')
      return
    }

    setValidationError('')
    setIsSaving(true)
    try {
      const data: { name?: string; token?: string; location_id?: string } = {
        name: name.trim(),
        location_id: locationId.trim(),
      }
      if (token.trim()) {
        data.token = token.trim()
      }
      const error = await onSave(data)
      if (error) {
        setValidationError(error)
      }
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancelClick = () => {
    setName(connection.name)
    setToken('')
    setLocationId(connection.location_id)
    setValidationError('')
    onCancel()
  }

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowDeleteConfirm(true)
  }

  const handleDeleteConfirm = async () => {
    setIsDeleting(true)
    await onDelete()
    setIsDeleting(false)
  }

  const handleDeleteCancel = () => {
    setShowDeleteConfirm(false)
  }

  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  const validationIcon = connection.validation_status === 'valid'
    ? <CheckCircle className="w-4 h-4 text-green-500" />
    : connection.validation_status === 'invalid'
      ? <XCircle className="w-4 h-4 text-red-500" />
      : null

  // Display mode
  if (!isEditing) {
    if (showDeleteConfirm) {
      return (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-gray-900 mb-4">
            Delete <span className="font-semibold">{connection.name}</span>?
          </p>
          <div className="flex gap-3">
            <button
              onClick={handleDeleteCancel}
              disabled={isDeleting}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
              className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm disabled:opacity-50"
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>
      )
    }

    return (
      <div
        onClick={onEdit}
        className="bg-white rounded-xl border border-gray-200 p-6 hover:border-tre-teal cursor-pointer transition-colors relative"
      >
        <button
          onClick={handleDeleteClick}
          className="absolute top-4 right-4 text-gray-400 hover:text-red-600 transition-colors"
          aria-label="Delete connection"
        >
          <Trash2 className="w-4 h-4" />
        </button>

        <div className="pr-8">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-gray-900">{connection.name}</h3>
            {validationIcon}
          </div>
          <p className="text-sm text-gray-500">Location ID: {connection.location_id}</p>
          <p className="text-sm text-gray-500">Token: ****{connection.token_last4}</p>
          <p className="text-xs text-gray-400 mt-2">
            Added {formatDate(connection.created_at)}
          </p>
        </div>
      </div>
    )
  }

  // Edit mode
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Connection Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Main Account"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Private Integration Token
          </label>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Leave blank to keep current token"
            autoComplete="new-password"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
          />
          <p className="text-xs text-gray-500 mt-1">Current token: ****{connection.token_last4}</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Location ID
          </label>
          <input
            type="text"
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            placeholder="e.g., abc123xyz"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
          />
        </div>

        {validationError && (
          <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3">
            {validationError}
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            onClick={handleCancelClick}
            disabled={isSaving}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveClick}
            disabled={isSaving}
            className="flex-1 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors disabled:opacity-50"
          >
            {isSaving ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Saving...
              </span>
            ) : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
