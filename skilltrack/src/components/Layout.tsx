import { useEffect, useRef, useState } from 'react'
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import type { Role } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { Logo } from './AuthLayout'

const NAV: Record<Role, { to: string; label: string }[]> = {
  student: [
    { to: '/student', label: 'Dashboard' },
    { to: '/student/domains', label: 'Domains' },
    { to: '/exam', label: 'Take Exam' },
  ],
  owner: [
    { to: '/owner', label: 'Track Overview' },
    { to: '/owner/syllabus', label: 'Syllabus' },
    { to: '/owner/questions', label: 'Question Paper' }
  ],
  admin: [
    { to: '/admin', label: 'Analytics' },
    { to: '/invigilator', label: 'Exam Keys' },
  ],
  invigilator: [{ to: '/invigilator', label: 'Exam Keys' }],
}

const ROLE_LABEL: Record<Role, string> = {
  student: 'Student', owner: 'Track Owner', admin: 'Admin', invigilator: 'Invigilator',
}

function MoonIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="h-4 w-4" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  )
}

function SunIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="h-4 w-4" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 7a5 5 0 100 10A5 5 0 0012 7z" />
    </svg>
  )
}

export default function Layout() {
  const { user, loading, logout } = useAuth()
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => { setOpen(false) }, [location.pathname])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  if (loading) return <div className="p-6 text-sm text-slate-500 dark:text-slate-400">Loading…</div>
  if (!user) return <Navigate to="/login" replace />

  function signOut() { logout(); navigate('/login', { replace: true }) }
  const initial = user.name.trim().charAt(0).toUpperCase()

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-800 dark:bg-slate-950 dark:text-slate-100">

      {/* ── Fixed hamburger button ── */}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close menu' : 'Open menu'}
        aria-expanded={open}
        aria-controls="side-menu"
        className="fixed left-3 top-3 z-50 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-950 text-white shadow transition hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 dark:bg-slate-700 dark:hover:bg-slate-600"
      >
        {open ? (
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        )}
      </button>

      {/* ── Backdrop ── */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm"
          aria-hidden="true"
          onClick={() => setOpen(false)}
        />
      )}

      {/* ── Slide-in side menu ── */}
      <div
        id="side-menu"
        ref={menuRef}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col overflow-hidden bg-slate-950 text-white shadow-2xl transition-transform duration-300 ease-in-out ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Aurora glows */}
        <div className="pointer-events-none absolute -left-10 -top-10 h-48 w-48 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 left-1/4 h-64 w-64 rounded-full bg-purple-600/20 blur-3xl" />

        <div className="relative z-10 flex h-full flex-col p-5">
          {/* Logo + close */}
          <div className="mb-8 flex items-center justify-between">
            <Logo />
            <button
              onClick={() => setOpen(false)}
              aria-label="Close menu"
              className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Nav links */}
          <nav className="flex-1 space-y-1" aria-label="Main navigation">
            {NAV[user.role].map((item, i) => (
              <NavLink
                key={`${item.to}-${i}`}
                to={item.to}
                end
                className={({ isActive }) =>
                  `block rounded-xl px-3 py-2.5 text-sm font-semibold transition-all ${
                    isActive
                      ? 'bg-indigo-500/20 text-indigo-200 shadow-sm ring-1 ring-inset ring-indigo-500/30'
                      : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* Dark mode toggle */}
          <button
            onClick={toggle}
            className="mb-3 flex w-full items-center gap-2.5 rounded-xl border border-white/10 px-3 py-2.5 text-sm font-semibold text-slate-300 transition hover:bg-white/10 hover:text-white"
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>

        </div>
      </div>

      {/* ── Top header ── */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-2.5 pl-14 dark:border-slate-800 dark:bg-slate-900">
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
          {ROLE_LABEL[user.role]}
        </span>
        <div className="flex items-center gap-3 text-sm">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-50 text-sm font-bold text-indigo-700 ring-1 ring-inset ring-indigo-600/20 dark:bg-indigo-900/40 dark:text-indigo-300 dark:ring-indigo-500/30">
              {initial}
            </span>
            <span className="font-bold text-slate-800 dark:text-slate-100">{user.name}</span>
          </div>
          <button
            onClick={signOut}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 hover:text-slate-900 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="flex-1 p-4 sm:p-6">
        <div className="mx-auto max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
