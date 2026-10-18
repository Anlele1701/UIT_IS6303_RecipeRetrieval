// Appendix: every query, list + detail ("Page layout and charts"). Filter state lives in the URL so a link opens one query.
import { useMemo, useState, type ReactNode } from 'react'
import { BUCKET_LONG, BUCKET_SHORT, BUCKETS, CFG, CONFIGS, rank, STRATEGIES, STRATEGY_NAME } from './format'
import { Marker, P, Section } from './parts'
import type { Bucket, Bundle, PerQuery } from './types'

type Filter = { strategy: string; bucket: Bucket | ''; overlap: '' | 'high' | 'low'; rewritten: boolean; text: string }
const EMPTY = { bucket: '' as const, overlap: '' as const, rewritten: false, text: '' }

function readUrl(): [Filter, string | null] {
  const p = new URLSearchParams(location.search)
  const strategy = p.get('strategy')
  const bucket = p.get('bucket') as Bucket | null
  const overlap = p.get('overlap')
  return [{
    strategy: strategy && STRATEGIES.includes(strategy) ? strategy : 'semantic',
    bucket: bucket && BUCKETS.includes(bucket) ? bucket : '',
    overlap: overlap === 'high' || overlap === 'low' ? overlap : '',
    rewritten: p.get('rewritten') === '1',
    text: p.get('text') ?? '',
  }, p.get('q')]
}

function writeUrl(f: Filter, q: string | null) {
  const u = new URLSearchParams()
  const set = (k: string, v: string) => { if (v) u.set(k, v) }
  set('strategy', f.strategy === 'semantic' ? '' : f.strategy); set('bucket', f.bucket); set('overlap', f.overlap)
  set('rewritten', f.rewritten ? '1' : ''); set('text', f.text); set('q', q ?? '')
  const qs = u.toString()
  history.replaceState(null, '', `${location.pathname}${qs ? `?${qs}` : ''}${location.hash}`)
}

function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-line bg-surface p-0.5">
      {options.map(([v, text]) => (
        <button key={v} role="radio" aria-checked={value === v} onClick={() => onChange(v)}
          className={`rounded px-2.5 py-1 ${value === v ? 'bg-ink text-page' : 'text-ink-soft hover:text-ink'}`}>{text}</button>
      ))}
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid items-center gap-x-3 gap-y-1 sm:grid-cols-[8rem_1fr]">
      <span className="text-muted">{label}</span>
      <div className="flex flex-wrap items-center gap-1.5">{children}</div>
    </div>
  )
}

function RankCell({ r }: { r: number | null }) {
  const tone = r == null ? 'text-muted' : r <= 5 ? 'font-semibold text-ink' : 'text-ink-soft'
  return <span className={`tabular-nums ${tone}`}>{rank(r)}</span>
}

function Detail({ b, row, strategy }: { b: Bundle; row: PerQuery; strategy: string }) {
  const q = b.queries[row.query_id]
  return (
    <div className="space-y-5 rounded-md border border-line bg-surface p-4">
      <div className="space-y-2">
        <p className="text-base font-medium leading-snug text-ink">“{q.text}”</p>
        <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted">Query id</dt><dd className="font-mono text-ink-soft">{row.query_id}</dd>
          <dt className="text-muted">Written from</dt><dd className="font-medium text-ink">{q.recipe_title}</dd>
          <dt className="text-muted">Right Recipes</dt><dd className="text-ink-soft">{q.right.length === 1 ? 'only that one' : `${q.right.length}, including that one`}</dd>
          {q.label_check !== 'good' && <><dt className="text-muted">Label check</dt><dd className="text-ink-soft">one detail of the query doesn’t match that Recipe</dd></>}
          <dt className="text-muted">Word overlap</dt><dd className="tabular-nums text-ink-soft">{q.word_overlap.toFixed(2)} ({q.word_overlap >= b.failures.high_overlap ? 'high' : 'low'})</dd>
          {q.hand_rewritten && <><dt className="text-muted">Rewritten by hand</dt><dd className="text-ink-soft">{q.edit_reason ?? 'yes'}; the model wrote “{q.edited_from}”</dd></>}
          {q.error_group && row.buckets.includes('every_miss') && <><dt className="text-muted">Miss group</dt><dd className="text-ink-soft">{q.error_group}</dd></>}
          {row.buckets.length > 0 && <><dt className="text-muted">Patterns</dt><dd className="flex flex-wrap gap-1">{row.buckets.map(k => (
            <span key={k} title={BUCKET_LONG[k]} className="rounded-full border border-line px-2 py-0.5 text-ink-soft">{BUCKET_SHORT[k]}</span>))}</dd></>}
        </dl>
      </div>
      <table className="text-xs tabular-nums">
        <thead className="text-muted"><tr><th className="py-1 pr-6 text-left font-normal">Rank of the first right Recipe</th>
          {CONFIGS.map(c => <th key={c} className="px-2 text-right font-normal">{CFG[c].name}</th>)}</tr></thead>
        <tbody>{STRATEGIES.map(s => {
          const r = b.per_query.find(p => p.strategy === s && p.query_id === row.query_id)!
          return (
            <tr key={s} className={`border-t border-line ${s === strategy ? 'bg-page font-medium' : ''}`}>
              <td className="py-1 pr-6 text-ink-soft">{STRATEGY_NAME[s]}</td>
              {CONFIGS.map(c => <td key={c} className="px-2 text-right"><RankCell r={r.ranks[c]} /></td>)}
            </tr>
          )
        })}</tbody>
      </table>
      <div>
        <h4 className="mb-2 text-xs text-muted">Top 20 on {STRATEGY_NAME[strategy]}. Right Recipes are highlighted.</h4>
        <div className="grid grid-cols-1 gap-x-4 gap-y-4 text-xs sm:grid-cols-2">
          {CONFIGS.map(c => (
            <ol key={c} className="space-y-0.5">
              <li className="mb-1 flex items-center gap-1.5 font-medium text-ink"><svg width="10" height="10" aria-hidden><Marker config={c} x={5} y={5} size={7} /></svg>{CFG[c].name}</li>
              {row.top[c].map((id, i) => (
                <li key={i} title={b.recipes[String(id)]} className={`truncate rounded px-1 ${q.right.includes(id) ? 'bg-ok/15 font-semibold text-ink' : 'text-ink-soft'}`}>
                  <span className="mr-2 inline-block w-5 text-right text-muted tabular-nums">{i + 1}</span>{b.recipes[String(id)] ?? id}
                </li>
              ))}
              {row.top[c].length === 0 && <li className="text-muted">No results.</li>}
            </ol>
          ))}
        </div>
      </div>
    </div>
  )
}

export function Drill({ b }: { b: Bundle }) {
  const [initial, initialQ] = useMemo(() => readUrl(), [])
  const [f, setF] = useState<Filter>(initial)
  const [q, setQ] = useState<string | null>(initialQ)
  const set = (patch: Partial<Filter>) => { const nf = { ...f, ...patch }; setF(nf); writeUrl(nf, q) }
  const pick = (id: string) => { setQ(id); writeUrl(f, id) }

  const inStrategy = useMemo(() => b.per_query.filter(r => r.strategy === f.strategy), [b, f.strategy])
  const rows = useMemo(() => {
    const text = f.text.trim().toLowerCase()
    return inStrategy.filter(r => {
      const x = b.queries[r.query_id]
      return (!f.bucket || r.buckets.includes(f.bucket))
        && (!f.overlap || (f.overlap === 'high') === (x.word_overlap >= b.failures.high_overlap))
        && (!f.rewritten || x.hand_rewritten)
        && (!text || x.text.toLowerCase().includes(text) || r.query_id.includes(text) || x.recipe_title.toLowerCase().includes(text))
    })
  }, [b, inStrategy, f])
  const current = rows.find(r => r.query_id === q) ?? rows[0]
  const n = (k: Bucket) => inStrategy.filter(r => r.buckets.includes(k)).length
  const active = f.bucket || f.overlap || f.rewritten || f.text
  const chip = (on: boolean) => `rounded-full border px-2.5 py-1 ${on ? 'border-ink bg-ink text-page' : 'border-line bg-surface text-ink-soft hover:border-muted'}`

  return (
    <Section id="appendix" title="Appendix: all queries">
      <P>Pick a query to see where each config ranked its first right Recipe. A dash means no right Recipe was in the top 20, and ranks 1 to 5 are bold.</P>
      <div className="sticky top-0 z-10 space-y-2 rounded-md border border-line bg-page p-3 text-xs">
        <Field label="Chunking strategy">
          <Segmented label="Chunking strategy" value={f.strategy} onChange={v => set({ strategy: v })} options={STRATEGIES.map(s => [s, STRATEGY_NAME[s]] as [string, string])} />
        </Field>
        <Field label="Show">
          <button className={chip(!f.bucket)} onClick={() => set({ bucket: '' })}>All queries <span className="tabular-nums opacity-70">{inStrategy.length}</span></button>
          {BUCKETS.map(k => (
            <button key={k} title={BUCKET_LONG[k]} className={chip(f.bucket === k)} onClick={() => set({ bucket: f.bucket === k ? '' : k })}>
              {BUCKET_SHORT[k]} <span className="tabular-nums opacity-70">{n(k)}</span>
            </button>
          ))}
        </Field>
        <Field label="Word overlap">
          <Segmented label="Word overlap" value={f.overlap} onChange={v => set({ overlap: v })} options={[['', 'Any'], ['high', 'High'], ['low', 'Low']]} />
          <span className="text-muted">High means every content word of the query appears in its Recipe.</span>
        </Field>
        <Field label="Query">
          <input aria-label="Search queries" className="w-full max-w-64 rounded-md border border-line bg-surface px-2 py-1 text-ink" placeholder="Words, a Recipe title or an id like q012"
            value={f.text} onChange={e => set({ text: e.target.value })} />
          <label className="ml-2 flex items-center gap-1.5 text-ink-soft">
            <input type="checkbox" checked={f.rewritten} onChange={e => set({ rewritten: e.target.checked })} />Only hand-rewritten queries
          </label>
        </Field>
        <div className="flex items-center justify-between border-t border-line pt-2 text-muted">
          <span><span className="font-medium text-ink tabular-nums">{rows.length}</span> of {inStrategy.length} queries</span>
          {active && <button className="underline" onClick={() => set(EMPTY)}>Clear filters</button>}
        </div>
      </div>
      <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-[19rem_minmax(0,1fr)]">
        <div className="overflow-hidden rounded-md border border-line bg-surface text-sm">
          <div className="grid grid-cols-[3.25rem_minmax(0,1fr)_3.5rem] gap-2 border-b border-line bg-page px-3 py-1.5 text-xs text-muted">
            <span>Id</span><span>Query</span><span className="text-right">Hybrid</span>
          </div>
          <ul className="max-h-[70vh] overflow-y-auto">
            {rows.length === 0 && <li className="px-3 py-4 text-xs text-muted">No queries match these filters.</li>}
            {rows.map(r => {
              const on = current?.query_id === r.query_id
              return (
                <li key={r.query_id}>
                  <button onClick={() => pick(r.query_id)} aria-current={on}
                    className={`grid w-full grid-cols-[3.25rem_minmax(0,1fr)_3.5rem] items-center gap-2 border-b border-line px-3 py-1.5 text-left hover:bg-page ${on ? 'bg-page shadow-[inset_3px_0_0_var(--ink)]' : ''}`}>
                    <span className="font-mono text-xs text-muted">{r.query_id}</span>
                    <span className="truncate text-ink-soft">{b.queries[r.query_id].text}</span>
                    <span className="text-right text-xs"><RankCell r={r.ranks.hybrid} /></span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
        {current && <Detail b={b} row={current} strategy={f.strategy} />}
      </div>
    </Section>
  )
}
