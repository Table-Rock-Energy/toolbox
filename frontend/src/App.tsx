import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import Extract from './pages/Extract'
import Title from './pages/Title'
import Proration from './pages/Proration'
import Revenue from './pages/Revenue'
import Settings from './pages/Settings'
import Login from './pages/Login'

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, isAuthorized } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-navy flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal"></div>
      </div>
    )
  }

  if (!user || !isAuthorized) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="extract" element={<Extract />} />
        <Route path="title" element={<Title />} />
        <Route path="proration" element={<Proration />} />
        <Route path="revenue" element={<Revenue />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

export default App
