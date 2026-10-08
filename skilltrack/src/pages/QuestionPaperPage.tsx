import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage } from '../api'
import Card from '../components/Card'

interface Question {
  id: number
  text: string
  options: string[]
  answer_index: number
  difficulty: string
  topic: string
}

export default function QuestionPaperPage() {
  const [levels, setLevels] = useState<{id: number, name: string, question_generation_status?: string}[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)

  const loadQuestions = useCallback(() => {
    if (!selectedId) return
    setLoading(true)
    api.get(`/owner/levels/${selectedId}/questions`)
      .then(res => {
        setQuestions(res.data)
        setLoading(false)
      })
      .catch(err => {
        setError(errorMessage(err))
        setLoading(false)
      })
  }, [selectedId])

  const loadLevels = useCallback(async () => {
    try {
      const res = await api.get('/owner/overview')
      setLevels(res.data.levels)
      if (res.data.levels.length > 0 && selectedId === null) {
        setSelectedId(res.data.levels[0].id)
      }
    } catch (err) {
      setError(errorMessage(err, 'Could not load levels'))
    }
  }, [selectedId])

  useEffect(() => { loadLevels() }, [loadLevels])
  useEffect(() => { loadQuestions() }, [loadQuestions])

  const currentLevel = levels.find(l => l.id === selectedId)
  
  useEffect(() => {
    if (currentLevel?.question_generation_status === 'generating') {
      setGenerating(true)
    } else {
      setGenerating(false)
    }
  }, [currentLevel?.question_generation_status])

  useEffect(() => {
    let interval: any
    if (generating && selectedId) {
      interval = setInterval(async () => {
        try {
          const res = await api.get('/owner/overview')
          setLevels(res.data.levels)
          const curr = res.data.levels.find((l: any) => l.id === selectedId)
          if (curr && curr.question_generation_status !== 'generating') {
            setGenerating(false)
            loadQuestions()
          }
        } catch (e) {}
      }, 5000)
    }
    return () => clearInterval(interval)
  }, [generating, selectedId, loadQuestions])

  async function handleGenerate() {
    if (!selectedId) return
    setGenerating(true)
    try {
      await api.post(`/owner/levels/${selectedId}/generate`)
      loadLevels() // this will fetch updated generation status
    } catch (err) {
      alert(errorMessage(err))
      setGenerating(false)
    }
  }

  async function deleteQuestion(id: number) {
    if (!window.confirm("Are you sure you want to delete this question?")) return
    try {
      await api.delete(`/owner/questions/${id}`)
      loadQuestions()
    } catch (err) {
      alert(errorMessage(err))
    }
  }

  async function deleteAllQuestions() {
    if (!selectedId) return
    if (!window.confirm("Are you sure you want to delete ALL questions for this level? This action cannot be undone.")) return
    try {
      await api.delete(`/owner/levels/${selectedId}/questions`)
      loadQuestions()
    } catch (err) {
      alert(errorMessage(err))
    }
  }

  function EditableQuestion({ q, index }: { q: Question, index: number }) {
    const [editing, setEditing] = useState(false)
    const [text, setText] = useState(q.text)
    const [options, setOptions] = useState([...q.options])
    const [answerIndex, setAnswerIndex] = useState(q.answer_index)
    const [difficulty, setDifficulty] = useState(q.difficulty)
    const [topic, setTopic] = useState(q.topic)
    const [saving, setSaving] = useState(false)

    async function handleSave(e: React.FormEvent) {
      e.preventDefault()
      setSaving(true)
      try {
        await api.put(`/owner/questions/${q.id}`, {
          text, options, answer_index: answerIndex, difficulty, topic
        })
        setEditing(false)
        loadQuestions()
      } catch (err) {
        alert(errorMessage(err))
      } finally {
        setSaving(false)
      }
    }

    if (editing) {
      return (
        <form onSubmit={handleSave} className="rounded-xl border border-indigo-200 p-4 shadow-md bg-indigo-50/30">
          <div className="mb-4 flex items-center justify-between">
            <span className="font-bold text-slate-700">Editing Q{index + 1}</span>
            <div className="flex gap-2">
              <button type="button" onClick={() => setEditing(false)} className="text-xs text-slate-500 hover:text-slate-700">Cancel</button>
              <button type="submit" disabled={saving} className="rounded bg-indigo-600 px-3 py-1 text-xs font-semibold text-white hover:bg-indigo-500">Save</button>
            </div>
          </div>
          
          <div className="grid gap-3 sm:grid-cols-2 mb-3">
            <label className="text-xs font-semibold text-slate-600">
              Difficulty
              <select value={difficulty} onChange={e => setDifficulty(e.target.value)} className="mt-1 block w-full rounded border px-2 py-1 text-sm outline-none focus:border-indigo-500">
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-600">
              Topic
              <input value={topic} onChange={e => setTopic(e.target.value)} required className="mt-1 block w-full rounded border px-2 py-1 text-sm outline-none focus:border-indigo-500" />
            </label>
          </div>

          <label className="block text-xs font-semibold text-slate-600 mb-3">
            Question Text
            <textarea value={text} onChange={e => setText(e.target.value)} required rows={3} className="mt-1 block w-full rounded border px-2 py-1 text-sm outline-none focus:border-indigo-500" />
          </label>

          <p className="text-xs font-semibold text-slate-600 mb-2">Options (Select radio button for correct answer)</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {options.map((opt, optIdx) => (
              <div key={optIdx} className="flex items-center gap-2">
                <input type="radio" name={`correct-${q.id}`} checked={answerIndex === optIdx} onChange={() => setAnswerIndex(optIdx)} className="h-4 w-4 text-indigo-600" />
                <input value={opt} onChange={e => {
                  const newOpts = [...options]
                  newOpts[optIdx] = e.target.value
                  setOptions(newOpts)
                }} required className="flex-1 rounded border px-2 py-1 text-sm outline-none focus:border-indigo-500" />
                <button type="button" onClick={() => {
                  if (options.length <= 2) return alert("Minimum 2 options required")
                  setOptions(options.filter((_, i) => i !== optIdx))
                  if (answerIndex === optIdx) setAnswerIndex(0)
                  else if (answerIndex > optIdx) setAnswerIndex(answerIndex - 1)
                }} className="text-red-500 hover:text-red-700 text-xs">✕</button>
              </div>
            ))}
          </div>
          {options.length < 6 && (
            <button type="button" onClick={() => setOptions([...options, ''])} className="mt-2 text-xs font-semibold text-indigo-600 hover:underline">+ Add Option</button>
          )}
        </form>
      )
    }

    return (
      <div className="group rounded-xl border border-slate-200 p-4 shadow-sm bg-white hover:shadow-md transition">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-600">Q{index + 1}</span>
            <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700 capitalize">{q.difficulty}</span>
            <span className="rounded-full bg-purple-50 px-2 py-0.5 text-xs font-semibold text-purple-700">{q.topic}</span>
          </div>
          <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition" style={{ opacity: 1 }}>
            <button onClick={() => setEditing(true)} className="text-xs text-indigo-600 font-semibold hover:underline">Edit</button>
            <button onClick={() => deleteQuestion(q.id)} className="text-xs text-red-500 font-semibold hover:underline">Delete</button>
          </div>
        </div>
        <p className="whitespace-pre-wrap text-sm font-medium text-slate-800">{q.text}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {q.options.map((opt, optIdx) => (
            <div key={optIdx} className={`rounded-lg border px-3 py-2 text-sm ${optIdx === q.answer_index ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-900' : 'border-slate-100 bg-slate-50 text-slate-600'}`}>
              <span className={`mr-2 inline-block h-5 w-5 text-center text-xs font-bold leading-5 ${optIdx === q.answer_index ? 'text-emerald-700' : 'text-slate-400'}`}>
                {['A', 'B', 'C', 'D', 'E', 'F'][optIdx]}
              </span>
              {opt}
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error) return <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">{error}</p>
  if (levels.length === 0) return <div className="p-6 text-sm text-slate-500">Loading…</div>



  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Generated Question Paper</h1>
      <Card title="Question Paper Details">
        <label className="block text-sm mb-6">
          <span className="font-semibold text-slate-700">Select Level</span>
          <select value={selectedId ?? ''} onChange={(e) => setSelectedId(Number(e.target.value))} className="mt-1.5 block w-full max-w-xs rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100">
            {levels.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </label>

        {loading ? (
          <p className="text-sm text-slate-500">Loading questions...</p>
        ) : questions.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 flex flex-col items-center gap-4">
            <p>No questions generated for this level yet.</p>
            <button 
              onClick={handleGenerate}
              disabled={generating}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-indigo-500 disabled:opacity-75 disabled:cursor-not-allowed"
            >
              {generating ? "Generating..." : "Generate Questions"}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-semibold text-slate-700">Total Questions: {questions.length}</p>
              <div className="flex items-center gap-2">
                <button 
                  onClick={handleGenerate}
                  disabled={generating}
                  className="text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-lg transition disabled:opacity-75 disabled:cursor-not-allowed"
                >
                  {generating ? "Generating..." : "Regenerate Questions"}
                </button>
                <button 
                  onClick={deleteAllQuestions} 
                  disabled={generating}
                  className="text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 px-3 py-1.5 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Delete All Questions
                </button>
              </div>
            </div>
            {questions.map((q, i) => (
              <EditableQuestion key={q.id} q={q} index={i} />
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
