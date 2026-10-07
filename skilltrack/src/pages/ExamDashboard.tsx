import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api'
import Card from '../components/Card'
import { Icon, Logo } from '../components/AuthLayout'
import { authField } from '../components/authStyles'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../useFetch'

type Stage = 'details' | 'key' | 'test' | 'done'

interface Session {
  session_id: number
  level: { id: number; name: string; pass_mark: number }
  seconds_left: number
  server_time: string
  ends_at: string
  questions: { id: number; text: string; options: string[] }[]
}

interface Result {
  passed: boolean
  score: number
  correct: number
  total: number
  pass_mark: number
  attempt_no: number
  points_earned: number
  removed: boolean
  certificate: string | null
  new_semester: number | null
  late: boolean
  skill_gaps: { topic: string; score: number }[]
  topic_scores: { topic: string; score: number }[]
}

interface MySlot {
  id: number
  starts_at: string
  venue: string
  level_name: string
  domain_name: string
  seconds_until_start: number
}

/** After this many times leaving the exam window the test is submitted automatically. */
const MAX_VIOLATIONS = 3

const PATHS = {
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zM9 12l2 2 4-4',
  clock: 'M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  alert: 'M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z',
  key: 'M21 2l-2 2m-7.6 7.6a5.5 5.5 0 11-7.8 7.8 5.5 5.5 0 017.8-7.8zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4',
  user: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM4 21a8 8 0 0116 0',
  id: 'M4 6h16a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V7a1 1 0 011-1zM7 11h4M7 14h2M15 11h2',
  check: 'M5 13l4 4L19 7',
  expand: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5',
  copy: 'M9 9h10v10H9zM5 15V5h10',
  eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 100-6 3 3 0 000 6z',
  arrow: 'M5 12h14m-6-6l6 6-6 6',
}

const ico = (name: keyof typeof PATHS, className = 'h-4 w-4') => (
  <Icon className={className}><path strokeLinecap="round" strokeLinejoin="round" d={PATHS[name]} /></Icon>
)

const primaryBtn =
  'group inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-500 hover:shadow-indigo-500/40 active:translate-y-0 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none'

const RULES: { icon: ReactNode; title: string; text: string }[] = [
  { icon: ico('expand', 'h-5 w-5'), title: 'Full-screen lock', text: 'The exam opens in full screen. Leaving it is recorded.' },
  { icon: ico('eye', 'h-5 w-5'), title: 'No switching windows', text: `Alt-Tab or opening another tab is logged. After ${MAX_VIOLATIONS} warnings the exam is submitted automatically.` },
  { icon: ico('copy', 'h-5 w-5'), title: 'Copy & paste disabled', text: 'Copying, pasting, right-click and dev-tool shortcuts are blocked.' },
  { icon: ico('clock', 'h-5 w-5'), title: 'Timed test', text: 'The timer cannot be paused. Answers are submitted when time runs out.' },
]

function fmt(sec: number) {
  const s = Math.max(0, sec)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function fmtWait(sec: number) {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}

function Steps({ stage }: { stage: Stage }) {
  const idx = { details: 0, key: 1, test: 2, done: 3 }[stage]
  const labels = ['Your details', 'Exam key', 'Take the test']
  return (
    <ol className="flex items-center gap-2 sm:gap-3">
      {labels.map((l, i) => (
        <li key={l} className="flex items-center gap-2 sm:gap-3">
          <span className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${i < idx ? 'bg-emerald-500 text-white' : i === idx ? 'bg-white text-indigo-600 ring-4 ring-white/30' : 'bg-white/20 text-white/80'}`}>
            {i < idx ? ico('check') : i + 1}
          </span>
          <span className={`hidden text-sm font-medium sm:inline ${i === idx ? 'text-white' : 'text-white/70'}`}>{l}</span>
          {i < labels.length - 1 && <span className="h-px w-6 bg-white/30 sm:w-10" />}
        </li>
      ))}
    </ol>
  )
}

function ScoreRing({ score, passed }: { score: number; passed: boolean }) {
  const c = 2 * Math.PI * 52
  return (
    <div className="relative h-36 w-36 shrink-0">
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
        <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,.25)" strokeWidth="10" />
        <circle
          cx="60" cy="60" r="52" fill="none" stroke="#fff" strokeWidth="10" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - Math.min(100, score) / 100)} className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold">{score}%</span>
        <span className="text-xs font-semibold uppercase tracking-wide text-white/85">{passed ? 'Passed' : 'Not passed'}</span>
      </div>
    </div>
  )
}

interface ActiveDomainCheck {
  active_enrollment: { domain_id: number; domain_name: string } | null
  can_enroll: boolean
}

export default function ExamDashboard() {
  const { user } = useAuth()
  const [stage, setStage] = useState<Stage>('details')
  const domainCheck = useFetch<ActiveDomainCheck>('/domains?check_only=1')
  const [details, setDetails] = useState({ name: user?.name ?? '', regNo: user?.reg_no ?? '' })
  const [keyInput, setKeyInput] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [session, setSession] = useState<Session | null>(null)
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [violations, setViolations] = useState(0)
  const [warning, setWarning] = useState<string | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [mySlot, setMySlot] = useState<MySlot | null>(null)
  const [opensAt, setOpensAt] = useState<number | null>(null)
  const [serverTimeOffset, setServerTimeOffset] = useState(0) // Client time - Server time offset in ms
  const submitting = useRef(false)
  const away = useRef(false)

  // The student's booked slot: the exam can only be started once it opens (countdown uses the server's clock)
  useEffect(() => {
    api.get<MySlot | null>('/exam/my-slot')
      .then((res) => {
        setMySlot(res.data)
        if (res.data) setOpensAt(Date.now() + res.data.seconds_until_start * 1000)
      })
      .catch(() => {})
  }, [])

  const waitSeconds = opensAt === null ? 0 : Math.max(0, Math.ceil((opensAt - now) / 1000))
  const notYetOpen = waitSeconds > 0
  const startsTime = mySlot ? new Date(mySlot.starts_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : ''
  const startsDate = mySlot ? new Date(mySlot.starts_at).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }) : ''

  // Calculate remaining time based on server-provided end time
  const secondsLeft = session ? Math.max(0, Math.floor((new Date(session.ends_at).getTime() - (now - serverTimeOffset)) / 1000)) : 0

  useEffect(() => {
    if (stage !== 'test' && !notYetOpen) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [stage, notYetOpen])

  // Sync with server time every 30 seconds during exam to prevent clock drift/manipulation
  useEffect(() => {
    if (stage !== 'test' || !session) return
    const syncTime = async () => {
      try {
        const res = await api.get<{ server_time: string; ends_at: string }>(`/exam/sessions/${session.session_id}/time`)
        const clientTime = Date.now()
        const serverTime = new Date(res.data.server_time).getTime()
        setServerTimeOffset(clientTime - serverTime)
        // Update session end time in case of any discrepancies
        setSession({ ...session, ends_at: res.data.ends_at })
      } catch {
        // Silently fail - continue with existing offset
      }
    }
    const id = setInterval(syncTime, 30000) // Sync every 30 seconds
    return () => clearInterval(id)
  }, [stage, session])

  // Safe-exam lockdown: record every time the candidate leaves the exam window
  useEffect(() => {
    if (stage !== 'test') return
    // One "leave" can fire blur, visibilitychange and fullscreenchange together, so count it once
    let debounceTimer: NodeJS.Timeout | null = null
    const leave = (reason: string) => {
      if (away.current || submitting.current) return
      away.current = true

      // Clear any pending debounce to prevent multiple counts
      if (debounceTimer) clearTimeout(debounceTimer)

      setViolations((v) => {
        setWarning(reason)
        return v + 1
      })

      // Allow new violations after 1 second debounce
      debounceTimer = setTimeout(() => {
        away.current = false
        debounceTimer = null
      }, 1000)
    }
    const onVisibility = () => { if (document.hidden) leave('You switched to another tab or window.') }
    const onBlur = () => leave('The exam window lost focus (Alt-Tab or another app).')
    const onFullscreen = () => { if (!document.fullscreenElement) leave('You exited full-screen mode.') }
    const onKey = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase()
      const mod = e.ctrlKey || e.metaKey
      if (k === 'f12' || k === 'printscreen' || (mod && ['c', 'v', 'x', 'u', 'p', 's'].includes(k)) || (mod && e.shiftKey && ['i', 'j', 'c'].includes(k))) {
        e.preventDefault()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('blur', onBlur)
    document.addEventListener('fullscreenchange', onFullscreen)
    document.addEventListener('keydown', onKey)
    return () => {
      if (debounceTimer) clearTimeout(debounceTimer)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
      document.removeEventListener('fullscreenchange', onFullscreen)
      document.removeEventListener('keydown', onKey)
    }
  }, [stage])

  // Leave full screen if the page is closed mid-test
  useEffect(() => () => { if (document.fullscreenElement) document.exitFullscreen().catch(() => {}) }, [])

  async function startExam() {
    setBusy(true)
    setError('')
    try {
      const res = await api.post<Session>('/exam/start', { key: keyInput })
      const clientTime = Date.now()
      const serverTime = new Date(res.data.server_time).getTime()
      setServerTimeOffset(clientTime - serverTime) // Store offset for time calculations
      setNow(clientTime)
      setSession(res.data)
      setAnswers({})
      setViolations(0)
      setWarning(null)
      away.current = false
      submitting.current = false
      setStage('test')
      document.documentElement.requestFullscreen().catch(() => {})
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function submit() {
    if (!session || submitting.current) return
    submitting.current = true
    setBusy(true)
    try {
      const res = await api.post<Result>(`/exam/sessions/${session.session_id}/submit`, { answers, violations })
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
      setWarning(null)
      setResult(res.data)
      setStage('done')
    } catch (err) {
      setError(errorMessage(err, 'Could not submit. Try again.'))
      submitting.current = false
    } finally {
      setBusy(false)
    }
  }

  async function resume() {
    await document.documentElement.requestFullscreen().catch(() => {})
    away.current = false
    setWarning(null)
  }

  const expired = secondsLeft <= 0

  // Auto-submit when time runs out or too many warnings have been given
  useEffect(() => {
    if (stage !== 'test') return
    if (violations >= MAX_VIOLATIONS) { submit(); return }
    if (expired) {
      // Everyone's timer ends together, so spread the submits over a few seconds (the server allows a 2 minute grace)
      const id = setTimeout(submit, Math.random() * 4000)
      return () => clearTimeout(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, expired, violations])

  /* ---------- Exam (locked, full-window) ---------- */
  if (stage === 'test' && session) {
    const answered = Object.keys(answers).length
    const total = session.questions.length
    const lowTime = secondsLeft < 60
    return (
      <div
        className="fixed inset-0 z-50 select-none overflow-y-auto bg-slate-50 dark:bg-slate-950"
        onCopy={(e) => e.preventDefault()}
        onPaste={(e) => e.preventDefault()}
        onCut={(e) => e.preventDefault()}
        onContextMenu={(e) => e.preventDefault()}
      >
        <header className="sticky top-0 z-10 border-b border-white/10 bg-slate-950/80 text-white shadow-lg backdrop-blur-lg">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="flex items-center gap-3">
              <Logo />
              <span className="hidden items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-xs font-semibold sm:inline-flex">
                {ico('shield')} Safe exam mode
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 ${violations ? 'bg-red-500' : 'bg-white/20'}`}>
                {ico('alert')} Warnings {violations}/{MAX_VIOLATIONS}
              </span>
              <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-mono ${lowTime ? 'animate-pulse bg-red-500' : 'bg-white/20'}`}>
                {ico('clock')} {fmt(secondsLeft)}
              </span>
            </div>
          </div>
          <div className="h-1 bg-white/20">
            <div className="h-full bg-emerald-300 transition-all duration-500" style={{ width: `${total ? (answered / total) * 100 : 0}%` }} />
          </div>
        </header>

        <div className={`mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[1fr_16rem] ${warning ? 'pointer-events-none blur-md' : ''}`}>
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{session.level.name}</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">Pass mark {session.level.pass_mark}% · {total} questions</p>
            </div>

            {session.questions.map((q, i) => (
              <section key={q.id} id={`q-${q.id}`} className="scroll-mt-28 rounded-2xl border border-slate-100 bg-white p-5 shadow-lg shadow-indigo-100/40 dark:border-slate-700 dark:bg-slate-900 dark:shadow-slate-950/40">
                <div className="mb-4 flex items-start gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-sm font-bold text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-400">{i + 1}</span>
                  <p className="pt-1 text-sm font-semibold text-slate-800 dark:text-slate-100">{q.text}</p>
                </div>
                <div className="space-y-2">
                  {q.options.map((opt, idx) => {
                    const picked = answers[q.id] === idx
                    return (
                      <label
                        key={opt}
                        className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition ${picked ? 'border-indigo-500 bg-indigo-50 font-medium text-indigo-900 ring-4 ring-indigo-100 dark:border-indigo-500 dark:bg-indigo-900/30 dark:text-indigo-200 dark:ring-indigo-900/60' : 'border-slate-200 hover:border-indigo-300 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:border-indigo-600 dark:hover:bg-slate-800'}`}
                      >
                        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${picked ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 dark:border-slate-600'}`}>
                          {picked && ico('check', 'h-3 w-3')}
                        </span>
                        <input className="sr-only" type="radio" name={`q${q.id}`} checked={picked} onChange={() => setAnswers({ ...answers, [q.id]: idx })} />
                        {opt}
                      </label>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>

          <aside className="lg:sticky lg:top-24 lg:self-start">
            <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-lg shadow-indigo-100/40 dark:border-slate-700 dark:bg-slate-900 dark:shadow-slate-950/40">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Question palette</p>
              <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">{answered} of {total} answered</p>
              <div className="grid grid-cols-5 gap-2">
                {session.questions.map((q, i) => (
                  <button
                    key={q.id} type="button"
                    onClick={() => document.getElementById(`q-${q.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })}
                    className={`h-9 rounded-lg text-xs font-bold transition hover:-translate-y-0.5 ${answers[q.id] !== undefined ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-400 dark:hover:bg-slate-600'}`}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
              {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">{error}</p>}
              <button disabled={busy} onClick={submit} className="mt-4 w-full group inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-500 hover:shadow-indigo-500/40 active:translate-y-0 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none">
                {busy ? 'Submitting…' : 'Submit answers'}
              </button>
            </div>
          </aside>
        </div>

        {warning && (
          <div role="alertdialog" aria-modal="true" className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/85 p-4 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-3xl bg-white p-8 text-center shadow-2xl">
              <span className="mx-auto flex h-16 w-16 animate-pulse items-center justify-center rounded-full bg-red-100 text-red-600">{ico('alert', 'h-8 w-8')}</span>
              <h2 className="mt-4 text-2xl font-bold text-slate-900">Warning {Math.min(violations, MAX_VIOLATIONS)} of {MAX_VIOLATIONS}</h2>
              <p className="mt-2 text-sm text-slate-600">{warning}</p>
              <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm font-medium text-red-700">
                {violations >= MAX_VIOLATIONS
                  ? 'Too many warnings. Your exam is being submitted.'
                  : `Your invigilator is notified. ${MAX_VIOLATIONS - violations} more and your exam is submitted automatically.`}
              </p>
              {violations < MAX_VIOLATIONS && (
                <button onClick={resume} className={`${primaryBtn} mt-6 w-full`}>Return to exam {ico('expand')}</button>
              )}
            </div>
          </div>
        )}
      </div>
    )
  }

  /* ---------- Pre-exam and result screens ---------- */

  // Active-domain check for the pre-exam screens only
  const hasActiveDomain = domainCheck.data?.active_enrollment != null
  const noActiveDomain = !domainCheck.loading && domainCheck.data != null && !hasActiveDomain && stage !== 'done'

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {noActiveDomain && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
          <p className="font-semibold text-base">No active domain</p>
          <p className="mt-1">You must be enrolled in a domain to take the examination.</p>
          <Link to="/student/domains" className="mt-3 inline-flex items-center gap-1 rounded-lg bg-amber-700 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600">
            Enroll in a Domain →
          </Link>
        </div>
      )}
      <section className="relative overflow-hidden rounded-3xl bg-slate-950 p-6 text-white shadow-2xl sm:p-10">
        <div className="pointer-events-none absolute -right-20 -top-20 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/4 h-96 w-96 rounded-full bg-purple-600/20 blur-3xl" />
        <div className="relative">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium">{ico('shield')} Safe exam mode</span>
          <h1 className="mt-3 text-3xl font-bold">{stage === 'done' ? 'Your result' : 'Take your exam'}</h1>
          <p className="mt-1 text-sm text-gray-400">{stage === 'done' ? 'Here is how you did.' : 'Follow the steps below. The test runs in a locked, full-screen window.'}</p>
          {stage !== 'done' && <div className="mt-5"><Steps stage={stage} /></div>}
        </div>
      </section>

      {mySlot && (stage === 'details' || stage === 'key') && (
        <section className={`flex flex-wrap items-center gap-4 rounded-2xl border p-4 ${notYetOpen ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50'}`}>
          <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-white ${notYetOpen ? 'bg-amber-500' : 'bg-emerald-500'}`}>{ico('clock', 'h-6 w-6')}</span>
          <div className="min-w-0 flex-1">
            <p className={`text-sm font-semibold ${notYetOpen ? 'text-amber-900' : 'text-emerald-900'}`}>
              {notYetOpen ? `Your exam starts at ${startsTime} on ${startsDate}` : 'Your slot is open. You can start your exam now.'}
            </p>
            <p className="text-xs text-slate-600">{mySlot.domain_name} · {mySlot.level_name} · {mySlot.venue}{!notYetOpen && ` · started ${startsTime}`}</p>
          </div>
          {notYetOpen && (
            <div className="text-right">
              <p className="font-mono text-2xl font-bold text-amber-800">{fmtWait(waitSeconds)}</p>
              <p className="text-xs text-amber-700">until your exam opens</p>
            </div>
          )}
        </section>
      )}

      {stage === 'details' && (
        <div className="grid gap-6 md:grid-cols-[1.1fr_1fr]">
          <Card title="Confirm your details" icon={ico('user')}>
            <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); setStage('key') }}>
              <label className="block">
                <span className="mb-1.5 block text-sm font-semibold text-slate-800">Full name</span>
                <div className="relative">
                  <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-slate-400">{ico('user')}</span>
                  <input required placeholder="Full name" value={details.name} onChange={(e) => setDetails({ ...details, name: e.target.value })} className={authField} />
                </div>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-semibold text-slate-800">Register number</span>
                <div className="relative">
                  <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-slate-400">{ico('id')}</span>
                  <input required placeholder="Register number" value={details.regNo} onChange={(e) => setDetails({ ...details, regNo: e.target.value })} className={authField} />
                </div>
              </label>
              <button className={primaryBtn}>Continue {ico('arrow', 'h-4 w-4 transition group-hover:translate-x-1')}</button>
            </form>
          </Card>
          <RulesCard />
        </div>
      )}

      {stage === 'key' && (
        <div className="grid gap-6 md:grid-cols-[1.1fr_1fr]">
          <Card title="Enter exam key" icon={ico('key')}>
            <p className="mb-4 text-sm text-slate-600">Hi <span className="font-semibold">{details.name}</span>. Enter the key given by your invigilator. Keys are valid for a limited time.</p>
            <div className="relative">
              <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-slate-400">{ico('key')}</span>
              <input value={keyInput} disabled={notYetOpen} onChange={(e) => setKeyInput(e.target.value)} placeholder="SKL-0000" className={`${authField} font-mono uppercase tracking-widest disabled:bg-slate-50 disabled:text-slate-400`} />
            </div>
            <button disabled={busy || notYetOpen || !keyInput.trim()} onClick={startExam} className={`${primaryBtn} mt-4 w-full`}>
              {busy ? 'Checking…' : notYetOpen ? `Opens at ${startsTime}` : <>Start exam {ico('arrow', 'h-4 w-4 transition group-hover:translate-x-1')}</>}
            </button>
            {error && (
              <p role="alert" className="mt-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{ico('alert', 'mt-0.5 h-4 w-4 shrink-0')}{error}</p>
            )}
            <p className="mt-3 text-xs text-slate-500">If your key stops working because of a network issue, ask the invigilator to issue a new one in person.</p>
            <button onClick={() => setStage('details')} className="mt-2 text-xs font-semibold text-indigo-600 hover:underline">← Back</button>
          </Card>
          <RulesCard />
        </div>
      )}

      {stage === 'done' && result && (
        <>
          <section className={`flex flex-col items-center gap-6 rounded-3xl p-6 text-white shadow-sm sm:flex-row sm:p-8 ${result.passed ? 'bg-emerald-600' : 'bg-rose-600'}`}>
            <ScoreRing score={result.score} passed={result.passed} />
            <div className="text-center sm:text-left">
              <h2 className="text-2xl font-bold">{result.passed ? 'Congratulations, you passed! 🎉' : 'Not passed this time'}</h2>
              <p className="mt-1 text-sm text-white/90">
                {result.correct} of {result.total} correct · pass mark {result.pass_mark}% · attempt {result.attempt_no}
              </p>
              {result.passed && (
                <p className="mt-2 text-sm text-white/90">
                  +{result.points_earned} points{result.attempt_no === 1 && ' and a first-attempt badge 🏅'} · certificate {result.certificate} issued · next level unlocked.
                </p>
              )}
            </div>
          </section>

          {(result.late || result.new_semester || result.removed) && (
            <div className="space-y-3">
              {result.late && <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">Submitted after the time limit, so answers were not counted.</p>}
              {result.new_semester && (
                <p className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-700">
                  🎉 You have moved up to <strong>Semester {result.new_semester}</strong>.
                  {result.new_semester >= 3 ? ' Domain selection is now open on your dashboard.' : ' Your next common test is now available.'}
                </p>
              )}
              {result.removed && <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">You have used all attempts and have been removed from this domain.</p>}
            </div>
          )}

          <div className="grid gap-6 md:grid-cols-2">
            {result.topic_scores.length > 1 && (
              <Card title="Scores by section" icon={ico('check')}>
                <ul className="space-y-3">
                  {result.topic_scores.map((t) => (
                    <li key={t.topic} className="text-sm">
                      <div className="flex justify-between font-medium"><span>{t.topic}</span><span>{t.score}%</span></div>
                      <div className="mt-1.5 h-2 rounded-full bg-slate-100">
                        <div className={`h-2 rounded-full ${t.score >= 60 ? 'bg-emerald-500' : 'bg-rose-500'}`} style={{ width: `${t.score}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            {result.skill_gaps.length > 0 && (
              <Card title="Topics to improve" icon={ico('alert')}>
                <ul className="space-y-2 text-sm">
                  {result.skill_gaps.map((g) => (
                    <li key={g.topic} className="flex justify-between rounded-lg bg-red-50 px-3 py-2"><span className="font-medium text-slate-800">{g.topic}</span><span className="font-semibold text-red-600">{g.score}%</span></li>
                  ))}
                </ul>
              </Card>
            )}
          </div>

          <Link to="/student" className={primaryBtn}>Back to dashboard {ico('arrow', 'h-4 w-4 transition group-hover:translate-x-1')}</Link>
        </>
      )}
    </div>
  )
}

function RulesCard() {
  return (
    <Card title="Exam rules" icon={ico('shield')}>
      <ul className="space-y-3">
        {RULES.map((r) => (
          <li key={r.title} className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">{r.icon}</span>
            <div>
              <p className="text-sm font-semibold text-slate-800">{r.title}</p>
              <p className="text-xs text-slate-500">{r.text}</p>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
