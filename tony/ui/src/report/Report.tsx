// The Report page at /report. Reads the bundle written by scripts/report_bundle.py; needs no API, DB or Ollama.
import { useEffect, useState } from 'react'
import { useTheme } from '../useTheme'
import { Ablation } from './Ablation'
import { Conclusion, References } from './Conclusion'
import { Drill } from './Drill'
import { Errors } from './Errors'
import { reportSettings } from './data'
import { Dataset, Problem, Setup } from './Intro'
import { Results } from './Results'
import type { Bundle } from './types'

const TOC: [string, string][] = [
  ['s1', '1. Problem and scope'], ['s2', '2. Dataset'], ['s3', '3. Evaluation setup'], ['s4', '4. Main results'],
  ['s5', '5. Ablation'], ['s6', '6. Error analysis'], ['s7', '7. Conclusion'], ['appendix', 'All queries'], ['refs', 'References'],
]

export default function Report() {
  const [theme, setTheme] = useTheme()
  const [b, setB] = useState<Bundle | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    document.title = 'Recipe retrieval report'
    fetch('/report.json').then(r => (r.ok ? r.json() : Promise.reject(r.status))).then(setB).catch(() => setError(true))
  }, [])

  useEffect(() => {  // a link like /report?q=q012#appendix scrolls once the bundle has rendered
    if (b && location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView()
  }, [b])

  if (error) return <p className="p-8 text-sm text-danger">Couldn’t load report.json. Build it with <code>uv run python scripts/report_bundle.py</code>.</p>
  if (!b) return <p className="p-8 text-sm text-muted">Loading the report…</p>

  const s = reportSettings(b)
  const next = theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system'
  return (
    <div className="min-h-screen bg-page text-ink">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl items-start justify-between gap-4 px-4 py-5 sm:px-6">
          <div>
            <p className="text-xs text-muted">IS603 · <a href="/" className="underline underline-offset-2 hover:text-ink">search page</a></p>
            <h1 className="mt-1 text-2xl font-semibold">Recipe retrieval: Sparse, Dense and Hybrid search on Shengtao/recipe</h1>
            <p className="mt-2 break-all font-mono text-[11px] text-muted">
              run {b.meta.manifest.report_run.split('/').pop()} · commit {s.git_commit} · query set {s.query_set_sha256.slice(0, 12)} · built {b.meta.built_at.slice(0, 16).replace('T', ' ')} UTC
            </p>
          </div>
          <button className="shrink-0 rounded border border-line px-2 py-1 text-xs text-ink-soft hover:text-ink" onClick={() => setTheme(next)}
            aria-label={`Theme: ${theme}. Switch to ${next}.`}>Theme: {theme}</button>
        </div>
      </header>
      <div className="mx-auto grid max-w-6xl gap-10 grid-cols-1 px-4 py-8 sm:px-6 lg:grid-cols-[11rem_minmax(0,1fr)]">
        <nav aria-label="Sections" className="hidden lg:block">
          <ol className="sticky top-6 space-y-1.5 text-xs">
            {TOC.map(([id, label]) => <li key={id}><a href={`#${id}`} className="text-muted hover:text-ink">{label}</a></li>)}
          </ol>
        </nav>
        <main className="min-w-0 space-y-14">
          <Problem b={b} />
          <Dataset b={b} />
          <Setup b={b} />
          <Results b={b} />
          <Ablation b={b} />
          <Errors b={b} />
          <Conclusion b={b} />
          <Drill b={b} />
          <References />
        </main>
      </div>
    </div>
  )
}
