import { Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import Extract from './pages/Extract'
import Title from './pages/Title'
import Proration from './pages/Proration'
import Revenue from './pages/Revenue'
import Settings from './pages/Settings'
import Help from './pages/Help'

function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="extract" element={<Extract />} />
        <Route path="title" element={<Title />} />
        <Route path="proration" element={<Proration />} />
        <Route path="revenue" element={<Revenue />} />
        <Route path="settings" element={<Settings />} />
        <Route path="help" element={<Help />} />
      </Route>
    </Routes>
  )
}

export default App
