import { useEffect, useRef, useState } from 'react'
import { api, errorMessage } from '../api'
import Card from '../components/Card'
import { Icon } from '../components/AuthLayout'
import { useFetch } from '../useFetch'

// ── Types ──────────────────────────────────────────────────────────────────────

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

// ── Icons ──────────────────────────────────────────────────────────────────────

const PATHS = {
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z',
  ribbon:  'M12 14a6 6 0 100-12 6 6 0 000 12zM8.5 13L7 22l5-3 5 3-1.5-9',
  check:   'M5 13l4 4L19 7',
  download:'M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 4v11',
  x:       'M6 18L18 6M6 6l12 12',
  eye:     'M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z',
  arrow:   'M5 12h14m-6-6l6 6-6 6',
}

const ico = (name: keyof typeof PATHS, cls = 'h-4 w-4') => (
  <Icon className={cls}><path strokeLinecap="round" strokeLinejoin="round" d={PATHS[name]} /></Icon>
)

// ── Helpers ────────────────────────────────────────────────────────────────────

const ACCENT = [
  'bg-indigo-100 text-indigo-700 ring-indigo-200 dark:bg-indigo-900/40 dark:text-indigo-300 dark:ring-indigo-800',
  'bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300 dark:ring-emerald-800',
  'bg-amber-100 text-amber-700 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-800',
  'bg-blue-100 text-blue-700 ring-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:ring-blue-800',
  'bg-purple-100 text-purple-700 ring-purple-200 dark:bg-purple-900/40 dark:text-purple-300 dark:ring-purple-800',
  'bg-pink-100 text-pink-700 ring-pink-200 dark:bg-pink-900/40 dark:text-pink-300 dark:ring-pink-800',
  'bg-teal-100 text-teal-700 ring-teal-200 dark:bg-teal-900/40 dark:text-teal-300 dark:ring-teal-800',
  'bg-orange-100 text-orange-700 ring-orange-200 dark:bg-orange-900/40 dark:text-orange-300 dark:ring-orange-800',
]
const accent = (id: number) => ACCENT[id % ACCENT.length]

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

// ── Focus-trap hook ────────────────────────────────────────────────────────────

function useFocusTrap(containerRef: { current: HTMLElement | null }, active: boolean) {
  useEffect(() => {
    if (!active || !containerRef.current) return
    const el = containerRef.current
    const sel = 'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'
    const focusable = () =>
      Array.from(el.querySelectorAll<HTMLElement>(sel)).filter((n) => !(n as HTMLButtonElement).disabled)
    const timer = setTimeout(() => focusable()[0]?.focus(), 0)
    function trap(e: KeyboardEvent) {
      if (e.key !== 'Tab') return
      const nodes = focusable()
      if (!nodes.length) return
      const first = nodes[0], last = nodes[nodes.length - 1]
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus() }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    el.addEventListener('keydown', trap)
    return () => { clearTimeout(timer); el.removeEventListener('keydown', trap) }
  }, [active, containerRef])
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
      .then((r) => { if (!cancelled) { url = URL.createObjectURL(r.data); setImgUrl(url) } })
      .catch((e) => { if (!cancelled) setErr(errorMessage(e as Error, 'Could not load badge')) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url) }
  }, [badge.id])

  return (
    <div
      role="dialog" aria-modal="true" aria-label={`Badge: ${badge.level_name}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
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
            className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 dark:disabled:bg-slate-700">
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
      .then((r) => { if (!cancelled) { url = URL.createObjectURL(r.data); setPdfUrl(url) } })
      .catch((e) => { if (!cancelled) setErr(errorMessage(e as Error, 'Could not load certificate')) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url) }
  }, [domain.certificate?.code])

  const cert = domain.certificate!

  return (
    <div
      role="dialog" aria-modal="true" aria-label={`Certificate: ${domain.domain_name}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div ref={dialogRef} className="relative flex w-full max-w-4xl flex-col rounded-3xl bg-white shadow-2xl dark:bg-slate-900"
        style={{ maxHeight: '90vh' }}>

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
          {err && (
            <div className="absolute inset-0 flex items-center justify-center p-6">
              <p className="text-center text-sm text-red-600 dark:text-red-400">{err}</p>
            </div>
          )}
          {pdfUrl && !isMobile && (
            <iframe src={pdfUrl} title={`${domain.domain_name} certificate`}
              className="h-full w-full border-0" style={{ minHeight: '400px' }} />
          )}
          {pdfUrl && isMobile && (
            <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
              <div className="rounded-2xl bg-indigo-50 p-6 dark:bg-indigo-900/30">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-indigo-100 text-indigo-500 dark:bg-indigo-900/60 dark:text-indigo-400">
                  {ico('ribbon', 'h-7 w-7')}
                </div>
                <p className="mt-3 text-sm font-semibold text-slate-700 dark:text-slate-200">PDF preview not available on mobile.</p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Use the buttons below to open or save your certificate.</p>
              </div>
            </div>
          )}
        </div>

        <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-6 py-4 dark:border-slate-800">
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Verify:{' '}
            <a href={`/verify/${cert.code}`} target="_blank" rel="noopener noreferrer"
              className="font-mono text-indigo-600 hover:underline dark:text-indigo-400">
              /verify/{cert.code}
            </a>
          </p>
          <div className="flex flex-wrap gap-3">
            <button onClick={onClose}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
              Close
            </button>
            {isMobile && pdfUrl && (
              <a href={pdfUrl} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 px-4 py-2 text-sm font-semibold text-indigo-600 hover:bg-indigo-50 dark:border-indigo-700 dark:text-indigo-400 dark:hover:bg-indigo-900/30">
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

// ── Page ───────────────────────────────────────────────────────────────────────

export default function CredentialsPage() {
  const creds = useFetch<Credentials>('/me/credentials')
  const [actionErr, setActionErr] = useState('')
  const [viewingBadge, setViewingBadge] = useState<BadgeItem | null>(null)
  const [viewingCert, setViewingCert] = useState<DomainProgress | null>(null)

  async function downloadCert(code: string) {
    setActionErr('')
    try {
      const res = await api.get<Blob>(`/me/certificates/${code}/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url; a.download = `${code}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch (e) { setActionErr(errorMessage(e as Error, 'Could not download certificate')) }
  }

  async function downloadBadge(id: number, domain: string, level: number) {
    setActionErr('')
    try {
      const res = await api.get<Blob>(`/me/badges/${id}/png`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url; a.download = `badge-${domain.toLowerCase().replace(/\s+/g, '-')}-level-${level}.png`
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch (e) { setActionErr(errorMessage(e as Error, 'Could not download badge')) }
  }

  const { loading, data } = creds

  const byDomain = (data?.badges ?? []).reduce<Record<string, BadgeItem[]>>((acc, b) => {
    ;(acc[b.domain_id] ??= []).push(b)
    return acc
  }, {})

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-slate-950 p-6 text-white shadow-2xl sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-20 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/4 h-96 w-96 rounded-full bg-purple-600/20 blur-3xl" />
        <div className="relative">
          <h1 className="text-3xl font-bold">My Badges &amp; Certificates</h1>
          <p className="mt-1 text-sm text-slate-400">All your earned credentials in one place.</p>
          {data && (
            <div className="mt-4 flex flex-wrap gap-3 text-sm font-semibold">
              <span className="rounded-full bg-white/10 px-3 py-1">
                {data.badges.length} badge{data.badges.length !== 1 ? 's' : ''}
              </span>
              <span className="rounded-full bg-white/10 px-3 py-1">
                {data.domains.filter(d => d.completed).length} certificate{data.domains.filter(d => d.completed).length !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </div>
      </section>

      {actionErr && (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800/60 dark:bg-red-900/20 dark:text-red-300">{actionErr}</p>
      )}

      {/* Badges */}
      <Card title="Badges" icon={ico('sparkle')}>
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />Loading…
          </div>
        ) : !data || data.badges.length === 0 ? (
          <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:bg-slate-800 dark:text-slate-400">Pass a level to earn your first badge.</p>
        ) : (
          <div className="space-y-6">
            {Object.entries(byDomain).map(([domId, badges]) => (
              <div key={domId}>
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{badges[0].domain_name}</p>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                  {badges.map((b) => (
                    <div key={b.id}
                      className={`flex flex-col items-center gap-2 rounded-2xl border p-3 text-center ring-1 transition hover:shadow-md ${accent(b.domain_id)}`}>
                      <span className="text-3xl font-bold leading-none">{b.level_number}</span>
                      <div>
                        <div className="text-xs font-semibold">{b.level_name}</div>
                        <div className="mt-0.5 text-xs opacity-70">{fmtDate(b.awarded_at)}</div>
                      </div>
                      <div className="mt-1 flex w-full flex-col gap-1.5">
                        <button onClick={() => setViewingBadge(b)}
                          className="w-full rounded-lg border border-current/30 px-2 py-1.5 text-xs font-semibold transition hover:opacity-75">
                          {ico('eye', 'inline-block h-3 w-3 mr-1 align-text-bottom')} View
                        </button>
                        <button onClick={() => downloadBadge(b.id, b.domain_name, b.level_number)}
                          className="w-full rounded-lg border border-current/30 px-2 py-1.5 text-xs font-semibold transition hover:opacity-75">
                          {ico('download', 'inline-block h-3 w-3 mr-1 align-text-bottom')} Download
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

      {/* Certificates */}
      <Card title="Domain Certificates" icon={ico('ribbon')}>
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />Loading…
          </div>
        ) : !data || data.domains.length === 0 ? (
          <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:bg-slate-800 dark:text-slate-400">Complete all levels in a domain to earn a certificate.</p>
        ) : (
          <ul className="space-y-3">
            {data.domains.map((d) => (
              <li key={d.domain_id}
                className={`rounded-xl border p-4 transition hover:shadow-md ${d.completed ? 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-800/60 dark:bg-emerald-900/20' : 'border-slate-100 dark:border-slate-700'}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${d.completed ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400' : 'bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500'}`}>
                      {ico('ribbon', 'h-5 w-5')}
                    </span>
                    <div>
                      <div className="font-semibold text-slate-900 dark:text-white">{d.domain_name}</div>
                      {d.completed ? (
                        <div className="mt-0.5 flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400">
                          {ico('check', 'h-3.5 w-3.5')} Completed · {d.total_levels}/{d.total_levels} levels
                        </div>
                      ) : (
                        <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{d.passed_levels}/{d.total_levels} levels</div>
                      )}
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    {d.completed && d.certificate ? (
                      <>
                        <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">Available</span>
                        <button onClick={() => setViewingCert(d)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 px-3 py-1.5 text-xs font-semibold text-indigo-600 transition hover:bg-indigo-50 dark:border-indigo-700 dark:text-indigo-400 dark:hover:bg-indigo-900/30">
                          {ico('eye', 'h-3.5 w-3.5')} View
                        </button>
                        <button onClick={() => downloadCert(d.certificate!.code)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 px-3 py-1.5 text-xs font-semibold text-indigo-600 transition hover:bg-indigo-50 dark:border-indigo-700 dark:text-indigo-400 dark:hover:bg-indigo-900/30">
                          {ico('download', 'h-3.5 w-3.5')} Download
                        </button>
                      </>
                    ) : d.completed ? (
                      <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">Processing…</span>
                    ) : (
                      <div className="w-32">
                        <div className="mb-1 flex justify-between text-xs text-slate-500 dark:text-slate-400">
                          <span>Progress</span><span>{d.passed_levels}/{d.total_levels}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                          <div className="h-2 rounded-full bg-linear-to-r from-indigo-500 to-purple-500 transition-all"
                            style={{ width: `${d.total_levels > 0 ? Math.round(d.passed_levels / d.total_levels * 100) : 0}%` }} />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                {d.certificate && (
                  <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">ID: {d.certificate.code} · Issued {fmtDate(d.certificate.issued_at)}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Modals */}
      {viewingBadge && (
        <BadgeViewModal
          badge={viewingBadge}
          onClose={() => setViewingBadge(null)}
          onDownload={() => downloadBadge(viewingBadge.id, viewingBadge.domain_name, viewingBadge.level_number)}
        />
      )}
      {viewingCert?.certificate && (
        <CertViewModal
          domain={viewingCert}
          onClose={() => setViewingCert(null)}
          onDownload={() => downloadCert(viewingCert.certificate!.code)}
        />
      )}
    </div>
  )
}
