// §4 Main results: configs, Chunking strategy, latency vs accuracy.
import { CFG, CONFIGS, dec, linear, log, METRIC_NAME, ms, numRange, pct, ptsRange, STRATEGIES, STRATEGY_NAME, times } from './format'
import { Axis, ConfigLabel, Figure, Forest, Grid, Legend, Marker, Note, P, Section, Sub, Table, Toggle } from './parts'
import { holmWhere, range } from './data'
import type { Bundle, Config, Metric, MetricRow } from './types'

const TABLE_METRICS: Metric[] = ['recall@5', 'recall@10', 'recall@20', 'mrr', 'ndcg@5', 'ndcg@10']

const row = (b: Bundle, c: Config, s: string) => b.metrics.find(m => m.config === c && m.strategy === s)!
const chunks = (b: Bundle, s: string) => Object.values(b.corpus.strategies[s].chunks).reduce((a, n) => a + n, 0)

function MainTable({ b }: { b: Bundle }) {
  const rows = STRATEGIES.flatMap(s => CONFIGS.map(c => row(b, c, s)))
  return (
    <Table
      head={['Chunking strategy', 'Config', ...TABLE_METRICS.map(m => METRIC_NAME[m]), 'R@5 95% CI', 'MRR 95% CI']}
      right={[2, 3, 4, 5, 6, 7, 8, 9]}
      groupStart={[0, 4, 8]}
      highlight={rows.flatMap((r, i) => (r.best_r5 ? [i] : []))}
      rows={rows.map((r, i) => [
        i % 4 === 0 ? STRATEGY_NAME[r.strategy] : '', <ConfigLabel config={r.config} />,
        ...TABLE_METRICS.map(m => (m.startsWith('recall') ? pct(r[m]) : dec(r[m]))),
        `${pct(r.ci['recall@5'].lo)}–${pct(r.ci['recall@5'].hi)}`, `${dec(r.ci.mrr.lo)}–${dec(r.ci.mrr.hi)}`,
      ])}
    />
  )
}

/** R@5 → R@20 per config and strategy: how much each config finds versus how much it puts on top. */
function Dumbbells({ b }: { b: Bundle }) {
  const ticks = [0.8, 0.85, 0.9, 0.95, 1]
  const at = linear(0.8, 1)
  return (
    <div className="min-w-[32rem] text-xs">
      <div className="grid grid-cols-[9rem_1fr] gap-x-3"><span /><Axis ticks={ticks} at={at} fmt={v => pct(v, 0)} /></div>
      {CONFIGS.map(c => (
        <div key={c} className="mt-1 border-t border-line pt-1">
          {STRATEGIES.map((s, i) => {
            const r = row(b, c, s)
            return (
              <div key={s} className="grid h-6 grid-cols-[9rem_1fr] items-center gap-x-3">
                <span className="text-ink-soft">{i === 0 ? <ConfigLabel config={c} /> : ''}<span className="float-right text-muted">{STRATEGY_NAME[s]}</span></span>
                <div className="relative h-full" title={`${CFG[c].name}, ${STRATEGY_NAME[s]}: R@5 ${pct(r['recall@5'])}%, R@20 ${pct(r['recall@20'])}%`}>
                  <Grid ticks={ticks} at={at} />
                  <div className="absolute top-1/2 h-[2px] -translate-y-1/2" style={{ left: `${at(r['recall@5'])}%`, width: `${at(r['recall@20']) - at(r['recall@5'])}%`, background: CFG[c].color, opacity: 0.45 }} />
                  <svg className="absolute inset-0 h-full w-full overflow-visible">
                    <circle cx={`${at(r['recall@20'])}%`} cy="50%" r="4" fill="var(--surface)" stroke={CFG[c].color} strokeWidth="2" />
                  </svg>
                  <svg className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 overflow-visible" style={{ left: `${at(r['recall@5'])}%` }}>
                    <Marker config={c} x={6} y={6} size={9} />
                  </svg>
                </div>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

const R5_TICKS = [0.75, 0.8, 0.85, 0.9, 0.95, 1]
const LAT_TICKS = [10, 30, 100, 300, 1000, 3000]
const x5 = linear(0.75, 1)
const xl = log(10, 3000)

/** §4.3 "aligned panels": R@5 with its CI next to latency (median p50, p50 range, line to p95), one row each. */
function AlignedPanels({ b }: { b: Bundle }) {
  const cols = 'grid grid-cols-[8rem_1fr_3rem_1fr_4.5rem] items-center gap-x-3'
  return (
    <div className="min-w-[40rem] text-xs">
      <div className={cols}>
        <div /><div className="font-medium text-ink-soft">Recall@5 (%)</div><div />
        <div className="font-medium text-ink-soft">Median p50 per query (ms, log scale)</div><div />
        <div /><Axis ticks={R5_TICKS} at={x5} fmt={v => pct(v, 0)} /><div /><Axis ticks={LAT_TICKS} at={xl} fmt={String} /><div />
      </div>
      {CONFIGS.map(c => (
        <div key={c} className="mt-2 border-t border-line pt-2">
          <div className="mb-1 font-medium text-ink"><ConfigLabel config={c} /></div>
          {STRATEGIES.map(s => {
            const r = row(b, c, s), t = r.latency.total, color = CFG[c].color
            return (
              <div key={s} className={`${cols} h-7`}>
                <div className="pl-5 text-muted">{STRATEGY_NAME[s]}</div>
                <div className="relative h-full" title={`R@5 ${pct(r['recall@5'])}%, 95% CI ${pct(r.ci['recall@5'].lo)}–${pct(r.ci['recall@5'].hi)}`}>
                  <Grid ticks={R5_TICKS} at={x5} />
                  <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full" style={{ left: `${x5(r.ci['recall@5'].lo)}%`, width: `${x5(r.ci['recall@5'].hi) - x5(r.ci['recall@5'].lo)}%`, background: color, opacity: 0.3 }} />
                  <div className="absolute top-1/2 h-4 w-[3px] -translate-x-1/2 -translate-y-1/2 rounded" style={{ left: `${x5(r['recall@5'])}%`, background: color }} />
                </div>
                <div className="text-right tabular-nums text-ink">{pct(r['recall@5'])}</div>
                <div className="relative h-full" title={`p50 ${ms(t.p50)} ms (range ${ms(t.p50_min)}–${ms(t.p50_max)}), p95 ${ms(t.p95)} ms`}>
                  <Grid ticks={LAT_TICKS} at={xl} />
                  <div className="absolute top-1/2 h-px -translate-y-1/2" style={{ left: `${xl(t.p50)}%`, width: `${xl(t.p95) - xl(t.p50)}%`, background: color, opacity: 0.6 }} />
                  <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full" style={{ left: `${xl(t.p50_min)}%`, width: `${Math.max(xl(t.p50_max) - xl(t.p50_min), 0.5)}%`, background: color, opacity: 0.3 }} />
                  <div className="absolute top-1/2 h-4 w-[3px] -translate-x-1/2 -translate-y-1/2 rounded" style={{ left: `${xl(t.p50)}%`, background: color }} />
                </div>
                <div className="text-right tabular-nums text-ink">{ms(t.p50)} ms</div>
              </div>
            )
          })}
        </div>
      ))}
      <div className={`${cols} mt-3 items-start text-muted`}>
        <div /><p>Tick: Recall@5. Shaded bar: 95% bootstrap CI.</p><div />
        <p>Tick: median p50 of the 3 Timing repeats (Hybrid: one run with the served reranker, so no range). Shaded bar: lowest to highest p50. Thin line: out to the median p95.</p><div />
      </div>
    </div>
  )
}

function LatencyTable({ rows }: { rows: MetricRow[] }) {
  const sorted = STRATEGIES.flatMap(s => CONFIGS.map(c => rows.find(r => r.strategy === s && r.config === c)!))
  return (
    <>
      <Table
        head={['Chunking strategy', 'Config', 'R@5 (%)', '95% CI', 'p50 ms', 'p50 range', 'p95 ms']}
        right={[2, 3, 4, 5, 6]} groupStart={[0, 4, 8]}
        highlight={sorted.flatMap((r, i) => (r.best_r5 ? [i] : []))}
        rows={sorted.map((r, i) => {
          const t = r.latency.total
          return [i % 4 === 0 ? STRATEGY_NAME[r.strategy] : '', <ConfigLabel config={r.config} />, pct(r['recall@5']),
            `${pct(r.ci['recall@5'].lo)}–${pct(r.ci['recall@5'].hi)}`, ms(t.p50), `${ms(t.p50_min)}–${ms(t.p50_max)}`, ms(t.p95)]
        })}
      />
      <Note>Green rows have the highest Recall@5 under their Chunking strategy. Ties are all marked.</Note>
    </>
  )
}

const STAGES = ['embed', 'sparse', 'dense', 'rrf', 'rerank']
const STAGE_NAME: Record<string, string> = { embed: 'Embedding the query', sparse: 'Sparse', dense: 'Dense', rrf: 'RRF', rerank: 'Reranking' }

function StageBar({ b }: { b: Bundle }) {
  return (
    <div className="min-w-[32rem]">
      <h4 className="text-sm font-medium text-ink">Hybrid query time by stage (median p50, ms)</h4>
      <div className="mt-2 space-y-2">
        {STRATEGIES.map(s => {
          const r = row(b, 'hybrid', s)
          const parts = STAGES.map(k => [k, r.latency[k]?.p50 ?? 0] as const)
          const total = parts.reduce((a, [, v]) => a + v, 0)
          return (
            <div key={s} className="grid grid-cols-[8rem_1fr_13rem] items-center gap-3 text-xs">
              <span className="pl-5 text-muted">{STRATEGY_NAME[s]}</span>
              <div className="flex h-4 gap-[2px]">
                {parts.map(([k, v]) => (
                  <div key={k} title={`${STAGE_NAME[k]}: ${ms(v)} ms`}
                    className={k === 'rerank' ? 'rounded-r bg-hybrid' : 'bg-muted/50 first:rounded-l'}
                    style={{ width: `${(v / total) * 100}%`, minWidth: 2 }} />
                ))}
              </div>
              <span className="text-right tabular-nums text-ink-soft">Reranking {ms(r.latency.rerank.p50)} of {ms(total)} ms</span>
            </div>
          )
        })}
      </div>
      <Note>Grey: embedding the query, Sparse, Dense and RRF, left to right. Purple: Reranking. Stage medians are taken separately, so they needn't add up to the total p50 exactly.</Note>
    </div>
  )
}

export function Results({ b }: { b: Bundle }) {
  const h = b.headline
  const pairs = b.significance.filter(t => t.arm === null && t.a.strategy !== t.b.strategy)
  const ratio = h.latency_ratio_hybrid_fusion
  const hf = b.significance.filter(t => t.arm === null && t.a.config === 'hybrid' && t.b.config === 'fusion')
  const sigText = (['recall@5', 'mrr'] as const).map(m => {
    const ts = hf.filter(t => t.metric === m)
    const on = ts.filter(t => t.p_holm < b.meta.alpha).map(t => STRATEGY_NAME[t.a.strategy])
    const raw = Math.max(...ts.map(t => t.p_raw))
    const name = METRIC_NAME[m]
    const where = on.length === ts.length ? 'under every Chunking strategy' : on.length ? `only under ${on.join(' and ')}` : 'under no Chunking strategy'
    return `the ${name} gain is significant after Holm ${where} (raw p at most ${raw.toFixed(3)})`
  }).join(', and ')
  const fewest = STRATEGIES.reduce((a, s) => (chunks(b, s) < chunks(b, a) ? s : a))
  const r5Diffs = (a: Config, o: Config) => range(holmWhere(b, a, o, 'recall@5').tests.map(t => t.diff))
  const sd = h.sparse_vs_dense_r5
  const sparseDense = sd.min > 0 ? `Sparse ahead by ${ptsRange(sd)} points of R@5`
    : sd.max < 0 ? `Dense ahead by ${ptsRange({ min: -sd.max, max: -sd.min })} points of R@5`
      : `within ${ptsRange({ min: 0, max: Math.max(-sd.min, sd.max) })} points of each other on R@5`
  const hybridOn = holmWhere(b, 'hybrid', 'fusion', 'recall@5').on
  const hybridSig = hybridOn.length === STRATEGIES.length ? 'significant after Holm under every Chunking strategy'
    : hybridOn.length ? `significant after Holm only under ${hybridOn.map(s => STRATEGY_NAME[s]).join(' and ')}` : 'not significant after Holm under any Chunking strategy'
  return (
    <Section id="s4" title="4. Main results">
      <Sub id="s4-1" title="4.1 Configs">
        <P>
          Each stage adds a few points and none adds many. Fusing Sparse and Dense raises R@5 by {ptsRange(r5Diffs('fusion', 'sparse'))} points
          over Sparse alone and {ptsRange(r5Diffs('fusion', 'dense'))} over Dense alone, and R@20 by {ptsRange(h.fusion_vs_sparse_r20)} and {ptsRange(h.fusion_vs_dense_r20)}.
          Reranking the fused list then adds {ptsRange(h.hybrid_vs_fusion_r5)} points of R@5 and {numRange(h.hybrid_vs_fusion_mrr, v => v.toFixed(3))} of MRR:
          {' '}{sigText}.{' '}
          {hybridOn.length === STRATEGIES.length
            ? 'Hybrid is the most accurate config, and its lead holds up under every Chunking strategy.'
            : hybridOn.length
              ? `So Hybrid's lead holds up only under ${hybridOn.map(s => STRATEGY_NAME[s]).join(' and ')}. Section 5.1 shows a reranker whose gain is clearer.`
              : "So Hybrid is the most accurate config on average, but with the served reranker its lead can't be told apart from chance at this sample size. Section 5.1 shows a reranker whose gain can."}
          {' '}Sparse and Dense are close overall, {sparseDense}, but they miss different queries (Section 6).
        </P>
        <MainTable b={b} />
        <Note>Recall in percent. Green rows have the highest R@5 under their Chunking strategy. CIs are 95% bootstrap intervals, not adjusted.</Note>
        <Figure caption="Each config's R@5 (filled marker) and R@20 (hollow circle). A long bar means the config finds the Recipe but ranks it low; Reranking shortens the bar from the left.">
          <Legend />
          <div className="mt-3"><Dumbbells b={b} /></div>
        </Figure>
      </Sub>
      <Sub id="s4-2" title="4.2 Chunking strategy">
        <P>
          The Chunking strategy makes no detectable difference to Hybrid. Every pair's interval crosses zero, and the smallest raw p
          is {h.strategy_pairs_min_p?.toFixed(2)}. A gap of one point is about three queries out of {b.metrics[0].queries}, well inside the
          noise at this sample size. A strategy is better picked on cost: {STRATEGY_NAME[fewest]} has the fewest Chunks to embed and index.
        </P>
        <Figure caption="Hybrid, difference between Chunking strategies, paired bootstrap. A hollow dot means the interval crosses zero.">
          <div className="space-y-4">
            {(['recall@5', 'mrr'] as const).map(m => (
              <div key={m}>
                <div className="mb-1 text-xs font-medium text-ink">{METRIC_NAME[m]}</div>
                <Forest unit={m === 'mrr' ? 'mrr' : 'pts'} ticks={m === 'mrr' ? [-0.1, -0.05, 0, 0.05, 0.1] : [-0.1, -0.05, 0, 0.05, 0.1]}
                  items={pairs.filter(t => t.metric === m).map(t => ({
                    key: t.a.strategy + t.b.strategy, label: `${STRATEGY_NAME[t.a.strategy]} − ${STRATEGY_NAME[t.b.strategy]}`,
                    diff: t.diff, lo: t.ci_lo, hi: t.ci_hi, p: t.p_holm, color: 'var(--hybrid)',
                  }))} />
              </div>
            ))}
          </div>
        </Figure>
      </Sub>
      <Sub id="s4-3" title="4.3 Latency vs accuracy">
        <P>
          Hybrid takes about {times(ratio.min)} to {times(ratio.max)} times as long per query as the Fusion baseline
          ({numRange(h.hybrid_p50, ms)} ms against {numRange(h.fusion_p50, ms)} ms median p50) and puts the right Recipe in the top 5 for
          {' '}{ptsRange(h.hybrid_vs_fusion_r5)} more queries in every 100 ({hybridSig}). Nearly all of the extra time is Reranking, {ptsRange(h.rerank_share)}% of
          Hybrid's p50. The other three configs answer in under 100 ms. Section 5 looks at cheaper rerankers, and Section 7 says
          when the trade is worth it.
        </P>
        <Figure>
          <AlignedPanels b={b} />
          <Toggle><LatencyTable rows={b.metrics} /></Toggle>
        </Figure>
        <Figure><StageBar b={b} /></Figure>
        <Note>
          On {STRATEGY_NAME[h.hybrid_p50_spread.strategy]}, Hybrid's p50 with bge-reranker-base moved between {ms(h.hybrid_p50_spread.min)} and {ms(h.hybrid_p50_spread.max)} ms
          across the three Timing repeats on the same code, which is why latency is shown as a range. Hybrid with the served mxbai-rerank-base-v1 was timed in one run only. Its p95 tail reaches {numRange({ min: Math.min(...STRATEGIES.map(s => row(b, 'hybrid', s).latency.total.p95)), max: Math.max(...STRATEGIES.map(s => row(b, 'hybrid', s).latency.total.p95)) }, ms)} ms.
        </Note>
      </Sub>
    </Section>
  )
}
