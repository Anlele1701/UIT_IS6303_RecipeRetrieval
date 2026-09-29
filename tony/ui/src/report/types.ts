// Shape of ui/public/report.json, written by scripts/report_bundle.py. The page reads it and computes nothing
// a claim rests on (see "Page data contract").

export type Config = 'sparse' | 'dense' | 'fusion' | 'hybrid'
export type Metric = 'recall@5' | 'recall@10' | 'recall@20' | 'mrr' | 'ndcg@5' | 'ndcg@10'
export type Stat = { p50: number; p95: number; p50_min: number; p50_max: number }
export type Range = { min: number; max: number }
export type Side = { config: Config; variant: 'default' | 'arm'; strategy: string }

export type MetricRow = Record<Metric, number> & {
  config: Config
  strategy: string
  queries: number
  short_lists: number
  ci: Record<'recall@5' | 'mrr', { lo: number; hi: number }>
  latency: Record<string, Stat>
  best_r5: boolean
}

export type Test = {
  arm: string | null
  a: Side
  b: Side
  metric: 'recall@5' | 'mrr'
  queries: number
  diff: number
  ci_lo: number
  ci_hi: number
  p_raw: number
  p_holm: number
}

export type TestResult = Pick<Test, 'diff' | 'ci_lo' | 'ci_hi' | 'p_raw' | 'p_holm'>

export type AblationRow = {
  arm: string
  set: Record<string, string | number>
  config: Config
  strategy: string
  default: Record<Metric, number>
  arm_metrics: Record<Metric, number>
  short_lists: { default: number; arm: number }
  tests: Partial<Record<'recall@5' | 'mrr', TestResult>>
  latency_same_run: Record<'default' | 'arm', Record<string, number>>
  latency_ratio: Record<string, number>
  p50_on_report_scale: number
  hnsw_indexes: { partition: string; index: string; bytes: number; options: string[] }[] | null
}

export type NetEffect = {
  hurt: number
  help: number
  same: number
  hurt_left_top5: number
  help_entered_top5: number
  net_into_top5: number
  median_drop_when_hurt: number | null
  hurt_left_top20: number
  help_from_outside_top20: number
}

export type Bucket = 'sparse_win' | 'dense_win' | 'rerank_help' | 'rerank_hurt' | 'every_miss'

export type PerQuery = {
  strategy: string
  query_id: string
  ranks: Record<Config, number | null>
  top: Record<Config, number[]>
  buckets: Bucket[]
}

export type Query = {
  text: string
  recipe_id: number
  recipe_title: string
  right: number[]  // every right Recipe in the pooled qrels, the written-from one included
  label_check: 'good' | 'partial' | 'wrong'
  vague: boolean
  word_overlap: number
  hand_rewritten: boolean
  edited_from: string | null
  edit_reason: string | null
  error_group: string | null
}

export type Case = { query_id: string; bucket: Bucket; why: string; description: string; ingredients: string[] }

export type StrategyCorpus = {
  parameters: Record<string, string | number>
  chunks: Record<'summary' | 'ingredients' | 'step', number>
  step_chars: { min: number; p10: number; median: number; p90: number; max: number; bin_width: number; bins: Record<string, number> }
}

export type Settings = Record<string, unknown> & {
  git_commit: string
  query_set_sha256: string
  strategies: string[]
  started_at: string
  seconds: number
}

export type Bundle = {
  meta: {
    manifest: {
      report_run: string; check_run: string; single_answer_run: string; qrels: string; qrels_check: string
      timing_repeats: string[]; ablation_runs: Record<string, string>; labels: Record<string, string>
    }
    runs: Record<string, Settings>
    input_hashes: Record<string, string>
    built_at: string
    alpha: number
  }
  metrics: MetricRow[]
  significance: Test[]
  ablations: AblationRow[]
  failures: {
    configs: Config[]
    counts: Record<string, Record<string, number>>
    group_sizes: { high: number; low: number }
    overlap: (Record<Metric, number> & { config: Config; strategy: string; overlap: 'high' | 'low' })[]
    rerank_net: Record<string, NetEffect>
    hybrid_kinds: Record<string, Record<string, Record<string, number>>>
    bucket_counts: { per_strategy: Record<Bucket, Record<string, number>>; all_strategies: Record<Bucket, number> }
    found_at: number
    high_overlap: number
  }
  per_query: PerQuery[]
  queries: Record<string, Query>
  recipes: Record<string, string>
  cases: Case[]
  qrels: {
    pool_depth: number
    judged_pairs: number
    relevant_judged: number
    queries_with_extra: number
    max_extra: number
    agreement: { pairs: number; agree: number; kappa: number }
    label_check: { good: number; partial: number; wrong: number; vague: number }
    single_answer_every_miss: number
    every_miss_found_by_group: Record<string, number>
    single_answer: (Record<Metric, number> & { config: Config; strategy: string })[]
  }
  corpus: {
    recipes: number
    categories: number
    strategies: Record<string, StrategyCorpus>
    category_recipes: Record<string, number>
  }
  query_set: {
    prompt: string
    model: string
    seed: number
    sampled: number
    queries: number
    skipped: number
    rewritten: number
    reasons: Record<string, number>
    overlap: { before_mean: number; after_mean: number; median: number; high: number; before_bins: number[]; after_bins: number[] }
    length: { mean: number; median: number; min: number; max: number }
    categories: { category: string; queries: number; query_share: number; corpus_share: number }[]
  }
  headline: Record<string, Range | number | null> & {
    hybrid_vs_fusion_r5: Range
    hybrid_vs_fusion_mrr: Range
    fusion_vs_sparse_r20: Range
    fusion_vs_dense_r20: Range
    sparse_vs_dense_r5: Range
    latency_ratio_hybrid_fusion: Range
    hybrid_p50: Range
    fusion_p50: Range
    hybrid_p50_spread: Range & { strategy: string }
    rerank_share: Range
    strategy_pairs_min_p: number | null
    net_into_top5: Range
    rerank_hurt: Range
    rerank_help: Range
    every_miss_all_strategies: number
    family_size: number
  }
}
