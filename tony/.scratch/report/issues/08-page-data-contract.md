# Page data contract

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by: 01
Parent: ../map.md

## Question

How the Report page gets its data.

- Which run files it reads (`metrics.json`, `per_query.csv`, `settings.json`, `queries.jsonl`, failure lists, `significance.json` from "Significance tests") and in what shape. CSV in the browser, or converted to JSON?
- How it gets them: copied into `ui/public` at build time, or served by an API route that reads `eval/runs/`.
- How it knows which run is "the report run", and how ablation runs sit next to it.
- Recipe titles: `per_query.csv` stores only `top_recipe_ids`. Case studies need the titles (and maybe text) of wrong hits. Export them into the run, or look them up live?
- Does the page work without the DB and Ollama running? It should if it's to be graded.
- Where the report prose lives (markdown next to the data, or in components).

## Answer

The page reads one committed, derived JSON file (the report bundle). It never talks to FastAPI, the DB or Ollama, and computes nothing a claim rests on.

- **Transport**: a Python bundle script reads the run folders and writes the bundle into `ui/public/`. The file is committed, and the page `fetch`es it. Works under `vite preview`, FastAPI or any static host.
- **Who computes**: Python only. Metrics, bootstrap CIs, significance, overlap splits, failure counts and the rerank_hurt breakdown are all in the bundle. The page formats and plots. Per-query rows are included only for drill-down.
- **Which run**: a committed manifest (e.g. `eval/report.json`) names the Report run and maps each ablation arm to where its results live. The bundle script reads only what it names. Works for either arm storage layout (still fog on the map).
- **Prose**: TSX, one component per section. Every number comes from the bundle through small format helpers. Nothing is hand-typed.
- **Route**: path `/report`, switched on `location.pathname` in `App.tsx` with no router library, plus one `FileResponse` route in `api/main.py`.
- **Recipe titles**: every Recipe in any top-20 list (~10.1k, ~500 KB). ~~Read from `data/recipe.csv`.~~ Amended by "Failure cases and the synthetic-query bias": `recipe_id` is not a `recipe.csv` row index, so `evaluate.py` writes `recipes.csv` (recipe_id, url, title) into the run folder and the bundle reads titles from it.
- **Case text**: Recipe-level description and ingredients from `recipe.csv`, joined on `url` (see the amendment above), only for case-study queries. No matched Chunk text (it would need Chunk ids in `per_query.csv` and the DB). If "Explaining rerank_hurt" needs Chunk-level evidence, it reopens this.
- **Failure data**: the bundle script imports `failures.analyze_run()` directly. Run folders stay what `evaluate.py` wrote, plus `significance.json` (already decided: slow, seeded).
- **Freshness**: the bundle stores the manifest's run folders and a hash of each input file. A pytest recomputes the hashes and fails on mismatch. Not built inside `npm run build`, because that would need Python and `recipe.csv` in the UI build.
- **Hand rewrites**: `hand_rewritten` comes from the `edited_from` field already in `queries.jsonl`.

Skeleton (inner fields of `failures` and `cases` get added by "Explaining rerank_hurt" and "Failure cases and the synthetic-query bias", not reshaped):

```
{
  meta:         { manifest, runs: {name → settings.json}, input_hashes, built_at },
  metrics:      [ metrics.json rows + bootstrap CI on R@5/MRR, tagged by run ],
  significance: [ {a, b, strategy, metric, diff, ci_lo, ci_hi, p_raw, p_holm} ],
  failures:     { counts per strategy, overlap split rows, rerank_hurt breakdown },
  per_query:    [ {config, strategy, query_id, rank, stage ms…, top_recipe_ids} ],
  queries:      { query_id → {text, recipe_id, word_overlap, hand_rewritten} },
  recipes:      { recipe_id → title },
  cases:        { query_ids: [...], recipe_text: { recipe_id → {description, ingredients} } }
}
```

Amended by "Dataset section stats": run folders also hold `corpus.json` (written by `evaluate.py`), and the bundle gains a `corpus` block plus the query prompt text.

Build items for the spec: the bundle script, the manifest, the freshness test, the `/report` route in `App.tsx` and `api/main.py`.

New ticket: [Page layout and charts](14-page-layout-and-charts.md).
