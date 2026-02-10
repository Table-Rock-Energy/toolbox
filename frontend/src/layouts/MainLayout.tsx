import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import Sidebar from '../components/Sidebar'

const toolNames: Record<string, string> = {
  '/': 'Dashboard',
  '/extract': 'Extract',
  '/title': 'Title',
  '/proration': 'Proration',
  '/revenue': 'Revenue',
  '/settings': 'Settings',
  '/admin': 'Admin Settings',
  '/help': 'Help',
}

export default function MainLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  const currentPage = toolNames[location.pathname] || 'Table Rock Tools'

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Desktop Sidebar - hidden on mobile */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
          />
          {/* Drawer */}
          <div className="relative h-full w-64">
            <Sidebar mobile onClose={() => setMobileOpen(false)} />
            {/* Close button */}
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute top-4 right-4 w-8 h-8 bg-white/20 hover:bg-white/30 rounded-full flex items-center justify-center text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <main className="flex-1 overflow-auto">
        {/* Mobile Header */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 bg-tre-navy">
          <button
            onClick={() => setMobileOpen(true)}
            className="text-white p-1"
            aria-label="Open navigation"
          >
            <Menu className="w-6 h-6" />
          </button>
          <img
            src="/logo-circle.png"
            alt="Table Rock Energy"
            className="w-8 h-8"
          />
          <span className="text-white font-oswald font-semibold tracking-wide">
            {currentPage}
          </span>
        </div>

        {/* Page Content */}
        <div className="p-4 lg:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
