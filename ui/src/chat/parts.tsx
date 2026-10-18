import { useEffect, useRef, useState, type ReactNode } from 'react'
import { CloseIcon } from '../components/icons'
import type { Group, Lift, Limit, RecipeBrief, RecipeDetail, SessionConstraint, TreeNode } from './api'
import { ALLERGEN, DIET, PRESETS, constraintText, nutrientName, nutrientUnit } from './labels'

// ---- answer text with citations -------------------------------------------------------------------------------

const TOKEN = /(\[R\d+\]|\[H:[^\]\s]+\]|\*\*[^*\n]+\*\*)/g

/** The answer with [R<id>] as links to recipe cards and [H:<node>] as links into the record tree. */
export function AnswerText({ text, onRecipe, onNode }: {
  text: string; onRecipe: (id: number) => void; onNode: (node: string) => void
}) {
  return (
    <div className="whitespace-pre-wrap leading-relaxed">
      {text.split(TOKEN).map((part, i) => {
        const r = /^\[R(\d+)\]$/.exec(part)
        if (r) return (
          <button key={i} type="button" onClick={() => onRecipe(Number(r[1]))}
            className="mx-0.5 rounded bg-hybrid/12 px-1 text-xs font-semibold text-hybrid hover:bg-hybrid/20">R{r[1]}</button>
        )
        const h = /^\[H:([^\]]+)\]$/.exec(part)
        if (h) return (
          <button key={i} type="button" onClick={() => onNode(h[1])} title="Mở mục này trong hồ sơ"
            className="mx-0.5 rounded bg-dense/12 px-1 text-xs font-semibold text-dense hover:bg-dense/20">hồ sơ: {h[1]}</button>
        )
        if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
        return <span key={i}>{part}</span>
      })}
    </div>
  )
}

// ---- recipe card ------------------------------------------------------------------------------------------------

export function RecipeCard({ r, cited, highlight, limits, onOpen }: {
  r: RecipeBrief; cited: boolean; highlight: boolean; limits: Record<string, Limit>; onOpen: () => void
}) {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    if (highlight) ref.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [highlight])
  return (
    <article ref={ref} id={`recipe-${r.id}`}
      className={`flex flex-col gap-2 rounded-lg border bg-surface p-3 text-sm transition-shadow ${
        highlight ? 'border-hybrid shadow-md shadow-hybrid/15' : 'border-line'}`}>
      <div className="flex items-start justify-between gap-2">
        <h4 className="font-medium text-ink">
          <span className="mr-1.5 text-xs font-semibold text-hybrid">R{r.id}</span>{r.title}
        </h4>
        {cited && <span className="shrink-0 rounded-full bg-ok/12 px-2 py-0.5 text-xs text-ok">được trích</span>}
      </div>
      <div className="flex flex-wrap gap-1.5 text-xs">
        {r.total_minutes != null && <span className="rounded bg-page px-1.5 py-0.5 text-ink-soft">{r.total_minutes} phút</span>}
        {r.diet_flags.map(d => <span key={d} className="rounded bg-ok/10 px-1.5 py-0.5 text-ok">{DIET[d] ?? d}</span>)}
        {r.allergens.map(a => <span key={a} className="rounded bg-danger/10 px-1.5 py-0.5 text-danger">chứa {ALLERGEN[a] ?? a}</span>)}
        {r.allergens_may.map(a => <span key={a} className="rounded bg-warn/12 px-1.5 py-0.5 text-warn">có thể chứa {ALLERGEN[a] ?? a}</span>)}
      </div>
      {r.nutrients && Object.keys(r.nutrients).length > 0 && (
        <ul className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted">
          {Object.entries(r.nutrients).map(([col, v]) => {
            const lim = limits[col]
            const bad = v != null && lim && (lim[0] === 'max' ? v > lim[1] : v < lim[1])
            return (
              <li key={col} className={bad ? 'text-danger' : undefined}>
                {nutrientName(col)}: {v == null ? 'chưa rõ' : `${Math.round(v * 10) / 10} ${nutrientUnit(col)}`}
              </li>
            )
          })}
        </ul>
      )}
      <button type="button" onClick={onOpen} className="self-start text-xs font-medium text-hybrid hover:underline">
        Xem nguyên liệu và cách làm
      </button>
    </article>
  )
}

// ---- constraint panel ---------------------------------------------------------------------------------------------

const LockIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
    <rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
)

export interface PanelData {
  dialogue: SessionConstraint[]
  groups: Group[]
  nutrients: { id: string; text: string; soft: boolean; evidence: string }[]
  lifted: Lift[]
  warnings: string[]
}

/** Dialogue chips (removable), one locked chip per record group (confirm to lift, details to lift one), nutrient
 *  limits one by one; lifted items greyed out. `readOnly` before the session exists (nothing to PATCH yet). */
export function ConstraintPanel({ data, readOnly, onRemove, onLift, onNode }: {
  data: PanelData; readOnly: boolean
  onRemove: (id: string) => void
  onLift: (target: { id: string; label: string; members: string[] }) => void
  onNode: (node: string) => void
}) {
  const [open, setOpen] = useState<string | null>(null)
  const empty = !data.dialogue.length && !data.groups.length && !data.nutrients.length && !data.lifted.length
  return (
    <section aria-label="Ràng buộc đang áp dụng" className="flex flex-col gap-3 text-sm">
      <h3 className="font-semibold text-ink">Ràng buộc đang áp dụng</h3>
      {empty && <p className="text-muted">Chưa có. Nói trong tin nhắn, ví dụ "tôi dị ứng đậu phộng", hoặc chọn một hồ sơ bệnh nhân.</p>}

      {data.warnings.map(w => (
        <p key={w} className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-ink">{w}</p>
      ))}

      {(data.groups.length > 0 || data.nutrients.length > 0) && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium text-muted">Từ hồ sơ (gỡ cần xác nhận)</p>
          {data.groups.map(g => (
            <div key={g.group_id} className="rounded-md border border-dense/40 bg-dense/8 px-3 py-2">
              <div className="flex items-start justify-between gap-2">
                <button type="button" onClick={() => onNode(g.node_id)} title="Mở mục này trong hồ sơ"
                  className="flex items-start gap-1.5 text-left text-ink hover:underline">
                  <span className="mt-1 text-dense"><LockIcon /></span>
                  <span>{g.members.filter(m => m.startsWith('allergen:')).map(constraintText).join(', ') || 'Nguyên liệu cần tránh'}
                    <span className="block text-xs text-muted">{g.text}</span></span>
                </button>
              </div>
              <div className="mt-1.5 flex gap-3 text-xs">
                <button type="button" onClick={() => setOpen(open === g.group_id ? null : g.group_id)}
                  aria-expanded={open === g.group_id} className="text-ink-soft hover:text-ink">
                  Chi tiết ({g.members.length})
                </button>
                {!readOnly && (
                  <button type="button" onClick={() => onLift({ id: g.group_id, label: g.text, members: g.members })}
                    className="font-medium text-danger hover:underline">Xác nhận gỡ cả nhóm</button>
                )}
              </div>
              {open === g.group_id && (
                <ul className="mt-2 flex flex-col gap-1 border-t border-line pt-2 text-xs">
                  {g.members.map(m => (
                    <li key={m} className="flex items-center justify-between gap-2">
                      <span className="text-ink-soft">{constraintText(m)}</span>
                      {!readOnly && (
                        <button type="button" onClick={() => onLift({ id: m, label: constraintText(m), members: [m] })}
                          className="text-danger hover:underline">gỡ</button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          {data.nutrients.map(n => (
            <div key={n.id} className="flex items-start justify-between gap-2 rounded-md border border-dense/40 bg-dense/8 px-3 py-2">
              <span className="flex items-start gap-1.5 text-ink" title={n.evidence}>
                <span className="mt-1 text-dense"><LockIcon /></span>
                <span>{n.text}{n.soft && <span className="ml-1 text-xs text-muted">(ưu tiên, không loại)</span>}</span>
              </span>
              {!readOnly && (
                <button type="button" onClick={() => onLift({ id: n.id, label: n.text, members: [n.id] })}
                  className="shrink-0 text-xs text-danger hover:underline">gỡ</button>
              )}
            </div>
          ))}
        </div>
      )}

      {data.dialogue.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium text-muted">Từ hội thoại</p>
          <div className="flex flex-wrap gap-2">
            {data.dialogue.map(c => (
              <span key={c.constraint_id} className="inline-flex items-center gap-1 rounded-full border border-line bg-surface py-1 pr-1 pl-3 text-ink">
                {constraintText(c.constraint_id)}
                {c.scope === 'turn' && <span className="text-xs text-muted">(lượt này)</span>}
                <button type="button" onClick={() => onRemove(c.constraint_id)} aria-label={`Xóa ${constraintText(c.constraint_id)}`}
                  className="rounded-full p-1 text-muted hover:bg-page hover:text-ink"><CloseIcon width={12} height={12} /></button>
              </span>
            ))}
          </div>
        </div>
      )}

      {data.lifted.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-muted">Đã gỡ sau khi xác nhận</p>
          {data.lifted.map(l => (
            <p key={l.constraint_id} className="text-xs text-muted line-through decoration-muted/50">
              {l.constraint_id.startsWith('record:') ? `Nhóm ${l.constraint_id}` : constraintText(l.constraint_id)}
              {l.reason && <span className="no-underline"> · {l.reason}</span>}
            </p>
          ))}
        </div>
      )}
    </section>
  )
}

// ---- dialogs and drawers ---------------------------------------------------------------------------------------

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    panel.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-ink/30 p-4 sm:items-center" onClick={onClose}>
      <div ref={panel} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} onClick={e => e.stopPropagation()}
        className={`max-h-[85vh] w-full overflow-y-auto rounded-xl border border-line bg-surface shadow-xl focus:outline-none ${wide ? 'max-w-3xl' : 'max-w-md'}`}>
        <div className="sticky top-0 flex items-center justify-between border-b border-line bg-surface px-5 py-3">
          <h2 className="font-semibold text-ink">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Đóng" className="rounded-md p-1.5 text-muted hover:bg-page hover:text-ink"><CloseIcon /></button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  )
}

export function LiftDialog({ target, busy, error, onConfirm, onClose }: {
  target: { id: string; label: string; members: string[] }; busy: boolean; error: string | null
  onConfirm: (reason: string) => void; onClose: () => void
}) {
  const [reason, setReason] = useState('')
  return (
    <Modal title="Xác nhận gỡ ràng buộc từ hồ sơ" onClose={onClose}>
      <p className="text-sm text-ink">
        Ràng buộc này đến từ hồ sơ bệnh nhân: <strong>{target.label}</strong>
        {target.members.length > 1 && <> ({target.members.length} mục: {target.members.slice(0, 4).map(constraintText).join(', ')}{target.members.length > 4 ? '…' : ''})</>}.
      </p>
      <p className="mt-2 text-sm text-muted">Chỉ gỡ khi đã có xác nhận (ví dụ của bác sĩ). Việc gỡ được ghi lại và chỉ áp dụng cho phiên này.</p>
      <label className="mt-4 block text-sm font-medium text-ink">
        Lý do
        <input value={reason} onChange={e => setReason(e.target.value)} maxLength={500} placeholder="ví dụ: bác sĩ xác nhận đã hết dị ứng"
          className="mt-1 w-full rounded-md border border-line bg-page px-3 py-2 text-sm font-normal text-ink focus:border-hybrid focus:outline-none" />
      </label>
      {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="rounded-md border border-line px-4 py-2 text-sm text-ink hover:border-muted">Hủy</button>
        <button type="button" disabled={busy} onClick={() => onConfirm(reason.trim())}
          className="rounded-md bg-danger px-4 py-2 text-sm font-semibold text-white hover:bg-danger/85 disabled:opacity-50">
          {busy ? 'Đang gỡ…' : 'Xác nhận gỡ'}
        </button>
      </div>
    </Modal>
  )
}

export function RecipeModal({ recipe, onClose }: { recipe: RecipeDetail | 'loading' | { error: string }; onClose: () => void }) {
  if (recipe === 'loading') return <Modal title="Công thức" onClose={onClose}><p className="text-sm text-muted">Đang tải…</p></Modal>
  if ('error' in recipe) return <Modal title="Công thức" onClose={onClose}><p className="text-sm text-danger">{recipe.error}</p></Modal>
  return (
    <Modal title={`R${recipe.id} · ${recipe.title}`} onClose={onClose} wide>
      <div className="flex flex-wrap gap-1.5 text-xs">
        {recipe.total_minutes != null && <span className="rounded bg-page px-1.5 py-0.5 text-ink-soft">{recipe.total_minutes} phút</span>}
        {recipe.allergens.map(a => <span key={a} className="rounded bg-danger/10 px-1.5 py-0.5 text-danger">chứa {ALLERGEN[a] ?? a}</span>)}
        {recipe.allergens_may.map(a => <span key={a} className="rounded bg-warn/12 px-1.5 py-0.5 text-warn">có thể chứa {ALLERGEN[a] ?? a}</span>)}
      </div>
      {recipe.summary && <p className="mt-3 text-sm text-ink-soft">{recipe.summary}</p>}
      <h3 className="mt-4 text-sm font-semibold text-ink">Nguyên liệu</h3>
      <ul className="mt-1 list-disc pl-5 text-sm text-ink-soft">{recipe.ingredients.map((l, i) => <li key={i}>{l}</li>)}</ul>
      <h3 className="mt-4 text-sm font-semibold text-ink">Cách làm</h3>
      <p className="mt-1 whitespace-pre-wrap text-sm text-ink-soft">{recipe.directions}</p>
      <p className="mt-4 text-xs text-muted">Luôn kiểm tra nhãn nguyên liệu: dữ liệu công thức có thể thiếu thành phần ẩn.</p>
    </Modal>
  )
}

function factLine(f: Record<string, unknown>): string {
  return Object.entries(f).filter(([, v]) => v != null && v !== '' && !(Array.isArray(v) && !v.length))
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.map(x => (typeof x === 'object' ? JSON.stringify(x) : String(x))).join('; ') : String(v)}`)
    .join(' · ')
}

/** The record tree as a model sees it (prompt views only), with the node an [H:] citation named opened. */
export function TreeDrawer({ nodes, focus, onClose }: { nodes: TreeNode[] | 'loading' | { error: string }; focus: string | null; onClose: () => void }) {
  return (
    <Modal title="Hồ sơ bệnh nhân (phần mô hình được thấy)" onClose={onClose} wide>
      {nodes === 'loading' ? <p className="text-sm text-muted">Đang tải…</p>
        : 'error' in nodes ? <p className="text-sm text-danger">{nodes.error}</p>
        : (
          <div className="flex flex-col gap-2">
            {nodes.map(n => (
              <details key={n.node_id} open={n.node_id === focus || (focus === null && n.kind === 'fixed')}
                className={`rounded-md border px-3 py-2 text-sm ${n.node_id === focus ? 'border-dense bg-dense/8' : 'border-line'}`}>
                <summary className="cursor-pointer text-ink">
                  <span className="font-medium">{n.title}</span>
                  <span className="ml-2 text-xs text-muted">{n.node_id}{n.summary ? ` · ${n.summary}` : ''}</span>
                </summary>
                {n.facts.length === 0 ? <p className="mt-1 text-xs text-muted">Không có mục nào được phép hiển thị.</p> : (
                  <ul className="mt-1.5 flex flex-col gap-1 text-xs text-ink-soft">
                    {n.facts.slice(0, 60).map((f, i) => <li key={i}>{factLine(f)}</li>)}
                    {n.facts.length > 60 && <li className="text-muted">… và {n.facts.length - 60} mục khác</li>}
                  </ul>
                )}
              </details>
            ))}
            <p className="text-xs text-muted">Chỉ hiển thị dữ liệu qua danh sách cho phép (ADR-0006): không có tên, không có dữ liệu nhạy cảm.</p>
          </div>
        )}
    </Modal>
  )
}

export function ChatSettings({ preset, onPreset, onClose }: { preset: string; onPreset: (p: string) => void; onClose: () => void }) {
  return (
    <Modal title="Cài đặt" onClose={onClose}>
      <fieldset>
        <legend className="mb-2 text-sm font-semibold text-ink">Cấu hình (preset)</legend>
        <p className="mb-3 text-xs text-muted">Đổi cấu hình sẽ mở phiên mới. Mọi cấu hình chạy cùng một code, chỉ khác cờ.</p>
        <div className="flex flex-col gap-1">
          {PRESETS.map(p => (
            <label key={p.name} className={`flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-sm ${p.name === preset ? 'bg-page' : 'hover:bg-page'}`}>
              <input type="radio" name="preset" checked={p.name === preset} onChange={() => onPreset(p.name)} className="mt-1" />
              <span><span className="font-medium text-ink">{p.name}</span> <span className="text-muted">{p.label}</span></span>
            </label>
          ))}
        </div>
      </fieldset>
    </Modal>
  )
}

