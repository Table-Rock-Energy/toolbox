const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  headers?: Record<string, string>
  body?: unknown
  timeout?: number
}

interface ApiResponse<T> {
  data: T | null
  error: string | null
  status: number
}

class ApiClient {
  private baseUrl: string
  private defaultHeaders: Record<string, string>

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    }
  }

  setAuthToken(token: string) {
    this.defaultHeaders['Authorization'] = `Bearer ${token}`
  }

  clearAuthToken() {
    delete this.defaultHeaders['Authorization']
  }

  private async request<T>(
    endpoint: string,
    options: ApiRequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const {
      method = 'GET',
      headers = {},
      body,
      timeout = 30000,
    } = options

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method,
        headers: {
          ...this.defaultHeaders,
          ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      const contentType = response.headers.get('content-type')
      let data: T | null = null

      if (contentType?.includes('application/json')) {
        data = await response.json()
      }

      if (!response.ok) {
        return {
          data: null,
          error: (data as { detail?: string })?.detail || `HTTP error ${response.status}`,
          status: response.status,
        }
      }

      return {
        data,
        error: null,
        status: response.status,
      }
    } catch (error) {
      clearTimeout(timeoutId)

      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          return {
            data: null,
            error: 'Request timed out',
            status: 408,
          }
        }
        return {
          data: null,
          error: error.message,
          status: 0,
        }
      }

      return {
        data: null,
        error: 'An unexpected error occurred',
        status: 0,
      }
    }
  }

  async get<T>(endpoint: string, options?: Omit<ApiRequestOptions, 'method' | 'body'>) {
    return this.request<T>(endpoint, { ...options, method: 'GET' })
  }

  async post<T>(endpoint: string, body?: unknown, options?: Omit<ApiRequestOptions, 'method' | 'body'>) {
    return this.request<T>(endpoint, { ...options, method: 'POST', body })
  }

  async uploadFile<T>(
    endpoint: string,
    file: File,
    additionalData?: Record<string, string>
  ): Promise<ApiResponse<T>> {
    const formData = new FormData()
    formData.append('file', file)

    if (additionalData) {
      Object.entries(additionalData).forEach(([key, value]) => {
        formData.append(key, value)
      })
    }

    try {
      const headers = { ...this.defaultHeaders }
      delete headers['Content-Type'] // Let browser set multipart boundary

      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'POST',
        headers,
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        return {
          data: null,
          error: data?.detail || `HTTP error ${response.status}`,
          status: response.status,
        }
      }

      return {
        data,
        error: null,
        status: response.status,
      }
    } catch (error) {
      return {
        data: null,
        error: error instanceof Error ? error.message : 'Upload failed',
        status: 0,
      }
    }
  }
}

// Create and export a singleton instance
export const api = new ApiClient(API_BASE_URL)

// AI validation types
export interface AiSuggestion {
  entry_index: number
  field: string
  current_value: string
  suggested_value: string
  reason: string
  confidence: 'high' | 'medium' | 'low'
}

export interface AiValidationResult {
  success: boolean
  suggestions: AiSuggestion[]
  summary: string
  entries_reviewed: number
  issues_found: number
  error_message?: string | null
}

export interface AiStatusResponse {
  enabled: boolean
  model: string
  requests_remaining_minute: number
  requests_remaining_day: number
  monthly_budget: number
  monthly_spend: number
  monthly_budget_remaining: number
}

export const aiApi = {
  getStatus: () => api.get<AiStatusResponse>('/ai/status'),
  validate: (tool: string, entries: unknown[]) =>
    api.post<AiValidationResult>('/ai/validate', { tool, entries }, { timeout: 120000 }),
}

export default api
