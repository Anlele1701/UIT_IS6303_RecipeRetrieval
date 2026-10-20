// §6 Error analysis: population counts first, then the overlap bias, Reranking's net effect, cases and error groups.
import { BUCKET_LONG, BUCKET_SHORT, CFG, CONFIGS, pct, pts, rank, STRATEGIES, STRATEGY_NAME } from './format'
import { ConfigLabel, Figure, Marker, Note, P, Pill, Section, Sub, Table, Toggle } from './parts'
import { CASE_STRATEGY, kindShare } from './data'
import type { Bucket, Bundle, Config } from './types'

const COUNTED: Bucket[] = ['sparse_win', 'dense_win', 'rerank_help', 'rerank_hurt', 'every_miss']

function Counts({ b }: { b: Bundle }) {
  const c = b.failures.bucket_counts
  return (
    <Table
      head={['', ...STRATEGIES.map(s => STRATEGY_NAME[s]), 'Under all three']} right={[1, 2, 3, 4]}
      rows={COUNTED.map(k => [<span title={BUCKET_LONG[k]}>{BUCKET_SHORT[k]}</span>, ...STRATEGIES.map(s => c.per_strategy[k][s]), c.all_strategies[k]])}
    />
  )
}

const overlapRow = (b: Bundle, c: Config, s: string, g: 'high' | 'low') =>
  b.failures.overlap.find(r => r.config === c && r.strategy === s && r.overlap === g)!['recall@5']

/** One small slope chart per strategy: R@5 on high-overlap queries (left) to low-overlap ones (right). */
function Slopes({ b }: { b: Bundle }) {
  const configs: Config[] = ['sparse', 'dense', 'hybrid']
  const y = (v: number) => 10 + (1 - (v - 0.6) / 0.4) * 150
  return (
    <div className="grid min-w-[30rem] grid-cols-3 gap-4">
      {STRATEGIES.map(s => (
        <div key={s}>
          <div className="mb-1 text-xs font-medium text-ink">{STRATEGY_NAME[s]}</div>
          <svg viewBox="0 0 200 190" className="w-full" role="img" aria-label={`${STRATEGY_NAME[s]}: R@5 on high and low overlap queries`}>
            {[0.6, 0.7, 0.8, 0.9, 1].map(t => (
              <g key={t}>
                <line x1="40" x2="190" y1={y(t)} y2={y(t)} className="stroke-[var(--line)]" />
                <text x="34" y={y(t) + 4} textAnchor="end" className="fill-[var(--muted)] text-[10px]">{pct(t, 0)}</text>
              </g>
            ))}
            {configs.map(c => {
              const hi = overlapRow(b, c, s, 'high'), lo = overlapRow(b, c, s, 'low')
              return (
                <g key={c}>
                  <line x1="60" x2="170" y1={y(hi)} y2={y(lo)} stroke={CFG[c].color} strokeWidth="2" />
                  <Marker config={c} x={60} y={y(hi)} size={8} />
                  <Marker config={c} x={170} y={y(lo)} size={8} />
                </g>
              )
            })}
            <text x="60" y="184" textAnchor="middle" className="fill-[var(--muted)] text-[10px]">high overlap</text>
            <text x="170" y="184" textAnchor="middle" className="fill-[var(--muted)] text-[10px]">low overlap</text>
          </svg>
        </div>
      ))}
    </div>
  )
}

function NetTable({ b }: { b: Bundle }) {
  const n = b.failures.rerank_net
  const lines: [string, (s: string) => number | string | null][] = [
    ['Reranking moved the Recipe down', s => n[s].hurt],
    ['Reranking moved the Recipe up', s => n[s].help],
    ['Same rank', s => n[s].same],
    ['Moved down and out of the top 5', s => n[s].hurt_left_top5],
    ['Moved up and into the top 5', s => n[s].help_entered_top5],
    ['Net change in queries with the Recipe in the top 5', s => (n[s].net_into_top5 >= 0 ? '+' : '−') + Math.abs(n[s].net_into_top5)],
    ['Median ranks lost when moved down', s => n[s].median_drop_when_hurt],
    ['Moved down and out of the top 20', s => n[s].hurt_left_top20],
    ['Moved up from outside the top 20', s => n[s].help_from_outside_top20],
  ]
  return <Table head={['Hybrid against the Fusion baseline', ...STRATEGIES.map(s => STRATEGY_NAME[s])]} right={[1, 2, 3]}
    rows={lines.map(([label, f]) => [label, ...STRATEGIES.map(s => f(s) ?? '–')])} highlight={[5]} />
}

function KindTable({ b }: { b: Bundle }) {
  const k = b.failures.hybrid_kinds
  if (!k || !Object.keys(k).length) return null
  const kinds = ['summary', 'ingredients', 'step']
  const share = (s: string, group: string, kind: string) => `${pct(kindShare(b, s, group, kind), 0)}%`
  return (
    <Table head={['Chunk that ranked the Recipe in Hybrid', ...STRATEGIES.flatMap(s => [`${STRATEGY_NAME[s]}: all`, 'moved down'])]} right={[1, 2, 3, 4, 5, 6]}
      rows={kinds.map(kind => [kind[0].toUpperCase() + kind.slice(1), ...STRATEGIES.flatMap(s => [share(s, 'all', kind), share(s, 'rerank_hurt', kind)])])} />
  )
}

function CaseCard({ b, id }: { b: Bundle; id: string }) {
  const c = b.cases.find(x => x.query_id === id)!
  const q = b.queries[id]
  const per = (s: string) => b.per_query.find(r => r.query_id === id && r.strategy === s)!
  const here = per(CASE_STRATEGY)
  return (
    <article className="rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-[15px] font-semibold text-ink">“{q.text}”</h4>
        <Pill title={BUCKET_LONG[c.bucket]}>{BUCKET_SHORT[c.bucket]}</Pill>
      </div>
      <p className="mt-1 text-xs text-muted">
        <span className="font-mono">{id}</span> · written from <span className="text-ink-soft">{q.recipe_title}</span>
        {q.right.length > 1 && ` · ${q.right.length} right Recipes`} · word overlap {q.word_overlap.toFixed(2)}
        {q.hand_rewritten && ' · rewritten by hand'}
      </p>
      <p className="mt-3 max-w-[46rem] text-sm text-ink-soft">{c.why}</p>
      <div className="mt-3 grid gap-4 md:grid-cols-[auto_1fr]">
        <Table head={['Rank of the first right Recipe', ...STRATEGIES.map(s => STRATEGY_NAME[s])]} right={[1, 2, 3]}
          rows={CONFIGS.map(cf => [<ConfigLabel config={cf} />, ...STRATEGIES.map(s => rank(per(s).ranks[cf]))])} />
        <div className="grid grid-cols-2 gap-3 text-xs">
          {CONFIGS.map(cf => (
            <div key={cf}>
              <div className="mb-1 font-medium text-ink"><ConfigLabel config={cf} /> <span className="font-normal text-muted">top 5, {STRATEGY_NAME[CASE_STRATEGY]}</span></div>
              <ol className="space-y-0.5">
                {here.top[cf].slice(0, 5).map((rid, i) => (
                  <li key={rid} className={`truncate ${q.right.includes(rid) ? 'font-semibold text-ok' : 'text-ink-soft'}`}>
                    <span className="mr-1 inline-block w-4 text-right text-muted tabular-nums">{i + 1}</span>{b.recipes[String(rid)]}
                  </li>
                ))}
                {here.top[cf].length === 0 && <li className="text-muted">No results.</li>}
              </ol>
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <Toggle label="the Recipe's description and ingredients">
          <div className="max-w-[46rem] space-y-2 text-xs text-ink-soft">
            <p>{c.description}</p>
            <ul className="list-disc pl-5">{c.ingredients.map((x, i) => <li key={i}>{x}</li>)}</ul>
          </div>
        </Toggle>
        <a className="mt-3 text-xs text-muted underline underline-offset-2 hover:text-ink" href={`?strategy=${CASE_STRATEGY}&q=${id}#appendix`}>See it in all queries</a>
      </div>
    </article>
  )
}

const GROUP_ORDER = ['near-duplicate', 'opaque title', 'lexical trap', 'other']
const GROUP_MEANING: Record<string, string> = {
  'near-duplicate': 'The top hits are arguably right, but the answer key doesn’t count them.',
  'opaque title': 'The Recipe’s name doesn’t describe the dish.',
  'lexical trap': 'One shared word pulls in a different dish.',
  other: 'None of the above.',
}

/** Queries no config finds under any Chunking strategy. */
const missedEverywhere = (b: Bundle) =>
  new Set(Object.keys(b.queries).filter(id => STRATEGIES.every(s => b.per_query.find(r => r.query_id === id && r.strategy === s)!.buckets.includes('every_miss'))))

function ErrorGroups({ b }: { b: Bundle }) {
  const missed = missedEverywhere(b)
  const byGroup = GROUP_ORDER.map(g => ({ g, ids: [...missed].filter(id => b.queries[id].error_group === g).sort() })).filter(x => x.ids.length)
  return (
    <Table head={['Group', 'Queries', 'What it means', 'Example']} right={[1]}
      rows={byGroup.map(({ g, ids }) => {
        const ex = ids[0] ? b.queries[ids[0]] : null
        const top = ids[0] ? b.per_query.find(r => r.query_id === ids[0] && r.strategy === CASE_STRATEGY)!.top.hybrid[0] : null
        return [g[0].toUpperCase() + g.slice(1), ids.length, GROUP_MEANING[g],
          ex ? <span>“{ex.text}” is written for <em>{ex.recipe_title}</em>; Hybrid's first hit is <em>{b.recipes[String(top)]}</em>.</span> : '–']
      })} />
  )
}

export function Errors({ b }: { b: Bundle }) {
  const f = b.failures, h = b.headline
  const gap = (s: string, g: 'high' | 'low') => overlapRow(b, 'sparse', s, g) - overlapRow(b, 'dense', s, g)
  const highGap = STRATEGIES.map(s => gap(s, 'high')), lowGap = STRATEGIES.map(s => gap(s, 'low'))
  const drop = (c: Config) => STRATEGIES.map(s => overlapRow(b, c, s, 'high') - overlapRow(b, c, s, 'low'))
  const hurtIngr = STRATEGIES.map(s => kindShare(b, s, 'rerank_hurt', 'ingredients'))
  const allIngr = STRATEGIES.map(s => kindShare(b, s, 'all', 'ingredients'))
  const leans = STRATEGIES.every((_, i) => hurtIngr[i] > allIngr[i])
  const rr = (xs: number[]) => {
    const lo = pct(Math.min(...xs), 0), hi = pct(Math.max(...xs), 0)
    return lo === hi ? lo : `${lo} to ${hi}`
  }
  const k = b.qrels
  const found = k.single_answer_every_miss - h.every_miss_all_strategies
  const nearAll = Object.values(b.queries).filter(q => q.error_group === 'near-duplicate').length
  const nearFound = k.every_miss_found_by_group['near-duplicate'] ?? 0
  const missed = missedEverywhere(b)
  const left = GROUP_ORDER.map(g => [g, [...missed].filter(id => b.queries[id].error_group === g).length] as const).filter(([, n]) => n)
  const unlabelled = [...missed].filter(id => !b.queries[id].error_group).length
  const all3 = f.bucket_counts.all_strategies
  const count = (k: Bucket) => {
    const xs = STRATEGIES.map(s => f.bucket_counts.per_strategy[k][s])
    return Math.min(...xs) === Math.max(...xs) ? String(xs[0]) : `${Math.min(...xs)} to ${Math.max(...xs)}`
  }
  return (
    <Section id="s6" title="6. Error analysis">
      <Sub id="s6-1" title="6.1 Where the configs disagree">
        <P>
          Sparse and Dense miss different queries. Under each Chunking strategy Sparse finds {count('sparse_win')} queries
          in its top {f.found_at} that Dense doesn't, and Dense finds {count('dense_win')} that Sparse doesn't.
          That is why fusing the two lists raises R@20. The last column counts queries in the same group under all three strategies.
        </P>
        <Counts b={b} />
        <Note>Hover a group for its exact rule. A query can be in more than one group.</Note>
      </Sub>

      <Sub id="s6-2" title="6.2 The synthetic queries favour Sparse">
        <P>
          Split the queries by word overlap and the Sparse against Dense result flips sign. On the {f.group_sizes.high} queries whose every
          content word appears in the Recipe, Sparse leads Dense by {rr(highGap)} points of R@5. On the other {f.group_sizes.low}, it trails
          by {rr(lowGap.map(x => -x))}. About half the Query set is high overlap, so the headline Sparse against Dense comparison leans
          toward Sparse. Low-overlap queries are harder for every config: Hybrid also drops {rr(drop('hybrid'))} points, against {rr(drop('sparse'))} for
          Sparse and {rr(drop('dense'))} for Dense.
        </P>
        <Figure caption="R@5 in percent on high-overlap queries (left end) and low-overlap queries (right end). The Sparse and Dense lines cross under every Chunking strategy.">
          <div className="mb-2 flex gap-4 text-xs text-ink-soft">{(['sparse', 'dense', 'hybrid'] as Config[]).map(c => <ConfigLabel key={c} config={c} />)}</div>
          <Slopes b={b} />
          <Toggle>
            <Table head={['Chunking strategy', 'Config', 'R@5 high overlap', 'R@5 low overlap', 'Drop']} right={[2, 3, 4]} groupStart={[0, 3, 6]}
              rows={STRATEGIES.flatMap(s => (['sparse', 'dense', 'hybrid'] as Config[]).map((c, i) => [
                i === 0 ? STRATEGY_NAME[s] : '', CFG[c].name, pct(overlapRow(b, c, s, 'high')), pct(overlapRow(b, c, s, 'low')),
                pts(overlapRow(b, c, s, 'low') - overlapRow(b, c, s, 'high'))]))} />
          </Toggle>
        </Figure>
      </Sub>

      <Sub id="s6-3" title="6.3 When Reranking hurts">
        <P>
          Reranking moves the Recipe down for {h.rerank_hurt.min} to {h.rerank_hurt.max} queries per Chunking strategy, but mostly by a rank or two,
          and it moves {h.rerank_help.min} to {h.rerank_help.max} up, often into the top 5. The net gain is {h.net_into_top5.min} to {h.net_into_top5.max} more
          queries with a right Recipe in the top 5, which is why Hybrid comes out ahead on average despite the hurts. The hurts are also unstable: only {all3.rerank_hurt} queries
          are hurt under all three Chunking strategies, which reads as near-ties flipping.
        </P>
        <NetTable b={b} />
        <P>
          One explanation is that the reranker judges a Recipe by a single Chunk, not by the whole Recipe. If so, the queries it moves
          down should often be won by a Chunk that says little about the dish, such as the ingredient list. When Reranking moved the Recipe
          down, its best Chunk in Hybrid's list was the Ingredients Chunk {rr(hurtIngr)}% of
          the time, against {rr(allIngr)}% over all queries.{' '}
          {leans
            ? 'The data leans that way: an ingredient list gives the reranker little to match a dish description against.'
            : 'With the served reranker the data doesn’t support it: Ingredients Chunks are no more common among the hurts than overall.'}
          {' '}The groups are small ({h.rerank_hurt.min} to {h.rerank_hurt.max} queries) and this split wasn't tested for significance.
        </P>
        <Toggle><KindTable b={b} /></Toggle>
        <Note>Chunk kinds come from the check runs, which rank every query exactly as the runs they check and record the Chunk that ranked the first right Recipe. Hybrid's come from the rerank check run. Queries Hybrid missed are left out of the shares.</Note>
      </Sub>

      <Sub id="s6-4" title="6.4 Case studies">
        <P>
          Five queries, one for each pattern above, picked by hand from the queries that show the pattern under all three Chunking
          strategies. Top-5 lists are from {STRATEGY_NAME[CASE_STRATEGY]}, the search page's default. Right Recipes are in green.
        </P>
        <div className="space-y-4">{b.cases.map(c => <CaseCard key={c.query_id} b={b} id={c.query_id} />)}</div>
      </Sub>

      <Sub id="s6-5" title="6.5 Queries every config misses">
        <P>
          {h.every_miss_all_strategies} queries have no right Recipe in any config's top 20 under all three Chunking strategies. With one
          right Recipe per query there were {k.single_answer_every_miss}, each labelled by hand. The pooled key found a right Recipe for {found} of
          them, including {nearFound === nearAll ? `all ${nearAll}` : `${nearFound} of the ${nearAll}`} near-duplicates, so those were gaps in the answer key,
          not retrieval failures. The {h.every_miss_all_strategies} left are real misses:
          {' '}{left.map(([g, n]) => `${n} ${g}${n > 1 ? 's' : ''}`).join(' and ')}{unlabelled ? `, and ${unlabelled} not labelled` : ''}.
          Their titles or a single shared word point the search at other dishes.
        </P>
        <ErrorGroups b={b} />
      </Sub>
    </Section>
  )
}

