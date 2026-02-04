const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

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

  async put<T>(endpoint: string, body?: unknown, options?: Omit<ApiRequestOptions, 'method' | 'body'>) {
    return this.request<T>(endpoint, { ...options, method: 'PUT', body })
  }

  async patch<T>(endpoint: string, body?: unknown, options?: Omit<ApiRequestOptions, 'method' | 'body'>) {
    return this.request<T>(endpoint, { ...options, method: 'PATCH', body })
  }

  async delete<T>(endpoint: string, options?: Omit<ApiRequestOptions, 'method' | 'body'>) {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' })
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

// Export specific API functions for each tool
export const extractApi = {
  uploadDocument: (file: File) => api.uploadFile('/extract/upload', file),
  getExtractionStatus: (jobId: string) => api.get(`/extract/status/${jobId}`),
  getExtractionResult: (jobId: string) => api.get(`/extract/result/${jobId}`),
  listExtractions: () => api.get('/extract/list'),
}

export const titleApi = {
  uploadDocument: (file: File) => api.uploadFile('/title/upload', file),
  searchTitle: (query: string) => api.get(`/title/search?q=${encodeURIComponent(query)}`),
  getTitleDetails: (id: string) => api.get(`/title/${id}`),
}

export const prorationApi = {
  calculate: (data: unknown) => api.post('/proration/calculate', data),
  getHistory: () => api.get('/proration/history'),
  getCalculation: (id: string) => api.get(`/proration/${id}`),
}

export const revenueApi = {
  uploadStatement: (file: File) => api.uploadFile('/revenue/upload', file),
  getAnalysis: (jobId: string) => api.get(`/revenue/analysis/${jobId}`),
  listStatements: () => api.get('/revenue/statements'),
}

export default api
