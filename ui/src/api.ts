// Client for the FastAPI search service (api/main.py). See CONTEXT.md for the terms.

export type Method = 'sparse' | 'dense' | 'hybrid'
export type Kind = 'summary' | 'ingredients' | 'step'

export interface Hit {
  chunk_id: number
  recipe_id: number
  title: string
  kind: Kind
  position: number
  text: string
  score: number
  sparse_rank?: number
  dense_rank?: number
  rrf_score?: number
  rerank_score?: number
}

export interface SearchResponse {
  method: Method
  strategy: string
  query: string
  k: number
  took_ms: number
  results: Hit[]
}

/** A loaded Chunking strategy (GET /strategies). */
export interface Strategy {
  name: string
  method: string
  parameters: Record<string, unknown>
  loaded_at: string
}

export interface Health {
  reranker?: string
  reranker_device?: string
  /** Chunks per loaded Chunking strategy. */
  chunks?: Record<string, number>
  database?: string
  embedding?: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Detail = string | { loc: (string | number)[]; msg: string }[] | Record<string, unknown>

function errorMessage(status: number, detail: Detail | undefined): string {
  if (Array.isArray(detail)) return detail.map(e => `${e.loc.slice(1).join('.')}: ${e.msg}`).join('\n')
  if (typeof detail === 'string') {
    if (detail.startsWith('embedding service unavailable'))
      return 'The embedding service is not responding, so this method cannot run. Start Ollama, then search again.'
    if (status === 404 && detail.startsWith('no patient')) return 'That patient is not in the database.'
    return detail
  }
  return `The API returned HTTP ${status}.`
}

async function getJson<T>(url: string, signal?: AbortSignal, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, { signal, ...init })
  } catch (e) {
    if (signal?.aborted) throw e
    throw new ApiError(0, 'Cannot reach the search API. Check that uvicorn is running.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, errorMessage(res.status, body?.detail))
  return body as T
}

export const search = (method: Method, params: URLSearchParams, signal?: AbortSignal) =>
  getJson<SearchResponse>(`/search/${method}?${params}`, signal)

export const getStrategies = () => getJson<Strategy[]>('/strategies')

export const getCategories = () => getJson<string[]>('/categories')

/** /health answers 503 with the same status object when a service is down. */
export async function getHealth(): Promise<Health> {
  const res = await fetch('/health')
  const body = await res.json()
  return res.ok ? body : body.detail
}

// --- Patient recommender (POST /recommend, GET /patients) -------------------------------------

export interface PatientRow {
  patient_id: string
  display_name: string
  age: number
  gender: string
  active_conditions: number
}

export interface ActiveCondition {
  code: string
  description: string
  since: string
}

export interface ActiveAllergy {
  code: string
  description: string
  category: 'food' | 'environment' | 'medication' | null
  since: string
}

export interface PatientProfile {
  patient_id: string
  display_name: string
  age: number
  gender: string
  reference_date: string
  active_conditions: ActiveCondition[]
  active_allergies: ActiveAllergy[]
}

export interface AppliedLimit {
  rule_id: string
  label: string
  nutrient: string
  daily: number
  per_serving: number
  source: string
  rule_status: string
  conditions: ActiveCondition[]
  binding: boolean
}

export interface UnsupportedCondition extends ActiveCondition {
  rule_id: string
  reason: string
}

export interface DietPlan {
  patient_id: string
  status: 'filtered' | 'no_applicable_rules'
  filters: Record<string, number>
  evidence: AppliedLimit[]
  unapplied_limits: AppliedLimit[]
  unsupported_conditions: UnsupportedCondition[]
  unmatched_conditions: number
}

export interface LimitCheck {
  nutrient: string
  limit: number
  value: number | null
  ok: boolean
}

export interface RecommendedRecipe {
  rank: number
  recipe_id: number
  title: string
  category: string
  url: string
  rating: number
  total_minutes: number | null
  servings: number
  nutrition: Record<string, number | null>
  ingredients: string[]
  best_chunk: { kind: Kind; position: number; text: string; rerank_score: number | null }
  checks: LimitCheck[]
}

export interface AllergyExclusion {
  recipe_id: number
  title: string
  allergen: string
  matched: string
  where: string
}

export interface AllergyCheck {
  checked: string[]
  unchecked: string[]
  excluded: AllergyExclusion[]
}

export interface RecommendResponse {
  patient: PatientProfile
  query: string
  strategy: string
  k: number
  diet_plan: DietPlan
  recipes: RecommendedRecipe[]
  dropped_by_nutrition_check: number[]
  allergy_check: AllergyCheck
  warnings: string[]
  answer: string | null
  answer_error: string | null
  unverified_numbers: string[]
  timings_ms: Record<string, number>
}

export const getPatients = (params: URLSearchParams, signal?: AbortSignal) =>
  getJson<PatientRow[]>(`/patients?${params}`, signal)

export const recommend = (
  body: { patient_id: string; query: string; strategy: string; k: number; explain: boolean },
  signal?: AbortSignal,
) =>
  getJson<RecommendResponse>('/recommend', signal, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const getPatient = (id: string, signal?: AbortSignal) => getJson<PatientProfile>(`/patients/${id}`, signal)

export const getDietPlan = (id: string, signal?: AbortSignal) => getJson<DietPlan>(`/patients/${id}/diet-plan`, signal)

// --- Where the active conditions come from (GET /patients/{id}/active-conditions) ---------------

export type ConditionSource = 'sql' | 'tree' | 'dense'

export interface ConditionRef {
  code: string
  description: string
}

export interface ActiveConditionsResult {
  source: ConditionSource
  conditions: ConditionRef[]
  /** The answer key: always read from the tables. */
  sql_conditions: ConditionRef[]
  missing_vs_sql: string[]
  extra_vs_sql: string[]
  /** Sections (tree) or pieces (dense) that were read. */
  selected: string[]
  chars_read: number
  llm_calls: number
  invented_codes: string[]
  error: string | null
  timings_ms: Record<string, number>
}

export const getActiveConditions = (id: string, source: ConditionSource, signal?: AbortSignal) =>
  getJson<ActiveConditionsResult>(`/patients/${id}/active-conditions?source=${source}`, signal)
