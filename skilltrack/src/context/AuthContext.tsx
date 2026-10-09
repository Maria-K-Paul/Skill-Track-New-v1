import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, refreshSession, setAccessToken, setSessionExpiredHandler } from '../api'

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
  logout: () => Promise<void>
  logoutEverywhere: () => Promise<void>
}

const AuthContext = createContext<AuthCtx | null>(null)

// The refresh token is never here: the API sets it as an httpOnly cookie
interface TokenResponse {
  access_token: string
  user: User
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // The session ended (signed out elsewhere, idle, 1 day passed, or a stolen token was detected)
    setSessionExpiredHandler(() => {
      setAccessToken(null)
      setUser(null)
    })
    // The access token is kept only in memory, so after a reload get a new one with the refresh cookie
    refreshSession()
      .then((data) => setUser((data as TokenResponse).user))
      .catch(() => setAccessToken(null))
      .finally(() => setLoading(false))
  }, [])

  function signedIn(data: TokenResponse) {
    setAccessToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  async function login(email: string, password: string) {
    return signedIn((await api.post<TokenResponse>('/auth/login', { email, password })).data)
  }

  async function register(details: RegisterDetails) {
    return signedIn((await api.post<TokenResponse>('/auth/register', details)).data)
  }

  // Ends the session on the server too, so the refresh cookie and any copy of the tokens stop working
  async function endSession(path: string) {
    try {
      await api.post(path)
    } catch {
      // already ended or offline: sign out locally anyway
    } finally {
      setAccessToken(null)
      setUser(null)
    }
  }

  const logout = () => endSession('/auth/logout')
  const logoutEverywhere = () => endSession('/auth/logout-all')

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, logoutEverywhere }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
