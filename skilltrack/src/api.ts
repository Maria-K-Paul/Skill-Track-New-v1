import axios from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'

export const TOKEN_KEY = 'skilltrack_token'
export const REFRESH_KEY = 'skilltrack_refresh_token'

// The live site only allows calls to its own address (Content-Security-Policy connect-src 'self'), and Render
// forwards /api/* to the API, so production builds always go through /api
export const api = axios.create({
  baseURL: import.meta.env.PROD ? '/api' : (import.meta.env.VITE_API_URL ?? 'http://localhost:8000'),
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Access tokens last 15 minutes. When a request is refused because one ran out, swap the refresh token
// for a new access token and retry the request once. When the refresh token has run out too, sign out.
let onSessionExpired = () => {}
let refreshing: Promise<void> | null = null

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler
}

function refreshAccessToken(): Promise<void> {
  // Requests that fail together share one refresh call
  refreshing ??= axios
    .post<{ access_token: string }>('/auth/refresh', { refresh_token: localStorage.getItem(REFRESH_KEY) }, { baseURL: api.defaults.baseURL })
    .then((res) => localStorage.setItem(TOKEN_KEY, res.data.access_token))
    .finally(() => { refreshing = null })
  return refreshing
}

const NO_REFRESH = ['/auth/login', '/auth/register']  // a 401 here means wrong details, not an expired session

api.interceptors.response.use(undefined, async (err) => {
  const request = err.config as (InternalAxiosRequestConfig & { retried?: boolean }) | undefined
  if (
    err.response?.status !== 401 || !request || request.retried
    || NO_REFRESH.includes(request.url ?? '') || !localStorage.getItem(REFRESH_KEY)
  ) {
    throw err
  }
  request.retried = true
  try {
    await refreshAccessToken()
  } catch (refreshErr) {
    // Only a refused refresh ends the session; a network error leaves the user signed in
    if (axios.isAxiosError(refreshErr) && refreshErr.response?.status === 401) onSessionExpired()
    throw err
  }
  return api(request)
})

export function errorMessage(err: unknown, fallback = 'Something went wrong') {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d: { loc?: unknown[]; msg?: string }) => `${String(d.loc?.at(-1) ?? 'Input')}: ${d.msg ?? 'invalid'}`).join('; ')
    }
    if (!err.response) return `Network Error: ${err.message}`
  }
  return fallback
}
