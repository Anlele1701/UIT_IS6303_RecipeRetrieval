# Getting started

There are two ways in. Pick the one you need.

- **See the results:** open one file, no setup. Takes a minute.
- **Run the search app:** set up the database and models, then search recipes yourself. Takes about 4 hours the first time, mostly waiting while the Chunks are embedded.

Terms like Chunk, Chunking strategy and Hybrid are defined in [CONTEXT.md](CONTEXT.md). The full reference, including every script and option, is the [README](README.md).

## See the results

Open `report.html` in any browser. Double-clicking it works.

It holds every evaluation result: the main table, the charts, the significance tests and the ablations. Nothing else needs to be installed or running. Use the buttons at the top to switch the charts between the `fixed`, `semantic` and `sentence` Chunking strategies.

For the longer write-up with every section, run the Report page instead (needs Node):

```sh
cd ui && npm install && npm run dev
```

Then open http://localhost:5173/report.

## Run the search app

### 1. Install the tools

| Tool | Why | Check it works |
|---|---|---|
| [Docker](https://docs.docker.com/get-docker/) | runs the ParadeDB database | `docker --version` |
| [uv](https://docs.astral.sh/uv/) | installs Python 3.11+ and every Python package | `uv --version` |
| [Ollama](https://ollama.com) | runs the embedding model on your machine | `ollama --version` |
| [Node](https://nodejs.org) 20.19+ or 22.12+ | builds the web page | `node --version` |

Then download the embedding model:

```sh
ollama pull nomic-embed-text
```

### 2. Start the database and install packages

From the repo folder:

```sh
docker compose up -d --wait
uv sync
```

ParadeDB starts on port 5434 and creates the tables on its first start.

### 3. Load the recipes

```sh
uv run scripts/ingest.py load
```

This downloads the dataset (61 MB) and loads 32,719 Recipes. It takes under a minute.

### 4. Build at least one Chunking strategy

```sh
uv run scripts/ingest.py chunk semantic
```

This cuts every Recipe into Chunks, embeds them and builds the search index. It takes about 70 minutes on an M-series MacBook. Leave it running. If it stops partway, run the same command again and it starts over cleanly.

One strategy is enough to search. To compare all three, also run `chunk fixed` (about 60 minutes) and `chunk sentence` (about 85 minutes).

### 5. Start the app

```sh
cd ui && npm install && npm run build && cd ..
uv run uvicorn api.main:app
```

Open http://localhost:8000. Type a query, for example `creamy black bean and tomato stew`. The page shows Sparse, Hybrid and Dense results side by side. The first search takes a few seconds longer, because the reranker model (about 0.7 GB) downloads the first time it runs.

To check that everything is connected, open http://localhost:8000/health. It reports the database, Ollama and the reranker.

## Common problems

| What you see | What to do |
|---|---|
| `'semantic' is not loaded yet` | Step 4 hasn't finished. Wait until it prints `semantic loaded`. |
| The embedding service is not responding | Start Ollama, then search again. |
| Port 5434 is already in use | Another Postgres is using it. Stop it, or set `DATABASE_URL` to another port. |
| `uv run pytest` fails with a path error | The folder name has a space in it. Use `uv run python -m pytest` instead. |
| `drop strategies first` when loading | The recipes are already loaded. Skip step 3. |

## Run the evaluation yourself

You don't need this to see the results. It's only for rerunning the numbers.

```sh
RERANK_MODEL=BAAI/bge-reranker-base uv run scripts/evaluate.py
```

This runs 298 test queries through all four configurations on every loaded strategy, in about 13 minutes. The report's numbers were measured with `bge-reranker-base`, so set `RERANK_MODEL` as above to reproduce them. Keep the machine idle while it runs, since other work on the laptop changes the timing.

After a new run, rebuild the results file:

```sh
uv run python scripts/report_bundle.py
uv run python scripts/static_report.py
```
