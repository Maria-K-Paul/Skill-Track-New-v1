import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage } from '../api'
import Card from '../components/Card'
import { Icon } from '../components/AuthLayout'
import StatTile from '../components/StatTile'
import { inputClass, primaryBtn } from '../components/authStyles'

interface Catalog {
  id: number
  name: string
  levels: { id: number; number: number; name: string }[]
}

interface Student { id: number; name: string; reg_no: string | null }

interface SlotInfo {
  id: number
  level_id: number
  level_name: string
  domain_name: string
  starts_at: string
  venue: string
  capacity: number
  booked: number
  students: Student[]
}

interface ExamKey {
  id: number
  code: string
  level_name: string
  domain_name: string
  expires_at: string
  slot: SlotInfo | null
}

const PATHS = {
  key: 'M21 2l-2 2m-7.6 7.6a5.5 5.5 0 11-7.8 7.8 5.5 5.5 0 017.8-7.8zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4',
  clock: 'M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  list: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
  plus: 'M12 5v14M5 12h14',
  copy: 'M9 9h10v10H9zM5 15V5h10',
  check: 'M5 13l4 4L19 7',
  calendar: 'M7 3v4M17 3v4M4 9h16M5 5h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1z',
  users: 'M16 11a3 3 0 100-6 3 3 0 000 6zM8 11a3 3 0 100-6 3 3 0 000 6zM2 20a6 6 0 0112 0M14 14.5A6 6 0 0122 20',
  pin: 'M12 21s-7-6.2-7-11a7 7 0 1114 0c0 4.8-7 11-7 11zM12 12a2.5 2.5 0 100-5 2.5 2.5 0 000 5z',
}

const ico = (name: keyof typeof PATHS, className = 'h-4 w-4') => (
  <Icon className={className}><path strokeLinecap="round" strokeLinejoin="round" d={PATHS[name]} /></Icon>
)

const fmtDate = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
const fmtTime = (iso: string) => new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })

export default function InvigilatorDashboard() {
  const [slots, setSlots] = useState<SlotInfo[]>([])
  const [catalog, setCatalog] = useState<Catalog[]>([])
  const [useSlot, setUseSlot] = useState(true)
  const [slotId, setSlotId] = useState<number | ''>('')
  const [domainId, setDomainId] = useState<number | ''>('')
  const [levelId, setLevelId] = useState<number | ''>('')
  const [minutes, setMinutes] = useState(5)
  const [keys, setKeys] = useState<ExamKey[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const [now, setNow] = useState(() => Date.now())

  const loadKeys = useCallback(async () => {
    const res = await api.get<ExamKey[]>('/exam/keys')
    setKeys(res.data)
  }, [])

  useEffect(() => {
    Promise.all([api.get<Catalog[]>('/exam/catalog'), api.get<SlotInfo[]>('/exam/slots'), loadKeys()])
      .then(([cat, sl]) => {
        setCatalog(cat.data)
        setSlots(sl.data)
        setSlotId(sl.data[0]?.id ?? '')
      })
      .catch((err) => setError(errorMessage(err)))
  }, [loadKeys])

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const levels = catalog.find((d) => d.id === domainId)?.levels ?? []
  const selectedSlot = slots.find((s) => s.id === slotId)
  const latest = keys[0]
  const left = (k: ExamKey) => Math.max(0, Math.floor((new Date(k.expires_at).getTime() - now) / 1000))
  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  const activeCount = keys.filter((k) => left(k) > 0).length
  const ready = useSlot ? slotId !== '' : levelId !== ''

  async function issue() {
    setBusy(true)
    setError('')
    try {
      await api.post('/exam/keys', { ...(useSlot ? { slot_id: slotId } : { level_id: levelId }), minutes })
      await loadKeys()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function copy(code: string) {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-slate-950 p-6 text-white shadow-2xl sm:p-10">
        <div className="pointer-events-none absolute -right-20 -top-20 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/4 h-96 w-96 rounded-full bg-purple-600/20 blur-3xl" />
        <div className="relative">
          <span className="inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-medium">Invigilator</span>
          <h1 className="mt-3 text-3xl font-bold sm:text-4xl">Exam keys</h1>
          <p className="mt-1 max-w-xl text-sm text-gray-400">Pick a test slot to issue a time-limited key. Only students who booked that slot can use it. If a key fails because of a network issue, issue a new one in person.</p>
          <div className="mt-6 grid max-w-md grid-cols-2 gap-3">
            <StatTile label="Active keys" value={activeCount} icon={ico('key', 'h-5 w-5')} />
            <StatTile label="Upcoming slots" value={slots.length} icon={ico('calendar', 'h-5 w-5')} />
          </div>
        </div>
      </section>

      <Card title="Issue a new key" icon={ico('plus')}>
        {useSlot ? (
          <>
            <p className="mb-3 text-sm font-semibold text-slate-700">1 · Choose the slot this key is for</p>
            {slots.length === 0 ? (
              <p className="rounded-xl bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">No upcoming slots. Ask the admin or track owner to schedule one.</p>
            ) : (
              <div className="grid gap-3 lg:grid-cols-[1.1fr_1fr]">
                <ul className="max-h-96 space-y-2 overflow-y-auto pr-1">
                  {slots.map((s) => {
                    const picked = s.id === slotId
                    return (
                      <li key={s.id}>
                        <button
                          type="button" onClick={() => setSlotId(s.id)}
                          className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left text-sm transition ${picked ? 'border-indigo-500 bg-indigo-50 ring-4 ring-indigo-100' : 'border-slate-200 hover:border-indigo-300 hover:shadow-md'}`}
                        >
                          <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${picked ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/30' : 'bg-indigo-50 text-indigo-600'}`}>{ico('calendar', 'h-5 w-5')}</span>
                          <span className="min-w-0 flex-1">
                            <span className="block font-semibold text-slate-800">{fmtDate(s.starts_at)} · {fmtTime(s.starts_at)}</span>
                            <span className="block truncate text-xs text-slate-500">{s.domain_name} · {s.level_name}</span>
                            <span className="block text-xs text-slate-500">{s.venue}</span>
                          </span>
                          <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${s.booked ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{s.booked}/{s.capacity} booked</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>

                <div className="rounded-2xl bg-indigo-50/60 p-4">
                  {selectedSlot ? (
                    <>
                      <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">{ico('users', 'h-4 w-4 text-indigo-500')} Students this key is for ({selectedSlot.students.length})</p>
                      <p className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">{ico('pin', 'h-3.5 w-3.5')} {selectedSlot.venue} · {selectedSlot.level_name}</p>
                      {selectedSlot.students.length === 0 ? (
                        <p className="mt-3 rounded-xl bg-white px-3 py-4 text-center text-sm text-slate-500">No students have booked this slot yet. A key for it would not work for anyone.</p>
                      ) : (
                        <ul className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
                          {selectedSlot.students.map((st) => (
                            <li key={st.id} className="flex items-center gap-3 rounded-xl bg-white p-2.5 text-sm shadow-sm transition-all hover:bg-slate-50">
                              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-50 text-xs font-bold text-indigo-700 ring-1 ring-inset ring-indigo-600/20">{st.name.trim().charAt(0).toUpperCase()}</span>
                              <span className="font-semibold text-slate-800">{st.name}</span>
                              <span className="ml-auto text-xs text-slate-500">{st.reg_no}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  ) : (
                    <p className="py-6 text-center text-sm text-slate-500">Select a slot to see who booked it.</p>
                  )}
                </div>
              </div>
            )}
          </>
        ) : (
          <>
            <p className="mb-3 text-sm font-semibold text-slate-700">1 · Choose the level (any student at that level can use the key)</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <select value={domainId} onChange={(e) => { setDomainId(e.target.value ? Number(e.target.value) : ''); setLevelId('') }} className={`${inputClass} py-2.5`}>
                <option value="">Choose a domain…</option>
                {catalog.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <select value={levelId} disabled={!domainId} onChange={(e) => setLevelId(e.target.value ? Number(e.target.value) : '')} className={`${inputClass} py-2.5 disabled:bg-slate-50 disabled:text-slate-400`}>
                <option value="">Choose a level…</option>
                {levels.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
          </>
        )}
        <button type="button" onClick={() => setUseSlot((v) => !v)} className="mt-3 text-xs font-semibold text-indigo-600 hover:underline">
          {useSlot ? 'Issue without a slot (by level)' : '← Back to choosing a slot'}
        </button>

        <p className="mb-2 mt-5 text-sm font-semibold text-slate-700">2 · Key valid for</p>
        <div className="grid max-w-md grid-cols-4 gap-2">
          {[2, 5, 10, 15].map((m) => (
            <button
              key={m} type="button" onClick={() => setMinutes(m)}
              className={`rounded-xl border px-2 py-2 text-sm font-semibold transition ${minutes === m ? 'border-indigo-500 bg-indigo-50 text-indigo-700 ring-4 ring-indigo-100' : 'border-slate-200 text-slate-600 hover:border-indigo-300'}`}
            >
              {m} min
            </button>
          ))}
        </div>

        <button disabled={busy || !ready} onClick={issue} className={`${primaryBtn} mt-5 flex w-full max-w-md items-center justify-center gap-2 py-3`}>
          {ico('key')} {busy ? 'Issuing…' : useSlot && selectedSlot ? `Issue key for ${fmtTime(selectedSlot.starts_at)} · ${selectedSlot.venue}` : 'Issue key'}
        </button>
        {error && <p role="alert" className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
      </Card>

      {latest && (
        <section className="relative grid gap-6 overflow-hidden rounded-2xl bg-slate-950 p-6 text-white shadow-2xl md:grid-cols-[auto_1fr]">
          <div className="pointer-events-none absolute -left-20 -top-20 h-64 w-64 rounded-full bg-indigo-600/20 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-purple-600/20 blur-3xl" />
          <div className="relative flex flex-col items-center justify-center text-center">
            <p className="text-xs font-semibold uppercase tracking-widest text-white/70">Latest key</p>
            <div className="mt-3 rounded-2xl border-2 border-dashed border-white/40 bg-white/10 px-6 py-4 font-mono text-4xl font-bold tracking-widest">{latest.code}</div>
            <p className={`mt-3 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-semibold ${left(latest) > 0 ? 'bg-emerald-400/90 text-emerald-950' : 'bg-red-500 text-white'}`}>
              {left(latest) > 0 && <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-900" />}
              {ico('clock')} {left(latest) > 0 ? `Expires in ${fmt(left(latest))}` : 'Expired'}
            </p>
            <button onClick={() => copy(latest.code)} className="mt-3 inline-flex items-center gap-2 rounded-xl bg-white/20 px-4 py-2 text-sm font-semibold transition hover:bg-white/30">
              {ico(copied ? 'check' : 'copy')} {copied ? 'Copied' : 'Copy key'}
            </button>
          </div>

          <div className="relative text-sm">
            <p className="text-xs font-semibold uppercase tracking-widest text-white/70">This key is for</p>
            <p className="mt-2 text-lg font-bold">{latest.domain_name} · {latest.level_name}</p>
            {latest.slot ? (
              <>
                <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-white/90">
                  <span className="inline-flex items-center gap-1.5">{ico('calendar')} {fmtDate(latest.slot.starts_at)} · {fmtTime(latest.slot.starts_at)}</span>
                  <span className="inline-flex items-center gap-1.5">{ico('pin')} {latest.slot.venue}</span>
                </p>
                <p className="mt-3 inline-flex items-center gap-1.5 text-white/90">{ico('users')} {latest.slot.students.length} booked student{latest.slot.students.length === 1 ? '' : 's'}</p>
                <ul className="mt-2 flex max-h-28 flex-wrap gap-2 overflow-y-auto">
                  {latest.slot.students.map((st) => (
                    <li key={st.id} className="rounded-full bg-white/20 px-3 py-1 text-xs font-medium">{st.name}{st.reg_no && ` · ${st.reg_no}`}</li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="mt-2 rounded-xl bg-white/15 px-3 py-2 text-white/90">Not tied to a slot, so any student at this level can use it.</p>
            )}
          </div>
        </section>
      )}

      {keys.length > 1 && (
        <Card title="Recent keys" icon={ico('list')}>
          <ul className="space-y-2">
            {keys.slice(1).map((k) => {
              const live = left(k) > 0
              return (
                <li key={k.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3 text-sm transition hover:shadow-md">
                  <div className="flex items-center gap-3">
                    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${live ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-400'}`}>{ico('key', 'h-5 w-5')}</span>
                    <div>
                      <div className="font-mono font-semibold tracking-wider">{k.code}</div>
                      <div className="text-xs text-slate-500">
                        {k.level_name}
                        {k.slot ? ` · ${fmtDate(k.slot.starts_at)} ${fmtTime(k.slot.starts_at)} · ${k.slot.venue} · ${k.slot.students.length} students` : ' · no slot'}
                      </div>
                    </div>
                  </div>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${live ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{live ? fmt(left(k)) : 'Expired'}</span>
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </div>
  )
}
