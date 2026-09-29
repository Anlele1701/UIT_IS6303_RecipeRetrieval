// Building blocks every section uses: headings, tables, the config marker, axes and the forest row.
// Charts are plain SVG and positioned divs, drawn with the theme tokens, so no chart library is needed.
import { useState, type ReactNode } from 'react'
import { CFG, CONFIGS, linear, pValue, pts } from './format'
import type { Config } from './types'

export function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-6">
      <h2 className="text-xl font-semibold text-ink">{title}</h2>
      <div className="mt-3 space-y-4">{children}</div>
    </section>
  )
}

export function Sub({ id, title, children }: { id?: string; title: string; children: ReactNode }) {
  return (
    <div id={id} className="scroll-mt-6 space-y-3 pt-2">
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {children}
    </div>
  )
}

export const P = ({ children }: { children: ReactNode }) => <p className="max-w-[46rem] text-[15px] leading-relaxed text-ink-soft">{children}</p>

export const Note = ({ children }: { children: ReactNode }) => <p className="max-w-[46rem] text-xs leading-relaxed text-muted">{children}</p>

export function Figure({ caption, children }: { caption?: ReactNode; children: ReactNode }) {
  return (
    <figure className="overflow-x-auto rounded-lg border border-line bg-surface p-4">
      {children}
      {caption && <figcaption className="mt-3 text-xs leading-relaxed text-muted">{caption}</figcaption>}
    </figure>
  )
}

export function Toggle({ label = 'table', children }: { label?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-3">
      <button className="text-xs text-muted underline underline-offset-2 hover:text-ink" aria-expanded={open}
        onClick={() => setOpen(o => !o)}>{open ? `Hide ${label}` : `Show ${label}`}</button>
      {open && <div className="mt-2">{children}</div>}
    </div>
  )
}

/** A compact data table. `right` marks numeric columns by index. */
export function Table({ head, rows, right = [], highlight = [], groupStart = [] }: {
  head: ReactNode[]; rows: ReactNode[][]; right?: number[]; highlight?: number[]; groupStart?: number[]
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead className="text-muted">
          <tr>{head.map((h, i) => <th key={i} className={`py-1.5 pr-3 font-normal ${right.includes(i) ? 'text-right' : 'text-left'}`}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={`${groupStart.includes(i) ? 'border-t-2' : 'border-t'} border-line ${highlight.includes(i) ? 'bg-ok/10 font-semibold text-ink' : 'text-ink-soft'}`}>
              {r.map((c, j) => <td key={j} className={`py-1.5 pr-3 align-top ${right.includes(j) ? 'text-right tabular-nums' : ''}`}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Marker({ config, x, y, size = 9 }: { config: Config; x: number; y: number; size?: number }) {
  const { color, shape } = CFG[config]
  const h = size / 2
  const common = { fill: color, stroke: 'var(--surface)', strokeWidth: 1.5 }
  if (shape === 'circle') return <circle cx={x} cy={y} r={h} {...common} />
  if (shape === 'square') return <rect x={x - h} y={y - h} width={size} height={size} rx={1.5} {...common} />
  if (shape === 'diamond') return <path d={`M${x} ${y - h - 1}L${x + h + 1} ${y}L${x} ${y + h + 1}L${x - h - 1} ${y}Z`} {...common} />
  return <path d={`M${x} ${y - h - 1}L${x + h + 1} ${y + h}L${x - h - 1} ${y + h}Z`} {...common} />
}

export function ConfigLabel({ config }: { config: Config }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <svg width="12" height="12" aria-hidden><Marker config={config} x={6} y={6} size={8} /></svg>
      {CFG[config].name}
    </span>
  )
}

export function Legend({ configs = CONFIGS }: { configs?: Config[] }) {
  return <div className="flex flex-wrap gap-4 text-xs text-ink-soft">{configs.map(c => <ConfigLabel key={c} config={c} />)}</div>
}


export function Grid({ ticks, at, zero }: { ticks: number[]; at: (v: number) => number; zero?: number }) {
  return (
    <>
      {ticks.map(t => <div key={t} className={`absolute inset-y-0 w-px ${t === zero ? 'bg-ink-soft/60' : 'bg-line'}`} style={{ left: `${at(t)}%` }} />)}
    </>
  )
}

export function Axis({ ticks, at, fmt }: { ticks: number[]; at: (v: number) => number; fmt: (v: number) => string }) {
  return (
    <div className="relative h-4">
      {ticks.map((t, i) => (
        <span key={t} className="absolute whitespace-nowrap text-[11px] text-muted tabular-nums"
          style={{ left: `${at(t)}%`, transform: i === 0 ? 'none' : i === ticks.length - 1 ? 'translateX(-100%)' : 'translateX(-50%)' }}>
          {fmt(t)}
        </span>
      ))}
    </div>
  )
}

export type ForestItem = { key: string; label: ReactNode; diff: number; lo: number; hi: number; p?: number; color?: string; extra?: ReactNode }

/**
 * Differences with a 95% CI against a zero line, one row each. `scale` is in points (0.01 = 1 pt).
 * The p shown is the Holm-adjusted one; a row whose CI crosses zero is drawn hollow.
 */
export function Forest({ items, ticks, unit = 'pts', extraHead }: { items: ForestItem[]; ticks: number[]; unit?: 'pts' | 'mrr'; extraHead?: ReactNode }) {
  const at = linear(ticks[0], ticks[ticks.length - 1])
  const signed = (v: number, digits: number) => (Math.abs(v) < 0.5 * 10 ** -digits ? (0).toFixed(digits) : (v > 0 ? '+' : '−') + Math.abs(v).toFixed(digits))
  const fmt = unit === 'pts' ? (v: number) => (v === 0 ? '0' : pts(v, 0)) : (v: number) => (v === 0 ? '0' : signed(v, 2))
  const val = unit === 'pts' ? (v: number) => signed(v * 100, 1) : (v: number) => signed(v, 3)
  const cols = 'grid items-center gap-x-3'
  const style = { gridTemplateColumns: `minmax(7rem, 13rem) 1fr 11rem 4rem${extraHead ? ' 4rem' : ''}` }
  return (
    <div className="min-w-[40rem] text-xs">
      <div className={`${cols} text-muted`} style={style}>
        <span /><Axis ticks={ticks} at={at} fmt={fmt} /><span className="text-right">difference (95% CI)</span><span className="text-right">Holm p</span>
        {extraHead && <span className="text-right">{extraHead}</span>}
      </div>
      {items.map(d => {
        const crosses = d.lo <= 0 && d.hi >= 0
        const color = d.color ?? 'var(--ink-soft)'
        return (
          <div key={d.key} className={`${cols} h-7 border-t border-line`} style={style}>
            <span className="truncate text-ink-soft">{d.label}</span>
            <div className="relative h-full">
              <Grid ticks={ticks} at={at} zero={0} />
              <div className="absolute top-1/2 h-[2px] -translate-y-1/2" style={{ left: `${at(Math.max(d.lo, ticks[0]))}%`, width: `${at(Math.min(d.hi, ticks[ticks.length - 1])) - at(Math.max(d.lo, ticks[0]))}%`, background: color }} />
              <div className="absolute top-1/2 h-[10px] w-[10px] -translate-x-1/2 -translate-y-1/2 rounded-full border-2"
                style={{ left: `${at(d.diff)}%`, borderColor: color, background: crosses ? 'var(--surface)' : color }} />
            </div>
            <span className="text-right tabular-nums text-ink">{val(d.diff)} <span className="text-muted">({val(d.lo)} to {val(d.hi)})</span></span>
            <span className={`text-right tabular-nums ${d.p != null && d.p < 0.05 ? 'font-semibold text-ink' : 'text-muted'}`}>{d.p == null ? '' : pValue(d.p)}</span>
            {extraHead && <span className="text-right tabular-nums text-ink-soft">{d.extra}</span>}
          </div>
        )
      })}
    </div>
  )
}

/** One-hue horizontal bars with the value in its own column. */
export function Bars({ items, max, fmt }: { items: { label: ReactNode; value: number; key: string }[]; max: number; fmt: (v: number) => string }) {
  return (
    <div className="space-y-1 text-xs">
      {items.map(i => (
        <div key={i.key} className="grid grid-cols-[minmax(8rem,12rem)_1fr_4rem] items-center gap-3">
          <span className="truncate text-ink-soft">{i.label}</span>
          <div className="h-3 rounded-sm bg-line/60"><div className="h-3 rounded-sm bg-ink-soft/70" style={{ width: `${(i.value / max) * 100}%` }} /></div>
          <span className="text-right tabular-nums text-ink">{fmt(i.value)}</span>
        </div>
      ))}
    </div>
  )
}

export function Stat({ value, label }: { value: ReactNode; label: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="text-2xl font-semibold text-ink">{value}</div>
      <div className="mt-0.5 text-xs text-muted">{label}</div>
    </div>
  )
}

export function Pill({ children, title }: { children: ReactNode; title?: string }) {
  return <span title={title} className="inline-block rounded-full border border-line bg-page px-2 py-0.5 text-[11px] text-ink-soft">{children}</span>
}
