# Recipe Retrieval

Sparse (BM25), Dense (embedding) and Hybrid (RRF + Reranking) retrieval over the [Shengtao/recipe](https://huggingface.co/datasets/Shengtao/recipe) dataset, stored in ParadeDB under three Chunking strategies (`fixed`, `sentence`, `semantic`). An evaluation scores four configs on a fixed Query set with Recall@k, MRR, nDCG@k and latency. Text only: images in the dataset aren't used.

The write-up is the Report page at `/report` (see [Report](#report)). The headline numbers are in [Results](#results).

Terms like Chunk, Chunking strategy and Fusion baseline are defined in [CONTEXT.md](CONTEXT.md). Design decisions are in [docs/adr/](docs/adr/). Dense search uses ParadeDB's own vector index rather than pgvector HNSW, so one index per partition serves BM25, vectors and Filters; [ADR 0003](docs/adr/0003-serve-dense-from-paradedb-index.md) explains why, and the report measures HNSW as an ablation.

## Results

Report run `eval/runs/20260928-122309` on commit `466b46a`: 298 queries, four configs, three Chunking strategies, scored against the pooled answer key in `eval/qrels.csv`. The full table with R@5/10/20, MRR, nDCG@5/10 and latency is [eval/pooled/20260928-122309/table.md](eval/pooled/20260928-122309/table.md). The same run scored with one right Recipe per query is [eval/runs/20260928-122309/table.md](eval/runs/20260928-122309/table.md); [ADR 0004](docs/adr/0004-score-against-a-pooled-answer-key.md) explains the change. Latency in the report comes from three Timing repeats rather than this single run.

## Report

The Report page reads one committed file, `ui/public/report.json`. It needs no database, Ollama or API:

```sh
cd ui && npm install && npm run dev     # open http://localhost:5173/report
```

Or build the UI and run the API (step 5 below), then open http://localhost:8000/report.

To rebuild the bundle after changing a run or a label file (needs `data/recipe.csv`, which step 2 downloads):

```sh
uv run python scripts/report_bundle.py
```

It reads only what the manifest `eval/report.json` names and fails if the check run, a Timing repeat or an Ablation run ranks a query differently from the Report run. A test fails when the committed bundle is older than its inputs.

## Demo

For a live demo, run the search page (step 5) and pick the `semantic` strategy. Three queries show the three stories from Section 6.4 of the report:

| Query | What to point out |
|---|---|
| `creamy black bean and tomato stew` (q155) | Sparse misses Black Bean and Tomato Soup because the query says stew; Dense and Hybrid find it. |
| `yellow split pea soup with curry powder` (q012) | Sparse ranks Vegan Split Pea Soup II first on the exact words; Dense loses it among other split pea soups. |
| `greek yogurt with fruit and nuts frozen dessert` (q076) | Neither list alone ranks Yogurt Bark well, and Reranking puts it first. |

## Prerequisites

- Docker (runs ParadeDB on port 5434)
- [uv](https://docs.astral.sh/uv/) (Python 3.11+ and all Python dependencies)
- Node 20.19+ or 22.12+ with npm (only for the UI)
- [Ollama](https://ollama.com) running on `http://localhost:11434`

Ollama models:

| Model | Used by | Needed for |
|---|---|---|
| `nomic-embed-text` | ingest, API, eval | embedding Chunks and queries |
| `qwen2.5:7b` | `make_queries.py` | only if you regenerate the Query set |

```sh
ollama pull nomic-embed-text
ollama pull qwen2.5:7b   # optional, see step 4
```

Two Hugging Face models download on first use, no account needed: `bert-base-uncased` (tokenizer for the `fixed` strategy) and `BAAI/bge-reranker-base` (~1 GB, the reranker used by Hybrid).

Every setting has a default that matches `docker-compose.yml`. Override with env vars if yours differ: `DATABASE_URL`, `OLLAMA_URL`, `EMBED_MODEL`, `RERANK_MODEL`, `HYBRID_CANDIDATES`, `RERANK_TOP` (all in `api/config.py`) and `QUERY_MODEL` (in `scripts/make_queries.py`).

## 1. Start the database

```sh
docker compose up -d --wait
uv sync
```

A fresh volume builds the schema from `sql/schema.sql` on first start. `uv sync` creates `.venv` with the API and dev dependencies.

## 2. Load the Recipes

```sh
uv run scripts/ingest.py load
```

Downloads `recipe.csv` (~61 MB) into `data/` if it isn't there, then loads 32,719 Recipes with their ingredients and nutrition. Takes under a minute. It refuses to run once any Chunking strategy exists, because a reload renumbers Recipes.

## 3. Build the Chunking strategies

```sh
uv run scripts/ingest.py chunk semantic
uv run scripts/ingest.py chunk fixed
uv run scripts/ingest.py chunk sentence
```

Each one chunks and embeds every Recipe through Ollama, builds the search index and marks the strategy loaded. Rough timings on an M-series MacBook: `semantic` ~70 min, `fixed` ~60 min, `sentence` ~85 min. Most of that is embedding.

- Transient Ollama errors are retried. If a run crashes, run the same command again: it discards the unfinished build and starts over.
- A strategy isn't searchable until its run prints `<name> loaded`.
- To rebuild one: `uv run scripts/ingest.py drop <name> --yes`, then `chunk <name>` again.

You can evaluate with fewer than three. The eval uses whatever is loaded.

## 4. Query set (already committed)

`eval/queries.jsonl` is in the repo: 298 queries, one per sampled Recipe. Use it as is to get the same numbers. Skip this step.

How it was made: `qwen2.5:7b` wrote one query per Recipe (2 of 300 sampled Recipes were skipped after 3 bad tries). Then all 298 were read against their Recipes and 57 were rewritten by hand: wrong facts, broken output, too vague, or copying the title.

To regenerate it anyway (a few seconds per Recipe on a laptop):

```sh
uv run scripts/make_queries.py --out eval/my-queries.jsonl
```

A regenerated set won't match the committed one: it lacks the hand rewrites, and LLM output can differ across machines and Ollama versions. The sample of Recipes is the same, since it uses a fixed seed (603). A rerun skips Recipes already in the output file, so a crash resumes. Pass the new file to the eval with `--queries eval/my-queries.jsonl`.

## 5. Run the API and UI

```sh
cd ui && npm install && npm run build && cd ..
uv run uvicorn api.main:app
```

Open http://localhost:8000. The page runs one query through Sparse, Hybrid and Dense side by side, with a strategy picker and filters in Settings. API docs are at http://localhost:8000/docs, and `/health` reports the DB, Ollama and reranker status.

For UI development with hot reload, see [ui/README.md](ui/README.md).

The API isn't needed for the eval, which calls the retrieval code directly.

## 6. Run the evaluation

```sh
uv run scripts/evaluate.py
```

Runs every query through four configs under every loaded Chunking strategy:

- `sparse`: Sparse retrieval only (BM25)
- `dense`: Dense retrieval only
- `fusion`: the Fusion baseline, Sparse and Dense fused with RRF, no Reranking (eval only)
- `hybrid`: RRF then Reranking, the same code and settings the API serves

A full run (298 queries × 4 configs × 3 strategies) took about 11 minutes. Reranking is most of it.

Each Evaluation run scores against the answer key `eval/qrels.csv`: a query counts at the rank of its first right Recipe. `--qrels none` scores only the Recipe each query was written from. It prints a markdown table and writes `eval/runs/<timestamp>/` with `settings.json`, `metrics.json`, `metrics.csv`, `per_query.csv` (ranks, latencies and the winning Chunk kind per query), `table.md`, `recipes.csv` (titles of every ranked Recipe and every query's known Recipe) and `corpus.json` (what was searched).

An Ablation run changes one setting against its default in the same run. The arms are named in `ARMS` in `scripts/evaluate.py`:

```sh
uv run scripts/evaluate.py --arm reranker-mxbai-base
```

The `hnsw-dense` arm needs its indexes first, and they are dropped after:

```sh
docker exec -i recipe-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 < sql/ablation/hnsw.sql
uv run scripts/evaluate.py --arm hnsw-dense
uv run scripts/runcheck.py eval/pooled/20260928-122309 eval/runs/<the new run>
docker exec -i recipe-paradedb psql -U recipe -d recipe < sql/ablation/hnsw-drop.sql
```

For a quick check:

```sh
uv run scripts/evaluate.py --configs sparse dense --strategies fixed --limit 20
```

## 7. Run the failure analyzer

```sh
uv run scripts/failures.py eval/runs/<timestamp>
```

Reads the run folder, doesn't search again. It prints and writes `failures.md` with:

- counts per strategy of `sparse_win` (Sparse top 10, Dense not), `dense_win` (the reverse), `rerank_hurt` (Hybrid ranks the Recipe worse than the Fusion baseline) and `rerank_help` (better), plus Reranking's net effect on the top 5
- the first N cases of each bucket with query, Recipe title and ranks (`--cases N`, default 10)
- each config's metrics split into high and low word overlap between query and Recipe

It also writes `failures.json`, which the report bundle reads.

## 8. Significance and the rank check

```sh
uv run scripts/significance.py eval/runs/<timestamp>   # paired bootstrap, writes significance.json
uv run scripts/runcheck.py eval/pooled/20260928-122309 eval/runs/<timestamp>   # ranks must match the Report run
```

The runs the report names were made before the answer key existed. `rescore.py` scores a saved run against it without searching again and writes `eval/pooled/<timestamp>/`, significance and failures included:

```sh
uv run python scripts/rescore.py eval/runs/<timestamp>
```

A new config or arm can put Recipes in its top 5 that were never judged; judge them into `eval/qrels.csv` before comparing (ADR 0004).

`significance.py` stores raw p only; the report bundle applies Holm across every run the manifest names.

Run folders are gitignored. Keep one for the report with `git add -f eval/runs/<timestamp>`.

## Tests

```sh
uv run python -m pytest
```

(`uv run pytest` fails when the project path contains a space, because the venv's script shebang breaks.)

Tests that need the database build a throwaway `recipe_test` DB inside the `recipe-paradedb` container and are skipped when it isn't running. They use fake embedders and scorers, so Ollama isn't needed.

## Layout

```
api/            FastAPI app: retrieval, filters, reranking, config
ui/             React + Tailwind search page and the Report page (/report), built into api/static
scripts/        ingest, search, make_queries, evaluate, failures, metrics, significance, runcheck, report_bundle
sql/            schema, BM25 + vector indexes, one-off migrations; ablation/ holds the HNSW DDL
eval/           the Query set, label files, the report manifest report.json; runs/ holds Evaluation runs (gitignored, report runs kept with -f)
docs/adr/       architecture decisions
tests/          pytest
```
