import { useEffect, useState } from 'react'
import { api, errorMessage } from './api'

export interface FetchState<T> {
  data: T | null
  error: string
  loading: boolean
  retry: () => void
}

/** GET `path` and track loading/error state. Pass null to skip the request. */
export function useFetch<T>(path: string | null): FetchState<T> {
  const [result, setResult] = useState<{ key: string | null; data: T | null; error: string }>({
    key: null, data: null, error: '',
  })
  const [attempt, setAttempt] = useState(0)
  const key = path ? `${path}#${attempt}` : null

  useEffect(() => {
    if (!path || !key) return
    let cancelled = false
    api.get<T>(path)
      .then((res) => { if (!cancelled) setResult({ key, data: res.data, error: '' }) })
      .catch((err) => { if (!cancelled) setResult({ key, data: null, error: errorMessage(err) }) })
    return () => { cancelled = true }
  }, [path, key])

  const current = key !== null && result.key === key
  return {
    data: current ? result.data : null,
    error: current ? result.error : '',
    loading: key !== null && !current,
    retry: () => setAttempt((n) => n + 1),
  }
}
