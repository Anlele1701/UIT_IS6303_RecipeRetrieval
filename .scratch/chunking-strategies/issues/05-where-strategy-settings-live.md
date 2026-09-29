# Where a strategy's name and settings live

Type: grilling
Status: resolved
Assignee: tonytrinh
Blocked by:
Parent: ../map.md

## Question

Is a Chunking strategy recorded in the DB (e.g. a `chunking_strategy` table with name, method, settings, created time, and `chunk.strategy` referencing it) so the API and UI can list what's loaded and results can be traced back to exact settings? Or does it stay a name in code only?

## Answer

Recorded in the DB. Code holds the chunking logic; the table records the parameters that actually produced a strategy's rows.

`chunking_strategy` table:

- `name text PRIMARY KEY`: `semantic`, `fixed`, `sentence`.
- `method text`: fixed / sentence / semantic. Kept apart from `name` so a retune like `fixed-64` is still `method = fixed`.
- `parameters jsonb`: e.g. `{"tokens": 56, "tokenizer": "bert-base-uncased"}`, `{"sentences": 3}`, `{"min_chars": 80, "max_chars": 400, "break_percentile": 25}`. Validated in code only; one column per number would be mostly null.
- `created_at timestamptz`, `loaded_at timestamptz NULL`.
- `chunk.strategy` has a foreign key to `chunking_strategy(name)`.

Lifecycle:

- Registering a strategy (insert the row and create its partition) is one transaction, done by ingest. A name without a partition, or the reverse, can't exist.
- Ingest sets `loaded_at` once every Recipe has chunks under that strategy.
- Crash policy is rollback-and-rerun, not resume: a rerun of a strategy with `loaded_at` NULL drops its partition and row and starts fresh from the current code. A loaded strategy is never touched without an explicit drop. This also means parameters can't drift mid-run, so no code-vs-row mismatch check is needed.
- The API and UI picker list only strategies with `loaded_at` set, so a half-built strategy is never searchable or evaluated.

Not part of a strategy: the embedding model. There is one model system-wide (`nomic-embed-text`); changing it re-embeds every partition and is its own effort.

Why a table over names in code only: code constants can change without a rename, so only a row written at ingest time says what made the rows you have. The partition catalog alone can't tell a half-loaded strategy from a finished one. A config file would be a third copy to keep in sync.

Checked while resolving (2026-09-27): the live `semantic-v1` data is complete (32,719/32,719 Recipes, 1 Summary + 1 Ingredients each, 101,000 Step chunks, no position gaps, no null embeddings). An earlier ingest interruption left nothing half-written, since ingest commits 200 whole Recipes per transaction. No rechunk needed.
