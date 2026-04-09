import { createClient } from '@supabase/supabase-js'
import axios from 'axios'

// Supabase client
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://your-project.supabase.co'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Axios API client for backend
const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Auto-attach auth token
api.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

// ── Global error event bus ──
const errorListeners = new Set()
export function onApiError(callback) {
  errorListeners.add(callback)
  return () => errorListeners.delete(callback)
}
function emitApiError(error) {
  const message = error.response?.data?.detail
    || error.response?.data?.message
    || error.message
    || 'Неизвестная ошибка'
  const status = error.response?.status || 0
  errorListeners.forEach(fn => fn({ message, status, error }))
}

// Handle 401 — refresh Supabase token (once per request, avoid infinite loop)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config
    // Only retry once, and skip if the 401 is from Instagram session (not Supabase auth)
    if (error.response?.status === 401 && !config._retried) {
      config._retried = true
      const { data, error: refreshError } = await supabase.auth.refreshSession()
      if (!refreshError && data.session) {
        config.headers.Authorization = `Bearer ${data.session.access_token}`
        return api.request(config)
      }
    }
    // Emit error for toast system (skip 401 retries)
    if (!config._silentError) {
      emitApiError(error)
    }
    return Promise.reject(error)
  }
)

export default api
