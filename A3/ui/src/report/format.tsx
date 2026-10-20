// Names, colours and number formats shared by every section. Numbers only ever reach the page through these.
import type { Bucket, Config, Range } from './types'

export const CONFIGS: Config[] = ['sparse', 'dense', 'fusion', 'hybrid']
export const STRATEGIES = ['fixed', 'semantic', 'sentence']

// Sparse and Hybrid are hard to tell apart for deuteranopes, so every mark also carries a shape and a label.
export const CFG: Record<Config, { name: string; color: string; shape: 'circle' | 'square' | 'diamond' | 'triangle' }> = {
  sparse: { name: 'Sparse', color: 'var(--sparse)', shape: 'circle' },
  dense: { name: 'Dense', color: 'var(--dense)', shape: 'square' },
  fusion: { name: 'Fusion baseline', color: 'var(--fusion)', shape: 'diamond' },
  hybrid: { name: 'Hybrid', color: 'var(--hybrid)', shape: 'triangle' },
}

export const STRATEGY_NAME: Record<string, string> = { fixed: 'Fixed', semantic: 'Semantic', sentence: 'Sentence' }

export const METRIC_NAME: Record<string, string> = {
  'recall@5': 'R@5', 'recall@10': 'R@10', 'recall@20': 'R@20', mrr: 'MRR', 'ndcg@5': 'nDCG@5', 'ndcg@10': 'nDCG@10',
}

export const BUCKET_LONG: Record<Bucket, string> = {
  sparse_win: 'Sparse found the Recipe in the top 10 and Dense didn’t.',
  dense_win: 'Dense found the Recipe in the top 10 and Sparse didn’t.',
  rerank_help: 'Reranking ranked the Recipe higher than the Fusion baseline did.',
  rerank_hurt: 'Reranking ranked the Recipe lower than the Fusion baseline did.',
  every_miss: 'No config had the Recipe in its top 20.',
}

export const BUCKET_SHORT: Record<Bucket, string> = {
  sparse_win: 'Sparse beat Dense',
  dense_win: 'Dense beat Sparse',
  rerank_help: 'Reranking moved it up',
  rerank_hurt: 'Reranking moved it down',
  every_miss: 'Every config missed',
}

export const BUCKETS: Bucket[] = ['sparse_win', 'dense_win', 'rerank_help', 'rerank_hurt', 'every_miss']

/** 0.7348 → "73.5" (percent, no sign). */
export const pct = (x: number, digits = 1) => (x * 100).toFixed(digits)
/** 0.0906 → "+9.1" (percentage points, signed, typographic minus). */
export const pts = (x: number, digits = 1) => `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(digits)}`
/** MRR and nDCG as 0.xxx. */
export const dec = (x: number) => x.toFixed(3)
export const ms = (x: number) => (x >= 100 ? x.toFixed(0) : x.toFixed(1))
export const times = (x: number) => (x >= 10 ? x.toFixed(0) : x.toFixed(x >= 1 ? 1 : 2))
export const int = (x: number) => x.toLocaleString('en-US')
export const rank = (r: number | null) => (r == null ? '–' : String(r))
export const pValue = (p: number) => (p < 0.001 ? '< 0.001' : p >= 1 ? '1' : p.toFixed(3))

/** "7 to 9" style text for a range of fractions shown as points, or one number if both ends round the same. */
export function ptsRange(r: Range, digits = 0) {
  const lo = (r.min * 100).toFixed(digits), hi = (r.max * 100).toFixed(digits)
  return lo === hi ? lo : `${lo} to ${hi}`
}

export function numRange(r: Range, fmt: (x: number) => string) {
  const lo = fmt(r.min), hi = fmt(r.max)
  return lo === hi ? lo : `${lo} to ${hi}`
}

/** Positions in percent of a track, for charts drawn with positioned divs. */
export const linear = (lo: number, hi: number) => (v: number) => ((v - lo) / (hi - lo)) * 100
export const log = (lo: number, hi: number) => (v: number) =>
  ((Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo))) * 100
