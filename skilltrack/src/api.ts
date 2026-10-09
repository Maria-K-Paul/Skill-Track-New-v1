import axios from 'axios'

export const TOKEN_KEY = 'skilltrack_token'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export function errorMessage(err: unknown, fallback = 'Something went wrong') {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d: { loc?: unknown[]; msg?: string }) => `${String(d.loc?.at(-1) ?? 'Input')}: ${d.msg ?? 'invalid'}`).join('; ')
    }
    if (!err.response) return 'Cannot reach the server. Is the API running?'
  }
  return fallback
}
