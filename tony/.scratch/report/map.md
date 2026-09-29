# IS603 report

Label: wayfinder:map

## Destination

A spec, ready to build, for a Report page in `ui/` that loads a committed Evaluation run's stored data (JSON/CSV) and presents the IS603 report, with every content and data decision locked: sections, the claim each one makes, the tables and charts behind it, the tests that back it, and the cases it shows.

Delivered in two parts so the runs don't wait on the UI: [Eval spec](eval-spec.md) (code changes and runs; written 2026-09-28, built) and the [page spec](page-spec.md) (written 2026-09-29). The destination is reached.

## Notes

- Domain: recipe retrieval over `Shengtao/recipe`, ParadeDB, FastAPI `api/`, Vite React `ui/`. Terms in `CONTEXT.md`, decisions in `docs/adr/`. Grilling tickets: call the Skill tool for "grilling" and "domain-modeling".
- Requirements come from `BRIEF.md`. It's a tutor prompt, not a rubric: no deadline, length or format rules. Phase 6 names the required report content: latency vs accuracy, logic placement, qualitative case studies, ablations.
- Reference: `~/School/IS603/UIT_IS6303_RecipeRetrieval/REPORT.md` and its `docs/08`–`11`. Different dataset, models, UI and query set, so only its structure and rigor carry over.
- Settled while charting:
  - English.
  - Follow the old report's 7 sections: problem and scope, dataset, evaluation setup, main results, ablation, error analysis, conclusion.
  - The page lives in `ui/` and reads stored evaluation data. It is not a hand-written page with hardcoded numbers.
  - Modality is text-only. The report says so (brief Phase 1).
  - Glossary terms only. The old report's "Hybrid (RRF)" is our Fusion baseline and its "Hybrid + Rerank" is our Hybrid.
  - The ablations include a cross-encoder model comparison. The served reranker stays `BAAI/bge-reranker-base` for this report; §7 recommends mxbai-rerank-base-v1 as a follow-up.
- Dense is ANN (ParadeDB probe 0.02) in every main run; the image is pinned by digest from the clean run on.
- Report run: `eval/runs/20260928-122309` (4 configs × 3 Chunking strategies, 298 queries, commit `466b46a`). Ablation runs are compared against it.
- Eval runtime budget: up to 8 h per run, so runtime doesn't limit arm choice.
- Planning only: no code changes on this map. Building and running the Eval spec is a separate build effort. Research findings go in `research/`, not on branches.

## Decisions so far

- [What the hand-in includes besides the page](issues/19-hand-in.md): live presentation plus GitHub repo; no PDF, print stylesheet, hosting or slides; demo on the search UI with q155 / q012 / q076 on semantic; README "Demo" and "Results" (links the Report run's `table.md`) are page-spec items.
- [What the conclusion recommends](issues/18-conclusion-recommendation.md): §7 in three tiers: Hybrid + mxbai-rerank-base-v1 (quality headline, MRR +10–12, ~1.25× latency), Hybrid + MiniLM-L6 (today's R@5 at ~¼ latency), Fusion baseline (latency critical); R@5 claims follow Holm; `rerank_top` stays 50; no Chunking strategy winner; doesn't wait for HNSW; 5 limits, 3 future-work lines.
- [Page layout and charts](issues/14-page-layout-and-charts.md): §4.3 aligned panels and drill-down list + detail; fixed value columns and axis ticks, labelled filter panel with plain chip names, best row per strategy highlighted in the table; plain full-sentence copy, prose numbers from the bundle. Amends "Latency vs accuracy framing": ~17×, not ~20×.
- [Compare Dense against pgvector HNSW](issues/17-dense-vs-pgvector-hnsw.md): HNSW is a 9th Ablation arm `hnsw-dense` (m 16 / ef_construction 64, ef_search 200, EXPLAIN-asserted), built from `sql/ablation/hnsw.sql` and dropped after runcheck; §5 three-way Dense table, §3 one line plus ADR 0003; Holm 81 → 90. Build is Eval spec step 5.
- [Pick the case studies and label the every-config misses](issues/16-pick-cases-and-label-misses.md): cases q155 / q012 / q048 / q076 / q066 on semantic (rerank_hurt picked as typical, not worst); misses 17 near-duplicate, 8 opaque title, 3 lexical trap, 1 other, so §6.5 says "17 of 29"; rewrites 25/7/12/6/7 replace the old unstored totals; labels become `eval/` files at build time.
- [How ablation runs and timing repeats are stored](issues/15-run-storage.md): one folder per arm (named `ARMS` in `evaluate.py`, `variant` column for arm vs default); 3 Timing repeats as full folders on the rotation commit, median p50/p95 with p50 min–max; bundle hard-fails unless repeat and arm-default ranks equal the Report run's; raw p per folder, Holm in the bundle; manifest `eval/report.json` holds paths only. Amends "Significance tests" and "Latency vs accuracy framing".
- [Dataset section stats](issues/13-dataset-section-stats.md): `evaluate.py` writes `corpus.json` into the run folder (backfilled for the report run); 2.1 counts, fields → Chunk kind, top 10 of 22 categories; 2.2 strategy × kind counts, parameters, Step length in chars; 2.3 prompt, rewrite reasons from a new `eval/query_edits.csv`, overlap before/after rewrites.
- [Failure cases and the synthetic-query bias](issues/11-failure-cases-and-query-bias.md): 5 cases (dense_win, sparse_win, rerank_hurt, rerank_help, every-config miss), shortlisted by "same bucket on all 3 strategies" then picked by hand, shown on semantic; §6.2 claims the Sparse−Dense sign flip (+8–13 high overlap, −5–10 low); §6.5 hand-labels the 29 every-config misses into 3 groups; `recipe_id` isn't a `recipe.csv` row, so `evaluate.py` writes `recipes.csv` and "Page data contract" is amended.
- [Explaining rerank_hurt](issues/10-explaining-rerank-hurt.md): mostly 1–2 rank shuffles, outweighed by bigger helps (net +20 to +27 queries into the top 5); net-effect table plus one case in §6; build items: `rerank_help` bucket and net-effect block in `failures.py`, Chunk kind of the winning hit in `per_query.csv` to test the one-Chunk cause.
- [Latency vs accuracy framing](issues/09-latency-vs-accuracy.md): 3 timing repeats (median, min–max range) and rotated config order as build items; Fusion baseline vs Hybrid totals headline, Hybrid-only stage breakdown; §4.3 claims ~20x latency for +7–9 pts R@5, recommendation left to §7; ablation latency as same-run ratio to default.
- [Page data contract](issues/08-page-data-contract.md): one committed JSON bundle in `ui/public/`, built by a Python script from a manifest-named Report run; page computes nothing, needs no DB/Ollama/API; titles and case text from `recipe.csv`; hash-checked by a pytest; route `/report`.
- [Clean Evaluation run on a committed tree](issues/01-clean-evaluation-run.md): report run is `20260928-122309` on `466b46a`; ranks identical to the old run; Hybrid latency moved +20% (Reranking), so latency needs repeats or a range.
- [What to do about approximate Dense search](issues/12-approximate-dense-search.md): keep probe 0.02 in main runs (ANN costs Dense 2–3.4 pts R@5 vs exact); add an exact-Dense ablation arm on Dense, Fusion baseline and Hybrid; pin the ParadeDB image by digest before the clean run.
- [Which ablations to run](issues/07-which-ablations.md): 7 arms on all 3 Chunking strategies: 3 cross-encoders vs bge-base (Hybrid), `rrf_k` 10/100 (Fusion baseline), `rerank_top` 20/100 (Hybrid); logic placement argued, not measured.
- [Significance tests](issues/06-significance-tests.md): paired bootstrap (10k, 95% CI) on R@5 and MRR over 15 fixed comparisons plus ablation arms, Holm-adjusted; `scripts/significance.py` writes `significance.json` per run; non-significant = "no detectable difference", with CI.
- [Is an eval-only Fusion baseline enough for the brief's Hybrid (RRF)?](issues/05-fusion-baseline-as-config-3.md): yes, not served; §1 maps brief names to glossary names once, with the eval-only note as a row note.
- [Report outline](issues/04-report-outline.md): 7 sections plus header and references; one provisional claim per subsection, R@5 headline; §4 split into configs / Chunking strategy / latency; bias noted in §2.4, measured in §6; caveats sit next to what they weaken.
- [Which cross-encoder models to compare](issues/03-cross-encoder-candidates.md): all drop-ins via `RERANK_MODEL`; shortlist MiniLM-L6 (fast, brief's pick), bge-reranker-v2-m3 (large), mxbai-rerank-base-v1 (same size, other training), gte-modernbert optional.
- [What vector index does ParadeDB build for our embeddings?](issues/02-paradedb-vector-index.md): ANN (ParadeDB's SPANN-style cluster index, not HNSW), probe 0.02, ~0.78 recall@50 on synthetic vectors; pg_search is real BM25, unlike `ts_rank_cd`.

## Not yet specified

Nothing. The page spec is written: [page-spec.md](page-spec.md) (2026-09-29).

## Out of scope

- Building the Report page. That's a separate build effort that follows the spec. (The human asked for it to be built right after, on 2026-09-29, outside this map.)
- Changing retrieval behaviour or the served configs. [Is an eval-only Fusion baseline enough for the brief's Hybrid (RRF)?](issues/05-fusion-baseline-as-config-3.md) chose not to serve the Fusion baseline.
- Switching the served reranker to mxbai-rerank-base-v1. [What the conclusion recommends](issues/18-conclusion-recommendation.md) recommends it; doing it changes the served configs, a follow-up after the report.
- Training or fine-tuning (brief constraint), multimodal retrieval, new embedding models.
