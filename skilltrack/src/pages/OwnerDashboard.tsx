import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, errorMessage } from '../api'
import Card from '../components/Card'
import { Icon } from '../components/AuthLayout'
import SlotManager from '../components/SlotManager'

type Difficulty = 'easy' | 'medium' | 'hard'

interface LevelData {
  id: number
  number: number
  name: string
  question_count: number
  pass_mark: number
  duration_min: number
  easy_pct: number
  medium_pct: number
  hard_pct: number
  bloom_level_ratio: {
    remember: number
    understand: number
    apply: number
    analyze: number
    evaluate: number
    create: number
  }
  question_generation_status: string
  topics: {
    id?: number
    name: string
    weightage: number
    subtopics: { id?: number; name: string; weightage: number }[]
  }[]
  bank: Record<Difficulty, number>
}

interface StudentRow {
  id: number
  name: string
  reg_no: string | null
  semester: number | null
  level: number | null
  attempts: number
  points: number
  status: 'Active' | 'At risk' | 'Removed' | 'Completed'
}

interface Overview {
  domain: { id: number; name: string }
  max_attempts: number
  students: StudentRow[]
  levels: LevelData[]
}

const STATUS_STYLE: Record<StudentRow['status'], string> = {
  Active: 'bg-emerald-100 text-emerald-700',
  'At risk': 'bg-amber-100 text-amber-700',
  Removed: 'bg-red-100 text-red-700',
  Completed: 'bg-indigo-100 text-indigo-700',
}

const PATHS = {
  users: 'M16 11a3 3 0 100-6 3 3 0 000 6zM8 11a3 3 0 100-6 3 3 0 000 6zM2 20a6 6 0 0112 0M14 14.5A6 6 0 0122 20',
  pulse: 'M3 12h4l3-8 4 16 3-8h4',
  alert: 'M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z',
  flag: 'M5 21V4m0 0h11l-2 4 2 4H5',
  sliders: 'M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4',
  calendar: 'M7 3v4M17 3v4M4 9h16M5 5h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1z',
  book: 'M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2V5zM4 19a2 2 0 002 2h13',
  check: 'M5 13l4 4L19 7',
  list: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
}

const ico = (name: keyof typeof PATHS, className = 'h-4 w-4') => (
  <Icon className={className}><path strokeLinecap="round" strokeLinejoin="round" d={PATHS[name]} /></Icon>
)

const inputClass =
  'rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100'
const primaryBtn =
  'group inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-500 hover:shadow-indigo-500/40 active:translate-y-0 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none'

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



export default function OwnerDashboard() {
  const [data, setData] = useState<Overview | null>(null)
  const [loadError, setLoadError] = useState('')
  const [edits, setEdits] = useState<Record<number, Partial<Pick<LevelData, 'question_count' | 'pass_mark' | 'duration_min'>>>>({})
  const [levelError, setLevelError] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await api.get<Overview>('/owner/overview')
      setData(res.data)
      setLoadError('')
    } catch (err) {
      setLoadError(errorMessage(err, 'Could not load your domain'))
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loadError) return <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">{loadError}</p>
  if (!data) {
    return (
      <div className="flex items-center gap-3 text-sm text-slate-500">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
        Loading your domain…
      </div>
    )
  }

  const count = (s: StudentRow['status']) => data.students.filter((x) => x.status === s).length

  async function saveLevel(id: number) {
    setLevelError('')
    try {
      await api.patch(`/owner/levels/${id}`, edits[id])
      setEdits(({ [id]: _saved, ...rest }) => rest)
      await load()
    } catch (err) {
      setLevelError(errorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-slate-950 p-6 text-white shadow-2xl sm:p-10">
        <div className="pointer-events-none absolute -right-20 -top-20 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/4 h-96 w-96 rounded-full bg-purple-600/20 blur-3xl" />
        <div className="relative">
          <span className="inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-medium">Track owner</span>
          <h1 className="mt-3 text-3xl font-bold sm:text-4xl">{data.domain.name}</h1>
          <p className="mt-1 text-sm text-gray-400">Manage students, test levels, slots and your question bank.</p>
          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Enrolled students" value={data.students.length} icon={ico('users', 'h-5 w-5')} />
            <StatTile label="Active" value={count('Active')} icon={ico('pulse', 'h-5 w-5')} />
            <StatTile label="At risk" value={count('At risk')} icon={ico('alert', 'h-5 w-5')} />
            <StatTile label="Completed" value={count('Completed')} icon={ico('check', 'h-5 w-5')} />
          </div>
        </div>
      </section>

      <Card title={`Enrolled students (${data.students.length})`} icon={ico('users')}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-400">
              <tr><th className="pb-3">Student</th><th className="pb-3">Reg no</th><th className="pb-3">Sem</th><th className="pb-3">Level</th><th className="pb-3">Attempts</th><th className="pb-3">Points</th><th className="pb-3">Status</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.students.map((s) => (
                <tr key={s.id} className="transition hover:bg-indigo-50/40">
                  <td className="py-3">
                    <div className="flex items-center gap-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-50 text-xs font-bold text-indigo-700 ring-1 ring-inset ring-indigo-600/20">{s.name.trim().charAt(0).toUpperCase()}</span>
                      <span className="font-semibold text-slate-800">{s.name}</span>
                    </div>
                  </td>
                  <td className="text-slate-600">{s.reg_no}</td>
                  <td>{s.semester}</td>
                  <td>{s.level ? <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold">L{s.level}</span> : <span className="text-emerald-600">Done</span>}</td>
                  <td>{s.level ? `${s.attempts}/${data.max_attempts}` : '–'}</td>
                  <td className="font-semibold">{s.points}</td>
                  <td><span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLE[s.status]}`}>{s.status}</span></td>
                </tr>
              ))}
              {data.students.length === 0 && <tr><td colSpan={7} className="py-8 text-center text-slate-400">No students enrolled yet</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Manage test levels" icon={ico('flag')}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-400">
              <tr><th className="pb-3">Level</th><th className="pb-3">Questions / test</th><th className="pb-3">Pass mark %</th><th className="pb-3">Duration (min)</th><th /></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.levels.map((l) => (
                <tr key={l.id}>
                  <td className="py-3">
                    <div className="flex items-center gap-3">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-xs font-bold text-indigo-600">{l.number}</span>
                      <span className="font-semibold">{l.name}</span>
                    </div>
                  </td>
                  {(['question_count', 'pass_mark', 'duration_min'] as const).map((f) => (
                    <td key={f}>
                      <input
                        type="number" min={1} value={edits[l.id]?.[f] ?? l[f]}
                        onChange={(e) => setEdits({ ...edits, [l.id]: { ...edits[l.id], [f]: Number(e.target.value) } })}
                        className={`${inputClass} w-24`}
                      />
                    </td>
                  ))}
                  <td className="text-right">{edits[l.id] && <button onClick={() => saveLevel(l.id)} className={`${primaryBtn} px-3 py-1.5 text-xs`}>Save</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {levelError && <p role="alert" className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-600">{levelError}</p>}
      </Card>

      <Card title="Test slots" icon={ico('calendar')}>
        <p className="mb-4 text-sm text-slate-500">Set the date, time, venue and seats for your domain's tests. Students book from these.</p>
        <SlotManager />
      </Card>

    </div>
  )
}
