import { useState } from 'react'
import { Settings as SettingsIcon, User, Bell, Shield, Database, Check, AlertCircle } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import {
  updatePassword,
  EmailAuthProvider,
  reauthenticateWithCredential,
} from 'firebase/auth'

type SettingsSection = 'profile' | 'notifications' | 'security' | 'data'

export default function Settings() {
  const { user } = useAuth()
  const [activeSection, setActiveSection] = useState<SettingsSection>('profile')
  const [notifications, setNotifications] = useState({
    email: true,
    browser: false,
    jobComplete: true,
    weeklyReport: true,
  })

  // Password change state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState('')

  const isGoogleUser = user?.providerData?.[0]?.providerId === 'google.com'

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

  const navItems = [
    { id: 'profile' as const, label: 'Profile', icon: User },
    { id: 'notifications' as const, label: 'Notifications', icon: Bell },
    { id: 'security' as const, label: 'Security', icon: Shield },
    { id: 'data' as const, label: 'Data & Storage', icon: Database },
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sidebar Navigation */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <nav className="space-y-1">
              {navItems.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setActiveSection(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    activeSection === item.id
                      ? 'bg-tre-teal/10 text-tre-teal'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <item.icon className="w-5 h-5" />
                  <span className={activeSection === item.id ? 'font-medium' : ''}>
                    {item.label}
                  </span>
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Settings Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Profile Section */}
          {activeSection === 'profile' && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
                Profile Information
              </h2>
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  {user?.photoURL ? (
                    <img
                      src={user.photoURL}
                      alt={user.displayName || 'User'}
                      className="w-20 h-20 rounded-full"
                    />
                  ) : (
                    <div className="w-20 h-20 bg-tre-brown-medium rounded-full flex items-center justify-center">
                      <User className="w-10 h-10 text-tre-tan" />
                    </div>
                  )}
                  <div>
                    <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                      Change Photo
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Display Name
                    </label>
                    <input
                      type="text"
                      defaultValue={user?.displayName || ''}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                    />
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
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Notifications Section */}
          {activeSection === 'notifications' && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
                Notification Preferences
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
              </div>
            </div>
          )}

          {/* Security Section */}
          {activeSection === 'security' && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
                Security Settings
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
          )}

          {/* Data & Storage Section */}
          {activeSection === 'data' && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
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
          )}

          {/* Save Button */}
          {activeSection !== 'security' && (
            <div className="flex justify-end">
              <button className="px-6 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors">
                Save Changes
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
