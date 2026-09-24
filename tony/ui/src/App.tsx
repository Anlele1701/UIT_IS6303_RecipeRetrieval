import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, getCategories, getHealth, search, type Health, type Hit, type Method } from './api'
import { Connectors } from './components/Connectors'
import { CloseIcon, SearchIcon, SlidersIcon } from './components/icons'
import { ResultColumn, type ColumnState } from './components/ResultColumn'
import { SettingsDrawer } from './components/SettingsDrawer'
import { activeChips, DEFAULT_FILTERS, toParams, type Filters } from './filters'
import { COLUMN_ORDER } from './methods'
import { useTheme } from './useTheme'

const EXAMPLES: { q: string; hint: string; filters?: Partial<Filters> }[] = [
  { q: 'chicken thighs garlic lemon', hint: 'Exact ingredient words, which BM25 matches directly' },
  { q: 'something warm for a cold night', hint: 'Few recipes use these words, so matching depends on meaning' },
  { q: 'quick vegetarian pasta', hint: 'Adds a 30-minute limit on total time', filters: { bounds: { max_total_minutes: '30' } } },
  { q: 'how to keep cookies chewy', hint: 'Searches Step chunks only', filters: { kind: ['step'] } },
]

const IDLE: Record<Method, ColumnState> = { sparse: { status: 'idle' }, hybrid: { status: 'idle' }, dense: { status: 'idle' } }

export default function App() {
  const [theme, setTheme] = useTheme()
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [columns, setColumns] = useState(IDLE)
  const [runId, setRunId] = useState(0)
  const [searchedQuery, setSearchedQuery] = useState('')
  const [hovered, setHovered] = useState<number | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [categories, setCategories] = useState<string[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState(false)

  const controller = useRef<AbortController | null>(null)
  const grid = useRef<HTMLDivElement>(null)
  const settingsButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    getCategories().then(setCategories).catch(() => setCategories([]))
    getHealth().then(setHealth).catch(() => setHealthError(true))
  }, [])

  const run = useCallback((q: string, f: Filters) => {
    q = q.trim()
    if (!q) return
    controller.current?.abort()
    const ctrl = (controller.current = new AbortController())
    const params = toParams(q, f)
    setSearchedQuery(q)
    setRunId(id => id + 1)
    setColumns({ sparse: { status: 'loading' }, hybrid: { status: 'loading' }, dense: { status: 'loading' } })
    for (const method of COLUMN_ORDER) {
      search(method, params, ctrl.signal)
        .then(data => setColumns(c => ({ ...c, [method]: { status: 'done', data } })))
        .catch(e => {
          if (ctrl.signal.aborted) return
          const message = e instanceof ApiError ? e.message : String(e)
          setColumns(c => ({ ...c, [method]: { status: 'error', message } }))
        })
    }
  }, [])

  const applyFilters = (f: Filters) => {
    setFilters(f)
    if (searchedQuery) run(query || searchedQuery, f)
  }

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false)
    settingsButton.current?.focus()
  }, [])

  const ranks = useMemo(() => {
    const out = {} as Record<Method, Map<number, number>>
    for (const m of COLUMN_ORDER) {
      const s = columns[m]
      out[m] = new Map(s.status === 'done' ? s.data.results.map((h, i) => [h.chunk_id, i + 1]) : [])
    }
    return out
  }, [columns])

  const hybridHits: Hit[] = columns.hybrid.status === 'done' ? columns.hybrid.data.results : []
  const chips = activeChips(filters)
  const serviceProblem = healthError
    ? 'Cannot reach the search API. Start it with uvicorn, then reload this page.'
    : health && health.database !== 'ok'
      ? 'The database is not responding, so no search can run. Start it with docker compose up -d.'
      : health && health.embedding !== 'ok'
        ? 'The embedding service is not responding. Sparse still works; Dense and Hybrid will fail until Ollama is running.'
        : null

  return (
    <>
      <div inert={drawerOpen} className="mx-auto max-w-[1440px] px-4 pb-16 sm:px-8">
        <header className="flex items-center justify-between gap-4 py-6">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-ink">Recipe Search</h1>
            <p className="text-sm text-muted">Compare how three retrieval methods rank the same query.</p>
          </div>
          <button
            ref={settingsButton}
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-haspopup="dialog"
            aria-expanded={drawerOpen}
            className="inline-flex shrink-0 items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm font-medium text-ink hover:border-muted"
          >
            <SlidersIcon width={16} height={16} />
            Settings
            {chips.length > 0 && (
              <span className="rounded-full bg-ink px-1.5 text-xs font-semibold tabular-nums text-surface">{chips.length}</span>
            )}
          </button>
        </header>

        {serviceProblem && (
          <p role="status" className="mb-6 rounded-lg border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-ink">
            {serviceProblem}
          </p>
        )}

        <form
          onSubmit={e => { e.preventDefault(); run(query, filters) }}
          className="flex flex-col gap-3 sm:flex-row"
          role="search"
        >
          <label className="relative flex-1">
            <span className="sr-only">Search recipes</span>
            <SearchIcon className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              maxLength={500}
              placeholder="Search recipes, for example creamy tomato soup"
              className="w-full rounded-lg border border-line bg-surface py-3 pr-4 pl-11 text-base text-ink shadow-sm shadow-ink/5 placeholder:text-muted/80 focus:border-hybrid focus:outline-none focus:ring-3 focus:ring-hybrid/15"
            />
          </label>
          <button
            type="submit"
            disabled={!query.trim()}
            className="rounded-lg bg-ink px-6 py-3 text-base font-semibold text-surface hover:bg-ink/85 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Search
          </button>
        </form>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Examples</span>
          {EXAMPLES.map(ex => (
            <button
              key={ex.q}
              type="button"
              title={ex.hint}
              onClick={() => {
                const f = { ...DEFAULT_FILTERS, k: filters.k, ...ex.filters }
                setQuery(ex.q)
                setFilters(f)
                run(ex.q, f)
              }}
              className="rounded-full border border-line bg-surface px-3 py-1 text-ink-soft hover:border-muted hover:text-ink"
            >
              {ex.q}
            </button>
          ))}
        </div>

        {chips.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted">Filters</span>
            {chips.map(chip => (
              <span key={chip.id} className="inline-flex items-center gap-1 rounded-full bg-hybrid/10 py-1 pr-1.5 pl-3 text-ink">
                {chip.label}
                <button
                  type="button"
                  aria-label={`Remove filter ${chip.label}`}
                  onClick={() => applyFilters(chip.remove(filters))}
                  className="rounded-full p-0.5 text-muted hover:bg-hybrid/15 hover:text-ink"
                >
                  <CloseIcon width={13} height={13} />
                </button>
              </span>
            ))}
            {chips.length > 1 && (
              <button
                type="button"
                onClick={() => applyFilters({ ...DEFAULT_FILTERS, k: filters.k })}
                className="px-1 text-muted underline-offset-2 hover:text-ink hover:underline"
              >
                Clear all
              </button>
            )}
          </div>
        )}

        <div ref={grid} className="relative mt-10 grid gap-10 lg:grid-cols-3 lg:gap-x-16">
          {COLUMN_ORDER.map(m => (
            <ResultColumn
              key={m}
              method={m}
              state={columns[m]}
              k={filters.k}
              ranks={ranks}
              hovered={hovered}
              onHover={setHovered}
            />
          ))}
          <Connectors gridRef={grid} hybrid={hybridHits} runId={runId} hovered={hovered} layoutKey={columns} />
        </div>
      </div>

      <SettingsDrawer
        open={drawerOpen}
        filters={filters}
        categories={categories}
        health={health}
        healthError={healthError}
        theme={theme}
        onTheme={setTheme}
        onApply={f => { applyFilters(f); closeDrawer() }}
        onClose={closeDrawer}
      />
    </>
  )
}
