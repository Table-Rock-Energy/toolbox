import { useState } from 'react'
import { Settings as SettingsIcon, User, Bell, Shield, Database } from 'lucide-react'

export default function Settings() {
  const [notifications, setNotifications] = useState({
    email: true,
    browser: false,
    jobComplete: true,
    weeklyReport: true,
  })

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
              <button className="w-full flex items-center gap-3 px-4 py-3 rounded-lg bg-tre-teal/10 text-tre-teal">
                <User className="w-5 h-5" />
                <span className="font-medium">Profile</span>
              </button>
              <button className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors">
                <Bell className="w-5 h-5" />
                <span>Notifications</span>
              </button>
              <button className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors">
                <Shield className="w-5 h-5" />
                <span>Security</span>
              </button>
              <button className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors">
                <Database className="w-5 h-5" />
                <span>Data & Storage</span>
              </button>
            </nav>
          </div>
        </div>

        {/* Settings Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Profile Section */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
              Profile Information
            </h2>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="w-20 h-20 bg-tre-brown-medium rounded-full flex items-center justify-center">
                  <User className="w-10 h-10 text-tre-tan" />
                </div>
                <div>
                  <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                    Change Photo
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    First Name
                  </label>
                  <input
                    type="text"
                    defaultValue="User"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Last Name
                  </label>
                  <input
                    type="text"
                    defaultValue="Name"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    defaultValue="user@tablerockenergy.com"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Notifications Section */}
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

          {/* Save Button */}
          <div className="flex justify-end">
            <button className="px-6 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors">
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
