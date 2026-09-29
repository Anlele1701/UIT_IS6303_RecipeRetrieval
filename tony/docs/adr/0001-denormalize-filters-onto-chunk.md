---
status: accepted
---

# Copy filter attributes onto the chunk table

The recipe tables are the normalized source of truth (3NF). The `chunk` table is derived from them and copies 12 filter attributes (category, times, rating, servings, key nutrition). This knowingly violates 2NF, because each copied attribute depends only on `recipe_id`, which is part of chunk's natural key `(recipe_id, chunker, kind, position)`. We accept this because a ParadeDB index can only filter during the search on columns of the table it indexes. Filters on joined tables are applied after top-k ranking, which returns too few results and adds latency. The usual risk of denormalization, update anomalies, is avoided by one rule: `chunk` is never updated in place. It is only rebuilt from the recipe tables, in one load step, and the source data is loaded once and never changes.

## Considered Options

- **Join at query time:** fully normalized, but filters are applied after ranking, for both BM25 and vector search.
- **ParadeDB join pushdown (pg_search ≥ 0.25):** needs a ParadeDB index on every joined table with all join and filter columns indexed, and a `LIMIT`. If any condition is missing it quietly falls back to a plain join, and vector ordering is not documented as supported.

## Consequences

- Any change to a recipe must be followed by rebuilding that recipe's chunks. Editing `chunk` directly is never allowed.
- A consistency check (chunk's copied columns joined against recipe, expecting zero mismatches) is enough to show the copies have not drifted.
