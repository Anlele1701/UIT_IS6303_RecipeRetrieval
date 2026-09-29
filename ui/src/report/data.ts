// Data helpers shared by the sections. Selection and ranges only; the bundle already holds every computed number.
import { STRATEGIES } from './format'
import type { Bundle, Config, Range } from './types'

export const reportSettings = (b: Bundle) => b.meta.runs[b.meta.manifest.report_run]

export const CASE_STRATEGY = 'semantic'  // the search page's default Chunking strategy

/** Share of `kind` among the queries in `group` where Hybrid found the Recipe (misses left out). */
export function kindShare(b: Bundle, s: string, group: string, kind: string) {
  const g = b.failures.hybrid_kinds[s][group]
  const found = Object.entries(g).filter(([x]) => x !== 'miss').reduce((a, [, n]) => a + n, 0)
  return found ? (g[kind] ?? 0) / found : 0
}

export const ARM_NAME: Record<string, string> = {
  'reranker-minilm-l6': 'MiniLM-L6',
  'reranker-mxbai-base': 'mxbai-rerank-base-v1',
  'reranker-bge-v2-m3': 'bge-reranker-v2-m3',
  'rrf-k-10': 'RRF k = 10',
  'rrf-k-100': 'RRF k = 100',
  'rerank-top-20': '20 Chunks reranked',
  'rerank-top-100': '100 Chunks reranked',
  'exact-dense': 'Exact Dense',
  'hnsw-dense': 'pgvector HNSW',
}

export const rows = (b: Bundle, arm: string, config?: Config) =>
  b.ablations.filter(r => r.arm === arm && (!config || r.config === config)).sort((x, y) => STRATEGIES.indexOf(x.strategy) - STRATEGIES.indexOf(y.strategy))

export const range = (xs: number[]): Range => ({ min: Math.min(...xs), max: Math.max(...xs) })

export function armSummary(b: Bundle, arm: string, config: Config) {
  const rs = rows(b, arm, config)
  const t = (m: 'recall@5' | 'mrr') => rs.map(r => r.tests[m]).filter(x => x != null)
  return {
    rows: rs,
    r5: range(t('recall@5').map(x => x.diff)),
    mrr: range(t('mrr').map(x => x.diff)),
    r5Holm: range(t('recall@5').map(x => x.p_holm)),
    mrrHolm: range(t('mrr').map(x => x.p_holm)),
    ratio: range(rs.map(r => r.latency_ratio.total)),
    p50: range(rs.map(r => r.p50_on_report_scale)),
    shortArm: range(rs.map(r => r.short_lists.arm)),
  }
}


export const holmWords = (p: Range, alpha: number) =>
  p.max < alpha ? 'significant after Holm' : p.min < alpha ? 'significant after Holm on some Chunking strategies only' : 'not significant after Holm'

/** Largest R@5 gap between the HNSW and exact-Dense arms over every config and strategy, in queries; null without HNSW. */
export function hnswExactGap(b: Bundle): number | null {
  const hn = b.ablations.filter(r => r.arm === 'hnsw-dense')
  if (!hn.length) return null
  const gaps = hn.map(x => {
    const e = b.ablations.find(y => y.arm === 'exact-dense' && y.config === x.config && y.strategy === x.strategy)
    return e ? Math.round(Math.abs(e.arm_metrics['recall@5'] - x.arm_metrics['recall@5']) * b.metrics[0].queries) : Infinity
  })
  return Math.max(...gaps)
}

/** Strategies where the main-run test of `a` against `b` on `metric` is significant after Holm, and all tested ones. */
export function holmWhere(b: Bundle, a: Config, other: Config, metric: 'recall@5' | 'mrr') {
  const ts = b.significance.filter(t => t.arm === null && t.a.config === a && t.b.config === other && t.metric === metric
    && t.a.strategy === t.b.strategy)
  return { on: ts.filter(t => t.p_holm < b.meta.alpha).map(t => t.a.strategy), tests: ts }
}
