import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { api, errorMessage } from '../api'
import { Icon } from '../components/AuthLayout'
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from 'recharts'

interface SkillGapReport {
  id: number
  assessment_id: number | null
  overall_summary: string
  readiness: 'READY' | 'DEVELOPING' | 'NOT_READY'
  strengths: string[]
  gaps: Array<{
    topic: string
    score: number
    classification: string
    severity: string
    confidence: string
    trend: string
    reason: string
    priority: number
  }>
  next_level_priorities: Array<{
    topic: string
    reason: string
    prerequisites: string[]
    actions: string[]
  }>
  recommended_plan: string[]
  confidence: string
  created_at: string
}

type PageState = 'loading' | 'no-analysis' | 'has-analysis' | 'generating' | 'error'

const PATHS = {
  arrow: 'M5 12h14m-6-6l6 6-6 6',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z',
  chart: 'M4 20V10M10 20V4M16 20v-8M22 20H2',
  check: 'M5 13l4 4L19 7',
  info: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  ribbon: 'M12 14a6 6 0 100-12 6 6 0 000 12zM8.5 13L7 22l5-3 5 3-1.5-9',
  target: 'M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10 10-4.477 10-10 10zm0-18a8 8 0 100 16 8 8 0 000-16zm0 4a4 4 0 100 8 4 4 0 000-8z',
  clock: 'M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  refresh: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
}

const ico = (name: keyof typeof PATHS, className = 'h-5 w-5') => (
  <Icon className={className}><path strokeLinecap="round" strokeLinejoin="round" d={PATHS[name]} /></Icon>
)

// Animated counter
function AnimatedCounter({ value, duration = 800, suffix = '', prefix = '' }: {
  value: number
  duration?: number
  suffix?: string
  prefix?: string
}) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    const increment = value / (duration / 16)
    let current = 0
    const timer = setInterval(() => {
      current += increment
      if (current >= value) {
        setCount(value)
        clearInterval(timer)
      } else {
        setCount(Math.floor(current))
      }
    }, 16)
    return () => clearInterval(timer)
  }, [value, duration])

  return <span>{prefix}{count}{suffix}</span>
}

// Severity badge
function SeverityBadge({ severity }: { severity: string }) {
  const styles =
    severity === 'HIGH' ? 'bg-red-100 text-red-700 border-red-300' :
    severity === 'MEDIUM' ? 'bg-amber-100 text-amber-700 border-amber-300' :
    'bg-green-100 text-green-700 border-green-300'

  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${styles}`}>
      {severity}
    </span>
  )
}

// Format date
function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffHours < 1) return 'just now'
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// Generation workflow steps
const GENERATION_STEPS = [
  { label: 'Retrieving assessment data', duration: 700 },
  { label: 'Analyzing topic performance', duration: 700 },
  { label: 'Evaluating skill gaps', duration: 700 },
  { label: 'Identifying trends', duration: 700 },
  { label: 'Generating AI insights', duration: 700 },
]

// Generation workflow component
function GenerationWorkflow({ onComplete }: { onComplete?: () => void }) {
  const [currentStep, setCurrentStep] = useState(0)

  useEffect(() => {
    if (currentStep < GENERATION_STEPS.length) {
      const timer = setTimeout(() => {
        setCurrentStep(currentStep + 1)
      }, GENERATION_STEPS[currentStep].duration)
      return () => clearTimeout(timer)
    } else if (onComplete) {
      onComplete()
    }
  }, [currentStep, onComplete])

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex min-h-[60vh] items-center justify-center">
          <div className="w-full max-w-xl">
            <div className="rounded-2xl border border-indigo-200 bg-white p-8 shadow-lg">
              <div className="mb-8 text-center">
                <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100">
                  {ico('sparkle', 'h-8 w-8 text-indigo-600 animate-pulse')}
                </div>
                <h2 className="text-2xl font-bold text-slate-900">AI Skill Analysis</h2>
                <p className="mt-2 text-sm text-slate-600">Processing your performance data</p>
              </div>

              <div className="space-y-3">
                {GENERATION_STEPS.map((step, idx) => (
                  <div
                    key={step.label}
                    className={`flex items-center gap-3 rounded-lg p-3 transition-all ${
                      idx < currentStep ? 'bg-green-50' :
                      idx === currentStep ? 'bg-indigo-50' :
                      'bg-slate-50'
                    }`}
                  >
                    <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                      idx < currentStep ? 'bg-green-500' :
                      idx === currentStep ? 'bg-indigo-500' :
                      'bg-slate-300'
                    }`}>
                      {idx < currentStep ? (
                        <span className="text-white text-xs">✓</span>
                      ) : idx === currentStep ? (
                        <span className="h-2 w-2 animate-pulse rounded-full bg-white"></span>
                      ) : (
                        <span className="h-2 w-2 rounded-full bg-white opacity-50"></span>
                      )}
                    </div>
                    <span className={`text-sm font-medium ${
                      idx <= currentStep ? 'text-slate-900' : 'text-slate-400'
                    }`}>
                      {step.label}
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-6">
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-700 ease-out"
                    style={{ width: `${(currentStep / GENERATION_STEPS.length) * 100}%` }}
                  />
                </div>
                <p className="mt-2 text-center text-xs text-slate-500">
                  This may take a few seconds...
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function SkillAnalysisPage() {
  const [pageState, setPageState] = useState<PageState>('loading')
  const [report, setReport] = useState<SkillGapReport | null>(null)
  const [error, setError] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const generationRef = useRef<Promise<SkillGapReport> | null>(null)

  // Load existing analysis
  useEffect(() => {
    let cancelled = false

    async function loadExisting() {
      try {
        const res = await api.get<SkillGapReport>('/ai/skill-gap/latest')
        if (!cancelled) {
          setReport(res.data)
          setPageState('has-analysis')
        }
      } catch (err) {
        if (!cancelled) {
          if (axios.isAxiosError(err) && err.response?.status === 404) {
            setPageState('no-analysis')
          } else {
            setError(errorMessage(err, 'Could not load analysis'))
            setPageState('error')
          }
        }
      }
    }

    loadExisting()
    return () => { cancelled = true }
  }, [])

  // Run AI analysis
  async function runAnalysis() {
    setIsGenerating(true)
    setPageState('generating')
    setError('')

    try {
      let generation = generationRef.current
      if (!generation) {
        generation = api.post<SkillGapReport>('/ai/skill-gap/analyze').then(res => res.data)
        generationRef.current = generation
      }

      const data = await generation
      setReport(data)
      setPageState('has-analysis')
      generationRef.current = null
    } catch (err) {
      setError(errorMessage(err, 'Analysis generation failed'))
      // If we have previous report, keep showing it
      if (report) {
        setPageState('has-analysis')
      } else {
        setPageState('error')
      }
      generationRef.current = null
    } finally {
      setIsGenerating(false)
    }
  }

  // Loading initial check
  if (pageState === 'loading') {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
          <div className="flex min-h-[60vh] items-center justify-center">
            <div className="text-center">
              <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600"></div>
              <p className="text-sm font-medium text-slate-600">Loading...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Generating state
  if (pageState === 'generating') {
    return <GenerationWorkflow />
  }

  // No analysis state
  if (pageState === 'no-analysis') {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
          <Link to="/student" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition-colors hover:text-indigo-600">
            ← Back to Dashboard
          </Link>
          <div className="mt-8 flex min-h-[60vh] items-center justify-center">
            <div className="w-full max-w-2xl text-center">
              <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-full bg-indigo-100">
                {ico('sparkle', 'h-10 w-10 text-indigo-600')}
              </div>
              <h1 className="mb-3 text-3xl font-bold text-slate-900">AI Skill Analysis</h1>
              <p className="mb-8 text-slate-600">
                Generate a personalized analysis of your performance, skill gaps, and readiness for the next level.
              </p>
              <button
                onClick={runAnalysis}
                disabled={isGenerating}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-8 py-4 text-lg font-semibold text-white shadow-lg transition-all hover:-translate-y-0.5 hover:bg-indigo-700 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50"
              >
                {ico('sparkle', 'h-6 w-6')}
                Run AI Skill Analysis
              </button>
              {error && (
                <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  {error}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Error state (no previous report)
  if (pageState === 'error' && !report) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
          <Link to="/student" className="inline-flex items-center gap-2 text-sm font-medium text-indigo-600 transition-colors hover:text-indigo-700">
            ← Back to Dashboard
          </Link>
          <div className="mt-8 rounded-2xl border border-red-200 bg-white p-8 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-50">
              {ico('info', 'h-8 w-8 text-red-600')}
            </div>
            <h3 className="mb-2 text-lg font-semibold text-slate-900">Analysis Not Available</h3>
            <p className="mb-6 text-sm text-slate-600">{error || 'Complete an assessment to generate your AI skill analysis.'}</p>
            <button
              onClick={runAnalysis}
              disabled={isGenerating}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-6 py-3 text-sm font-semibold text-white transition-all hover:bg-indigo-700 disabled:opacity-50"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Has analysis - show full report
  if (!report) return null

  // Calculate metrics
  const totalGaps = report.gaps.length
  const highPriorityGaps = report.gaps.filter(g => g.severity === 'HIGH').length
  const mediumPriorityGaps = report.gaps.filter(g => g.severity === 'MEDIUM').length
  const averageGapScore = totalGaps > 0 ? Math.round(report.gaps.reduce((sum, g) => sum + g.score, 0) / totalGaps) : 0

  // Prepare chart data
  const topGaps = report.gaps.slice(0, 6).sort((a, b) => a.score - b.score)

  // Radar data
  const radarData = report.gaps.length >= 3 ? report.gaps.slice(0, 6).map(g => ({
    topic: g.topic.length > 12 ? g.topic.substring(0, 12) + '...' : g.topic,
    fullTopic: g.topic,
    score: g.score,
  })) : []

  // Severity distribution
  const severityCounts = report.gaps.reduce((acc, g) => {
    acc[g.severity] = (acc[g.severity] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const donutData = Object.entries(severityCounts).map(([name, value]) => ({ name, value }))

  const COLORS = { HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#10b981' }

  // Readiness status parsing
  const readinessText = report.readiness.replace('_', ' ')
  const isReady = readinessText.includes('READY') && !readinessText.includes('NOT')
  const isDeveloping = readinessText.includes('DEVELOPING')
  const statusColor = isReady ? 'text-green-600' : isDeveloping ? 'text-amber-600' : 'text-red-600'
  const statusBg = isReady ? 'bg-green-50' : isDeveloping ? 'bg-amber-50' : 'bg-red-50'
  const statusBorder = isReady ? 'border-green-200' : isDeveloping ? 'border-amber-200' : 'border-red-200'

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <Link to="/student" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition-colors hover:text-indigo-600">
            ← Back to Dashboard
          </Link>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="flex h-2 w-2 rounded-full bg-green-500"></span>
              <span>Updated {formatDate(report.created_at)}</span>
            </div>
            <button
              onClick={runAnalysis}
              disabled={isGenerating}
              className="inline-flex items-center gap-2 rounded-lg border border-indigo-600 bg-white px-4 py-2 text-sm font-semibold text-indigo-600 transition-all hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {ico('refresh', 'h-4 w-4')}
              {isGenerating ? 'Analyzing...' : 'Refresh Analysis'}
            </button>
          </div>
        </div>

        {/* Error banner if refresh failed */}
        {error && pageState === 'has-analysis' && (
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-start gap-3">
              {ico('info', 'h-5 w-5 text-amber-600 shrink-0')}
              <div className="flex-1">
                <p className="text-sm font-medium text-amber-900">Analysis refresh failed</p>
                <p className="text-xs text-amber-700">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Hero Intelligence Section */}
        <div className="mb-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="grid gap-6 p-6 lg:grid-cols-[1fr,320px] lg:gap-8 lg:p-8">
            {/* Left: Content */}
            <div className="min-w-0">
              <div className="mb-4 flex items-center gap-2">
                {ico('sparkle', 'h-5 w-5 text-indigo-600')}
                <h1 className="text-xs font-bold uppercase tracking-wider text-indigo-600">AI Skill Intelligence</h1>
              </div>

              {/* Status */}
              <div className={`mb-4 inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 ${statusBorder} ${statusBg}`}>
                <span className={`text-2xl font-bold leading-none ${statusColor}`}>{readinessText}</span>
              </div>

              {/* Summary */}
              <p className="mb-6 text-sm leading-relaxed text-slate-700">{report.overall_summary}</p>

              {/* Metadata */}
              <div className="flex flex-wrap gap-4 text-sm text-slate-600">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-900">Confidence:</span>
                  <span className="font-semibold text-indigo-600">{report.confidence}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-900">Gaps:</span>
                  <span className="font-semibold">{totalGaps}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-900">Strengths:</span>
                  <span className="font-semibold">{report.strengths.length}</span>
                </div>
              </div>
            </div>

            {/* Right: Readiness Visualization */}
            <div className={`flex flex-col items-center justify-center rounded-xl border ${statusBorder} ${statusBg} p-6`}>
              <div className="relative">
                <svg className="h-36 w-36 -rotate-90 transform" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r="50" stroke="#e2e8f0" strokeWidth="8" fill="none" />
                  <circle
                    cx="60"
                    cy="60"
                    r="50"
                    stroke={isReady ? '#10b981' : isDeveloping ? '#f59e0b' : '#ef4444'}
                    strokeWidth="8"
                    fill="none"
                    strokeDasharray={`${2 * Math.PI * 50}`}
                    strokeDashoffset={`${2 * Math.PI * 50 * (1 - averageGapScore / 100)}`}
                    strokeLinecap="round"
                    className="transition-all duration-1000"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
                  <div className={`text-3xl font-bold leading-none ${statusColor}`}>{averageGapScore}%</div>
                  <div className="mt-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">Avg Score</div>
                </div>
              </div>
              <div className="mt-4 text-center">
                <div className="text-xs font-medium text-slate-500">Overall Status</div>
                <div className={`text-sm font-bold ${statusColor}`}>{readinessText}</div>
              </div>
            </div>
          </div>
        </div>

        {/* KPI Strip */}
        <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="animate-fadeIn rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md">
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">Latest Score</div>
            <div className="text-2xl font-bold text-slate-900"><AnimatedCounter value={averageGapScore} suffix="%" /></div>
            <div className="mt-1 text-xs text-slate-500">Average performance</div>
          </div>
          <div className="animate-fadeIn rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md" style={{ animationDelay: '100ms' }}>
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">Total Gaps</div>
            <div className="text-2xl font-bold text-slate-900"><AnimatedCounter value={totalGaps} /></div>
            <div className="mt-1 text-xs text-slate-500">Topics analyzed</div>
          </div>
          <div className="animate-fadeIn rounded-xl border border-red-200 bg-red-50 p-4 shadow-sm transition-shadow hover:shadow-md" style={{ animationDelay: '200ms' }}>
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-red-600">High Priority</div>
            <div className="text-2xl font-bold text-red-600"><AnimatedCounter value={highPriorityGaps} /></div>
            <div className="mt-1 text-xs text-red-600">Critical gaps</div>
          </div>
          <div className="animate-fadeIn rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-sm transition-shadow hover:shadow-md" style={{ animationDelay: '300ms' }}>
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-amber-600">Medium Priority</div>
            <div className="text-2xl font-bold text-amber-600"><AnimatedCounter value={mediumPriorityGaps} /></div>
            <div className="mt-1 text-xs text-amber-600">Needs attention</div>
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          {/* Left Column */}
          <div className="space-y-8 lg:col-span-8">
            {/* Performance by Topic */}
            {topGaps.length > 0 && (
              <div className="animate-fadeIn rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" style={{ animationDelay: '400ms' }}>
                <div className="mb-6">
                  <div className="flex items-center gap-2">
                    {ico('chart', 'h-5 w-5 text-indigo-600')}
                    <h2 className="text-lg font-bold text-slate-900">Performance by Topic</h2>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">Current skill levels across key topics</p>
                </div>
                <div className="space-y-4">
                  {topGaps.map((gap, idx) => (
                    <div key={gap.topic} className="group" style={{ animationDelay: `${(idx + 5) * 80}ms` }}>
                      <div className="mb-2 flex items-baseline justify-between gap-3">
                        <div className="flex min-w-0 flex-1 items-center gap-2">
                          <span className="truncate text-sm font-semibold text-slate-900">{gap.topic}</span>
                          <SeverityBadge severity={gap.severity} />
                        </div>
                        <span className="shrink-0 text-sm font-bold tabular-nums text-slate-900">{gap.score}%</span>
                      </div>
                      <div className="relative h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full transition-all duration-1000 ${
                            gap.severity === 'HIGH' ? 'bg-red-500' :
                            gap.severity === 'MEDIUM' ? 'bg-amber-500' :
                            'bg-green-500'
                          }`}
                          style={{ width: `${gap.score}%`, transitionDelay: `${(idx + 5) * 80}ms` }}
                        />
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                        <span className={`font-medium ${
                          gap.trend === 'IMPROVING' ? 'text-green-600' :
                          gap.trend === 'DECLINING' ? 'text-red-600' :
                          'text-slate-500'
                        }`}>
                          {gap.trend === 'IMPROVING' ? '↗' : gap.trend === 'DECLINING' ? '↘' : '→'} {gap.trend.toLowerCase()}
                        </span>
                        <span>•</span>
                        <span>{gap.classification}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Priority Skill Gaps */}
            {report.gaps.length > 0 && (
              <div className="animate-fadeIn rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" style={{ animationDelay: '500ms' }}>
                <div className="mb-6">
                  <div className="flex items-center gap-2">
                    {ico('target', 'h-5 w-5 text-red-600')}
                    <h2 className="text-lg font-bold text-slate-900">Priority Skill Gaps</h2>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">Topics requiring immediate attention with AI reasoning</p>
                </div>
                <div className="space-y-4">
                  {report.gaps.slice(0, 3).map((gap, idx) => (
                    <div
                      key={gap.topic}
                      className="rounded-xl border border-slate-200 bg-slate-50 p-5"
                      style={{ animationDelay: `${(idx + 6) * 100}ms` }}
                    >
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <h3 className="font-bold text-slate-900">{gap.topic}</h3>
                        <SeverityBadge severity={gap.severity} />
                      </div>
                      <div className="mb-3 grid grid-cols-2 gap-3 text-xs">
                        <div>
                          <div className="text-slate-500">Current Score</div>
                          <div className="text-lg font-bold text-slate-900">{gap.score}%</div>
                        </div>
                        <div>
                          <div className="text-slate-500">Trend</div>
                          <div className={`text-sm font-semibold ${
                            gap.trend === 'IMPROVING' ? 'text-green-600' :
                            gap.trend === 'DECLINING' ? 'text-red-600' :
                            'text-slate-600'
                          }`}>
                            {gap.trend === 'IMPROVING' ? '↗' : gap.trend === 'DECLINING' ? '↘' : '→'} {gap.trend}
                          </div>
                        </div>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-white p-3">
                        <div className="mb-1 text-xs font-bold uppercase tracking-wider text-indigo-600">Why It Matters</div>
                        <p className="text-xs leading-relaxed text-slate-700">{gap.reason}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column */}
          <div className="space-y-8 lg:col-span-4">
            {/* Donut Distribution */}
            {donutData.length > 0 && (
              <div className="animate-fadeIn rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" style={{ animationDelay: '600ms' }}>
                <div className="mb-4">
                  <h3 className="text-sm font-bold text-slate-900">Gap Distribution</h3>
                  <p className="text-xs text-slate-500">By severity level</p>
                </div>
                <div className="relative flex flex-col items-center">
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={donutData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {donutData.map((entry) => (
                          <Cell key={entry.name} fill={COLORS[entry.name as keyof typeof COLORS]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="pointer-events-none absolute left-1/2 top-[100px] -translate-x-1/2 -translate-y-1/2 text-center">
                    <div className="text-2xl font-bold text-slate-900">{totalGaps}</div>
                    <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">Total</div>
                  </div>
                  <div className="mt-4 space-y-2">
                    {donutData.map(item => (
                      <div key={item.name} className="flex items-center gap-3 text-xs">
                        <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COLORS[item.name as keyof typeof COLORS] }}></div>
                        <span className="font-medium text-slate-700">{item.name}</span>
                        <span className="font-bold text-slate-900">{item.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Radar Chart */}
            {radarData.length > 0 ? (
              <div className="animate-fadeIn rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" style={{ animationDelay: '700ms' }}>
                <div className="mb-4">
                  <h3 className="text-sm font-bold text-slate-900">Skill Profile</h3>
                  <p className="text-xs text-slate-500">Multi-dimensional view</p>
                </div>
                <ResponsiveContainer width="100%" height={240}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#e2e8f0" />
                    <PolarAngleAxis dataKey="topic" tick={{ fill: '#64748b', fontSize: 10 }} />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 9 }} />
                    <Radar dataKey="score" stroke="#6366f1" fill="#818cf8" fillOpacity={0.4} />
                    <Tooltip content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = radarData.find(d => d.topic === payload[0].payload.topic)
                        return (
                          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
                            <p className="text-xs font-semibold text-slate-900">{data?.fullTopic}</p>
                            <p className="text-xs text-slate-600">Score: {payload[0].value}%</p>
                          </div>
                        )
                      }
                      return null
                    }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="animate-fadeIn rounded-2xl border border-slate-200 bg-slate-50 p-8 text-center" style={{ animationDelay: '700ms' }}>
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
                  {ico('ribbon', 'h-6 w-6 text-slate-400')}
                </div>
                <p className="text-sm font-medium text-slate-600">Building skill profile</p>
                <p className="text-xs text-slate-500">Complete more assessments</p>
              </div>
            )}

            {/* Strengths */}
            {report.strengths.length > 0 && (
              <div className="animate-fadeIn rounded-2xl border border-green-200 bg-gradient-to-br from-green-50 to-white p-6 shadow-sm" style={{ animationDelay: '800ms' }}>
                <div className="mb-4 flex items-center gap-2">
                  {ico('check', 'h-5 w-5 text-green-600')}
                  <h3 className="text-sm font-bold text-slate-900">Your Strengths</h3>
                </div>
                <div className="space-y-2">
                  {report.strengths.slice(0, 4).map((strength, idx) => (
                    <div key={strength} className="flex items-start gap-2" style={{ animationDelay: `${(idx + 10) * 60}ms` }}>
                      <span className="mt-0.5 text-green-600">✓</span>
                      <p className="text-xs leading-relaxed text-slate-700">{strength}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* AI Insights */}
        <div className="mt-8 animate-fadeIn rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 via-purple-50 to-white p-8 shadow-sm" style={{ animationDelay: '900ms' }}>
          <div className="mb-6 flex items-center gap-3">
            {ico('sparkle', 'h-6 w-6 text-indigo-600')}
            <h2 className="text-xl font-bold text-slate-900">AI Insights & Recommendations</h2>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-2 text-xs font-bold uppercase tracking-wider text-indigo-600">Key Finding</div>
              <p className="text-sm leading-relaxed text-slate-700">
                {report.gaps.length > 0
                  ? `${report.gaps[0].topic} is ${report.gaps[0].severity === 'HIGH' ? 'the highest priority' : 'a priority'} gap at ${report.gaps[0].score}%.`
                  : 'Strong performance across all assessed topics.'}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-2 text-xs font-bold uppercase tracking-wider text-purple-600">Why It Matters</div>
              <p className="text-sm leading-relaxed text-slate-700">
                {report.gaps.length > 0 ? report.gaps[0].reason : 'Continue your current preparation strategy.'}
              </p>
            </div>
            {report.next_level_priorities.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-2 text-xs font-bold uppercase tracking-wider text-amber-600">Recommended Action</div>
                <p className="text-sm font-semibold text-slate-900">{report.next_level_priorities[0].topic}</p>
                <p className="mt-1 text-sm leading-relaxed text-slate-700">{report.next_level_priorities[0].reason}</p>
              </div>
            )}
          </div>
        </div>

        {/* Learning Roadmap */}
        {report.recommended_plan.length > 0 && (
          <div className="mt-8 animate-fadeIn rounded-2xl border border-slate-200 bg-white p-8 shadow-sm" style={{ animationDelay: '1000ms' }}>
            <div className="mb-8">
              <h2 className="text-xl font-bold text-slate-900">Personalized Learning Roadmap</h2>
              <p className="mt-1 text-sm text-slate-600">Your step-by-step path to improvement</p>
            </div>
            <div className="relative space-y-6">
              {report.recommended_plan.map((step, idx) => (
                <div key={step} className="relative flex gap-4" style={{ animationDelay: `${(idx + 12) * 100}ms` }}>
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-bold text-white shadow-md">
                    {idx + 1}
                  </div>
                  {idx < report.recommended_plan.length - 1 && (
                    <div className="absolute left-5 top-10 h-full w-0.5 bg-indigo-100"></div>
                  )}
                  <div className="flex-1 rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <p className="text-sm font-medium leading-relaxed text-slate-900">{step}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Next-Level Preparation */}
        {report.next_level_priorities.length > 0 && (
          <div className="mt-8 animate-fadeIn rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-8 shadow-sm" style={{ animationDelay: '1100ms' }}>
            <div className="mb-6">
              <h2 className="text-xl font-bold text-slate-900">Next-Level Preparation</h2>
              <p className="mt-1 text-sm text-slate-600">Essential topics for advancing to the next level</p>
            </div>
            <div className="space-y-6">
              {report.next_level_priorities.map((item, idx) => (
                <div key={item.topic} className="rounded-xl border border-amber-200 bg-white p-6" style={{ animationDelay: `${(idx + 14) * 80}ms` }}>
                  <h3 className="mb-2 font-bold text-slate-900">{item.topic}</h3>
                  <p className="mb-4 text-sm leading-relaxed text-slate-700">{item.reason}</p>
                  {item.actions.length > 0 && (
                    <div>
                      <div className="mb-2 text-xs font-bold uppercase tracking-wider text-amber-700">Action Items</div>
                      <ul className="space-y-2">
                        {item.actions.map(action => (
                          <li key={action} className="flex items-start gap-2 text-xs text-slate-700">
                            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-100 text-[10px] font-bold text-amber-700">▸</span>
                            <span className="flex-1">{action}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
