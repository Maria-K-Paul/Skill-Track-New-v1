import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { REFRESH_KEY, TOKEN_KEY, api, setSessionExpiredHandler } from '../api'

export type Role = 'student' | 'owner' | 'admin' | 'invigilator'

export interface User {
  id: number
  name: string
  email: string
  reg_no: string | null
  role: Role
  department: string | null
  semester: number | null
}

export const HOME: Record<Role, string> = {
  student: '/student',
  owner: '/owner',
  admin: '/admin',
  invigilator: '/invigilator',
}

export interface RegisterDetails {
  name: string
  email: string
  reg_no: string
  department: string
  password: string
}

interface AuthCtx {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (details: RegisterDetails) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthCtx | null>(null)

interface TokenResponse {
  access_token: string
  refresh_token: string
  user: User
}

function saveTokens(res: TokenResponse) {
  localStorage.setItem(TOKEN_KEY, res.access_token)
  localStorage.setItem(REFRESH_KEY, res.refresh_token)
}

function clearTokens() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => !!localStorage.getItem(TOKEN_KEY))

  useEffect(() => {
    // The refresh token ran out (1 day after sign-in): drop the session so the pages redirect to /login
    setSessionExpiredHandler(() => {
      clearTokens()
      setUser(null)
    })
    if (!localStorage.getItem(TOKEN_KEY)) return
    api.get<User>('/auth/me')
      .then((res) => setUser(res.data))
      .catch(clearTokens)
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const res = await api.post<TokenResponse>('/auth/login', { email, password })
    saveTokens(res.data)
    setUser(res.data.user)
    return res.data.user
  }

  async function register(details: RegisterDetails) {
    const res = await api.post<TokenResponse>('/auth/register', details)
    saveTokens(res.data)
    setUser(res.data.user)
    return res.data.user
  }

  function logout() {
    clearTokens()
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
