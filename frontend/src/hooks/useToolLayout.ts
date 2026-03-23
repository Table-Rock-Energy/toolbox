import { useState, useEffect } from 'react'

const PANEL_COLLAPSED_PREFIX = 'tool-panel-collapsed'

/**
 * Hook for managing tool page layout preferences:
 * - Left panel collapse/expand state
 * - Dual column visibility storage keys (narrow vs wide mode)
 */
export function useToolLayout(tool: string, userId: string | undefined, storageKeyPrefix: string) {
  const uid = userId || 'anon'

  // Panel always starts visible, pages auto-collapse when preview data loads
  const panelKey = `${PANEL_COLLAPSED_PREFIX}-${tool}-${uid}`
  const [panelCollapsed, setPanelCollapsed] = useState(false)

  useEffect(() => {
    localStorage.setItem(panelKey, String(panelCollapsed))
  }, [panelCollapsed, panelKey])

  // Column visibility storage key changes based on panel state
  const narrowStorageKey = `${storageKeyPrefix}-${uid}`
  const wideStorageKey = `${storageKeyPrefix}-wide-${uid}`
  const activeStorageKey = panelCollapsed ? wideStorageKey : narrowStorageKey

  return {
    panelCollapsed,
    setPanelCollapsed,
    togglePanel: () => setPanelCollapsed(prev => !prev),
    activeStorageKey,
    narrowStorageKey,
    wideStorageKey,
  }
}
