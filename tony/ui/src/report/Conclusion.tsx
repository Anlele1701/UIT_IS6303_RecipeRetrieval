// §7 Conclusion and the references.
import { armSummary, hnswExactGap, holmWhere, holmWords, range } from './data'
import { ms, numRange, pct, pts, ptsRange, STRATEGIES, times } from './format'
import { ConfigLabel, P, Section, Sub, Table } from './parts'
import type { Bundle, Range } from './types'


export function Conclusion({ b }: { b: Bundle }) {
  const a = b.meta.alpha
  const mxbai = armSummary(b, 'reranker-mxbai-base', 'hybrid')
  const mini = armSummary(b, 'reranker-minilm-l6', 'hybrid')
  const k10 = armSummary(b, 'rrf-k-10', 'fusion')
  const get = (c: string, s: string) => b.metrics.find(m => m.config === c && m.strategy === s)!
  const r5 = (rows: typeof mxbai.rows) => range(rows.map(r => r.arm_metrics['recall@5']))
  const fusionR5 = range(STRATEGIES.map(s => get('fusion', s)['recall@5']))
  const hybridR5 = range(STRATEGIES.map(s => get('hybrid', s)['recall@5']))
  const fusionP50 = range(STRATEGIES.map(s => get('fusion', s).latency.total.p50))
  const pctR = (x: Range) => numRange(x, v => pct(v))
  const h = b.headline
  const hnswGap = hnswExactGap(b)
  const hybridOn = holmWhere(b, 'hybrid', 'fusion', 'recall@5').on
  const lift = range(b.qrels.single_answer.map(r => get(r.config, r.strategy)['recall@5'] - r['recall@5']))
  const hybridTop = (rows: { config: string; strategy: string; 'recall@5': number }[]) =>
    STRATEGIES.every(s => rows.filter(r => r.strategy === s).every(r => r.config === 'hybrid' || r['recall@5'] < rows.find(x => x.config === 'hybrid' && x.strategy === s)!['recall@5']))
  return (
    <Section id="s7" title="7. Conclusion">
      <Sub title="7.1 What to use">
        <P>
          Hybrid is the most accurate config, and the reranker is the setting that matters most.
          {hybridOn.length === STRATEGIES.length
            ? ' With the served reranker its lead over the Fusion baseline is already significant after Holm.'
            : ` With the served reranker its lead over the Fusion baseline (${ptsRange(h.hybrid_vs_fusion_r5)} points of R@5) is ${hybridOn.length ? 'significant after Holm on some Chunking strategies only' : 'not significant after Holm'}; a better reranker is what makes the gain clear.`}
          {' '}The choice depends on how much latency a search can take.
        </P>
        <Table
          head={['When', 'Config', 'R@5 (%)', 'p50 ms']} right={[2, 3]}
          rows={[
            ['Quality matters most', <><ConfigLabel config="hybrid" /> with mxbai-rerank-base-v1</>, pctR(r5(mxbai.rows)), numRange(mxbai.p50, ms)],
            ['Latency matters', <><ConfigLabel config="hybrid" /> with MiniLM-L6</>, pctR(r5(mini.rows)), numRange(mini.p50, ms)],
            ['Latency is critical', <ConfigLabel config="fusion" />, pctR(fusionR5), numRange(fusionP50, ms)],
          ]}
        />
        <P>
          mxbai-rerank-base-v1 is the headline recommendation. Its MRR gain over the served bge-reranker-base
          ({numRange(mxbai.mrr, v => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(3))}) is {holmWords(mxbai.mrrHolm, a)}, and
          its R@5 gain of {numRange(mxbai.r5, v => pts(v))} points is {holmWords(mxbai.r5Holm, a)}. It is the same size as the served model and
          costs about {numRange(mxbai.ratio, times)}× the latency. This report still measures bge-reranker-base everywhere else, because that is what the search
          page served when the runs were made; switching is a follow-up.
        </P>
        <P>
          MiniLM-L6 keeps today's R@5 ({pctR(hybridR5)}% with bge-reranker-base) at about {numRange(mini.ratio, times)}× the latency. The Fusion baseline
          answers in under 50 ms but gives up the Reranking gain. RRF k = 10 raises its MRR by {numRange(k10.mrr, v => v.toFixed(3))} at no cost
          ({holmWords(k10.mrrHolm, a)}), and its R@5 by {numRange(k10.r5, v => pts(v))} points ({holmWords(k10.r5Holm, a)}).
          Reranking 20 or 100 Chunks instead of 50 doesn't help: 20 leaves most lists short of 20 Recipes, and 100 costs more for nothing.
        </P>
        <P>
          The Chunking strategy makes no detectable difference, so pick it on cost. The Dense index question (Section 5.4) doesn't change
          the recommendation, because exact search barely moves Hybrid.
        </P>
      </Sub>
      <Sub title="7.2 What the method taught">
        <P>
          Two things would have gone wrong without the checks. Hybrid's p50 moved by up to{' '}
          {pct(h.hybrid_p50_spread.max / h.hybrid_p50_spread.min - 1, 0)}% between runs of the same code, so latency needs repeats and a range, and
          a fixed config order had later configs running on a warm cache. And the headline Sparse against Dense result hides a sign flip:
          which one wins depends on how many of the Recipe's words the query uses. Finally, the first answer key counted one right
          Recipe per query. Pooling it raised every config's R@5 by {ptsRange(lift)} points and showed that most of the queries every
          config &ldquo;missed&rdquo; had been answered{hybridTop(b.metrics) && hybridTop(b.qrels.single_answer) ? ', while Hybrid stayed the most accurate config under both keys' : ''}.
        </P>
      </Sub>
      <Sub title="7.3 Limits">
        <ul className="max-w-[46rem] list-disc space-y-1 pl-5 text-[15px] leading-relaxed text-ink-soft">
          <li>The queries are synthetic and favour Sparse (Section 6.2).</li>
          <li>The other right Recipes were judged by an LLM, only down to each config's top 5, and as right or wrong with no partial credit (Section 3.1).</li>
          <li>Lists with fewer than 20 unique Recipes count the empty places as misses.</li>
          <li>Everything ran on one laptop; on {h.hybrid_p50_spread.strategy[0].toUpperCase() + h.hybrid_p50_spread.strategy.slice(1)}, Hybrid's p50 varied between {ms(h.hybrid_p50_spread.min)} and {ms(h.hybrid_p50_spread.max)} ms across Timing repeats.</li>
          <li>Text only: images in the dataset were not used.</li>
        </ul>
      </Sub>
      <Sub title="7.4 Future work">
        <ul className="max-w-[46rem] list-disc space-y-1 pl-5 text-[15px] leading-relaxed text-ink-soft">
          <li>Serve mxbai-rerank-base-v1 and rerun the main tables.</li>
          {hnswGap != null && hnswGap <= 2 && <li>Try serving Dense from pgvector HNSW, which {hnswGap === 0 ? 'matched exact search on R@5' : `came within ${hnswGap} ${hnswGap === 1 ? 'query' : 'queries'} of exact search on R@5`} here in less Dense-stage time than the served index (Section 5.4). It means a second index per partition and fresh runs (ADR 0003).</li>}
          <li>Evaluate on real user queries, with a person checking a sample of the judged pairs and graded relevance instead of right or wrong.</li>
          <li>Re-time on a GPU server, where the cross-encoders' latency ranking may change. A hosted reranker API is another option, at the cost of a network hop and sending queries to a third party.</li>
        </ul>
      </Sub>
    </Section>
  )
}

const REFS: [string, string, string][] = [
  ['Shengtao/recipe dataset', 'Hugging Face', 'https://huggingface.co/datasets/Shengtao/recipe'],
  ['Cormack, Clarke and Büttcher. Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods', 'SIGIR 2009', 'https://doi.org/10.1145/1571941.1572114'],
  ['nomic-embed-text', 'Nomic AI', 'https://huggingface.co/nomic-ai/nomic-embed-text-v1.5'],
  ['BAAI/bge-reranker-base', 'BAAI', 'https://huggingface.co/BAAI/bge-reranker-base'],
  ['mixedbread-ai/mxbai-rerank-base-v1', 'Mixedbread', 'https://huggingface.co/mixedbread-ai/mxbai-rerank-base-v1'],
  ['ParadeDB (pg_search)', 'ParadeDB', 'https://docs.paradedb.com'],
  ['pgvector', 'GitHub', 'https://github.com/pgvector/pgvector'],
]

export function References() {
  return (
    <Section id="refs" title="References">
      <ol className="max-w-[46rem] list-decimal space-y-1 pl-5 text-sm text-ink-soft">
        {REFS.map(([title, where, url]) => (
          <li key={url}>{title}. {where}. <a className="break-all text-muted underline underline-offset-2 hover:text-ink" href={url}>{url}</a></li>
        ))}
      </ol>
    </Section>
  )
}
