import { useEffect, useState } from 'react'
import { api } from '../utils/api'

export interface FeatureFlags {
  cleanUpEnabled: boolean
  validateEnabled: boolean
  enrichEnabled: boolean
  loaded: boolean
}

interface FeatureStatusResponse {
  cleanup_enabled: boolean
  validate_enabled: boolean
  enrich_enabled: boolean
}

const DEFAULT_FLAGS: FeatureFlags = {
  cleanUpEnabled: false,
  validateEnabled: false,
  enrichEnabled: false,
  loaded: false,
}

export function useFeatureFlags(): FeatureFlags {
  const [flags, setFlags] = useState<FeatureFlags>(DEFAULT_FLAGS)

  useEffect(() => {
    let cancelled = false

    async function fetchFlags() {
      const response = await api.get<FeatureStatusResponse>('/features/status')
      if (cancelled) return

      if (response.data) {
        setFlags({
          cleanUpEnabled: response.data.cleanup_enabled,
          validateEnabled: response.data.validate_enabled,
          enrichEnabled: response.data.enrich_enabled,
          loaded: true,
        })
      } else {
        // On error, leave defaults (buttons stay hidden -- safe failure mode)
        setFlags((prev) => ({ ...prev, loaded: true }))
      }
    }

    fetchFlags()
    return () => {
      cancelled = true
    }
  }, [])

  return flags
}
