import { useState, useRef, useEffect } from 'react'
import { Settings as SettingsIcon, User, Bell, Shield, Database, Check, AlertCircle, Upload, Link2, Plus } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import {
  updatePassword,
  updateProfile,
  EmailAuthProvider,
  reauthenticateWithCredential,
} from 'firebase/auth'
import { GhlConnectionCard } from '../components'
import useLocalStorage from '../hooks/useLocalStorage'
import type { GhlConnection } from '../hooks/useLocalStorage'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export default function Settings() {
  const { user } = useAuth()

  // Section refs for scroll navigation
  const profileRef = useRef<HTMLDivElement>(null)
  const securityRef = useRef<HTMLDivElement>(null)
  const notificationsRef = useRef<HTMLDivElement>(null)
  const ghlRef = useRef<HTMLDivElement>(null)
  const dataRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [notifications, setNotifications] = useState({
    email: true,
    browser: false,
    jobComplete: true,
    weeklyReport: true,
  })
  const [isSavingNotifications, setIsSavingNotifications] = useState(false)
  const [notificationSuccess, setNotificationSuccess] = useState('')

  // Profile form state
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [isSavingProfile, setIsSavingProfile] = useState(false)
  const [profileError, setProfileError] = useState('')
  const [profileSuccess, setProfileSuccess] = useState('')
  const [isUploadingPhoto, setIsUploadingPhoto] = useState(false)

  // Initialize name from user's displayName
  useEffect(() => {
    if (user?.displayName) {
      const parts = user.displayName.trim().split(' ')
      if (parts.length >= 2) {
        setFirstName(parts[0])
        setLastName(parts.slice(1).join(' '))
      } else {
        setFirstName(user.displayName)
        setLastName('')
      }
    }
  }, [user])

  // Load notification preferences from Firestore
  useEffect(() => {
    if (!user?.email) return
    const loadPreferences = async () => {
      try {
        const res = await fetch(`${API_BASE}/admin/preferences/${encodeURIComponent(user.email!)}`)
        if (res.ok) {
          const data = await res.json()
          setNotifications({
            email: data.email_notifications ?? true,
            browser: data.browser_notifications ?? false,
            jobComplete: data.job_complete_alerts ?? true,
            weeklyReport: data.weekly_report ?? true,
          })
        }
      } catch (err) {
        console.error('Failed to load notification preferences:', err)
      }
    }
    loadPreferences()
  }, [user?.email])

  const handleSaveNotifications = async () => {
    if (!user?.email) return
    setIsSavingNotifications(true)
    setNotificationSuccess('')
    try {
      const res = await fetch(`${API_BASE}/admin/preferences/${encodeURIComponent(user.email)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email_notifications: notifications.email,
          browser_notifications: notifications.browser,
          job_complete_alerts: notifications.jobComplete,
          weekly_report: notifications.weeklyReport,
        }),
      })
      if (res.ok) {
        setNotificationSuccess('Notification preferences saved!')
        setTimeout(() => setNotificationSuccess(''), 3000)
      }
    } catch (err) {
      console.error('Failed to save notification preferences:', err)
    } finally {
      setIsSavingNotifications(false)
    }
  }

  // Password change state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState('')

  const isGoogleUser = user?.providerData?.[0]?.providerId === 'google.com'

  // GHL Connections state
  const [connections, setConnections] = useLocalStorage<GhlConnection[]>('ghl_connections', [])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [isAddingNew, setIsAddingNew] = useState(false)
  const [newConnection, setNewConnection] = useState({ name: '', token: '', locationId: '' })
  const [newConnectionError, setNewConnectionError] = useState('')

  const scrollToSection = (ref: React.RefObject<HTMLDivElement | null>) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const handleSaveProfile = async () => {
    if (!user) return

    setIsSavingProfile(true)
    setProfileError('')
    setProfileSuccess('')

    try {
      // Combine first and last name for displayName
      const fullName = [firstName.trim(), lastName.trim()].filter(Boolean).join(' ')
      await updateProfile(user, {
        displayName: fullName || null,
      })
      setProfileSuccess('Profile updated successfully!')
      // Force a re-render by reloading the user
      await user.reload()
    } catch (error) {
      console.error('Error updating profile:', error)
      setProfileError('Failed to update profile. Please try again.')
    } finally {
      setIsSavingProfile(false)
    }
  }

  const handlePhotoClick = () => {
    fileInputRef.current?.click()
  }

  const handlePhotoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !user) return

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setProfileError('Please select an image file.')
      return
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      setProfileError('Image must be less than 5MB.')
      return
    }

    setIsUploadingPhoto(true)
    setProfileError('')
    setProfileSuccess('')

    try {
      // Upload to backend
      const formData = new FormData()
      formData.append('file', file)
      formData.append('user_id', user.uid)

      const response = await fetch(`${API_BASE}/admin/upload-profile-image`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error('Upload failed')
      }

      const data = await response.json()

      if (!data.photo_url) {
        setProfileError('Photo uploaded but URL could not be generated. Please try again.')
        return
      }

      // Update Firebase profile with the new photo URL
      // Add cache-busting timestamp so the browser fetches the new image
      const photoUrl = `${data.photo_url}?t=${Date.now()}`
      await updateProfile(user, {
        photoURL: photoUrl,
      })
      await user.reload()
      setProfileSuccess('Profile photo updated!')
      // Force page reload to show new photo
      window.location.reload()
    } catch (error) {
      console.error('Error uploading photo:', error)
      setProfileError('Failed to upload photo. Please try again.')
    } finally {
      setIsUploadingPhoto(false)
    }
  }

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordError('')
    setPasswordSuccess('')

    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.')
      return
    }

    if (newPassword.length < 6) {
      setPasswordError('Password must be at least 6 characters.')
      return
    }

    if (!user?.email) {
      setPasswordError('No user email found.')
      return
    }

    setIsChangingPassword(true)

    try {
      const credential = EmailAuthProvider.credential(user.email, currentPassword)
      await reauthenticateWithCredential(user, credential)
      await updatePassword(user, newPassword)

      setPasswordSuccess('Password updated successfully!')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (error: unknown) {
      const firebaseError = error as { code?: string }
      if (firebaseError.code === 'auth/wrong-password') {
        setPasswordError('Current password is incorrect.')
      } else if (firebaseError.code === 'auth/requires-recent-login') {
        setPasswordError('Please sign out and sign back in before changing your password.')
      } else {
        setPasswordError('Failed to update password. Please try again.')
      }
    } finally {
      setIsChangingPassword(false)
    }
  }

  const handleAddConnection = () => {
    // Validate required fields
    if (newConnection.name.trim().length === 0 || newConnection.locationId.trim().length === 0) {
      setNewConnectionError('Connection name and Location ID are required')
      return
    }

    const connection: GhlConnection = {
      id: crypto.randomUUID(),
      name: newConnection.name.trim(),
      token: newConnection.token.trim(),
      locationId: newConnection.locationId.trim(),
      createdAt: new Date().toISOString(),
    }

    setConnections((prev) => [...prev, connection])
    setNewConnection({ name: '', token: '', locationId: '' })
    setNewConnectionError('')
    setIsAddingNew(false)
  }

  const handleCancelAdd = () => {
    setNewConnection({ name: '', token: '', locationId: '' })
    setNewConnectionError('')
    setIsAddingNew(false)
  }

  const navItems = [
    { id: 'profile', label: 'Profile', icon: User, ref: profileRef },
    { id: 'security', label: 'Security', icon: Shield, ref: securityRef },
    { id: 'notifications', label: 'Notifications', icon: Bell, ref: notificationsRef },
    { id: 'ghl', label: 'GoHighLevel', icon: Link2, ref: ghlRef },
    { id: 'data', label: 'Data & Storage', icon: Database, ref: dataRef },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-gray-100 rounded-lg">
          <SettingsIcon className="w-6 h-6 text-gray-600" />
        </div>
        <div>
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Settings
          </h1>
          <p className="text-gray-500 text-sm">
            Manage your account and application preferences
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Navigation - Sticky */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl border border-gray-200 p-4 sticky top-6">
            <nav className="space-y-1">
              {navItems.map((item) => (
                <button
                  key={item.id}
                  onClick={() => scrollToSection(item.ref)}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Settings Content - All Sections */}
        <div className="lg:col-span-3 space-y-6">
          {/* Profile Section */}
          <div ref={profileRef} className="bg-white rounded-xl border border-gray-200 p-6 scroll-mt-6">
            <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
              Profile
            </h2>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="relative">
                  {user?.photoURL ? (
                    <img
                      src={user.photoURL}
                      alt={user.displayName || 'User'}
                      className="w-20 h-20 rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-20 h-20 bg-tre-teal/20 rounded-full flex items-center justify-center">
                      <User className="w-10 h-10 text-tre-teal" />
                    </div>
                  )}
                  {isUploadingPhoto && (
                    <div className="absolute inset-0 bg-black/50 rounded-full flex items-center justify-center">
                      <div className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    </div>
                  )}
                </div>
                <div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handlePhotoChange}
                    className="hidden"
                  />
                  <button
                    onClick={handlePhotoClick}
                    disabled={isUploadingPhoto}
                    className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm disabled:opacity-50"
                  >
                    <Upload className="w-4 h-4" />
                    {isUploadingPhoto ? 'Uploading...' : 'Change Photo'}
                  </button>
                  <p className="text-xs text-gray-500 mt-1">Max 5MB, JPG or PNG</p>
                </div>
              </div>

              {profileError && (
                <div className="flex items-center gap-2 text-red-600 text-sm p-3 bg-red-50 rounded-lg">
                  <AlertCircle className="w-4 h-4" />
                  {profileError}
                </div>
              )}

              {profileSuccess && (
                <div className="flex items-center gap-2 text-green-600 text-sm p-3 bg-green-50 rounded-lg">
                  <Check className="w-4 h-4" />
                  {profileSuccess}
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    First Name
                  </label>
                  <input
                    type="text"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
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
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Last name"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  defaultValue={user?.email || ''}
                  disabled
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
                />
                <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
              </div>
              <div className="flex justify-end pt-2">
                <button
                  onClick={handleSaveProfile}
                  disabled={isSavingProfile}
                  className="px-6 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors disabled:opacity-50"
                >
                  {isSavingProfile ? 'Saving...' : 'Save Profile'}
                </button>
              </div>
            </div>
          </div>

          {/* Security Section */}
          <div ref={securityRef} className="bg-white rounded-xl border border-gray-200 p-6 scroll-mt-6">
            <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
              Security
            </h2>

            {/* Account Type Info */}
            <div className="mb-6 p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">
                <span className="font-medium">Account type:</span>{' '}
                {isGoogleUser ? 'Google Sign-In' : 'Email/Password'}
              </p>
              <p className="text-sm text-gray-600 mt-1">
                <span className="font-medium">Email:</span> {user?.email}
              </p>
            </div>

            {isGoogleUser ? (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-blue-800 text-sm">
                  Your account uses Google Sign-In. Password management is handled through your Google Account.
                  Visit{' '}
                  <a
                    href="https://myaccount.google.com/security"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline font-medium"
                  >
                    Google Account Settings
                  </a>{' '}
                  to manage your password.
                </p>
              </div>
            ) : (
              <form onSubmit={handlePasswordChange} className="space-y-4">
                <h3 className="font-medium text-gray-900">Change Password</h3>

                <div>
                  <label htmlFor="currentPassword" className="block text-sm font-medium text-gray-700 mb-1">
                    Current Password
                  </label>
                  <input
                    type="password"
                    id="currentPassword"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                    required
                  />
                </div>

                <div>
                  <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700 mb-1">
                    New Password
                  </label>
                  <input
                    type="password"
                    id="newPassword"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                    required
                  />
                </div>

                <div>
                  <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    id="confirmPassword"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                    required
                  />
                </div>

                {passwordError && (
                  <div className="flex items-center gap-2 text-red-600 text-sm">
                    <AlertCircle className="w-4 h-4" />
                    {passwordError}
                  </div>
                )}

                {passwordSuccess && (
                  <div className="flex items-center gap-2 text-green-600 text-sm">
                    <Check className="w-4 h-4" />
                    {passwordSuccess}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isChangingPassword}
                  className="px-6 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors disabled:opacity-50"
                >
                  {isChangingPassword ? 'Updating...' : 'Update Password'}
                </button>
              </form>
            )}
          </div>

          {/* Notifications Section */}
          <div ref={notificationsRef} className="bg-white rounded-xl border border-gray-200 p-6 scroll-mt-6">
            <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
              Notifications
            </h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="font-medium text-gray-900">Email Notifications</p>
                  <p className="text-sm text-gray-500">Receive updates via email</p>
                </div>
                <button
                  onClick={() => setNotifications((n) => ({ ...n, email: !n.email }))}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    notifications.email ? 'bg-tre-teal' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      notifications.email ? 'left-7' : 'left-1'
                    }`}
                  />
                </button>
              </div>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="font-medium text-gray-900">Browser Notifications</p>
                  <p className="text-sm text-gray-500">Show desktop notifications</p>
                </div>
                <button
                  onClick={() => setNotifications((n) => ({ ...n, browser: !n.browser }))}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    notifications.browser ? 'bg-tre-teal' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      notifications.browser ? 'left-7' : 'left-1'
                    }`}
                  />
                </button>
              </div>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="font-medium text-gray-900">Job Completion Alerts</p>
                  <p className="text-sm text-gray-500">Notify when jobs complete</p>
                </div>
                <button
                  onClick={() => setNotifications((n) => ({ ...n, jobComplete: !n.jobComplete }))}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    notifications.jobComplete ? 'bg-tre-teal' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      notifications.jobComplete ? 'left-7' : 'left-1'
                    }`}
                  />
                </button>
              </div>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="font-medium text-gray-900">Weekly Summary Report</p>
                  <p className="text-sm text-gray-500">Get a weekly activity digest</p>
                </div>
                <button
                  onClick={() => setNotifications((n) => ({ ...n, weeklyReport: !n.weeklyReport }))}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    notifications.weeklyReport ? 'bg-tre-teal' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      notifications.weeklyReport ? 'left-7' : 'left-1'
                    }`}
                  />
                </button>
              </div>
              {notificationSuccess && (
                <div className="flex items-center gap-2 text-green-600 text-sm p-3 bg-green-50 rounded-lg">
                  <Check className="w-4 h-4" />
                  {notificationSuccess}
                </div>
              )}
              <div className="flex justify-end pt-2">
                <button
                  onClick={handleSaveNotifications}
                  disabled={isSavingNotifications}
                  className="px-6 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors disabled:opacity-50"
                >
                  {isSavingNotifications ? 'Saving...' : 'Save Notifications'}
                </button>
              </div>
            </div>
          </div>

          {/* GoHighLevel Connections Section */}
          <div ref={ghlRef} className="bg-white rounded-xl border border-gray-200 p-6 scroll-mt-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-oswald font-semibold text-tre-navy">
                  GoHighLevel Connections
                </h2>
                <span className="px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded">
                  Preview
                </span>
              </div>
              <button
                onClick={() => {
                  setIsAddingNew(true)
                  setEditingId(null)
                }}
                className="flex items-center gap-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm hover:bg-gray-50 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Connection
              </button>
            </div>

            <div className="space-y-4">
              {/* Existing connections */}
              {connections.map((connection) => (
                <GhlConnectionCard
                  key={connection.id}
                  connection={connection}
                  isEditing={editingId === connection.id}
                  onEdit={() => {
                    setEditingId(connection.id)
                    setIsAddingNew(false)
                  }}
                  onSave={(updated) => {
                    setConnections((prev) =>
                      prev.map((c) => (c.id === updated.id ? updated : c))
                    )
                    setEditingId(null)
                  }}
                  onDelete={() => {
                    setConnections((prev) => prev.filter((c) => c.id !== connection.id))
                  }}
                  onCancel={() => {
                    setEditingId(null)
                  }}
                />
              ))}

              {/* Add new connection form */}
              {isAddingNew && (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
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
                        value={newConnection.locationId}
                        onChange={(e) => setNewConnection((prev) => ({ ...prev, locationId: e.target.value }))}
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
                        className="flex-1 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Empty state */}
              {connections.length === 0 && !isAddingNew && (
                <div className="text-center py-8 text-gray-500 text-sm">
                  No connections configured. Click "Add Connection" to get started.
                </div>
              )}
            </div>
          </div>

          {/* Data & Storage Section */}
          <div ref={dataRef} className="bg-white rounded-xl border border-gray-200 p-6 scroll-mt-6">
            <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
              Data & Storage
            </h2>
            <div className="space-y-4">
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="font-medium text-gray-900">Local Storage</p>
                <p className="text-sm text-gray-500 mt-1">
                  Cached data for faster loading. This data is stored locally in your browser.
                </p>
                <button className="mt-3 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors text-sm">
                  Clear Cache
                </button>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="font-medium text-gray-900">Export Data</p>
                <p className="text-sm text-gray-500 mt-1">
                  Download a copy of your processing history and settings.
                </p>
                <button className="mt-3 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors text-sm">
                  Export All Data
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
