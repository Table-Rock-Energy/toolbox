import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import {
  updatePassword,
  EmailAuthProvider,
  reauthenticateWithCredential,
} from 'firebase/auth'
import { User, Lock, Check, AlertCircle } from 'lucide-react'

export default function Profile() {
  const { user } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState('')

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
      // Re-authenticate user first
      const credential = EmailAuthProvider.credential(user.email, currentPassword)
      await reauthenticateWithCredential(user, credential)

      // Update password
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

  const isGoogleUser = user?.providerData?.[0]?.providerId === 'google.com'

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-oswald font-semibold text-white mb-8">
        Profile Settings
      </h1>

      {/* User Info Card */}
      <div className="bg-tre-brown-dark border border-tre-teal/20 rounded-lg p-6 mb-6">
        <div className="flex items-center gap-4 mb-6">
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
            <h2 className="text-xl font-oswald font-medium text-white">
              {user?.displayName || 'User'}
            </h2>
            <p className="text-tre-tan/80">{user?.email}</p>
            <p className="text-xs text-tre-teal mt-1">
              {isGoogleUser ? 'Signed in with Google' : 'Email/Password account'}
            </p>
          </div>
        </div>
      </div>

      {/* Password Change Card */}
      <div className="bg-tre-brown-dark border border-tre-teal/20 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-6">
          <Lock className="w-5 h-5 text-tre-teal" />
          <h2 className="text-xl font-oswald font-medium text-white">
            Change Password
          </h2>
        </div>

        {isGoogleUser ? (
          <p className="text-tre-tan/60 text-sm">
            Password management is handled by Google for your account.
            Visit your Google Account settings to change your password.
          </p>
        ) : (
          <form onSubmit={handlePasswordChange} className="space-y-4">
            <div>
              <label htmlFor="currentPassword" className="block text-tre-tan text-sm mb-1">
                Current Password
              </label>
              <input
                type="password"
                id="currentPassword"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full bg-white border border-tre-teal/30 rounded-lg px-4 py-3 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-tre-teal focus:ring-1 focus:ring-tre-teal transition-colors"
                placeholder="Enter current password"
                required
              />
            </div>

            <div>
              <label htmlFor="newPassword" className="block text-tre-tan text-sm mb-1">
                New Password
              </label>
              <input
                type="password"
                id="newPassword"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full bg-white border border-tre-teal/30 rounded-lg px-4 py-3 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-tre-teal focus:ring-1 focus:ring-tre-teal transition-colors"
                placeholder="Enter new password"
                required
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-tre-tan text-sm mb-1">
                Confirm New Password
              </label>
              <input
                type="password"
                id="confirmPassword"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full bg-white border border-tre-teal/30 rounded-lg px-4 py-3 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-tre-teal focus:ring-1 focus:ring-tre-teal transition-colors"
                placeholder="Confirm new password"
                required
              />
            </div>

            {passwordError && (
              <div className="flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle className="w-4 h-4" />
                {passwordError}
              </div>
            )}

            {passwordSuccess && (
              <div className="flex items-center gap-2 text-green-400 text-sm">
                <Check className="w-4 h-4" />
                {passwordSuccess}
              </div>
            )}

            <button
              type="submit"
              disabled={isChangingPassword}
              className="bg-tre-teal text-tre-navy font-semibold rounded-lg px-6 py-3 hover:bg-tre-teal/90 transition-colors disabled:opacity-50"
            >
              {isChangingPassword ? 'Updating...' : 'Update Password'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
