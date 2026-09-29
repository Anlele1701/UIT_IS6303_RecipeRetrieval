# Spec: Evaluation

**Status:** ready-for-agent

Measure how well each retrieval config finds the right Recipe, so the report can compare configs and Chunking strategies with numbers instead of screenshots.

Tracker: [tracker.md](tracker.md). Tickets: [issues/](issues/).

## Problem Statement

The system can search the recipe dataset with Sparse, Dense and Hybrid retrieval under three Chunking strategies, but nothing says which one works best. The dataset has no queries and no relevance judgments, so I can't score anything. The IS603 brief asks for Recall@k, MRR and nDCG@k across four configs, a failure analysis and a latency vs accuracy discussion. Today I can only eyeball results in the UI.

## Solution

- Generate a fixed set of 300 test queries with a local LLM. Each query is written from one Recipe, and that Recipe is the correct answer (known-item search).
- One eval command runs every query through four configs under every loaded Chunking strategy:
  - Sparse
  - Dense
  - Hybrid RRF (no Reranking, eval-only baseline)
  - Hybrid (RRF + Reranking, as served by the API)
- It prints a markdown table of Recall@5/10/20, MRR, nDCG@5/10 and latency, and writes the same numbers plus per-query ranks to JSON and CSV.
- A failure analyzer reads a run's per-query ranks and lists the queries where one config found the Recipe and another didn't, and where Reranking made the rank worse.
- A README explains how to reproduce all of it from a fresh clone.

## User Stories

1. As a student, I want a fixed set of test queries checked into the repo, so that every eval run scores the same questions.
2. As a student, I want each query to name the one Recipe it was written from, so that I have ground truth without judging results by hand.
3. As a student, I want queries sampled across categories with a fixed seed, so that the set isn't dominated by one kind of dish and can be regenerated identically.
4. As a student, I want queries to read like something a person would type, not a copy of the title, so that Sparse retrieval doesn't win just by matching words.
5. As a student, I want each query's word overlap with its Recipe recorded, so that I can show in the report how much the synthetic queries favour Sparse.
6. As a student, I want query generation to run on a local Ollama model, so that it costs nothing and needs no API key.
7. As a student, I want query generation to skip Recipes it already has a query for, so that a crash halfway doesn't mean starting over.
8. As a student, I want bad LLM output (empty, too long, just the title) rejected and retried, so that the query set is clean.
9. As a student, I want one command that evaluates all four configs, so that I don't stitch runs together by hand.
10. As a student, I want the eval to run under every loaded Chunking strategy by default, so that one run compares strategies too.
11. As a student, I want to limit a run to some configs or strategies, so that I can iterate quickly on one comparison.
12. As a student, I want metrics computed per Recipe, not per Chunk, so that a Recipe appearing three times in the top 5 counts once.
13. As a student, I want Recall@5, @10 and @20, so that I can see how deep the right Recipe usually sits.
14. As a student, I want MRR, so that I can see how high the right Recipe ranks on average.
15. As a student, I want nDCG@5 and @10, so that the report has the metrics the brief asks for.
16. As a student, I want latency per config (median and p95), so that I can discuss the accuracy vs speed trade-off.
17. As a student, I want latency split into stages (query embedding, Sparse, Dense, Reranking), so that I can say where the time goes.
18. As a student, I want a markdown table printed at the end, so that I can paste it straight into the report.
19. As a student, I want JSON and CSV files for every run, so that I can make charts and keep results over time.
20. As a student, I want per-query ranks saved for every config, so that failure analysis doesn't need to re-run searches.
21. As a student, I want each run's files in their own folder with a timestamp and the settings used, so that I can tell runs apart later.
22. As a student, I want Hybrid in the eval to use the same candidate and rerank settings as the API, so that the numbers describe what users actually get.
23. As a student, I want Hybrid RRF without Reranking as a baseline, so that I can show what Reranking adds.
24. As a student, I want the domain glossary to say RRF-only is an eval baseline, so that nobody mistakes it for a retrieval method we serve.
25. As a student, I want a list of queries where Sparse found the Recipe in the top 10 and Dense didn't, and the reverse, so that I can write case studies about each method's weak spots.
26. As a student, I want a list of queries where Reranking pushed the Recipe down compared with RRF, so that I can discuss when Reranking hurts.
27. As a student, I want those lists to include the query text, the Recipe title and the ranks, so that I can read a case without opening the DB.
28. As a student, I want failure counts per Chunking strategy, so that I can see whether a strategy changes which method fails.
29. As a student, I want a README with setup, ingest, query generation and eval steps, so that a grader can reproduce my numbers.
30. As a student, I want the Ollama models the project needs listed in one place, so that a fresh clone doesn't fail on a missing model.
31. As a student, I want metric code tested against hand-worked examples, so that I trust the numbers in my report.
32. As a student, I want the eval command tested end to end on the throwaway test DB, so that a refactor doesn't silently break it.

## Implementation Decisions

- **Ground truth is per Recipe** (known-item). One query, one relevant Recipe, binary relevance. This follows the chunking map's guardrail: chunk ids differ across Chunking strategies, Recipe ids don't.
- **Query set:** 300 Recipes, sampled stratified by category with a fixed seed. One query per Recipe. Stored as a JSONL file in the repo (not under the gitignored data folder), one line per query: query id, text, Recipe id, Recipe title, word overlap, model name.
- **Query generator:**
  - A local Ollama chat model (default `qwen2.5:7b`, overridable by env var).
  - It reads the Recipe's title, description and ingredients, and is told to write a short search a home cook would type, without repeating the title.
  - Output is validated: non-empty, at most ~12 words, not equal to the title. Retry up to 3 times, then skip the Recipe and log it.
  - The generator takes the LLM as a parameter (a callable from prompt to text) so tests can pass a fake.
  - Word overlap: share of the query's content words (stopwords dropped, stemmed) that appear in the Recipe's text. Measured, not filtered on.
- **Four configs**, all built from the existing retrieval functions. The eval doesn't go through HTTP.
  - Sparse and Dense: pull the top 100 Chunks, dedupe to Recipes, keep the top 20.
  - Hybrid RRF: Sparse and Dense each pull the API's Hybrid candidate count, fused with the existing RRF, then deduped.
  - Hybrid: the same as the API (RRF, then Reranking of the top candidates), then deduped. It uses the existing Reranker.
  - If a Hybrid config returns fewer than 20 unique Recipes, the missing positions count as misses. The report should mention this.
- **Chunk → Recipe dedupe:** walk the ranked Chunks and keep each Recipe the first time it appears. A Recipe's rank is its position in that deduped list, starting at 1.
- **Metrics** are hand-written, not `ranx`. With a single relevant Recipe they are short formulas:
  - Recall@k is 1 if the rank is ≤ k, else 0.
  - The reciprocal rank is 1/rank, or 0 if the Recipe wasn't found in the top 20.
  - nDCG@k is 1/log2(rank+1) if the rank is ≤ k, else 0.
  - Each is averaged over queries. Hand-written keeps the dependency list small and every number explainable.
- **The metrics module is pure:** a mapping from query to the relevant Recipe, and a mapping from (config, strategy, query) to a ranked list of Recipe ids, go in. A metrics table comes out. It doesn't touch the DB.
- **Latency** is measured in process with a monotonic clock, per query, per stage: query embedding, Sparse, Dense, RRF, Reranking. Each config reports p50 and p95 of its total. The reranker model loads once before timing starts, and one warm-up query isn't counted.
- **Run output:** a folder per run, named by timestamp. It holds:
  - the settings (configs, strategies, candidate counts, models, query-set file hash)
  - the metrics as JSON and CSV
  - the per-query ranks and latencies as CSV
  - the markdown table
  - Run folders are gitignored except those I choose to keep for the report.
- **Eval command options:** config and strategy selection, query-set path, and a query limit for quick runs. By default it runs every loaded Chunking strategy, read from the registry the same way the API lists them.
- **Failure analyzer:** a separate command that reads a run folder. It doesn't search again.
  - "Sparse win" means Sparse rank ≤ 10 and Dense rank > 10. "Dense win" is the reverse.
  - "Rerank hurt" means the Hybrid rank is worse than the Hybrid RRF rank.
  - Output: counts per strategy, plus a markdown list per bucket with the query, Recipe title and ranks. Case studies take the first N of each bucket by query id, so they're stable.
- **Glossary:** `CONTEXT.md` gains a term for the RRF-only baseline (e.g. **Fusion baseline**: Hybrid retrieval without Reranking, used only in evaluation) and terms for **Query set** and **Evaluation run**. The rule "Reranking is always part of Hybrid retrieval" stays true for served search.
- **No API or UI changes.**

## Testing Decisions

- Good tests check behaviour through the seam, not internals. Pass inputs, check outputs. Don't assert on private helpers or SQL text unless the SQL text is the behaviour (as in the existing tie-break test).
- **Seam 1, metrics (pure, no DB):** hand-made runs with known ranks.
  - A rank of 1, a rank of 7, and a missing Recipe give the hand-worked Recall/MRR/nDCG values.
  - A duplicated Recipe in the Chunk list is counted once, at its first rank.
  - Averages cover every query, and a query with no results counts as a miss.
- **Seam 2, the eval command end to end** on the throwaway `recipe_test` DB, using the existing conftest fixture. It loads a few Recipes and Chunks with fixed embeddings, passes a fake embedder and a fake reranker scorer, runs a two-query set, and checks that the run folder has the expected files and that the known-item query ranks its Recipe first.
- **Query generator:** a fake LLM returns scripted outputs. Check that the title is rejected and retried, a Recipe is skipped after 3 bad outputs, finished Recipes are skipped on re-run, and the same seed gives the same sample.
- **Failure analyzer:** built from a hand-written per-query ranks file. Check the bucket membership and counts.
- **Prior art:**
  - The pure-function tests in the retrieval tests (RRF and rerank with a fake scorer).
  - The ingest tests that build `recipe_test` from the schema and skip when the container is down.

## Out of Scope

- API or UI changes, including a "rerank off" switch on Hybrid search.
- New embedding or reranker models, and any training or fine-tuning.
- Human relevance judgments or graded relevance.
- Filters in evaluation. Every query runs unfiltered.
- Image or multimodal retrieval.
- Tuning RRF k, candidate counts or chunk settings based on the results. That's follow-up work once numbers exist.
- Writing the report itself. This spec produces the numbers and case lists it's written from.

## Further Notes

- Known bias to state in the report: queries written from one Recipe's own text tend to share its words, which helps Sparse. The recorded word overlap lets the report show this, for example by splitting metrics into low- and high-overlap queries.
- Known-item ground truth counts other good matches as misses (a query for "garlic butter shrimp" may fit several Recipes). Absolute numbers are pessimistic, so the comparison between configs is what matters.
- The generation model has to be pulled into Ollama first. Expect roughly 300 × a few seconds on a laptop.
- Reranking cost dominates eval time: 300 queries × 3 strategies × up to 50 pairs each.
