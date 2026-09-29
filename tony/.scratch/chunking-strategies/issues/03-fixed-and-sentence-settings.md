# Settings for fixed-size and sentence-based

Type: grilling
Status: resolved
Blocked by: 02
Parent: ../map.md

## Question

What exact settings do the fixed-size and sentence-based strategies use (size, unit chars/tokens, overlap, word/sentence boundary handling, strategy names)? Should they be tuned so their average Step chunk size matches semantic-v1, so chunk size isn't a hidden second variable?

## Answer

Rule: fixed-size and sentence-based are tuned to match semantic's chunk count and mean size, so the only thing that differs between strategies is where the cuts fall. Chunk size alone moves both BM25 (more terms in longer chunks) and dense scores (a longer chunk's vector averages more topics), so an unmatched size would hide the effect being compared.

Shared by all three:

- Input: `split_sentences(normalize_fractions(directions))`, joined with single spaces.
- The title prefix is added after cutting and not counted in any size limit (same as semantic today).
- No overlap.

`fixed`:

- Windows of 56 tokens, counted with nomic-embed-text's tokenizer (bert-base-uncased WordPiece).
- Cuts only between words, never mid-word. Ignores sentence ends.
- Why 56: it gives the same chunk count and mean as semantic (100,536 vs 101,000 chunks; 47.0 vs 46.7 tokens). 48 undershoots, 64 overshoots.
- Why 0% overlap: 10%/20% are copied defaults, not measured. Overlap adds 5–12% more chunks and repeated text only to this strategy, a second difference besides cut placement.

`sentence`:

- 3 consecutive sentences per chunk. A Recipe's leftover 1–2 sentences stay as their own chunk.
- No size cap (p99 88 tokens, max 152 tokens / 609 chars); a cap would make it part fixed-size.
- Why 3: semantic's median chunk is 3 sentences. Gives 110,314 chunks, mean 42.8 tokens. 4 would be about 57 tokens.

`semantic`: unchanged. Its `MIN_CHARS = 80` folds tiny pieces like "Serve." into their most similar neighbour, and `MAX_CHARS = 400` caps size. Neither reason was written down before this.

Names: `semantic`, `fixed`, `sentence`, no version suffix; a retune takes a new name. The live `semantic-v1` rows are renamed during the partition migration.

Measured on the local DB, 2026-09-27, by simulating each setting over all 32,719 Recipes' directions.
