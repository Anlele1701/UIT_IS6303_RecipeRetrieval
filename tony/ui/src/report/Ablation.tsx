// §5 Ablation: one Ablation run per arm, each arm compared with its default inside the same run.
import { CFG, dec, int, ms, numRange, pct, pts, pValue, STRATEGIES, STRATEGY_NAME, times } from './format'
import { ConfigLabel, Figure, Forest, Note, P, Section, Sub, Table } from './parts'
import { ARM_NAME, armSummary, hnswExactGap, holmWords, range, rows } from './data'
import type { AblationRow, Bundle, Config, Range } from './types'

function ArmForest({ b, arms, config, metric }: { b: Bundle; arms: string[]; config: Config; metric: 'recall@5' | 'mrr' }) {
  const items = arms.flatMap(arm => rows(b, arm, config).flatMap(r => {
    const t = r.tests[metric]
    return t ? [{ key: arm + r.strategy, label: <>{ARM_NAME[arm]} <span className="text-muted">· {STRATEGY_NAME[r.strategy]}</span></>,
      diff: t.diff, lo: t.ci_lo, hi: t.ci_hi, p: t.p_holm, color: CFG[config].color, extra: `${times(r.latency_ratio.total)}×` }] : []
  }))
  const ticks = metric === 'mrr' ? [-0.05, 0, 0.05, 0.1, 0.15, 0.2] : [-0.1, -0.05, 0, 0.05, 0.1]
  return <Forest items={items} ticks={ticks} unit={metric === 'mrr' ? 'mrr' : 'pts'} extraHead="latency" />
}

function ArmFigure({ b, arms, config, caption }: { b: Bundle; arms: string[]; config: Config; caption: string }) {
  return (
    <Figure caption={caption}>
      <div className="space-y-5">
        {(['recall@5', 'mrr'] as const).map(m => (
          <div key={m}>
            <div className="mb-1 text-xs font-medium text-ink">{m === 'mrr' ? 'MRR' : 'R@5'}, arm − default</div>
            <ArmForest b={b} arms={arms} config={config} metric={m} />
          </div>
        ))}
      </div>
    </Figure>
  )
}

const RERANKERS = ['reranker-minilm-l6', 'reranker-mxbai-base', 'reranker-bge-v2-m3']

function DenseIndexTable({ b }: { b: Bundle }) {
  const hnsw = b.ablations.some(r => r.arm === 'hnsw-dense')
  const configs: Config[] = ['dense', 'fusion', 'hybrid']
  const cell = (r: AblationRow | undefined, variant: 'default' | 'arm', m: 'recall@5' | 'mrr') =>
    r ? (m === 'mrr' ? dec((variant === 'arm' ? r.arm_metrics : r.default)[m]) : pct((variant === 'arm' ? r.arm_metrics : r.default)[m])) : '–'
  const out: React.ReactNode[][] = []
  const starts: number[] = []
  for (const c of configs) {
    starts.push(out.length)
    for (const s of STRATEGIES) {
      const exact = b.ablations.find(r => r.arm === 'exact-dense' && r.config === c && r.strategy === s)
      const hn = b.ablations.find(r => r.arm === 'hnsw-dense' && r.config === c && r.strategy === s)
      out.push([
        s === STRATEGIES[0] ? <ConfigLabel config={c} /> : '', STRATEGY_NAME[s],
        cell(exact, 'default', 'recall@5'), ...(hnsw ? [cell(hn, 'arm', 'recall@5')] : []), cell(exact, 'arm', 'recall@5'),
        cell(exact, 'default', 'mrr'), ...(hnsw ? [cell(hn, 'arm', 'mrr')] : []), cell(exact, 'arm', 'mrr'),
        ...(hnsw ? [hn ? `${times(hn.latency_ratio.dense)}×` : '–'] : []),
        exact ? `${times(exact.latency_ratio.dense)}×` : '–',
      ])
    }
  }
  const head = hnsw
    ? ['Config', 'Chunking strategy', 'R@5 served', 'R@5 HNSW', 'R@5 exact', 'MRR served', 'MRR HNSW', 'MRR exact', 'Dense time HNSW', 'Dense time exact']
    : ['Config', 'Chunking strategy', 'R@5 served', 'R@5 exact', 'MRR served', 'MRR exact', 'Dense time exact']
  return <Table head={head} rows={out} groupStart={starts} right={head.map((_, i) => i).slice(2)} />
}

export function Ablation({ b }: { b: Bundle }) {
  const a = b.meta.alpha
  const mini = armSummary(b, 'reranker-minilm-l6', 'hybrid')
  const mxbai = armSummary(b, 'reranker-mxbai-base', 'hybrid')
  const m3 = armSummary(b, 'reranker-bge-v2-m3', 'hybrid')
  const k10 = armSummary(b, 'rrf-k-10', 'fusion')
  const k100 = armSummary(b, 'rrf-k-100', 'fusion')
  const t20 = armSummary(b, 'rerank-top-20', 'hybrid')
  const t100 = armSummary(b, 'rerank-top-100', 'hybrid')
  const exactDense = armSummary(b, 'exact-dense', 'dense')
  const exactHybrid = armSummary(b, 'exact-dense', 'hybrid')
  const hasHnsw = b.ablations.some(r => r.arm === 'hnsw-dense')
  const hnswDense = hasHnsw ? armSummary(b, 'hnsw-dense', 'dense') : null
  const hnswHybrid = hasHnsw ? armSummary(b, 'hnsw-dense', 'hybrid') : null
  const report = b.meta.runs[b.meta.manifest.report_run] as Record<string, unknown>
  const queries = b.metrics[0].queries
  const idx = hasHnsw ? rows(b, 'hnsw-dense', 'dense')[0]?.hnsw_indexes : null
  const hnswGap = hnswExactGap(b)
  const denseStage = (arm: string) => range(rows(b, arm, 'dense').map(r => r.latency_same_run.arm.dense))
  const r = (x: Range) => numRange(x, v => pts(v))
  const m = (x: Range) => numRange(x, v => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(3))
  return (
    <Section id="s5" title="5. Ablation">
      <P>
        Each arm changes one setting and runs next to the default in the same Ablation run, query by query, under all three Chunking
        strategies. Differences are arm minus default on the same {queries} queries. Latency is the arm's p50 as a multiple of the
        default's in that run, because absolute times drift between runs. All {b.headline.family_size} tests share one Holm correction.
      </P>

      <Sub id="s5-1" title="5.1 Cross-encoder models">
        <P>
          The served reranker is {String(report.rerank_model)}. Three drop-in replacements ran in its place. mxbai-rerank-base-v1, the same
          size, gains {r(mxbai.r5)} points of R@5 ({holmWords(mxbai.r5Holm, a)}) and {m(mxbai.mrr)} MRR ({holmWords(mxbai.mrrHolm, a)}) at
          about {numRange(mxbai.ratio, times)}× the latency. bge-reranker-v2-m3 gains {r(m3.r5)} points of R@5 and {m(m3.mrr)} MRR but costs
          about {numRange(m3.ratio, times)}×. MiniLM-L6, the brief's suggestion, keeps R@5 where it is ({r(mini.r5)} points, {holmWords(mini.r5Holm, a)})
          at about {numRange(mini.ratio, times)}× the latency.
        </P>
        <ArmFigure b={b} arms={RERANKERS} config="hybrid"
          caption="Hybrid with each cross-encoder minus Hybrid with bge-reranker-base, paired bootstrap 95% CI. Holm p in bold when below 0.05; a hollow dot means the interval crosses zero. Latency: the arm's total p50 as a multiple of the default's, same run." />
      </Sub>

      <Sub id="s5-2" title="5.2 RRF k">
        <P>
          k sets how fast RRF's credit falls with rank. On the Fusion baseline, k = 10 gains {r(k10.r5)} points of R@5 and {m(k10.mrr)} MRR
          ({holmWords(k10.r5Holm, a)} on R@5) at the same latency, because a smaller k trusts the top of each list more. k = 100
          changes R@5 by {r(k100.r5)} points. Under Hybrid, k only decides which Chunks reach the reranker, which re-sorts them anyway,
          so it wasn't measured there.
        </P>
        <ArmFigure b={b} arms={['rrf-k-10', 'rrf-k-100']} config="fusion" caption="Fusion baseline with k = 10 and k = 100 minus k = 60, paired bootstrap 95% CI." />
      </Sub>

      <Sub id="s5-3" title="5.3 How many Chunks to rerank">
        <P>
          Reranking 20 Chunks instead of 50 changes R@5 by {r(t20.r5)} points ({holmWords(t20.r5Holm, a)}) and runs at
          about {numRange(t20.ratio, times)}× the latency, but {numRange(t20.shortArm, int)} of the {queries} lists then come back with fewer than 20
          Recipes, so R@10 and R@20 lose their meaning. Reranking 100 changes R@5 by {r(t100.r5)} points and MRR by {m(t100.mrr)} for
          about {numRange(t100.ratio, times)}× the latency. 50 stays.
        </P>
        <ArmFigure b={b} arms={['rerank-top-20', 'rerank-top-100']} config="hybrid" caption="Hybrid reranking 20 and 100 Chunks minus 50, paired bootstrap 95% CI." />
      </Sub>

      <Sub id="s5-4" title="5.4 Dense index: served, HNSW and exact">
        <P>
          The served Dense index is approximate. Exact search changes Dense's R@5 by {r(exactDense.r5)} points, and the loss mostly
          disappears inside Hybrid ({r(exactHybrid.r5)} points), because the reranker re-sorts what fusion found.
          {hnswDense && hnswHybrid
            ? <> pgvector HNSW (m 16, ef_construction 64, ef_search 200) changes Dense's R@5 by {r(hnswDense.r5)} points against the served index
              and Hybrid's by {r(hnswHybrid.r5)}. Its Dense stage takes {numRange(range(rows(b, 'hnsw-dense', 'dense').map(x => x.latency_ratio.dense)), times)}× the
              served index's time ({numRange(denseStage('hnsw-dense'), ms)} ms p50 in that run).
              {hnswGap === 0
                ? ' At ef_search 200 its R@5 equals exact search on every row (MRR is within a few thousandths), so on this corpus HNSW gets exact-quality results in less time than the served index gets approximate ones.'
                : hnswGap != null && hnswGap <= 2
                  ? ` At ef_search 200 its R@5 is within ${hnswGap} ${hnswGap === 1 ? 'query' : 'queries'} of exact search on every row, so on this corpus HNSW gets near-exact results in less time than the served index gets approximate ones.`
                  : ''}</>
            : ' The pgvector HNSW arm has not been added to the manifest yet.'}
        </P>
        <Figure caption={`R@5 in percent and MRR for each Dense index. "Served" is the default side of the exact-Dense Ablation run${hasHnsw ? ', which ranks identically to the HNSW run\'s default' : ''}. Dense time is the arm's Dense stage p50 as a multiple of the served index's, same run.`}>
          <DenseIndexTable b={b} />
        </Figure>
        {idx && <Note>HNSW indexes, one per partition: {idx.map(i => `${i.partition} ${(i.bytes / 1024 ** 2).toFixed(0)} MB`).join(', ')}. They existed only for this run and were dropped after it.</Note>}
        <Note>
          Exact Dense's own Dense stage ran at {numRange(denseStage('exact-dense'), ms)} ms p50. Compare Dense-stage times only: in both
          Dense-index runs, Hybrid's arm side also shows a slower Sparse stage, which the Dense change can't cause, so their total latency
          ratios for Hybrid aren't a fair measure. All Holm p for these rows are in the table below.
        </Note>
        <Table
          head={['Arm', 'Config', 'Chunking strategy', 'ΔR@5', 'Holm p', 'ΔMRR', 'Holm p']} right={[3, 4, 5, 6]}
          rows={['exact-dense', ...(hasHnsw ? ['hnsw-dense'] : [])].flatMap(arm => (['dense', 'fusion', 'hybrid'] as Config[]).flatMap(c => rows(b, arm, c).map(x => [
            ARM_NAME[arm], CFG[c].name, STRATEGY_NAME[x.strategy],
            x.tests['recall@5'] ? pts(x.tests['recall@5'].diff) : '–', x.tests['recall@5'] ? pValue(x.tests['recall@5'].p_holm) : '–',
            x.tests.mrr ? (x.tests.mrr.diff >= 0 ? '+' : '−') + dec(Math.abs(x.tests.mrr.diff)) : '–', x.tests.mrr ? pValue(x.tests.mrr.p_holm) : '–']))) }
        />
      </Sub>
      <Note>
        Logic placement wasn't measured as an arm. RRF runs in Python and costs well under a millisecond, so moving it into SQL could
        save one round trip at most (Section 1.2).
      </Note>
    </Section>
  )
}
