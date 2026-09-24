import type { Hit, Method, SearchResponse } from '../api'
import { COLUMN_ORDER, METHOD } from '../methods'
import { HitCard, type Sighting } from './HitCard'

export type ColumnState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; data: SearchResponse }
  | { status: 'error'; message: string }

interface Props {
  method: Method
  state: ColumnState
  k: number
  /** Visible rank of each chunk_id, per column, for the "also in" pills. */
  ranks: Record<Method, Map<number, number>>
  hovered: number | null
  onHover: (chunkId: number | null) => void
}

function sightingsFor(method: Method, hit: Hit, ranks: Props['ranks']): Sighting[] {
  if (method === 'hybrid') {
    // Hybrid knows where each candidate ranked in Sparse and Dense, even outside the visible top k.
    const out: Sighting[] = []
    if (hit.sparse_rank) out.push({ method: 'sparse', rank: hit.sparse_rank, note: `Ranked ${hit.sparse_rank} by Sparse` })
    if (hit.dense_rank) out.push({ method: 'dense', rank: hit.dense_rank, note: `Ranked ${hit.dense_rank} by Dense` })
    return out
  }
  return COLUMN_ORDER.filter(o => o !== method && ranks[o].has(hit.chunk_id)).map(o => ({
    method: o,
    rank: ranks[o].get(hit.chunk_id)!,
    note: `Also returned by ${METHOD[o].name}`,
  }))
}

export function ResultColumn({ method, state, k, ranks, hovered, onHover }: Props) {
  const m = METHOD[method]

  return (
    <section data-col={method} aria-labelledby={`col-${method}`} className="min-w-0">
      <header className={`mb-4 border-t-2 pt-3 ${m.border}`}>
        <div className="flex items-baseline justify-between gap-3">
          <h2 id={`col-${method}`} className="text-lg font-semibold text-ink">{m.name}</h2>
          <span className="text-xs text-muted">
            {state.status === 'done' ? `Top ${k} in ${state.data.took_ms} ms` : `Top ${k}`}
          </span>
        </div>
        <p className="mt-1 max-w-prose text-sm text-muted">{m.blurb}</p>
      </header>

      <div className="flex flex-col gap-3" aria-live="polite" aria-busy={state.status === 'loading'}>
        {state.status === 'idle' && (
          <p className="rounded-lg border border-dashed border-line px-4 py-8 text-center text-sm text-muted">
            Results appear here after you search.
          </p>
        )}
        {state.status === 'loading' &&
          [0, 1, 2].map(i => (
            <div key={i} className="h-28 rounded-lg border border-line bg-surface motion-safe:animate-pulse" />
          ))}
        {state.status === 'error' && (
          <p role="alert" className="whitespace-pre-wrap rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
            {state.message}
          </p>
        )}
        {state.status === 'done' && state.data.results.length === 0 && (
          <p className="rounded-lg border border-dashed border-line px-4 py-8 text-center text-sm text-muted">
            No Chunks match this query with the current filters. Remove a filter and search again.
          </p>
        )}
        {state.status === 'done' &&
          state.data.results.map((hit, i) => (
            <HitCard
              key={hit.chunk_id}
              method={method}
              hit={hit}
              rank={i + 1}
              sightings={sightingsFor(method, hit, ranks)}
              highlighted={hovered === hit.chunk_id}
              onHover={onHover}
            />
          ))}
      </div>
    </section>
  )
}
