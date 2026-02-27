import { useEffect, useState, useRef, useCallback } from 'react'

interface ProgressData {
  processed: number
  total: number
  created: number
  updated: number
  failed: number
}

interface CompletionData {
  status: string
  created: number
  updated: number
  failed: number
  failed_contacts: Array<{
    mineral_contact_system_id: string
    error_category: 'validation' | 'api_error' | 'rate_limit' | 'network' | 'unknown'
    error_message: string
    contact_data: Record<string, string>
  }>
  updated_contacts: Array<{
    mineral_contact_system_id: string
    status: string
    ghl_contact_id?: string
  }>
  dailyLimitHit?: boolean
}

interface UseSSEProgressReturn {
  progress: ProgressData | null
  completionData: CompletionData | null
  isComplete: boolean
  error: string | null
  disconnect: () => void
}

export function useSSEProgress(jobId: string | null): UseSSEProgressReturn {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [completionData, setCompletionData] = useState<CompletionData | null>(null)
  const [isComplete, setIsComplete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectAttemptRef = useRef(0)
  const reconnectTimeoutRef = useRef<number | null>(null)

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!jobId) return

    // Reset state for new job
    setProgress(null)
    setCompletionData(null)
    setIsComplete(false)
    setError(null)
    reconnectAttemptRef.current = 0

    const connectEventSource = () => {
      const url = `/api/ghl/send/${jobId}/progress`
      const eventSource = new EventSource(url)
      eventSourceRef.current = eventSource

      eventSource.addEventListener('progress', (e: MessageEvent) => {
        const data = JSON.parse(e.data)

        // Reset reconnect counter on successful message
        reconnectAttemptRef.current = 0

        setProgress({
          processed: data.processed,
          total: data.total,
          created: data.created,
          updated: data.updated,
          failed: data.failed,
        })
      })

      eventSource.addEventListener('complete', (e: MessageEvent) => {
        const data = JSON.parse(e.data)

        // Reset reconnect counter on successful message
        reconnectAttemptRef.current = 0

        setProgress({
          processed: data.total || data.processed,
          total: data.total,
          created: data.created,
          updated: data.updated,
          failed: data.failed,
        })
        setCompletionData({
          status: data.status,
          created: data.created,
          updated: data.updated,
          failed: data.failed,
          failed_contacts: data.failed_contacts || [],
          updated_contacts: data.updated_contacts || [],
          dailyLimitHit: data.status === 'daily_limit_hit',
        })
        setIsComplete(true)
        eventSource.close()
      })

      eventSource.addEventListener('error', (e: Event) => {
        // Check if it's an SSE error event with data
        const msgEvent = e as MessageEvent
        if (msgEvent.data) {
          try {
            const errorData = JSON.parse(msgEvent.data)
            setError(errorData.error || 'Unknown error')
          } catch {
            setError('Connection error')
          }
        }
        eventSource.close()
      })

      // Handle EventSource connection errors (network issues)
      eventSource.onerror = () => {
        if (eventSource.readyState === EventSource.CLOSED) {
          // Attempt reconnection with exponential backoff
          if (reconnectAttemptRef.current < 5) {
            const backoffMs = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 30000)
            reconnectAttemptRef.current++

            reconnectTimeoutRef.current = window.setTimeout(() => {
              connectEventSource()
            }, backoffMs)
          } else {
            setError('Connection lost. Refresh to check progress.')
          }
        }
      }
    }

    connectEventSource()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }
  }, [jobId])

  return { progress, completionData, isComplete, error, disconnect }
}
