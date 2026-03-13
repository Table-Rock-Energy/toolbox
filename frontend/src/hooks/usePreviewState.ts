import { useState, useMemo, useCallback, useEffect, useRef } from 'react'

export interface UsePreviewStateOptions<T> {
  entries: T[]
  keyField: keyof T
  flagField?: keyof T
}

export interface PreviewState<T> {
  // Core state
  previewEntries: T[]
  excludedKeys: Set<string>
  editedFields: Map<string, Partial<T>>

  // Derived
  entriesToExport: T[]
  flaggedCount: number

  // Actions
  updateEntries: (entries: T[]) => void
  toggleExclude: (key: string) => void
  toggleExcludeAll: () => void
  editField: (key: string, field: keyof T, value: unknown) => void
  resetEdits: () => void

  // Selection helpers
  isAllSelected: boolean
  isSomeSelected: boolean
  isExcluded: (key: string) => boolean
}

export function usePreviewState<T extends Record<string, unknown>>(
  options: UsePreviewStateOptions<T>
): PreviewState<T> {
  const { entries: sourceEntries, keyField, flagField = 'flagged' as keyof T } = options

  const [overrideEntries, setOverrideEntries] = useState<T[] | null>(null)
  const [excludedKeys, setExcludedKeys] = useState<Set<string>>(new Set())
  const [editedFields, setEditedFields] = useState<Map<string, Partial<T>>>(new Map())

  // Track sourceEntries reference to reset state when new data arrives
  const prevSourceRef = useRef(sourceEntries)
  useEffect(() => {
    if (prevSourceRef.current !== sourceEntries) {
      prevSourceRef.current = sourceEntries
      setOverrideEntries(null)
      setExcludedKeys(new Set())
      setEditedFields(new Map())
    }
  }, [sourceEntries])

  const entries = overrideEntries ?? sourceEntries

  // updateEntries: replace full entry array (for enrichment callbacks)
  // Does NOT reset edits -- edits are keyed by stable key
  const updateEntries = useCallback((newEntries: T[]) => {
    setOverrideEntries(newEntries)
  }, [])

  // Apply edits and sort flagged to top (stable sort)
  const previewEntries = useMemo(() => {
    const withEdits = entries.map((entry) => {
      const key = String(entry[keyField])
      const edits = editedFields.get(key)
      if (edits) {
        return { ...entry, ...edits }
      }
      return entry
    })

    // Stable sort: flagged first, preserve original order within groups
    return [...withEdits].sort((a, b) => {
      const aFlagged = Boolean(a[flagField])
      const bFlagged = Boolean(b[flagField])
      if (aFlagged && !bFlagged) return -1
      if (!aFlagged && bFlagged) return 1
      return 0
    })
  }, [entries, keyField, flagField, editedFields])

  // entriesToExport: non-excluded entries with edits applied
  const entriesToExport = useMemo(() => {
    return previewEntries.filter(
      (entry) => !excludedKeys.has(String(entry[keyField]))
    )
  }, [previewEntries, excludedKeys, keyField])

  const flaggedCount = useMemo(() => {
    return previewEntries.filter((entry) => Boolean(entry[flagField])).length
  }, [previewEntries, flagField])

  const toggleExclude = useCallback((key: string) => {
    setExcludedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(String(key))) {
        next.delete(String(key))
      } else {
        next.add(String(key))
      }
      return next
    })
  }, [])

  const toggleExcludeAll = useCallback(() => {
    setExcludedKeys((prev) => {
      if (prev.size === 0) {
        // None excluded -> exclude all
        return new Set(entries.map((entry) => String(entry[keyField])))
      }
      // Some or all excluded -> clear exclusions
      return new Set()
    })
  }, [entries, keyField])

  const editField = useCallback((key: string, field: keyof T, value: unknown) => {
    setEditedFields((prev) => {
      const next = new Map(prev)
      const existing = next.get(String(key)) ?? {} as Partial<T>
      next.set(String(key), { ...existing, [field]: value } as Partial<T>)
      return next
    })
  }, [])

  const resetEdits = useCallback(() => {
    setEditedFields(new Map())
  }, [])

  const isAllSelected = excludedKeys.size === 0
  const isSomeSelected = excludedKeys.size > 0 && excludedKeys.size < previewEntries.length

  const isExcluded = useCallback(
    (key: string) => excludedKeys.has(String(key)),
    [excludedKeys]
  )

  return {
    previewEntries,
    excludedKeys,
    editedFields,
    entriesToExport,
    flaggedCount,
    updateEntries,
    toggleExclude,
    toggleExcludeAll,
    editField,
    resetEdits,
    isAllSelected,
    isSomeSelected,
    isExcluded,
  }
}
