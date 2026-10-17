import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError, getDietPlan, getPatient, getPatients, getStrategies, recommend,
  type AppliedLimit, type DietPlan, type PatientProfile, type PatientRow, type RecommendedRecipe,
  type RecommendResponse, type Strategy, type UnsupportedCondition,
} from './api'
import { useStrategy } from './useStrategy'
import { useTheme } from './useTheme'

const PAGE = 50

const EXAMPLES = [
  'a comforting soup',
  'chicken dinner',
  'pasta with vegetables',
  'a light breakfast',
  'something with beans',
]

const NUTRIENT: Record<string, { label: string; unit: string }> = {
  calories: { label: 'Calories', unit: 'kcal' },
  protein_g: { label: 'Protein', unit: 'g' },
  fat_g: { label: 'Fat', unit: 'g' },
  saturated_fat_g: { label: 'Saturated fat', unit: 'g' },
  carbohydrates_g: { label: 'Carbohydrates', unit: 'g' },
  sugars_g: { label: 'Sugars', unit: 'g' },
  sodium_mg: { label: 'Sodium', unit: 'mg' },
}

const label = (n: string) => NUTRIENT[n]?.label ?? n
const unit = (n: string) => NUTRIENT[n]?.unit ?? ''
const fmt = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1))

type Result =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; data: RecommendResponse }

type Selected =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; profile: PatientProfile; plan: DietPlan }

/** One entry per rule, so four stages of one disease read as one line. */
function groupByRule(conditions: UnsupportedCondition[]): UnsupportedCondition[][] {
  const groups = new Map<string, UnsupportedCondition[]>()
  for (const c of conditions) groups.set(c.rule_id, [...(groups.get(c.rule_id) ?? []), c])
  return [...groups.values()]
}

const message = (e: unknown) => (e instanceof ApiError ? e.message : String(e))

function Card({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-wide text-ink uppercase">{title}</h2>
        {note && <span className="text-xs text-muted">{note}</span>}
      </div>
      {children}
    </section>
  )
}

function Limit({ l, dim }: { l: AppliedLimit; dim?: boolean }) {
  return (
    <li className={`rounded-md border border-line px-3 py-2 text-sm ${dim ? 'opacity-70' : ''}`}>
      <div className="font-medium text-ink">
        {label(l.nutrient)} ≤ {fmt(l.per_serving)} {unit(l.nutrient)} per serving
        <span className="ml-2 font-normal text-muted">
          ({fmt(l.daily)} {unit(l.nutrient)} a day ÷ meals)
        </span>
      </div>
      <div className="text-ink-soft">
        {l.label}: {l.conditions.map(c => c.description).join(', ')}
      </div>
      <div className="mt-0.5 text-xs text-muted">
        Rule {l.rule_id} · {l.rule_status}
        {l.binding && ' · strictest, so this is the Filter'}
      </div>
    </li>
  )
}

function PatientPanel({ sel }: { sel: Selected | null }) {
  if (!sel) return <p className="text-sm text-muted">Pick a patient to see their conditions and the limits those imply.</p>
  if (sel.status === 'loading') return <p className="text-sm text-muted">Loading the patient…</p>
  if (sel.status === 'error') return <p className="text-sm text-danger">{sel.message}</p>
  const { profile, plan } = sel
  return (
    <div className="space-y-4">
      <div>
        <div className="text-base font-semibold text-ink">{profile.display_name}</div>
        <div className="text-sm text-muted">
          {profile.age} years old · {profile.gender === 'F' ? 'female' : profile.gender === 'M' ? 'male' : profile.gender} ·
          record as of {profile.reference_date}
        </div>
        <h3 className="mt-3 mb-1 text-xs font-semibold tracking-wide text-muted uppercase">Conditions</h3>
        <ul className="flex flex-wrap gap-1.5">
          {profile.active_conditions.map(c => (
            <li key={c.code} title={`SNOMED ${c.code}, since ${c.since}`} className="rounded-full bg-page px-2.5 py-0.5 text-xs text-ink-soft">
              {c.description}
            </li>
          ))}
          {profile.active_conditions.length === 0 && <li className="text-sm text-muted">No active conditions.</li>}
        </ul>
      </div>

      <div>
        <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-muted uppercase">Allergies</h3>
        {profile.active_allergies.length === 0 ? (
          <p className="text-sm text-muted">None recorded.</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {profile.active_allergies.map(a => (
              <li
                key={a.code}
                title={a.category === 'food' ? 'Recipes naming this are removed' : `${a.category ?? 'other'} allergy: does not affect recipes`}
                className={`rounded-full px-2.5 py-0.5 text-xs ${a.category === 'food' ? 'bg-danger/10 font-medium text-ink' : 'bg-page text-muted'}`}
              >
                {a.description.replace(/ \((substance|edible)\)/g, '').replace(/ \(edible\)/, '')}
                <span className="ml-1 text-muted">{a.category}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-muted uppercase">Filters applied to the search</h3>
        {plan.evidence.length === 0 ? (
          <p className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-ink">
            No dietary Filter applies, so the search is not restricted.
          </p>
        ) : (
          <ul className="space-y-2">{plan.evidence.map(l => <Limit key={l.rule_id + l.nutrient} l={l} />)}</ul>
        )}
      </div>

      {plan.unapplied_limits.length > 0 && (
        <div>
          <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-muted uppercase">Limits that cannot be applied yet</h3>
          <ul className="space-y-2">{plan.unapplied_limits.map(l => <Limit key={l.rule_id + l.nutrient} l={l} dim />)}</ul>
        </div>
      )}

      {plan.unsupported_conditions.length > 0 && (
        <div>
          <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-muted uppercase">Conditions with no supported rule</h3>
          <ul className="space-y-1 text-sm text-ink-soft">
            {groupByRule(plan.unsupported_conditions).map(group => (
              <li key={group[0].rule_id}>
                <b className="font-medium text-ink">{group.map(c => c.description).join('; ')}</b>: {group[0].reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function RecipeCard({ r }: { r: RecommendedRecipe }) {
  const checked = new Map(r.checks.map(c => [c.nutrient, c]))
  return (
    <li className="rounded-lg border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-ink">
            <span className="mr-2 tabular-nums text-muted">{r.rank}.</span>
            <a href={r.url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">{r.title}</a>
          </h3>
          <p className="text-sm text-muted">
            {r.category} · ★ {r.rating.toFixed(1)}
            {r.total_minutes != null && ` · ${r.total_minutes} min`} · serves {r.servings}
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-hybrid/10 px-2 py-0.5 text-xs text-ink-soft" title="Chunk that matched best">
          {r.best_chunk.kind}
          {r.best_chunk.rerank_score != null && ` · ${r.best_chunk.rerank_score.toFixed(2)}`}
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {Object.entries(r.nutrition).map(([k, v]) => {
          const c = checked.get(k)
          return (
            <div
              key={k}
              className={`rounded-md border px-2.5 py-1.5 ${c ? (c.ok ? 'border-ok/50 bg-ok/10' : 'border-danger/50 bg-danger/10') : 'border-line'}`}
            >
              <dt className="text-xs text-muted">{label(k)}</dt>
              <dd className="text-sm font-medium tabular-nums text-ink">
                {v == null ? 'n/a' : `${fmt(v)} ${unit(k)}`}
              </dd>
              {c && (
                <div className={`text-xs ${c.ok ? 'text-ok' : 'text-danger'}`}>
                  {c.ok ? '✓' : '✗'} limit {fmt(c.limit)}
                </div>
              )}
            </div>
          )
        })}
      </dl>

      <p className="mt-3 line-clamp-3 text-sm text-ink-soft">{r.best_chunk.text}</p>

      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-muted hover:text-ink">Ingredients ({r.ingredients.length})</summary>
        <ul className="mt-1 list-disc pl-5 text-ink-soft">{r.ingredients.map((l, i) => <li key={i}>{l}</li>)}</ul>
      </details>
    </li>
  )
}

export default function Recommend() {
  useTheme()
  const [strategies, setStrategies] = useState<Strategy[] | null>(null)
  const [strategiesError, setStrategiesError] = useState(false)
  const [strategy, chooseStrategy] = useStrategy(strategies?.map(s => s.name) ?? null)

  const [q, setQ] = useState('')
  const [order, setOrder] = useState<'name' | 'conditions'>('conditions')
  const [rows, setRows] = useState<PatientRow[]>([])
  const [more, setMore] = useState(false)
  const [listError, setListError] = useState<string | null>(null)
  const [listLoading, setListLoading] = useState(true)

  const [patientId, setPatientId] = useState<string | null>(null)
  const [selected, setSelected] = useState<Selected | null>(null)

  const [query, setQuery] = useState('')
  const [k, setK] = useState(5)
  const [explain, setExplain] = useState(true)
  const [result, setResult] = useState<Result>({ status: 'idle' })
  const controller = useRef<AbortController | null>(null)

  useEffect(() => {
    getStrategies().then(setStrategies).catch(() => setStrategiesError(true))
  }, [])

  const loadPatients = useCallback((offset: number, signal: AbortSignal, search: string, sort: string) => {
    const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset), order: sort })
    if (search.trim()) params.set('q', search.trim())
    setListLoading(true)
    getPatients(params, signal)
      .then(page => {
        setRows(prev => (offset === 0 ? page : [...prev, ...page]))
        setMore(page.length === PAGE)
        setListError(null)
      })
      .catch(e => { if (!signal.aborted) setListError(message(e)) })
      .finally(() => { if (!signal.aborted) setListLoading(false) })
  }, [])

  useEffect(() => {
    const ctrl = new AbortController()
    const t = setTimeout(() => loadPatients(0, ctrl.signal, q, order), 250)
    return () => { clearTimeout(t); ctrl.abort() }
  }, [q, order, loadPatients])

  const pickController = useRef<AbortController | null>(null)
  const pick = (id: string) => {
    pickController.current?.abort()
    const ctrl = (pickController.current = new AbortController())
    setPatientId(id)
    setSelected({ status: 'loading' })
    setResult({ status: 'idle' })
    controller.current?.abort()
    Promise.all([getPatient(id, ctrl.signal), getDietPlan(id, ctrl.signal)])
      .then(([profile, plan]) => setSelected({ status: 'ready', profile, plan }))
      .catch(e => { if (!ctrl.signal.aborted) setSelected({ status: 'error', message: message(e) }) })
  }

  const run = (text: string) => {
    text = text.trim()
    if (!patientId || !strategy || !text) return
    controller.current?.abort()
    const ctrl = (controller.current = new AbortController())
    setResult({ status: 'loading' })
    recommend({ patient_id: patientId, query: text, strategy, k, explain }, ctrl.signal)
      .then(data => setResult({ status: 'done', data }))
      .catch(e => { if (!ctrl.signal.aborted) setResult({ status: 'error', message: message(e) }) })
  }

  const canRun = !!patientId && !!strategy && !!query.trim() && result.status !== 'loading'
  const data = result.status === 'done' ? result.data : null
  const problem = strategiesError
    ? 'Could not load the Chunking strategies. Reload this page.'
    : strategies?.length === 0
      ? 'No Chunking strategy is loaded, so there is nothing to search.'
      : null

  return (
    <div className="mx-auto max-w-[1440px] px-4 pb-16 sm:px-8">
      <header className="flex items-center justify-between gap-4 py-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Diet Recommender</h1>
          <p className="text-sm text-muted">
            A patient's conditions set nutrition limits; the search only returns recipes within them. Synthetic data, not medical advice.
          </p>
        </div>
        <nav className="flex shrink-0 gap-2 text-sm">
          <a href="/" className="rounded-md border border-line bg-surface px-3 py-2 font-medium text-ink hover:border-muted">Recipe Search</a>
          <a href="/report" className="rounded-md border border-line bg-surface px-3 py-2 font-medium text-ink hover:border-muted">Report</a>
        </nav>
      </header>

      {problem && (
        <p role="status" className="mb-6 rounded-lg border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-ink">{problem}</p>
      )}

      <div className="grid gap-8 lg:grid-cols-[22rem_1fr]">
        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <Card title="1. Patient" note={rows.length ? `${rows.length} shown` : undefined}>
            <div className="flex gap-2">
              <input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search by name"
                aria-label="Search patients by name"
                className="min-w-0 flex-1 rounded-md border border-line bg-page px-3 py-2 text-sm text-ink placeholder:text-muted/80 focus:border-hybrid focus:outline-none"
              />
              <select
                value={order}
                onChange={e => setOrder(e.target.value as 'name' | 'conditions')}
                aria-label="Sort patients"
                className="rounded-md border border-line bg-page px-2 py-2 text-sm text-ink"
              >
                <option value="conditions">Most conditions</option>
                <option value="name">Name</option>
              </select>
            </div>
            {listError && <p className="mt-2 text-sm text-danger">{listError}</p>}
            <ul className="mt-3 max-h-72 space-y-1 overflow-y-auto">
              {rows.map(p => (
                <li key={p.patient_id}>
                  <button
                    type="button"
                    aria-pressed={patientId === p.patient_id}
                    onClick={() => pick(p.patient_id)}
                    className={`flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left text-sm ${
                      patientId === p.patient_id ? 'bg-hybrid/10 font-medium text-ink' : 'text-ink-soft hover:bg-page'
                    }`}
                  >
                    <span>{p.display_name}<span className="ml-2 text-xs text-muted">{p.age}{p.gender}</span></span>
                    <span className="text-xs tabular-nums text-muted">{p.active_conditions} cond.</span>
                  </button>
                </li>
              ))}
              {!listLoading && rows.length === 0 && !listError && <li className="px-3 py-2 text-sm text-muted">No patient matches.</li>}
            </ul>
            {listLoading && <p className="mt-2 text-xs text-muted">Loading…</p>}
            {more && !listLoading && (
              <button
                type="button"
                onClick={() => loadPatients(rows.length, new AbortController().signal, q, order)}
                className="mt-2 text-sm text-muted underline-offset-2 hover:text-ink hover:underline"
              >
                Load more
              </button>
            )}
          </Card>

          <Card title="Conditions and limits">
            <PatientPanel sel={selected} />
          </Card>
        </aside>

        <main className="min-w-0 space-y-6">
          <form
            onSubmit={e => { e.preventDefault(); run(query) }}
            className="space-y-3 rounded-lg border border-line bg-surface p-4"
            role="search"
          >
            <h2 className="text-sm font-semibold tracking-wide text-ink uppercase">2. What would they like to eat?</h2>
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                maxLength={500}
                placeholder="For example: a comforting soup"
                aria-label="What the patient wants to eat"
                className="flex-1 rounded-lg border border-line bg-page px-4 py-3 text-base text-ink placeholder:text-muted/80 focus:border-hybrid focus:outline-none focus:ring-3 focus:ring-hybrid/15"
              />
              <button
                type="submit"
                disabled={!canRun}
                className="rounded-lg bg-ink px-6 py-3 text-base font-semibold text-surface hover:bg-ink/85 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {result.status === 'loading' ? 'Working…' : 'Recommend'}
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
              {strategies && strategies.length > 0 && (
                <div role="group" aria-label="Chunking strategy" className="flex items-center gap-1 rounded-lg border border-line p-1">
                  {strategies.map(s => (
                    <button
                      key={s.name}
                      type="button"
                      aria-pressed={strategy === s.name}
                      onClick={() => chooseStrategy(s.name)}
                      className={`rounded-md px-3 py-1 ${strategy === s.name ? 'bg-page font-medium text-ink shadow-sm' : 'text-muted hover:text-ink'}`}
                    >
                      {s.name}
                    </button>
                  ))}
                </div>
              )}
              <label className="flex items-center gap-2 text-ink-soft">
                Recipes
                <select value={k} onChange={e => setK(Number(e.target.value))} className="rounded-md border border-line bg-page px-2 py-1 text-ink">
                  {[3, 5, 8, 10].map(n => <option key={n}>{n}</option>)}
                </select>
              </label>
              <label className="flex items-center gap-2 text-ink-soft">
                <input type="checkbox" checked={explain} onChange={e => setExplain(e.target.checked)} />
                Explain with the LLM
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted">Examples</span>
              {EXAMPLES.map(ex => (
                <button
                  key={ex}
                  type="button"
                  disabled={!patientId || !strategy}
                  onClick={() => { setQuery(ex); run(ex) }}
                  className="rounded-full border border-line px-3 py-1 text-ink-soft hover:border-muted hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {ex}
                </button>
              ))}
            </div>
            {!patientId && <p className="text-sm text-muted">Pick a patient first.</p>}
          </form>

          {result.status === 'loading' && (
            <p role="status" className="text-sm text-muted">Searching, checking nutrition{explain ? ' and writing the explanation (the LLM can take a while)' : ''}…</p>
          )}
          {result.status === 'error' && (
            <p role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm whitespace-pre-line text-ink">{result.message}</p>
          )}

          {data && (
            <>
              {data.warnings.length > 0 && (
                <ul role="status" className="space-y-1 rounded-lg border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-ink">
                  {data.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              )}

              {data.allergy_check.excluded.length > 0 && (
                <Card
                  title="Removed for allergy"
                  note={`${new Set(data.allergy_check.excluded.map(e => e.recipe_id)).size} recipe(s) never shown`}
                >
                  <ul className="space-y-1 text-sm text-ink-soft">
                    {data.allergy_check.excluded.map((e, i) => (
                      <li key={i}>
                        <b className="font-medium text-ink">{e.title}</b>: {e.allergen}
                        {e.matched && <> — “{e.matched}” in {e.where === 'title' ? 'the title' : <>“{e.where}”</>}</>}
                        {!e.matched && <> — {e.where}</>}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {(data.answer || data.answer_error) && (
                <Card title="Explanation" note={data.answer ? 'written by the LLM from the data below' : undefined}>
                  {data.answer ? (
                    <p className="text-sm leading-relaxed whitespace-pre-line text-ink">{data.answer}</p>
                  ) : (
                    <p className="text-sm text-ink-soft">
                      The recipes below are still valid. The explanation could not be written: {data.answer_error}
                    </p>
                  )}
                </Card>
              )}

              <section>
                <h2 className="mb-3 text-sm font-semibold tracking-wide text-ink uppercase">
                  Recipes for “{data.query}” <span className="font-normal text-muted">({data.recipes.length} of {data.k})</span>
                </h2>
                {data.recipes.length === 0 ? (
                  <p className="rounded-lg border border-line bg-surface px-4 py-6 text-center text-sm text-muted">
                    No recipe within this patient's limits matches. The Filters were not relaxed.
                  </p>
                ) : (
                  <ul className="space-y-3">{data.recipes.map(r => <RecipeCard key={r.recipe_id} r={r} />)}</ul>
                )}
              </section>

              <p className="text-xs text-muted tabular-nums">
                {Object.entries(data.timings_ms).map(([k2, v]) => `${k2} ${Math.round(v)} ms`).join(' · ')}
              </p>
            </>
          )}
        </main>
      </div>
    </div>
  )
}
