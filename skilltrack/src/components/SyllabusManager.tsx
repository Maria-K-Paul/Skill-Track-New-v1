import { useState, useEffect } from 'react'
import { api, errorMessage } from '../api'

interface Subtopic {
  id?: number
  name: string
  weightage: number
}

interface Topic {
  id?: number
  name: string
  weightage: number
  subtopics: Subtopic[]
}

interface BloomRatio {
  remember: number
  understand: number
  apply: number
  analyze: number
  evaluate: number
  create: number
}

interface SyllabusManagerProps {
  levelId: number
  levelName: string
  initialTopics: Topic[]
  initialBloom: BloomRatio
  onSaved: () => Promise<void>
  generationStatus: string
}

const inputClass = 'rounded-lg border border-slate-200 px-2 py-1.5 text-sm outline-none transition focus:border-indigo-500'
const primaryBtn = 'rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-indigo-500 disabled:opacity-50'
const secondaryBtn = 'rounded-xl bg-slate-100 px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-200'

const BLOOM_KEYS: (keyof BloomRatio)[] = ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create']
const BLOOM_STYLE: Record<keyof BloomRatio, { bar: string; accent: string; chip: string }> = {
  remember: { bar: 'bg-emerald-400', accent: 'accent-emerald-500', chip: 'bg-emerald-50 text-emerald-700' },
  understand: { bar: 'bg-blue-400', accent: 'accent-blue-500', chip: 'bg-blue-50 text-blue-700' },
  apply: { bar: 'bg-indigo-400', accent: 'accent-indigo-500', chip: 'bg-indigo-50 text-indigo-700' },
  analyze: { bar: 'bg-violet-400', accent: 'accent-violet-500', chip: 'bg-violet-50 text-violet-700' },
  evaluate: { bar: 'bg-amber-400', accent: 'accent-amber-500', chip: 'bg-amber-50 text-amber-700' },
  create: { bar: 'bg-rose-400', accent: 'accent-rose-500', chip: 'bg-rose-50 text-rose-700' },
}

export default function SyllabusManager({ levelId, levelName, initialTopics, initialBloom, onSaved, generationStatus }: SyllabusManagerProps) {
  const [topics, setTopics] = useState<Topic[]>([])
  const [bloom, setBloom] = useState<BloomRatio>({ remember: 100, understand: 0, apply: 0, analyze: 0, evaluate: 0, create: 0 })
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  useEffect(() => {
    setTopics(initialTopics || [])
    setBloom(initialBloom || { remember: 100, understand: 0, apply: 0, analyze: 0, evaluate: 0, create: 0 })
  }, [initialTopics, initialBloom, levelId])

  const addTopic = () => {
    setTopics([...topics, { name: '', weightage: 0, subtopics: [] }])
  }

  const updateTopic = (index: number, field: keyof Topic, value: any) => {
    const newTopics = [...topics]
    newTopics[index] = { ...newTopics[index], [field]: value }
    setTopics(newTopics)
  }

  const removeTopic = (index: number) => {
    setTopics(topics.filter((_, i) => i !== index))
  }

  const addSubtopic = (topicIndex: number) => {
    const newTopics = [...topics]
    newTopics[topicIndex].subtopics.push({ name: '', weightage: 0 })
    setTopics(newTopics)
  }

  const updateSubtopic = (topicIndex: number, subIndex: number, field: keyof Subtopic, value: any) => {
    const newTopics = [...topics]
    newTopics[topicIndex].subtopics[subIndex] = { ...newTopics[topicIndex].subtopics[subIndex], [field]: value }
    setTopics(newTopics)
  }

  const removeSubtopic = (topicIndex: number, subIndex: number) => {
    const newTopics = [...topics]
    newTopics[topicIndex].subtopics = newTopics[topicIndex].subtopics.filter((_, i) => i !== subIndex)
    setTopics(newTopics)
  }

  const saveSyllabus = async (e?: React.SyntheticEvent) => {
    if (e) e.preventDefault()
    setError('')
    setMsg('')
    
    // Validations
    const topicWeightSum = topics.reduce((acc, t) => acc + (t.weightage || 0), 0)
    if (topics.length > 0 && topicWeightSum !== 100) {
      setError(`Topic weightages must sum to 100%. Currently: ${topicWeightSum}%`)
      return
    }
    
    for (const t of topics) {
      const subWeightSum = t.subtopics.reduce((acc, st) => acc + (st.weightage || 0), 0)
      if (t.subtopics.length > 0 && subWeightSum !== 100) {
        setError(`Subtopic weightages for topic '${t.name}' must sum to 100%. Currently: ${subWeightSum}%`)
        return
      }
      if (t.subtopics.length === 0) {
        setError(`Topic '${t.name}' must have at least one subtopic.`)
        return
      }
    }
    
    const bloomSum = Object.values(bloom).reduce((acc, val) => acc + (val || 0), 0)
    if (bloomSum !== 100) {
      setError(`Bloom level ratio must sum to 100%. Currently: ${bloomSum}%`)
      return
    }

    try {
      await api.put(`/owner/levels/${levelId}/syllabus`, { topics, bloom_level_ratio: bloom })
      setMsg('Syllabus and Bloom ratio saved successfully.')
      await onSaved()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const statusColors: Record<string, string> = {
    idle: 'bg-slate-100 text-slate-700',
    generating: 'bg-amber-100 text-amber-700 animate-pulse',
    completed: 'bg-emerald-100 text-emerald-700',
    failed: 'bg-rose-100 text-rose-700'
  }

  return (
    <div className="mt-6 border-t border-slate-100 pt-6">
      
      {/* Bloom Section */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-slate-800">Bloom's Taxonomy Configuration for {levelName}</h3>
        <div className="flex items-center gap-2 text-sm font-semibold">
          Status: 
          <span className={`px-2 py-1 rounded-full text-xs ${statusColors[generationStatus] || statusColors.idle}`}>
            {generationStatus.toUpperCase()}
          </span>
        </div>
      </div>
      
      <div className="mb-8 rounded-xl bg-slate-50/50 p-4 border border-slate-100">
        <div className="flex items-center justify-between mb-3">
          <p className="font-semibold text-slate-700 text-sm">Bloom's Level Ratios (%)</p>
          <span className={`text-xs font-bold ${Object.values(bloom).reduce((a, b) => a + (b || 0), 0) === 100 ? 'text-emerald-600' : 'text-red-500'}`}>
            Total: {Object.values(bloom).reduce((a, b) => a + (b || 0), 0)}%
          </span>
        </div>
        
        {/* live preview of the mix */}
        <div className="flex h-3 overflow-hidden rounded-full bg-slate-200">
          {BLOOM_KEYS.map((k) => <div key={k} className={`${BLOOM_STYLE[k].bar} transition-all duration-300`} style={{ width: `${Math.min(bloom[k] || 0, 100)}%` }} />)}
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3 md:grid-cols-6">
          {BLOOM_KEYS.map((k) => (
            <div key={k} className="rounded-2xl border border-slate-200 p-4 text-sm shadow-sm bg-white hover:shadow-md transition">
              <div className="flex items-center justify-between">
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${BLOOM_STYLE[k].chip}`}>{k}</span>
                <span className="text-base font-bold text-slate-700">{bloom[k] || 0}%</span>
              </div>
              <input
                type="range" min={0} max={100} step={5} value={bloom[k] || 0}
                onChange={(e) => {
                  setBloom({ ...bloom, [k]: Number(e.target.value) });
                  setError('');
                  setMsg('');
                }}
                className={`mt-4 w-full ${BLOOM_STYLE[k].accent}`}
              />
            </div>
          ))}
        </div>
        <div className="mt-5 flex justify-end">
          <button type="button" onClick={saveSyllabus} className={primaryBtn}>Save Bloom Ratio</button>
        </div>
      </div>

      {/* Syllabus Section */}
      <h3 className="text-lg font-bold text-slate-800 mb-4 border-t border-slate-100 pt-6">Syllabus Topics for {levelName}</h3>
      
      <div className="space-y-4">
        {topics.map((topic, tIdx) => (
          <div key={tIdx} className="rounded-xl border border-slate-200 p-4 shadow-sm bg-white">
            <div className="flex items-center gap-3 mb-3">
              <span className="font-bold text-slate-400 text-lg">{tIdx + 1}.</span>
              <input 
                placeholder="Topic Name" 
                value={topic.name} 
                onChange={(e) => updateTopic(tIdx, 'name', e.target.value)} 
                className={`${inputClass} flex-1`}
                required
              />
              <div className="flex items-center gap-2 w-32">
                <input 
                  type="number" min="1" max="100" 
                  value={topic.weightage || ''} 
                  onChange={(e) => updateTopic(tIdx, 'weightage', Number(e.target.value))} 
                  className={`${inputClass} w-16`} 
                  placeholder="%"
                  required
                />
                <span className="text-sm text-slate-500">%</span>
              </div>
              <button type="button" onClick={() => removeTopic(tIdx)} className="text-red-500 hover:text-red-700 ml-2">Delete</button>
            </div>
            
            <div className="ml-8 space-y-2 border-l-2 border-slate-100 pl-4">
              {topic.subtopics.map((sub, sIdx) => (
                <div key={sIdx} className="flex items-center gap-2">
                  <input 
                    placeholder="Subtopic Name" 
                    value={sub.name} 
                    onChange={(e) => updateSubtopic(tIdx, sIdx, 'name', e.target.value)} 
                    className={`${inputClass} flex-1 text-xs`}
                    required
                  />
                  <input 
                    type="number" min="1" max="100" 
                    value={sub.weightage || ''} 
                    onChange={(e) => updateSubtopic(tIdx, sIdx, 'weightage', Number(e.target.value))} 
                    className={`${inputClass} w-16 text-xs`} 
                    placeholder="%"
                    required
                  />
                  <span className="text-xs text-slate-500">%</span>
                  <button type="button" onClick={() => removeSubtopic(tIdx, sIdx)} className="text-red-400 hover:text-red-600 text-xs">✕</button>
                </div>
              ))}
              <button type="button" onClick={() => addSubtopic(tIdx)} className="text-xs text-indigo-600 font-semibold hover:underline mt-1">+ Add subtopic</button>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between">
        <button type="button" onClick={addTopic} className={secondaryBtn}>+ Add Topic</button>
        <div className="flex items-center gap-3">
          {error && <p className="text-sm font-medium text-red-600">{error}</p>}
          {msg && <p className="text-sm font-medium text-emerald-600">{msg}</p>}
          <button type="button" onClick={saveSyllabus} className={primaryBtn}>Save Syllabus</button>
        </div>
      </div>
    </div>
  )
}
