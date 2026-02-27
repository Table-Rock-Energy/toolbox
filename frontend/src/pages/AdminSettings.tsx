import { useState, useEffect } from 'react'
import {
  Shield,
  Users,
  Plus,
  Pencil,
  Trash2,
  Key,
  Check,
  AlertCircle,
  X,
  Bot,
  Save,
  MapPin,
  Plug,
  Eye,
  EyeOff,
  RefreshCw,
  Copy,
  Lock,
  Link2,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { enrichmentApi, ghlApi } from '../utils/api'
import { GhlConnectionCard } from '../components'
import type { GhlConnectionResponse } from '../utils/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

interface UserEntry {
  email: string
  first_name: string | null
  last_name: string | null
  added_by: string | null
  role: string
  scope: string
  tools: string[]
}

interface AdminOptions {
  roles: string[]
  scopes: string[]
  tools: string[]
}

interface GeminiSettings {
  has_key: boolean
  enabled: boolean
  model: string
  monthly_budget: number
}

interface GoogleMapsSettings {
  has_key: boolean
  enabled: boolean
}

export default function AdminSettings() {
  const { getIdToken } = useAuth()

  const authHeaders = async (): Promise<Record<string, string>> => {
    const token = await getIdToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }

  // Users state
  const [users, setUsers] = useState<UserEntry[]>([])
  const [options, setOptions] = useState<AdminOptions>({ roles: [], scopes: [], tools: [] })
  const [loadingUsers, setLoadingUsers] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Add/Edit modal state
  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState<UserEntry | null>(null)
  const [formEmail, setFormEmail] = useState('')
  const [formFirstName, setFormFirstName] = useState('')
  const [formLastName, setFormLastName] = useState('')
  const [formRole, setFormRole] = useState('user')
  const [formScope, setFormScope] = useState('all')
  const [formTools, setFormTools] = useState<string[]>([])
  const [formPassword, setFormPassword] = useState('')
  const [showFormPassword, setShowFormPassword] = useState(false)
  const [passwordCopied, setPasswordCopied] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Gemini state
  const [gemini, setGemini] = useState<GeminiSettings>({ has_key: false, enabled: false, model: 'gemini-2.5-flash', monthly_budget: 15.0 })
  const [geminiApiKey, setGeminiApiKey] = useState('')
  const [geminiEnabled, setGeminiEnabled] = useState(false)
  const [geminiModel, setGeminiModel] = useState('gemini-2.5-flash')
  const [geminiBudget, setGeminiBudget] = useState(15.0)
  const [isSavingGemini, setIsSavingGemini] = useState(false)
  const [geminiSuccess, setGeminiSuccess] = useState('')
  const [geminiError, setGeminiError] = useState('')

  // Google Maps state
  const [googleMaps, setGoogleMaps] = useState<GoogleMapsSettings>({ has_key: false, enabled: false })
  const [googleMapsApiKey, setGoogleMapsApiKey] = useState('')
  const [googleMapsEnabled, setGoogleMapsEnabled] = useState(false)
  const [isSavingGoogleMaps, setIsSavingGoogleMaps] = useState(false)
  const [googleMapsSuccess, setGoogleMapsSuccess] = useState('')
  const [googleMapsError, setGoogleMapsError] = useState('')

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  // Enrichment / Integrations state
  const [pdlApiKey, setPdlApiKey] = useState('')
  const [searchbugApiKey, setSearchbugApiKey] = useState('')
  const [enrichmentEnabled, setEnrichmentEnabled] = useState(false)
  const [isSavingEnrichment, setIsSavingEnrichment] = useState(false)
  const [enrichmentError, setEnrichmentError] = useState('')
  const [enrichmentSuccess, setEnrichmentSuccess] = useState('')
  const [showPdlKey, setShowPdlKey] = useState(false)
  const [showSearchbugKey, setShowSearchbugKey] = useState(false)
  const [enrichmentLoaded, setEnrichmentLoaded] = useState(false)
  const [pdlConfigured, setPdlConfigured] = useState(false)
  const [searchbugConfigured, setSearchbugConfigured] = useState(false)

  // GHL Connections state
  const [connections, setConnections] = useState<GhlConnectionResponse[]>([])
  const [isLoadingConnections, setIsLoadingConnections] = useState(false)
  const [connectionsError, setConnectionsError] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [isAddingNew, setIsAddingNew] = useState(false)
  const [newConnection, setNewConnection] = useState({ name: '', token: '', location_id: '' })
  const [newConnectionError, setNewConnectionError] = useState('')
  const [isSavingConnection, setIsSavingConnection] = useState(false)

  const fetchConnections = async () => {
    setIsLoadingConnections(true)
    setConnectionsError('')
    try {
      const res = await ghlApi.listConnections()
      if (res.data) {
        setConnections(res.data.connections)
      } else if (res.error) {
        setConnectionsError(res.error)
      }
    } catch {
      setConnectionsError('Failed to load connections')
    } finally {
      setIsLoadingConnections(false)
    }
  }

  const handleAddConnection = async () => {
    if (newConnection.name.trim().length === 0 || newConnection.location_id.trim().length === 0) {
      setNewConnectionError('Connection name and Location ID are required')
      return
    }

    setIsSavingConnection(true)
    setNewConnectionError('')
    try {
      const res = await ghlApi.createConnection({
        name: newConnection.name.trim(),
        token: newConnection.token.trim(),
        location_id: newConnection.location_id.trim(),
      })
      if (res.data) {
        await fetchConnections()
        setNewConnection({ name: '', token: '', location_id: '' })
        setIsAddingNew(false)
      } else if (res.error) {
        setNewConnectionError(res.error)
      }
    } catch {
      setNewConnectionError('Failed to create connection')
    } finally {
      setIsSavingConnection(false)
    }
  }

  const handleCancelAdd = () => {
    setNewConnection({ name: '', token: '', location_id: '' })
    setNewConnectionError('')
    setIsAddingNew(false)
  }

  useEffect(() => {
    fetchUsers()
    fetchOptions()
    fetchGeminiSettings()
    fetchGoogleMapsSettings()
    loadEnrichmentConfig()
    fetchConnections()
  }, [])

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/users`)
      if (res.ok) {
        const data = await res.json()
        setUsers(data.users)
      }
    } catch (err) {
      console.error('Error fetching users:', err)
    } finally {
      setLoadingUsers(false)
    }
  }

  const fetchOptions = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/options`)
      if (res.ok) {
        const data = await res.json()
        setOptions(data)
      }
    } catch (err) {
      console.error('Error fetching options:', err)
    }
  }

  const fetchGeminiSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/settings/gemini`)
      if (res.ok) {
        const data = await res.json()
        setGemini(data)
        setGeminiEnabled(data.enabled)
        setGeminiModel(data.model)
        setGeminiBudget(data.monthly_budget)
      }
    } catch (err) {
      console.error('Error fetching Gemini settings:', err)
    }
  }

  const fetchGoogleMapsSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/settings/google-maps`)
      if (res.ok) {
        const data = await res.json()
        setGoogleMaps(data)
        setGoogleMapsEnabled(data.enabled)
      }
    } catch (err) {
      console.error('Error fetching Google Maps settings:', err)
    }
  }

  const handleSaveGoogleMaps = async () => {
    setIsSavingGoogleMaps(true)
    setGoogleMapsError('')
    setGoogleMapsSuccess('')

    try {
      const body: Record<string, unknown> = {
        enabled: googleMapsEnabled,
      }
      if (googleMapsApiKey) {
        body.api_key = googleMapsApiKey
      }

      const res = await fetch(`${API_BASE}/admin/settings/google-maps`, {
        method: 'PUT',
        headers: await authHeaders(),
        body: JSON.stringify(body),
      })

      if (!res.ok) throw new Error('Failed to update Google Maps settings')

      const data = await res.json()
      setGoogleMaps(data)
      setGoogleMapsApiKey('')
      setGoogleMapsSuccess('Google Maps API settings saved successfully')
    } catch (err) {
      setGoogleMapsError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsSavingGoogleMaps(false)
    }
  }

  const loadEnrichmentConfig = async () => {
    try {
      const { data } = await enrichmentApi.getConfig()
      if (data) {
        setEnrichmentEnabled(data.enabled)
        setPdlConfigured(!!data.pdl_api_key)
        setSearchbugConfigured(!!data.searchbug_api_key)
      }
    } catch {
      // Enrichment not available, ignore
    } finally {
      setEnrichmentLoaded(true)
    }
  }

  const handleSaveEnrichment = async () => {
    setIsSavingEnrichment(true)
    setEnrichmentError('')
    setEnrichmentSuccess('')

    try {
      const updatePayload: { pdl_api_key?: string; searchbug_api_key?: string; enabled?: boolean } = {
        enabled: enrichmentEnabled,
      }

      if (pdlApiKey && !pdlApiKey.startsWith('*')) {
        updatePayload.pdl_api_key = pdlApiKey
      }
      if (searchbugApiKey && !searchbugApiKey.startsWith('*')) {
        updatePayload.searchbug_api_key = searchbugApiKey
      }

      const { data, error } = await enrichmentApi.updateConfig(updatePayload)
      if (error) {
        setEnrichmentError(error)
      } else if (data) {
        setEnrichmentSuccess('Enrichment settings saved successfully!')
        setPdlConfigured(data.status.pdl_configured)
        setSearchbugConfigured(data.status.searchbug_configured)
        setPdlApiKey('')
        setSearchbugApiKey('')
      }
    } catch {
      setEnrichmentError('Failed to save enrichment settings.')
    } finally {
      setIsSavingEnrichment(false)
    }
  }

  const openAddModal = () => {
    setEditingUser(null)
    setFormEmail('')
    setFormFirstName('')
    setFormLastName('')
    setFormRole('user')
    setFormScope('all')
    setFormTools(options.tools.length > 0 ? [...options.tools] : ['extract', 'title', 'proration', 'revenue'])
    setFormPassword('')
    setShowFormPassword(false)
    setPasswordCopied(false)
    setShowModal(true)
    setError('')
  }

  const openEditModal = (u: UserEntry) => {
    setEditingUser(u)
    setFormEmail(u.email)
    setFormFirstName(u.first_name || '')
    setFormLastName(u.last_name || '')
    setFormRole(u.role)
    setFormScope(u.scope)
    setFormTools([...u.tools])
    setFormPassword('')
    setShowFormPassword(false)
    setPasswordCopied(false)
    setShowModal(true)
    setError('')
  }

  const handleToolToggle = (tool: string) => {
    setFormTools(prev =>
      prev.includes(tool)
        ? prev.filter(t => t !== tool)
        : [...prev, tool]
    )
  }

  const generatePassword = () => {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%&*'
    const array = new Uint8Array(16)
    crypto.getRandomValues(array)
    const password = Array.from(array, b => chars[b % chars.length]).join('')
    setFormPassword(password)
    setShowFormPassword(true)
  }

  const copyPassword = async () => {
    if (!formPassword) return
    await navigator.clipboard.writeText(formPassword)
    setPasswordCopied(true)
    setTimeout(() => setPasswordCopied(false), 2000)
  }

  const handleSaveUser = async () => {
    setIsSaving(true)
    setError('')
    setSuccess('')

    try {
      if (editingUser) {
        // Update existing user
        const updateBody: Record<string, unknown> = {
            first_name: formFirstName || null,
            last_name: formLastName || null,
            role: formRole,
            scope: formScope,
            tools: formTools,
        }
        if (formPassword) updateBody.password = formPassword

        const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(editingUser.email)}`, {
          method: 'PUT',
          headers: await authHeaders(),
          body: JSON.stringify(updateBody),
        })

        if (!res.ok) {
          const data = await res.json()
          throw new Error(data.detail || 'Failed to update user')
        }

        setSuccess(`User ${editingUser.email} updated successfully`)
      } else {
        // Add new user
        if (!formEmail) {
          setError('Email is required')
          setIsSaving(false)
          return
        }

        const addBody: Record<string, unknown> = {
            email: formEmail,
            first_name: formFirstName || null,
            last_name: formLastName || null,
            role: formRole,
            scope: formScope,
            tools: formTools,
        }
        if (formPassword) addBody.password = formPassword

        const res = await fetch(`${API_BASE}/admin/users`, {
          method: 'POST',
          headers: await authHeaders(),
          body: JSON.stringify(addBody),
        })

        if (!res.ok) {
          const data = await res.json()
          throw new Error(data.detail || 'Failed to add user')
        }

        setSuccess(`User ${formEmail} added successfully`)
      }

      setShowModal(false)
      fetchUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteUser = async (email: string) => {
    setError('')
    setSuccess('')

    try {
      const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(email)}`, {
        method: 'DELETE',
        headers: await authHeaders(),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to remove user')
      }

      setSuccess(`User ${email} removed`)
      setDeleteTarget(null)
      fetchUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setDeleteTarget(null)
    }
  }

  const handleSaveGemini = async () => {
    setIsSavingGemini(true)
    setGeminiError('')
    setGeminiSuccess('')

    try {
      const body: Record<string, unknown> = {
        enabled: geminiEnabled,
        model: geminiModel,
        monthly_budget: geminiBudget,
      }
      if (geminiApiKey) {
        body.api_key = geminiApiKey
      }

      const res = await fetch(`${API_BASE}/admin/settings/gemini`, {
        method: 'PUT',
        headers: await authHeaders(),
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        throw new Error('Failed to update Gemini settings')
      }

      const data = await res.json()
      setGemini(data)
      setGeminiApiKey('')
      setGeminiSuccess('Gemini AI settings saved successfully')
    } catch (err) {
      setGeminiError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsSavingGemini(false)
    }
  }

  const roleColors: Record<string, string> = {
    admin: 'bg-red-100 text-red-800',
    user: 'bg-blue-100 text-blue-800',
    viewer: 'bg-gray-100 text-gray-800',
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-red-50 rounded-lg">
          <Shield className="w-6 h-6 text-red-600" />
        </div>
        <div>
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Admin Settings
          </h1>
          <p className="text-gray-500 text-sm">
            Manage users, roles, and application configuration
          </p>
        </div>
      </div>

      {/* Global alerts */}
      {error && (
        <div className="flex items-center gap-2 text-red-600 text-sm p-3 bg-red-50 rounded-lg border border-red-200">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button onClick={() => setError('')} className="ml-auto"><X className="w-4 h-4" /></button>
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 text-green-600 text-sm p-3 bg-green-50 rounded-lg border border-green-200">
          <Check className="w-4 h-4 flex-shrink-0" />
          {success}
          <button onClick={() => setSuccess('')} className="ml-auto"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* User Management Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-tre-navy" />
            <h2 className="text-lg font-oswald font-semibold text-tre-navy">
              User Management
            </h2>
          </div>
          <button
            onClick={openAddModal}
            className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />
            Add User
          </button>
        </div>

        {loadingUsers ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-tre-teal border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left">
                  <th className="py-3 px-4 font-medium text-gray-600">User</th>
                  <th className="py-3 px-4 font-medium text-gray-600">Role</th>
                  <th className="py-3 px-4 font-medium text-gray-600">Scope</th>
                  <th className="py-3 px-4 font-medium text-gray-600">Tool Access</th>
                  <th className="py-3 px-4 font-medium text-gray-600 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.email} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div>
                        <p className="font-medium text-gray-900">
                          {[u.first_name, u.last_name].filter(Boolean).join(' ') || u.email}
                        </p>
                        <p className="text-gray-500 text-xs">{u.email}</p>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${roleColors[u.role] || roleColors.user}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-700 capitalize">{u.scope}</span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1">
                        {u.tools.map(tool => (
                          <span key={tool} className="px-2 py-0.5 bg-tre-teal/10 text-tre-navy text-xs rounded capitalize">
                            {tool}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => openEditModal(u)}
                          className="p-1.5 text-gray-400 hover:text-tre-teal transition-colors rounded hover:bg-gray-100"
                          title="Edit user"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        {u.email.toLowerCase() !== 'james@tablerocktx.com' && (
                          <>
                            {deleteTarget === u.email ? (
                              <div className="flex items-center gap-1">
                                <button
                                  onClick={() => handleDeleteUser(u.email)}
                                  className="px-2 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700"
                                >
                                  Confirm
                                </button>
                                <button
                                  onClick={() => setDeleteTarget(null)}
                                  className="px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded hover:bg-gray-300"
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setDeleteTarget(u.email)}
                                className="p-1.5 text-gray-400 hover:text-red-500 transition-colors rounded hover:bg-gray-100"
                                title="Remove user"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Gemini AI Configuration */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Bot className="w-5 h-5 text-tre-navy" />
          <h2 className="text-lg font-oswald font-semibold text-tre-navy">
            Gemini AI Configuration
          </h2>
        </div>

        <div className="space-y-4">
          {/* Status indicator */}
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
            <div className={`w-3 h-3 rounded-full ${gemini.has_key && gemini.enabled ? 'bg-green-500' : 'bg-gray-400'}`} />
            <span className="text-sm text-gray-700">
              {gemini.has_key && gemini.enabled
                ? 'Gemini AI is active'
                : gemini.has_key
                  ? 'API key configured but AI is disabled'
                  : 'No API key configured'}
            </span>
          </div>

          {/* API Key input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              <Key className="w-4 h-4 inline mr-1" />
              Gemini API Key
            </label>
            <input
              type="password"
              value={geminiApiKey}
              onChange={(e) => setGeminiApiKey(e.target.value)}
              placeholder={gemini.has_key ? 'Key is set (enter new key to replace)' : 'Enter your Gemini API key'}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
            />
            <p className="text-xs text-gray-500 mt-1">
              Get an API key from Google AI Studio
            </p>
          </div>

          {/* Enable/Disable toggle */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-medium text-gray-900">Enable AI Validation</p>
              <p className="text-sm text-gray-500">Use Gemini to validate and suggest corrections for extracted data</p>
            </div>
            <button
              onClick={() => setGeminiEnabled(!geminiEnabled)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                geminiEnabled ? 'bg-tre-teal' : 'bg-gray-300'
              }`}
            >
              <span
                className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                  geminiEnabled ? 'left-7' : 'left-1'
                }`}
              />
            </button>
          </div>

          {/* Model selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Model
            </label>
            <select
              value={geminiModel}
              onChange={(e) => setGeminiModel(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal bg-white"
            >
              <option value="gemini-2.5-flash">Gemini 2.5 Flash (fast, affordable)</option>
              <option value="gemini-2.5-pro">Gemini 2.5 Pro (advanced)</option>
              <option value="gemini-2.0-flash">Gemini 2.0 Flash (legacy)</option>
            </select>
          </div>

          {/* Budget */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Monthly Budget (USD)
            </label>
            <input
              type="number"
              value={geminiBudget}
              onChange={(e) => setGeminiBudget(parseFloat(e.target.value) || 0)}
              min={0}
              step={5}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
            />
            <p className="text-xs text-gray-500 mt-1">
              AI requests will stop when the monthly budget is reached
            </p>
          </div>

          {/* Gemini alerts */}
          {geminiError && (
            <div className="flex items-center gap-2 text-red-600 text-sm p-3 bg-red-50 rounded-lg">
              <AlertCircle className="w-4 h-4" />
              {geminiError}
            </div>
          )}
          {geminiSuccess && (
            <div className="flex items-center gap-2 text-green-600 text-sm p-3 bg-green-50 rounded-lg">
              <Check className="w-4 h-4" />
              {geminiSuccess}
            </div>
          )}

          <div className="flex justify-end pt-2">
            <button
              onClick={handleSaveGemini}
              disabled={isSavingGemini}
              className="flex items-center gap-2 px-6 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {isSavingGemini ? 'Saving...' : 'Save AI Settings'}
            </button>
          </div>
        </div>
      </div>

      {/* Google Maps API Configuration */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <MapPin className="w-5 h-5 text-tre-navy" />
          <h2 className="text-lg font-oswald font-semibold text-tre-navy">
            Google Maps API Configuration
          </h2>
        </div>

        <div className="space-y-4">
          {/* Status indicator */}
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
            <div className={`w-3 h-3 rounded-full ${googleMaps.has_key && googleMaps.enabled ? 'bg-green-500' : 'bg-gray-400'}`} />
            <span className="text-sm text-gray-700">
              {googleMaps.has_key && googleMaps.enabled
                ? 'Google Maps address validation is active'
                : googleMaps.has_key
                  ? 'API key configured but validation is disabled'
                  : 'No API key configured'}
            </span>
          </div>

          {/* API Key input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              <Key className="w-4 h-4 inline mr-1" />
              Google Maps API Key
            </label>
            <input
              type="password"
              value={googleMapsApiKey}
              onChange={(e) => setGoogleMapsApiKey(e.target.value)}
              placeholder={googleMaps.has_key ? 'Key is set (enter new key to replace)' : 'Enter your Google Maps API key'}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
            />
            <p className="text-xs text-gray-500 mt-1">
              Requires Geocoding API enabled in Google Cloud Console
            </p>
          </div>

          {/* Enable/Disable toggle */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-medium text-gray-900">Enable Address Validation</p>
              <p className="text-sm text-gray-500">Validate and correct addresses using Google Maps during data enrichment</p>
            </div>
            <button
              onClick={() => setGoogleMapsEnabled(!googleMapsEnabled)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                googleMapsEnabled ? 'bg-tre-teal' : 'bg-gray-300'
              }`}
            >
              <span
                className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                  googleMapsEnabled ? 'left-7' : 'left-1'
                }`}
              />
            </button>
          </div>

          {/* Google Maps alerts */}
          {googleMapsError && (
            <div className="flex items-center gap-2 text-red-600 text-sm p-3 bg-red-50 rounded-lg">
              <AlertCircle className="w-4 h-4" />
              {googleMapsError}
            </div>
          )}
          {googleMapsSuccess && (
            <div className="flex items-center gap-2 text-green-600 text-sm p-3 bg-green-50 rounded-lg">
              <Check className="w-4 h-4" />
              {googleMapsSuccess}
            </div>
          )}

          <div className="flex justify-end pt-2">
            <button
              onClick={handleSaveGoogleMaps}
              disabled={isSavingGoogleMaps}
              className="flex items-center gap-2 px-6 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {isSavingGoogleMaps ? 'Saving...' : 'Save Maps Settings'}
            </button>
          </div>
        </div>
      </div>

      {/* Integrations / Enrichment Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-1">
          <Plug className="w-5 h-5 text-tre-navy" />
          <h2 className="text-lg font-oswald font-semibold text-tre-navy">
            Integrations
          </h2>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Configure API keys for data enrichment services. Enrich names and addresses with phone numbers, emails, social media, and public records.
        </p>

        {!enrichmentLoaded ? (
          <div className="flex items-center gap-2 text-gray-400 text-sm py-4">
            <div className="w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
            Loading configuration...
          </div>
        ) : (
          <div className="space-y-5">
            {/* Master toggle */}
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="font-medium text-gray-900">Enable Data Enrichment</p>
                <p className="text-sm text-gray-500">Turn on enrichment lookups across all tools</p>
              </div>
              <button
                onClick={() => setEnrichmentEnabled((v) => !v)}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  enrichmentEnabled ? 'bg-tre-teal' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    enrichmentEnabled ? 'left-7' : 'left-1'
                  }`}
                />
              </button>
            </div>

            {/* People Data Labs */}
            <div className="p-4 bg-gray-50 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">People Data Labs</p>
                  <p className="text-sm text-gray-500">Phone numbers, emails, and social media profiles</p>
                </div>
                {pdlConfigured && (
                  <span className="flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
                    <Check className="w-3 h-3" /> Configured
                  </span>
                )}
              </div>
              <div className="relative">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  API Key
                </label>
                <div className="relative">
                  <input
                    type={showPdlKey ? 'text' : 'password'}
                    value={pdlApiKey}
                    onChange={(e) => setPdlApiKey(e.target.value)}
                    placeholder={pdlConfigured ? 'Key configured (enter new key to update)' : 'Enter your PDL API key'}
                    className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal font-mono text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPdlKey((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPdlKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  Get your API key at{' '}
                  <a href="https://dashboard.peopledatalabs.com" target="_blank" rel="noopener noreferrer" className="text-tre-teal hover:underline">
                    dashboard.peopledatalabs.com
                  </a>
                </p>
              </div>
            </div>

            {/* SearchBug */}
            <div className="p-4 bg-gray-50 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">SearchBug</p>
                  <p className="text-sm text-gray-500">Deceased records, bankruptcy, liens, and judgments</p>
                </div>
                {searchbugConfigured && (
                  <span className="flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
                    <Check className="w-3 h-3" /> Configured
                  </span>
                )}
              </div>
              <div className="relative">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  API Key
                </label>
                <div className="relative">
                  <input
                    type={showSearchbugKey ? 'text' : 'password'}
                    value={searchbugApiKey}
                    onChange={(e) => setSearchbugApiKey(e.target.value)}
                    placeholder={searchbugConfigured ? 'Key configured (enter new key to update)' : 'Enter your SearchBug API key'}
                    className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal font-mono text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => setShowSearchbugKey((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showSearchbugKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  Get your API key at{' '}
                  <a href="https://www.searchbug.com/api/default.aspx" target="_blank" rel="noopener noreferrer" className="text-tre-teal hover:underline">
                    searchbug.com/api
                  </a>
                </p>
              </div>
            </div>

            {enrichmentError && (
              <div className="flex items-center gap-2 text-red-600 text-sm p-3 bg-red-50 rounded-lg">
                <AlertCircle className="w-4 h-4" />
                {enrichmentError}
              </div>
            )}

            {enrichmentSuccess && (
              <div className="flex items-center gap-2 text-green-600 text-sm p-3 bg-green-50 rounded-lg">
                <Check className="w-4 h-4" />
                {enrichmentSuccess}
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                onClick={handleSaveEnrichment}
                disabled={isSavingEnrichment}
                className="flex items-center gap-2 px-6 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {isSavingEnrichment ? 'Saving...' : 'Save Integrations'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* GoHighLevel Connections */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Link2 className="w-5 h-5 text-tre-navy" />
            <h2 className="text-lg font-oswald font-semibold text-tre-navy">
              GoHighLevel Connections
            </h2>
          </div>
          <button
            onClick={() => {
              setIsAddingNew(true)
              setEditingId(null)
            }}
            className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />
            Add Connection
          </button>
        </div>

        <div className="space-y-4">
          {isLoadingConnections && (
            <div className="text-center py-4 text-gray-500 text-sm">Loading connections...</div>
          )}

          {connectionsError && (
            <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3">{connectionsError}</div>
          )}

          {connections.map((connection) => (
            <GhlConnectionCard
              key={connection.id}
              connection={connection}
              isEditing={editingId === connection.id}
              onEdit={() => {
                setEditingId(connection.id)
                setIsAddingNew(false)
              }}
              onSave={async (data) => {
                const res = await ghlApi.updateConnection(connection.id, data)
                if (res.data) {
                  await fetchConnections()
                  setEditingId(null)
                }
                return res.error || null
              }}
              onDelete={async () => {
                const res = await ghlApi.deleteConnection(connection.id)
                if (res.data) {
                  await fetchConnections()
                }
              }}
              onCancel={() => {
                setEditingId(null)
              }}
              onRefresh={fetchConnections}
            />
          ))}

          {/* Add new connection form */}
          {isAddingNew && (
            <div className="bg-gray-50 rounded-lg p-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Connection Name
                  </label>
                  <input
                    type="text"
                    value={newConnection.name}
                    onChange={(e) => setNewConnection((prev) => ({ ...prev, name: e.target.value }))}
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
                    value={newConnection.token}
                    onChange={(e) => setNewConnection((prev) => ({ ...prev, token: e.target.value }))}
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
                    value={newConnection.location_id}
                    onChange={(e) => setNewConnection((prev) => ({ ...prev, location_id: e.target.value }))}
                    placeholder="e.g., abc123xyz"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                  />
                </div>

                {newConnectionError && (
                  <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3">
                    {newConnectionError}
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    onClick={handleCancelAdd}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleAddConnection}
                    disabled={isSavingConnection}
                    className="flex-1 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors disabled:opacity-50"
                  >
                    {isSavingConnection ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Empty state */}
          {connections.length === 0 && !isAddingNew && !isLoadingConnections && (
            <div className="text-center py-8 text-gray-500 text-sm">
              No connections configured. Click "Add Connection" to get started.
            </div>
          )}
        </div>
      </div>

      {/* Add/Edit User Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowModal(false)} />
          <div className="relative bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-oswald font-semibold text-tre-navy">
                  {editingUser ? 'Edit User' : 'Add New User'}
                </h3>
                <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                {/* Email */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                    disabled={!!editingUser}
                    placeholder="user@example.com"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal disabled:bg-gray-50 disabled:text-gray-500"
                  />
                </div>

                {/* Name */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      First Name
                    </label>
                    <input
                      type="text"
                      value={formFirstName}
                      onChange={(e) => setFormFirstName(e.target.value)}
                      placeholder="First name"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Last Name
                    </label>
                    <input
                      type="text"
                      value={formLastName}
                      onChange={(e) => setFormLastName(e.target.value)}
                      placeholder="Last name"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                    />
                  </div>
                </div>

                {/* Role */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role
                  </label>
                  <select
                    value={formRole}
                    onChange={(e) => setFormRole(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal bg-white"
                  >
                    {(options.roles.length > 0 ? options.roles : ['admin', 'user', 'viewer']).map(r => (
                      <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    {formRole === 'admin' && 'Full access to all settings and user management'}
                    {formRole === 'user' && 'Can use assigned tools and manage own profile'}
                    {formRole === 'viewer' && 'Read-only access to assigned tools'}
                  </p>
                </div>

                {/* Scope */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Scope
                  </label>
                  <select
                    value={formScope}
                    onChange={(e) => setFormScope(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal bg-white"
                  >
                    {(options.scopes.length > 0 ? options.scopes : ['all', 'land', 'revenue', 'operations']).map(s => (
                      <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                    ))}
                  </select>
                </div>

                {/* Tool Access */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Tool Access
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {(options.tools.length > 0 ? options.tools : ['extract', 'title', 'proration', 'revenue']).map(tool => (
                      <label
                        key={tool}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${
                          formTools.includes(tool)
                            ? 'border-tre-teal bg-tre-teal/10 text-tre-navy'
                            : 'border-gray-200 bg-white text-gray-500 hover:bg-gray-50'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={formTools.includes(tool)}
                          onChange={() => handleToolToggle(tool)}
                          className="sr-only"
                        />
                        <div className={`w-4 h-4 rounded border flex items-center justify-center ${
                          formTools.includes(tool) ? 'bg-tre-teal border-tre-teal' : 'border-gray-300'
                        }`}>
                          {formTools.includes(tool) && <Check className="w-3 h-3 text-white" />}
                        </div>
                        <span className="capitalize text-sm font-medium">{tool}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Password */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <Lock className="w-4 h-4 inline mr-1" />
                    {editingUser ? 'Set New Password' : 'Initial Password'}
                  </label>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <input
                        type={showFormPassword ? 'text' : 'password'}
                        value={formPassword}
                        onChange={(e) => setFormPassword(e.target.value)}
                        placeholder={editingUser ? 'Leave blank to keep current' : 'Optional initial password'}
                        className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal font-mono text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setShowFormPassword(v => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showFormPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={generatePassword}
                      className="flex items-center gap-1.5 px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm text-gray-700"
                      title="Generate password"
                    >
                      <RefreshCw className="w-4 h-4" />
                      Generate
                    </button>
                  </div>
                  {formPassword && (
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={copyPassword}
                        className="flex items-center gap-1 text-xs text-tre-teal hover:text-tre-navy transition-colors"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        {passwordCopied ? 'Copied!' : 'Copy to clipboard'}
                      </button>
                      <span className="text-xs text-gray-400">
                        {formPassword.length} characters
                      </span>
                    </div>
                  )}
                  <p className="text-xs text-gray-500 mt-1">
                    {editingUser
                      ? 'Sets a new password for email/password sign-in. Leave blank to keep unchanged.'
                      : 'Creates a Firebase account with email/password sign-in. Leave blank for Google Sign-In only.'}
                  </p>
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                  <button
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveUser}
                    disabled={isSaving}
                    className="flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm disabled:opacity-50"
                  >
                    {isSaving ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <Check className="w-4 h-4" />
                    )}
                    {editingUser ? 'Save Changes' : 'Add User'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
