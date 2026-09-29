# Measure semantic-v1's chunk sizes

Type: task
Status: resolved
Blocked by:
Parent: ../map.md

## Question

From the live DB (`chunk WHERE chunker = 'semantic-v1' AND kind = 'step'`), record: chars per Step chunk (mean, median, p10/p90), sentences per Step chunk, Step chunks per Recipe, and total chunk count. These are the facts the fixed-size and sentence-based settings will be tuned against.

## Answer

Measured 2026-09-27 on the local DB, semantic-v1 only. Sizes are the Step text without the `title\n` prefix. Sentences are counted with the ingest's own `split_sentences`.

Counts:

- 166,438 chunks total: 32,719 summary, 32,719 ingredients, 101,000 step.
- Every Recipe has at least 1 Step chunk.

Per Step chunk:

| | mean | p10 | median | p90 | p99 | max |
|---|---|---|---|---|---|---|
| chars | 196 | 56 | 185 | 355 | 396 | 400 |
| words | 34.6 | 10 | 33 | 62 | 72 | 83 |
| sentences | 3.0 | 1 | 3 | 5 | 7 | 13 |

Per Recipe: Step chunks mean 3.1, median 3, p90 6, max 25.

Source text the other strategies will cut (directions, fractions normalized):

- chars per Recipe: mean 608, median 542, p90 1,048, max 4,263.
- sentences per Recipe: mean 9.1, median 8, p90 16.
- chars per sentence: mean 66, median 59, p90 111, max 393. No sentence exceeds 400 chars, so a 400-char cap never has to cut mid-sentence.

Quirk to account for in the settings ticket:

- 15% of Step chunks (15,020) are under `MIN_CHARS` = 80, and 22.6% are a single sentence.
- 14,920 of those 15,020 are in Recipes whose directions are over 400 chars. The oversized-piece split runs after the merge step and never re-merges, so splitting leaves short fragments (e.g. "Spread over the cake.").
- So semantic-v1's sizes have a heavy short tail. Matching its mean (196 chars) alone won't make chunk size a non-variable; compare the whole distribution.
- The data is kept as-is (settled on the map), so this is a fact to tune against, not a fix.

Script: throwaway, read-only; re-run by querying `chunk WHERE chunker = 'semantic-v1' AND kind = 'step'` and stripping everything up to the first newline.
