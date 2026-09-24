import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Health } from '../api'
import { KINDS, RANGE_GROUPS, DEFAULT_FILTERS, type BoundKey, type Filters } from '../filters'
import type { Theme } from '../useTheme'
import { CloseIcon, MonitorIcon, MoonIcon, SunIcon } from './icons'

interface Props {
  open: boolean
  filters: Filters
  categories: string[]
  health: Health | null
  healthError: boolean
  theme: Theme
  onTheme: (t: Theme) => void
  onApply: (f: Filters) => void
  onClose: () => void
}

const THEMES: { value: Theme; label: string; Icon: typeof SunIcon }[] = [
  { value: 'system', label: 'System', Icon: MonitorIcon },
  { value: 'light', label: 'Light', Icon: SunIcon },
  { value: 'dark', label: 'Dark', Icon: MoonIcon },
]

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-b border-line px-6 py-5">
      <h3 className="mb-3 text-sm font-semibold text-ink">{title}</h3>
      {children}
    </section>
  )
}

const input =
  'w-full min-w-0 rounded-md border border-line bg-page px-2.5 py-1.5 text-sm tabular-nums text-ink placeholder:text-muted/70 focus:border-hybrid focus:outline-none'

/**
 * Filters are edited as a draft: "Apply" commits them and runs the search again,
 * closing the drawer any other way discards the changes. The theme applies at once.
 */
export function SettingsDrawer({ open, filters, categories, health, healthError, theme, onTheme, onApply, onClose }: Props) {
  const [draft, setDraft] = useState(filters)
  const [wasOpen, setWasOpen] = useState(open)
  const panel = useRef<HTMLDivElement>(null)

  // Each opening starts from the applied filters.
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) setDraft(filters)
  }

  useEffect(() => {
    if (!open) return
    panel.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter(x => x !== v) : [...list, v])
  const setBound = (key: BoundKey, value: string) => setDraft(d => ({ ...d, bounds: { ...d.bounds, [key]: value } }))

  return (
    <div className={`fixed inset-0 z-40 ${open ? '' : 'pointer-events-none'}`} inert={!open}>
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-ink/25 transition-opacity duration-200 ${open ? 'opacity-100' : 'opacity-0'}`}
      />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        tabIndex={-1}
        className={`absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-line bg-surface shadow-ink/10 ${open ? 'shadow-2xl' : ''} outline-none transition-transform duration-200 ease-out motion-reduce:transition-none ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <h2 id="settings-title" className="text-lg font-semibold text-ink">Settings</h2>
          <button type="button" onClick={onClose} aria-label="Close settings without applying"
            className="rounded-md p-1.5 text-muted hover:bg-page hover:text-ink">
            <CloseIcon />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <Section title="Results per column">
            <div className="flex items-center gap-4">
              <input type="range" min={1} max={50} value={draft.k} aria-label="Results per column"
                onChange={e => setDraft(d => ({ ...d, k: Number(e.target.value) }))}
                className="flex-1 accent-hybrid" />
              <span className="w-8 text-right text-sm font-semibold tabular-nums text-ink">{draft.k}</span>
            </div>
          </Section>

          <Section title="Chunk kind">
            <div className="flex gap-2">
              {KINDS.map(k => {
                const on = draft.kind.includes(k.value)
                return (
                  <button key={k.value} type="button" aria-pressed={on}
                    onClick={() => setDraft(d => ({ ...d, kind: toggle(d.kind, k.value) }))}
                    className={`rounded-full border px-3 py-1 text-sm ${
                      on ? 'border-hybrid bg-hybrid/10 text-ink' : 'border-line text-ink-soft hover:border-muted'
                    }`}>
                    {k.label}
                  </button>
                )
              })}
            </div>
            <p className="mt-2 text-xs text-muted">None selected searches every kind.</p>
          </Section>

          <Section title="Category">
            {categories.length === 0 ? (
              <p className="text-sm text-muted">Categories could not be loaded.</p>
            ) : (
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                {categories.map(c => (
                  <label key={c} className="flex min-w-0 items-center gap-2 text-sm text-ink-soft">
                    <input type="checkbox" className="accent-hybrid" checked={draft.category.includes(c)}
                      onChange={() => setDraft(d => ({ ...d, category: toggle(d.category, c) }))} />
                    <span className="truncate">{c}</span>
                  </label>
                ))}
              </div>
            )}
          </Section>

          {RANGE_GROUPS.map(group => (
            <Section key={group.name} title={group.name}>
              <div className="grid grid-cols-[1fr_5.5rem_5.5rem] items-center gap-x-2 gap-y-2">
                <span />
                <span className="text-xs text-muted">Min</span>
                <span className="text-xs text-muted">Max</span>
                {group.ranges.map(r => (
                  <div key={r.column} className="contents">
                    <span className="text-sm text-ink-soft">
                      {r.label}{r.unit && <span className="text-muted"> ({r.unit})</span>}
                    </span>
                    {(['min', 'max'] as const).map(b => {
                      const key: BoundKey = `${b}_${r.column}`
                      return (
                        <input key={key} type="number" inputMode="decimal" min={0} step={r.step ?? 1}
                          aria-label={`${b === 'min' ? 'Minimum' : 'Maximum'} ${r.label.toLowerCase()}`}
                          value={draft.bounds[key] ?? ''} onChange={e => setBound(key, e.target.value)}
                          className={input} />
                      )
                    })}
                  </div>
                ))}
              </div>
            </Section>
          ))}

          <Section title="Appearance">
            <div className="inline-flex rounded-lg border border-line p-0.5">
              {THEMES.map(({ value, label, Icon }) => (
                <button key={value} type="button" aria-pressed={theme === value} onClick={() => onTheme(value)}
                  className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm ${
                    theme === value ? 'bg-page font-medium text-ink shadow-sm' : 'text-muted hover:text-ink'
                  }`}>
                  <Icon width={15} height={15} />{label}
                </button>
              ))}
            </div>
          </Section>

          <Section title="Services">
            {healthError ? (
              <p className="text-sm text-danger">Cannot reach the search API.</p>
            ) : !health ? (
              <p className="text-sm text-muted">Checking</p>
            ) : (
              <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-sm">
                <dt className="text-muted">Database</dt><dd><Status value={health.database} /></dd>
                <dt className="text-muted">Embedding</dt><dd><Status value={health.embedding} /></dd>
                <dt className="text-muted">Chunker</dt><dd className="text-ink">{health.chunker}</dd>
                <dt className="text-muted">Chunks</dt><dd className="tabular-nums text-ink">{health.chunks?.toLocaleString() ?? 'unknown'}</dd>
                <dt className="text-muted">Reranker</dt><dd className="break-all text-ink">{health.reranker} on {health.reranker_device}</dd>
              </dl>
            )}
          </Section>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-line px-6 py-4">
          <button type="button" onClick={() => setDraft({ ...DEFAULT_FILTERS, k: draft.k })}
            className="rounded-md px-3 py-2 text-sm font-medium text-muted hover:text-ink">
            Clear filters
          </button>
          <button type="button" onClick={() => onApply(draft)}
            className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-surface hover:bg-ink/85">
            Apply
          </button>
        </div>
      </div>
    </div>
  )
}

function Status({ value }: { value?: string }) {
  const ok = value === 'ok'
  return (
    <span className={`inline-flex items-center gap-2 ${ok ? 'text-ink' : 'text-danger'}`}>
      <span className={`size-2 rounded-full ${ok ? 'bg-ok' : 'bg-danger'}`} />
      {ok ? 'Running' : value ?? 'unknown'}
    </span>
  )
}
