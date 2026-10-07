// §1 Problem and scope, §2 Dataset, §3 Evaluation setup.
import { CONFIGS, dec, int, pct, STRATEGIES, STRATEGY_NAME } from './format'
import { Bars, ConfigLabel, Figure, Note, P, Section, Stat, Sub, Table, Toggle } from './parts'
import { reportSettings } from './data'
import type { Bundle, Settings } from './types'


function SystemDiagram() {
  const box = 'fill-[var(--surface)] stroke-[var(--line)]'
  const text = 'fill-[var(--ink)] text-[12px]'
  const soft = 'fill-[var(--muted)] text-[11px]'
  return (
    <svg viewBox="0 0 720 230" className="w-full max-w-[46rem]" role="img"
      aria-label="The search page calls the FastAPI service. The service embeds the query with Ollama, runs Sparse and Dense retrieval in ParadeDB, fuses the two lists with RRF and reranks with the cross-encoder.">
      <defs>
        <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0 0L8 4L0 8Z" className="fill-[var(--muted)]" />
        </marker>
      </defs>
      <rect x="10" y="85" width="110" height="56" rx="8" className={box} />
      <text x="65" y="110" textAnchor="middle" className={text}>Search page</text>
      <text x="65" y="126" textAnchor="middle" className={soft}>React, ui/</text>

      <rect x="180" y="20" width="300" height="190" rx="10" className={box} />
      <text x="196" y="42" className={text} fontWeight={600}>FastAPI service (api/)</text>
      <rect x="196" y="56" width="128" height="92" rx="6" className="fill-[var(--page)] stroke-[var(--line)]" />
      <text x="260" y="98" textAnchor="middle" className={soft}>RRF fusion</text>
      <text x="260" y="114" textAnchor="middle" className={soft}>(Python)</text>
      <rect x="196" y="160" width="268" height="40" rx="6" className="fill-[var(--page)] stroke-[var(--hybrid)]" />
      <text x="330" y="184" textAnchor="middle" className={soft}>Reranking: cross-encoder on the laptop GPU (MPS)</text>
      <rect x="336" y="56" width="128" height="40" rx="6" className="fill-[var(--page)] stroke-[var(--line)]" />
      <text x="400" y="80" textAnchor="middle" className={soft}>SQL, Sparse and Dense</text>
      <rect x="336" y="108" width="128" height="40" rx="6" className="fill-[var(--page)] stroke-[var(--line)]" />
      <text x="400" y="132" textAnchor="middle" className={soft}>query embedding call</text>

      <rect x="560" y="20" width="150" height="80" rx="8" className={box} />
      <text x="635" y="48" textAnchor="middle" className={text}>ParadeDB</text>
      <text x="635" y="66" textAnchor="middle" className={soft}>one index per partition:</text>
      <text x="635" y="82" textAnchor="middle" className={soft}>BM25 + vectors + Filters</text>
      <rect x="560" y="130" width="150" height="56" rx="8" className={box} />
      <text x="635" y="154" textAnchor="middle" className={text}>Ollama</text>
      <text x="635" y="172" textAnchor="middle" className={soft}>nomic-embed-text</text>

      <path d="M120 113H176" className="stroke-[var(--muted)]" markerEnd="url(#arrow)" />
      <path d="M464 76H556" className="stroke-[var(--muted)]" markerEnd="url(#arrow)" />
      <path d="M464 128C512 128 512 158 556 158" fill="none" className="stroke-[var(--muted)]" markerEnd="url(#arrow)" />
    </svg>
  )
}

export function Problem({ b }: { b: Bundle }) {
  const s = reportSettings(b) as Settings & Record<string, number | string>
  return (
    <Section id="s1" title="1. Problem and scope">
      <Sub title="1.1 Problem">
        <P>
          Someone types a short description of a dish, and the system should return the Recipe they mean. The corpus is the
          Shengtao/recipe dataset from Hugging Face. Queries and Recipes are text only: the system reads titles,
          descriptions, ingredients and directions, and ignores the images.
        </P>
      </Sub>
      <Sub title="1.2 System and where the logic runs">
        <Figure caption="Everything runs on one laptop. ParadeDB and Ollama run next to the service; the eval calls the same retrieval code without going through HTTP.">
          <SystemDiagram />
        </Figure>
        <P>
          The database does index work: BM25 scoring, vector search and every Filter run inside one ParadeDB index per
          Chunking strategy, so a filtered search never pulls rows it will throw away. The service does the rest. It fuses the
          Sparse and Dense lists with RRF in Python and runs the cross-encoder, the only model heavy enough to need the GPU.
        </P>
        <P>
          RRF could run in SQL instead. It takes well under a millisecond in Python, so moving it would save one round trip at
          most, and it would split the Hybrid logic across two languages. Reranking can't move into the database at all, because
          it needs the model.
        </P>
      </Sub>
      <Sub title="1.3 The four configs">
        <P>The brief names four configurations. This report uses the project's own names for them from here on.</P>
        <Table
          head={['Brief', 'This report', 'What it does']}
          rows={[
            ['BM25-only', <ConfigLabel config="sparse" />, 'BM25 over Chunk text, from ParadeDB.'],
            ['Dense-only', <ConfigLabel config="dense" />, `Nearest Chunks to the query embedding by cosine distance (${s.embed_model}).`],
            ['Hybrid (RRF)', <ConfigLabel config="fusion" />,
              <>Top {s.hybrid_candidates} Chunks from Sparse and from Dense, merged with RRF (k = {s.rrf_k}). Evaluated but not served: it is Hybrid with Reranking switched off, kept to measure what Reranking adds.</>],
            ['Hybrid + Reranking', <ConfigLabel config="hybrid" />,
              <>The Fusion baseline's top {s.rerank_top} Chunks, reordered by the cross-encoder ({s.rerank_model}). This is what the search page serves.</>],
          ]}
        />
      </Sub>
    </Section>
  )
}

const FIELDS: [string, string][] = [
  ['title + description', 'Summary Chunk'],
  ['ingredients', 'Ingredients Chunk'],
  ['directions', 'Step Chunks, cut by the Chunking strategy'],
  ['category, times, rating, nutrition', 'Filters only, not searched'],
]

function StepHistogram({ name, c }: { name: string; c: Bundle['corpus']['strategies'][string] }) {
  const bins = Object.entries(c.step_chars.bins).map(([edge, n]) => [Number(edge), n] as const).sort((a, b) => a[0] - b[0])
  const max = Math.max(...bins.map(([, n]) => n))
  const top = c.step_chars.max
  const x = (v: number) => (v / (Math.ceil(top / c.step_chars.bin_width) * c.step_chars.bin_width)) * 100
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-ink">{STRATEGY_NAME[name]}</div>
      <div className="relative h-20 border-b border-line">
        {bins.map(([edge, n]) => (
          <div key={edge} className="absolute bottom-0 rounded-t-sm bg-ink-soft/60" title={`${edge}–${edge + c.step_chars.bin_width - 1} characters: ${int(n)} Chunks`}
            style={{ left: `${x(edge)}%`, width: `calc(${x(c.step_chars.bin_width)}% - 2px)`, height: `${(n / max) * 100}%` }} />
        ))}
        {(['p10', 'median', 'p90'] as const).map(k => (
          <div key={k} className="absolute -bottom-1 h-2 w-px bg-ink" style={{ left: `${x(c.step_chars[k])}%` }} />
        ))}
      </div>
      <div className="mt-1 text-[11px] text-muted tabular-nums">
        median {int(c.step_chars.median)} · p10 {int(c.step_chars.p10)} · p90 {int(c.step_chars.p90)} · max {int(c.step_chars.max)}
      </div>
    </div>
  )
}

function OverlapBins({ before, after }: { before: number[]; after: number[] }) {
  const max = Math.max(...before, ...after)
  const labels = ['0', '0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '1.0']
  return (
    <div className="min-w-[24rem] text-xs">
      <div className="flex h-28 items-end gap-1 border-b border-line">
        {after.map((a, i) => (
          <div key={i} className="flex h-full flex-1 items-end gap-[2px]" title={`${labels[i]}: ${before[i]} before, ${a} after`}>
            <div className="flex-1 rounded-t-sm bg-muted/40" style={{ height: `${(before[i] / max) * 100}%` }} />
            <div className="flex-1 rounded-t-sm bg-ink-soft" style={{ height: `${(a / max) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1 text-[11px] text-muted">{labels.map(l => <span key={l} className="flex-1 text-center">{l}</span>)}</div>
      <div className="mt-2 flex gap-4 text-[11px] text-muted">
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-muted/40" />before the hand rewrites</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-ink-soft" />after (the Query set as evaluated)</span>
      </div>
    </div>
  )
}

export function Dataset({ b }: { b: Bundle }) {
  const c = b.corpus, q = b.query_set
  const cats = Object.entries(c.category_recipes).sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0]))  // numeric-looking names would sort first
  const top = cats.slice(0, 10)
  const other = cats.slice(10).reduce((s, [, n]) => s + n, 0)
  const strategies = STRATEGIES.filter(s => c.strategies[s])
  const reasons = Object.entries(q.reasons).sort((a, b) => b[1] - a[1])
  const catRows = [...q.categories].sort((a, b) => b.queries - a.queries)
  return (
    <Section id="s2" title="2. Dataset">
      <Sub title="2.1 Source">
        <div className="grid grid-cols-3 gap-3">
          <Stat value={int(c.recipes)} label="Recipes, after dropping duplicate URLs" />
          <Stat value={int(c.categories)} label="categories" />
          <Stat value={int(q.queries)} label="queries in the Query set" />
        </div>
        <P>Each Recipe is split into Chunks by kind. Only text fields are searched; the rest become Filters.</P>
        <Table head={['Field', 'Becomes']} rows={FIELDS.map(([f, k]) => [f, k])} />
        <Figure caption="Recipes per category. The 10 largest are shown, and the other categories are summed in the last bar.">
          <Bars max={Math.max(...top.map(([, n]) => n), other)} fmt={int}
            items={[...top.map(([name, n]) => ({ key: name, label: name, value: n })), { key: 'other', label: `${cats.length - 10} other categories`, value: other }]} />
        </Figure>
      </Sub>
      <Sub title="2.2 Chunks and Chunking strategies">
        <P>
          Every Recipe has one Summary Chunk and one Ingredients Chunk under every Chunking strategy. The strategies only differ
          in how they cut the directions into Step Chunks.
        </P>
        <Table
          head={['Chunking strategy', 'Parameters', 'Summary', 'Ingredients', 'Step', 'Total']}
          right={[2, 3, 4, 5]}
          rows={strategies.map(s => {
            const k = c.strategies[s].chunks
            return [STRATEGY_NAME[s], Object.entries(c.strategies[s].parameters).map(([p, v]) => `${p} ${v}`).join(', '),
              int(k.summary), int(k.ingredients), int(k.step), int(k.summary + k.ingredients + k.step)]
          })}
        />
        <Figure caption="Length of Step Chunks in characters, without the title line every Chunk starts with. Ticks under each histogram mark p10, the median and p90. Characters, not tokens, because Fixed cuts by tokens and Semantic by characters.">
          <div className="grid min-w-[30rem] grid-cols-3 gap-4">{strategies.map(s => <StepHistogram key={s} name={s} c={c.strategies[s]} />)}</div>
        </Figure>
      </Sub>
      <Sub title="2.3 Query set">
        <P>
          The dataset has no queries, so {q.model} wrote one per Recipe for a sample of {q.sampled} Recipes, stratified by category
          (seed {q.seed}). {q.skipped} Recipes were skipped after three bad tries, which leaves {q.queries}. Every query was then
          read against its Recipe, and {q.rewritten} were rewritten by hand. A query is written from one Recipe, but other Recipes
          can answer it just as well; Section 3.1 describes how those were found.
        </P>
        <Toggle label="the prompt">
          <pre className="whitespace-pre-wrap rounded-md border border-line bg-page p-3 font-mono text-[11px] leading-relaxed text-ink-soft">{q.prompt}</pre>
        </Toggle>
        <Table head={['Why a query was rewritten', 'Queries']} right={[1]} rows={reasons.map(([r, n]) => [r, n])} />
        <P>
          Word overlap is the share of a query's content words (stemmed, stopwords dropped) that appear anywhere in its Recipe.
          The rewrites raised the mean from {q.overlap.before_mean.toFixed(2)} to {q.overlap.after_mean.toFixed(2)}, mostly by
          fixing queries that named ingredients the Recipe doesn't have. The median is {q.overlap.median.toFixed(1)}: {q.overlap.high} of
          the {q.queries} queries share every content word with their Recipe. Queries are {q.length.min} to {q.length.max} words
          long, {q.length.mean.toFixed(1)} on average.
        </P>
        <Figure caption="Queries by word overlap, before and after the hand rewrites. The last pair is exactly 1.0.">
          <OverlapBins before={q.overlap.before_bins} after={q.overlap.after_bins} />
        </Figure>
        <Toggle label="queries per category">
          <Table head={['Category', 'Queries', 'Share of queries', 'Share of Recipes']} right={[1, 2, 3]}
            rows={catRows.map(r => [r.category, r.queries, `${pct(r.query_share)}%`, `${pct(r.corpus_share)}%`])} />
        </Toggle>
      </Sub>
      <Sub title="2.4 Limits of the ground truth">
        <P>
          The queries are synthetic. An LLM that just read the Recipe tends to reuse its words, so these numbers flatter Sparse,
          which matches words. Section 6.2 measures by how much. The other right Recipes were judged by an LLM too, and only
          where some config ranked them in its top 5 (Section 3.1). A list with fewer than 20 unique Recipes counts its empty
          places as misses.
        </P>
      </Sub>
    </Section>
  )
}

const SETTING_ROWS: [string, string][] = [
  ['git_commit', 'Commit'], ['queries', 'Queries'], ['depth', 'Depth (unique Recipes ranked)'],
  ['chunk_pool', 'Chunks pulled by Sparse and Dense alone'], ['hybrid_candidates', 'Chunks per list before RRF'],
  ['rrf_k', 'RRF k'], ['rerank_top', 'Chunks sent to the reranker'], ['embed_model', 'Embedding model'],
  ['rerank_model', 'Reranker'], ['pg_search_version', 'pg_search version'],
  ['vector_cluster_max_probe', 'Dense index probe'], ['warmup_queries', 'Warm-up queries'], ['started_at', 'Started'], ['seconds', 'Run time (s)'],
]

export function Setup({ b }: { b: Bundle }) {
  const s = reportSettings(b) as Settings & Record<string, number | string>
  const repeats = b.meta.manifest.timing_repeats.map(r => b.meta.runs[r])
  const commits = [...new Set(repeats.map(r => r.git_commit))].join(', ')
  return (
    <Section id="s3" title="3. Evaluation setup">
      <P>
        Every query runs through the four configs under each of the three Chunking strategies. A config's result list is cut
        to its top {s.depth} unique Recipes, and a query is scored at the rank of its first right Recipe (Section 3.1). Recall@k is
        the share of queries with a right Recipe in the top k. MRR averages 1 / that rank (0 if there is none), and nDCG@k
        discounts the hit by its position. R@5 is the headline, because the search page shows five results by default; MRR comes second.
      </P>
      <P>
        Ranks come from the Report run on commit {s.git_commit}, rescored against the pooled answer key without searching
        again. A fresh run that scores with the answer key itself ranks every query identically. Latency comes from three Timing repeats of the same run on
        commit {commits}, which added a rotating config order, so no config always runs on a cache the others warmed. Their
        ranks were checked to be identical to the Report run's before any latency was used. Each number is the median over the
        three repeats, with the lowest and highest shown as a range. Hybrid is the exception: the search page now serves
        mxbai-rerank-base-v1, so every Hybrid number, ranks and latency, comes from a separate run with that reranker, whose Fusion
        ranks were checked to be identical to the Report run's.
      </P>
      <P>
        Significance comes from a paired bootstrap on per-query scores: 10,000 resamples of the {s.queries} queries, a 95%
        percentile interval on the difference, and a two-sided p. Holm's correction runs over all {b.headline.family_size} tests
        in the report at α = {b.meta.alpha}. Confidence intervals are not adjusted. A difference that isn't significant is
        reported as "no detectable difference", not as "the same". Resampling queries only speaks for queries like these
        synthetic ones.
      </P>
      <Note>
        Caveats. Everything ran on one M-series laptop, one query at a time, with one warm-up query and the reranker on the
        laptop GPU (MPS). Dense search is approximate: ParadeDB's vector index probes {pct(Number(s.vector_cluster_max_probe), 0)}%
        of its clusters (pg_search {s.pg_search_version}, image pinned by digest). The brief suggests pgvector HNSW; the served
        index stays ParadeDB's own because one index then serves Sparse, Dense and every Filter, and switching would invalidate
        every run here (ADR 0003). Section 5 measures both against exact search. Sparse and Dense on their own pull {s.chunk_pool} Chunks,
        while inside the Fusion baseline and Hybrid each pulls {s.hybrid_candidates}, so their stage times aren't directly comparable.
      </Note>
      <Toggle label="all settings">
        <Table head={['Setting', 'Value']} rows={SETTING_ROWS.filter(([k]) => k in s).map(([k, label]) => [label, String(s[k])])} />
      </Toggle>
      <AnswerKey b={b} />
    </Section>
  )
}

function AnswerKey({ b }: { b: Bundle }) {
  const k = b.qrels, n = b.query_set.queries
  const single = (c: string, st: string) => k.single_answer.find(r => r.config === c && r.strategy === st)!
  const pooled = (c: string, st: string) => b.metrics.find(r => r.config === c && r.strategy === st)!
  return (
    <Sub id="s3-1" title="3.1 The answer key">
      <P>
        The Query set gives each query one right Recipe, the one it was written from. That undercounts, because many queries fit
        other Recipes just as well. So the answer key was pooled: the top {k.pool_depth} Recipes of every config, Chunking strategy
        and Ablation arm went into one pool per query, and an LLM (Claude) judged each against the query with one strict rule. A
        Recipe is right if someone typing the query would be as happy with it as with the written-from Recipe: it has the dish, the
        key ingredients, the method and words like spicy or no-bake. Of {int(k.judged_pairs)} judged pairs, {k.relevant_judged} were
        right, so {k.queries_with_extra} of the {n} queries have more than one right Recipe (at most {k.max_extra + 1}).
      </P>
      <P>
        Two checks back it. A blind re-judge of {k.agreement.pairs} pairs agreed on {k.agreement.agree} (Cohen's κ {k.agreement.kappa.toFixed(2)}),
        with the disagreements split both ways. And every written-from Recipe was read against its query: {k.label_check.good} fit
        it fully, {k.label_check.partial} get one detail wrong but stay the closest Recipe, and {k.label_check.wrong} are
        wrong. {k.label_check.vague} queries are generic enough that many Recipes would fit.
      </P>
      <P>
        The pool is fair across configs, because every config's top {k.pool_depth} is in it. It is complete only to
        rank {k.pool_depth}: a right Recipe that no config ranked that high was never judged and counts as wrong. So R@5 is exact,
        while R@10, R@20 and MRR are slight underestimates. Relevance is right or wrong, with no partial credit.
      </P>
      <Figure caption="The Report run scored both ways. Every other number in this report uses the pooled key.">
        <Table
          head={['Chunking strategy', 'Config', 'R@5 one Recipe', 'R@5 pooled', 'MRR one Recipe', 'MRR pooled']}
          right={[2, 3, 4, 5]} groupStart={[0, 4, 8]}
          rows={STRATEGIES.flatMap(st => CONFIGS.map((c, i) => [
            i === 0 ? STRATEGY_NAME[st] : '', <ConfigLabel config={c} />,
            pct(single(c, st)['recall@5']), pct(pooled(c, st)['recall@5']), dec(single(c, st).mrr), dec(pooled(c, st).mrr)]))}
        />
      </Figure>
    </Sub>
  )
}
