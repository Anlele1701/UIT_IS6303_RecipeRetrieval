import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '../api'
import { SlidersIcon } from '../components/icons'
import { SiteNav } from '../components/SiteNav'
import { useTheme } from '../useTheme'
import {
  getPatientProfile, getPatients, getRecipe, getSession, getTree, postFeedback, removeConstraint, streamChat,
  type ConstraintsEvent, type DoneEvent, type Limit, type PatientSummary, type RecipeBrief, type RecipeDetail,
  type SessionView, type TreeNode,
} from './api'
import { ALLERGEN, EXAMPLES, constraintText, limitText } from './labels'
import { AnswerText, ChatSettings, ConstraintPanel, LiftDialog, RecipeCard, RecipeModal, TreeDrawer, type PanelData } from './parts'

interface Turn {
  user: string
  locked: { constraint: string; message: string }[]
  text: string           // streamed tokens, replaced by done.answer
  recipes: RecipeBrief[]
  limits: Record<string, Limit>
  done: DoneEvent | null
  error: string | null
  clarify: string | null
  rating: 1 | -1 | null
}

const NEW_TURN = (user: string): Turn =>
  ({ user, locked: [], text: '', recipes: [], limits: {}, done: null, error: null, clarify: null, rating: null })

function personLabel(p: PatientSummary): string {
  const who = `${p.sex === 'F' ? 'Nữ' : p.sex === 'M' ? 'Nam' : '?'}, ${p.age_years ?? '?'} tuổi`
  const s = p.summary
  const bits = s ? [...s.allergens.map(a => ALLERGEN[a] ?? a), ...s.nutrient_limits.map(c => `giới hạn ${c.split('_')[0]}`)] : []
  return `${p.patient_id.slice(0, 8)} · ${who}${bits.length ? ` · ${bits.join(', ')}` : ''}`
}

export default function ChatPage() {
  useTheme()
  const [patients, setPatients] = useState<PatientSummary[] | null>(null)
  const [patientId, setPatientId] = useState<string>('')
  const [preset, setPreset] = useState('S')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [view, setView] = useState<SessionView | null>(null)
  const [preview, setPreview] = useState<PanelData | null>(null)  // a chosen patient before the first message
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [highlight, setHighlight] = useState<number | null>(null)
  const [recipe, setRecipe] = useState<RecipeDetail | 'loading' | { error: string } | null>(null)
  const [tree, setTree] = useState<{ nodes: TreeNode[] | 'loading' | { error: string }; focus: string | null } | null>(null)
  const [lift, setLift] = useState<{ id: string; label: string; members: string[] } | null>(null)
  const [liftBusy, setLiftBusy] = useState(false)
  const [liftError, setLiftError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [settings, setSettings] = useState(false)
  const controller = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => { getPatients().then(setPatients).catch(() => setPatients([])) }, [])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [turns])

  const refresh = useCallback((sid: string) => getSession(sid).then(setView).catch(() => {}), [])

  const reset = useCallback((nextPatient: string, nextPreset: string) => {
    controller.current?.abort()
    setSessionId(null); setView(null); setTurns([]); setNotice(null); setProblem(null); setPreview(null)
    setPatientId(nextPatient); setPreset(nextPreset)
    if (nextPatient) {
      getPatientProfile(nextPatient).then(p => setPreview({
        dialogue: [], groups: p.groups, lifted: [], warnings: p.warnings,
        nutrients: [
          ...Object.entries(p.nutrient_limits).map(([c, l]) => ({ id: `nutrient:${c}`, text: limitText(c, l), soft: false,
            evidence: (p.evidence[`nutrient:${c}`] ?? []).map(e => e.text).join('; ') })),
          ...Object.entries(p.nutrient_soft).map(([c, l]) => ({ id: `soft:${c}`, text: limitText(c, l), soft: true,
            evidence: (p.evidence[`soft:${c}`] ?? []).map(e => e.text).join('; ') })),
        ],
      })).catch(e => setProblem(e instanceof ApiError ? e.message : String(e)))
    }
  }, [])

  const update = (fn: (t: Turn) => Turn) => setTurns(ts => [...ts.slice(0, -1), fn(ts[ts.length - 1])])

  const send = async (text: string) => {
    text = text.trim()
    if (!text || busy) return
    setInput(''); setBusy(true); setProblem(null); setNotice(null)
    setTurns(ts => [...ts, NEW_TURN(text)])
    const ctrl = (controller.current = new AbortController())
    let sid = sessionId
    try {
      await streamChat(
        sid ? { message: text, session_id: sid } : { message: text, preset, ...(patientId ? { patient_id: patientId } : {}) },
        e => {
          switch (e.type) {
            case 'constraints': {
              const c: ConstraintsEvent = e.data
              if (!sid) { sid = c.session_id; setSessionId(sid) }
              update(t => ({ ...t, locked: c.record_locked ?? [], clarify: c.clarify, limits: c.constraints.nutrient_limits }))
              break
            }
            case 'recipes': update(t => ({ ...t, recipes: e.data })); break
            case 'token': update(t => ({ ...t, text: t.text + e.data })); break
            case 'done': update(t => ({ ...t, text: e.data.answer, done: e.data })); break
            case 'error': update(t => ({ ...t, error: `${e.data.error}: ${e.data.detail}` })); break
          }
        },
        ctrl.signal,
      )
    } catch (e) {
      if (!ctrl.signal.aborted) update(t => ({ ...t, error: e instanceof ApiError ? e.message : String(e) }))
    } finally {
      setBusy(false)
      if (sid) refresh(sid)
    }
  }

  const remove = async (id: string) => {
    if (!sessionId) return
    try {
      await removeConstraint(sessionId, id)
      setNotice(`Đã bỏ "${constraintText(id)}". Áp dụng từ tin nhắn tiếp theo.`)
      refresh(sessionId)
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : String(e))
    }
  }

  const confirmLift = async (reason: string) => {
    if (!sessionId || !lift) return
    setLiftBusy(true); setLiftError(null)
    try {
      const out = await removeConstraint(sessionId, lift.id, true, reason || undefined)
      setNotice(out.kept?.length
        ? `Đã gỡ ${out.members?.length ?? 0} mục. Vẫn giữ ${out.kept.map(constraintText).join(', ')} vì một mục khác trong hồ sơ cũng yêu cầu.`
        : `Đã gỡ "${lift.label}" sau khi xác nhận. Áp dụng từ tin nhắn tiếp theo.`)
      setLift(null)
      refresh(sessionId)
    } catch (e) {
      setLiftError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setLiftBusy(false)
    }
  }

  const openRecipe = (id: number) => {
    setRecipe('loading')
    getRecipe(id).then(setRecipe).catch(e => setRecipe({ error: e instanceof ApiError ? e.message : String(e) }))
  }

  const showRecipe = (id: number) => {
    setHighlight(id)
    if (!document.getElementById(`recipe-${id}`)) openRecipe(id)
  }

  const openNode = (node: string | null) => {
    const pid = view?.patient_id ?? patientId
    if (!pid) return
    setTree({ nodes: 'loading', focus: node })
    getTree(pid).then(nodes => setTree({ nodes, focus: node }))
      .catch(e => setTree({ nodes: { error: e instanceof ApiError ? e.message : String(e) }, focus: node }))
  }

  const rate = async (i: number, rating: 1 | -1) => {
    const id = turns[i].done?.message_id
    if (!id) return
    await postFeedback(id, rating).catch(() => {})
    setTurns(ts => ts.map((t, j) => (j === i ? { ...t, rating } : t)))
  }

  const panel: PanelData = useMemo(() => {
    if (!view) return preview ?? { dialogue: [], groups: [], nutrients: [], lifted: [], warnings: [] }
    const record = view.constraints.filter(c => c.source === 'patient' && (c.type === 'nutrient' || c.type === 'nutrient_soft'))
    return {
      dialogue: view.constraints.filter(c => c.source === 'dialogue'),
      groups: view.groups ?? [],
      nutrients: record.map(c => {
        const m = /^(.+?)(<=|>=)(.+)$/.exec(c.value)
        const lim: Limit = [m?.[2] === '>=' ? 'min' : 'max', Number(m?.[3])]
        return { id: c.constraint_id, text: limitText(m?.[1] ?? c.value, lim), soft: c.type === 'nutrient_soft',
          evidence: c.evidence.map(e => e.text).join('; ') }
      }),
      lifted: view.lifted ?? [],
      warnings: view.warnings ?? [],
    }
  }, [view, preview])

  return (
    <>
      <div className="mx-auto flex max-w-[1440px] flex-col px-4 pb-10 sm:px-8">
        <header className="flex flex-wrap items-center justify-between gap-4 py-6">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-ink">Trợ lý công thức</h1>
            <p className="text-sm text-muted">Gợi ý món ăn theo dị ứng, chế độ ăn, thời gian và hồ sơ bệnh nhân.</p>
          </div>
          <div className="flex items-center gap-3">
            <SiteNav current="/chat" />
            <button type="button" onClick={() => setSettings(true)} aria-haspopup="dialog"
              className="inline-flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm font-medium text-ink hover:border-muted">
              <SlidersIcon width={16} height={16} /> Cài đặt <span className="text-xs text-muted">{preset}</span>
            </button>
          </div>
        </header>

        <p role="note" className="mb-4 rounded-lg border border-line bg-surface px-4 py-2.5 text-sm text-ink-soft">
          Công cụ chỉ hỗ trợ chọn món, không thay lời khuyên y tế. Luôn kiểm tra nhãn nguyên liệu trước khi nấu.
        </p>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <main className="flex min-h-[60vh] flex-col">
            <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
              <label className="flex items-center gap-2">
                <span className="text-muted">Hồ sơ bệnh nhân</span>
                <select value={patientId} onChange={e => reset(e.target.value, e.target.value ? 'P-Vectorless' : 'S')}
                  className="max-w-[420px] rounded-md border border-line bg-surface px-2 py-1.5 text-ink">
                  <option value="">Không dùng hồ sơ</option>
                  {patients?.map(p => <option key={p.patient_id} value={p.patient_id}>{personLabel(p)}</option>)}
                </select>
              </label>
              {(view?.patient_id ?? patientId) && (
                <button type="button" onClick={() => openNode(null)} className="text-hybrid hover:underline">Xem hồ sơ</button>
              )}
              <button type="button" onClick={() => reset(patientId, preset)}
                className="ml-auto rounded-md border border-line bg-surface px-3 py-1.5 text-ink hover:border-muted">Phiên mới</button>
            </div>

            <div className="flex flex-1 flex-col gap-6 rounded-xl border border-line bg-surface p-4 sm:p-6" aria-live="polite">
              {turns.length === 0 && (
                <div className="flex flex-col gap-3 text-sm">
                  <p className="text-muted">Thử một trong các kịch bản demo:</p>
                  <div className="flex flex-wrap gap-2">
                    {EXAMPLES.map(ex => (
                      <button key={ex.text} type="button" title={ex.hint} onClick={() => send(ex.text)}
                        className="rounded-full border border-line px-3 py-1 text-left text-ink-soft hover:border-muted hover:text-ink">{ex.text}</button>
                    ))}
                  </div>
                </div>
              )}
              {turns.map((t, i) => (
                <div key={i} className="flex flex-col gap-3">
                  <div className="self-end rounded-2xl rounded-br-sm bg-ink px-4 py-2 text-sm text-surface">{t.user}</div>
                  {t.locked.map(l => (
                    <p key={l.constraint} className="self-end rounded-md border border-dense/40 bg-dense/8 px-3 py-1.5 text-xs text-ink">
                      🔒 {constraintText(l.constraint)}: {l.message}
                    </p>
                  ))}
                  <div className="max-w-[90%] text-sm text-ink">
                    {t.text ? <AnswerText text={t.text} onRecipe={showRecipe} onNode={openNode} />
                      : t.done ? <span className="text-muted">Cấu hình này chỉ truy hồi công thức, không sinh câu trả lời (ví dụ B0).</span>
                      : !t.error && <span className="text-muted">{busy && i === turns.length - 1 ? 'Đang trả lời…' : ''}</span>}
                    {t.error && <p role="alert" className="mt-2 rounded-md border border-danger/40 bg-danger/8 px-3 py-2 text-danger">{t.error}</p>}
                    {t.done && (
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted">
                        {t.done.fallback && <span className="rounded bg-page px-1.5 py-0.5">câu trả lời tóm tắt từ hồ sơ (do code viết)</span>}
                        {t.done.regenerated && <span>đã sinh lại sau kiểm tra</span>}
                        {t.done.usage.done_reason === 'length' && <span className="text-warn">câu trả lời bị cắt do quá dài</span>}
                        <span>{(t.done.latency_ms.total / 1000).toFixed(1)} giây</span>
                        <span className="ml-auto flex gap-1">
                          {([1, -1] as const).map(r => (
                            <button key={r} type="button" onClick={() => rate(i, r)} aria-pressed={t.rating === r}
                              aria-label={r === 1 ? 'Hữu ích' : 'Không hữu ích'}
                              className={`rounded px-1.5 py-0.5 ${t.rating === r ? 'bg-page text-ink' : 'hover:bg-page'}`}>{r === 1 ? '👍' : '👎'}</button>
                          ))}
                        </span>
                      </div>
                    )}
                  </div>
                  {t.recipes.length > 0 && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {t.recipes.map(r => (
                        <RecipeCard key={r.id} r={r} limits={t.limits} cited={!!t.done?.citations.includes(r.id)}
                          highlight={highlight === r.id && i === turns.length - 1} onOpen={() => openRecipe(r.id)} />
                      ))}
                    </div>
                  )}
                </div>
              ))}
              <div ref={bottom} />
            </div>

            {problem && <p role="alert" className="mt-3 rounded-lg border border-danger/40 bg-danger/8 px-4 py-2 text-sm text-danger">{problem}</p>}
            {notice && <p role="status" className="mt-3 rounded-lg border border-ok/40 bg-ok/8 px-4 py-2 text-sm text-ink">{notice}</p>}

            <form onSubmit={e => { e.preventDefault(); send(input) }} className="mt-3 flex gap-2">
              <label className="flex-1">
                <span className="sr-only">Tin nhắn</span>
                <input value={input} onChange={e => setInput(e.target.value)} maxLength={2000} disabled={busy}
                  placeholder="Ví dụ: gợi ý món chay dưới 30 phút, không có nấm"
                  className="w-full rounded-lg border border-line bg-surface px-4 py-3 text-base text-ink placeholder:text-muted/80 focus:border-hybrid focus:outline-none focus:ring-3 focus:ring-hybrid/15 disabled:opacity-60" />
              </label>
              <button type="submit" disabled={busy || !input.trim()}
                className="rounded-lg bg-ink px-6 py-3 text-base font-semibold text-surface hover:bg-ink/85 disabled:cursor-not-allowed disabled:opacity-40">Gửi</button>
            </form>
          </main>

          <aside className="lg:sticky lg:top-6 lg:self-start">
            <div className="rounded-xl border border-line bg-surface p-4">
              <ConstraintPanel data={panel} readOnly={!sessionId} onRemove={remove} onNode={openNode}
                onLift={t => { setLiftError(null); setLift(t) }} />
              {!sessionId && preview && <p className="mt-3 text-xs text-muted">Gửi tin nhắn đầu tiên để bắt đầu phiên; sau đó mới gỡ được ràng buộc.</p>}
            </div>
          </aside>
        </div>
      </div>

      {recipe && <RecipeModal recipe={recipe} onClose={() => setRecipe(null)} />}
      {tree && <TreeDrawer nodes={tree.nodes} focus={tree.focus} onClose={() => setTree(null)} />}
      {lift && <LiftDialog target={lift} busy={liftBusy} error={liftError} onConfirm={confirmLift} onClose={() => setLift(null)} />}
      {settings && <ChatSettings preset={preset} onPreset={p => { setSettings(false); reset(patientId, p) }} onClose={() => setSettings(false)} />}
    </>
  )
}
