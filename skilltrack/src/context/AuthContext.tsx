import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { TOKEN_KEY, api } from '../api'

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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => !!localStorage.getItem(TOKEN_KEY))

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) return
    api.get<User>('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const res = await api.post<{ access_token: string; user: User }>('/auth/login', { email, password })
    localStorage.setItem(TOKEN_KEY, res.data.access_token)
    setUser(res.data.user)
    return res.data.user
  }

  async function register(details: RegisterDetails) {
    const res = await api.post<{ access_token: string; user: User }>('/auth/register', details)
    localStorage.setItem(TOKEN_KEY, res.data.access_token)
    setUser(res.data.user)
    return res.data.user
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
