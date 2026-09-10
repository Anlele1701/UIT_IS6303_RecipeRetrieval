# 11 — Error Analysis

The report should not rely on metrics alone — concrete examples must be analyzed. This document is a template to fill in once retrieval is implemented and run (TODO — no examples exist yet; do not fabricate them).

## Good cases

For each example:

```text
Query
↓
Top-k results
↓
Why retrieval is good
```

## Bad cases

For each example:

```text
Query
↓
Incorrect result
↓
Expected result
↓
Why the system failed
```

## Potential error categories specific to `recipe-with-images`

- **Synonym mismatch** — e.g. "shrimp" vs "prawn" in ingredients text.
- **Rare ingredient** — uncommon ingredient terms with few occurrences in the corpus (e.g. "sumac", "pluots" as seen in sampled rows).
- **Ambiguous query** — e.g. "salad" could mean a fruit salad or a vegetable salad.
- **Ingredients field noise** — the `ingredients` field mixes quantities, units, prep steps, and sub-headers (e.g. "Dressing:", "For serving:"), which can dilute lexical/embedding signal (see `03_DATASET.md` §6.2, §6.4).
- **No native category/cuisine label** — makes it hard to verify diversity of results automatically; relies on manual inspection.
- **Visually similar but semantically different dish** — since retrieval is text-based here, this specific error mode mainly matters if/when the image-retrieval extension (`19_FUTURE_IMAGE_RETRIEVAL` in the plan) is built.
- **Insufficient ground truth** — because relevance labels are constructed by the team (not native to the dataset), some "errors" may actually be labeling gaps rather than retrieval failures; this must be flagged when it happens.

Representative examples should be included in the final report rather than a large number of screenshots.
