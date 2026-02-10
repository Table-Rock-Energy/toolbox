import { useState, useEffect } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  FileSearch,
  FileText,
  Calculator,
  DollarSign,
  Database,
  LogOut,
  ChevronRight,
  ChevronLeft,
  User,
  Shield,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

const SIDEBAR_COLLAPSED_KEY = 'sidebar-collapsed'

const toolNavItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Extract', path: '/extract', icon: FileSearch },
  { name: 'Title', path: '/title', icon: FileText },
  { name: 'Proration', path: '/proration', icon: Calculator },
  { name: 'Revenue', path: '/revenue', icon: DollarSign },
  { name: 'Database', path: '/mineral-rights', icon: Database },
]

interface SidebarProps {
  mobile?: boolean
  onClose?: () => void
}

export default function Sidebar({ mobile, onClose }: SidebarProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, signOut, isAdmin } = useAuth()
  const [isUserMenuVisible, setIsUserMenuVisible] = useState(false)
  const [collapsed, setCollapsed] = useState(() => {
    if (mobile) return false
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
    } catch { return false }
  })

  useEffect(() => {
    if (!mobile) {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed))
    }
  }, [collapsed, mobile])

  // Close mobile drawer on route change
  useEffect(() => {
    if (mobile && onClose) {
      onClose()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  // In mobile mode, never collapse
  const isCollapsed = mobile ? false : collapsed

  const getLinkClassName = (path: string) => {
    const isActive = path === '/'
      ? location.pathname === '/'
      : location.pathname.startsWith(path)

    if (isCollapsed) {
      return `flex items-center justify-center p-3 rounded-lg transition-all duration-200 group ${
        isActive
          ? 'bg-tre-teal/20 text-tre-teal'
          : 'text-gray-300 hover:bg-tre-navy/50 hover:text-tre-teal'
      }`
    }

    return `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group ${
      isActive
        ? 'bg-tre-teal/20 text-tre-teal border-l-4 border-tre-teal'
        : 'text-gray-300 hover:bg-tre-navy/50 hover:text-tre-teal'
    }`
  }

  const handleSignOut = async () => {
    await signOut()
  }

  const toggleUserMenu = () => {
    setIsUserMenuVisible(!isUserMenuVisible)
  }

  return (
    <aside className={`${isCollapsed ? 'w-16' : 'w-64'} bg-tre-navy flex flex-col h-full transition-all duration-200 relative`}>
      {/* Collapse Toggle - desktop only */}
      {!mobile && (
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-20 z-50 w-6 h-6 bg-tre-navy border border-tre-teal/30 rounded-full flex items-center justify-center text-tre-teal hover:bg-tre-teal/20 transition-colors"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
        </button>
      )}

      {/* Logo Section */}
      <div className={`${isCollapsed ? 'p-3' : 'p-6'} border-b border-tre-teal/20`}>
        <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'gap-3'}`}>
          <img
            src="/logo-circle.png"
            alt="Table Rock Energy"
            className={`${isCollapsed ? 'w-10 h-10' : 'w-20 h-20'} transition-all duration-200`}
          />
          {!isCollapsed && (
            <div>
              <h1 className="text-white font-oswald font-semibold text-lg tracking-wide">
                Table Rock
              </h1>
              <p className="text-tre-teal text-xs font-light tracking-widest uppercase">
                Tools
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Tools Navigation */}
      <nav className={`flex-1 ${isCollapsed ? 'p-2' : 'p-4'} space-y-1`}>
        {!isCollapsed && (
          <p className="text-tre-tan/60 text-xs uppercase tracking-wider mb-3 px-4">
            Tools
          </p>
        )}
        {toolNavItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={getLinkClassName(item.path)}
            title={isCollapsed ? item.name : undefined}
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            {!isCollapsed && (
              <>
                <span className="font-oswald font-light tracking-wide">{item.name}</span>
                <ChevronRight className="w-4 h-4 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User Section - click to toggle menu (works on touch + mouse) */}
      <div
        className={`${isCollapsed ? 'p-2' : 'p-4'} border-t border-tre-teal/20 relative`}
        onMouseEnter={() => { if (!mobile) setIsUserMenuVisible(true) }}
        onMouseLeave={() => { if (!mobile) setIsUserMenuVisible(false) }}
      >
        {/* Flyout Menu */}
        {isUserMenuVisible && (
          <div className={`absolute bottom-full ${isCollapsed ? 'left-2 right-2' : 'left-4 right-4'} mb-2 bg-tre-navy border border-tre-teal/30 rounded-lg shadow-xl overflow-hidden z-50`}>
            <button
              onClick={() => { navigate('/settings'); setIsUserMenuVisible(false) }}
              className="w-full flex items-center gap-3 px-4 py-3 text-gray-300 hover:bg-tre-teal/10 hover:text-tre-teal transition-colors"
            >
              <User className="w-4 h-4" />
              {!isCollapsed && <span className="text-sm">Profile Settings</span>}
            </button>
            {isAdmin && (
              <button
                onClick={() => { navigate('/admin'); setIsUserMenuVisible(false) }}
                className="w-full flex items-center gap-3 px-4 py-3 text-gray-300 hover:bg-tre-teal/10 hover:text-tre-teal transition-colors border-t border-tre-teal/20"
              >
                <Shield className="w-4 h-4" />
                {!isCollapsed && <span className="text-sm">Admin Settings</span>}
              </button>
            )}
            <button
              onClick={() => { handleSignOut(); setIsUserMenuVisible(false) }}
              className="w-full flex items-center gap-3 px-4 py-3 text-gray-300 hover:text-red-400 hover:bg-red-400/10 transition-colors border-t border-tre-teal/20"
            >
              <LogOut className="w-4 h-4" />
              {!isCollapsed && <span className="text-sm">Sign Out</span>}
            </button>
          </div>
        )}

        {/* User Info - clickable for touch devices */}
        <div
          onClick={toggleUserMenu}
          className={`flex items-center ${isCollapsed ? 'justify-center p-2' : 'gap-3 px-4 py-2'} rounded-lg cursor-pointer hover:bg-tre-navy/50 transition-colors`}
        >
          {user?.photoURL ? (
            <img
              src={user.photoURL}
              alt={user.displayName || 'User'}
              className={`${isCollapsed ? 'w-8 h-8' : 'w-10 h-10'} rounded-full`}
            />
          ) : (
            <div className={`${isCollapsed ? 'w-8 h-8' : 'w-10 h-10'} bg-tre-teal/20 rounded-full flex items-center justify-center`}>
              <span className="text-tre-teal font-medium">
                {user?.displayName?.charAt(0) || user?.email?.charAt(0) || '?'}
              </span>
            </div>
          )}
          {!isCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-white font-oswald font-medium text-sm truncate">
                {user?.displayName || 'User'}
              </p>
              <p className="text-tre-tan/60 text-xs truncate">
                {user?.email || ''}
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
