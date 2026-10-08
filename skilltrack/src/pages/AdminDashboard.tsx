import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, errorMessage } from '../api'
import { useAuth } from '../context/AuthContext'
import Card from '../components/Card'
import { Icon } from '../components/AuthLayout'
import QuestionBank from '../components/QuestionBank'
import SlotManager from '../components/SlotManager'
import StatTile from '../components/StatTile'
import { inputClass, primaryBtn } from '../components/authStyles'

// Chart palette: indigo + pink, matching the app's gradient
const INDIGO = '#6366f1'
const PINK = '#ec4899'
const GRID = '#e2e8f0'
const INK = '#64748b'
const TOOLTIP = { borderRadius: 12, border: 'none', boxShadow: '0 10px 25px rgba(99,102,241,.2)', fontSize: 12 }

const SEMESTERS = [1, 2, 3, 4, 5, 6]

interface Overview {
  kpis: { students: number; pass_rate: number | null; certificates: number; tests_this_month: number }
  domain_performance: { domain: string; avg: number | null; attempts: number }[]
  semester_results: { sem: string; pass: number; fail: number }[]
  skill_gaps: { topic: string; students: number }[]
}

type StudentStatus = 'Active' | 'At risk' | 'Removed' | 'Completed' | 'Cleared' | 'Not enrolled'

interface StudentRow {
  id: number
  name: string
  reg_no: string | null
  department: string | null
  semester: number | null
  domain: string | null
  attempts: number
  certificates: number
  status: StudentStatus
  cleared: boolean | null
}

interface StudentsResponse { students: StudentRow[]; departments: string[]; domains: string[] }
interface ActivityRow { id: number; action: string; created_at: string }
interface StaffRow { id: number; name: string; email: string; role: string; is_active: boolean }
interface DomainsResponse {
  domains: { id: number; name: string; owner_id: number | null; students: number; levels: number }[]
  owners: { id: number; name: string }[]
}
interface Settings {
  max_attempts: number
  points_to_unlock: number
  first_attempt_points: number
  retry_points: number
  key_minutes: number
}

const STATUS_STYLE: Record<StudentStatus, string> = {
  Active: 'bg-emerald-100 text-emerald-700',
  'At risk': 'bg-amber-100 text-amber-700',
  Removed: 'bg-red-100 text-red-700',
  Completed: 'bg-indigo-100 text-indigo-700',
  Cleared: 'bg-emerald-100 text-emerald-700',
  'Not enrolled': 'bg-slate-100 text-slate-500',
}

const ROLE_STYLE: Record<string, string> = {
  admin: 'bg-fuchsia-100 text-fuchsia-700',
  owner: 'bg-indigo-100 text-indigo-700',
  invigilator: 'bg-sky-100 text-sky-700',
}

const TABS = ['Users', 'Domains', 'Slots', 'Questions', 'Promote', 'Assign', 'Settings'] as const

const PATHS = {
  users: 'M16 11a3 3 0 100-6 3 3 0 000 6zM8 11a3 3 0 100-6 3 3 0 000 6zM2 20a6 6 0 0112 0M14 14.5A6 6 0 0122 20',
  pass: 'M5 13l4 4L19 7',
  ribbon: 'M12 14a6 6 0 100-12 6 6 0 000 12zM8.5 13L7 22l5-3 5 3-1.5-9',
  test: 'M9 5H6a1 1 0 00-1 1v14a1 1 0 001 1h12a1 1 0 001-1V6a1 1 0 00-1-1h-3M9 5a2 2 0 012-2h2a2 2 0 012 2v0a2 2 0 01-2 2h-2a2 2 0 01-2-2zM9 13l2 2 4-4',
  chart: 'M4 20V10M10 20V4M16 20v-8M22 20H2',
  alert: 'M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z',
  pulse: 'M3 12h4l3-8 4 16 3-8h4',
  cap: 'M12 3L2 8l10 5 10-5-10-5zM6 10.5V15c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5',
  cog: 'M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z',
}

const ico = (name: keyof typeof PATHS, className = 'h-4 w-4') => (
  <Icon className={className}><path strokeLinecap="round" strokeLinejoin="round" d={PATHS[name]} /></Icon>
)

const short = (name: string) => (name.length > 13 ? `${name.slice(0, 12)}…` : name)
const initial = (name: string) => name.trim().charAt(0).toUpperCase()

function Avatar({ name }: { name: string }) {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-xs font-bold text-indigo-700 ring-1 ring-inset ring-indigo-600/20">
      {initial(name)}
    </span>
  )
}

function Status({ status }: { status: StudentStatus }) {
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLE[status]}`}>{status}</span>
}

function Empty({ children }: { children: string }) {
  return <p className="rounded-xl bg-slate-50 px-3 py-3 text-center text-sm text-slate-500">{children}</p>
}

function ErrorNote({ text }: { text: string }) {
  return <p role="alert" className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-600">{text}</p>
}

function Message({ message }: { message: { ok: boolean; text: string } | null }) {
  if (!message) return null
  return <span className={`text-sm font-medium ${message.ok ? 'text-emerald-600' : 'text-red-600'}`}>{message.text}</span>
}

const thClass = 'pb-3 text-xs font-semibold uppercase tracking-wide text-slate-400'

function Filter({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: (string | number)[]
}) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className={inputClass}>
      <option value="">All {label}</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}

function ManageUsers() {
  const { user: currentUser } = useAuth()
  const [staff, setStaff] = useState<StaffRow[]>([])
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'invigilator' })
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setStaff((await api.get<StaffRow[]>('/admin/users')).data)
  }, [])
  useEffect(() => { load().catch((err) => setError(errorMessage(err))) }, [load])

  async function create(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/admin/users', form)
      setForm({ name: '', email: '', password: '', role: 'invigilator' })
      await load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function toggle(u: StaffRow) {
    setError('')
    try {
      await api.patch(`/admin/users/${u.id}`, { is_active: !u.is_active })
      await load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <ul className="space-y-2">
        {staff.map((u) => (
          <li key={u.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3 text-sm transition hover:shadow-md">
            <div className="flex min-w-0 items-center gap-3">
              <Avatar name={u.name} />
              <div className="min-w-0">
                <div className={`font-semibold ${u.is_active ? '' : 'text-slate-400 line-through'}`}>{u.name}</div>
                <div className="truncate text-xs text-slate-500">{u.email}</div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${ROLE_STYLE[u.role] ?? 'bg-slate-100 text-slate-600'}`}>{u.role}</span>
              {u.id === currentUser?.id ? (
                <span className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-400" title="You cannot deactivate your own account">You</span>
              ) : (
                <button
                  onClick={() => toggle(u)}
                  className={`rounded-lg border px-3 py-1 text-xs font-semibold transition ${u.is_active ? 'border-red-200 text-red-600 hover:bg-red-50' : 'border-emerald-200 text-emerald-600 hover:bg-emerald-50'}`}
                >
                  {u.is_active ? 'Deactivate' : 'Activate'}
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>

      <form onSubmit={create} className="mt-5 rounded-2xl bg-indigo-50/60 p-4">
        <p className="mb-3 text-sm font-semibold text-slate-800">Add a staff account</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputClass} />
          <input required type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputClass} />
          <input required type="password" minLength={8} placeholder="Password (8+)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={inputClass} />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className={inputClass}>
            <option value="invigilator">Invigilator</option>
            <option value="owner">Track owner</option>
            <option value="admin">Admin</option>
          </select>
          <button className={primaryBtn}>Add user</button>
        </div>
      </form>
      {error && <ErrorNote text={error} />}
    </>
  )
}

function ManageDomains() {
  const [data, setData] = useState<DomainsResponse | null>(null)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setData((await api.get<DomainsResponse>('/admin/domains')).data)
  }, [])
  useEffect(() => { load().catch((err) => setError(errorMessage(err))) }, [load])

  async function act(request: () => Promise<unknown>) {
    setError('')
    try {
      await request()
      await load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <ul className="space-y-2">
        {data?.domains.map((d) => (
          <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-100 p-3 text-sm transition hover:shadow-md">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">{ico('cap', 'h-5 w-5')}</span>
              <div>
                <div className="font-semibold">{d.name}</div>
                <div className="text-xs text-slate-500">{d.students} students · {d.levels} levels</div>
              </div>
            </div>
            <select
              value={d.owner_id ?? ''} className={inputClass} aria-label={`Owner of ${d.name}`}
              onChange={(e) => act(() => api.patch(`/admin/domains/${d.id}`, { owner_id: e.target.value ? Number(e.target.value) : null }))}
            >
              <option value="">No owner</option>
              {data.owners.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </li>
        ))}
      </ul>
      <form
        className="mt-5 rounded-2xl bg-indigo-50/60 p-4"
        onSubmit={(e) => { e.preventDefault(); act(() => api.post('/admin/domains', { name })).then(() => setName('')) }}
      >
        <p className="mb-3 text-sm font-semibold text-slate-800">Add a domain</p>
        <div className="flex gap-3">
          <input required minLength={2} placeholder="New domain name" value={name} onChange={(e) => setName(e.target.value)} className={`${inputClass} flex-1`} />
          <button className={primaryBtn}>Add domain</button>
        </div>
        <p className="mt-2 text-xs text-slate-500">New domains get 5 default levels. The track owner then adds questions.</p>
      </form>
      {error && <ErrorNote text={error} />}
    </>
  )
}

interface CatalogDomain { id: number; name: string; levels: { id: number; name: string }[] }

function ManageQuestions() {
  const [catalog, setCatalog] = useState<CatalogDomain[]>([])
  const [domainId, setDomainId] = useState<number | null>(null)
  const [levelId, setLevelId] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<CatalogDomain[]>('/manage/slots/catalog')
      .then((res) => {
        setCatalog(res.data)
        setDomainId(res.data[0]?.id ?? null)
        setLevelId(res.data[0]?.levels[0]?.id ?? null)
      })
      .catch((err) => setError(errorMessage(err)))
  }, [])

  const domain = catalog.find((d) => d.id === domainId)
  const level = domain?.levels.find((l) => l.id === levelId)

  if (error) return <ErrorNote text={error} />
  return (
    <>
      <div className="flex flex-wrap gap-3">
        <select
          value={domainId ?? ''} className={inputClass} aria-label="Domain"
          onChange={(e) => { const id = Number(e.target.value); setDomainId(id); setLevelId(catalog.find((d) => d.id === id)?.levels[0]?.id ?? null) }}
        >
          {catalog.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select value={levelId ?? ''} onChange={(e) => setLevelId(Number(e.target.value))} className={inputClass} aria-label="Level">
          {domain?.levels.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
      </div>
      {level && <QuestionBank key={level.id} levelId={level.id} levelName={level.name} />}
    </>
  )
}

function ManagePromotion() {
  const [semester, setSemester] = useState(1)
  const [rows, setRows] = useState<StudentRow[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const load = useCallback(async () => {
    const res = await api.get<StudentsResponse>('/admin/students', { params: { semester } })
    setRows(res.data.students)
    // Semesters 1-2: start with the students who cleared the common test. Later semesters: everyone.
    setSelected(new Set(res.data.students.filter((s) => s.cleared !== false).map((s) => s.id)))
  }, [semester])

  useEffect(() => { load().catch((err) => setMessage({ ok: false, text: errorMessage(err) })) }, [load])

  function toggle(id: number) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  async function promote() {
    try {
      const res = await api.post<{ promoted: number }>('/admin/promote', { student_ids: [...selected] })
      setMessage({ ok: true, text: `${res.data.promoted} student(s) moved to Semester ${semester + 1}` })
      await load()
    } catch (err) {
      setMessage({ ok: false, text: errorMessage(err) })
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-slate-500">Promote students from</span>
        <select value={semester} onChange={(e) => { setSemester(Number(e.target.value)); setMessage(null) }} className={inputClass} aria-label="From semester">
          {[1, 2, 3, 4, 5].map((s) => <option key={s} value={s}>Semester {s}</option>)}
        </select>
        <span className="text-slate-500">to Semester {semester + 1}</span>
      </div>
      {semester < 3 && <p className="mt-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">Students move up automatically when they clear their common test. Use this to move anyone else. Students who cleared the test are ticked by default.</p>}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr><th className="w-8 pb-3" /><th className={thClass}>Student</th><th className={thClass}>Reg no</th><th className={thClass}>Dept</th><th className={thClass}>Status</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((s) => (
              <tr key={s.id} className="transition hover:bg-indigo-50/40">
                <td className="py-3"><input type="checkbox" className="h-4 w-4 accent-indigo-600" checked={selected.has(s.id)} onChange={() => toggle(s.id)} aria-label={`Select ${s.name}`} /></td>
                <td><div className="flex items-center gap-3"><Avatar name={s.name} /><span className="font-semibold">{s.name}</span></div></td>
                <td className="text-slate-600">{s.reg_no}</td><td>{s.department}</td>
                <td><Status status={s.status} /></td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-slate-400">No students in Semester {semester}</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button disabled={selected.size === 0} onClick={promote} className={primaryBtn}>Promote {selected.size} selected</button>
        <Message message={message} />
      </div>
    </>
  )
}

const SETTING_FIELDS: { key: keyof Settings; label: string }[] = [
  { key: 'max_attempts', label: 'Max attempts per test' },
  { key: 'points_to_unlock', label: 'Points needed to unlock another domain' },
  { key: 'first_attempt_points', label: 'Points for a first-attempt pass' },
  { key: 'retry_points', label: 'Points for a pass on a later attempt' },
  { key: 'key_minutes', label: 'Default exam key validity (minutes)' },
]

function ManageSettings() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    api.get<Settings>('/admin/settings').then((res) => setSettings(res.data))
      .catch((err) => setMessage({ ok: false, text: errorMessage(err) }))
  }, [])

  async function save(e: FormEvent) {
    e.preventDefault()
    try {
      const res = await api.put<Settings>('/admin/settings', settings)
      setSettings(res.data)
      setMessage({ ok: true, text: 'Settings saved' })
    } catch (err) {
      setMessage({ ok: false, text: errorMessage(err, 'Check that every value is in range') })
    }
  }

  if (!settings) return <p className="text-sm text-slate-500">{message?.text ?? 'Loading…'}</p>

  return (
    <form onSubmit={save}>
      <div className="grid gap-3 sm:grid-cols-2">
        {SETTING_FIELDS.map((f) => (
          <label key={f.key} className="flex items-center justify-between gap-4 rounded-xl border border-slate-100 p-3 text-sm">
            <span className="font-medium text-slate-700">{f.label}</span>
            <input
              type="number" min={0} value={settings[f.key]} className={`${inputClass} w-24 text-center font-semibold`}
              onChange={(e) => { setSettings({ ...settings, [f.key]: Number(e.target.value) }); setMessage(null) }}
            />
          </label>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button className={primaryBtn}>Save settings</button>
        <Message message={message} />
      </div>
    </form>
  )
}

function ManageAssign() {
  const [semester, setSemester] = useState(1)
  const [form, setForm] = useState({ when: '', venue: '', capacity: 30 })
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [loading, setLoading] = useState(false)

  const pad = (n: number) => String(n).padStart(2, '0')
  const toLocalInput = (iso: string) => {
    const d = new Date(iso)
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  async function assign(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setMessage(null)
    try {
      const res = await api.post<{
        enrolled: number; already_enrolled: number; total_students: number; slot_id: number; level_name: string
      }>('/admin/assign-common', {
        semester,
        starts_at: new Date(form.when).toISOString(),
        venue: form.venue,
        capacity: form.capacity,
      })
      const d = res.data
      setMessage({
        ok: true,
        text: `✅ ${d.enrolled} student(s) enrolled (${d.already_enrolled} already enrolled). Slot created for "${d.level_name}" with ${form.capacity} seats at ${form.venue}.`,
      })
      setForm({ when: '', venue: '', capacity: 30 })
    } catch (err) {
      setMessage({ ok: false, text: errorMessage(err) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <p className="mb-4 rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
        <strong>Assign Common Assessment</strong> — Auto-enroll all Semester 1 or 2 students in the Common Assessments domain and create an exam slot in one step.
      </p>

      <form onSubmit={assign} className="space-y-4">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="font-medium text-slate-700">Semester</span>
          <select
            value={semester} onChange={(e) => { setSemester(Number(e.target.value)); setMessage(null) }}
            className={inputClass} aria-label="Semester"
          >
            <option value={1}>Semester 1</option>
            <option value={2}>Semester 2</option>
          </select>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-500">Date & Time</label>
            <input
              required type="datetime-local" value={form.when}
              min={toLocalInput(new Date().toISOString())}
              onChange={(e) => setForm({ ...form, when: e.target.value })}
              className={`${inputClass} w-full`} aria-label="Date and time"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-semibold text-slate-500">Venue</label>
            <input
              required minLength={2} placeholder="e.g. Block A - Lab 2" value={form.venue}
              onChange={(e) => setForm({ ...form, venue: e.target.value })}
              className={`${inputClass} w-full`}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-500">Capacity</label>
            <input
              required type="number" min={1} max={500} value={form.capacity}
              onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })}
              className={`${inputClass} w-full`} aria-label="Seats"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button disabled={loading} className={primaryBtn}>
            {loading ? 'Assigning…' : `Enroll & create slot for Semester ${semester}`}
          </button>
          <Message message={message} />
        </div>
      </form>
    </>
  )
}

export default function AdminDashboard() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [loadError, setLoadError] = useState('')
  const [activity, setActivity] = useState<ActivityRow[]>([])
  const [dept, setDept] = useState('')
  const [sem, setSem] = useState('')
  const [domain, setDomain] = useState('')
  const [studentData, setStudentData] = useState<StudentsResponse | null>(null)
  const [tab, setTab] = useState<(typeof TABS)[number]>('Users')

  useEffect(() => {
    Promise.all([api.get<Overview>('/admin/overview'), api.get<ActivityRow[]>('/admin/activity')])
      .then(([o, a]) => { setOverview(o.data); setActivity(a.data) })
      .catch((err) => setLoadError(errorMessage(err, 'Could not load analytics')))
  }, [])

  useEffect(() => {
    api.get<StudentsResponse>('/admin/students', { params: { department: dept || undefined, semester: sem || undefined, domain: domain || undefined } })
      .then((res) => setStudentData(res.data))
      .catch((err) => setLoadError(errorMessage(err)))
  }, [dept, sem, domain])

  if (loadError) return <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">{loadError}</p>
  if (!overview) {
    return (
      <div className="flex items-center gap-3 text-sm text-slate-500">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
        Loading analytics…
      </div>
    )
  }

  const { kpis } = overview
  const rows = studentData?.students ?? []

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-slate-950 p-6 text-white shadow-2xl sm:p-10">
        <div className="pointer-events-none absolute -right-20 -top-20 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/4 h-96 w-96 rounded-full bg-purple-600/20 blur-3xl" />
        <div className="relative">
          <span className="inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-medium">Admin</span>
          <h1 className="mt-3 text-3xl font-bold sm:text-4xl">Institution overview</h1>
          <p className="mt-1 text-sm text-gray-400">Analytics across all departments, semesters and domains.</p>
          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Total students" value={kpis.students.toLocaleString()} icon={ico('users', 'h-5 w-5')} />
            <StatTile label="Overall pass rate" value={kpis.pass_rate === null ? '–' : `${kpis.pass_rate}%`} icon={ico('pass', 'h-5 w-5')} />
            <StatTile label="Certificates issued" value={kpis.certificates.toLocaleString()} icon={ico('ribbon', 'h-5 w-5')} />
            <StatTile label="Tests this month" value={kpis.tests_this_month.toLocaleString()} icon={ico('test', 'h-5 w-5')} />
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Average score by domain (%)" icon={ico('chart')}>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={overview.domain_performance} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="adm-bar" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={PINK} />
                    <stop offset="100%" stopColor={INDIGO} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="domain" tickFormatter={short} tick={{ fill: INK, fontSize: 11 }} tickLine={false} axisLine={{ stroke: GRID }} interval={0} />
                <YAxis domain={[0, 100]} tick={{ fill: INK, fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: '#eef2ff' }} contentStyle={TOOLTIP} formatter={(v) => [`${v}%`, 'Average score']} />
                <Bar dataKey="avg" name="Average score" fill="url(#adm-bar)" radius={[6, 6, 0, 0]} maxBarSize={32} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-slate-400">Domains with no attempts yet show no bar.</p>
        </Card>

        <Card title="Pass / fail by semester (attempts)" icon={ico('pass')}>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={overview.semester_results} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="sem" tick={{ fill: INK, fontSize: 11 }} tickLine={false} axisLine={{ stroke: GRID }} />
                <YAxis allowDecimals={false} tick={{ fill: INK, fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: '#eef2ff' }} contentStyle={TOOLTIP} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="pass" name="Pass" stackId="r" fill={INDIGO} stroke="#fff" strokeWidth={2} maxBarSize={32} />
                <Bar dataKey="fail" name="Fail" stackId="r" fill={PINK} stroke="#fff" strokeWidth={2} radius={[6, 6, 0, 0]} maxBarSize={32} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-slate-400">Semesters 1–2 common assessments are not recorded yet.</p>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Top skill gaps (students affected)" icon={ico('alert')}>
          {overview.skill_gaps.length === 0 ? (
            <Empty>No skill-gap data yet.</Empty>
          ) : (
            <div className="h-60">
              <ResponsiveContainer>
                <BarChart data={overview.skill_gaps} layout="vertical" margin={{ top: 0, right: 16, left: 24, bottom: 0 }}>
                  <CartesianGrid stroke={GRID} horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={{ fill: INK, fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="topic" width={130} tick={{ fill: INK, fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{ fill: '#eef2ff' }} contentStyle={TOOLTIP} formatter={(v) => [`${v}`, 'Students']} />
                  <Bar dataKey="students" name="Students" fill={INDIGO} radius={[0, 6, 6, 0]} maxBarSize={20} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="Platform activity" icon={ico('pulse')}>
          {activity.length === 0 && <Empty>No activity yet.</Empty>}
          <ul className="max-h-60 space-y-3 overflow-y-auto pr-1">
            {activity.map((a) => (
              <li key={a.id} className="flex gap-3 text-sm">
                <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-indigo-500 shadow-sm shadow-indigo-500/50" />
                <div>
                  <p className="text-slate-700">{a.action}</p>
                  <p className="text-xs text-slate-400">
                    {new Date(a.created_at).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Students" icon={ico('users')}>
        <div className="mb-4 flex flex-wrap gap-3">
          <Filter label="departments" value={dept} onChange={setDept} options={studentData?.departments ?? []} />
          <Filter label="semesters" value={sem} onChange={setSem} options={SEMESTERS} />
          <Filter label="domains" value={domain} onChange={setDomain} options={studentData?.domains ?? []} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr><th className={thClass}>Student</th><th className={thClass}>Reg no</th><th className={thClass}>Dept</th><th className={thClass}>Sem</th><th className={thClass}>Domain</th><th className={thClass}>Attempts</th><th className={thClass}>Certs</th><th className={thClass}>Status</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((s) => (
                <tr key={s.id} className="transition hover:bg-indigo-50/40">
                  <td className="py-3"><div className="flex items-center gap-3"><Avatar name={s.name} /><span className="font-semibold">{s.name}</span></div></td>
                  <td className="text-slate-600">{s.reg_no}</td><td>{s.department}</td><td>{s.semester}</td><td>{s.domain ?? '–'}</td>
                  <td>{s.attempts}</td><td className="font-semibold">{s.certificates}</td>
                  <td><Status status={s.status} /></td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={8} className="py-8 text-center text-slate-400">No students match these filters</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Manage platform" icon={ico('cog')}>
        <div className="mb-5 flex flex-wrap gap-2 rounded-2xl bg-slate-100 p-1.5">
          {TABS.map((t) => (
            <button
              key={t} onClick={() => setTab(t)}
              className={`flex-1 rounded-xl px-4 py-2 text-sm font-semibold transition ${tab === t ? 'bg-white text-indigo-600 shadow-md' : 'text-slate-500 hover:text-slate-800'}`}
            >
              {t}
            </button>
          ))}
        </div>
        {tab === 'Users' && <ManageUsers />}
        {tab === 'Domains' && <ManageDomains />}
        {tab === 'Slots' && <SlotManager />}
        {tab === 'Questions' && <ManageQuestions />}
        {tab === 'Promote' && <ManagePromotion />}
        {tab === 'Assign' && <ManageAssign />}
        {tab === 'Settings' && <ManageSettings />}
      </Card>
    </div>
  )
}
