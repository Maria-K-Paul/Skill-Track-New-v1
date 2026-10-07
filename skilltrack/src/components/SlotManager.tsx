import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, errorMessage } from '../api'

interface CatalogDomain {
  id: number
  name: string
}

interface SlotRow {
  id: number
  domain_id: number
  domain_name: string
  starts_at: string
  venue: string
  capacity: number
  booked: number
}

const inputClass = 'rounded border border-slate-300 px-2 py-1.5 text-sm'
const emptyForm = { when: '', venue: '', capacity: 30 }

const pad = (n: number) => String(n).padStart(2, '0')

/** ISO timestamp -> value for <input type="datetime-local"> in the user's own timezone */
function toLocalInput(iso: string) {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const fmt = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

/** Create, edit and remove test slots. Admins see every domain; track owners see their own. */
export default function SlotManager() {
  const [catalog, setCatalog] = useState<CatalogDomain[]>([])
  const [domainId, setDomainId] = useState<number | null>(null)
  const [slots, setSlots] = useState<SlotRow[]>([])
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<CatalogDomain[]>('/manage/slots/catalog')
      .then((res) => {
        setCatalog(res.data)
        setDomainId(res.data[0]?.id ?? null)
      })
      .catch((err) => setError(errorMessage(err)))
  }, [])

  const loadSlots = useCallback(async () => {
    if (domainId === null) return
    const res = await api.get<SlotRow[]>('/manage/slots', { params: { domain_id: domainId } })
    setSlots(res.data)
  }, [domainId])

  useEffect(() => { loadSlots().catch((err) => setError(errorMessage(err))) }, [loadSlots])

  function pickDomain(id: number) {
    setDomainId(id)
    resetForm()
  }

  function resetForm() {
    setForm(emptyForm)
    setEditingId(null)
    setError('')
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    setError('')
    const payload = { starts_at: new Date(form.when).toISOString(), venue: form.venue, capacity: form.capacity }
    try {
      if (editingId) await api.patch(`/manage/slots/${editingId}`, payload)
      else await api.post('/manage/slots', { domain_id: domainId, ...payload })
      resetForm()
      await loadSlots()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function remove(id: number) {
    setError('')
    try {
      await api.delete(`/manage/slots/${id}`)
      if (editingId === id) resetForm()
      await loadSlots()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  function startEdit(s: SlotRow) {
    setEditingId(s.id)
    setForm({ when: toLocalInput(s.starts_at), venue: s.venue, capacity: s.capacity })
    setError('')
  }

  const now = Date.now()
  const selectedDomain = catalog.find((d) => d.id === domainId)

  if (catalog.length === 0) return <p className="text-sm text-slate-500">{error || 'No domains to manage yet.'}</p>

  return (
    <>
      <div className="mb-3 flex flex-wrap gap-2">
        <select value={domainId ?? ''} onChange={(e) => pickDomain(Number(e.target.value))} className={inputClass} aria-label="Domain">
          <option value="">Select a domain...</option>
          {catalog.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        {selectedDomain && (
          <p className="flex items-center rounded-xl bg-indigo-50 px-3 py-2 text-sm text-indigo-700">
            <span className="font-semibold">{selectedDomain.name}</span> - Students of any level can book these slots
          </p>
        )}
      </div>

      {slots.length === 0 && <p className="text-sm text-slate-500">No slots for this domain yet. Students cannot book until you add one.</p>}
      <ul className="divide-y divide-slate-100 text-sm">
        {slots.map((s) => {
          const past = new Date(s.starts_at).getTime() <= now
          return (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div className={past ? 'text-slate-400' : ''}>
                <span className="font-medium">{fmt(s.starts_at)}</span> · {s.venue}
                <span className="ml-2 text-xs">{s.booked}/{s.capacity} booked{past && ' · past'}</span>
              </div>
              <div className="flex gap-3 text-xs">
                <button onClick={() => startEdit(s)} className="text-indigo-600 hover:underline">Edit</button>
                <button onClick={() => remove(s.id)} className="text-red-600 hover:underline">Delete</button>
              </div>
            </li>
          )
        })}
      </ul>

      <form onSubmit={save} className="mt-4 border-t border-slate-100 pt-4">
        <p className="mb-2 text-sm font-medium">{editingId ? 'Edit slot' : 'Add a slot'}</p>
        <div className="grid gap-2 sm:grid-cols-4">
          <input
            required type="datetime-local" value={form.when} min={toLocalInput(new Date().toISOString())}
            onChange={(e) => setForm({ ...form, when: e.target.value })} className={inputClass} aria-label="Date and time"
          />
          <input
            required minLength={2} placeholder="Venue, e.g. Block A - Lab 2" value={form.venue}
            onChange={(e) => setForm({ ...form, venue: e.target.value })} className={`${inputClass} sm:col-span-2`}
          />
          <input
            required type="number" min={1} max={500} value={form.capacity} aria-label="Seats"
            onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })} className={inputClass}
          />
        </div>
        <div className="mt-2 flex gap-2">
          <button className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500">
            {editingId ? 'Save changes' : 'Add slot'}
          </button>
          {editingId && <button type="button" onClick={resetForm} className="rounded bg-slate-100 px-3 py-1.5 text-sm hover:bg-slate-200">Cancel</button>}
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </form>
    </>
  )
}
