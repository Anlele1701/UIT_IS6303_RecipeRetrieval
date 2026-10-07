# Architecture

Terms (Recipe, Chunk, Chunking strategy, Fusion baseline) are defined in [CONTEXT.md](../CONTEXT.md). Decisions are in [adr/](adr/).

The repo has four parts that share one database:

1. **Build**: load the dataset and turn Recipes into Chunks (offline, run once per strategy)
2. **Serve**: the FastAPI app answers Sparse, Dense and Hybrid searches
3. **Evaluate**: score the configs on a fixed Query set and save each run to disk
4. **Report**: turn saved runs into one JSON file the Report page reads

## The whole system

```mermaid
flowchart LR
    subgraph ext[External]
        HF[(Shengtao/recipe<br/>data/recipe.csv)]
        OL[Ollama<br/>nomic-embed-text<br/>qwen2.5:7b]
        RR[mxbai-rerank-base-v1<br/>local, sentence-transformers]
    end

    subgraph db[ParadeDB in Docker, port 5434]
        SRC[(Source tables<br/>recipe, category, author,<br/>ingredient, nutrition)]
        REG[(chunking_strategy)]
        CH[(chunk<br/>one partition per strategy<br/>BM25 + vector index each)]
    end

    subgraph build[1. Build: scripts/ingest.py]
        LOAD[load]
        CHUNK[chunk &lt;name&gt;]
    end

    subgraph serve[2. Serve: api/]
        API[FastAPI :8000<br/>/search/sparse<br/>/search/dense<br/>/search/hybrid]
    end

    subgraph eval[3. Evaluate: scripts/]
        MQ[make_queries.py]
        EV[evaluate.py]
        POST[rescore / failures /<br/>significance / runcheck]
        RUNS[(eval/runs/&lt;ts&gt;/<br/>eval/pooled/&lt;ts&gt;/)]
    end

    subgraph report[4. Report]
        RB[report_bundle.py]
        JSON[(ui/public/report.json)]
        UI[React + Vite UI<br/>search page, /report]
    end

    HF --> LOAD --> SRC
    SRC --> CHUNK
    OL -- embed chunks --> CHUNK
    CHUNK --> CH
    CHUNK -- set loaded_at --> REG

    UI -- search --> API
    API --> CH
    API -- check loaded --> REG
    OL -- embed query --> API
    RR --> API

    SRC --> MQ
    OL -- write queries --> MQ
    MQ --> Q[(eval/queries.jsonl)]
    Q --> EV
    EV -- same Hybrid code as the API --> API
    EV --> RUNS --> POST --> RUNS
    QR[(eval/qrels.csv)] --> POST

    RUNS --> RB --> JSON --> UI
```

Two things to notice:

- `evaluate.py` imports the API's retrieval code rather than calling it over HTTP. What gets scored is exactly what gets served.
- The Report page only needs `report.json`. No database, Ollama or API has to be running to read it.

## Build: from CSV to searchable Chunks

```mermaid
flowchart TB
    CSV[data/recipe.csv] -->|ingest.py load| SRC[(Source tables, 3NF)]
    SRC -->|ingest.py chunk semantic| S1[Summary chunk<br/>Ingredients chunk<br/>Step chunks]
    SRC -->|ingest.py chunk fixed| S2[same Summary + Ingredients<br/>Step chunks cut every 56 tokens]
    SRC -->|ingest.py chunk sentence| S3[same Summary + Ingredients<br/>Step chunks of 3 sentences]
    S1 & S2 & S3 -->|embed each with Ollama, 768 dims| P
    subgraph P[chunk table, partitioned by strategy]
        P1[chunk_semantic<br/>own index]
        P2[chunk_fixed<br/>own index]
        P3[chunk_sentence<br/>own index]
    end
    P -->|index built| L[chunking_strategy.loaded_at = now]
```

- Summary and Ingredients chunks are identical under every strategy. Only where Step chunks start and end changes.
- Filter columns (category, minutes, rating, calories...) are copied onto each Chunk so the index can filter during the search ([ADR 0001](adr/0001-denormalize-filters-onto-chunk.md)).
- One partition per strategy means each has its own BM25 stats ([ADR 0002](adr/0002-partition-chunk-by-strategy.md)).
- A strategy can't be searched until `loaded_at` is set, so a half-built one never serves results.

## Data model

```mermaid
erDiagram
    category ||--o{ recipe : groups
    author ||--o{ recipe : wrote
    recipe ||--o| recipe_nutrition : has
    recipe ||--o{ recipe_ingredient : lists
    recipe ||--o{ chunk : "split into"
    chunking_strategy ||--o{ chunk : "partition key"

    recipe {
        int id PK
        text title
        text description
        text directions
        real rating
        int total_minutes
    }
    chunking_strategy {
        text name PK
        text method
        jsonb parameters
        timestamptz loaded_at "null = not searchable"
    }
    chunk {
        bigint id PK
        text strategy PK
        int recipe_id FK
        text kind "summary / ingredients / step"
        text content "title + chunk text"
        vector embedding "768 dims"
        text category "copied filter"
        int total_minutes "copied filter"
    }
```

The source tables are the truth. `chunk` is derived from them and is only rebuilt, never edited.

## Serve: one Hybrid search

```mermaid
sequenceDiagram
    autonumber
    participant U as UI / client
    participant A as FastAPI
    participant O as Ollama
    participant P as ParadeDB (one partition)
    participant R as Reranker (in process)

    U->>A: GET /search/hybrid?q=...&strategy=semantic&k=5
    A->>P: is 'semantic' loaded?
    A->>O: embed "search_query: " + q
    O-->>A: 768-dim vector
    A->>P: BM25 top 50 (filters inside the index)
    P-->>A: sparse hits
    A->>P: cosine top 50 (same index, same filters)
    P-->>A: dense hits
    Note over A: RRF: score = sum of 1/(60 + rank)<br/>keep the top 50
    A->>R: score (query, chunk content) pairs
    R-->>A: rerank scores
    Note over A: sort by rerank score, return top k
    A-->>U: Chunks with sparse_rank, dense_rank, rrf_score, rerank_score
```

- `/search/sparse` stops after step 5 and `/search/dense` after step 7.
- Dense runs on ParadeDB's own vector index, not pgvector HNSW, so one index serves BM25, vectors and filters ([ADR 0003](adr/0003-serve-dense-from-paradedb-index.md)).
- The reranker loads once at startup and runs one batch at a time behind a lock (MPS, CUDA or CPU).
- Settings live in `api/config.py`: 50 candidates per retriever, 50 sent to the reranker, RRF k = 60.

## Evaluate and Report

```mermaid
flowchart LR
    SRC[(Source tables)] -->|sample 300 Recipes<br/>by category, seed 603| MQ[make_queries.py<br/>qwen2.5:7b writes a query]
    MQ --> Q[(queries.jsonl)]
    Q --> EV[evaluate.py<br/>4 configs x 3 strategies]
    EV --> RUN[(eval/runs/&lt;ts&gt;/<br/>per_query.csv, metrics, table.md)]

    QR[(qrels.csv<br/>pooled answer key)] --> RS[rescore.py]
    RUN --> RS --> POOL[(eval/pooled/&lt;ts&gt;/)]
    POOL --> SIG[significance.py<br/>paired bootstrap]
    POOL --> FAIL[failures.py<br/>who wins where]
    RUN --> RC[runcheck.py<br/>repeats rank the same?]

    MAN[(eval/report.json<br/>manifest)] --> RB[report_bundle.py]
    POOL & SIG & FAIL & RC --> RB
    RB --> OUT[(ui/public/report.json)] --> PAGE[/report page/]
```

- Four configs: `sparse`, `dense`, `fusion` (RRF order before reranking, eval only) and `hybrid`.
- Metrics: Recall@5/10/20, MRR, nDCG@5/10 and latency per stage.
- Retrieval is deterministic, so a new answer key only needs `rescore.py`, not new searches ([ADR 0004](adr/0004-score-against-a-pooled-answer-key.md)).
- Timing repeats and Ablation runs (e.g. HNSW, `sql/ablation/`) must rank every query the same as the Report run. `runcheck.py` fails the bundle if they don't.
- The bundle stores a hash of every input. A test fails when the committed `report.json` is older than what it was built from.

## Where things live

| Path | What |
|---|---|
| `api/` | FastAPI app: `retrieval.py` (sparse, dense, RRF, rerank), `filters.py`, `strategies.py`, `embed.py`, `rerank.py` |
| `scripts/` | Build (`ingest.py`), queries, evaluation and report tooling |
| `sql/` | `schema.sql`, `indexes.sql`, migrations, HNSW ablation |
| `eval/` | Query set, answer key, manifest, saved runs |
| `ui/` | React 19 + Vite + Tailwind: search page and Report page |
| `docs/adr/` | Design decisions |
| `tests/` | pytest, including the stale-bundle check |
