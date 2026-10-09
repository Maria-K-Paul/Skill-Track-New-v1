import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage } from '../api'
import Card from '../components/Card'
import { Icon } from '../components/AuthLayout'
import SyllabusManager from '../components/SyllabusManager'

type Difficulty = 'easy' | 'medium' | 'hard'
const DIFFICULTIES: Difficulty[] = ['easy', 'medium', 'hard']

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
  bloom_level_ratio: any
  question_generation_status: string
  topics: any[]
  bank: Record<Difficulty, number>
}

interface Overview {
  domain: { id: number; name: string }
  levels: LevelData[]
}

const DIFF_STYLE: Record<Difficulty, { bar: string; accent: string; chip: string }> = {
  easy: { bar: 'bg-emerald-400', accent: 'accent-emerald-500', chip: 'bg-emerald-50 text-emerald-700' },
  medium: { bar: 'bg-amber-400', accent: 'accent-amber-500', chip: 'bg-amber-50 text-amber-700' },
  hard: { bar: 'bg-rose-400', accent: 'accent-rose-500', chip: 'bg-rose-50 text-rose-700' },
}

const inputClass = 'rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100'
const primaryBtn = 'group inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:-translate-y-0.5 hover:bg-indigo-500 hover:shadow-indigo-500/40 active:translate-y-0 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none'

function AllotCard({ level, onSaved }: { level: LevelData; onSaved: () => Promise<void> }) {
  const [mix, setMix] = useState<Record<Difficulty, number>>({
    easy: level.easy_pct, medium: level.medium_pct, hard: level.hard_pct,
  })
  const [questionCount, setQuestionCount] = useState<number>(level.question_count)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const total = mix.easy + mix.medium + mix.hard

  async function save() {
    try {
      await api.patch(`/owner/levels/${level.id}`, { 
        easy_pct: mix.easy, 
        medium_pct: mix.medium, 
        hard_pct: mix.hard,
        question_count: questionCount
      })
      await onSaved()
      setMessage({ ok: true, text: `Saved for ${level.name}` })
    } catch (err) {
      setMessage({ ok: false, text: errorMessage(err) })
    }
  }

  return (
    <div className="mt-6 border-t border-slate-100 pt-6">
      <div className="mb-6">
        <h3 className="text-lg font-bold text-slate-800 mb-4">Test Configuration</h3>
        <label className="block text-sm max-w-xs">
          <span className="font-semibold text-slate-700">Total Number of Questions</span>
          <input 
            type="number" min="1" max="200" 
            value={questionCount || ''} 
            onChange={(e) => { setQuestionCount(Number(e.target.value)); setMessage(null); }} 
            className={`${inputClass} mt-1.5 block w-full`} 
          />
        </label>
      </div>

      <p className="text-sm font-semibold">Difficulty distribution <span className="font-normal text-slate-500">({questionCount} questions per test)</span></p>
      <div className="mt-3 flex h-3 overflow-hidden rounded-full bg-slate-100">
        {DIFFICULTIES.map((d) => <div key={d} className={`${DIFF_STYLE[d].bar} transition-all duration-300`} style={{ width: `${Math.min(mix[d], 100)}%` }} />)}
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {DIFFICULTIES.map((d) => (
          <div key={d} className="rounded-2xl border border-slate-100 p-4 text-sm shadow-sm">
            <div className="flex items-center justify-between">
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${DIFF_STYLE[d].chip}`}>{d}</span>
              <span className="text-lg font-bold">{mix[d]}%</span>
            </div>
            <input
              type="range" min={0} max={100} step={5} value={mix[d]}
              onChange={(e) => { setMix({ ...mix, [d]: Number(e.target.value) }); setMessage(null) }}
              className={`mt-3 w-full ${DIFF_STYLE[d].accent}`}
            />
          </div>
        ))}
      </div>
      <p className={`mt-4 text-sm font-semibold ${total === 100 ? 'text-emerald-600' : 'text-red-600'}`}>
        Total: {total}% {total !== 100 && '(must equal 100%)'}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button disabled={total !== 100 || !questionCount || questionCount <= 0} onClick={save} className={primaryBtn}>Save Configuration</button>
        {message && <span className={`text-sm font-medium ${message.ok ? 'text-emerald-600' : 'text-red-600'}`}>{message.text}</span>}
      </div>
    </div>
  )
}

export default function SyllabusPage() {
  const [data, setData] = useState<Overview | null>(null)
  const [loadError, setLoadError] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await api.get<Overview>('/owner/overview')
      setData(res.data)
      setSelectedId((id) => id ?? res.data.levels[0]?.id ?? null)
      setLoadError('')
    } catch (err) {
      setLoadError(errorMessage(err, 'Could not load levels'))
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loadError) return <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">{loadError}</p>
  if (!data) return <div className="p-6 text-sm text-slate-500">Loading levels…</div>

  const level = data.levels.find((l) => l.id === selectedId) ?? data.levels[0]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Manage Syllabus - {data.domain.name}</h1>
      {level && (
        <Card title="Syllabus Configuration" icon={<Icon className="h-4 w-4"><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4" /></Icon>}>
          <label className="block text-sm">
            <span className="font-semibold text-slate-700">Level</span>
            <select value={level.id} onChange={(e) => setSelectedId(Number(e.target.value))} className={`${inputClass} mt-1.5 block w-full max-w-xs`}>
              {data.levels.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </label>
          <AllotCard key={`allot-${level.id}`} level={level} onSaved={load} />
          <SyllabusManager 
            key={`syllabus-${level.id}`} 
            levelId={level.id} 
            levelName={level.name} 
            initialTopics={level.topics} 
            initialBloom={level.bloom_level_ratio} 
            generationStatus={level.question_generation_status}
            onSaved={load} 
          />
        </Card>
      )}
    </div>
  )
}
