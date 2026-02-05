import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  FileSearch,
  FileText,
  Calculator,
  DollarSign,
  Settings,
  HelpCircle,
  LogOut,
  ChevronRight,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

const toolNavItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Extract', path: '/extract', icon: FileSearch },
  { name: 'Title', path: '/title', icon: FileText },
  { name: 'Proration', path: '/proration', icon: Calculator },
  { name: 'Revenue', path: '/revenue', icon: DollarSign },
]

const accountNavItems = [
  { name: 'Settings', path: '/settings', icon: Settings },
  { name: 'Help', path: '/help', icon: HelpCircle },
]

export default function Sidebar() {
  const location = useLocation()
  const { user, signOut } = useAuth()

  const getLinkClassName = (path: string) => {
    const isActive = path === '/'
      ? location.pathname === '/'
      : location.pathname.startsWith(path)

    return `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group ${
      isActive
        ? 'bg-tre-teal/20 text-tre-teal border-l-4 border-tre-teal'
        : 'text-gray-300 hover:bg-tre-navy/50 hover:text-tre-teal'
    }`
  }

  return (
    <aside className="w-64 bg-tre-navy flex flex-col h-full">
      {/* Logo Section */}
      <div className="p-6 border-b border-tre-teal/20">
        <div className="flex items-center gap-3">
          <img
            src="/logo-circle.png"
            alt="Table Rock Energy"
            className="w-10 h-10 rounded-lg"
          />
          <div>
            <h1 className="text-white font-oswald font-semibold text-lg tracking-wide">
              Table Rock
            </h1>
            <p className="text-tre-teal text-xs font-light tracking-widest uppercase">
              Tools
            </p>
          </div>
        </div>
      </div>

      {/* Tools Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        <p className="text-tre-tan/60 text-xs uppercase tracking-wider mb-3 px-4">
          Tools
        </p>
        {toolNavItems.map((item) => (
          <NavLink key={item.path} to={item.path} className={getLinkClassName(item.path)}>
            <item.icon className="w-5 h-5" />
            <span className="font-oswald font-light tracking-wide">{item.name}</span>
            <ChevronRight className="w-4 h-4 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
          </NavLink>
        ))}
      </nav>

      {/* Account Section */}
      <div className="p-4 border-t border-tre-teal/20">
        <p className="text-tre-tan/60 text-xs uppercase tracking-wider mb-3 px-4">
          Account
        </p>
        {accountNavItems.map((item) => (
          <NavLink key={item.path} to={item.path} className={getLinkClassName(item.path)}>
            <item.icon className="w-5 h-5" />
            <span className="font-oswald font-light tracking-wide">{item.name}</span>
          </NavLink>
        ))}
      </div>

      {/* User Section */}
      <div className="p-4 border-t border-tre-teal/20">
        <div className="flex items-center gap-3 px-4 py-2">
          {user?.photoURL ? (
            <img
              src={user.photoURL}
              alt={user.displayName || 'User'}
              className="w-10 h-10 rounded-full"
            />
          ) : (
            <div className="w-10 h-10 bg-tre-teal/20 rounded-full flex items-center justify-center">
              <span className="text-tre-teal font-medium">
                {user?.displayName?.charAt(0) || user?.email?.charAt(0) || '?'}
              </span>
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-white font-oswald font-medium text-sm truncate">
              {user?.displayName || 'User'}
            </p>
            <p className="text-tre-tan/60 text-xs truncate">
              {user?.email || ''}
            </p>
          </div>
        </div>
        <button
          onClick={signOut}
          className="w-full flex items-center gap-3 px-4 py-2 mt-2 text-gray-400 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span className="text-sm">Sign Out</span>
        </button>
      </div>
    </aside>
  )
}
