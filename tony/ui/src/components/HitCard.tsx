import { useState } from 'react'
import type { Hit, Method } from '../api'
import { METHOD } from '../methods'

export interface Sighting {
  method: Method
  rank: number
  note: string
}

interface Props {
  method: Method
  hit: Hit
  rank: number
  /** Where else this Chunk appears: other visible columns, or Hybrid's candidate ranks. */
  sightings: Sighting[]
  highlighted: boolean
  onHover: (chunkId: number | null) => void
}

const KIND_LABEL = { summary: 'Summary', ingredients: 'Ingredients', step: 'Step' }

const num = (x: number | undefined, digits = 3) => (x === undefined ? 'n/a' : x.toFixed(digits))

export function HitCard({ method, hit, rank, sightings, highlighted, onHover }: Props) {
  const [open, setOpen] = useState(false)
  const m = METHOD[method]

  return (
    <article
      data-chunk={hit.chunk_id}
      onMouseEnter={() => onHover(hit.chunk_id)}
      onMouseLeave={() => onHover(null)}
      className={`rounded-lg border bg-surface p-4 transition-shadow ${
        highlighted ? `${m.border} ring-1 ${m.ring}` : 'border-line'
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`w-5 shrink-0 pt-px text-sm font-semibold tabular-nums ${m.text}`}>{rank}</span>
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold leading-snug text-ink">{hit.title}</h3>
          <p className="mt-0.5 text-xs text-muted">
            {KIND_LABEL[hit.kind]}{hit.kind === 'step' ? ` ${hit.position}` : ''}
          </p>
        </div>
        <span className="shrink-0 pt-px text-xs text-muted" title={m.scoreName}>
          {num(hit.score)}
        </span>
      </div>

      <p className={`mt-3 pl-8 text-sm leading-relaxed text-ink-soft ${open ? '' : 'line-clamp-3'}`}>{hit.text}</p>

      <div className="mt-3 flex flex-wrap items-center gap-1.5 pl-8">
        {sightings.map(s => (
          <span
            key={s.method}
            title={s.note}
            className="inline-flex items-center gap-1.5 rounded-full border border-line px-2 py-0.5 text-xs text-ink-soft"
          >
            <span className={`size-1.5 rounded-full ${METHOD[s.method].bg}`} />
            {METHOD[s.method].name} #{s.rank}
          </span>
        ))}
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          aria-expanded={open}
          className="ml-auto rounded text-xs font-medium text-muted hover:text-ink"
        >
          {open ? 'Hide details' : 'Details'}
        </button>
      </div>

      {open && (
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 border-t border-line pt-3 pl-8 text-xs tabular-nums">
          <dt className="text-muted">{m.scoreName}</dt><dd className="text-ink">{num(hit.score, 4)}</dd>
          {method === 'hybrid' && (
            <>
              <dt className="text-muted">Sparse rank</dt><dd className="text-ink">{hit.sparse_rank ?? 'not found'}</dd>
              <dt className="text-muted">Dense rank</dt><dd className="text-ink">{hit.dense_rank ?? 'not found'}</dd>
              <dt className="text-muted">RRF score</dt><dd className="text-ink">{num(hit.rrf_score, 4)}</dd>
            </>
          )}
          <dt className="text-muted">Recipe</dt><dd className="text-ink">{hit.recipe_id}</dd>
          <dt className="text-muted">Chunk</dt><dd className="text-ink">{hit.chunk_id}</dd>
        </dl>
      )}
    </article>
  )
}
