import axios from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'

// The website reaches the API through its own address: /api/* is rewritten to the API on Render (render.yaml) and
// proxied to the local API by Vite in development. Being same-site lets the browser keep the refresh cookie.
export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? '/api', withCredentials: true })

// The access token lives only in this variable, never in localStorage, so there is no stored token to copy.
// The refresh token is an httpOnly cookie that page scripts cannot read; the browser sends it to /api/auth/*.
let accessToken: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

// Older versions kept both tokens in localStorage; remove them
try {
  localStorage.removeItem('skilltrack_token')
  localStorage.removeItem('skilltrack_refresh_token')
} catch {
  // storage unavailable (private mode): nothing to clean
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

export interface SessionData {
  access_token: string
  user: unknown
}

let onSessionExpired = () => {}
let refreshing: Promise<SessionData> | null = null

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler
}

function postRefresh() {
  return axios.post<SessionData>('/auth/refresh', null, { baseURL: api.defaults.baseURL, withCredentials: true })
}

async function callRefresh(): Promise<SessionData> {
  // Tabs share the refresh cookie and each refresh replaces it, so tabs take turns (Web Locks) instead of
  // presenting the same cookie at once
  const run = () => postRefresh().then((res) => res.data)
  try {
    return 'locks' in navigator ? await navigator.locks.request('skilltrack-refresh', run) : await run()
  } catch (err) {
    // 409: another tab refreshed with the same cookie a moment ago; its replacement is in the browser by now
    if (axios.isAxiosError(err) && err.response?.status === 409) {
      await new Promise((resolve) => setTimeout(resolve, 500))
      return run()
    }
    throw err
  }
}

/** Get a new access token with the refresh cookie. Also restores the session after a page reload. */
export function refreshSession(): Promise<SessionData> {
  // Requests that fail together share one refresh call
  refreshing ??= callRefresh()
    .then((data) => {
      accessToken = data.access_token
      return data
    })
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

// A 401 here means wrong details or no session, not an expired access token
const NO_REFRESH = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']

// Access tokens last 15 minutes. When a request is refused because one ran out, refresh and retry it once.
// When the session itself has ended (signed out elsewhere, idle, stolen token detected), sign out here too.
api.interceptors.response.use(undefined, async (err) => {
  const request = err.config as (InternalAxiosRequestConfig & { retried?: boolean }) | undefined
  if (err.response?.status !== 401 || !request || request.retried || NO_REFRESH.includes(request.url ?? '')) {
    throw err
  }
  request.retried = true
  try {
    await refreshSession()
  } catch (refreshErr) {
    if (axios.isAxiosError(refreshErr) && refreshErr.response?.status === 401) {
      accessToken = null
      onSessionExpired()
    }
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
