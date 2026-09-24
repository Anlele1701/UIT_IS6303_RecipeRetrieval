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
  query: string
  k: number
  took_ms: number
  results: Hit[]
}

export interface Health {
  chunker?: string
  reranker?: string
  reranker_device?: string
  chunks?: number
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
    return detail
  }
  return `The API returned HTTP ${status}.`
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, { signal })
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

export const getCategories = () => getJson<string[]>('/categories')

/** /health answers 503 with the same status object when a service is down. */
export async function getHealth(): Promise<Health> {
  const res = await fetch('/health')
  const body = await res.json()
  return res.ok ? body : body.detail
}
