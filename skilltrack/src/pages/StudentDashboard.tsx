import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { api, errorMessage } from '../api'
import Card from '../components/Card'
import { Icon, StudentIllustration } from '../components/AuthLayout'
import { semesters } from '../data/studentData'
import { useFetch } from '../useFetch'
import type { FetchState } from '../useFetch'

type LevelStatus = 'cleared' | 'active' | 'locked' | 'removed'

interface ActiveBooking {
  booking_id: number
  slot_id: number
  starts_at: string
  venue: string
  level_name: string
  domain_name: string
  booked_at: string
  change_cancel_deadline: string
  window_expired: boolean
  seconds_remaining_in_window: number
  status: string
}

interface Dashboard {
  user: { name: string; department: string | null; semester: number | null }
  domains: { id: number; name: string }[]
  points_to_unlock: number
  total_points: number
  points_unlocked: boolean
  max_attempts: number | null
  enrollment: {
    domain_id: number; domain: string; status: string; is_common: boolean; points: number;
    current_level: number; level_count: number; passed_levels: number; progress_pct: number;
    enrolled_at: string | null
  } | null
  levels: { id: number; number: number; name: string; status: LevelStatus; attempts_used: number; score: number | null; first_attempt: boolean }[]
  slots: { id: number; starts_at: string; venue: string; seats_left: number }[]
  booked_slot_id: number | null
  active_booking: ActiveBooking | null
  skill_gap: { level_name: string; weak: { topic: string; score: number }[] } | null
  certificates: { code: string; title: string; issued_at: string; first_attempt: boolean }[]
  completed_domain: { domain_id: number; domain_name: string; completed_at: string | null; certificate_code: string | null } | null
}

interface BadgeItem {
  id: number
  domain_id: number
  domain_name: string
  level_id: number
  level_number: number
  level_name: string
  awarded_at: string
}

interface DomainProgress {
  domain_id: number
  domain_name: string
  total_levels: number
  passed_levels: number
  completed: boolean
  certificate: { code: string; issued_at: string; status: string } | null
}

interface Credentials {
  badges: BadgeItem[]
  domains: DomainProgress[]
}

interface AiRec { domain: string; match: number; reason: string }
interface AiPrep {
  level: string
  focus_topics: { topic: string; why: string }[]
  study_plan: string[]
  requirements: string[]
}

interface SkillGapReport {
  id: number
  assessment_id: number | null
  overall_summary: string
  readiness: string
  strengths: string[]
  gaps: Array<{
    topic: string
    score: number
    classification: string
    severity: string
    confidence: string
    trend: string
    reason: string
    priority: number
  }>
  next_level_priorities: Array<{
    topic: string
    reason: string
    prerequisites: string[]
    actions: string[]
  }>
  recommended_plan: string[]
  confidence: string
  created_at: string
}

const PATHS = {
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z',
  star: 'M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z',
  flag: 'M5 21V4m0 0h11l-2 4 2 4H5',
  book: 'M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2V5zM4 19a2 2 0 002 2h13',
  calendar: 'M7 3v4M17 3v4M4 9h16M5 5h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1z',
  chart: 'M4 20V10M10 20V4M16 20v-8M22 20H2',
  ribbon: 'M12 14a6 6 0 100-12 6 6 0 000 12zM8.5 13L7 22l5-3 5 3-1.5-9',
  cap: 'M12 3L2 8l10 5 10-5-10-5zM6 10.5V15c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5',
  check: 'M5 13l4 4L19 7',
  lock: 'M16 11V7a4 4 0 00-8 0v4M6 11h12a1 1 0 011 1v8a1 1 0 01-1 1H6a1 1 0 01-1-1v-8a1 1 0 011-1z',
  chat: 'M4 5h16v11H9l-5 4V5z',
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  arrow: 'M5 12h14m-6-6l6 6-6 6',
  info: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  clock:    'M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  eye:      'M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z',
  x:        'M6 18L18 6M6 6l12 12',
  download: 'M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 4v11',
}

const ico = (name: keyof typeof PATHS, className = 'h-4 w-4') => (
  <Icon className={className}><path strokeLinecap="round" strokeLinejoin="round" d={PATHS[name]} /></Icon>
)

const primaryBtn =
  'group inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-500 hover:shadow-indigo-500/40 active:translate-y-0 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none'

// ── Focus-trap hook ────────────────────────────────────────────────────────────

function useFocusTrap(ref: { current: HTMLElement | null }, active: boolean) {
  useEffect(() => {
    if (!active || !ref.current) return
    const el = ref.current
    const sel = 'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'
    const getFocusable = () => Array.from(el.querySelectorAll<HTMLElement>(sel)).filter(n => !(n as HTMLButtonElement).disabled)
    const timer = setTimeout(() => getFocusable()[0]?.focus(), 0)
    function trap(e: KeyboardEvent) {
      if (e.key !== 'Tab') return
      const nodes = getFocusable()
      if (!nodes.length) return
      const first = nodes[0], last = nodes[nodes.length - 1]
      if (e.shiftKey) { if (document.activeElement === first) { e.preventDefault(); last.focus() } }
      else { if (document.activeElement === last) { e.preventDefault(); first.focus() } }
    }
    el.addEventListener('keydown', trap)
    return () => { clearTimeout(timer); el.removeEventListener('keydown', trap) }
  }, [active, ref])
}

// ── Badge view modal ───────────────────────────────────────────────────────────

function BadgeViewModal({ badge, onClose, onDownload }: {
  badge: BadgeItem
  onClose: () => void
  onDownload: () => void
}) {
  const [imgUrl, setImgUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const dialogRef = useRef<HTMLDivElement>(null)
  useFocusTrap(dialogRef, true)

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    return () => { prev?.focus() }
  }, [])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    api.get<Blob>(`/me/badges/${badge.id}/png`, { responseType: 'blob' })
      .then(r => { if (!cancelled) { url = URL.createObjectURL(r.data); setImgUrl(url) } })
      .catch(e => { if (!cancelled) setErr(errorMessage(e as Error, 'Could not load badge')) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url) }
  }, [badge.id])

  return (
    <div role="dialog" aria-modal="true" aria-label={`Badge: ${badge.level_name}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={dialogRef} className="relative w-full max-w-sm space-y-4 rounded-3xl bg-white p-6 shadow-2xl dark:bg-slate-900">
        <button onClick={onClose} aria-label="Close"
          className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200">
          {ico('x', 'h-5 w-5')}
        </button>
        <div>
          <h2 className="pr-8 text-lg font-bold text-slate-900 dark:text-white">{badge.level_name} Badge</h2>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{badge.domain_name} · Awarded {fmtDate(badge.awarded_at)}</p>
        </div>
        <div className="flex min-h-[220px] items-center justify-center rounded-2xl bg-slate-50 p-6 dark:bg-slate-800">
          {loading && <span className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />}
          {err && <p className="text-center text-sm text-red-600 dark:text-red-400">{err}</p>}
          {imgUrl && <img src={imgUrl} alt={`Level ${badge.level_number} badge`} className="h-48 w-48 object-contain drop-shadow-xl" />}
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose}
            className="flex-1 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
            Close
          </button>
          <button onClick={onDownload} disabled={loading || !!err}
            className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400">
            {ico('download', 'h-4 w-4')} Download
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Certificate view modal ─────────────────────────────────────────────────────

function CertViewModal({ domain, onClose, onDownload }: {
  domain: DomainProgress
  onClose: () => void
  onDownload: () => void
}) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const dialogRef = useRef<HTMLDivElement>(null)
  const isMobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)
  useFocusTrap(dialogRef, true)

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    return () => { prev?.focus() }
  }, [])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  useEffect(() => {
    if (!domain.certificate) return
    let url: string | null = null
    let cancelled = false
    api.get<Blob>(`/me/certificates/${domain.certificate.code}/pdf`, { responseType: 'blob' })
      .then(r => { if (!cancelled) { url = URL.createObjectURL(r.data); setPdfUrl(url) } })
      .catch(e => { if (!cancelled) setErr(errorMessage(e as Error, 'Could not load certificate')) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url) }
  }, [domain.certificate?.code])

  const cert = domain.certificate!
  return (
    <div role="dialog" aria-modal="true" aria-label={`Certificate: ${domain.domain_name}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={dialogRef} className="relative flex w-full max-w-4xl flex-col rounded-3xl bg-white shadow-2xl dark:bg-slate-900" style={{ maxHeight: '90vh' }}>
        <div className="flex shrink-0 items-center justify-between border-b border-slate-100 px-6 py-4 dark:border-slate-800">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">{domain.domain_name} Certificate</h2>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">ID: {cert.code} · Issued {fmtDate(cert.issued_at)}</p>
          </div>
          <button onClick={onClose} aria-label="Close"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200">
            {ico('x', 'h-5 w-5')}
          </button>
        </div>
        <div className="relative min-h-[400px] flex-1 overflow-hidden bg-slate-50 dark:bg-slate-800">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
            </div>
          )}
          {err && <div className="absolute inset-0 flex items-center justify-center p-6"><p className="text-center text-sm text-red-600 dark:text-red-400">{err}</p></div>}
          {pdfUrl && !isMobile && <iframe src={pdfUrl} title="Certificate preview" className="h-full w-full border-0" style={{ minHeight: '400px' }} />}
          {pdfUrl && isMobile && (
            <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">PDF preview not available on mobile.</p>
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-6 py-4 dark:border-slate-800">
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Verify: <a href={`/verify/${cert.code}`} target="_blank" rel="noopener noreferrer" className="font-mono text-indigo-600 hover:underline dark:text-indigo-400">/verify/{cert.code}</a>
          </p>
          <div className="flex flex-wrap gap-3">
            <button onClick={onClose}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
              Close
            </button>
            {isMobile && pdfUrl && (
              <a href={pdfUrl} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 px-4 py-2 text-sm font-semibold text-indigo-600 hover:bg-indigo-50">
                {ico('arrow', 'h-4 w-4')} Open in new tab
              </a>
            )}
            <button onClick={onDownload}
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500">
              {ico('download', 'h-4 w-4')} Download PDF
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function AiStatus({ state }: { state: FetchState<unknown> }) {
  if (state.loading) {
    return (
      <p className="flex items-center gap-2 rounded-xl bg-indigo-50 px-3 py-2 text-sm text-indigo-600">
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
        Asking Gemini…
      </p>
    )
  }
  if (state.error) {
    return (
      <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-600">
        {state.error} <button onClick={state.retry} className="ml-1 font-semibold text-indigo-600 underline">Try again</button>
      </p>
    )
  }
  return null
}

function StatTile({ label, value, icon }: { label: string; value: ReactNode; icon: ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white/15 px-4 py-3 backdrop-blur transition hover:bg-white/25">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/25">{icon}</span>
      <div>
        <div className="text-xl font-bold leading-none">{value}</div>
        <div className="mt-1 text-xs text-white/80">{label}</div>
      </div>
    </div>
  )
}

const STATUS_STYLE: Record<LevelStatus, string> = {
  cleared: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  active: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
  locked: 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400',
  removed: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
}

const STATUS_DOT: Record<LevelStatus, string> = {
  cleared: 'bg-emerald-500 text-white',
  active: 'bg-gray-900 text-white ring-4 ring-gray-100 dark:bg-indigo-600 dark:ring-indigo-900/60',
  locked: 'bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500',
  removed: 'bg-red-100 text-red-500 dark:bg-red-900/40 dark:text-red-400',
}

const STATUS_LABEL: Record<LevelStatus, string> = {
  cleared: 'Cleared', active: 'In progress', locked: 'Locked', removed: 'Removed',
}

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

// ── Credential accent palette (must match backend _ACCENTS order) ─────────────
const ACCENT_CLASSES = [
  'bg-indigo-100 text-indigo-700 ring-indigo-200 dark:bg-indigo-900/40 dark:text-indigo-300 dark:ring-indigo-800',
  'bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300 dark:ring-emerald-800',
  'bg-amber-100 text-amber-700 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-800',
  'bg-blue-100 text-blue-700 ring-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:ring-blue-800',
  'bg-purple-100 text-purple-700 ring-purple-200 dark:bg-purple-900/40 dark:text-purple-300 dark:ring-purple-800',
  'bg-pink-100 text-pink-700 ring-pink-200 dark:bg-pink-900/40 dark:text-pink-300 dark:ring-pink-800',
  'bg-teal-100 text-teal-700 ring-teal-200 dark:bg-teal-900/40 dark:text-teal-300 dark:ring-teal-800',
  'bg-orange-100 text-orange-700 ring-orange-200 dark:bg-orange-900/40 dark:text-orange-300 dark:ring-orange-800',
]
const accentClass = (domainId: number) => ACCENT_CLASSES[domainId % ACCENT_CLASSES.length]

function BadgesSection({
  credentials, onDownload,
}: {
  credentials: Credentials | null | undefined
  onDownload: (id: number, domain: string, level: number) => void
}) {
  const [viewingBadge, setViewingBadge] = useState<BadgeItem | null>(null)

  const viewAll = (
    <Link to="/student/credentials" className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 px-3 py-1.5 text-xs font-semibold text-indigo-600 transition hover:bg-indigo-50 dark:border-indigo-800 dark:text-indigo-400 dark:hover:bg-indigo-900/30">
      View All
    </Link>
  )
  if (!credentials) {
    return (
      <Card title="Badges" icon={ico('sparkle')} action={viewAll}>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
          Loading badges…
        </div>
      </Card>
    )
  }

  const byDomain = credentials.badges.reduce<Record<string, BadgeItem[]>>((acc, b) => {
    const key = String(b.domain_id)
    if (!acc[key]) acc[key] = []
    acc[key].push(b)
    return acc
  }, {})

  return (
    <>
      {viewingBadge && (
        <BadgeViewModal
          badge={viewingBadge}
          onClose={() => setViewingBadge(null)}
          onDownload={() => { onDownload(viewingBadge.id, viewingBadge.domain_name, viewingBadge.level_number); setViewingBadge(null) }}
        />
      )}
      <Card title="Badges" icon={ico('sparkle')} action={viewAll}>
        {credentials.badges.length === 0 ? (
          <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500">Pass a level to earn your first badge.</p>
        ) : (
          <div className="space-y-5">
            {Object.entries(byDomain).map(([domId, badges]) => (
              <div key={domId}>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{badges[0].domain_name}</p>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {badges.map((b) => (
                    <div
                      key={b.id}
                      className={`flex flex-col items-center gap-2 rounded-2xl border p-4 text-center transition hover:shadow-md ring-1 ${accentClass(b.domain_id)}`}
                    >
                      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-current/10 text-2xl font-bold">{b.level_number}</span>
                      <div className="min-w-0 w-full">
                        <div className="truncate text-xs font-semibold">{b.level_name}</div>
                        <div className="mt-0.5 text-xs opacity-70">{fmtDate(b.awarded_at)}</div>
                      </div>
                      <div className="mt-1 flex w-full gap-1.5">
                        <button
                          onClick={() => setViewingBadge(b)}
                          className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-current/30 px-2 py-1.5 text-xs font-semibold transition hover:opacity-80"
                        >
                          {ico('eye', 'h-3 w-3')} View
                        </button>
                        <button
                          onClick={() => onDownload(b.id, b.domain_name, b.level_number)}
                          className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-current/30 px-2 py-1.5 text-xs font-semibold transition hover:opacity-80"
                        >
                          {ico('download', 'h-3 w-3')}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  )
}

function CertificatesSection({
  credentials, onDownload,
}: {
  credentials: Credentials | null | undefined
  onDownload: (code: string) => void
}) {
  const [viewingCert, setViewingCert] = useState<DomainProgress | null>(null)

  const viewAll = (
    <Link to="/student/credentials" className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 px-3 py-1.5 text-xs font-semibold text-indigo-600 transition hover:bg-indigo-50 dark:border-indigo-800 dark:text-indigo-400 dark:hover:bg-indigo-900/30">
      View All
    </Link>
  )
  if (!credentials) {
    return (
      <Card title="Domain Certificates" icon={ico('ribbon')} action={viewAll}>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
          Loading certificates…
        </div>
      </Card>
    )
  }

  if (credentials.domains.length === 0) {
    return (
      <Card title="Domain Certificates" icon={ico('ribbon')} action={viewAll}>
        <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500">Enroll in a domain and pass all levels to earn a certificate.</p>
      </Card>
    )
  }

  return (
    <>
      {viewingCert && (
        <CertViewModal
          domain={viewingCert}
          onClose={() => setViewingCert(null)}
          onDownload={() => { onDownload(viewingCert.certificate!.code); setViewingCert(null) }}
        />
      )}
      <Card title="Domain Certificates" icon={ico('ribbon')} action={viewAll}>
        <ul className="space-y-3">
          {credentials.domains.map((d) => (
            <li key={d.domain_id} className={`rounded-xl border p-4 transition hover:shadow-md ${d.completed ? 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-800/60 dark:bg-emerald-900/20' : 'border-slate-100 dark:border-slate-700'}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${d.completed ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400' : 'bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500'}`}>
                    {ico('ribbon', 'h-5 w-5')}
                  </span>
                  <div>
                    <div className="font-semibold text-slate-900 dark:text-white">{d.domain_name}</div>
                    {d.completed ? (
                      <div className="mt-0.5 flex items-center gap-1.5 text-xs text-emerald-600">
                        {ico('check', 'h-3.5 w-3.5')} Domain Completed · {d.total_levels}/{d.total_levels} levels
                      </div>
                    ) : (
                      <div className="mt-0.5 text-xs text-slate-500">{d.passed_levels}/{d.total_levels} levels completed</div>
                    )}
                  </div>
                </div>
                {d.completed && d.certificate ? (
                  <div className="flex shrink-0 flex-wrap gap-2">
                    <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">Certificate Available</span>
                    <button
                      onClick={() => setViewingCert(d)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 px-3 py-1.5 text-xs font-semibold text-indigo-600 transition hover:bg-indigo-50"
                    >
                      {ico('eye', 'h-3.5 w-3.5')} View
                    </button>
                    <button
                      onClick={() => onDownload(d.certificate!.code)}
                      className="rounded-lg border border-indigo-200 px-3 py-1.5 text-xs font-semibold text-indigo-600 transition hover:bg-indigo-50"
                    >
                      Download PDF
                    </button>
                  </div>
                ) : d.completed ? (
                  <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">Processing…</span>
                ) : (
                  <div className="w-32">
                    <div className="mb-1 flex justify-between text-xs text-slate-500">
                      <span>Progress</span><span>{d.passed_levels}/{d.total_levels}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-2 rounded-full bg-linear-to-r from-indigo-500 to-purple-500 transition-all"
                        style={{ width: `${d.total_levels > 0 ? Math.round(d.passed_levels / d.total_levels * 100) : 0}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
              {d.certificate && (
                <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">ID: {d.certificate.code} · Issued {fmtDate(d.certificate.issued_at)}</p>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}
const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })

// ── Booking confirmation modal ─────────────────────────────────────────────

function BookingConfirmModal({
  slot,
  onConfirm,
  onCancel,
  busy,
}: {
  slot: { id: number; starts_at: string; venue: string; seats_left: number }
  onConfirm: (slotId: number) => void
  onCancel: () => void
  busy: boolean
}) {
  const [acknowledged, setAcknowledged] = useState(false)
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl space-y-4 dark:bg-slate-900">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Confirm Slot Booking</h2>
        <div className="rounded-xl bg-slate-50 p-3 text-sm space-y-1 dark:bg-slate-800">
          <div className="font-semibold text-slate-800 dark:text-slate-100">{fmtDate(slot.starts_at)} · {fmtTime(slot.starts_at)}</div>
          <div className="text-slate-500 dark:text-slate-400">{slot.venue} · {slot.seats_left} seat{slot.seats_left !== 1 ? 's' : ''} left</div>
        </div>
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 space-y-1.5 dark:border-amber-700/60 dark:bg-amber-900/20 dark:text-amber-300">
          <p className="font-semibold">Slot booking rules:</p>
          <ul className="list-disc pl-4 space-y-1 text-xs">
            <li>You can cancel within 30 minutes of booking.</li>
            <li>You can change your slot within 30 minutes of booking.</li>
            <li>After 30 minutes, cancellation/change is not allowed.</li>
            <li>If you book a slot and skip the examination, it will affect your points and examination attempts.</li>
            <li>Make sure you are available at the selected time.</li>
          </ul>
        </div>
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded accent-indigo-600"
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
          />
          <span className="text-sm text-slate-700 dark:text-slate-300">I understand the slot booking rules and agree to the above conditions.</span>
        </label>
        <div className="flex gap-3 pt-1">
          <button onClick={onCancel} className="flex-1 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
            Go Back
          </button>
          <button
            disabled={!acknowledged || busy}
            onClick={() => onConfirm(slot.id)}
            className="flex-1 group inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none"
          >
            {busy ? 'Booking…' : 'Confirm Booking'}
          </button>
        </div>
      </div>
    </div>
  )
}

function useBookingCountdown(deadline: string | null | undefined, serverSecondsRemaining: number | undefined) {
  const [seconds, setSeconds] = useState(serverSecondsRemaining ?? 0)
  const startRef = useRef<number>(Date.now())
  const initialRef = useRef<number>(serverSecondsRemaining ?? 0)

  useEffect(() => {
    if (!deadline) return
    startRef.current = Date.now()
    initialRef.current = serverSecondsRemaining ?? 0
    setSeconds(initialRef.current)
    if (initialRef.current <= 0) return
    const id = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startRef.current) / 1000)
      const remaining = Math.max(0, initialRef.current - elapsed)
      setSeconds(remaining)
    }, 1000)
    return () => clearInterval(id)
  // Only reset when the booking itself changes (new deadline)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deadline])

  return seconds
}

function fmtCountdown(sec: number) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

// ── Current Domain card ────────────────────────────────────────────────────

// ── Slot Booking card ─────────────────────────────────────────────────────────

function SlotBookingCard({
  data,
  onAct,
  cancelConfirm,
  setCancelConfirm,
  changeSlotId,
  setChangeSlotId,
  changeBusy,
  setChangeBusy,
}: {
  data: Dashboard
  onAct: (req: () => Promise<unknown>) => void
  cancelConfirm: boolean
  setCancelConfirm: (v: boolean) => void
  changeSlotId: number | null
  setChangeSlotId: (v: number | null) => void
  changeBusy: boolean
  setChangeBusy: (v: boolean) => void
}) {
  const { slots, active_booking } = data
  const [bookingSlot, setBookingSlot] = useState<typeof slots[0] | null>(null)
  const [bookBusy, setBookBusy] = useState(false)
  const [bookErr, setBookErr] = useState('')

  const windowSeconds = useBookingCountdown(
    active_booking?.change_cancel_deadline,
    active_booking?.seconds_remaining_in_window,
  )
  const windowExpired = active_booking ? windowSeconds === 0 : false

  async function confirmBooking(slotId: number) {
    setBookBusy(true)
    setBookErr('')
    try {
      await onAct(() => api.post(`/slots/${slotId}/book`, { acknowledgement: true }))
      setBookingSlot(null)
    } catch (e) {
      setBookErr(errorMessage(e as Error))
    } finally {
      setBookBusy(false)
    }
  }

  async function doCancel() {
    if (!active_booking) return
    setCancelConfirm(false)
    await onAct(() => api.delete(`/me/bookings/${active_booking.booking_id}`))
  }

  async function doChange(newSlotId: number) {
    if (!active_booking) return
    setChangeBusy(true)
    try {
      await onAct(() => api.post(`/me/bookings/${active_booking.booking_id}/change`, { new_slot_id: newSlotId }))
      setChangeSlotId(null)
    } catch (e) {
      // bubble up via onAct error handling isn't available here — handle inline
      alert(errorMessage(e as Error))
    } finally {
      setChangeBusy(false)
    }
  }

  return (
    <>
      {bookingSlot && (
        <BookingConfirmModal
          slot={bookingSlot}
          onConfirm={confirmBooking}
          onCancel={() => { setBookingSlot(null); setBookErr('') }}
          busy={bookBusy}
        />
      )}
      {bookErr && (
        <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{bookErr}</p>
      )}

      {/* Cancel confirmation dialog */}
      {cancelConfirm && active_booking && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
          role="dialog" aria-modal="true"
        >
          <div className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl space-y-4 text-center dark:bg-slate-900">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Cancel Examination Booking?</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {active_booking.level_name} · {fmtDate(active_booking.starts_at)} at {fmtTime(active_booking.starts_at)}
            </p>
            <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">This will free your seat. You can re-book another slot later.</p>
            <div className="flex gap-3">
              <button onClick={() => setCancelConfirm(false)} className="flex-1 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
                Keep Booking
              </button>
              <button onClick={doCancel} className="flex-1 rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500">
                Yes, Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <Card title="Book your test slot" icon={ico('calendar')}>
        {/* Active booking view */}
        {active_booking && (
          <div className="mb-4 rounded-xl border border-emerald-300 bg-emerald-50 p-4 space-y-2 dark:border-emerald-700/60 dark:bg-emerald-900/20">
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-800 dark:text-emerald-300">
              {ico('check', 'h-4 w-4')} Your Booking
            </div>
            <div className="text-sm text-slate-700 font-semibold dark:text-slate-200">{fmtDate(active_booking.starts_at)} · {fmtTime(active_booking.starts_at)}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">{active_booking.venue}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">{active_booking.level_name}</div>

            {/* 30-min countdown */}
            {!windowExpired ? (
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800 dark:bg-amber-900/20 dark:border-amber-700/60 dark:text-amber-300">
                <span className="font-semibold">{ico('clock', 'inline-block h-3.5 w-3.5 mr-1 align-text-bottom')}
                Change/cancel window: </span>
                <span className="font-mono text-base font-bold">{fmtCountdown(windowSeconds)}</span>
                <span> remaining</span>
              </div>
            ) : (
              <p className="rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-500 dark:bg-slate-700 dark:text-slate-400">
                The 30-minute change/cancellation window has expired. You can no longer change or cancel this booking.
              </p>
            )}

            <div className="flex gap-2 pt-1">
              <button
                disabled={windowExpired}
                onClick={() => setCancelConfirm(true)}
                className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Cancel Booking
              </button>
              <button
                disabled={windowExpired}
                onClick={() => setChangeSlotId(active_booking.slot_id)}
                className="rounded-lg border border-indigo-200 px-3 py-1.5 text-xs font-semibold text-indigo-600 hover:bg-indigo-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Change Slot
              </button>
            </div>
          </div>
        )}

        {/* Available slots */}
        {!active_booking && slots.length === 0 && (
          <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500">
            No upcoming slots for this level yet. Ask your admin or track owner to schedule one.
          </p>
        )}
        {!active_booking && (
          <ul className="space-y-3">
            {slots.map((s) => {
              const full = s.seats_left === 0
              const isChange = changeSlotId !== null && changeSlotId !== s.id
              return (
                <li key={s.id} className={`flex items-center justify-between gap-3 rounded-xl border p-3 text-sm transition hover:shadow-md ${full ? 'opacity-60 border-slate-100 dark:border-slate-700' : 'border-slate-100 dark:border-slate-700'}`}>
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-400">{ico('calendar', 'h-5 w-5')}</span>
                    <div>
                      <div className="font-semibold dark:text-slate-100">{fmtDate(s.starts_at)} · {fmtTime(s.starts_at)}</div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">{s.venue} · {full ? 'Full' : `${s.seats_left} seats left`}</div>
                    </div>
                  </div>
                  {full ? (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500 dark:bg-slate-700 dark:text-slate-400">Full</span>
                  ) : isChange ? (
                    <button
                      disabled={changeBusy}
                      onClick={() => doChange(s.id)}
                      className={primaryBtn}
                    >
                      {changeBusy ? 'Changing…' : 'Select'}
                    </button>
                  ) : (
                    <button
                      onClick={() => setBookingSlot(s)}
                      className={primaryBtn}
                    >
                      Book
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
        {changeSlotId !== null && !active_booking && (
          <button onClick={() => setChangeSlotId(null)} className="mt-2 text-xs font-semibold text-slate-500 hover:text-slate-800">
            Cancel slot change
          </button>
        )}
      </Card>
    </>
  )
}

export default function StudentDashboard() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [cancelConfirm, setCancelConfirm] = useState(false)
  const [changeSlotId, setChangeSlotId] = useState<number | null>(null)
  const [changeBusy, setChangeBusy] = useState(false)
  const [skillGapAttempt, setSkillGapAttempt] = useState(0)
  const [skillGapState, setSkillGapState] = useState<{
    data: SkillGapReport | null
    error: string
    loading: boolean
  }>({ data: null, error: '', loading: false })
  const skillGapGeneration = useRef<Promise<SkillGapReport> | null>(null)

  const hasActiveLevel = !!data?.levels.some((l) => l.status === 'active')
  const hasCompletedAssessment = !!data?.levels.some((l) => l.attempts_used > 0)
  const recs = useFetch<{ recommendations: AiRec[] }>(data && (data.user.semester ?? 1) >= 3 ? '/ai/recommendations' : null)
  // Load the AI cards one after another, so the free Gemini tier's requests-per-minute limit is not hit
  // Only fetch if previous fetch succeeded or wasn't attempted
  const prep = useFetch<AiPrep>(hasActiveLevel && !recs.loading && !recs.error ? '/ai/prep' : null)
  const credentials = useFetch<Credentials>(data ? '/me/credentials' : null)
  const skillGapReport: FetchState<SkillGapReport> = {
    ...skillGapState,
    retry: () => setSkillGapAttempt((attempt) => attempt + 1),
  }

  const load = useCallback(async () => {
    try {
      const res = await api.get<Dashboard>('/me/dashboard')
      setData(res.data)
      setLoadError('')
    } catch (err) {
      setLoadError(errorMessage(err, 'Could not load your dashboard'))
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!data) return
    let cancelled = false
    const setResult = (result: SkillGapReport | null, error = '') => {
      if (!cancelled) setSkillGapState({ data: result, error, loading: false })
    }

    async function loadSkillGapReport() {
      setSkillGapState({ data: null, error: '', loading: true })
      try {
        const latest = await api.get<SkillGapReport>('/ai/skill-gap/latest')
        setResult(latest.data)
        return
      } catch (err) {
        if (!axios.isAxiosError(err) || err.response?.status !== 404) {
          setResult(null, errorMessage(err, 'Could not load your skill-gap analysis'))
          return
        }
      }

      if (!hasCompletedAssessment) {
        setResult(null)
        return
      }

      let generation: Promise<SkillGapReport> | null = null
      try {
        generation = skillGapGeneration.current
        if (!generation) {
          generation = api.post<SkillGapReport>('/ai/skill-gap/analyze').then((res) => res.data)
          skillGapGeneration.current = generation
        }
        setResult(await generation)
      } catch (err) {
        setResult(null, errorMessage(err, 'Could not generate your skill-gap analysis'))
      } finally {
        if (skillGapGeneration.current === generation) skillGapGeneration.current = null
      }
    }

    loadSkillGapReport()
    return () => { cancelled = true }
  }, [data !== null, hasCompletedAssessment, skillGapAttempt])

  async function act(request: () => Promise<unknown>) {
    setActionError('')
    try {
      await request()
      await load()
    } catch (err) {
      setActionError(errorMessage(err))
    }
  }

  async function downloadCertificate(code: string) {
    setActionError('')
    let url: string | null = null
    try {
      const res = await api.get<Blob>(`/me/certificates/${code}/pdf`, { responseType: 'blob' })
      url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = `${code}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      setActionError(errorMessage(err, 'Could not download the certificate'))
    } finally {
      if (url) URL.revokeObjectURL(url)
    }
  }

  async function downloadBadge(badgeId: number, domainName: string, levelNumber: number) {
    setActionError('')
    try {
      const res = await api.get<Blob>(`/me/badges/${badgeId}/png`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = `badge-${domainName.toLowerCase().replace(/\s+/g, '-')}-level-${levelNumber}.png`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setActionError(errorMessage(err, 'Could not download the badge'))
    }
  }

  if (loadError) return <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">{loadError}</p>
  if (!data) {
    return (
      <div className="flex items-center gap-3 text-sm text-slate-500">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
        Loading your dashboard…
      </div>
    )
  }

  const { user, enrollment, levels } = data
  const semester = user.semester ?? 1
  const activeLevel = levels.find((l) => l.status === 'active')
  const pointsPct = Math.min(100, Math.round((data.total_points / data.points_to_unlock) * 100))
  const clearedCount = levels.filter((l) => l.status === 'cleared').length
  const badgeCount = credentials.data?.badges.length ?? 0
  const certCount = credentials.data?.domains.filter((d) => d.completed).length ?? data.certificates.length
  const semPct = semesters.length > 1 ? ((semester - 1) / (semesters.length - 1)) * 100 : 0
  const edge = `${50 / semesters.length}%`

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-slate-950 p-6 text-white shadow-2xl sm:p-10 xl:min-h-72">
        <div className="pointer-events-none absolute -right-20 -top-20 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/4 h-96 w-96 rounded-full bg-purple-600/20 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-1/4 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="relative z-10 max-w-xl xl:max-w-[55%]">
          <p className="text-sm font-medium text-white/80">Welcome back 👋</p>
          <h1 className="mt-1 text-3xl font-bold sm:text-4xl">{user.name}</h1>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
            {user.department && <span className="rounded-full bg-white/20 px-3 py-1">{user.department}</span>}
            <span className="rounded-full bg-white/20 px-3 py-1">Semester {semester}</span>
            {enrollment && <span className="rounded-full bg-amber-300/90 px-3 py-1 text-amber-950">{enrollment.domain}</span>}
          </div>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-2 2xl:grid-cols-4">
            <StatTile label="Points" value={enrollment?.points ?? 0} icon={ico('star', 'h-5 w-5')} />
            <StatTile label="Levels cleared" value={`${clearedCount}/${levels.length}`} icon={ico('flag', 'h-5 w-5')} />
            <StatTile label="Badges earned" value={badgeCount} icon={ico('sparkle', 'h-5 w-5')} />
            <StatTile label="Certificates" value={certCount} icon={ico('ribbon', 'h-5 w-5')} />
          </div>
        </div>
        <div className="pointer-events-none absolute -bottom-2 right-6 hidden w-72 xl:block">
          <StudentIllustration />
        </div>
      </section>

      {actionError && (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{actionError}</p>
      )}


      {/* Semester stepper */}
      <Card title="Semester progress" icon={ico('cap')}>
        <div className="relative">
          <div className="absolute top-5 h-1.5 rounded-full bg-slate-100/80 shadow-inner" style={{ left: edge, right: edge }}>
            <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 shadow-md transition-all duration-700" style={{ width: `${semPct}%` }} />
          </div>
          <ol className="relative grid" style={{ gridTemplateColumns: `repeat(${semesters.length}, minmax(0, 1fr))` }}>
            {semesters.map((s) => {
              const state = s.sem < semester ? 'done' : s.sem === semester ? 'current' : 'upcoming'
              const dot = {
                done: 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/30',
                current: 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/40 ring-4 ring-indigo-500/20',
                upcoming: 'border-2 border-slate-200 bg-white text-slate-400 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-500',
              }[state]
              return (
                <li key={s.sem} className="flex flex-col items-center text-center">
                  <span className={`relative flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold ${dot}`}>
                    {state === 'done' ? ico('check', 'h-5 w-5') : s.sem}
                    {state === 'current' && <span className="absolute inset-0 animate-ping rounded-full bg-indigo-400/40" />}
                  </span>
                  <span className={`mt-2 text-sm font-semibold ${state === 'upcoming' ? 'text-slate-400 dark:text-slate-500' : 'text-slate-800 dark:text-slate-100'}`}>Sem {s.sem}</span>
                  <span className="text-xs text-slate-500 dark:text-slate-400">{s.label}</span>
                </li>
              )
            })}
          </ol>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="AI recommended domains (top 3)" icon={ico('sparkle')}>
          <AiStatus state={recs} />
          <ul className="space-y-4">
            {(recs.data?.recommendations ?? []).map((r) => (
              <li key={r.domain} className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
                <div className="flex justify-between text-sm font-semibold">
                  <span>{r.domain}</span><span className="text-indigo-600">{r.match}% match</span>
                </div>
                <div className="mt-2 h-2 rounded-full bg-slate-100/80 shadow-inner">
                  <div className="h-2 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-700" style={{ width: `${r.match}%` }} />
                </div>
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{r.reason}</p>
              </li>
            ))}
          </ul>

          {semester < 3 ? (
            <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">Semesters 1–2 use common assessments. Domain selection opens in Semester 3.</p>
          ) : (
            <Link to="/student/domains" className={`${primaryBtn} mt-4 w-full`}>
              Browse & Enroll in Domains {ico('arrow', 'h-4 w-4')}
            </Link>
          )}
        </Card>

        <Card title="Points & badges" icon={ico('star')}>
          {enrollment?.is_common ? (
            <>
              <div className="text-4xl font-bold text-slate-900">{enrollment.points} <span className="text-base font-normal text-slate-500">pts</span></div>
              <p className="mt-2 text-sm text-slate-500">Domain selection opens in Semester 3, based on how you do in these common tests.</p>
              <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-800">
                🏅 Badges earned: {badgeCount}
              </p>
            </>
          ) : data.total_points > 0 || enrollment ? (
            <>
              <div className="text-4xl font-bold text-slate-900">
                {data.total_points} <span className="text-base font-normal text-slate-500">/ {data.points_to_unlock} pts</span>
              </div>
              <div className="mt-3 h-3 rounded-full bg-slate-100/80 shadow-inner">
                <div
                  className={`h-3 rounded-full transition-all duration-700 ${data.points_unlocked ? 'bg-linear-to-r from-emerald-400 to-emerald-500' : 'bg-linear-to-r from-indigo-500 to-purple-500'}`}
                  style={{ width: `${pointsPct}%` }}
                />
              </div>
              {data.total_points >= data.points_to_unlock ? (
                <>
                  <p className="mt-2 text-sm font-semibold text-emerald-600">
                    {ico('check', 'inline-block h-4 w-4 mr-1 align-text-bottom')} Domain unlocked — you can choose your next track!
                  </p>
                  {!enrollment && data.completed_domain && (
                    <Link to="/student/domains" className={`${primaryBtn} mt-3`}>
                      {ico('grid', 'h-4 w-4')} Choose Your Next Domain
                    </Link>
                  )}
                </>
              ) : (
                <p className="mt-2 text-sm text-slate-500">
                  {enrollment
                    ? `Earn ${data.points_to_unlock - data.total_points} more points to unlock another domain.`
                    : 'Start earning points by completing levels.'}
                </p>
              )}
              <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-800">
                🏅 Badges earned: {badgeCount}
              </p>
            </>
          ) : (
            <p className="text-sm text-slate-500">Enroll in a domain to start earning points and badges.</p>
          )}
        </Card>
      </div>

      {enrollment && (
        <Card title={`${enrollment.domain} · Levels`} icon={ico('flag')}>
          <ul className="space-y-2">
            {levels.map((l) => (
              <li key={l.id} className={`flex flex-wrap items-center gap-3 rounded-xl border p-3 transition hover:shadow-md ${l.status === 'active' ? 'border-indigo-200 bg-indigo-50/50 dark:border-indigo-800/60 dark:bg-indigo-900/20' : 'border-slate-100 dark:border-slate-700'}`}>
                <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold ${STATUS_DOT[l.status]}`}>
                  {l.status === 'cleared' ? ico('check', 'h-5 w-5') : l.status === 'locked' ? ico('lock') : l.number}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold dark:text-slate-100">{l.name} {l.first_attempt && <span title="Cleared on first attempt">🏅</span>}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    Attempts: {l.attempts_used}{data.max_attempts !== null && `/${data.max_attempts}`}{l.score !== null && ` · Last score ${l.score}%`}
                  </div>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLE[l.status]}`}>{STATUS_LABEL[l.status]}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-slate-400">
            {data.max_attempts !== null
              ? `Failing all ${data.max_attempts} attempts removes you from the domain.`
              : 'Your test opens for the semester you are in. You can retake it until you clear it.'}
          </p>
        </Card>
      )}

      {activeLevel && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title={`Prepare for ${activeLevel.name}`} icon={ico('book')}>
            <AiStatus state={prep} />
            {prep.data && (
              <div className="space-y-4">
                <div>
                  <p className="mb-1.5 text-sm font-semibold">What to learn</p>
                  <ul className="space-y-1.5 text-sm text-slate-600 dark:text-slate-300">
                    {prep.data.focus_topics.map((t) => (
                      <li key={t.topic} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800"><span className="font-semibold text-slate-800 dark:text-slate-100">{t.topic}</span> — {t.why}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-1.5 text-sm font-semibold">Study plan</p>
                  <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600 marker:font-semibold marker:text-indigo-500">
                    {prep.data.study_plan.map((s) => <li key={s}>{s}</li>)}
                  </ol>
                </div>
                <div>
                  <p className="mb-1.5 text-sm font-semibold">Requirements</p>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 marker:text-indigo-500">
                    {prep.data.requirements.map((t) => <li key={t}>{t}</li>)}
                  </ul>
                </div>
              </div>
            )}
          </Card>

          <SlotBookingCard
            data={data}
            onAct={act}
            cancelConfirm={cancelConfirm}
            setCancelConfirm={setCancelConfirm}
            changeSlotId={changeSlotId}
            setChangeSlotId={setChangeSlotId}
            changeBusy={changeBusy}
            setChangeBusy={setChangeBusy}
          />
        </div>
      )}

      <Card title="AI skill gap analysis" icon={ico('chart')}>
        <AiStatus state={skillGapReport} />
        {skillGapReport.data ? (
          <div className="space-y-4">
            <div className="rounded-xl bg-gradient-to-br from-indigo-50 to-purple-50 p-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">Overall Readiness</div>
              <div className="text-2xl font-bold text-slate-900">{skillGapReport.data.readiness}</div>
              <p className="mt-2 text-sm text-slate-600">{skillGapReport.data.overall_summary}</p>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-xl border border-green-200 bg-green-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-green-600">Strengths</div>
                <div className="mt-1 text-2xl font-bold text-slate-900">{skillGapReport.data.strengths.length}</div>
              </div>
              <div className="rounded-xl border border-red-200 bg-red-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-red-600">Skill Gaps</div>
                <div className="mt-1 text-2xl font-bold text-slate-900">
                  {skillGapReport.data.gaps.filter(g => g.severity === 'HIGH' || g.severity === 'MEDIUM').length}
                </div>
              </div>
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-amber-600">Confidence</div>
                <div className="mt-1 text-2xl font-bold text-slate-900">{skillGapReport.data.confidence}</div>
              </div>
            </div>

            {skillGapReport.data.gaps.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="mb-2 text-xs font-semibold text-slate-700">Top Priority Gap</div>
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900">{skillGapReport.data.gaps[0].topic}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                    skillGapReport.data.gaps[0].severity === 'HIGH' ? 'bg-red-100 text-red-700' :
                    skillGapReport.data.gaps[0].severity === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                    'bg-green-100 text-green-700'
                  }`}>
                    {skillGapReport.data.gaps[0].severity}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-600">{skillGapReport.data.gaps[0].score}% · {skillGapReport.data.gaps[0].trend}</p>
              </div>
            )}

            <Link
              to="/student/skill-analysis"
              className="group flex items-center justify-center gap-2 rounded-xl border-2 border-indigo-600 bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition-all hover:-translate-y-0.5 hover:bg-indigo-700 hover:shadow-xl"
            >
              <span>View Full AI Analysis</span>
              {ico('arrow', 'h-4 w-4 transition-transform group-hover:translate-x-1')}
            </Link>
          </div>
        ) : !hasCompletedAssessment && !skillGapReport.loading && !skillGapReport.error ? (
          <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500">Your skill-gap analysis appears after your first assessment.</p>
        ) : null}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <BadgesSection credentials={credentials.data} onDownload={downloadBadge} />
        <CertificatesSection credentials={credentials.data} onDownload={downloadCertificate} />
      </div>
    </div>
  )
}
