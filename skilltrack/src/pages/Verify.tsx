import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import Card from '../components/Card'
import { useFetch } from '../useFetch'

interface Verification {
  valid: boolean
  code?: string
  holder?: string
  credential?: string
  issued_at?: string
  status?: string
}

/** Public page (no login): confirms whether a certificate ID is genuine. */
export default function Verify() {
  const { code = '' } = useParams()
  const result = useFetch<Verification>(`/verify/${encodeURIComponent(code)}`)
  const v = result.data

  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const isMobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)

  useEffect(() => {
    if (!v?.valid || !v.code) return
    let url: string | null = null
    let cancelled = false
    api.get<Blob>(`/verify/${encodeURIComponent(v.code)}/pdf`, { responseType: 'blob' })
      .then((r) => { if (!cancelled) { url = URL.createObjectURL(r.data); setPdfUrl(url) } })
      .catch(() => {}) // silently fall back — no preview, just the details
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url) }
  }, [v?.valid, v?.code])

  return (
    <div className="flex min-h-screen items-start justify-center bg-slate-50 p-4 pt-10 dark:bg-slate-950">
      <div className="w-full max-w-2xl space-y-4">
        <h1 className="text-center text-2xl font-bold text-indigo-600 dark:text-indigo-400">SkillTrack</h1>

        <Card title="Certificate verification">
          {result.loading && <p className="text-sm text-slate-500">Checking…</p>}
          {result.error && <p className="text-sm text-red-600">{result.error}</p>}
          {v && !v.valid && (
            <>
              <p className="text-lg font-semibold text-red-600">Certificate not valid</p>
              <p className="mt-1 text-sm text-slate-500">
                The certificate ID <span className="font-mono">{code}</span> is unknown or invalid.
              </p>
            </>
          )}
          {v?.valid && (
            <>
              <p className="text-lg font-semibold text-emerald-600">✓ Certificate Verified</p>
              <dl className="mt-3 space-y-2 text-sm">
                <div><dt className="text-xs uppercase text-slate-500">Status</dt><dd className="font-medium text-emerald-600">{v.status}</dd></div>
                <div><dt className="text-xs uppercase text-slate-500">Awarded to</dt><dd className="font-medium">{v.holder}</dd></div>
                <div><dt className="text-xs uppercase text-slate-500">Domain</dt><dd className="font-medium">{v.credential}</dd></div>
                <div>
                  <dt className="text-xs uppercase text-slate-500">Issue Date</dt>
                  <dd>{new Date(v.issued_at!).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}</dd>
                </div>
                <div><dt className="text-xs uppercase text-slate-500">Certificate ID</dt><dd className="font-mono">{v.code}</dd></div>
              </dl>

              {/* Inline PDF preview */}
              {pdfUrl && !isMobile && (
                <div className="mt-4 overflow-hidden rounded-xl border border-slate-200">
                  <iframe
                    src={pdfUrl}
                    title="Certificate preview"
                    className="w-full border-0"
                    style={{ height: '480px' }}
                  />
                </div>
              )}
              {pdfUrl && isMobile && (
                <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50 px-4 py-3 text-center text-sm text-indigo-700">
                  PDF preview not available on mobile.
                  <a href={pdfUrl} target="_blank" rel="noopener noreferrer"
                    className="ml-2 font-semibold underline">
                    Open in new tab
                  </a>
                </div>
              )}
            </>
          )}
        </Card>

        <p className="text-center text-sm">
          <Link to="/login" className="text-indigo-600 hover:underline">Go to SkillTrack</Link>
        </p>
      </div>
    </div>
  )
}
