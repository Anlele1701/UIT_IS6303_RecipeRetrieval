# API and UI contract for picking a strategy

Type: grilling
Status: resolved
Assignee: tonytrinh
Blocked by:
Parent: ../map.md

## Question

How does a search say which Chunking strategy to use, and how does the UI offer the choice? Covers: the query parameter name on `/search/{method}`, whether it's required or has a default (and which), the error for an unknown or not-yet-loaded name, a `/strategies` endpoint (or similar) reading `chunking_strategy WHERE loaded_at IS NOT NULL`, per-strategy chunk counts on `/health` replacing today's single `chunker`, and where the single-choice picker sits in the UI (Settings drawer or next to the search box). Today `CHUNKER` comes from `api/config.py:10` and is applied in `api/filters.py:43`.

## Answer

Resolved 2026-09-27.

API:

- **Parameter** `strategy` on `SearchParams`, so `/search/sparse`, `/search/dense` and `/search/hybrid` all take it. `extra="forbid"` turns a leftover `chunker=` into a clear error.
- **Required, no default.** The `CHUNKER` env var (`api/config.py:10`) is removed. Matches ADR-0002 ("the API always requires a strategy"); a silent default is how comparison results get mislabelled.
- **Validation** per request against `chunking_strategy` (tiny table, never stale; no startup cache, so a newly loaded strategy is searchable without a restart). 422 for both cases, with different messages: `strategy: 'fixed' is not loaded yet` and `strategy: 'foo' is unknown; loaded: semantic, sentence`.
- **`GET /strategies`** lists loaded strategies only (`loaded_at IS NOT NULL`): `[{name, method, parameters, loaded_at}]`, ordered by name. No counts, so it stays a cheap metadata read.
- **`/health`** replaces `chunker` and `chunks` with `chunks: {"semantic": 166438, ...}`, one count per loaded strategy. A loaded strategy with 0 chunks is a visible problem.
- **`SearchResponse`** gains `strategy` next to `method`, so any saved or screenshotted result says what produced it.

UI:

- A segmented control next to the search box, not in the Settings drawer: the strategy is the variable being compared, not a filter. Changing it re-runs the current query immediately (no Apply step).
- Options come from `/strategies`. Pre-select `semantic` if loaded, else the first; remember the last choice in `localStorage`. With no loaded strategy, search is disabled with a message saying so.
- Each column header shows the strategy name.

Other places still on `chunker` (found while resolving), all renamed in the same change:

- `scripts/search.py:17,30` imports `CHUNKER` from ingest and queries the DB directly. By the same rule as the API, it takes a required `--strategy`.
- `tests/test_retrieval.py:31` asserts the `chunker = %s` SQL.
- `ui/src/api.ts:29` (`Health.chunker`) and the Services section of `ui/src/components/SettingsDrawer.tsx:179` show the single Chunker and count; they switch to the per-strategy counts.
- `sql/queries.sql` examples filter on `chunker = 'semantic-v1'`.

