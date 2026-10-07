import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errorMessage } from '../api'
import Card from '../components/Card'
import { Icon } from '../components/AuthLayout'

// ── Types ─────────────────────────────────────────────────────────────────────

interface DomainItem {
  id: number
  name: string
  description: string | null
  difficulty: 'beginner' | 'intermediate' | 'advanced' | null
  level_count: number
  topic_count: number
  total_duration_min: number
  enrollment_status: 'active' | 'completed' | 'removed' | null
  passed_levels: number
  progress_pct: number
}

interface DomainsResponse {
  domains: DomainItem[]
  active_enrollment: { domain_id: number; domain_name: string } | null
  can_enroll: boolean
  points_to_unlock: number
  student_points: number
  points_unlocked: boolean
}

interface LevelDetail {
  id: number
  number: number
  name: string
  pass_mark: number
  duration_min: number
  question_count: number
  status: 'completed' | 'current' | 'locked'
  topics: string[]
}

interface DomainDetail {
  id: number
  name: string
  description: string | null
  difficulty: string | null
  level_count: number
  topic_count: number
  total_duration_min: number
  levels: LevelDetail[]
  enrollment_status: string | null
  active_enrollment: { domain_id: number; domain_name: string } | null
  can_enroll: boolean
  points_to_unlock: number
  student_points: number
  points_unlocked: boolean
}

// ── Icon paths ────────────────────────────────────────────────────────────────

const PATHS = {
  search: 'M21 21l-5.2-5.2M17 11A6 6 0 115 11a6 6 0 0112 0z',
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  check: 'M5 13l4 4L19 7',
  lock: 'M16 11V7a4 4 0 00-8 0v4M6 11h12a1 1 0 011 1v8a1 1 0 01-1 1H6a1 1 0 01-1-1v-8a1 1 0 011-1z',
  clock: 'M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  book: 'M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2V5zM4 19a2 2 0 002 2h13',
  layers: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
  x: 'M6 18L18 6M6 6l12 12',
  star: 'M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z',
  arrow: 'M5 12h14m-6-6l6 6-6 6',
  ribbon: 'M12 14a6 6 0 100-12 6 6 0 000 12zM8.5 13L7 22l5-3 5 3-1.5-9',
  info: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
}

const ico = (name: keyof typeof PATHS, cls = 'h-4 w-4') => (
  <Icon className={cls}><path strokeLinecap="round" strokeLinejoin="round" d={PATHS[name]} /></Icon>
)

// ── Helpers ───────────────────────────────────────────────────────────────────

const DIFF_STYLE: Record<string, string> = {
  beginner:     'bg-emerald-100 text-emerald-700',
  intermediate: 'bg-amber-100 text-amber-700',
  advanced:     'bg-red-100 text-red-700',
}

const ENROLL_STYLE: Record<string, string> = {
  active:    'bg-indigo-100 text-indigo-700',
  completed: 'bg-emerald-100 text-emerald-700',
  removed:   'bg-red-100 text-red-700',
}

const LEVEL_STATUS_DOT: Record<string, string> = {
  completed: 'bg-emerald-500 text-white',
  current:   'bg-indigo-600 text-white ring-4 ring-indigo-500/20',
  locked:    'border-2 border-slate-200 bg-white text-slate-400 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-500',
}

function fmtDuration(min: number) {
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m ? `${h}h ${m}m` : `${h}h`
}

const primaryBtn =
  'inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-500 hover:shadow-indigo-500/40 active:translate-y-0 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none'

// ── Domain Detail Modal ───────────────────────────────────────────────────────

function DomainModal({
  domainId,
  onClose,
  onEnroll,
}: {
  domainId: number
  onClose: () => void
  onEnroll: (id: number, name: string) => void
}) {
  const [detail, setDetail] = useState<DomainDetail | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get<DomainDetail>(`/domains/${domainId}`)
      .then((r) => setDetail(r.data))
      .catch((e) => setErr(errorMessage(e)))
  }, [domainId])

  const canEnroll =
    detail &&
    detail.can_enroll &&
    detail.points_unlocked &&
    !detail.enrollment_status &&
    !detail.active_enrollment

  const blocked = detail?.active_enrollment && detail.active_enrollment.domain_id !== domainId
  const needsPoints = detail && detail.can_enroll && !detail.points_unlocked && !detail.enrollment_status && !detail.active_enrollment

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-3xl bg-white shadow-2xl dark:bg-slate-900">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white px-6 py-4 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">{detail?.name ?? 'Loading…'}</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700">{ico('x', 'h-5 w-5')}</button>
        </div>

        <div className="p-6 space-y-6">
          {err && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-600">{err}</p>}

          {!detail && !err && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
              Loading…
            </div>
          )}

          {detail && (
            <>
              {/* Meta */}
              <div className="flex flex-wrap gap-2 text-xs font-semibold">
                {detail.difficulty && (
                  <span className={`rounded-full px-3 py-1 capitalize ${DIFF_STYLE[detail.difficulty] ?? 'bg-slate-100 text-slate-600'}`}>
                    {detail.difficulty}
                  </span>
                )}
                <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">{detail.level_count} levels</span>
                {detail.topic_count > 0 && (
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">{detail.topic_count} topics</span>
                )}
                {detail.enrollment_status && (
                  <span className={`rounded-full px-3 py-1 capitalize ${ENROLL_STYLE[detail.enrollment_status] ?? 'bg-slate-100'}`}>
                    {detail.enrollment_status}
                  </span>
                )}
              </div>

              {detail.description && (
                <p className="text-sm text-slate-600 dark:text-slate-300">{detail.description}</p>
              )}

              {/* Levels */}
              <div>
                <h3 className="mb-3 text-sm font-semibold text-slate-800">Levels</h3>
                <ul className="space-y-3">
                  {detail.levels.map((lv) => (
                    <li key={lv.id} className={`rounded-xl border p-3 ${lv.status === 'current' ? 'border-indigo-200 bg-indigo-50/50 dark:border-indigo-800/60 dark:bg-indigo-900/20' : 'border-slate-100 dark:border-slate-700'}`}>
                      <div className="flex items-center gap-3">
                        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${LEVEL_STATUS_DOT[lv.status]}`}>
                          {lv.status === 'completed' ? ico('check', 'h-4 w-4') : lv.status === 'locked' ? ico('lock', 'h-3.5 w-3.5') : lv.number}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">{lv.name}</div>
                          <div className="mt-0.5 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                            <span>{lv.question_count} questions</span>
                            <span>·</span>
                            <span>Pass: {lv.pass_mark}%</span>
                            <span>·</span>
                            <span>{fmtDuration(lv.duration_min)}</span>
                          </div>
                          {lv.topics.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {lv.topics.map((t) => (
                                <span key={t} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{t}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Enroll / blocked message */}
              {blocked && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                  {ico('info', 'inline-block h-4 w-4 mr-1 align-text-bottom')}
                  You are currently enrolled in <strong>{detail.active_enrollment!.domain_name}</strong>.
                  Complete that domain before enrolling in a new one.
                </div>
              )}

              {detail.enrollment_status === 'completed' && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                  {ico('ribbon', 'inline-block h-4 w-4 mr-1 align-text-bottom')}
                  You have completed this domain.
                </div>
              )}

              {!detail.can_enroll && (
                <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-500">
                  Domain enrollment opens in Semester 3.
                </p>
              )}

              {needsPoints && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 space-y-1.5">
                  {ico('star', 'inline-block h-4 w-4 mr-1 align-text-bottom')}
                  <span className="font-semibold">Points required to unlock this domain</span>
                  <div className="mt-2">
                    <div className="mb-1 flex justify-between text-xs">
                      <span>Your points</span>
                      <span className="font-semibold">{detail.student_points} / {detail.points_to_unlock}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-amber-100">
                      <div
                        className="h-2 rounded-full bg-amber-400 transition-all"
                        style={{ width: `${Math.min(100, Math.round(detail.student_points / detail.points_to_unlock * 100))}%` }}
                      />
                    </div>
                    <p className="mt-1.5 text-xs">Earn {detail.points_to_unlock - detail.student_points} more points to unlock your next domain.</p>
                  </div>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
                  Close
                </button>
                {canEnroll && (
                  <button
                    onClick={() => { onEnroll(detail.id, detail.name); onClose() }}
                    className={primaryBtn}
                  >
                    Enroll in Domain
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Domain Card ───────────────────────────────────────────────────────────────

function DomainCard({
  domain,
  activeEnrollment,
  canEnroll,
  pointsUnlocked,
  onView,
  onEnroll,
  enrolling,
}: {
  domain: DomainItem
  activeEnrollment: { domain_id: number; domain_name: string } | null
  canEnroll: boolean
  pointsUnlocked: boolean
  onView: (id: number) => void
  onEnroll: (id: number, name: string) => void
  enrolling: number | null
}) {
  const isActive = domain.enrollment_status === 'active'
  const isCompleted = domain.enrollment_status === 'completed'
  const isEnrolled = !!domain.enrollment_status
  const blocked = !isEnrolled && !!activeEnrollment
  const needsPoints = !isEnrolled && !blocked && canEnroll && !pointsUnlocked

  return (
    <div className={`flex flex-col rounded-2xl border bg-white shadow-sm transition hover:shadow-md dark:bg-slate-900 dark:hover:shadow-slate-950/60 ${isActive ? 'border-indigo-200 ring-1 ring-inset ring-indigo-200 dark:border-indigo-800 dark:ring-indigo-800' : 'border-slate-100 dark:border-slate-700'}`}>
      {/* Header */}
      <div className={`flex items-center justify-between rounded-t-2xl px-4 py-3 ${isCompleted ? 'bg-emerald-50 dark:bg-emerald-900/20' : isActive ? 'bg-indigo-50/60 dark:bg-indigo-900/20' : 'bg-slate-50 dark:bg-slate-800'}`}>
        <div className="flex items-center gap-2">
          <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg font-bold ${isCompleted ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' : isActive ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300' : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'}`}>
            {domain.name.charAt(0)}
          </span>
          <div className="min-w-0">
            <div className="text-sm font-bold text-slate-900 truncate dark:text-white">{domain.name}</div>
            {domain.difficulty && (
              <span className={`text-xs font-semibold capitalize ${DIFF_STYLE[domain.difficulty] ? '' : 'text-slate-500'}`} style={{ color: 'inherit' }}>
                <span className={`rounded-full px-2 py-0.5 ${DIFF_STYLE[domain.difficulty] ?? 'bg-slate-100 text-slate-500'}`}>{domain.difficulty}</span>
              </span>
            )}
          </div>
        </div>
        {isCompleted && (
          <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">{ico('check', 'inline-block h-3 w-3 mr-0.5')}Done</span>
        )}
        {isActive && (
          <span className="shrink-0 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700">Active</span>
        )}
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col gap-3 p-4">
        {domain.description ? (
          <p className="text-xs text-slate-500 line-clamp-2 dark:text-slate-400">{domain.description}</p>
        ) : (
          <p className="text-xs text-slate-400 italic dark:text-slate-500">No description yet.</p>
        )}

        <div className="flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1">{ico('layers', 'h-3.5 w-3.5')}{domain.level_count} levels</span>
          {domain.topic_count > 0 && <span className="flex items-center gap-1">{ico('book', 'h-3.5 w-3.5')}{domain.topic_count} topics</span>}
        </div>

        {/* Progress bar (if enrolled) */}
        {isEnrolled && domain.level_count > 0 && (
          <div>
            <div className="mb-1 flex justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Progress</span><span>{domain.passed_levels}/{domain.level_count}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
              <div
                className={`h-2 rounded-full transition-all ${isCompleted ? 'bg-emerald-500' : 'bg-linear-to-r from-indigo-500 to-purple-500'}`}
                style={{ width: `${domain.progress_pct}%` }}
              />
            </div>
          </div>
        )}

        {/* Blocked message */}
        {blocked && (
          <p className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-700">
            Already enrolled in <strong>{activeEnrollment!.domain_name}</strong>. Complete that domain first.
          </p>
        )}

        {/* Points-lock message */}
        {needsPoints && (
          <p className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-700">
            {ico('lock', 'inline-block h-3.5 w-3.5 mr-1 align-text-bottom')}
            Earn more points to unlock domain selection.
          </p>
        )}
      </div>

      {/* Footer actions */}
      <div className="flex gap-2 border-t border-slate-100 p-3 dark:border-slate-700">
        <button
          onClick={() => onView(domain.id)}
          className="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          View Domain
        </button>
        {!isEnrolled && canEnroll && !blocked && pointsUnlocked && (
          <button
            disabled={enrolling === domain.id}
            onClick={() => onEnroll(domain.id, domain.name)}
            className={`flex-1 rounded-xl ${primaryBtn} text-xs px-3 py-2`}
          >
            {enrolling === domain.id ? 'Enrolling…' : 'Enroll'}
          </button>
        )}
        {(blocked || needsPoints) && (
          <button
            disabled
            title={blocked ? `Complete ${activeEnrollment!.domain_name} first` : 'Earn more points to unlock'}
            className="flex-1 rounded-xl border border-slate-100 px-3 py-2 text-xs font-semibold text-slate-300 cursor-not-allowed"
          >
            {ico('lock', 'inline-block h-3 w-3 mr-1 align-text-bottom')} Locked
          </button>
        )}
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function DomainsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<DomainsResponse | null>(null)
  const [loadErr, setLoadErr] = useState('')
  const [actionErr, setActionErr] = useState('')
  const [actionOk, setActionOk] = useState('')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [viewingId, setViewingId] = useState<number | null>(null)
  const [enrolling, setEnrolling] = useState<number | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Debounce search input (300 ms)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [search])

  const load = useCallback(async () => {
    try {
      const res = await api.get<DomainsResponse>('/domains', {
        params: debouncedSearch ? { search: debouncedSearch } : {},
      })
      setData(res.data)
      setLoadErr('')
    } catch (e) {
      setLoadErr(errorMessage(e, 'Could not load domains'))
    }
  }, [debouncedSearch])

  useEffect(() => { load() }, [load])

  async function handleEnroll(domainId: number, domainName: string) {
    setActionErr('')
    setActionOk('')
    setEnrolling(domainId)
    try {
      await api.post('/enrollments', { domain_id: domainId })
      setActionOk(`Successfully enrolled in ${domainName}.`)
      await load()
    } catch (e) {
      setActionErr(errorMessage(e))
    } finally {
      setEnrolling(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="relative overflow-hidden rounded-3xl bg-slate-950 p-6 text-white shadow-2xl sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-20 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/4 h-96 w-96 rounded-full bg-purple-600/20 blur-3xl" />
        <div className="relative">
          <h1 className="text-3xl font-bold">Explore Domains</h1>
          <p className="mt-1 text-sm text-slate-400">Browse skill tracks, see what each covers, and enroll in one to start earning points and badges.</p>
          {data?.active_enrollment && (
            <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-indigo-500/20 px-4 py-2 text-sm font-semibold text-indigo-200">
              {ico('star', 'h-4 w-4')} Currently enrolled: {data.active_enrollment.domain_name}
            </div>
          )}
          {data && !data.active_enrollment && data.can_enroll && (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              {data.student_points >= data.points_to_unlock ? (
                <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/20 px-4 py-2 text-sm font-semibold text-emerald-200">
                  {ico('check', 'h-4 w-4')} Domain unlocked — choose any track below!
                </div>
              ) : data.student_points > 0 ? (
                <div className="inline-flex items-center gap-3 rounded-2xl bg-white/10 px-4 py-2 text-sm">
                  <span className="text-white/70">{ico('lock', 'h-4 w-4')}</span>
                  <div>
                    <span className="font-semibold text-white">Points to unlock: </span>
                    <span className="text-white/80">{data.student_points} / {data.points_to_unlock}</span>
                  </div>
                  <div className="w-24 h-2 rounded-full bg-white/20 overflow-hidden">
                    <div
                      className="h-2 rounded-full bg-indigo-400 transition-all"
                      style={{ width: `${Math.min(100, Math.round(data.student_points / data.points_to_unlock * 100))}%` }}
                    />
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </section>

      {/* Alerts */}
      {actionOk && (
        <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {ico('check', 'inline-block h-4 w-4 mr-1 align-text-bottom text-emerald-500')} {actionOk}
          {' '}<button onClick={() => navigate('/student')} className="font-semibold underline text-emerald-800 ml-1">Go to Dashboard</button>
        </p>
      )}
      {actionErr && (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{actionErr}</p>
      )}

      {/* Search */}
      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-slate-400">{ico('search', 'h-5 w-5')}</span>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search domains…"
          className="w-full rounded-2xl border border-slate-200 bg-white py-3 pl-11 pr-4 text-sm text-slate-800 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:border-indigo-500 dark:focus:ring-indigo-900/40"
        />
      </div>

      {/* States */}
      {loadErr && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">{loadErr}</p>
      )}

      {!data && !loadErr && (
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
          Loading domains…
        </div>
      )}

      {data && data.domains.length === 0 && (
        <Card title="">
          <p className="py-6 text-center text-sm text-slate-500">
            No domains found{debouncedSearch ? ` matching "${debouncedSearch}"` : ''}.
          </p>
        </Card>
      )}

      {/* Domain grid */}
      {data && data.domains.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.domains.map((d) => (
            <DomainCard
              key={d.id}
              domain={d}
              activeEnrollment={data.active_enrollment}
              canEnroll={data.can_enroll}
              pointsUnlocked={data.points_unlocked}
              onView={setViewingId}
              onEnroll={handleEnroll}
              enrolling={enrolling}
            />
          ))}
        </div>
      )}

      {/* Domain detail modal */}
      {viewingId !== null && (
        <DomainModal
          domainId={viewingId}
          onClose={() => setViewingId(null)}
          onEnroll={handleEnroll}
        />
      )}
    </div>
  )
}
