import { useLayoutEffect, useState, type RefObject } from 'react'
import type { Hit } from '../api'
import { METHOD } from '../methods'

interface Link {
  id: string
  chunk: number
  from: 'sparse' | 'dense'
  d: string
  ends: [number, number, number, number]
}

interface Props {
  gridRef: RefObject<HTMLDivElement | null>
  hybrid: Hit[]
  runId: number
  hovered: number | null
  /** Changes whenever any column's content changes, so the lines are measured again. */
  layoutKey: unknown
}

const ANCHOR_Y = 22 // level with a card's title line

/**
 * Draws a line from each Hybrid card to the same Chunk's card in the Sparse and Dense
 * columns, so you can see which retriever each Hybrid result came from. Wide screens only.
 */
export function Connectors({ gridRef, hybrid, runId, hovered, layoutKey }: Props) {
  const [links, setLinks] = useState<Link[]>([])

  useLayoutEffect(() => {
    const grid = gridRef.current
    if (!grid) return
    const wide = window.matchMedia('(min-width: 1024px)')

    const measure = () => {
      if (!wide.matches) return setLinks([])
      const g = grid.getBoundingClientRect()
      const card = (col: string, id: number) =>
        grid.querySelector(`[data-col="${col}"] [data-chunk="${id}"]`)?.getBoundingClientRect()
      const next: Link[] = []
      for (const h of hybrid) {
        const hr = card('hybrid', h.chunk_id)
        if (!hr) continue
        for (const from of ['sparse', 'dense'] as const) {
          const or = card(from, h.chunk_id)
          if (!or) continue
          const [x1, y1, x2, y2] = from === 'sparse'
            ? [or.right, or.top + ANCHOR_Y, hr.left, hr.top + ANCHOR_Y]
            : [hr.right, hr.top + ANCHOR_Y, or.left, or.top + ANCHOR_Y]
          const [a, b, c, d] = [x1 - g.left, y1 - g.top, x2 - g.left, y2 - g.top]
          const mid = (a + c) / 2
          next.push({
            id: `${runId}-${from}-${h.chunk_id}`, chunk: h.chunk_id, from,
            d: `M${a},${b} C${mid},${b} ${mid},${d} ${c},${d}`, ends: [a, b, c, d],
          })
        }
      }
      setLinks(next)
    }

    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(grid)
    grid.querySelectorAll('[data-col]').forEach(col => ro.observe(col))
    wide.addEventListener('change', measure)
    return () => {
      ro.disconnect()
      wide.removeEventListener('change', measure)
    }
  }, [gridRef, hybrid, runId, layoutKey])

  if (!links.length) return null
  return (
    <svg aria-hidden className="pointer-events-none absolute inset-0 hidden size-full overflow-visible lg:block">
      {links.map(l => {
        const opacity = hovered === null ? 0.75 : hovered === l.chunk ? 1 : 0.12
        return (
          <g key={l.id} style={{ opacity }} className="transition-opacity duration-150">
            <path d={l.d} pathLength={1} className={`connector fill-none ${METHOD[l.from].stroke}`} strokeWidth={2} />
            <circle cx={l.ends[0]} cy={l.ends[1]} r={3} className={METHOD[l.from].fill} />
            <circle cx={l.ends[2]} cy={l.ends[3]} r={3} className={METHOD[l.from].fill} />
          </g>
        )
      })}
    </svg>
  )
}
