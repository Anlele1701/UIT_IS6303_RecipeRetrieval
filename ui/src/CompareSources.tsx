import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ApiError, getActiveConditions,
  type ActiveConditionsResult, type ConditionRef, type ConditionSource, type DietPlan,
} from './api'

const SOURCES: { id: ConditionSource; name: string; how: string }[] = [
  { id: 'sql', name: 'SQL', how: 'Keyed lookup in the tables. What /recommend uses. No embeddings, no LLM.' },
  { id: 'tree', name: 'Tree', how: 'The LLM reads only a table of contents, picks sections, then lists conditions from them. No vectors.' },
  { id: 'dense', name: 'Dense', how: 'The record is cut into fixed pieces, the 4 closest to a question by embedding go to the LLM.' },
]

type Run =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; data: ActiveConditionsResult; ms: number }

type Runs = Record<ConditionSource, Run>

const IDLE: Runs = { sql: { status: 'idle' }, tree: { status: 'idle' }, dense: { status: 'idle' } }

const message = (e: unknown) => (e instanceof ApiError ? e.message : String(e))

/** Short condition name: drop the SNOMED type in brackets at the end, e.g. "(disorder)". */
const plain = (description: string) => description.replace(/\s*\([^()]*\)\s*$/, '')

function Cell({ run, found, active }: { run: Run; found: boolean; active: boolean }) {
  if (run.status === 'loading') return <span className="text-muted">…</span>
  if (run.status !== 'done') return <span className="text-muted">–</span>
  if (found && active) return <span className="font-medium text-ok" title="Found, and active in the tables">✓ found</span>
  if (found) return <span className="font-medium text-danger" title="Returned, but the tables do not call it active">✗ extra</span>
  if (active) return <span className="font-medium text-danger" title="Active in the tables, not returned">✗ missed</span>
  return <span className="text-muted">–</span>
}

export default function CompareSources({ patientId, plan }: { patientId: string; plan: DietPlan }) {
  const [runs, setRuns] = useState<Runs>(IDLE)
  const controller = useRef<AbortController | null>(null)
  const running = Object.values(runs).some(r => r.status === 'loading')

  useEffect(() => () => controller.current?.abort(), [])

  const start = async () => {
    controller.current?.abort()
    const ctrl = (controller.current = new AbortController())
    setRuns({ sql: { status: 'loading' }, tree: { status: 'idle' }, dense: { status: 'idle' } })
    // One at a time: the local model serves one request at a time anyway, and each answer shows as soon as it is ready.
    for (const { id } of SOURCES) {
      setRuns(prev => ({ ...prev, [id]: { status: 'loading' } }))
      const t0 = performance.now()
      try {
        const data = await getActiveConditions(patientId, id, ctrl.signal)
        if (ctrl.signal.aborted) return
        setRuns(prev => ({ ...prev, [id]: { status: 'done', data, ms: performance.now() - t0 } }))
      } catch (e) {
        if (ctrl.signal.aborted) return
        setRuns(prev => ({ ...prev, [id]: { status: 'error', message: message(e) } }))
      }
    }
  }

  const filterCodes = useMemo(
    () => new Set(plan.evidence.flatMap(l => l.conditions.map(c => c.code))),
    [plan],
  )

  const done = (id: ConditionSource) => (runs[id].status === 'done' ? (runs[id] as Extract<Run, { status: 'done' }>) : null)

  // The answer key comes with every response; take it from the first source that has answered.
  const truth = useMemo<ConditionRef[]>(() => {
    for (const s of SOURCES) {
      const r = runs[s.id]
      if (r.status === 'done') return r.data.sql_conditions
    }
    return []
  }, [runs])
  const truthCodes = useMemo(() => new Set(truth.map(c => c.code)), [truth])

  // Rows: every active condition, then whatever a source returned that the tables do not call active.
  const rows = useMemo(() => {
    const byCode = new Map<string, string>()
    for (const c of truth) byCode.set(c.code, c.description)
    const extras = new Map<string, string>()
    for (const id of ['tree', 'dense'] as const) {
      const r = runs[id]
      if (r.status !== 'done') continue
      for (const c of r.data.conditions) if (!byCode.has(c.code)) extras.set(c.code, c.description)
    }
    const sorted = (m: Map<string, string>) => [...m].sort((a, b) => plain(a[1]).localeCompare(plain(b[1])))
    // Conditions that set a Filter first: those are the ones a miss would cost the patient.
    const active = sorted(byCode).sort((a, b) => Number(filterCodes.has(b[0])) - Number(filterCodes.has(a[0])))
    return [...active, ...sorted(extras)]
  }, [runs, truth, filterCodes])

  const foundCodes = (id: ConditionSource) => new Set(done(id)?.data.conditions.map(c => c.code) ?? [])
  const stats = (id: ConditionSource) => {
    const d = done(id)
    if (!d) return null
    const found = foundCodes(id)
    const hit = [...truthCodes].filter(c => found.has(c)).length
    const filters = [...filterCodes]
    return {
      hit,
      extra: [...found].filter(c => !truthCodes.has(c)).length,
      filterHit: filters.filter(c => found.has(c)).length,
      filterTotal: filters.length,
      d,
    }
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-wide text-ink uppercase">Compare where the conditions come from</h2>
        <button
          type="button"
          onClick={start}
          disabled={running}
          className="rounded-md border border-line bg-page px-3 py-1.5 text-sm font-medium text-ink hover:border-muted disabled:cursor-not-allowed disabled:opacity-40"
        >
          {running ? 'Running…' : Object.values(runs).some(r => r.status !== 'idle') ? 'Run again' : 'Run comparison'}
        </button>
      </div>
      <p className="mb-3 text-sm text-muted">
        For demonstration only: recommendations always use SQL. Tree and Dense read this patient's text record
        with the LLM, which can take about 30 seconds each.
      </p>

      <ul className="mb-3 grid gap-2 text-xs text-ink-soft sm:grid-cols-3">
        {SOURCES.map(s => (
          <li key={s.id} className="rounded-md border border-line px-3 py-2">
            <b className="font-medium text-ink">{s.name}</b>: {s.how}
          </li>
        ))}
      </ul>

      {Object.values(runs).every(r => r.status === 'idle') ? null : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted uppercase">
                  <th className="py-1.5 pr-3 font-semibold">Condition</th>
                  {SOURCES.map(s => <th key={s.id} className="px-3 py-1.5 font-semibold">{s.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map(([code, description]) => {
                  const active = truthCodes.has(code)
                  return (
                    <tr key={code} className="border-b border-line/60 last:border-0">
                      <td className="py-1.5 pr-3 text-ink" title={`SNOMED ${code}`}>
                        {plain(description)}
                        {filterCodes.has(code) && (
                          <span className="ml-2 rounded-full bg-hybrid/10 px-2 py-0.5 text-xs text-ink-soft" title="This condition sets a Filter">
                            sets a Filter
                          </span>
                        )}
                        {!active && <span className="ml-2 text-xs text-muted">not active in the tables</span>}
                      </td>
                      {SOURCES.map(s => (
                        <td key={s.id} className="px-3 py-1.5 whitespace-nowrap">
                          <Cell
                            run={runs[s.id]}
                            found={foundCodes(s.id).has(code)}
                            active={active}
                          />
                        </td>
                      ))}
                    </tr>
                  )
                })}
                {rows.length === 0 && (
                  <tr><td colSpan={4} className="py-3 text-muted">No active conditions to compare.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <dl className="mt-4 grid gap-2 sm:grid-cols-3">
            {SOURCES.map(s => {
              const run = runs[s.id]
              const st = stats(s.id)
              return (
                <div key={s.id} className="rounded-md border border-line px-3 py-2 text-sm">
                  <dt className="font-medium text-ink">{s.name}</dt>
                  <dd className="mt-1 space-y-0.5 text-ink-soft">
                    {run.status === 'idle' && <span className="text-muted">Waiting.</span>}
                    {run.status === 'loading' && <span className="text-muted">Working…</span>}
                    {run.status === 'error' && <span className="text-danger">{run.message}</span>}
                    {st && (
                      <>
                        {st.d.data.error ? (
                          <div className="text-danger">Failed: {st.d.data.error}</div>
                        ) : (
                          <>
                            <div>Found {st.hit} of {truthCodes.size} active conditions</div>
                            <div>
                              Conditions that set a Filter: {st.filterHit} of {st.filterTotal}
                              {st.filterTotal > 0 && st.filterHit < st.filterTotal && <span className="text-danger"> (a Filter would be missing)</span>}
                            </div>
                            <div>Not active but returned: {st.extra}</div>
                          </>
                        )}
                        {s.id !== 'sql' && (
                          <div className="text-xs text-muted tabular-nums">
                            {st.d.data.chars_read.toLocaleString()} characters read · {st.d.data.llm_calls} LLM call{st.d.data.llm_calls === 1 ? '' : 's'} · {(st.d.ms / 1000).toFixed(1)} s
                          </div>
                        )}
                        {s.id === 'tree' && st.d.data.selected.length > 0 && (
                          <div className="text-xs text-muted">Read sections: {st.d.data.selected.join(', ')}</div>
                        )}
                        {s.id === 'dense' && st.d.data.selected.length > 0 && (
                          <div className="text-xs text-muted">Read pieces: {st.d.data.selected.join(', ')}</div>
                        )}
                        {st.d.data.invented_codes.length > 0 && (
                          <div className="text-xs text-muted">
                            {st.d.data.invented_codes.length} code(s) the model named but never read were dropped
                          </div>
                        )}
                      </>
                    )}
                  </dd>
                </div>
              )
            })}
          </dl>
          <p className="mt-3 text-xs text-muted">
            One patient is an anecdote. Across 60 patients, Tree found 61% of active conditions and Dense 42%
            (see the evaluation report).
          </p>
        </>
      )}
    </section>
  )
}
