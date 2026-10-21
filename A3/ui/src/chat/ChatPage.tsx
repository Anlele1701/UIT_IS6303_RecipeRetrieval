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
  const name = p.name || p.patient_id.slice(0, 8)
  return `${name} · ${who}${bits.length ? ` · ${bits.join(', ')}` : ''}`
}

const SparkIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
    <path d="M12 3l1.2 4.1a5 5 0 0 0 3.4 3.4l4.1 1.2-4.1 1.2a5 5 0 0 0-3.4 3.4L12 20.5l-1.2-4.2a5 5 0 0 0-3.4-3.4l-4.1-1.2 4.1-1.2a5 5 0 0 0 3.4-3.4L12 3Z" />
  </svg>
)

const PatientIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
    <circle cx="12" cy="8" r="3.5" /><path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
  </svg>
)

const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
    <path d="m3 11 17-8-8 17-2-7-7-2Z" /><path d="m10 13 10-10" />
  </svg>
)

const EXAMPLE_TITLES = ['Kiểm tra dị ứng', 'Hội thoại nhiều lượt', 'Không có đáp án', 'Gỡ ràng buộc']

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
  const selectedPatient = patients?.find(p => p.patient_id === patientId) ?? null
  const selectedSummary = selectedPatient?.summary
  const profileFacts = selectedSummary
    ? selectedSummary.allergens.length + selectedSummary.nutrient_limits.length + selectedSummary.nutrient_soft.length
    : 0

  return (
    <>
      <div className="mx-auto flex max-w-[1440px] flex-col px-4 pb-10 sm:px-8">
        <header className="flex flex-wrap items-center justify-between gap-4 py-6">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-hybrid text-white shadow-sm shadow-hybrid/20">
              <SparkIcon />
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold tracking-tight text-ink">Trợ lý công thức</h1>
                <span className="rounded-full bg-dense/10 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-dense">
                  VECTORLESS RAG
                </span>
              </div>
              <p className="text-sm text-muted">Gợi ý món ăn an toàn theo hội thoại và hồ sơ bệnh nhân.</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <SiteNav current="/chat" />
            <button type="button" onClick={() => setSettings(true)} aria-haspopup="dialog"
              className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm font-medium text-ink shadow-sm shadow-ink/5 transition hover:border-hybrid/40 hover:shadow">
              <SlidersIcon width={16} height={16} /> Cài đặt
              <span className="rounded bg-page px-1.5 py-0.5 text-xs font-semibold text-hybrid">{preset}</span>
            </button>
          </div>
        </header>

        <div role="note" className="mb-5 flex items-start gap-2 rounded-xl border border-warn/25 bg-warn/8 px-4 py-3 text-sm text-ink-soft">
          <span className="mt-0.5 text-warn" aria-hidden>◆</span>
          <p><strong className="font-medium text-ink">Lưu ý an toàn:</strong> Công cụ hỗ trợ chọn món, không thay lời khuyên y tế. Luôn kiểm tra nhãn nguyên liệu trước khi nấu.</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <main className="flex min-h-[60vh] flex-col">
            <div className="mb-4 rounded-xl border border-line bg-surface p-3 shadow-sm shadow-ink/5 sm:p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className={`grid size-9 shrink-0 place-items-center rounded-lg ${patientId ? 'bg-dense/12 text-dense' : 'bg-page text-muted'}`}>
                  <PatientIcon />
                </span>
                <label className="min-w-[240px] flex-1">
                  <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">Hồ sơ bệnh nhân</span>
                  <select value={patientId} disabled={patients === null}
                    onChange={e => reset(e.target.value, e.target.value ? 'P-Vectorless' : 'S')}
                    className="w-full rounded-lg border border-line bg-page px-3 py-2 text-sm font-medium text-ink focus:border-dense focus:outline-none focus:ring-3 focus:ring-dense/15 disabled:opacity-60">
                    <option value="">{patients === null ? 'Đang tải danh sách…' : 'Không dùng hồ sơ — chỉ dùng nội dung hội thoại'}</option>
                    {patients?.map(p => <option key={p.patient_id} value={p.patient_id}>{personLabel(p)}</option>)}
                  </select>
                </label>
                <div className="flex items-center gap-2 self-end">
                  {(view?.patient_id ?? patientId) && (
                    <button type="button" onClick={() => openNode(null)}
                      className="rounded-lg border border-dense/25 bg-dense/8 px-3 py-2 text-sm font-medium text-dense hover:bg-dense/12">
                      Xem cây hồ sơ
                    </button>
                  )}
                  <button type="button" onClick={() => reset(patientId, preset)}
                    className="rounded-lg border border-line bg-surface px-3 py-2 text-sm font-medium text-ink hover:border-muted">
                    + Phiên mới
                  </button>
                </div>
              </div>
              {selectedPatient && (
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line pt-3 text-xs">
                  <span className="font-semibold text-ink">{selectedPatient.name || selectedPatient.patient_id.slice(0, 8)}</span>
                  <span className="font-mono text-muted">{selectedPatient.patient_id.slice(0, 8)}</span>
                  <span className="text-ink-soft">{selectedPatient.sex === 'F' ? 'Nữ' : selectedPatient.sex === 'M' ? 'Nam' : 'Chưa rõ'} · {selectedPatient.age_years ?? '?'} tuổi</span>
                  <span className="inline-flex items-center gap-1.5 text-dense">
                    <span className="size-1.5 rounded-full bg-dense" /> {profileFacts} ràng buộc dinh dưỡng & dị ứng
                  </span>
                  {!!selectedSummary?.warnings && <span className="text-warn">{selectedSummary.warnings} cảnh báo</span>}
                  <span className="ml-auto rounded-full bg-hybrid/10 px-2 py-1 font-medium text-hybrid">Đang dùng {preset}</span>
                </div>
              )}
            </div>

            <div className="flex flex-1 flex-col gap-6 rounded-2xl border border-line bg-surface p-4 shadow-sm shadow-ink/5 sm:p-6" aria-live="polite">
              {turns.length === 0 && (
                <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center py-6">
                  <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-hybrid/10 text-hybrid">
                    <SparkIcon />
                  </div>
                  <h2 className="mt-4 text-center text-lg font-semibold text-ink">Bạn muốn tìm món gì hôm nay?</h2>
                  <p className="mx-auto mt-1 max-w-xl text-center text-sm leading-relaxed text-muted">
                    Hệ thống hiểu yêu cầu, áp dụng ràng buộc an toàn, truy hồi công thức rồi kiểm tra trích dẫn trước khi trả lời.
                  </p>
                  <div className="mt-5 grid gap-2 sm:grid-cols-3">
                    {['Hiểu yêu cầu', 'Lọc theo ràng buộc', 'Sinh & kiểm tra đáp án'].map((step, i) => (
                      <div key={step} className="flex items-center gap-2 rounded-lg bg-page px-3 py-2 text-xs text-ink-soft">
                        <span className="grid size-5 shrink-0 place-items-center rounded-full bg-hybrid text-[10px] font-bold text-white">{i + 1}</span>
                        {step}
                      </div>
                    ))}
                  </div>
                  <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-muted">Kịch bản demo nhanh</p>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {EXAMPLES.map((ex, i) => (
                      <button key={ex.text} type="button" title={ex.hint} onClick={() => send(ex.text)}
                        className="group rounded-xl border border-line bg-surface p-3 text-left transition hover:-translate-y-0.5 hover:border-hybrid/35 hover:shadow-md hover:shadow-hybrid/8">
                        <span className="text-xs font-semibold text-hybrid">{EXAMPLE_TITLES[i] ?? `Kịch bản ${i + 1}`}</span>
                        <span className="mt-1 block line-clamp-2 text-sm text-ink-soft group-hover:text-ink">{ex.text}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {turns.map((t, i) => (
                <div key={i} className="flex flex-col gap-3">
                  <div className="max-w-[85%] self-end rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 text-sm leading-relaxed text-surface shadow-sm">{t.user}</div>
                  {t.locked.map(l => (
                    <p key={l.constraint} className="self-end rounded-md border border-dense/40 bg-dense/8 px-3 py-1.5 text-xs text-ink">
                      🔒 {constraintText(l.constraint)}: {l.message}
                    </p>
                  ))}
                  <div className="flex max-w-[94%] items-start gap-3 text-sm text-ink">
                    <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-hybrid/10 text-hybrid"><SparkIcon /></span>
                    <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm bg-page px-4 py-3">
                    {t.clarify && <p className="mb-2 rounded-lg border border-warn/30 bg-warn/8 px-3 py-2 text-ink-soft">{t.clarify}</p>}
                    {t.text ? <AnswerText text={t.text} onRecipe={showRecipe} onNode={openNode} />
                      : t.done ? <span className="text-muted">Cấu hình này chỉ truy hồi công thức, không sinh câu trả lời (ví dụ B0).</span>
                      : !t.error && <span className="inline-flex items-center gap-2 text-muted">
                        {busy && i === turns.length - 1 && <><span className="flex gap-1" aria-hidden><i className="size-1.5 animate-pulse rounded-full bg-hybrid" /><i className="size-1.5 animate-pulse rounded-full bg-hybrid [animation-delay:150ms]" /><i className="size-1.5 animate-pulse rounded-full bg-hybrid [animation-delay:300ms]" /></span>Đang phân tích và truy hồi…</>}
                      </span>}
                    {t.error && <p role="alert" className="mt-2 rounded-md border border-danger/40 bg-danger/8 px-3 py-2 text-danger">{t.error}</p>}
                    {t.done && (
                      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-line pt-2 text-xs text-muted">
                        {t.done.fallback && <span className="rounded bg-page px-1.5 py-0.5">câu trả lời tóm tắt từ hồ sơ (do code viết)</span>}
                        {t.done.regenerated && <span>đã sinh lại sau kiểm tra</span>}
                        {t.done.usage.done_reason === 'length' && <span className="text-warn">câu trả lời bị cắt do quá dài</span>}
                        {t.done.verified && <span className="font-medium text-ok">✓ Đã kiểm tra trích dẫn</span>}
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
                  </div>
                  {t.recipes.length > 0 && (
                    <div className="ml-0 grid gap-3 sm:ml-11 sm:grid-cols-2">
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

            <form onSubmit={e => { e.preventDefault(); send(input) }} className="mt-3 flex gap-2 rounded-xl border border-line bg-surface p-2 shadow-sm shadow-ink/5 focus-within:border-hybrid/50 focus-within:ring-3 focus-within:ring-hybrid/10">
              <label className="flex-1">
                <span className="sr-only">Tin nhắn</span>
                <input value={input} onChange={e => setInput(e.target.value)} maxLength={2000} disabled={busy}
                  placeholder="Ví dụ: gợi ý món chay dưới 30 phút, không có nấm"
                  className="w-full border-0 bg-transparent px-3 py-2 text-base text-ink placeholder:text-muted/80 focus:outline-none disabled:opacity-60" />
              </label>
              <button type="submit" disabled={busy || !input.trim()}
                className="inline-flex items-center gap-2 rounded-lg bg-hybrid px-5 py-2 text-sm font-semibold text-white shadow-sm shadow-hybrid/20 hover:bg-hybrid/90 disabled:cursor-not-allowed disabled:opacity-40">
                Gửi <SendIcon />
              </button>
            </form>
          </main>

          <aside className="lg:sticky lg:top-6 lg:self-start">
            <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-sm shadow-ink/5">
              <div className="flex items-center justify-between border-b border-line bg-page/60 px-4 py-3">
                <div>
                  <p className="text-sm font-semibold text-ink">Ngữ cảnh an toàn</p>
                  <p className="text-xs text-muted">Được áp dụng trước khi truy hồi</p>
                </div>
                <span className={`size-2 rounded-full ${patientId || panel.dialogue.length ? 'bg-ok' : 'bg-muted/40'}`} title="Trạng thái ràng buộc" />
              </div>
              <div className="p-4">
              <ConstraintPanel data={panel} readOnly={!sessionId} onRemove={remove} onNode={openNode}
                onLift={t => { setLiftError(null); setLift(t) }} />
              {!sessionId && preview && <p className="mt-3 text-xs text-muted">Gửi tin nhắn đầu tiên để bắt đầu phiên; sau đó mới gỡ được ràng buộc.</p>}
              </div>
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
