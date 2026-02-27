import { useState, useEffect } from 'react'
import { Trash2 } from 'lucide-react'
import type { GhlConnection } from '../hooks/useLocalStorage'

interface GhlConnectionCardProps {
  connection: GhlConnection
  isEditing: boolean
  onEdit: () => void
  onSave: (updated: GhlConnection) => void
  onDelete: () => void
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
  const [token, setToken] = useState(connection.token)
  const [locationId, setLocationId] = useState(connection.locationId)
  const [validationError, setValidationError] = useState('')

  // Delete confirmation state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Reset form data when connection prop changes (handles card switching)
  useEffect(() => {
    setName(connection.name)
    setToken(connection.token)
    setLocationId(connection.locationId)
    setValidationError('')
    setShowDeleteConfirm(false)
  }, [connection])

  const handleSaveClick = () => {
    // Validate required fields
    if (name.trim().length === 0 || locationId.trim().length === 0) {
      setValidationError('Connection name and Location ID are required')
      return
    }

    setValidationError('')
    onSave({
      ...connection,
      name: name.trim(),
      token: token.trim(),
      locationId: locationId.trim(),
    })
  }

  const handleCancelClick = () => {
    // Reset form state to original connection data
    setName(connection.name)
    setToken(connection.token)
    setLocationId(connection.locationId)
    setValidationError('')
    onCancel()
  }

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation() // Prevent triggering onEdit
    setShowDeleteConfirm(true)
  }

  const handleDeleteConfirm = () => {
    onDelete()
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
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
            >
              Cancel
            </button>
            <button
              onClick={handleDeleteConfirm}
              className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
            >
              Delete
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
          <h3 className="font-semibold text-gray-900 mb-1">{connection.name}</h3>
          <p className="text-sm text-gray-500">Location ID: {connection.locationId}</p>
          <p className="text-xs text-gray-400 mt-2">
            Added {formatDate(connection.createdAt)}
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
            placeholder="Enter token"
            autoComplete="new-password"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
          />
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
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveClick}
            className="flex-1 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
