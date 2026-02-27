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

  async put<T>(endpoint: string, body?: unknown, options?: Omit<ApiRequestOptions, 'method' | 'body'>) {
    return this.request<T>(endpoint, { ...options, method: 'PUT', body })
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

// Enrichment types
export interface EnrichmentPhoneNumber {
  number: string
  type?: string | null
  carrier?: string | null
}

export interface EnrichmentSocialProfile {
  platform: string
  url: string
  username?: string | null
}

export interface EnrichmentPublicRecords {
  is_deceased: boolean
  deceased_date?: string | null
  has_bankruptcy: boolean
  bankruptcy_details: string[]
  has_liens: boolean
  lien_details: string[]
}

export interface EnrichedPerson {
  original_name: string
  original_address?: string | null
  phones: EnrichmentPhoneNumber[]
  emails: string[]
  social_profiles: EnrichmentSocialProfile[]
  public_records: EnrichmentPublicRecords
  enrichment_sources: string[]
  enriched_at?: string | null
  match_confidence?: string | null
}

export interface EnrichmentStatusResponse {
  enabled: boolean
  pdl_configured: boolean
  searchbug_configured: boolean
}

export interface EnrichmentConfigResponse {
  enabled: boolean
  pdl_api_key: string | null
  searchbug_api_key: string | null
}

export interface EnrichmentResponse {
  success: boolean
  results: EnrichedPerson[]
  total_requested: number
  total_enriched: number
  error_message?: string | null
}

export const enrichmentApi = {
  getStatus: () => api.get<EnrichmentStatusResponse>('/enrichment/status'),
  getConfig: () => api.get<EnrichmentConfigResponse>('/enrichment/config'),
  updateConfig: (config: { pdl_api_key?: string; searchbug_api_key?: string; enabled?: boolean }) =>
    api.post<{ success: boolean; message: string; status: EnrichmentStatusResponse }>('/enrichment/config', config),
  lookup: (persons: { name: string; address?: string; city?: string; state?: string; zip_code?: string }[]) =>
    api.post<EnrichmentResponse>('/enrichment/lookup', { persons }, { timeout: 60000 }),
}

// GHL Connection types (matches backend Pydantic models)
export interface GhlConnectionResponse {
  id: string
  name: string
  token_last4: string
  location_id: string
  notes: string
  validation_status: string
  created_at: string
  updated_at: string
}

export interface GhlUserResponse {
  id: string
  name: string
  email: string
  role?: string
}

export interface GhlValidationResult {
  valid: boolean
  error?: string
  location_name?: string
  users: GhlUserResponse[]
}

export interface BulkContactData {
  mineral_contact_system_id: string
  first_name?: string
  last_name?: string
  email?: string
  phone?: string
  address1?: string
  city?: string
  state?: string
  postal_code?: string
}

export interface ContactResult {
  mineral_contact_system_id: string
  status: 'created' | 'updated' | 'failed' | 'skipped'
  ghl_contact_id?: string
  error?: string
}

export interface BulkSendValidationResponse {
  valid_count: number
  invalid_count: number
  invalid_contacts: ContactResult[]
}

export interface BulkSendResponse {
  job_id: string
  total_count: number
  created_count: number
  updated_count: number
  failed_count: number
  skipped_count: number
  results: ContactResult[]
}

export interface BulkSendRequest {
  connection_id: string
  contacts: BulkContactData[]
  campaign_tag: string
  manual_sms: boolean
  assigned_to_list?: string[]
  smart_list_name?: string
}

// New async job types (matching backend Plan 01)
export interface ProgressEvent {
  job_id: string
  processed: number
  total: number
  created: number
  updated: number
  failed: number
  status: 'processing' | 'completed' | 'failed' | 'cancelled'
}

export interface FailedContactDetail {
  mineral_contact_system_id: string
  error_category: 'validation' | 'api_error' | 'rate_limit' | 'network' | 'unknown'
  error_message: string
  contact_data: Record<string, string>
}

export interface JobStatusResponse {
  job_id: string
  status: 'processing' | 'completed' | 'failed' | 'cancelled'
  total_count: number
  processed_count: number
  created_count: number
  updated_count: number
  failed_count: number
  skipped_count: number
  failed_contacts: FailedContactDetail[]
  updated_contacts: ContactResult[]
  created_at: string | null
  completed_at: string | null
}

export interface BulkSendStartResponse {
  job_id: string
  status: string
  total_count: number
}

export interface DailyRateLimitInfo {
  daily_limit: number
  requests_today: number
  remaining: number
  resets_at: string
  warning_level: 'normal' | 'warning' | 'critical'
}

export interface QuickCheckResponse {
  valid: boolean
  error: string | null
}

export const ghlApi = {
  listConnections: () =>
    api.get<{ connections: GhlConnectionResponse[] }>('/ghl/connections'),

  createConnection: (data: { name: string; token: string; location_id: string }) =>
    api.post<{ connection: GhlConnectionResponse; validation: GhlValidationResult }>(
      '/ghl/connections', data
    ),

  updateConnection: (id: string, data: { name?: string; token?: string; location_id?: string }) =>
    api.put<{ connection: GhlConnectionResponse; validation?: GhlValidationResult }>(
      `/ghl/connections/${id}`, data
    ),

  deleteConnection: (id: string) =>
    api.delete<{ deleted: boolean }>(`/ghl/connections/${id}`),

  validateConnection: (id: string) =>
    api.post<GhlValidationResult>(`/ghl/connections/${id}/validate`),

  getUsers: (connectionId: string) =>
    api.get<{ users: GhlUserResponse[] }>(`/ghl/connections/${connectionId}/users`),

  validateBatch: (data: BulkSendRequest) =>
    api.post<BulkSendValidationResponse>('/ghl/contacts/validate-batch', data),

  bulkSend: (data: BulkSendRequest) =>
    api.post<BulkSendResponse>('/ghl/contacts/bulk-send', data),

  // New async job methods
  startBulkSend: (data: BulkSendRequest) =>
    api.post<BulkSendStartResponse>('/ghl/contacts/bulk-send', data, { timeout: 60000 }),

  getJobStatus: (jobId: string) =>
    api.get<JobStatusResponse>(`/ghl/send/${jobId}/status`),

  cancelJob: (jobId: string) =>
    api.post<{ cancelled: boolean }>(`/ghl/send/${jobId}/cancel`),

  getDailyLimit: () =>
    api.get<DailyRateLimitInfo>('/ghl/daily-limit'),

  quickCheckConnection: (id: string) =>
    api.post<QuickCheckResponse>(`/ghl/connections/${id}/quick-check`),
}

export default api
