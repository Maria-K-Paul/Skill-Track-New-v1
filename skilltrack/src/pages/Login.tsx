import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { errorMessage } from '../api'
import AuthLayout, { Icon, Logo } from '../components/AuthLayout'
import { authButton, authField } from '../components/authStyles'
import { HOME, useAuth } from '../context/AuthContext'

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={HOME[user.role]} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const u = await login(email, password)
      navigate(HOME[u.role], { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Login failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout>
      <form onSubmit={onSubmit} className="w-full max-w-md space-y-5 rounded-3xl border border-slate-100 bg-white p-8 shadow-2xl shadow-indigo-100 sm:p-10 dark:border-slate-800 dark:bg-slate-900 dark:shadow-slate-950">
        <Logo dark />
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Welcome back <span className="inline-block origin-[70%_70%] transition hover:rotate-12">👋</span></h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Sign in to pick up where you left off.</p>
        </div>

        <label className="block">
          <span className="mb-1.5 block text-sm font-semibold text-slate-800 dark:text-slate-200">Email</span>
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-slate-400">
              <Icon className="h-4 w-4"><path strokeLinecap="round" strokeLinejoin="round" d="M3 8l9 6 9-6M5 5h14a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2z" /></Icon>
            </span>
            <input type="email" required autoComplete="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} className={authField} />
          </div>
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-semibold text-slate-800 dark:text-slate-200">Password</span>
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-slate-400">
              <Icon className="h-4 w-4"><path strokeLinecap="round" strokeLinejoin="round" d="M16 11V7a4 4 0 00-8 0v4M6 11h12a1 1 0 011 1v8a1 1 0 01-1 1H6a1 1 0 01-1-1v-8a1 1 0 011-1z" /></Icon>
            </span>
            <input
              type={showPassword ? 'text' : 'password'} required autoComplete="current-password" placeholder="Enter your password"
              value={password} onChange={(e) => setPassword(e.target.value)} className={`${authField} pr-16`}
            />
            <button
              type="button" onClick={() => setShowPassword((s) => !s)} aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="absolute inset-y-0 right-0 px-4 text-xs font-semibold text-indigo-600 hover:text-indigo-500"
            >
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>
        </label>

        {error && (
          <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <Icon className="mt-0.5 h-4 w-4 shrink-0"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" /></Icon>
            <span>{error}</span>
          </div>
        )}

        <button disabled={busy} className={authButton}>
          {busy ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              Signing in…
            </>
          ) : (
            <>
              Sign in
              <Icon className="h-4 w-4 transition group-hover:translate-x-1"><path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6l6 6-6 6" /></Icon>
            </>
          )}
        </button>

        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span className="h-px flex-1 bg-slate-200" /> OR <span className="h-px flex-1 bg-slate-200" />
        </div>

        <p className="text-center text-sm text-slate-600 dark:text-slate-400">
          New student? <Link to="/register" className="font-semibold text-indigo-600 hover:underline dark:text-indigo-400">Create an account</Link>
        </p>
      </form>
    </AuthLayout>
  )
}
