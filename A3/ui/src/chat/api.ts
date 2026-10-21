// Client for the chat API (api/chat_api.py, api/patient_api.py). Contract: docs/plan/A3_ke_hoach_build.md 6.5.

import { ApiError } from '../api'

export type Limit = [op: 'max' | 'min', value: number]

export interface Evidence { node_id: string; text: string }

export interface Group { group_id: string; node_id: string; text: string; members: string[] }

export interface Lift { constraint_id: string; members: string[]; reason: string | null; confirmed_at: string }

export interface PatientProfileEvent {
  patient_id: string
  allergens_exclude: string[]
  ingredients_exclude: string[]
  nutrient_limits: Record<string, Limit>
  nutrient_soft: Record<string, Limit>
  warnings: string[]
  evidence: Record<string, Evidence[]>
  lifted: Lift[]
  groups: Group[]
  nodes_read: string[]
}

export interface Constraints {
  allergens_exclude: string[]
  ingredients_exclude: string[]
  ingredients_include: string[]
  diet: string | null
  max_total_minutes: number | null
  max_calories: number | null
  category: string | null
  nutrient_limits: Record<string, Limit>
  nutrient_soft: Record<string, Limit>
}

export interface ConstraintsEvent {
  session_id: string
  message_id: number
  intent: string
  route: string
  clarify: string | null
  constraints: Constraints
  notices: string[]
  record_locked?: { constraint: string; message: string }[]
}

export interface RecipeBrief {
  id: number
  title: string
  total_minutes: number | null
  allergens: string[]
  allergens_may: string[]
  diet_flags: string[]
  score: number
  nutrients?: Record<string, number | null>
}

export interface DoneEvent {
  message_id: number
  answer: string
  citations: number[]
  verified: boolean
  regenerated: boolean
  usage: { prompt_tokens: number; completion_tokens: number; done_reason?: string | null }
  latency_ms: Record<string, number>
  flags?: string[]
  fallback?: boolean
}

export type ChatEvent =
  | { type: 'patient_profile'; data: PatientProfileEvent }
  | { type: 'constraints'; data: ConstraintsEvent }
  | { type: 'recipes'; data: RecipeBrief[] }
  | { type: 'token'; data: string }
  | { type: 'done'; data: DoneEvent }
  | { type: 'error'; data: { error: string; detail: string } }

export interface SessionConstraint {
  constraint_id: string
  type: string
  value: string
  scope: string
  source: 'dialogue' | 'patient'
  evidence: Evidence[]
}

export interface SessionView {
  id: string
  preset: string
  patient_id: string | null
  constraints: SessionConstraint[]
  lifted?: Lift[]
  groups?: Group[]
  warnings?: string[]
}

export interface PatientSummary {
  patient_id: string
  name: string
  source: string
  sex: string | null
  age_years: number | null
  record_date: string
  deceased: boolean
  summary?: { allergens: string[]; nutrient_limits: string[]; nutrient_soft: string[]; warnings: number }
}

export interface TreeNode {
  node_id: string
  parent_id: string | null
  kind: 'root' | 'fixed' | 'context'
  title: string
  summary: string | null
  facts: Record<string, unknown>[]
}

export interface PatientProfile {
  allergens_exclude: string[]
  nutrient_limits: Record<string, Limit>
  nutrient_soft: Record<string, Limit>
  warnings: string[]
  groups: Group[]
  evidence: Record<string, Evidence[]>
}

export interface RecipeDetail {
  id: number
  title: string
  total_minutes: number | null
  allergens: string[]
  allergens_may: string[]
  diet_flags: string[]
  summary: string
  ingredients: string[]
  directions: string
}

export interface LiftResult { kind: 'record' | 'dialogue'; constraint_id: string; members?: string[]; kept?: string[] }

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ApiError(0, 'Không kết nối được API. Kiểm tra uvicorn đang chạy.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const d = body?.detail
    throw new ApiError(res.status, typeof d === 'string' ? d : `API trả về HTTP ${res.status}.`)
  }
  return body as T
}

const json = (method: string, body: unknown): RequestInit =>
  ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const getPatients = () => call<PatientSummary[]>('/patients')
export const getTree = (id: string) => call<TreeNode[]>(`/patients/${id}/tree`)
export const getPatientProfile = (id: string) => call<PatientProfile>(`/patients/${id}/profile`)
export const getSession = (id: string) => call<SessionView>(`/sessions/${id}`)
export const getRecipe = (id: number) => call<RecipeDetail>(`/recipes/${id}`)
export const postFeedback = (message_id: number, rating: 1 | -1) =>
  call<{ id: number }>('/feedback', json('POST', { message_id, rating }))
export const removeConstraint = (session: string, constraintId: string, confirm = false, reason?: string) =>
  call<LiftResult>(`/chat/${session}/constraints/${constraintId}`, json('PATCH', { action: 'remove', confirm, reason }))

/**
 * POST /chat and read its SSE stream (EventSource cannot POST). Calls `onEvent` per event, in order.
 * A failure before the stream starts (409, 422...) throws an ApiError.
 */
export async function streamChat(
  body: { message: string; session_id?: string; preset?: string; patient_id?: string },
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch('/chat', { ...json('POST', body), signal })
  } catch (e) {
    if (signal?.aborted) throw e
    throw new ApiError(0, 'Không kết nối được API. Kiểm tra uvicorn đang chạy.')
  }
  if (!res.ok || !res.body) {
    const d = (await res.json().catch(() => null))?.detail
    throw new ApiError(res.status, typeof d === 'string' ? d : `API trả về HTTP ${res.status}.`)
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let cut
    while ((cut = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, cut)
      buffer = buffer.slice(cut + 2)
      let type = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) type = line.slice(7)
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (data) onEvent({ type, data: JSON.parse(data) } as ChatEvent)
    }
  }
}
