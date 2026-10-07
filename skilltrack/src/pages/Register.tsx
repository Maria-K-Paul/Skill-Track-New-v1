import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { errorMessage } from '../api'
import AuthLayout, { Icon, Logo } from '../components/AuthLayout'
import { authButton, authField } from '../components/authStyles'
import { HOME, useAuth } from '../context/AuthContext'

const DEPARTMENTS = ['CSE', 'IT', 'ECE', 'EEE', 'MECH', 'AIML', 'AIDS', 'CYBERSECURITY', 'CHEMICAL', 'CIVIL', 'BIOTECHNOLOGY']

const ICONS = {
  user: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM4 21a8 8 0 0116 0',
  mail: 'M3 8l9 6 9-6M5 5h14a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2z',
  id: 'M4 6h16a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V7a1 1 0 011-1zM7 11h4M7 14h2M15 11h2',
  building: 'M4 21V5a1 1 0 011-1h8a1 1 0 011 1v16M14 9h5a1 1 0 011 1v11M3 21h18M8 8h2M8 12h2M8 16h2',
  book: 'M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2V5zM4 19a2 2 0 002 2h13',
  lock: 'M16 11V7a4 4 0 00-8 0v4M6 11h12a1 1 0 011 1v8a1 1 0 01-1 1H6a1 1 0 01-1-1v-8a1 1 0 011-1z',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zM9 12l2 2 4-4',
}

function Field({ label, icon, children }: { label: string; icon: keyof typeof ICONS; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-slate-800">{label}</span>
      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-0 z-10 flex items-center pl-4 text-slate-400">
          <Icon className="h-4 w-4"><path strokeLinecap="round" strokeLinejoin="round" d={ICONS[icon]} /></Icon>
        </span>
        {children}
      </div>
    </label>
  )
}

export default function Register() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '', email: '', reg_no: '', department: 'CSE', password: '', confirm: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={HOME[user.role]} replace />

  const set = (field: string, value: string | number) => setForm({ ...form, [field]: value })

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (form.password !== form.confirm) return setError('Passwords do not match')
    setBusy(true)
    setError('')
    try {
      const { confirm: _confirm, ...payload } = form
      const u = await register(payload)
      navigate(HOME[u.role], { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Could not create your account'))
    } finally {
      setBusy(false)
    }
  }

  const passwordType = showPassword ? 'text' : 'password'

  return (
    <AuthLayout>
      <form onSubmit={onSubmit} className="w-full max-w-lg space-y-4 rounded-3xl border border-slate-100 bg-white p-8 shadow-2xl shadow-indigo-100 sm:p-10">
        <Logo dark />
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Create your account <span className="inline-block origin-[70%_70%] transition hover:rotate-12">🎓</span></h1>
          <p className="mt-1 text-sm text-slate-500">Register as a student to start your skill track.</p>
        </div>

        <Field label="Full name" icon="user">
          <input required autoComplete="name" placeholder="Your full name" value={form.name} onChange={(e) => set('name', e.target.value)} className={authField} />
        </Field>
        <Field label="Email" icon="mail">
          <input required type="email" autoComplete="email" placeholder="you@example.com" value={form.email} onChange={(e) => set('email', e.target.value)} className={authField} />
        </Field>
        <Field label="Register number" icon="id">
          <input required placeholder="Your register number" value={form.reg_no} onChange={(e) => set('reg_no', e.target.value)} className={authField} />
        </Field>

        <Field label="Department" icon="building">
          <select value={form.department} onChange={(e) => set('department', e.target.value)} className={authField}>
            {DEPARTMENTS.map((d) => <option key={d}>{d}</option>)}
          </select>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Password" icon="lock">
            <input
              required type={passwordType} minLength={8} autoComplete="new-password" placeholder="At least 8 characters"
              value={form.password} onChange={(e) => set('password', e.target.value)} className={`${authField} pr-16`}
            />
            <button
              type="button" onClick={() => setShowPassword((s) => !s)} aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="absolute inset-y-0 right-0 px-4 text-xs font-semibold text-indigo-600 hover:text-indigo-500"
            >
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </Field>
          <Field label="Confirm password" icon="shield">
            <input
              required type={passwordType} autoComplete="new-password" placeholder="Repeat password"
              value={form.confirm} onChange={(e) => set('confirm', e.target.value)} className={authField}
            />
          </Field>
        </div>

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
              Creating account…
            </>
          ) : (
            <>
              Create account
              <Icon className="h-4 w-4 transition group-hover:translate-x-1"><path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6l6 6-6 6" /></Icon>
            </>
          )}
        </button>

        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span className="h-px flex-1 bg-slate-200" /> OR <span className="h-px flex-1 bg-slate-200" />
        </div>

        <p className="text-center text-sm text-slate-600">
          Already registered? <Link to="/login" className="font-semibold text-indigo-600 hover:underline">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  )
}
